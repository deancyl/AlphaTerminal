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
from typing import Optional, Any
from fastapi import APIRouter, Depends, HTTPException, Header, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

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
    id: int
    name: str
    token: str  # 原始 Token, 仅此一次显示
    token_prefix: str
    scopes: list[str]
    markets: list[str]
    paper_only: bool
    expires_at: Optional[str]


class WhoamiResponse(BaseModel):
    id: int
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


async def verify_token(
    authorization: str = Header(..., description="Bearer Token"),
) -> Any:
    """
    验证 Bearer Token
    
    从 Header 提取 Token 并验证, 返回 Token 对象
    """
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Invalid authorization header format")
    
    raw_token = authorization[7:]  # 去掉 "Bearer " 前缀
    
    service = get_token_service()
    token = service.verify_token(raw_token)
    
    if token is None:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    
    # 检查 Rate Limit
    if not service.check_rate_limit(token):
        raise HTTPException(status_code=429, detail="Rate limit exceeded")
    
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
    admin_auth: str = Header(..., description="Admin JWT Token"),
):
    """
    创建新的 Agent Token (需 Admin 权限)
    
    Token 仅在此刻显示一次, 请妥善保管。
    """
    # TODO: 验证 admin_auth 是否为有效 Admin JWT
    # 目前简化处理, 实际应该检查 JWT
    
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
    admin_auth: str = Header(..., description="Admin JWT Token"),
    include_inactive: bool = False,
):
    """列出所有 Token (需 Admin 权限)"""
    service = get_token_service()
    tokens = service.list_tokens(include_inactive=include_inactive)
    return [t.to_dict() for t in tokens]


@router.delete("/admin/tokens/{token_id}")
async def revoke_token(
    token_id: int,
    admin_auth: str = Header(..., description="Admin JWT Token"),
):
    """吊销 Token (需 Admin 权限)"""
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
    service.log_audit(token, "list_markets", "/markets")
    
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
    
    # TODO: 实现实际的标的搜索
    # 目前返回模拟数据
    if not token.can_access_market(market):
        raise HTTPException(status_code=403, detail=f"Market {market} not allowed")
    
    return SymbolsResponse(symbols=[
        {"symbol": "600519", "name": "贵州茅台", "market": "AStock"},
        {"symbol": "000858", "name": "五粮液", "market": "AStock"},
        {"symbol": "00700", "name": "腾讯控股", "market": "HKStock"},
    ][:limit])


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
    
    # TODO: 实现实际的 K 线获取
    # 目前返回模拟数据
    return KlinesResponse(
        market=request.market,
        symbol=request.symbol,
        timeframe=request.timeframe,
        data=[
            {
                "timestamp": "2024-01-01T00:00:00",
                "open": 100.0,
                "high": 105.0,
                "low": 98.0,
                "close": 103.0,
                "volume": 1000000,
            }
        ],
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
    
    # TODO: 实现实际的价格获取
    return {
        "market": market,
        "symbol": symbol,
        "price": 100.0,
        "change": 2.5,
        "change_pct": 2.56,
        "timestamp": int(time.time()),
    }


@router.get("/strategies")
async def list_strategies(
    token: Any = Depends(require_scope(TokenScope.READ)),
):
    """列出当前租户的策略"""
    # 审计日志
    service = get_token_service()
    service.log_audit(token, "list_strategies", "/strategies")
    
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
    service.log_audit(token, "get_job_status", f"/jobs/{job_id}")
    
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
    token_id: Optional[int] = None,
    action: Optional[str] = None,
    start_time: Optional[str] = None,
    end_time: Optional[str] = None,
    limit: int = 100,
    admin_auth: str = Header(..., description="Admin JWT Token"),
):
    """查询审计日志 (需 Admin 权限)"""
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
