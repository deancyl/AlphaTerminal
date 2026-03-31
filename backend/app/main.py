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

from app.routers import market, copilot, news, sentiment, debug
from app.services.scheduler import start_scheduler, stop_scheduler


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理：启动和关闭时执行"""
    # 启动时
    start_scheduler()

    # 立即触发一次新闻缓存预热（不等待，让后台线程静默执行）
    async def _bg_startup():
        # 等待scheduler初始化完成
        import time; await asyncio.sleep(1)
        from app.services.news_engine import refresh_news_cache
        logger.info("[Startup] 启动新闻预热...")
        refresh_news_cache(background=True)
        logger.info("[Startup] 新闻预热已触发（后台运行）")

    asyncio.create_task(_bg_startup())

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


@app.get("/health")
async def health():
    return {"status": "ok", "service": "AlphaTerminal"}
