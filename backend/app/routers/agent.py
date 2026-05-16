"""
Agent Gateway Router - AI Agent API 端点

参考 QuantDinger Agent Gateway 设计:
- /api/agent/v1/* 端点
- Bearer Token 认证
- Scope 权限检查
- Rate Limiting
- 审计日志
- Comprehensive Debug Logging for 20 debug cycles
"""

from __future__ import annotations

import os
import time
import logging
import traceback
from datetime import datetime
from typing import Optional, Any, Dict, List
from fastapi import APIRouter, Depends, HTTPException, Header, Request, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

# Configure comprehensive logging for 20 debug cycles
logger = logging.getLogger(__name__)

# Set DEBUG level for detailed logging during development
DEBUG_MODE = os.getenv("AGENT_API_DEBUG", "true").lower() == "true"

if DEBUG_MODE:
    logger.setLevel(logging.DEBUG)
    if not logger.handlers:
        handler = logging.StreamHandler()
        handler.setLevel(logging.DEBUG)
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - [%(funcName)s:%(lineno)d] - %(message)s'
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)

from ..services.agent.token_service import (
    AgentTokenService,
    TokenScope,
    Market,
)
from ..middleware.agent_auth import verify_agent_token, require_scope


# ─────────────────────────────────────────────────────────────────────────────
# Pydantic Models
# ─────────────────────────────────────────────────────────────────────────────

class CreateTokenRequest(BaseModel):
    name: str = Field(..., description="Token 名称")
    scopes: list[str] = Field(default=["R"], description="权限列表 (R/W/B/N/T)")
    markets: Optional[list[str]] = Field(default=None, description="可访问市场")
    instruments: Optional[list[str]] = Field(default=None, description="可交易标的")
    paper_only: bool = Field(default=True, description="是否仅模拟交易")
    rate_limit: int = Field(default=120, description="每分钟请求限制")
    expires_in_days: Optional[int] = Field(default=30, description="过期天数 (None=永不过期)")


class CreateTokenResponse(BaseModel):
    id: str
    name: str
    token: str  # 原始 Token, 仅此一次显示
    token_prefix: str
    scopes: list[str]
    markets: list[str]
    paper_only: bool
    expires_at: Optional[str]


class WhoamiResponse(BaseModel):
    id: str
    name: str
    scopes: list[str]
    markets: list[str]
    paper_only: bool
    rate_limit: int
    expires_at: Optional[str]
    last_used_at: Optional[str]


class HealthResponse(BaseModel):
    status: str = "ok"
    timestamp: int
    version: str = "0.6.12"


class MarketsResponse(BaseModel):
    markets: list[str]


class SymbolsResponse(BaseModel):
    symbols: list[dict]


class KlinesRequest(BaseModel):
    market: str
    symbol: str
    timeframe: str = Field(default="1D", description="时间周期 (1m/5m/15m/1H/4H/1D/1W)")
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    limit: int = Field(default=100, description="数据条数限制")


class KlinesResponse(BaseModel):
    market: str
    symbol: str
    timeframe: str
    data: list[dict]


class BacktestRequest(BaseModel):
    strategy_code: str = Field(..., description="策略代码")
    market: str
    symbol: str
    timeframe: str = "1D"
    start_date: str
    end_date: str
    initial_capital: float = Field(default=10000, description="初始资金")
    commission: float = Field(default=0.001, description="手续费率")
    slippage: float = Field(default=0.001, description="滑点率")


class BacktestResponse(BaseModel):
    job_id: str
    status: str = "pending"
    message: str


class JobStatusResponse(BaseModel):
    job_id: str
    status: str  # pending/running/completed/failed
    progress: Optional[float] = None
    result: Optional[dict] = None
    error: Optional[str] = None


# ─────────────────────────────────────────────────────────────────────────────
# Router & Dependencies
# ─────────────────────────────────────────────────────────────────────────────

router = APIRouter(prefix="/api/agent/v1", tags=["agent"])

# 全局服务实例
_token_service: Optional[AgentTokenService] = None


def get_token_service() -> AgentTokenService:
    global _token_service
    if _token_service is None:
        _token_service = AgentTokenService()
    return _token_service


def _verify_admin(admin_auth: Optional[str], x_admin_auth: Optional[str] = None) -> bool:
    """验证 admin token。支持 Header 或 X-Admin-Auth 方式。"""
    auth_value = x_admin_auth or admin_auth
    if auth_value is None:
        return False
    
    # Check if it's a session token (64 char hex)
    if len(auth_value) == 64 and all(c in '0123456789abcdef' for c in auth_value.lower()):
        from app.routers.admin import _validate_admin_session, _cleanup_expired_sessions
        _cleanup_expired_sessions()
        return _validate_admin_session(auth_value)
    
    # Legacy support for admin_ prefixed tokens (deprecated)
    return auth_value.startswith("admin_") or auth_value == "admin_ui"


# ─────────────────────────────────────────────────────────────────────────────
# Public Endpoints (No Auth Required)
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/health", response_model=HealthResponse)
async def health(request: Request):
    """
    Public health check endpoint (no authentication required).
    
    Returns:
        HealthResponse: Service status and timestamp
    """
    request_id = id(request)
    start_time = time.time()
    
    logger.info(f"[AGENT_HEALTH] Health check requested | request_id={request_id}")
    logger.debug(f"[AGENT_HEALTH] Request details | path={request.url.path} method={request.method}")
    logger.debug(f"[AGENT_HEALTH] Client info | ip={request.client.host if request.client else 'unknown'}")
    
    try:
        response_data = HealthResponse(
            status="ok",
            timestamp=str(int(time.time())),
            version="0.6.12"
        )
        
        duration = time.time() - start_time
        logger.info(f"[AGENT_HEALTH] Health check successful | request_id={request_id} duration={duration:.3f}s")
        logger.debug(f"[AGENT_HEALTH] Response | status={response_data.status} version={response_data.version}")
        
        return response_data
        
    except Exception as e:
        duration = time.time() - start_time
        logger.error(f"[AGENT_HEALTH] Health check failed | request_id={request_id} error={str(e)} duration={duration:.3f}s")
        logger.error(f"[AGENT_HEALTH] Stack trace:\n{traceback.format_exc()}")
        raise HTTPException(status_code=500, detail="Health check failed")


# ─────────────────────────────────────────────────────────────────────────────
# Token Management (Admin)
# ─────────────────────────────────────────────────────────────────────────────

@router.post("/admin/tokens")
async def create_token(
    request: CreateTokenRequest,
    admin_auth: Optional[str] = Header(None, description="Admin JWT Token"),
    x_admin_auth: Optional[str] = Header(None, alias="X-Admin-Auth", description="Admin UI Auth"),
):
    """
    创建新的 Agent Token (需 Admin 权限)
    
    Token 仅在此刻显示一次, 请妥善保管。
    """
    if not _verify_admin(admin_auth, x_admin_auth):
        raise HTTPException(status_code=403, detail="Invalid admin token")
    
    service = get_token_service()
    
    scope_enums = [TokenScope(s) if isinstance(s, str) else s for s in request.scopes]
    
    raw_token, token = service.create_token(
        name=request.name,
        scopes=scope_enums,
        markets=request.markets,
        instruments=request.instruments,
        paper_only=request.paper_only,
        rate_limit=request.rate_limit,
        expires_in_days=request.expires_in_days,
    )
    
    return {
        "code": 0,
        "message": "success",
        "data": {
            "id": token.id,
            "name": token.name,
            "token": raw_token,
            "token_prefix": token.token_prefix,
            "scopes": token.scopes,
            "markets": token.markets,
            "paper_only": token.paper_only,
            "expires_at": token.expires_at.isoformat() if token.expires_at else None,
        }
    }


@router.get("/admin/tokens")
async def list_tokens(
    admin_auth: Optional[str] = Header(None, description="Admin JWT Token"),
    x_admin_auth: Optional[str] = Header(None, alias="X-Admin-Auth", description="Admin UI Auth"),
    include_inactive: bool = False,
):
    """列出所有 Token (需 Admin 权限)"""
    if not _verify_admin(admin_auth, x_admin_auth):
        raise HTTPException(status_code=403, detail="Invalid admin token")
    
    service = get_token_service()
    tokens = service.list_tokens(include_inactive=include_inactive)
    return {
        "code": 0,
        "message": "success",
        "data": [t.to_dict() for t in tokens]
    }


@router.delete("/admin/tokens/{token_id}")
async def revoke_token(
    token_id: str,
    admin_auth: Optional[str] = Header(None, description="Admin JWT Token"),
    x_admin_auth: Optional[str] = Header(None, alias="X-Admin-Auth", description="Admin UI Auth"),
):
    """吊销 Token (需 Admin 权限)"""
    if not _verify_admin(admin_auth, x_admin_auth):
        raise HTTPException(status_code=403, detail="Invalid admin token")
    
    service = get_token_service()
    success = service.revoke_token(token_id)
    if not success:
        raise HTTPException(status_code=404, detail="Token not found")
    return {
        "code": 0,
        "message": "success",
        "data": {"status": "ok", "message": f"Token {token_id} revoked"}
    }


# ─────────────────────────────────────────────────────────────────────────────
# Token Info (Auth Required)
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/whoami", response_model=WhoamiResponse)
async def whoami(
    request: Request,
    token: Any = Depends(verify_agent_token)
):
    """
    Get current token identity and permissions.
    
    Requires valid Bearer token authentication.
    
    Returns:
        WhoamiResponse: Token details including scopes, markets, and usage stats
    """
    request_id = id(request)
    start_time = time.time()
    
    logger.info(f"[AGENT_WHOAMI] Whoami requested | request_id={request_id} token_id={token.id}")
    logger.debug(f"[AGENT_WHOAMI] Request details | path={request.url.path} method={request.method}")
    logger.debug(f"[AGENT_WHOAMI] Token details | name={token.name} scopes={[s.value for s in token.scopes]}")
    logger.debug(f"[AGENT_WHOAMI] Token permissions | markets={token.markets} paper_only={token.paper_only}")
    
    try:
        response_data = WhoamiResponse(
            id=token.id,
            name=token.name,
            scopes=[s.value for s in token.scopes],
            markets=token.markets,
            paper_only=token.paper_only,
            rate_limit=token.rate_limit,
            expires_at=token.expires_at.isoformat() if token.expires_at else None,
            last_used_at=token.last_used_at.isoformat() if token.last_used_at else None,
        )
        
        duration = time.time() - start_time
        logger.info(f"[AGENT_WHOAMI] Whoami successful | request_id={request_id} token_id={token.id} duration={duration:.3f}s")
        logger.debug(f"[AGENT_WHOAMI] Response | id={response_data.id} name={response_data.name} scopes={response_data.scopes}")
        
        return response_data
        
    except Exception as e:
        duration = time.time() - start_time
        logger.error(f"[AGENT_WHOAMI] Whoami failed | request_id={request_id} token_id={token.id} error={str(e)} duration={duration:.3f}s")
        logger.error(f"[AGENT_WHOAMI] Stack trace:\n{traceback.format_exc()}")
        raise HTTPException(status_code=500, detail="Failed to get token info")


# ─────────────────────────────────────────────────────────────────────────────
# Read Operations (R Scope)
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/markets", response_model=MarketsResponse)
async def list_markets(
    request: Request,
    token: Any = Depends(require_scope(TokenScope.READ))
):
    """
    List available markets.
    
    Requires R (Read) scope.
    Returns markets filtered by token permissions.
    
    Returns:
        MarketsResponse: List of available markets
    """
    request_id = id(request)
    start_time = time.time()
    
    logger.info(f"[AGENT_MARKETS] List markets requested | request_id={request_id} token_id={token.id}")
    logger.debug(f"[AGENT_MARKETS] Request details | path={request.url.path} method={request.method}")
    logger.debug(f"[AGENT_MARKETS] Token markets | markets={token.markets}")
    
    try:
        service = get_token_service()
        
        all_markets = [m.value for m in Market]
        logger.debug(f"[AGENT_MARKETS] All available markets | markets={all_markets}")
        
        if "*" in token.markets:
            allowed_markets = all_markets
            logger.debug(f"[AGENT_MARKETS] Token has wildcard access | returning all markets")
        else:
            allowed_markets = [m for m in all_markets if m in token.markets]
            logger.debug(f"[AGENT_MARKETS] Filtered markets | allowed={allowed_markets}")
        
        service.log_audit(
            token.id, 
            "list_markets", 
            "/markets",
            details={"markets_count": len(allowed_markets)}
        )
        
        response_data = MarketsResponse(markets=allowed_markets)
        
        duration = time.time() - start_time
        logger.info(f"[AGENT_MARKETS] List markets successful | request_id={request_id} token_id={token.id} markets_count={len(allowed_markets)} duration={duration:.3f}s")
        logger.debug(f"[AGENT_MARKETS] Response | markets={allowed_markets}")
        
        return response_data
        
    except Exception as e:
        duration = time.time() - start_time
        logger.error(f"[AGENT_MARKETS] List markets failed | request_id={request_id} token_id={token.id} error={str(e)} duration={duration:.3f}s")
        logger.error(f"[AGENT_MARKETS] Stack trace:\n{traceback.format_exc()}")
        raise HTTPException(status_code=500, detail="Failed to list markets")


@router.get("/markets/{market}/symbols", response_model=SymbolsResponse)
async def search_symbols(
    request: Request,
    market: str,
    keyword: str = Query("", description="Search keyword"),
    limit: int = Query(20, description="Maximum results", ge=1, le=100),
    token: Any = Depends(require_scope(TokenScope.READ)),
):
    """
    Search symbols in a specific market.
    
    Requires R (Read) scope.
    Market access is filtered by token permissions.
    
    Args:
        market: Market code (AStock/HKStock/USStock/Crypto/Forex/Futures)
        keyword: Search keyword
        limit: Maximum number of results (1-100)
        
    Returns:
        SymbolsResponse: List of matching symbols
    """
    request_id = id(request)
    start_time = time.time()
    
    logger.info(f"[AGENT_SYMBOLS] Search symbols requested | request_id={request_id} token_id={token.id} market={market}")
    logger.debug(f"[AGENT_SYMBOLS] Request details | path={request.url.path} method={request.method}")
    logger.debug(f"[AGENT_SYMBOLS] Search parameters | keyword={keyword} limit={limit}")
    logger.debug(f"[AGENT_SYMBOLS] Token markets | markets={token.markets}")
    
    if not token.can_access_market(market):
        logger.warning(f"[AGENT_SYMBOLS] Market access denied | token_id={token.id} market={market} allowed_markets={token.markets}")
        raise HTTPException(status_code=403, detail=f"Market {market} not allowed")
    
    logger.debug(f"[AGENT_SYMBOLS] Market access granted | market={market}")
    
    try:
        service = get_token_service()
        service.log_audit(
            token.id, "search_symbols", f"/markets/{market}/symbols",
            details={"market": market, "keyword": keyword, "limit": limit}
        )
        
        from app.routers.stocks import search_stocks as _search_stocks
        results = await _search_stocks(q=keyword)
        
        logger.debug(f"[AGENT_SYMBOLS] Search results | total={len(results.get('data', {}).get('stocks', []))}")
        
        market_prefix_map = {
            "AStock": ("sh", "sz"),
            "HKStock": ("hk",),
            "USStock": ("us",),
        }
        prefixes = market_prefix_map.get(market, ())
        
        filtered = []
        for item in results.get("data", {}).get("stocks", [])[:50]:
            code = item.get("code", "")
            if prefixes:
                if any(code.startswith(p) for p in prefixes):
                    filtered.append({
                        "symbol": code.lstrip("shszHK").lstrip("0").lstrip("hk").lstrip("us") or code,
                        "name": item.get("name", ""),
                        "market": market,
                        "code": code,
                    })
            else:
                filtered.append({
                    "symbol": code,
                    "name": item.get("name", ""),
                    "market": market,
                    "code": code,
                })
            if len(filtered) >= limit:
                break
        
        response_data = SymbolsResponse(symbols=filtered)
        
        duration = time.time() - start_time
        logger.info(f"[AGENT_SYMBOLS] Search symbols successful | request_id={request_id} token_id={token.id} market={market} results={len(filtered)} duration={duration:.3f}s")
        logger.debug(f"[AGENT_SYMBOLS] Response | symbols_count={len(filtered)}")
        
        return response_data
        
    except HTTPException as e:
        logger.debug(f"[AGENT_SYMBOLS] HTTPException re-raised: {e.detail}")
        raise
    except Exception as e:
        duration = time.time() - start_time
        logger.warning(f"[AGENT_SYMBOLS] Search symbols fallback | request_id={request_id} error={str(e)} duration={duration:.3f}s")
        logger.debug(f"[AGENT_SYMBOLS] Returning empty results due to error")
        return SymbolsResponse(symbols=[])


@router.post("/klines", response_model=KlinesResponse)
async def get_klines(
    request: Request,
    kline_request: KlinesRequest,
    token: Any = Depends(require_scope(TokenScope.READ)),
):
    """
    Get K-line (candlestick) data for a symbol.
    
    Requires R (Read) scope.
    Market access is filtered by token permissions.
    
    Args:
        kline_request: K-line request parameters
        
    Returns:
        KlinesResponse: K-line data with OHLCV
    """
    request_id = id(request)
    start_time = time.time()
    
    logger.info(f"[AGENT_KLINES] Get klines requested | request_id={request_id} token_id={token.id} market={kline_request.market} symbol={kline_request.symbol}")
    logger.debug(f"[AGENT_KLINES] Request details | path={request.url.path} method={request.method}")
    logger.debug(f"[AGENT_KLINES] K-line parameters | timeframe={kline_request.timeframe} limit={kline_request.limit} start={kline_request.start_date} end={kline_request.end_date}")
    
    if not token.can_access_market(kline_request.market):
        logger.warning(f"[AGENT_KLINES] Market access denied | token_id={token.id} market={kline_request.market} allowed_markets={token.markets}")
        raise HTTPException(status_code=403, detail=f"Market {kline_request.market} not allowed")
    
    logger.debug(f"[AGENT_KLINES] Market access granted | market={kline_request.market}")
    
    try:
        service = get_token_service()
        service.log_audit(
            token.id, "get_klines", "/klines",
            details={
                "market": kline_request.market,
                "symbol": kline_request.symbol,
                "timeframe": kline_request.timeframe,
                "limit": kline_request.limit,
            }
        )
        
        from app.db import get_periodic_history
        
        symbol = kline_request.symbol
        if kline_request.market == "AStock":
            symbol = symbol
        elif kline_request.market == "HKStock":
            symbol = f"hk{symbol}"
        elif kline_request.market == "USStock":
            symbol = f"us{symbol}"
        
        logger.debug(f"[AGENT_KLINES] Symbol mapping | original={kline_request.symbol} mapped={symbol}")
        
        period_map = {"1m": "1min", "5m": "5min", "15m": "15min", "1H": "60min", "4H": "60min", "1D": "daily", "1W": "weekly"}
        period = period_map.get(kline_request.timeframe, "daily")
        
        logger.debug(f"[AGENT_KLINES] Period mapping | timeframe={kline_request.timeframe} period={period}")
        
        limit = min(kline_request.limit, 1000)
        
        logger.debug(f"[AGENT_KLINES] Fetching data | symbol={symbol} period={period} limit={limit}")
        rows = get_periodic_history(symbol, period=period, limit=limit)
        
        logger.debug(f"[AGENT_KLINES] Data fetched | rows_count={len(rows)}")
        
        data = []
        for row in rows:
            data.append({
                "timestamp": row.get("trade_date", ""),
                "open": float(row.get("open", 0)),
                "high": float(row.get("high", 0)),
                "low": float(row.get("low", 0)),
                "close": float(row.get("close", 0)),
                "volume": float(row.get("volume", 0)),
            })
        
        response_data = KlinesResponse(
            market=kline_request.market,
            symbol=kline_request.symbol,
            timeframe=kline_request.timeframe,
            data=data,
        )
        
        duration = time.time() - start_time
        logger.info(f"[AGENT_KLINES] Get klines successful | request_id={request_id} token_id={token.id} symbol={kline_request.symbol} data_points={len(data)} duration={duration:.3f}s")
        logger.debug(f"[AGENT_KLINES] Response | market={response_data.market} symbol={response_data.symbol} timeframe={response_data.timeframe} data_count={len(response_data.data)}")
        
        return response_data
        
    except HTTPException as e:
        logger.debug(f"[AGENT_SYMBOLS] HTTPException re-raised: {e.detail}")
        raise
    except Exception as e:
        duration = time.time() - start_time
        logger.warning(f"[AGENT_KLINES] Get klines fallback | request_id={request_id} error={str(e)} duration={duration:.3f}s")
        logger.debug(f"[AGENT_KLINES] Returning empty data due to error")
        return KlinesResponse(
            market=kline_request.market,
            symbol=kline_request.symbol,
            timeframe=kline_request.timeframe,
            data=[],
        )


@router.get("/price")
async def get_price(
    request: Request,
    market: str = Query(..., description="Market code"),
    symbol: str = Query(..., description="Symbol code"),
    token: Any = Depends(require_scope(TokenScope.READ)),
):
    """
    Get latest price for a symbol.
    
    Requires R (Read) scope.
    Market and instrument access are filtered by token permissions.
    
    Args:
        market: Market code (AStock/HKStock/USStock/Crypto/Forex/Futures)
        symbol: Symbol code
        
    Returns:
        Latest price data with change and volume
    """
    request_id = id(request)
    start_time = time.time()
    
    logger.info(f"[AGENT_PRICE] Get price requested | request_id={request_id} token_id={token.id} market={market} symbol={symbol}")
    logger.debug(f"[AGENT_PRICE] Request details | path={request.url.path} method={request.method}")
    logger.debug(f"[AGENT_PRICE] Token permissions | markets={token.markets} instruments={token.instruments}")
    
    if not token.can_access_market(market):
        logger.warning(f"[AGENT_PRICE] Market access denied | token_id={token.id} market={market} allowed_markets={token.markets}")
        raise HTTPException(status_code=403, detail=f"Market {market} not allowed")
    
    if not token.can_access_instrument(symbol):
        logger.warning(f"[AGENT_PRICE] Instrument access denied | token_id={token.id} symbol={symbol} allowed_instruments={token.instruments}")
        raise HTTPException(status_code=403, detail=f"Instrument {symbol} not allowed")
    
    logger.debug(f"[AGENT_PRICE] Access granted | market={market} symbol={symbol}")
    
    try:
        service = get_token_service()
        service.log_audit(
            token.id, "get_price", "/price",
            details={"market": market, "symbol": symbol}
        )
        
        from app.routers.market import market_quote
        
        sym = symbol
        if market == "AStock":
            if not symbol.startswith(("sh", "sz")):
                sym = f"sh{symbol}" if symbol.startswith("6") else f"sz{symbol}"
        elif market == "HKStock":
            sym = f"hk{symbol}"
        elif market == "USStock":
            sym = f"us{symbol}"
        
        logger.debug(f"[AGENT_PRICE] Symbol mapping | original={symbol} mapped={sym}")
        
        quote = await market_quote(sym)
        
        logger.debug(f"[AGENT_PRICE] Quote fetched | has_data={'data' in quote}")
        
        if "data" in quote:
            data = quote["data"]
            response_data = {
                "market": market,
                "symbol": symbol,
                "price": data.get("price", 0),
                "change": data.get("price_change", 0),
                "change_pct": data.get("pct_change", 0),
                "volume": data.get("volume", 0),
                "timestamp": int(time.time()),
            }
            
            duration = time.time() - start_time
            logger.info(f"[AGENT_PRICE] Get price successful | request_id={request_id} token_id={token.id} symbol={symbol} price={response_data['price']} duration={duration:.3f}s")
            logger.debug(f"[AGENT_PRICE] Response | price={response_data['price']} change={response_data['change']} change_pct={response_data['change_pct']}")
            
            return response_data
        
    except HTTPException as e:
        logger.debug(f"[AGENT_SYMBOLS] HTTPException re-raised: {e.detail}")
        raise
    except Exception as e:
        duration = time.time() - start_time
        logger.warning(f"[AGENT_PRICE] Get price fallback | request_id={request_id} error={str(e)} duration={duration:.3f}s")
    
    fallback_data = {
        "market": market,
        "symbol": symbol,
        "price": 0,
        "change": 0,
        "change_pct": 0,
        "timestamp": int(time.time()),
        "error": "Failed to fetch price",
    }
    
    logger.debug(f"[AGENT_PRICE] Returning fallback data | symbol={symbol}")
    return fallback_data


# ─────────────────────────────────────────────────────────────────────────────
# Strategy Management (R/W Scope)
# ─────────────────────────────────────────────────────────────────────────────

class StrategyListResponse(BaseModel):
    strategies: list[dict]
    total: int
    limit: int
    offset: int
    has_more: bool


class StrategyDetailResponse(BaseModel):
    id: str
    name: str
    description: str
    code: str
    market: str
    parameters: dict
    stop_loss_pct: float
    take_profit_pct: float
    created_at: str
    updated_at: str


class StrategyCreateRequest(BaseModel):
    name: str = Field(..., description="Strategy name", min_length=1, max_length=100)
    description: str = Field(default="", description="Strategy description", max_length=500)
    code: str = Field(..., description="Strategy code", min_length=1)
    market: str = Field(default="AStock", description="Target market")
    parameters: dict = Field(default_factory=dict, description="Strategy parameters")
    stop_loss_pct: float = Field(default=2.0, description="Stop loss percentage", ge=0, le=100)
    take_profit_pct: float = Field(default=6.0, description="Take profit percentage", ge=0, le=100)


class StrategyUpdateRequest(BaseModel):
    name: Optional[str] = Field(None, description="Strategy name", min_length=1, max_length=100)
    description: Optional[str] = Field(None, description="Strategy description", max_length=500)
    code: Optional[str] = Field(None, description="Strategy code", min_length=1)
    market: Optional[str] = Field(None, description="Target market")
    parameters: Optional[dict] = Field(None, description="Strategy parameters")
    stop_loss_pct: Optional[float] = Field(None, description="Stop loss percentage", ge=0, le=100)
    take_profit_pct: Optional[float] = Field(None, description="Take profit percentage", ge=0, le=100)


@router.get("/strategies", response_model=StrategyListResponse)
async def list_strategies(
    request: Request,
    limit: int = Query(20, description="Maximum results", ge=1, le=100),
    offset: int = Query(0, description="Offset for pagination", ge=0),
    market: Optional[str] = Query(None, description="Filter by market"),
    status: Optional[str] = Query(None, description="Filter by status (active/deleted)"),
    token: Any = Depends(require_scope(TokenScope.READ)),
):
    """
    List strategies with pagination and filtering.
    
    Requires R (Read) scope.
    Supports pagination (limit/offset) and filtering (by market, status).
    
    Args:
        limit: Maximum number of results (1-100, default 20)
        offset: Offset for pagination (default 0)
        market: Filter by market (AStock/HKStock/USStock/etc.)
        status: Filter by status (active/deleted)
        
    Returns:
        StrategyListResponse: Paginated list of strategies
    """
    request_id = id(request)
    start_time = time.time()
    
    logger.info(f"[AGENT_STRATEGIES_LIST] List strategies requested | request_id={request_id} token_id={token.id}")
    logger.debug(f"[AGENT_STRATEGIES_LIST] Request details | path={request.url.path} method={request.method}")
    logger.debug(f"[AGENT_STRATEGIES_LIST] Pagination params | limit={limit} offset={offset}")
    logger.debug(f"[AGENT_STRATEGIES_LIST] Filter params | market={market} status={status}")
    logger.debug(f"[AGENT_STRATEGIES_LIST] Token markets | markets={token.markets}")
    
    try:
        service = get_token_service()
        
        # Check market access if filtering by market
        if market and not token.can_access_market(market):
            logger.warning(f"[AGENT_STRATEGIES_LIST] Market access denied | token_id={token.id} market={market} allowed_markets={token.markets}")
            raise HTTPException(status_code=403, detail=f"Market {market} not allowed")
        
        logger.debug(f"[AGENT_STRATEGIES_LIST] Market access check passed")
        
        # Import strategy_db functions
        from app.db.strategy_db import list_strategies as db_list_strategies, count_strategies as db_count_strategies
        
        # Build query parameters
        include_deleted = status == "deleted"
        filter_market = market if market else None
        
        logger.debug(f"[AGENT_STRATEGIES_LIST] Query params | include_deleted={include_deleted} filter_market={filter_market}")
        
        # Get strategies from database
        strategies = db_list_strategies(
            market=filter_market,
            include_deleted=include_deleted,
            limit=limit,
            offset=offset,
        )
        
        logger.debug(f"[AGENT_STRATEGIES_LIST] Query results | strategies_count={len(strategies)}")
        
        # Get total count
        total = db_count_strategies(market=filter_market, include_deleted=include_deleted)
        
        logger.debug(f"[AGENT_STRATEGIES_LIST] Total count | total={total}")
        
        # Calculate has_more
        has_more = (offset + len(strategies)) < total
        
        logger.debug(f"[AGENT_STRATEGIES_LIST] Pagination info | has_more={has_more}")
        
        # Filter strategies by token market access (if token has restricted markets)
        if "*" not in token.markets:
            allowed_markets = set(token.markets)
            strategies = [s for s in strategies if s.get("market", "AStock") in allowed_markets or s.get("market") is None]
            logger.debug(f"[AGENT_STRATEGIES_LIST] Filtered by token markets | filtered_count={len(strategies)}")
        
        # Log audit
        service.log_audit(
            token.id, "list_strategies", "/strategies",
            details={
                "limit": limit,
                "offset": offset,
                "market": market,
                "status": status,
                "results_count": len(strategies),
                "total": total,
            }
        )
        
        # Build response (exclude code field for list view)
        strategy_list = []
        for s in strategies:
            strategy_list.append({
                "id": s.get("id", ""),
                "name": s.get("name", ""),
                "description": s.get("description", ""),
                "market": s.get("market", "AStock"),
                "created_at": s.get("created_at", ""),
                "updated_at": s.get("updated_at", ""),
            })
        
        response_data = StrategyListResponse(
            strategies=strategy_list,
            total=total,
            limit=limit,
            offset=offset,
            has_more=has_more,
        )
        
        duration = time.time() - start_time
        logger.info(f"[AGENT_STRATEGIES_LIST] List strategies successful | request_id={request_id} token_id={token.id} results={len(strategy_list)} total={total} duration={duration:.3f}s")
        logger.debug(f"[AGENT_STRATEGIES_LIST] Response | limit={response_data.limit} offset={response_data.offset} has_more={response_data.has_more}")
        
        return response_data
        
    except HTTPException as e:
        logger.debug(f"[AGENT_SYMBOLS] HTTPException re-raised: {e.detail}")
        raise
    except Exception as e:
        duration = time.time() - start_time
        logger.error(f"[AGENT_STRATEGIES_LIST] List strategies failed | request_id={request_id} token_id={token.id} error={str(e)} duration={duration:.3f}s")
        logger.error(f"[AGENT_STRATEGIES_LIST] Stack trace:\n{traceback.format_exc()}")
        raise HTTPException(status_code=500, detail="Failed to list strategies")


@router.get("/strategies/{strategy_id}", response_model=StrategyDetailResponse)
async def get_strategy(
    request: Request,
    strategy_id: str,
    token: Any = Depends(require_scope(TokenScope.READ)),
):
    """
    Get strategy details by ID.
    
    Requires R (Read) scope.
    Market access is filtered by token permissions.
    
    Args:
        strategy_id: Strategy ID
        
    Returns:
        StrategyDetailResponse: Full strategy details including code
    """
    request_id = id(request)
    start_time = time.time()
    
    logger.info(f"[AGENT_STRATEGY_GET] Get strategy requested | request_id={request_id} token_id={token.id} strategy_id={strategy_id}")
    logger.debug(f"[AGENT_STRATEGY_GET] Request details | path={request.url.path} method={request.method}")
    logger.debug(f"[AGENT_STRATEGY_GET] Token markets | markets={token.markets}")
    
    try:
        service = get_token_service()
        
        # Import strategy_db function
        from app.db.strategy_db import get_strategy as db_get_strategy
        
        logger.debug(f"[AGENT_STRATEGY_GET] Fetching strategy from database | strategy_id={strategy_id}")
        
        # Get strategy from database
        strategy = db_get_strategy(strategy_id)
        
        if strategy is None:
            logger.warning(f"[AGENT_STRATEGY_GET] Strategy not found | strategy_id={strategy_id}")
            raise HTTPException(status_code=404, detail=f"Strategy {strategy_id} not found")
        
        logger.debug(f"[AGENT_STRATEGY_GET] Strategy found | name={strategy.get('name')} market={strategy.get('market')}")
        
        # Check market access
        strategy_market = strategy.get("market", "AStock")
        if not token.can_access_market(strategy_market):
            logger.warning(f"[AGENT_STRATEGY_GET] Market access denied | token_id={token.id} strategy_market={strategy_market} allowed_markets={token.markets}")
            raise HTTPException(status_code=403, detail=f"Market {strategy_market} not allowed")
        
        logger.debug(f"[AGENT_STRATEGY_GET] Market access granted | market={strategy_market}")
        
        # Log audit
        service.log_audit(
            token.id, "get_strategy", f"/strategies/{strategy_id}",
            details={
                "strategy_id": strategy_id,
                "strategy_name": strategy.get("name"),
                "market": strategy_market,
            }
        )
        
        response_data = StrategyDetailResponse(
            id=strategy.get("id", ""),
            name=strategy.get("name", ""),
            description=strategy.get("description", ""),
            code=strategy.get("code", ""),
            market=strategy_market,
            parameters=strategy.get("parameters", {}),
            stop_loss_pct=strategy.get("stop_loss_pct", 2.0),
            take_profit_pct=strategy.get("take_profit_pct", 6.0),
            created_at=strategy.get("created_at", ""),
            updated_at=strategy.get("updated_at", ""),
        )
        
        duration = time.time() - start_time
        logger.info(f"[AGENT_STRATEGY_GET] Get strategy successful | request_id={request_id} token_id={token.id} strategy_id={strategy_id} duration={duration:.3f}s")
        logger.debug(f"[AGENT_STRATEGY_GET] Response | id={response_data.id} name={response_data.name} market={response_data.market}")
        
        return response_data
        
    except HTTPException as e:
        logger.debug(f"[AGENT_SYMBOLS] HTTPException re-raised: {e.detail}")
        raise
    except Exception as e:
        duration = time.time() - start_time
        logger.error(f"[AGENT_STRATEGY_GET] Get strategy failed | request_id={request_id} token_id={token.id} strategy_id={strategy_id} error={str(e)} duration={duration:.3f}s")
        logger.error(f"[AGENT_STRATEGY_GET] Stack trace:\n{traceback.format_exc()}")
        raise HTTPException(status_code=500, detail="Failed to get strategy")


@router.post("/strategies")
async def create_strategy(
    request: Request,
    strategy_request: StrategyCreateRequest,
    token: Any = Depends(require_scope(TokenScope.WRITE)),
):
    """
    Create a new strategy.
    
    Requires W (Write) scope.
    Market access is validated against token permissions.
    Strategy code is validated before saving.
    
    Args:
        strategy_request: Strategy creation parameters
        
    Returns:
        Created strategy ID and confirmation
    """
    request_id = id(request)
    start_time = time.time()
    
    logger.info(f"[AGENT_STRATEGY_CREATE] Create strategy requested | request_id={request_id} token_id={token.id}")
    logger.debug(f"[AGENT_STRATEGY_CREATE] Request details | path={request.url.path} method={request.method}")
    logger.debug(f"[AGENT_STRATEGY_CREATE] Strategy params | name={strategy_request.name} market={strategy_request.market}")
    logger.debug(f"[AGENT_STRATEGY_CREATE] Strategy details | stop_loss={strategy_request.stop_loss_pct} take_profit={strategy_request.take_profit_pct}")
    logger.debug(f"[AGENT_STRATEGY_CREATE] Code length | code_length={len(strategy_request.code)}")
    logger.debug(f"[AGENT_STRATEGY_CREATE] Token markets | markets={token.markets}")
    
    # Check market access
    if not token.can_access_market(strategy_request.market):
        logger.warning(f"[AGENT_STRATEGY_CREATE] Market access denied | token_id={token.id} market={strategy_request.market} allowed_markets={token.markets}")
        raise HTTPException(status_code=403, detail=f"Market {strategy_request.market} not allowed")
    
    logger.debug(f"[AGENT_STRATEGY_CREATE] Market access granted | market={strategy_request.market}")
    
    try:
        service = get_token_service()
        
        # Validate strategy code
        logger.debug(f"[AGENT_STRATEGY_CREATE] Validating strategy code")
        from app.services.strategy import StrategyValidator
        
        is_valid, error = StrategyValidator.validate(strategy_request.code)
        if not is_valid:
            logger.warning(f"[AGENT_STRATEGY_CREATE] Strategy validation failed | error={error}")
            raise HTTPException(status_code=400, detail=f"Strategy code validation failed: {error}")
        
        logger.debug(f"[AGENT_STRATEGY_CREATE] Strategy code validated successfully")
        
        # Generate strategy ID
        import uuid
        strategy_id = str(uuid.uuid4())
        
        logger.debug(f"[AGENT_STRATEGY_CREATE] Generated strategy_id | strategy_id={strategy_id}")
        
        # Create strategy in database
        from app.db.strategy_db import create_strategy as db_create_strategy
        
        logger.debug(f"[AGENT_STRATEGY_CREATE] Creating strategy in database")
        
        created_strategy = db_create_strategy(
            strategy_id=strategy_id,
            name=strategy_request.name,
            description=strategy_request.description,
            code=strategy_request.code,
            market=strategy_request.market,
            parameters=strategy_request.parameters,
            stop_loss_pct=strategy_request.stop_loss_pct,
            take_profit_pct=strategy_request.take_profit_pct,
        )
        
        logger.debug(f"[AGENT_STRATEGY_CREATE] Strategy created | strategy_id={strategy_id}")
        
        # Log audit
        service.log_audit(
            token.id, "create_strategy", "/strategies",
            details={
                "strategy_id": strategy_id,
                "strategy_name": strategy_request.name,
                "market": strategy_request.market,
                "code_length": len(strategy_request.code),
            }
        )
        
        duration = time.time() - start_time
        logger.info(f"[AGENT_STRATEGY_CREATE] Create strategy successful | request_id={request_id} token_id={token.id} strategy_id={strategy_id} duration={duration:.3f}s")
        logger.debug(f"[AGENT_STRATEGY_CREATE] Response | strategy_id={strategy_id} name={strategy_request.name}")
        
        return {
            "code": 0,
            "message": "Strategy created successfully",
            "data": {
                "id": strategy_id,
                "name": strategy_request.name,
                "market": strategy_request.market,
            }
        }
        
    except HTTPException as e:
        logger.debug(f"[AGENT_SYMBOLS] HTTPException re-raised: {e.detail}")
        raise
    except ValueError as e:
        duration = time.time() - start_time
        logger.warning(f"[AGENT_STRATEGY_CREATE] Strategy creation failed (duplicate) | request_id={request_id} error={str(e)} duration={duration:.3f}s")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        duration = time.time() - start_time
        logger.error(f"[AGENT_STRATEGY_CREATE] Create strategy failed | request_id={request_id} token_id={token.id} error={str(e)} duration={duration:.3f}s")
        logger.error(f"[AGENT_STRATEGY_CREATE] Stack trace:\n{traceback.format_exc()}")
        raise HTTPException(status_code=500, detail="Failed to create strategy")


@router.put("/strategies/{strategy_id}")
async def update_strategy(
    request: Request,
    strategy_id: str,
    strategy_request: StrategyUpdateRequest,
    token: Any = Depends(require_scope(TokenScope.WRITE)),
):
    """
    Update an existing strategy.
    
    Requires W (Write) scope.
    Market access is validated against token permissions.
    Strategy code is validated if provided.
    
    Args:
        strategy_id: Strategy ID to update
        strategy_request: Strategy update parameters (partial update)
        
    Returns:
        Updated strategy confirmation
    """
    request_id = id(request)
    start_time = time.time()
    
    logger.info(f"[AGENT_STRATEGY_UPDATE] Update strategy requested | request_id={request_id} token_id={token.id} strategy_id={strategy_id}")
    logger.debug(f"[AGENT_STRATEGY_UPDATE] Request details | path={request.url.path} method={request.method}")
    logger.debug(f"[AGENT_STRATEGY_UPDATE] Update params | name={strategy_request.name} market={strategy_request.market}")
    logger.debug(f"[AGENT_STRATEGY_UPDATE] Token markets | markets={token.markets}")
    
    try:
        service = get_token_service()
        
        # Import strategy_db functions
        from app.db.strategy_db import get_strategy as db_get_strategy, update_strategy as db_update_strategy
        
        logger.debug(f"[AGENT_STRATEGY_UPDATE] Fetching existing strategy | strategy_id={strategy_id}")
        
        # Get existing strategy
        existing_strategy = db_get_strategy(strategy_id)
        if existing_strategy is None:
            logger.warning(f"[AGENT_STRATEGY_UPDATE] Strategy not found | strategy_id={strategy_id}")
            raise HTTPException(status_code=404, detail=f"Strategy {strategy_id} not found")
        
        logger.debug(f"[AGENT_STRATEGY_UPDATE] Existing strategy found | name={existing_strategy.get('name')} market={existing_strategy.get('market')}")
        
        # Check market access for existing strategy
        existing_market = existing_strategy.get("market", "AStock")
        if not token.can_access_market(existing_market):
            logger.warning(f"[AGENT_STRATEGY_UPDATE] Market access denied for existing | token_id={token.id} market={existing_market} allowed_markets={token.markets}")
            raise HTTPException(status_code=403, detail=f"Market {existing_market} not allowed")
        
        # Check market access for new market if provided
        if strategy_request.market and not token.can_access_market(strategy_request.market):
            logger.warning(f"[AGENT_STRATEGY_UPDATE] Market access denied for new market | token_id={token.id} market={strategy_request.market} allowed_markets={token.markets}")
            raise HTTPException(status_code=403, detail=f"Market {strategy_request.market} not allowed")
        
        logger.debug(f"[AGENT_STRATEGY_UPDATE] Market access granted")
        
        # Validate strategy code if provided
        if strategy_request.code is not None:
            logger.debug(f"[AGENT_STRATEGY_UPDATE] Validating new strategy code | code_length={len(strategy_request.code)}")
            from app.services.strategy import StrategyValidator
            
            is_valid, error = StrategyValidator.validate(strategy_request.code)
            if not is_valid:
                logger.warning(f"[AGENT_STRATEGY_UPDATE] Strategy validation failed | error={error}")
                raise HTTPException(status_code=400, detail=f"Strategy code validation failed: {error}")
            
            logger.debug(f"[AGENT_STRATEGY_UPDATE] Strategy code validated successfully")
        
        logger.debug(f"[AGENT_STRATEGY_UPDATE] Updating strategy in database")
        
        # Update strategy in database
        updated_strategy = db_update_strategy(
            strategy_id=strategy_id,
            name=strategy_request.name,
            description=strategy_request.description,
            code=strategy_request.code,
            market=strategy_request.market,
            parameters=strategy_request.parameters,
            stop_loss_pct=strategy_request.stop_loss_pct,
            take_profit_pct=strategy_request.take_profit_pct,
        )
        
        if updated_strategy is None:
            logger.warning(f"[AGENT_STRATEGY_UPDATE] Strategy update failed (not found) | strategy_id={strategy_id}")
            raise HTTPException(status_code=404, detail=f"Strategy {strategy_id} not found")
        
        logger.debug(f"[AGENT_STRATEGY_UPDATE] Strategy updated | strategy_id={strategy_id}")
        
        # Log audit
        update_fields = []
        if strategy_request.name is not None:
            update_fields.append("name")
        if strategy_request.description is not None:
            update_fields.append("description")
        if strategy_request.code is not None:
            update_fields.append("code")
        if strategy_request.market is not None:
            update_fields.append("market")
        if strategy_request.parameters is not None:
            update_fields.append("parameters")
        if strategy_request.stop_loss_pct is not None:
            update_fields.append("stop_loss_pct")
        if strategy_request.take_profit_pct is not None:
            update_fields.append("take_profit_pct")
        
        service.log_audit(
            token.id, "update_strategy", f"/strategies/{strategy_id}",
            details={
                "strategy_id": strategy_id,
                "strategy_name": updated_strategy.get("name"),
                "updated_fields": update_fields,
            }
        )
        
        duration = time.time() - start_time
        logger.info(f"[AGENT_STRATEGY_UPDATE] Update strategy successful | request_id={request_id} token_id={token.id} strategy_id={strategy_id} duration={duration:.3f}s")
        logger.debug(f"[AGENT_STRATEGY_UPDATE] Response | strategy_id={strategy_id} updated_fields={update_fields}")
        
        return {
            "code": 0,
            "message": "Strategy updated successfully",
            "data": {
                "id": strategy_id,
                "name": updated_strategy.get("name"),
                "market": updated_strategy.get("market"),
            }
        }
        
    except HTTPException as e:
        logger.debug(f"[AGENT_SYMBOLS] HTTPException re-raised: {e.detail}")
        raise
    except Exception as e:
        duration = time.time() - start_time
        logger.error(f"[AGENT_STRATEGY_UPDATE] Update strategy failed | request_id={request_id} token_id={token.id} strategy_id={strategy_id} error={str(e)} duration={duration:.3f}s")
        logger.error(f"[AGENT_STRATEGY_UPDATE] Stack trace:\n{traceback.format_exc()}")
        raise HTTPException(status_code=500, detail="Failed to update strategy")


@router.delete("/strategies/{strategy_id}")
async def delete_strategy(
    request: Request,
    strategy_id: str,
    hard: bool = Query(False, description="Hard delete (default: soft delete)"),
    token: Any = Depends(require_scope(TokenScope.WRITE)),
):
    """
    Delete a strategy.
    
    Requires W (Write) scope.
    Market access is validated against token permissions.
    Default is soft delete (sets deleted_at timestamp).
    
    Args:
        strategy_id: Strategy ID to delete
        hard: If True, perform hard delete (default: False, soft delete)
        
    Returns:
        Deletion confirmation
    """
    request_id = id(request)
    start_time = time.time()
    
    logger.info(f"[AGENT_STRATEGY_DELETE] Delete strategy requested | request_id={request_id} token_id={token.id} strategy_id={strategy_id}")
    logger.debug(f"[AGENT_STRATEGY_DELETE] Request details | path={request.url.path} method={request.method}")
    logger.debug(f"[AGENT_STRATEGY_DELETE] Delete params | hard={hard}")
    logger.debug(f"[AGENT_STRATEGY_DELETE] Token markets | markets={token.markets}")
    
    try:
        service = get_token_service()
        
        # Import strategy_db functions
        from app.db.strategy_db import get_strategy as db_get_strategy, delete_strategy as db_delete_strategy
        
        logger.debug(f"[AGENT_STRATEGY_DELETE] Fetching existing strategy | strategy_id={strategy_id}")
        
        # Get existing strategy to check permissions
        existing_strategy = db_get_strategy(strategy_id)
        if existing_strategy is None:
            logger.warning(f"[AGENT_STRATEGY_DELETE] Strategy not found | strategy_id={strategy_id}")
            raise HTTPException(status_code=404, detail=f"Strategy {strategy_id} not found")
        
        logger.debug(f"[AGENT_STRATEGY_DELETE] Existing strategy found | name={existing_strategy.get('name')} market={existing_strategy.get('market')}")
        
        # Check market access
        existing_market = existing_strategy.get("market", "AStock")
        if not token.can_access_market(existing_market):
            logger.warning(f"[AGENT_STRATEGY_DELETE] Market access denied | token_id={token.id} market={existing_market} allowed_markets={token.markets}")
            raise HTTPException(status_code=403, detail=f"Market {existing_market} not allowed")
        
        logger.debug(f"[AGENT_STRATEGY_DELETE] Market access granted")
        
        logger.debug(f"[AGENT_STRATEGY_DELETE] Deleting strategy | strategy_id={strategy_id} hard_delete={hard}")
        
        # Delete strategy
        success = db_delete_strategy(strategy_id, soft_delete=not hard)
        
        if not success:
            logger.warning(f"[AGENT_STRATEGY_DELETE] Strategy deletion failed | strategy_id={strategy_id}")
            raise HTTPException(status_code=404, detail=f"Strategy {strategy_id} not found")
        
        logger.debug(f"[AGENT_STRATEGY_DELETE] Strategy deleted | strategy_id={strategy_id}")
        
        # Log audit
        service.log_audit(
            token.id, "delete_strategy", f"/strategies/{strategy_id}",
            details={
                "strategy_id": strategy_id,
                "strategy_name": existing_strategy.get("name"),
                "market": existing_market,
                "hard_delete": hard,
            }
        )
        
        duration = time.time() - start_time
        logger.info(f"[AGENT_STRATEGY_DELETE] Delete strategy successful | request_id={request_id} token_id={token.id} strategy_id={strategy_id} hard={hard} duration={duration:.3f}s")
        logger.debug(f"[AGENT_STRATEGY_DELETE] Response | strategy_id={strategy_id} deleted=True")
        
        return {
            "code": 0,
            "message": "Strategy deleted successfully",
            "data": {
                "id": strategy_id,
                "deleted": True,
                "hard_delete": hard,
            }
        }
        
    except HTTPException as e:
        logger.debug(f"[AGENT_SYMBOLS] HTTPException re-raised: {e.detail}")
        raise
    except Exception as e:
        duration = time.time() - start_time
        logger.error(f"[AGENT_STRATEGY_DELETE] Delete strategy failed | request_id={request_id} token_id={token.id} strategy_id={strategy_id} error={str(e)} duration={duration:.3f}s")
        logger.error(f"[AGENT_STRATEGY_DELETE] Stack trace:\n{traceback.format_exc()}")
        raise HTTPException(status_code=500, detail="Failed to delete strategy")


# ─────────────────────────────────────────────────────────────────────────────
# Backtest Operations (B Scope)
# ─────────────────────────────────────────────────────────────────────────────

@router.post("/backtests", response_model=BacktestResponse)
async def submit_backtest(
    request: BacktestRequest,
    token: Any = Depends(require_scope(TokenScope.BACKTEST)),
):
    """
    提交回测任务
    
    返回 job_id 用于查询状态
    """
    if not token.can_access_market(request.market):
        raise HTTPException(status_code=403, detail=f"Market {request.market} not allowed")
    
    # 审计日志
    service = get_token_service()
    service.log_audit(
        token.id, "submit_backtest", "/backtests",
        details={
            "market": request.market,
            "symbol": request.symbol,
            "strategy_code_length": len(request.strategy_code),
        }
    )
    
    # TODO: 实现实际的回测提交
    import uuid
    job_id = str(uuid.uuid4())
    
    return BacktestResponse(
        job_id=job_id,
        status="pending",
        message="Backtest job submitted successfully",
    )


@router.get("/jobs/{job_id}", response_model=JobStatusResponse)
async def get_job_status(
    job_id: str,
    token: Any = Depends(require_scope(TokenScope.READ)),
):
    """查询任务状态"""
    # 审计日志
    service = get_token_service()
    service.log_audit(token.id, "get_job_status", f"/jobs/{job_id}")
    
    # TODO: 实现实际的 job 状态查询
    return JobStatusResponse(
        job_id=job_id,
        status="completed",
        progress=1.0,
        result={
            "total_return": 0.15,
            "annual_return": 0.18,
            "sharpe_ratio": 1.5,
            "max_drawdown": 0.08,
        },
    )


# ─────────────────────────────────────────────────────────────────────────────
# Audit Logs
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/admin/audit_logs")
async def get_audit_logs(
    token_id: Optional[str] = None,
    action: Optional[str] = None,
    start_time: Optional[str] = None,
    end_time: Optional[str] = None,
    limit: int = 100,
    admin_auth: Optional[str] = Header(None, description="Admin JWT Token"),
):
    """查询审计日志 (需 Admin 权限)"""
    if not _verify_admin(admin_auth):
        raise HTTPException(status_code=403, detail="Invalid admin token")
    
    service = get_token_service()
    
    from datetime import datetime as dt
    start = dt.fromisoformat(start_time) if start_time else None
    end = dt.fromisoformat(end_time) if end_time else None
    
    logs = service.get_audit_logs(
        token_id=token_id,
        action=action,
        start_time=start,
        end_time=end,
        limit=limit,
    )
    
    return {"logs": logs}


# ─────────────────────────────────────────────────────────────────────────────
# MCP Server Endpoints
# ─────────────────────────────────────────────────────────────────────────────

class MCPTool(BaseModel):
    name: str
    description: str
    input_schema: dict
    required_scope: str


class MCPToolsResponse(BaseModel):
    tools: list[MCPTool]
    count: int


class MCPCallRequest(BaseModel):
    tool_name: str
    arguments: dict = Field(default_factory=dict)


class MCPCallResponse(BaseModel):
    success: bool
    data: Optional[Any] = None
    error: Optional[str] = None


@router.get("/mcp/tools", response_model=MCPToolsResponse)
async def list_mcp_tools(
    token: Any = Depends(require_scope(TokenScope.READ)),
):
    """列出所有可用 MCP 工具"""
    from app.mcp.server import get_mcp_server

    server = get_mcp_server()
    tools = server.list_tools()

    return MCPToolsResponse(
        tools=[MCPTool(**t) for t in tools],
        count=len(tools),
    )


@router.post("/mcp/call", response_model=MCPCallResponse)
async def call_mcp_tool(
    request: MCPCallRequest,
    token: Any = Depends(verify_agent_token),
):
    """调用 MCP 工具"""
    from app.mcp.server import get_mcp_server
    from app.services.agent.token_service import TokenScope

    server = get_mcp_server()
    tool = server.get_tool(request.tool_name)

    if tool is None:
        raise HTTPException(status_code=404, detail=f"Unknown tool: {request.tool_name}")

    # Scope 权限检查
    scope_map = {"R": TokenScope.READ, "W": TokenScope.WRITE, "B": TokenScope.BACKTEST, "N": TokenScope.NOTIFY, "T": TokenScope.TRADE}
    required = scope_map.get(tool.required_scope, TokenScope.READ)
    if not token.has_scope(required):
        raise HTTPException(status_code=403, detail=f"Insufficient scope for tool {request.tool_name}")

    # 调用工具
    result = server.call_tool(request.tool_name, request.arguments)
    return MCPCallResponse(**result)
