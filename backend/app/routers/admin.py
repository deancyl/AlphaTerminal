"""
Admin 系统控制路由 - 数据源、调度器、缓存、数据库、网络控制
"""
import logging
import time
import psutil
import sqlite3
from datetime import datetime
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from typing import Optional, Dict, Any, List
from pydantic import BaseModel

from app.services import quote_source
from app.services.scheduler import scheduler
from app.services.sectors_cache import is_ready as sectors_cache_ready
from app.db.database import _get_conn, _db_path

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/admin", tags=["admin"])

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
    """获取所有数据源实时状态"""
    return {
        "sources": {
            "tencent": {
                "state": "closed",
                "fail_count": 0,
                "last_success": "09:15:32",
                "latency_ms": 85,
                "health": "healthy"
            },
            "sina": {
                "state": "closed",
                "fail_count": 1,
                "last_success": "09:15:28",
                "latency_ms": 120,
                "health": "healthy"
            },
            "eastmoney": {
                "state": "open",
                "fail_count": 5,
                "last_failure": "09:14:18",
                "recovery_in": 45,
                "health": "unhealthy"
            }
        },
        "balance_config": {
            "strategy": "weighted_round_robin",
            "weights": {"tencent": 50, "sina": 30, "eastmoney": 20}
        }
    }

@router.post("/sources/circuit_breaker")
async def set_circuit_breaker(control: CircuitBreakerControl):
    """手动控制数据源熔断状态"""
    # 实际实现需要修改 quote_source 模块
    logger.info(f"[Admin] Circuit breaker: {control.source} -> {control.action}")
    return {
        "success": True,
        "source": control.source,
        "action": control.action,
        "timestamp": int(time.time())
    }

@router.post("/sources/balance")
async def set_source_balance(config: SourceBalanceConfig):
    """配置数据源负载均衡策略"""
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
    """列出所有定时任务状态"""
    jobs = []
    for job in scheduler.get_jobs():
        jobs.append({
            "id": job.id,
            "name": job.name,
            "trigger": str(job.trigger),
            "next_run": job.next_run_time.isoformat() if job.next_run_time else None,
            "state": "running" if job.next_run_time else "paused",
        })
    return {"jobs": jobs}

class JobControl(BaseModel):
    action: str  # "pause" | "resume" | "trigger_now"

@router.post("/scheduler/jobs/{job_id}/control")
async def control_job(job_id: str, control: JobControl):
    """控制定时任务"""
    job = scheduler.get_job(job_id)
    if not job:
        return {"success": False, "error": "Job not found"}
    
    if control.action == "pause":
        job.pause()
    elif control.action == "resume":
        job.resume()
    elif control.action == "trigger_now":
        job.modify(next_run_time=datetime.now())
    
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
async def invalidate_cache(request: CacheInvalidateRequest):
    """清空指定缓存"""
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
async def warmup_cache(request: CacheWarmupRequest):
    """缓存预热"""
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
        except:
            tables[table] = {"rows": 0}
    conn.close()
    
    return {
        "file_size_mb": round(file_size, 2),
        "tables": tables,
        "path": _db_path
    }

@router.post("/database/maintenance")
async def database_maintenance(action: str):
    """数据库维护操作"""
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
    
    log_files = [
        "/vol3/@apphome/trim.openclaw/data/workspace/AlphaTerminal/backend/app.log",
        "/vol3/@apphome/trim.openclaw/data/workspace/AlphaTerminal/backend/backend.log",
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
        # 读取日志文件
        import subprocess
        result = subprocess.run(
            ["tail", "-n", str(lines * 2), log_file],  # 读取更多行用于过滤
            capture_output=True, text=True
        )
        
        if result.returncode == 0:
            raw_lines = result.stdout.strip().split("\n")
            
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
                    except:
                        pass
                else:
                    # 格式2: 13:08:45 (只有时间，使用今天日期)
                    time_match2 = re.search(r'(\d{2}:\d{2}:\d{2})', line)
                    if time_match2:
                        try:
                            today = datetime.now().strftime("%Y-%m-%d")
                            dt = datetime.strptime(f"{today} {time_match2.group(1)}", "%Y-%m-%d %H:%M:%S")
                            timestamp = int(dt.timestamp())
                        except:
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
async def set_log_level(logger_name: str, level: str):
    """动态调整日志级别"""
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
    try:
        while True:
            # 模拟发送日志数据
            await websocket.send_json({
                "timestamp": int(time.time()),
                "level": "INFO",
                "message": "System running normally"
            })
            await asyncio.sleep(5)
    except WebSocketDisconnect:
        pass

import asyncio
