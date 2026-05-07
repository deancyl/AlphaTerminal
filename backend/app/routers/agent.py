"""
Agent Gateway Router - AI Agent API 端点

参考 QuantDinger Agent Gateway 设计:
- /api/agent/v1/* 端点
- Bearer Token 认证
- Scope 权限检查
- Rate Limiting
- 审计日志
"""

from __future__ import annotations

import time
import logging
from typing import Optional, Any
from fastapi import APIRouter, Depends, HTTPException, Header, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

from ..services.agent.token_service import (
    AgentTokenService,
    TokenScope,
    Market,
)


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
    timestamp: str
    version: str = "0.6.11"


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


def _verify_admin(admin_auth: Optional[str]) -> bool:
    """验证 admin token。简单实现：检查是否以 'admin_' 开头。"""
    if admin_auth is None:
        return False
    return admin_auth.startswith("admin_")

async def verify_token(
    authorization: Optional[str] = Header(None, description="Bearer Token"),
) -> Any:
    """
    验证 Bearer Token
    
    从 Header 提取 Token 并验证, 返回 Token 对象
    """
    if authorization is None:
        raise HTTPException(status_code=401, detail="Missing authorization header")
    
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Invalid authorization header format")
    
    raw_token = authorization[7:]  # 去掉 "Bearer " 前缀
    
    service = get_token_service()
    token = service.verify_token(raw_token)
    
    if token is None:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    
    return token



def require_scope(required_scope: TokenScope):
    """
    Scope 权限检查依赖
    
    用法:
        @router.get("/some_endpoint")
        async def endpoint(token: dict = Depends(require_scope(TokenScope.READ))):
            ...
    """
    async def scope_checker(token: Any = Depends(verify_token)):
        if not token.has_scope(required_scope):
            raise HTTPException(
                status_code=403,
                detail=f"Insufficient scope. Required: {required_scope.value}"
            )
        return token
    return scope_checker


# ─────────────────────────────────────────────────────────────────────────────
# Public Endpoints (No Auth Required)
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/health", response_model=HealthResponse)
async def health():
    """健康检查"""
    return HealthResponse(
        status="ok",
        timestamp=int(time.time()),
    )


# ─────────────────────────────────────────────────────────────────────────────
# Token Management (Admin)
# ─────────────────────────────────────────────────────────────────────────────

@router.post("/admin/tokens", response_model=CreateTokenResponse)
async def create_token(
    request: CreateTokenRequest,
    admin_auth: Optional[str] = Header(None, description="Admin JWT Token"),
):
    """
    创建新的 Agent Token (需 Admin 权限)
    
    Token 仅在此刻显示一次, 请妥善保管。
    """
    if not _verify_admin(admin_auth):
        raise HTTPException(status_code=403, detail="Invalid admin token")
    
    service = get_token_service()
    raw_token, token = service.create_token(
        name=request.name,
        scopes=request.scopes,
        markets=request.markets,
        instruments=request.instruments,
        paper_only=request.paper_only,
        rate_limit=request.rate_limit,
        expires_in_days=request.expires_in_days,
    )
    
    return CreateTokenResponse(
        id=token.id,
        name=token.name,
        token=raw_token,  # 仅此一次显示
        token_prefix=token.token_prefix,
        scopes=token.scopes,
        markets=token.markets,
        paper_only=token.paper_only,
        expires_at=token.expires_at.isoformat() if token.expires_at else None,
    )


@router.get("/admin/tokens", response_model=list[dict])
async def list_tokens(
    admin_auth: Optional[str] = Header(None, description="Admin JWT Token"),
    include_inactive: bool = False,
):
    """列出所有 Token (需 Admin 权限)"""
    if not _verify_admin(admin_auth):
        raise HTTPException(status_code=403, detail="Invalid admin token")
    
    service = get_token_service()
    tokens = service.list_tokens(include_inactive=include_inactive)
    return [t.to_dict() for t in tokens]


@router.delete("/admin/tokens/{token_id}")
async def revoke_token(
    token_id: str,
    admin_auth: Optional[str] = Header(None, description="Admin JWT Token"),
):
    """吊销 Token (需 Admin 权限)"""
    if not _verify_admin(admin_auth):
        raise HTTPException(status_code=403, detail="Invalid admin token")
    
    service = get_token_service()
    success = service.revoke_token(token_id)
    if not success:
        raise HTTPException(status_code=404, detail="Token not found")
    return {"status": "ok", "message": f"Token {token_id} revoked"}


# ─────────────────────────────────────────────────────────────────────────────
# Token Info (Auth Required)
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/whoami", response_model=WhoamiResponse)
async def whoami(token: Any = Depends(verify_token)):
    """获取当前 Token 信息"""
    return WhoamiResponse(
        id=token.id,
        name=token.name,
        scopes=token.scopes,
        markets=token.markets,
        paper_only=token.paper_only,
        rate_limit=token.rate_limit,
        expires_at=token.expires_at.isoformat() if token.expires_at else None,
        last_used_at=token.last_used_at.isoformat() if token.last_used_at else None,
    )


# ─────────────────────────────────────────────────────────────────────────────
# Read Operations (R Scope)
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/markets", response_model=MarketsResponse)
async def list_markets(token: Any = Depends(require_scope(TokenScope.READ))):
    """获取支持的市场列表"""
    # 审计日志
    service = get_token_service()
    service.log_audit(token.id, "list_markets", "/markets")
    
    markets = [m.value for m in Market]
    return MarketsResponse(markets=markets)


@router.get("/markets/{market}/symbols", response_model=SymbolsResponse)
async def search_symbols(
    market: str,
    keyword: str = "",
    limit: int = 20,
    token: Any = Depends(require_scope(TokenScope.READ)),
):
    """
    搜索市场内的标的
    
    Args:
        market: 市场代码 (AStock/HKStock/USStock/Crypto/Forex/Futures)
        keyword: 搜索关键词
        limit: 返回数量限制
    """
    # 审计日志
    service = get_token_service()
    service.log_audit(
        token, "search_symbols", f"/markets/{market}/symbols",
        details={"market": market, "keyword": keyword, "limit": limit}
    )
    
    if not token.can_access_market(market):
        raise HTTPException(status_code=403, detail=f"Market {market} not allowed")
    
    # 调用现有的股票搜索功能
    try:
        from app.routers.stocks import search_stocks as _search_stocks
        results = await _search_stocks(q=keyword)
        
        # 过滤市场
        market_prefix_map = {
            "AStock": ("sh", "sz"),  # A股前缀
            "HKStock": ("hk",),  # 港股前缀
            "USStock": ("us",),  # 美股前缀
        }
        prefixes = market_prefix_map.get(market, ())
        
        filtered = []
        for item in results.get("data", {}).get("stocks", [])[:50]:
            code = item.get("code", "")
            # 根据市场过滤
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
        
        return SymbolsResponse(symbols=filtered)
    except Exception as e:
        # 降级为返回空列表
        logger.warning(f"[Agent] search_symbols failed: {e}")
        return SymbolsResponse(symbols=[])


@router.post("/klines", response_model=KlinesResponse)
async def get_klines(
    request: KlinesRequest,
    token: Any = Depends(require_scope(TokenScope.READ)),
):
    """
    获取 K 线数据
    
    Args:
        request: K线请求参数
    """
    if not token.can_access_market(request.market):
        raise HTTPException(status_code=403, detail=f"Market {request.market} not allowed")
    
    # 审计日志
    service = get_token_service()
    service.log_audit(
        token, "get_klines", f"/klines",
        details={
            "market": request.market,
            "symbol": request.symbol,
            "timeframe": request.timeframe,
            "limit": request.limit,
        }
    )
    
    # 调用现有的 K 线接口
    try:
        from app.routers.market import market_history
        from app.db import get_periodic_history
        
        # 转换市场代码
        symbol = request.symbol
        if request.market == "AStock":
            symbol = symbol  # 保持原样
        elif request.market == "HKStock":
            symbol = f"hk{symbol}"
        elif request.market == "USStock":
            symbol = f"us{symbol}"
        
        # 获取历史数据
        period_map = {"1m": "1min", "5m": "5min", "15m": "15min", "1H": "60min", "4H": "60min", "1D": "daily", "1W": "weekly"}
        period = period_map.get(request.timeframe, "daily")
        
        # 限制数量
        limit = min(request.limit, 1000)
        
        rows = get_periodic_history(symbol, period=period, limit=limit)
        
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
        
        return KlinesResponse(
            market=request.market,
            symbol=request.symbol,
            timeframe=request.timeframe,
            data=data,
        )
    except Exception as e:
        logger.warning(f"[Agent] get_klines failed: {e}")
        # 降级返回空数据
        return KlinesResponse(
            market=request.market,
            symbol=request.symbol,
            timeframe=request.timeframe,
            data=[],
        )


@router.get("/price")
async def get_price(
    market: str,
    symbol: str,
    token: Any = Depends(require_scope(TokenScope.READ)),
):
    """获取最新价格"""
    if not token.can_access_market(market):
        raise HTTPException(status_code=403, detail=f"Market {market} not allowed")
    
    if not token.can_access_instrument(symbol):
        raise HTTPException(status_code=403, detail=f"Instrument {symbol} not allowed")
    
    # 审计日志
    service = get_token_service()
    service.log_audit(
        token, "get_price", f"/price",
        details={"market": market, "symbol": symbol}
    )
    
    # 调用现有的实时行情接口
    try:
        from app.routers.market import market_quote
        
        # 转换市场代码
        sym = symbol
        if market == "AStock":
            if not symbol.startswith(("sh", "sz")):
                sym = f"sh{symbol}" if symbol.startswith("6") else f"sz{symbol}"
        elif market == "HKStock":
            sym = f"hk{symbol}"
        elif market == "USStock":
            sym = f"us{symbol}"
        
        quote = await market_quote(sym)
        
        if "data" in quote:
            data = quote["data"]
            return {
                "market": market,
                "symbol": symbol,
                "price": data.get("price", 0),
                "change": data.get("price_change", 0),
                "change_pct": data.get("pct_change", 0),
                "volume": data.get("volume", 0),
                "timestamp": int(time.time()),
            }
    except Exception as e:
        logger.warning(f"[Agent] get_price failed: {e}")
    
    # 降级返回
    return {
        "market": market,
        "symbol": symbol,
        "price": 0,
        "change": 0,
        "change_pct": 0,
        "timestamp": int(time.time()),
        "error": "Failed to fetch price",
    }


@router.get("/strategies")
async def list_strategies(
    token: Any = Depends(require_scope(TokenScope.READ)),
):
    """列出当前租户的策略"""
    # 审计日志
    service = get_token_service()
    service.log_audit(token.id, "list_strategies", "/strategies")
    
    # TODO: 实现实际的策略列表
    return {
        "strategies": [
            {
                "id": "1",
                "name": "均线交叉策略",
                "type": "indicator",
                "created_at": "2024-01-01T00:00:00",
            }
        ]
    }


@router.get("/strategies/{strategy_id}")
async def get_strategy(
    strategy_id: str,
    token: Any = Depends(require_scope(TokenScope.READ)),
):
    """获取策略详情"""
    # 审计日志
    service = get_token_service()
    service.log_audit(
        token, "get_strategy", f"/strategies/{strategy_id}"
    )
    
    # TODO: 实现实际的策略获取
    return {
        "id": strategy_id,
        "name": "均线交叉策略",
        "type": "indicator",
        "code": "# 策略代码...",
        "created_at": "2024-01-01T00:00:00",
    }


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
        token, "submit_backtest", "/backtests",
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
