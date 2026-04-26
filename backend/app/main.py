"""
AlphaTerminal Backend - FastAPI Application Entry Point
"""
import asyncio
import logging
import signal
import os
from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.exceptions import RequestValidationError
from pydantic import ValidationError
from contextlib import asynccontextmanager

logger = logging.getLogger(__name__)

from app.routers import market, copilot, news, sentiment, debug, bond, futures, portfolio, stocks, websocket as ws_router, admin, admin_source, fund
from app.services.scheduler import start_scheduler, stop_scheduler
from app.services.logging_queue import init_logging_queue
from app.db.db_writer import start_writer, stop_writer
from app.services.watchdog import init_watchdog, stop_watchdog


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理：启动和关闭时执行"""
    # 启动时
    start_writer()         # DB 异步写入线程
    start_scheduler()
    init_watchdog()        # 进程保活监控（从配置加载开关状态）

    yield
    # 关闭时：优雅退出 — 等待队列排空
    stop_writer()          # DB 写入队列 graceful shutdown（最多30s）
    stop_scheduler()
    stop_watchdog()        # 停止 watchdog 线程


app = FastAPI(
    title="AlphaTerminal API",
    version="0.5.167",
    lifespan=lifespan,
)

# 初始化日志队列（WebSocket 实时日志流）
init_logging_queue()

# ── CORS 中间件 ──────────────────────────────────────────────────────────────
# 允许的来源：本地开发 + 环境变量配置（生产环境应通过 ALLOWED_ORIGINS 配置）
_allowed_origins = [
    "http://localhost:60100",
    "http://127.0.0.1:60100",
    "http://0.0.0.0:60100",
]
# 从环境变量添加额外的允许来源
_extra_origins = os.environ.get("ALLOWED_ORIGINS", "")
if _extra_origins:
    _allowed_origins.extend([o.strip() for o in _extra_origins.split(",") if o.strip()])

app.add_middleware(
    CORSMiddleware,
    allow_origins=_allowed_origins,
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
app.include_router(admin_source.router, prefix="/api/v1", tags=["admin"])
app.include_router(news.router, prefix="/api/v1", tags=["news"])
app.include_router(sentiment.router, prefix="/api/v1", tags=["sentiment"])
app.include_router(debug.router, prefix="/api/v1", tags=["debug"])   # 放在最后兜底
app.include_router(bond.router, prefix="/api/v1", tags=["bond"])
app.include_router(futures.router, prefix="/api/v1", tags=["futures"])
app.include_router(portfolio.router, prefix="/api/v1", tags=["portfolio"])
app.include_router(copilot.router, prefix="/api/v1", tags=["copilot"])
app.include_router(stocks.router, prefix="/api/v1/stocks", tags=["stocks"])
app.include_router(fund.router, prefix="/api/v1", tags=["fund"])
app.include_router(ws_router.router)  # WebSocket: /ws/market/{symbol}

# 回测模块
try:
    from app.routers import backtest
    app.include_router(backtest.router, prefix="/api/v1/backtest", tags=["backtest"])
except Exception as e:
    print(f"[Warning] Backtest module not loaded: {e}")


# ── 静态文件服务（前端 dist 目录）──────────────────────────────────────────────
# 获取前端构建目录路径（相对于 backend 目录）
# main.py 位于 app/main.py，所以 frontend 在 ../frontend
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FRONTEND_DIST = os.path.abspath(os.path.join(BASE_DIR, "..", "frontend", "dist"))

# 如果 dist 目录存在，挂载静态文件服务
if os.path.exists(FRONTEND_DIST):
    app.mount("/assets", StaticFiles(directory=os.path.join(FRONTEND_DIST, "assets")), name="assets")
    
    @app.get("/")
    async def root():
        return FileResponse(os.path.join(FRONTEND_DIST, "index.html"))
    
    @app.get("/{path:path}")
    async def catch_all(path: str):
        # 排除 API 路径
        if path.startswith("api/") or path.startswith("ws/"):
            raise HTTPException(status_code=404, detail="Not Found")
        # 其他路径返回 index.html（支持前端路由）
        index_file = os.path.join(FRONTEND_DIST, "index.html")
        if os.path.exists(index_file):
            return FileResponse(index_file)
        raise HTTPException(status_code=404, detail="Not Found")
else:
    print(f"[Warning] Frontend dist not found at {FRONTEND_DIST}")


@app.get("/health")
async def health():
    return {"status": "ok", "service": "AlphaTerminal"}
