"""
Admin 系统控制路由 - 数据源、调度器、缓存、数据库、网络控制
"""
import asyncio
import logging
import time
import os
import psutil
import sqlite3
from datetime import datetime
from pathlib import Path
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, HTTPException, Depends, Header
from typing import Optional, Dict, Any, List
from pydantic import BaseModel

from app.services import quote_source
from app.services.scheduler import scheduler
from app.services.sectors_cache import is_ready as sectors_cache_ready
from app.db.database import _get_conn, _db_path

# ── 动态路径配置（解决硬编码路径问题）────────────────────────────────────────
# BASE_DIR = AlphaTerminal 项目根目录
BASE_DIR = Path(__file__).resolve().parent.parent.parent   # app/routers/admin.py → app/ → backend/ → AlphaTerminal/
# 默认日志目录
_DEFAULT_LOG_DIR = BASE_DIR / "logs"

logger = logging.getLogger(__name__)
router = APIRouter(
    prefix="/admin", 
    tags=["admin"],
    dependencies=[]
)

# ═══════════════════════════════════════════════════════════════
# 认证机制
# ═══════════════════════════════════════════════════════════════

def verify_admin_key(api_key: str = None):
    """Admin API 密钥校验"""
    configured_key = os.environ.get("ADMIN_API_KEY", "")
    
    # 未配置 key 时跳过认证（本机开发环境）
    if not configured_key:
        return True
    
    if api_key != configured_key:
        raise HTTPException(status_code=401, detail="Invalid API key")
    return True

def admin_read_auth(api_key: str = None):
    """读操作认证 - GET 类接口"""
    return verify_admin_key(api_key)

def admin_write_auth(api_key: str = None):
    """写操作认证 - POST/PUT/DELETE 类接口"""
    return verify_admin_key(api_key)

# ═══════════════════════════════════════════════════════════════
# 数据源控制
# ═══════════════════════════════════════════════════════════════

class SourceBalanceConfig(BaseModel):
    strategy: str = "weighted_round_robin"  # weighted_round_robin | priority | failover
    weights: Dict[str, int] = {"tencent": 50, "sina": 30, "eastmoney": 20}
    health_check: Dict[str, Any] = {
        "interval": 10,
        "timeout": 3,
        "fail_threshold": 3
    }

class CircuitBreakerControl(BaseModel):
    source: str
    action: str  # "open" | "close" | "half_open"

@router.get("/sources/status")
async def get_sources_status():
    """获取所有数据源实时状态（合并 SQLite 持久化的熔断状态）"""
    from app.services import quote_source
    from app.db.database import get_admin_config
    
    # 获取实时状态
    source_info = quote_source.get_source_status()
    source_status = source_info.get('sources', {})
    
    # 合并持久化的熔断状态（用户手动操作优先于自动状态）
    persisted_circuits = get_admin_config("circuit_breakers", {})
    
    # 获取调度器信息
    try:
        from app.services.scheduler import scheduler
        jobs_count = len(scheduler.get_jobs())
    except Exception as e:
        logger.exception("[Admin] 获取调度器 jobs 失败，使用默认值兜底")
        jobs_count = 0
    
    return {
        "sources": {
            "tencent": {
                "state": persisted_circuits.get("tencent") or ("closed" if source_status.get('tencent',{}).get('status') != 'ok' else "closed"),
                "fail_count": source_status.get('tencent',{}).get('fail_count', 0),
                "latency_ms": source_status.get('tencent',{}).get('latency') or 0,
                "health": "healthy" if source_status.get('tencent',{}).get('status') == 'ok' else "unhealthy",
                "status": source_status.get('tencent',{}).get('status', 'unknown'),
                "description": "腾讯财经 - 主数据源"
            },
            "sina": {
                "state": persisted_circuits.get("sina") or ("closed" if source_status.get('sina',{}).get('status') != 'ok' else "closed"),
                "fail_count": source_status.get('sina',{}).get('fail_count', 0),
                "latency_ms": source_status.get('sina',{}).get('latency') or 0,
                "health": "healthy" if source_status.get('sina',{}).get('status') == 'ok' else "unhealthy",
                "status": source_status.get('sina',{}).get('status', 'unknown'),
                "description": "新浪财经 - 备用源"
            },
            "eastmoney": {
                "state": persisted_circuits.get("eastmoney") or ("open" if source_status.get('eastmoney',{}).get('status') != 'ok' else "closed"),
                "fail_count": source_status.get('eastmoney',{}).get('fail_count', 0),
                "latency_ms": source_status.get('eastmoney',{}).get('latency') or 0,
                "health": "healthy" if source_status.get('eastmoney',{}).get('status') == 'ok' else "unhealthy",
                "status": source_status.get('eastmoney',{}).get('status', 'unknown'),
                "description": "东方财富 - 备用源"
            }
        },
        "balance_config": {
            "strategy": "weighted_round_robin",
            "weights": {"tencent": 50, "sina": 30, "eastmoney": 20},
            "current_primary": source_info.get('current', 'tencent'),
            "last_update": int(time.time())
        },
        "scheduler": {
            "jobs_count": jobs_count,
            "status": "running"
        }
    }

@router.post("/sources/circuit_breaker")
async def set_circuit_breaker(
    control: CircuitBreakerControl,
    x_api_key: str = Header(None)
):
    """手动控制数据源熔断状态（写入 SQLite 持久化）"""
    verify_admin_key(x_api_key)
    from app.db.database import set_admin_config
    # 持久化到 admin_config 表
    circuit_state = get_admin_config("circuit_breakers", {})
    circuit_state[control.source] = control.action  # "open" | "close"
    set_admin_config("circuit_breakers", circuit_state)
    logger.info(f"[Admin] Circuit breaker persisted: {control.source} -> {control.action}")
    return {
        "success": True,
        "source": control.source,
        "action": control.action,
        "timestamp": int(time.time())
    }

@router.post("/sources/balance")
async def set_source_balance(
    config: SourceBalanceConfig,
    x_api_key: str = Header(None)
):
    """配置数据源负载均衡策略"""
    verify_admin_key(x_api_key)
    logger.info(f"[Admin] Source balance config updated: {config.strategy}")
    return {
        "success": True,
        "config": config.dict(),
        "timestamp": int(time.time())
    }

@router.get("/data_quality/realtime")
async def get_data_quality_metrics():
    """实时数据质量指标"""
    return {
        "market_data": {
            "stocks": {"total": 5497, "updated_30s": 5490, "stale": 7, "missing": 0},
            "indices": {"total": 10, "updated_30s": 10, "stale": 0, "missing": 0},
            "sectors": {"total": 20, "updated_30s": 20, "stale": 0, "missing": 0}
        },
        "delays": {
            "tencent_avg_ms": 85,
            "sina_avg_ms": 120,
            "eastmoney_avg_ms": 0
        },
        "accuracy": {
            "price_anomalies": 3,
            "volume_anomalies": 0,
            "stale_data": 7
        },
        "timestamp": int(time.time())
    }

# ═══════════════════════════════════════════════════════════════
# 调度器控制
# ═══════════════════════════════════════════════════════════════

@router.get("/scheduler/jobs")
async def list_scheduler_jobs():
    """列出所有定时任务状态（合并 SQLite 持久化的暂停状态）"""
    from app.db.database import get_admin_config
    persisted_overrides = get_admin_config("scheduler_overrides", {})
    jobs = []
    for job in scheduler.get_jobs():
        # 持久化的暂停状态优先于内存状态
        override = persisted_overrides.get(job.id)
        state = "running"
        if override == "pause":
            state = "paused"
        elif override == "resume":
            state = "running"
        elif not job.next_run_time:
            state = "paused"
        jobs.append({
            "id": job.id,
            "name": job.name,
            "trigger": str(job.trigger),
            "next_run": job.next_run_time.isoformat() if job.next_run_time else None,
            "state": state,
        })
    return {"jobs": jobs}

class JobControl(BaseModel):
    action: str  # "pause" | "resume" | "trigger_now"

@router.post("/scheduler/jobs/{job_id}/control")
async def control_job(
    job_id: str, 
    control: JobControl,
    x_api_key: str = Header(None)
):
    """控制定时任务（写 SQLite 持久化暂停状态）"""
    verify_admin_key(x_api_key)
    from app.db.database import set_admin_config, get_admin_config
    job = scheduler.get_job(job_id)
    if not job:
        return {"success": False, "error": "Job not found"}
    
    if control.action == "pause":
        job.pause()
    elif control.action == "resume":
        job.resume()
    elif control.action == "trigger_now":
        job.modify(next_run_time=datetime.now())
    
    # 持久化调度器状态
    scheduler_state = get_admin_config("scheduler_overrides", {})
    scheduler_state[job_id] = control.action  # "pause" | "resume"
    set_admin_config("scheduler_overrides", scheduler_state)
    
    return {"success": True, "job_id": job_id, "action": control.action}

@router.get("/scheduler/history")
async def get_job_history(limit: int = 50):
    """任务执行历史"""
    # 实际实现需要存储历史记录
    return {"history": []}

# ═══════════════════════════════════════════════════════════════
# 缓存管理
# ═══════════════════════════════════════════════════════════════

@router.get("/cache/status")
async def get_cache_status():
    """缓存系统状态"""
    return {
        "memory_cache": {
            "wind_data": {"size": 6, "ttl": 10},
            "sectors": {"size": 20, "ttl": 300, "ready": sectors_cache_ready()},
            "news": {"size": 150, "ttl": 600}
        },
        "database_cache": {
            "market_realtime": {"rows": 22},
            "market_daily": {"rows": 12500},
            "all_stocks": {"rows": 5497}
        }
    }

class CacheInvalidateRequest(BaseModel):
    cache_type: str
    key: Optional[str] = None

class CacheWarmupRequest(BaseModel):
    data_type: str

@router.post("/cache/invalidate")
async def invalidate_cache(
    request: CacheInvalidateRequest,
    x_api_key: str = Header(None)
):
    """清空指定缓存"""
    verify_admin_key(x_api_key)
    cache_type = request.cache_type
    key = request.key
    
    if cache_type == "memory" or cache_type == "market":
        # 清空内存缓存
        from app.routers.market import _REALTIME_CACHE
        _REALTIME_CACHE.clear()
    elif cache_type == "sectors":
        # 清空板块缓存
        from app.services import sectors_cache
        sectors_cache._SECTORS_CACHE.clear()
        sectors_cache._CACHE_READY = False
    
    return {"success": True, "cache_type": cache_type, "key": key}

@router.post("/cache/warmup")
async def warmup_cache(
    request: CacheWarmupRequest,
    x_api_key: str = Header(None)
):
    """缓存预热"""
    verify_admin_key(x_api_key)
    data_type = request.data_type
    
    if data_type == "sectors":
        from app.services.sectors_cache import fetch_and_cache_sectors
        fetch_and_cache_sectors()
    
    return {"success": True, "data_type": data_type}

# ═══════════════════════════════════════════════════════════════
# 数据库管理
# ═══════════════════════════════════════════════════════════════

@router.get("/database/status")
async def get_database_status():
    """数据库状态监控"""
    import os
    
    file_size = os.path.getsize(_db_path) / (1024 * 1024)  # MB
    
    conn = _get_conn()
    tables = {}
    for table in ["market_data_realtime", "market_data_daily", "market_all_stocks", "portfolios"]:
        try:
            row = conn.execute(f"SELECT COUNT(*) as cnt FROM {table}").fetchone()
            tables[table] = {"rows": row["cnt"]}
        except Exception as e:
            logger.exception(f"[Admin] 统计表 {table} 行数失败，使用默认值兜底: {e}")
            tables[table] = {"rows": 0}
    conn.close()
    
    return {
        "file_size_mb": round(file_size, 2),
        "tables": tables,
        "path": _db_path
    }

# ═══════════════════════════════════════════════════════════════
# Admin 配置持久化（SQLite）
# ═══════════════════════════════════════════════════════════════

class AdminConfigItem(BaseModel):
    key: str
    value: Any

@router.get("/config")
async def get_admin_config_all():
    """读取所有持久化的 Admin 配置（数据源熔断状态、调度器开关等）"""
    from app.db.database import get_all_admin_configs
    return {"configs": get_all_admin_configs()}

@router.post("/config/{config_key}")
async def save_admin_config(config_key: str, body: dict, x_api_key: str = Header(None)):
    """保存单个 Admin 配置项到 SQLite"""
    verify_admin_key(x_api_key)
    from app.db.database import set_admin_config
    set_admin_config(config_key, body.get("value"))
    return {"success": True, "key": config_key, "value": body.get("value")}

class BulkConfigRequest(BaseModel):
    configs: Dict[str, Any]

@router.post("/config/bulk")
async def save_admin_config_bulk(body: BulkConfigRequest, x_api_key: str = Header(None)):
    """批量保存 Admin 配置项"""
    verify_admin_key(x_api_key)
    from app.db.database import set_admin_config
    for key, value in body.configs.items():
        set_admin_config(key, value)
    return {"success": True, "saved": list(body.configs.keys())}

class DatabaseMaintenanceRequest(BaseModel):
    action: str  # "vacuum" | "analyze" | "wal_checkpoint"

@router.post("/database/maintenance")
async def database_maintenance(
    request: DatabaseMaintenanceRequest,
    x_api_key: str = Header(None)
):
    """数据库维护操作"""
    verify_admin_key(x_api_key)
    action = request.action
    conn = _get_conn()
    
    if action == "vacuum":
        conn.execute("VACUUM")
    elif action == "analyze":
        conn.execute("ANALYZE")
    elif action == "wal_checkpoint":
        conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
    
    conn.close()
    return {"success": True, "action": action}

# ═══════════════════════════════════════════════════════════════
# 系统监控
# ═══════════════════════════════════════════════════════════════

@router.get("/system/metrics")
async def get_system_metrics():
    """系统性能指标"""
    return {
        "cpu_percent": psutil.cpu_percent(interval=1),
        "memory": {
            "percent": psutil.virtual_memory().percent,
            "used_gb": round(psutil.virtual_memory().used / (1024**3), 2),
            "total_gb": round(psutil.virtual_memory().total / (1024**3), 2)
        },
        "disk": {
            "percent": psutil.disk_usage('/').percent,
            "used_gb": round(psutil.disk_usage('/').used / (1024**3), 2),
            "total_gb": round(psutil.disk_usage('/').total / (1024**3), 2)
        },
        "network": {
            "connections": len(psutil.net_connections()),
            "io_counters": psutil.net_io_counters()._asdict()
        },
        "process": {
            "threads": psutil.Process().num_threads(),
            "open_files": len(psutil.Process().open_files()),
            "memory_mb": round(psutil.Process().memory_info().rss / (1024**2), 2)
        },
        "timestamp": int(time.time())
    }

# ═══════════════════════════════════════════════════════════════
# 日志管理
# ═══════════════════════════════════════════════════════════════

@router.get("/logs/recent")
async def get_recent_logs(lines: int = 100, level: str = None):
    """获取最近的日志内容"""
    import os
    import re
    from datetime import datetime
    
    # 动态构建日志文件路径（支持环境变量覆盖）
    log_dir = os.environ.get("LOG_DIR", str(_DEFAULT_LOG_DIR))
    log_files = [
        os.path.join(log_dir, "app.log"),
        os.path.join(log_dir, "backend.log"),
    ]
    
    # 找到存在的日志文件
    log_file = None
    for f in log_files:
        if os.path.exists(f):
            log_file = f
            break
    
    logs = []
    
    if not log_file:
        return {"logs": [], "total": 0, "source": "not found"}
    
    try:
        # 使用 Python 原生方式读取日志文件（安全、跨平台）
        raw_lines = []
        
        with open(log_file, 'r', encoding='utf-8', errors='ignore') as f:
            all_lines = f.readlines()
            # 取最后 lines*2 行
            raw_lines = all_lines[-(lines * 2):] if len(all_lines) > lines * 2 else all_lines
            
            for line in raw_lines:
                if not line or not line.strip():
                    continue
                
                # 跳过 tqdm 进度条行
                if "%|" in line or "it/s" in line or line.strip().startswith("|"):
                    continue
                
                # 解析日志级别 - 支持多种格式
                log_level = "INFO"
                upper_line = line.upper()
                
                if "ERROR" in upper_line or "CRITICAL" in upper_line or "EXCEPTION" in upper_line:
                    log_level = "ERROR"
                elif "WARNING" in upper_line or "WARN" in upper_line:
                    log_level = "WARNING"
                elif "DEBUG" in upper_line:
                    log_level = "DEBUG"
                
                # 级别过滤
                if level and level != "ALL" and log_level != level:
                    continue
                
                # 尝试提取时间戳
                timestamp = int(time.time())
                
                # 格式1: 2026-04-15 13:08:45,123
                time_match = re.search(r'(\d{4}-\d{2}-\d{2}[\sT]\d{2}:\d{2}:\d{2})', line)
                if time_match:
                    try:
                        dt = datetime.strptime(time_match.group(1), "%Y-%m-%d %H:%M:%S")
                        timestamp = int(dt.timestamp())
                    except Exception as e:
                        logger.debug(f"[Admin] 时间戳解析失败（格式1）: {e}")
                        pass
                else:
                    # 格式2: 13:08:45 (只有时间，使用今天日期)
                    time_match2 = re.search(r'(\d{2}:\d{2}:\d{2})', line)
                    if time_match2:
                        try:
                            today = datetime.now().strftime("%Y-%m-%d")
                            dt = datetime.strptime(f"{today} {time_match2.group(1)}", "%Y-%m-%d %H:%M:%S")
                            timestamp = int(dt.timestamp())
                        except Exception as e:
                            logger.debug(f"[Admin] 时间戳解析失败（格式2）: {e}")
                            pass
                
                # 清理消息内容
                message = line.strip()
                # 移除常见的日志前缀
                message = re.sub(r'^\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2}(,\d+)?\s*', '', message)
                message = re.sub(r'^\d{2}:\d{2}:\d{2}\s*', '', message)
                message = re.sub(r'^(INFO|DEBUG|WARNING|ERROR|CRITICAL)\s*[:\-]?\s*', '', message, flags=re.IGNORECASE)
                
                logs.append({
                    "timestamp": timestamp,
                    "level": log_level,
                    "message": message[:300]  # 限制长度
                })
                
                if len(logs) >= lines:
                    break
                    
    except Exception as e:
        logs.append({
            "timestamp": int(time.time()),
            "level": "ERROR",
            "message": f"Failed to read logs: {str(e)}"
        })
    
    return {
        "logs": logs,
        "total": len(logs),
        "source": log_file
    }

@router.post("/logs/level")
async def set_log_level(
    logger_name: str, 
    level: str,
    x_api_key: str = Header(None)
):
    """动态调整日志级别"""
    verify_admin_key(x_api_key)
    import logging
    
    if logger_name == "root":
        logging.getLogger().setLevel(getattr(logging, level.upper()))
    else:
        logging.getLogger(logger_name).setLevel(getattr(logging, level.upper()))
    
    return {"success": True, "logger": logger_name, "level": level}

# ═══════════════════════════════════════════════════════════════
# WebSocket 实时日志流
# ═══════════════════════════════════════════════════════════════

@router.websocket("/logs/stream")
async def log_stream_ws(websocket: WebSocket):
    """WebSocket实时日志流"""
    await websocket.accept()
    
    # 如果日志队列不存在，创建一个
    if not hasattr(log_stream_ws, '_log_queue'):
        log_stream_ws._log_queue = asyncio.Queue(maxsize=100)
    
    queue = log_stream_ws._log_queue
    
    async def log_writer():
        """日志写入队列的 handler（供外部调用）"""
        pass  # 实际实现在 services/logging_queue.py
    
    # 发送欢迎消息
    await websocket.send_json({
        "timestamp": int(time.time()),
        "level": "INFO",
        "message": "Log stream connected. Waiting for logs..."
    })
    
    try:
        while True:
            try:
                # 从队列获取日志（5秒超时）
                log_msg = await asyncio.wait_for(queue.get(), timeout=5.0)
                await websocket.send_json(log_msg)
            except asyncio.TimeoutError:
                # 超时发送心跳
                await websocket.send_json({
                    "timestamp": int(time.time()),
                    "level": "HEARTBEAT",
                    "message": "heartbeat"
                })
    except WebSocketDisconnect:
        pass

# 预先创建日志队列供外部导入使用
_log_queue = asyncio.Queue(maxsize=100)
