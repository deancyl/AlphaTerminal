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

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, HTTPException, Depends, Header, Body
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

# ═══════════════════════════════════════════════════════════════
# 认证机制（必须在 router 定义之前，否则 NameError）
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

# router 定义（在 verify_admin_key 之后）
router = APIRouter(
    prefix="/admin", 
    tags=["admin"],
    dependencies=[Depends(verify_admin_key)]
)


# ═══════════════════════════════════════════════════════════════
# LLM 配置管理（API Key 可视化配置）
# ═══════════════════════════════════════════════════════════════

def _mask_key(key: str) -> str:
    """掩码处理 API Key"""
    if not key:
        return ""
    if len(key) <= 8:
        return key
    return f"{key[:6]}...{key[-4:]}"

@router.get("/settings/llm")
def get_llm_settings():
    """获取 LLM 配置（API Key 已掩码）。优先级：数据库 > .env > 默认值"""
    from app.db.database import get_admin_config
    providers = ["deepseek", "qianwen", "openai"]
    defaults = {
        "deepseek": {"base_url": "https://api.deepseek.com", "model": "deepseek-chat"},
        "qianwen":  {"base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1", "model": "qwen-plus"},
        "openai":   {"base_url": "https://api.openai.com/v1", "model": "gpt-3.5-turbo"},
    }
    result = {}
    for p in providers:
        db  = get_admin_config(f"llm_{p}") or {}
        env = os.getenv(f"{p.upper()}_API_KEY", "")
        result[p] = {
            "api_key":       _mask_key(db.get("api_key") or env),
            "base_url":      db.get("base_url") or defaults[p]["base_url"],
            "model":          db.get("model")    or defaults[p]["model"],
            "has_db_config":  bool(db.get("api_key")),
        }
    return {"code": 0, "data": result}

@router.post("/settings/llm")
def save_llm_settings(body: dict = Body(...)):
    """保存 LLM 配置到数据库（永久生效）"""
    from app.db.database import get_admin_config, set_admin_config
    provider = (body.get("provider") or "").lower()
    key_map  = {"deepseek": "llm_deepseek", "qianwen": "llm_qianwen", "openai": "llm_openai"}
    if provider not in key_map:
        return {"code": 1, "error": f"Unknown provider: {provider}"}
    set_admin_config(key_map[provider], {
        "api_key":  body.get("api_key", "").strip(),
        "base_url": body.get("base_url", "").strip(),
        "model":    body.get("model", "").strip(),
    })
    return {"code": 0, "message": f"{provider} 配置已保存"}

@router.post("/settings/llm/test")
def test_llm_connection(body: dict = Body(...)):
    """探测 LLM Provider 连接"""
    import httpx
    provider = (body.get("provider") or "").lower()
    api_key  = (body.get("api_key") or "").strip()
    base_url = (body.get("base_url") or "").strip()
    model    = (body.get("model") or "").strip()
    if not api_key:
        return {"code": 1, "error": "API Key 不能为空"}
    defaults = {"deepseek": "deepseek-chat", "qianwen": "qwen-plus", "openai": "gpt-3.5-turbo"}
    test_url  = f"{base_url.rstrip('/')}/chat/completions"
    headers   = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    payload   = {"model": model or defaults.get(provider, "gpt-3.5-turbo"),
                 "messages": [{"role": "user", "content": "Hi"}], "max_tokens": 5}
    try:
        resp = httpx.post(test_url, headers=headers, json=payload, timeout=15)
        if resp.status_code == 200:
            return {"code": 0, "message": "连接成功 ✅", "status": resp.status_code}
        err = resp.json().get("error", {}) if "json" in resp.headers.get("content-type","") else {}
        return {"code": 1, "error": f"HTTP {resp.status_code}: {err.get('message', resp.text[:80])}"}
    except httpx.TimeoutException:
        return {"code": 1, "error": "连接超时，请检查 URL"}
    except Exception as e:
        return {"code": 1, "error": str(e)[:100]}


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
    
    # 从 quote_source 获取实时状态
    status_data = quote_source.get_source_status()
    real_time = status_data.get("sources", {})
    
    # 从 SQLite 获取持久化熔断状态
    conn = _get_conn()
    cursor = conn.cursor()
    cursor.execute("SELECT source, state, fail_count, last_fail_time FROM circuit_breaker")
    db_states = {row[0]: {"state": row[1], "fail_count": row[2], "last_fail_time": row[3]} for row in cursor.fetchall()}
    
    # 合并状态
    merged = {}
    for source, status in real_time.items():
        db_state = db_states.get(source, {})
        merged[source] = {
            **status,
            "state": db_state.get("state", status.get("state", "unknown")),
            "fail_count": db_state.get("fail_count", 0),
            "last_fail_time": db_state.get("last_fail_time")
        }
    
    return {"sources": merged, "timestamp": int(time.time())}

@router.post("/sources/circuit_breaker")
async def control_circuit_breaker(control: CircuitBreakerControl):
    """手动控制熔断器"""
    from app.services import quote_source
    
    if control.action == "open":
        quote_source.open_circuit(control.source)
        # 持久化到 SQLite
        conn = _get_conn()
        cursor = conn.cursor()
        cursor.execute(
            "INSERT OR REPLACE INTO circuit_breaker (source, state, updated_at) VALUES (?, ?, ?)",
            (control.source, "open", datetime.now().isoformat())
        )
        conn.commit()
        return {"message": f"已熔断 {control.source}", "state": "open"}
    
    elif control.action == "close":
        quote_source.close_circuit(control.source)
        conn = _get_conn()
        cursor = conn.cursor()
        cursor.execute(
            "INSERT OR REPLACE INTO circuit_breaker (source, state, updated_at) VALUES (?, ?, ?)",
            (control.source, "closed", datetime.now().isoformat())
        )
        conn.commit()
        return {"message": f"已恢复 {control.source}", "state": "closed"}
    
    else:
        raise HTTPException(status_code=400, detail=f"Unknown action: {control.action}")

@router.get("/sources/balance")
async def get_balance_config():
    """获取负载均衡配置"""
    conn = _get_conn()
    cursor = conn.cursor()
    cursor.execute("SELECT config_value FROM system_config WHERE config_key = 'source_balance'")
    row = cursor.fetchone()
    if row:
        import json
        return json.loads(row[0])
    return SourceBalanceConfig().dict()

@router.post("/sources/balance")
async def set_balance_config(config: SourceBalanceConfig):
    """设置负载均衡配置"""
    import json
    conn = _get_conn()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT OR REPLACE INTO system_config (config_key, config_value, updated_at) VALUES (?, ?, ?)",
        ("source_balance", json.dumps(config.dict()), datetime.now().isoformat())
    )
    conn.commit()
    return {"message": "负载均衡配置已更新", "config": config.dict()}


# ═══════════════════════════════════════════════════════════════
# 调度器控制
# ═══════════════════════════════════════════════════════════════

@router.get("/scheduler/jobs")
async def get_scheduler_jobs():
    """获取所有定时任务状态"""
    jobs = scheduler.get_jobs()
    return {
        "jobs": [
            {
                "id": job.id,
                "name": job.name,
                "next_run_time": job.next_run_time.isoformat() if job.next_run_time else None,
                "trigger": str(job.trigger),
            }
            for job in jobs
        ]
    }

@router.post("/scheduler/jobs/{job_id}/control")
async def control_scheduler_job(job_id: str, action: str = Body(..., embed=True)):
    """控制定时任务（pause/resume/run）"""
    if action == "pause":
        scheduler.pause_job(job_id)
        return {"message": f"任务 {job_id} 已暂停"}
    elif action == "resume":
        scheduler.resume_job(job_id)
        return {"message": f"任务 {job_id} 已恢复"}
    elif action == "run":
        job = scheduler.get_job(job_id)
        if job:
            job.modify(next_run_time=datetime.now())
            return {"message": f"任务 {job_id} 已触发立即执行"}
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found")
    else:
        raise HTTPException(status_code=400, detail=f"Unknown action: {action}")


# ═══════════════════════════════════════════════════════════════
# 缓存控制
# ═══════════════════════════════════════════════════════════════

@router.post("/cache/invalidate")
async def invalidate_cache(cache_type: str = Body(..., embed=True)):
    """清空指定缓存"""
    if cache_type == "sectors":
        from app.services.sectors_cache import invalidate
        invalidate()
        return {"message": "板块缓存已清空"}
    elif cache_type == "quotes":
        from app.services.quote_source import clear_cache
        clear_cache()
        return {"message": "行情缓存已清空"}
    elif cache_type == "all":
        from app.services.sectors_cache import invalidate as invalidate_sectors
        from app.services.quote_source import clear_cache as clear_quotes
        invalidate_sectors()
        clear_quotes()
        return {"message": "所有缓存已清空"}
    else:
        raise HTTPException(status_code=400, detail=f"Unknown cache type: {cache_type}")

@router.post("/cache/warmup")
async def warmup_cache(data_type: str = Body(..., embed=True)):
    """预热缓存"""
    if data_type == "sectors":
        from app.services.sectors_cache import warmup
        await warmup()
        return {"message": "板块缓存预热已启动"}
    elif data_type == "quotes":
        from app.services.quote_source import warmup
        await warmup()
        return {"message": "行情缓存预热已启动"}
    else:
        raise HTTPException(status_code=400, detail=f"Unknown data type: {data_type}")


# ═══════════════════════════════════════════════════════════════
# 数据库维护
# ═══════════════════════════════════════════════════════════════

@router.post("/database/maintenance")
async def database_maintenance(action: str = Body(..., embed=True)):
    """数据库维护操作"""
    conn = _get_conn()
    
    if action == "vacuum":
        conn.execute("VACUUM")
        return {"message": "数据库已优化 (VACUUM)"}
    elif action == "analyze":
        conn.execute("ANALYZE")
        return {"message": "数据库统计信息已更新 (ANALYZE)"}
    elif action == "integrity_check":
        cursor = conn.execute("PRAGMA integrity_check")
        result = cursor.fetchone()[0]
        return {"message": f"完整性检查结果: {result}", "status": result}
    else:
        raise HTTPException(status_code=400, detail=f"Unknown action: {action}")

@router.get("/database/stats")
async def get_database_stats():
    """获取数据库统计信息"""
    conn = _get_conn()
    cursor = conn.cursor()
    
    # 获取所有表的大小
    cursor.execute("""
        SELECT name, 
               (SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name=name) as count
        FROM sqlite_master 
        WHERE type='table'
    """)
    tables = cursor.fetchall()
    
    stats = {}
    for table_name, _ in tables:
        cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
        count = cursor.fetchone()[0]
        stats[table_name] = count
    
    # 获取数据库文件大小
    db_size = os.path.getsize(_db_path) if os.path.exists(_db_path) else 0
    
    return {
        "tables": stats,
        "total_tables": len(tables),
        "db_size_bytes": db_size,
        "db_size_mb": round(db_size / (1024 * 1024), 2)
    }


# ═══════════════════════════════════════════════════════════════
# 系统监控
# ═══════════════════════════════════════════════════════════════

@router.get("/system/metrics")
async def get_system_metrics():
    """获取系统资源使用情况"""
    cpu_percent = psutil.cpu_percent(interval=1)
    memory = psutil.virtual_memory()
    disk = psutil.disk_usage('/')
    
    return {
        "cpu_percent": cpu_percent,
        "memory": {
            "total": memory.total,
            "available": memory.available,
            "percent": memory.percent,
            "used": memory.used
        },
        "disk": {
            "total": disk.total,
            "used": disk.used,
            "free": disk.free,
            "percent": (disk.used / disk.total) * 100
        },
        "timestamp": int(time.time())
    }

@router.get("/system/logs")
async def get_recent_logs(lines: int = 100):
    """获取最近日志"""
    log_file = _DEFAULT_LOG_DIR / "app.log"
    if not log_file.exists():
        return {"logs": [], "message": "日志文件不存在"}
    
    with open(log_file, 'r') as f:
        all_lines = f.readlines()
    
    recent_lines = all_lines[-lines:] if len(all_lines) > lines else all_lines
    return {"logs": recent_lines}


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

# 初始化 error_logger 的队列引用
try:
    from app.services.error_logger import init_log_queue
    init_log_queue(_log_queue)
    logger.info("[Admin] error_logger 队列已初始化")
except Exception as e:
    logger.warning(f"[Admin] error_logger 初始化失败: {e}")


# ═══════════════════════════════════════════════════════════════
# 进程保活监控 (Watchdog)
# ═══════════════════════════════════════════════════════════════

@router.get("/watchdog/status")
async def get_watchdog_status():
    """获取进程保活监控状态"""
    from app.services.watchdog import get_watchdog_state
    return {
        "code": 0,
        "message": "success",
        "data": get_watchdog_state()
    }


@router.post("/watchdog/toggle")
async def toggle_watchdog_endpoint(body: dict = Body(...)):
    """切换进程保活开关
    
    请求体: {"enabled": true/false}
    """
    from app.services.watchdog import toggle_watchdog
    
    enabled = body.get("enabled")
    if enabled is None:
        return {"code": 400, "message": "缺少 enabled 参数"}
    
    success = toggle_watchdog(enabled)
    if success:
        return {
            "code": 0,
            "message": f"进程保活已{'启用' if enabled else '禁用'}",
            "data": {"enabled": enabled}
        }
    else:
        return {"code": 500, "message": "切换失败，请检查日志"}


@router.post("/watchdog/restart")
async def manual_restart_backend():
    """手动触发后端重启（用于紧急恢复）"""
    from app.services.watchdog import _restart_backend, _watchdog_state
    
    logger.warning("[Admin] 收到手动重启后端请求")
    success = _restart_backend()
    
    if success:
        _watchdog_state.record_restart()
        return {
            "code": 0,
            "message": "后端重启指令已发送，请等待 5-10 秒后刷新页面",
            "data": {"restart_time": datetime.now().isoformat()}
        }
    else:
        return {"code": 500, "message": "重启失败，请检查后端日志"}
