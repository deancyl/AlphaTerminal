"""
AlphaTerminal Backend - FastAPI Application Entry Point
"""
import asyncio
import signal
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from app.routers import market, copilot, news
from app.services.scheduler import start_scheduler, stop_scheduler


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理：启动和关闭时执行"""
    # 启动时
    start_scheduler()

    # 后台预热新闻缓存（不阻塞 uvicorn 启动）
    async def _prefetch_news():
        await asyncio.sleep(1)   # 等待 scheduler 完全就绪
        from app.services.news_engine import refresh_news_cache
        refresh_news_cache(background=True)
        await asyncio.sleep(0)

    asyncio.create_task(_prefetch_news())

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


@app.get("/health")
async def health():
    return {"status": "ok", "service": "AlphaTerminal"}
