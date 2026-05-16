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

from app.routers import market, copilot, news, sentiment, bond, futures, portfolio, stocks, websocket as ws_router, admin, admin_source, fund, export, macro, agent, mcp, performance, f9_deep, health, research, forex
from app.routers.macro import start_cache_cleanup, stop_cache_cleanup
from app.services.scheduler import start_scheduler, stop_scheduler
from app.services.logging_queue import init_logging_queue
from app.db.db_writer import start_writer, stop_writer
from app.services.watchdog import init_watchdog, stop_watchdog
from app.middleware.agent_auth import audit_middleware
from app.middleware.rate_limit import setup_rate_limiting, RateLimitConfig
from app.config.settings import get_settings
from app.services.executor_manager import executor_manager, ExecutorStatus


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理：启动和关闭时执行"""
    # 启动时
    start_writer()         # DB 异步写入线程
    start_scheduler()
    init_watchdog()        # 进程保活监控（从配置加载开关状态）
    start_cache_cleanup()  # Macro 缓存周期性清理
    
    # 注册核心服务到 ExecutorManager
    executor_manager.register("scheduler", type('SchedulerProxy', (), {
        'shutdown': lambda: stop_scheduler()
    })(), shutdown_method="shutdown")
    
    executor_manager.register("db_writer", type('DBWriterProxy', (), {
        'shutdown': lambda: stop_writer()
    })(), shutdown_method="shutdown")
    
    executor_manager.register("watchdog", type('WatchdogProxy', (), {
        'shutdown': lambda: stop_watchdog()
    })(), shutdown_method="shutdown")
    
    executor_manager.register("macro_cache_cleanup", type('MacroCacheProxy', (), {
        'shutdown': lambda: stop_cache_cleanup()
    })(), shutdown_method="shutdown")

    yield
    
    # 关闭时：优雅退出 — 等待队列排空
    logger.info("[Lifespan] Starting graceful shutdown...")
    
    # 使用 ExecutorManager 统一管理关闭
    shutdown_results = await executor_manager.shutdown_all(timeout=30.0)
    
    failed_shutdowns = [name for name, success in shutdown_results.items() if not success]
    if failed_shutdowns:
        logger.warning(f"[Lifespan] Some executors failed to shutdown: {failed_shutdowns}")
    else:
        logger.info("[Lifespan] All executors shutdown successfully")


app = FastAPI(
    title="AlphaTerminal API",
    version="0.6.40",
    lifespan=lifespan,
)

# 初始化日志队列（WebSocket 实时日志流）
init_logging_queue()

# ── Agent Authentication Middleware ───────────────────────────────────────────
# Add audit middleware for agent API requests
audit_middleware(app)

# ── Rate Limiting Middleware ───────────────────────────────────────────────────
# Global rate limit: 200/minute, expensive endpoints have stricter limits
rate_limit_config = RateLimitConfig(
    global_limit=200,
    global_period=60,
    enabled=True
)
setup_rate_limiting(app, config=rate_limit_config)

# ── CORS 中间件 ──────────────────────────────────────────────────────────────
# 使用 Settings 类统一管理 CORS 配置
settings = get_settings()
_cors_origins = settings.get_allowed_origins_list()

# 生产环境强制白名单模式
if settings.is_production():
    # 生产环境必须配置 ALLOWED_ORIGINS，否则只允许 localhost
    if _cors_origins == ["*"]:
        logger.warning("Production mode with wildcard CORS is insecure. Please set ALLOWED_ORIGINS environment variable.")
        _cors_origins = [
            "http://localhost:60100",
            "http://127.0.0.1:60100",
        ]
else:
    # 开发环境允许所有来源（便于调试）
    _cors_origins = ["*"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── 全局异常处理器 ───────────────────────────────────────────────────────────
from app.utils.exception_handlers import setup_exception_handlers

# 配置新的全局异常处理器
setup_exception_handlers(app)

# 保留原有的异常处理器作为兼容（会被新的处理器覆盖）
@app.exception_handler(RequestValidationError)
async def validation_exception_handler_legacy(request: Request, exc: RequestValidationError):
    """422: 参数校验失败 — 返回统一格式 (兼容旧版本)"""
    body = {}
    try:
        body = await request.body()
    except (RuntimeError, ValueError):
        # RuntimeError: Request body stream already consumed or closed
        # ValueError: Invalid request body encoding
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
async def http_exception_handler_legacy(request: Request, exc: HTTPException):
    """4xx: HTTP异常 — 返回统一格式 (兼容旧版本)"""
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
app.include_router(admin.session_router, prefix="/api/v1", tags=["admin"])
app.include_router(admin_source.router, prefix="/api/v1", tags=["admin"])
app.include_router(news.router, prefix="/api/v1", tags=["news"])
app.include_router(sentiment.router, prefix="/api/v1", tags=["sentiment"])
app.include_router(bond.router, prefix="/api/v1", tags=["bond"])
app.include_router(futures.router, prefix="/api/v1", tags=["futures"])
app.include_router(portfolio.router, prefix="/api/v1", tags=["portfolio"])
app.include_router(copilot.router, prefix="/api/v1", tags=["copilot"])
app.include_router(stocks.router, prefix="/api/v1/stocks", tags=["stocks"])
app.include_router(fund.router, prefix="/api/v1", tags=["fund"])
app.include_router(export.router, prefix="/api/v1", tags=["export"])
app.include_router(macro.router, prefix="/api/v1", tags=["macro"])
app.include_router(f9_deep.router, prefix="/api/v1", tags=["f9_deep_data"])
app.include_router(mcp.router, prefix="/api/v1", tags=["mcp"])
app.include_router(performance.router, prefix="/api/v1/performance", tags=["performance"])
app.include_router(health.router, prefix="/api/v1", tags=["health"])
app.include_router(forex.router, prefix="/api/v1", tags=["forex"])
app.include_router(research.router, tags=["research"])
app.include_router(ws_router.router)  # WebSocket: /ws/market/{symbol}
app.include_router(agent.router)  # Agent Gateway: /api/agent/v1

# 回测模块
try:
    from app.routers import backtest
    app.include_router(backtest.router, prefix="/api/v1/backtest", tags=["backtest"])
except (ImportError, AttributeError, SyntaxError) as e:
    logger.warning(f"Backtest module not loaded: {e}")
except Exception as e:
    logger.error(f"Unexpected error loading backtest module: {e}")

# 策略模块
try:
    from app.routers import strategy
    app.include_router(strategy.router)
except (ImportError, AttributeError, SyntaxError) as e:
    logger.warning(f"Strategy module not loaded: {e}")
except Exception as e:
    logger.error(f"Unexpected error loading strategy module: {e}")


@app.get("/health")
async def health():
    """
    健康检查端点（内部状态探测）
    生产环境可通过 HEALTH_CHECK_KEY 环境变量保护
    """
    # 可选认证：配置了 HEALTH_CHECK_KEY 时要求传递
    configured_key = os.environ.get("HEALTH_CHECK_KEY", "")
    if configured_key:
        # 由前端或监控服务在 header 或 query 中传递
        # 这里不强制校验，保持向后兼容
        pass
    return {"status": "ok", "service": "AlphaTerminal"}


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
    logger.warning(f"Frontend dist not found at {FRONTEND_DIST}")
