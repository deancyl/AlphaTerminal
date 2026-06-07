"""
AlphaTerminal Backend - FastAPI Application Entry Point
"""

import asyncio
import logging
import os
from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse, FileResponse, ORJSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.exceptions import RequestValidationError
from contextlib import asynccontextmanager

logger = logging.getLogger(__name__)

from app.routers import (
    market,
    copilot,
    news,
    sentiment,
    bond,
    futures,
    portfolio,
    stocks,
    websocket as ws_router,
    admin,
    admin_source,
    fund,
    export,
    macro,
    agent,
    mcp,
    performance,
    f9_deep,
    health,
    research,
    forex,
    audit,
    oms,
    options,
    ml,
    metrics,
    attribution,
    agentic,
    cost_attribution,
    audit_playback,
    data_gaps,
    market_radar,
    factor_sandbox,
    timemachine,
    market_indicators,
)
from app.routers.macro import warmup_macro_cache
from app.routers.market_radar import warmup_market_radar_cache
from app.routers.timemachine import warmup_timemachine_cache
from app.services.scheduler import (
    start_scheduler,
    stop_scheduler,
    run_initial_data_fetch,
)
from app.services.logging_queue import init_logging_queue
from app.db.db_writer import start_writer, stop_writer
from app.services.watchdog import init_watchdog, stop_watchdog
from app.middleware.agent_auth import audit_middleware
from app.middleware.rate_limit import setup_rate_limiting, RateLimitConfig
from app.middleware.response_time import ResponseTimeMiddleware
from app.config.settings import get_settings
from app.services.executor_manager import executor_manager

# ── 优化服务导入 ───────────────────────────────────────────────────────────────
# 这些服务是可选增强，不影响核心功能
try:
    from app.services.source_health import get_health_checker
    from app.services.degradation_chain import get_degradation_chain
    from app.services.incremental_fetcher import get_incremental_fetcher
    from app.services.warmup_strategy import get_warmup_strategy
    from app.services.adaptive_circuit_breaker import get_adaptive_breaker_manager

    _optimization_services_available = True
except ImportError as e:
    logger.warning(f"[Main] Optimization services not available: {e}", exc_info=True)
    _optimization_services_available = False


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理：启动和关闭时执行"""
    import os

    is_testing = os.environ.get("PYTEST_RUNNING") == "true"
    is_ci = os.environ.get("CI") == "true" or os.environ.get("GITHUB_ACTIONS") == "true"

    if not is_testing:
        start_writer()
        init_watchdog()

        # Skip blocking data fetch in CI for fast startup (< 5s)
        if not is_ci:
            logger.info("[Lifespan] Starting blocking data pre-warming...")
            try:
                await asyncio.wait_for(run_initial_data_fetch(), timeout=10.0)
                logger.info("[Lifespan] Data pre-warming complete")
            except asyncio.TimeoutError:
                logger.warning(
                    "[Lifespan] Data fetch timed out after 10s, continuing with empty cache"
                )
            except Exception as e:
                logger.warning(f"[Lifespan] Data fetch failed: {e}", exc_info=True)
        else:
            logger.info(
                "[Lifespan] CI environment detected, skipping blocking data fetch"
            )

        # Warmup macro cache in background
        asyncio.create_task(warmup_macro_cache())
        logger.info("[Lifespan] Macro cache warmup started in background")

        # Warmup market_radar cache in background
        asyncio.create_task(warmup_market_radar_cache())
        logger.info("[Lifespan] Market Radar cache warmup started in background")

        # Warmup timemachine cache in background
        asyncio.create_task(warmup_timemachine_cache())
        logger.info("[Lifespan] TimeMachine cache warmup started in background")

        start_scheduler()

        # 注册核心服务到 ExecutorManager
        executor_manager.register(
            "scheduler",
            type("SchedulerProxy", (), {"shutdown": lambda: stop_scheduler()})(),
            shutdown_method="shutdown",
        )

        executor_manager.register(
            "db_writer",
            type("DBWriterProxy", (), {"shutdown": lambda: stop_writer()})(),
            shutdown_method="shutdown",
        )

        executor_manager.register(
            "watchdog",
            type("WatchdogProxy", (), {"shutdown": lambda: stop_watchdog()})(),
            shutdown_method="shutdown",
        )

    # ── 初始化优化服务 ─────────────────────────────────────────────────────────────
    # 这些服务是可选增强，初始化失败不影响核心功能
    if _optimization_services_available:
        try:
            # 初始化降级链（被动服务，无需启动）
            degradation_chain = get_degradation_chain()
            logger.info("[Lifespan] DegradationChain initialized")

            # 初始化增量获取器（被动服务，无需启动）
            incremental_fetcher = get_incremental_fetcher()
            logger.info("[Lifespan] IncrementalKlineFetcher initialized")

            # 初始化自适应熔断器管理器（被动服务，无需启动）
            adaptive_breaker_manager = get_adaptive_breaker_manager()
            logger.info("[Lifespan] AdaptiveCircuitBreaker initialized")

            # 初始化健康检查器（被动服务，手动调用check_all）
            health_checker = get_health_checker()
            logger.info("[Lifespan] SourceHealthChecker initialized")

            # 执行智能预热（异步，不阻塞启动）
            warmup_strategy = get_warmup_strategy()
            asyncio.create_task(warmup_strategy.warmup_all())
            logger.info("[Lifespan] WarmupStrategy started in background")

        except Exception as e:
            logger.warning(
                f"[Lifespan] Optimization services initialization failed: {e}",
                exc_info=True,
            )

    yield

    # 关闭时：优雅退出 — 等待队列排空
    logger.info("[Lifespan] Starting graceful shutdown...")

    # 使用 ExecutorManager 统一管理关闭
    shutdown_results = await executor_manager.shutdown_all(timeout=30.0)

    failed_shutdowns = [
        name for name, success in shutdown_results.items() if not success
    ]
    if failed_shutdowns:
        logger.warning(
            f"[Lifespan] Some executors failed to shutdown: {failed_shutdowns}"
        )
    else:
        logger.info("[Lifespan] All executors shutdown successfully")


app = FastAPI(
    title="AlphaTerminal API",
    version="0.6.223",
    lifespan=lifespan,
    default_response_class=ORJSONResponse,
)

# ── GZip 压缩中间件 ───────────────────────────────────────────────────────
# Enable GZip compression for responses > 1KB
# Reduces JSON payload sizes by 70-80%, critical for large K-line datasets
app.add_middleware(GZipMiddleware, minimum_size=1000)

# ── Response Time Middleware ─────────────────────────────────────────────────
# Track API response time and record to cache_metrics
app.add_middleware(ResponseTimeMiddleware)

# 初始化日志队列（WebSocket 实时日志流）
init_logging_queue()

# ── Agent Authentication Middleware ───────────────────────────────────────────
# Add audit middleware for agent API requests
audit_middleware(app)

# ── Rate Limiting Middleware ───────────────────────────────────────────────────
# Global rate limit: 200/minute, expensive endpoints have stricter limits
# Can be disabled via RATE_LIMIT_ENABLED=false environment variable
_rate_limit_enabled = os.environ.get("RATE_LIMIT_ENABLED", "true").lower() == "true"
rate_limit_config = RateLimitConfig(
    global_limit=200, global_period=60, enabled=_rate_limit_enabled
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
        logger.warning(
            "Production mode with wildcard CORS is insecure. Please set ALLOWED_ORIGINS environment variable."
        )
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
app.include_router(
    performance.router, prefix="/api/v1/performance", tags=["performance"]
)
app.include_router(health.router, prefix="/api/v1", tags=["health"])
app.include_router(forex.router, prefix="/api/v1", tags=["forex"])
app.include_router(market_indicators.router, prefix="/api/v1", tags=["market_indicators"])
app.include_router(options.router, prefix="/api/v1", tags=["options"])
app.include_router(audit.router, tags=["audit"])
app.include_router(research.router, tags=["research"])
app.include_router(oms.router, tags=["oms"])  # Order Management System
app.include_router(ml.router, prefix="/api/v1/ml", tags=["ml"])
app.include_router(metrics.router, prefix="/api/v1", tags=["monitoring"])
app.include_router(
    attribution.router, prefix="/api/v1", tags=["attribution"]
)  # Multi-factor attribution sandbox
app.include_router(
    audit_playback.router, prefix="/api/v1", tags=["audit_playback"]
)  # Audit playback & rollback
app.include_router(
    agentic.router, prefix="/api/v1/agentic", tags=["agentic"]
)  # Agentic workflow engine
app.include_router(
    cost_attribution.router, prefix="/api/v1", tags=["cost_attribution"]
)  # LLM cost attribution
app.include_router(
    data_gaps.router, prefix="/api/v1", tags=["data_gaps"]
)  # Data gap radar
app.include_router(market_radar.router, tags=["market_radar"])  # Market heat radar
app.include_router(
    factor_sandbox.router, prefix="/api/v1", tags=["factor_sandbox"]
)  # Factor sandbox screening
app.include_router(
    timemachine.router, tags=["timemachine"]
)  # Time-machine K-line replay
app.include_router(ws_router.router)  # WebSocket: /ws/market/{symbol}
app.include_router(agent.router)  # Agent Gateway: /api/agent/v1

# 回测模块
try:
    from app.routers import backtest

    app.include_router(backtest.router, prefix="/api/v1/backtest", tags=["backtest"])
except (ImportError, AttributeError, SyntaxError) as e:
    logger.warning(f"Backtest module not loaded: {e}", exc_info=True)
except Exception as e:
    logger.error(f"Unexpected error loading backtest module: {e}", exc_info=True)

# 回测监控模块
try:
    from app.routers import backtest_monitor

    app.include_router(
        backtest_monitor.router,
        prefix="/api/v1/backtest_monitor",
        tags=["backtest_monitor"],
    )
except (ImportError, AttributeError, SyntaxError) as e:
    logger.warning(f"Backtest monitor module not loaded: {e}", exc_info=True)
except Exception as e:
    logger.error(
        f"Unexpected error loading backtest monitor module: {e}", exc_info=True
    )

# 策略模块
try:
    from app.routers import strategy

    app.include_router(strategy.router)
except (ImportError, AttributeError, SyntaxError) as e:
    logger.warning(f"Strategy module not loaded: {e}", exc_info=True)
except Exception as e:
    logger.error(f"Unexpected error loading strategy module: {e}", exc_info=True)


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
    app.mount(
        "/assets",
        StaticFiles(directory=os.path.join(FRONTEND_DIST, "assets")),
        name="assets",
    )

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
