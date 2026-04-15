"""
AlphaTerminal Backend - FastAPI Application Entry Point
"""
import asyncio
import logging
import signal
from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from pydantic import ValidationError
from contextlib import asynccontextmanager

logger = logging.getLogger(__name__)

from app.routers import market, copilot, news, sentiment, debug, bond, futures, portfolio, stocks, websocket as ws_router, admin
from app.services.scheduler import start_scheduler, stop_scheduler


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理：启动和关闭时执行"""
    # 启动时
    start_scheduler()

    # 启动时不触发新闻预热（scheduler 的 NewsRefresh 任务每 20 分钟自动运行，
    # 由它统一管理 _NEWS_CACHE，避免两个线程同时写缓存造成竞态）
    # sentiment_engine._do_news_fetch（scheduler 触发）现已修复为 stock_news_em（真实时间戳）

    yield
    # 关闭时
    stop_scheduler()


app = FastAPI(
    title="AlphaTerminal API",
    version="0.1.0",
    lifespan=lifespan,
)

# ── CORS 中间件 ──────────────────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:60100",
        "http://127.0.0.1:60100",
        "http://0.0.0.0:60100",
        "http://192.168.2.186:60100",
        "http://192.168.1.50:60100",
        "http://172.17.0.1:60100",
        "http://172.20.0.1:60100",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── 全局异常处理器 ───────────────────────────────────────────────────────────

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """422: 参数校验失败 — 返回统一格式"""
    body = {}
    try:
        body = await request.body()
    except Exception:
        pass
    errors = exc.errors()
    first = errors[0] if errors else {}
    field = ".".join(str(l) for l in (first.get("loc") or []))
    msg   = first.get("msg", "") or str(exc)
    logger.warning(f"[422 ValidationError] path={request.url.path} field={field} msg={msg}")
    return JSONResponse(
        status_code=422,
        content={
            "code": 422,
            "message": f"参数校验失败: {field} {msg}",
            "detail": errors,
        },
    )

@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    """4xx: HTTP异常 — 返回统一格式"""
    logger.warning(f"[HTTP {exc.status_code}] path={request.url.path} detail={exc.detail}")
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "code": exc.status_code,
            "message": str(exc.detail),
        },
    )

@app.exception_handler(Exception)
async def generic_exception_handler(request: Request, exc: Exception):
    """500: 未捕获异常 — 不泄露堆栈"""
    import traceback
    tb = "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))
    logger.error(f"[500 InternalError] path={request.url.path}\n{tb}")
    return JSONResponse(
        status_code=500,
        content={
            "code": 500,
            "message": "服务器内部错误，请稍后重试",
        },
    )

# ── 路由注册 ─────────────────────────────────────────────────────────────────
app.include_router(market.router, prefix="/api/v1", tags=["market"])
app.include_router(admin.router, prefix="/api/v1", tags=["admin"])
app.include_router(news.router, prefix="/api/v1", tags=["news"])
app.include_router(debug.router, prefix="/api/v1", tags=["debug"])   # ← 必须在 sentiment 之前（/{symbol} 拦截一切）
app.include_router(sentiment.router, prefix="/api/v1", tags=["sentiment"])
app.include_router(bond.router, prefix="/api/v1", tags=["bond"])
app.include_router(futures.router, prefix="/api/v1", tags=["futures"])
app.include_router(portfolio.router, prefix="/api/v1", tags=["portfolio"])
app.include_router(stocks.router, prefix="/api/v1/stocks", tags=["stocks"])
app.include_router(ws_router.router)  # WebSocket: /ws/market/{symbol}


@app.get("/health")
async def health():
    return {"status": "ok", "service": "AlphaTerminal"}
