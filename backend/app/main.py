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

from app.routers import market, copilot, news, sentiment
from app.services.scheduler import start_scheduler, stop_scheduler


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理：启动和关闭时执行"""
    # 启动时
    start_scheduler()

    # Task 3: 同步预热新闻缓存（阻塞 uvicorn 启动直到缓存就绪）
    # 确保前端刷新不再看到 Mock 数据
    async def _prefetch_news_sync():
        await asyncio.sleep(2)   # 等待 scheduler 启动
        from app.services.news_engine import refresh_news_cache
        logger.info("[Startup] 开始同步预热新闻缓存...")
        try:
            # 同步刷新（background=False，直接阻塞当前线程）
            refresh_news_cache(background=False)
            logger.info("[Startup] 新闻缓存预热完成！")
        except Exception as e:
            logger.error(f"[Startup] 新闻预热失败: {e}", exc_info=True)

    # 先执行一次同步预热，再继续
    await _prefetch_news_sync()

    # 再触发一次后台增量刷新（定时任务会继续每20分钟刷新）
    async def _bg_news():
        from app.services.sentiment_engine import trigger_news_fetch
        trigger_news_fetch()
    asyncio.create_task(_bg_news())

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
app.include_router(sentiment.router, prefix="/api/v1", tags=["sentiment"])


@app.get("/health")
async def health():
    return {"status": "ok", "service": "AlphaTerminal"}
