"""
AlphaTerminal Backend - FastAPI Application Entry Point
"""
import asyncio
import logging
import signal
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

logger = logging.getLogger(__name__)

from app.routers import market, copilot, news, sentiment, debug, bond, futures
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

# ── 路由注册 ─────────────────────────────────────────────────────────────────
app.include_router(market.router, prefix="/api/v1", tags=["market"])
app.include_router(copilot.router, prefix="/api/v1", tags=["copilot"])
app.include_router(news.router, prefix="/api/v1", tags=["news"])
app.include_router(debug.router, prefix="/api/v1", tags=["debug"])   # ← 必须在 sentiment 之前（/{symbol} 拦截一切）
app.include_router(sentiment.router, prefix="/api/v1", tags=["sentiment"])
app.include_router(bond.router, prefix="/api/v1", tags=["bond"])
app.include_router(futures.router, prefix="/api/v1", tags=["futures"])


@app.get("/health")
async def health():
    return {"status": "ok", "service": "AlphaTerminal"}
