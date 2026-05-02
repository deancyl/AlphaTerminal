"""
Debug / Diagnostics Router v2.0
===============================
管理面板联动的Debug工作流API

Features:
  1. 获取Debug工具列表
  2. 执行Debug脚本（异步+实时推送）
  3. 查看Debug历史报告
  4. 聚合健康检查
  5. WebSocket实时推送Debug结果
"""
import logging
import json
import asyncio
import subprocess
import os
import time
from datetime import datetime
from typing import List, Dict, Optional
from pathlib import Path

from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect, HTTPException, Header, Depends
from pydantic import BaseModel, Field

from app.services.ws_manager import ws_manager

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/debug", tags=["Debug"])

# ═══════════════════════════════════════════════════════════════
# 认证保护
# ═══════════════════════════════════════════════════════════════
DEBUG_API_KEY = os.environ.get("DEBUG_API_KEY", "")

def verify_debug_auth(x_api_key: str = Header(None, alias="X-API-Key")):
    """Debug API 认证（可选，生产环境建议配置）"""
    # 未配置 key 时跳过认证（开发环境）
    if not DEBUG_API_KEY:
        return True
    if x_api_key != DEBUG_API_KEY:
        raise HTTPException(status_code=401, detail="Invalid or missing API key")
    return True

# ═══════════════════════════════════════════════════════════════
# 配置
# ═══════════════════════════════════════════════════════════════
SCRIPT_DIR = Path(__file__).parent.parent.parent.parent / "scripts" / "debug"
REPORT_DIR = Path("/tmp/alphaterminal_reports")
REPORT_DIR.mkdir(exist_ok=True)

# Debug工具定义
DEBUG_TOOLS = [
    {
        "id": "quick_check",
        "name": "快速健康检查",
        "description": "检查所有服务的运行状态、API可用性、进程状态",
        "script": "quick_check.sh",
        "supports_json": True,
        "category": "health",
        "icon": "Activity",
        "timeout": 30
    },
    {
        "id": "api_check",
        "name": "API接口测试",
        "description": "测试所有后端API端点的响应状态",
        "script": "api_debug.sh",
        "supports_json": True,
        "category": "api",
        "icon": "Server",
        "timeout": 60
    },
    {
        "id": "database_check",
        "name": "数据库诊断",
        "description": "检查SQLite数据库完整性、表大小、索引状态",
        "script": "database_debug.sh",
        "supports_json": False,
        "category": "database",
        "icon": "Database",
        "timeout": 30
    },
    {
        "id": "security_audit",
        "name": "安全审计",
        "description": "运行Bandit、Safety扫描，检查密钥泄露",
        "script": "security_audit.sh",
        "supports_json": False,
        "category": "security",
        "icon": "Shield",
        "timeout": 120
    },
    {
        "id": "performance",
        "name": "性能分析",
        "description": "测量API响应时间，生成性能基线",
        "script": "performance_profile.sh",
        "supports_json": False,
        "category": "performance",
        "icon": "TrendingUp",
        "timeout": 120
    },
    {
        "id": "websocket_check",
        "name": "WebSocket测试",
        "description": "测试WebSocket连接、消息收发、延迟",
        "script": "websocket_debug.py",
        "supports_json": True,
        "category": "websocket",
        "icon": "Radio",
        "timeout": 30
    },
    {
        "id": "log_analysis",
        "name": "日志分析",
        "description": "分析后端/前端日志，统计错误和异常",
        "script": "log_analyzer.py",
        "supports_json": True,
        "category": "logs",
        "icon": "FileText",
        "timeout": 30
    }
]

# ═══════════════════════════════════════════════════════════════
# 数据模型
# ═══════════════════════════════════════════════════════════════
class DebugTool(BaseModel):
    id: str
    name: str
    description: str
    category: str
    icon: str
    timeout: int

class DebugExecutionRequest(BaseModel):
    tool_id: str = Field(..., description="要执行的debug工具ID")
    options: Dict[str, str] = Field(default_factory=dict, description="额外选项")

class DebugExecutionResult(BaseModel):
    id: str
    tool_id: str
    status: str
    start_time: str
    end_time: Optional[str]
    duration_ms: int
    output: str
    json_output: Optional[dict]
    exit_code: int

class HealthAggregation(BaseModel):
    overall_status: str
    backend_status: str
    frontend_status: str
    database_status: str
    last_check: str
    issues: List[Dict]

# ═══════════════════════════════════════════════════════════════
# 执行状态存储（生产环境应使用Redis）
# ═══════════════════════════════════════════════════════════════
execution_store: Dict[str, dict] = {}

# ═══════════════════════════════════════════════════════════════
# 辅助函数
# ═══════════════════════════════════════════════════════════════
async def run_script(script_name: str, args: List[str] = None, timeout: int = 60) -> dict:
    """异步执行脚本"""
    script_path = SCRIPT_DIR / script_name
    
    if not script_path.exists():
        return {
            "status": "error",
            "output": f"Script not found: {script_path}",
            "exit_code": -1
        }
    
    cmd = [str(script_path)]
    if args:
        cmd.extend(args)
    
    start_time = time.time()
    
    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=str(SCRIPT_DIR)
        )
        
        stdout, stderr = await asyncio.wait_for(
            proc.communicate(), 
            timeout=timeout
        )
        
        duration = int((time.time() - start_time) * 1000)
        output = stdout.decode('utf-8', errors='ignore')
        
        if stderr:
            output += "\n[STDERR]\n" + stderr.decode('utf-8', errors='ignore')
        
        return {
            "status": "success" if proc.returncode == 0 else "failed",
            "output": output,
            "exit_code": proc.returncode,
            "duration_ms": duration
        }
        
    except asyncio.TimeoutError:
        proc.kill()
        return {
            "status": "timeout",
            "output": f"Script timed out after {timeout}s",
            "exit_code": -1,
            "duration_ms": timeout * 1000
        }
    except Exception as e:
        return {
            "status": "error",
            "output": f"Execution error: {str(e)}",
            "exit_code": -1,
            "duration_ms": int((time.time() - start_time) * 1000)
        }

def parse_json_output(output: str) -> Optional[dict]:
    """尝试从输出中解析JSON"""
    try:
        # 尝试直接解析
        return json.loads(output)
    except json.JSONDecodeError:
        pass
    
    # 尝试从输出中提取JSON块
    try:
        lines = output.split('\n')
        for line in lines:
            line = line.strip()
            if line.startswith('{') and line.endswith('}'):
                return json.loads(line)
    except (json.JSONDecodeError, IndexError):
        pass
    
    return None

# ═══════════════════════════════════════════════════════════════
# API路由
# ═══════════════════════════════════════════════════════════════

@router.get("/tools", dependencies=[Depends(verify_debug_auth)], response_model=List[DebugTool])
async def list_debug_tools():
    """
    获取所有可用的Debug工具列表
    
    Returns:
        List[DebugTool]: Debug工具列表
    """
    return [DebugTool(**tool) for tool in DEBUG_TOOLS]


@router.post("/execute", dependencies=[Depends(verify_debug_auth)], response_model=DebugExecutionResult)
async def execute_debug_tool(request: DebugExecutionRequest):
    """
    执行指定的Debug工具
    
    Args:
        request: 执行请求，包含tool_id和选项
        
    Returns:
        DebugExecutionResult: 执行结果
    """
    tool = next((t for t in DEBUG_TOOLS if t["id"] == request.tool_id), None)
    if not tool:
        return DebugExecutionResult(
            id="",
            tool_id=request.tool_id,
            status="error",
            start_time=datetime.now().isoformat(),
            end_time=datetime.now().isoformat(),
            duration_ms=0,
            output=f"Unknown tool: {request.tool_id}",
            json_output=None,
            exit_code=-1
        )
    
    execution_id = f"{request.tool_id}_{int(time.time())}"
    start_time = datetime.now()
    
    # 准备参数
    args = []
    if tool.get("supports_json", False):
        args.append("--json")
    
    # 添加自定义选项
    for key, value in request.options.items():
        args.append(f"--{key}")
        if value:
            args.append(value)
    
    # 执行脚本
    result = await run_script(
        tool["script"], 
        args, 
        timeout=tool.get("timeout", 60)
    )
    
    end_time = datetime.now()
    duration = result.get("duration_ms", 0)
    
    # 解析JSON输出
    json_output = None
    if tool.get("supports_json", False):
        json_output = parse_json_output(result["output"])
    
    # 保存执行记录
    execution_record = {
        "id": execution_id,
        "tool_id": request.tool_id,
        "status": result["status"],
        "start_time": start_time.isoformat(),
        "end_time": end_time.isoformat(),
        "duration_ms": duration,
        "output": result["output"],
        "json_output": json_output,
        "exit_code": result["exit_code"]
    }
    execution_store[execution_id] = execution_record
    
    # 保存报告到文件
    report_file = REPORT_DIR / f"{execution_id}.json"
    with open(report_file, 'w', encoding='utf-8') as f:
        json.dump(execution_record, f, ensure_ascii=False, indent=2)
    
    return DebugExecutionResult(**execution_record)


@router.get("/executions", dependencies=[Depends(verify_debug_auth)])
async def list_executions(
    tool_id: Optional[str] = None,
    limit: int = Query(default=10, le=100)
):
    """
    获取Debug执行历史
    
    Args:
        tool_id: 过滤特定工具
        limit: 返回数量限制
        
    Returns:
        List[DebugExecutionResult]: 执行历史列表
    """
    executions = list(execution_store.values())
    
    if tool_id:
        executions = [e for e in executions if e["tool_id"] == tool_id]
    
    # 按时间倒序
    executions.sort(key=lambda x: x["start_time"], reverse=True)
    executions = executions[:limit]
    
    return [DebugExecutionResult(**e) for e in executions]


@router.get("/executions/{execution_id}", dependencies=[Depends(verify_debug_auth)])
async def get_execution(execution_id: str):
    """
    获取特定执行的详细结果
    
    Args:
        execution_id: 执行ID
        
    Returns:
        DebugExecutionResult: 执行结果详情
    """
    if execution_id not in execution_store:
        return {"code": 1, "message": f"Execution not found: {execution_id}"}
    
    return DebugExecutionResult(**execution_store[execution_id])


@router.get("/health/aggregate", dependencies=[Depends(verify_debug_auth)], response_model=HealthAggregation)
async def aggregate_health():
    """
    聚合健康检查 - 快速获取系统整体状态
    
    Returns:
        HealthAggregation: 聚合健康状态
    """
    start_time = time.time()
    issues = []
    
    # 检查后端
    backend_status = "unknown"
    try:
        result = await run_script(
            "quick_check.sh", 
            ["--json", "--backend-url", "http://localhost:8002", "--frontend-url", "http://localhost:60100"], 
            timeout=10
        )
        if result["exit_code"] == 0:
            json_output = parse_json_output(result["output"])
            if json_output:
                # 解析quick_check结果
                checks = json_output.get("checks", {})
                backend_check = checks.get("Backend Health", {})
                if backend_check.get("status") == "passed":
                    backend_status = "healthy"
                else:
                    backend_status = "unhealthy"
                    issues.append({
                        "component": "backend",
                        "severity": "error",
                        "message": "Backend health check failed"
                    })
        else:
            backend_status = "error"
            issues.append({
                "component": "backend",
                "severity": "error",
                "message": "Backend unreachable"
            })
    except Exception as e:
        backend_status = "error"
        issues.append({
            "component": "backend",
            "severity": "error",
            "message": str(e)
        })
    
    # 检查数据库
    db_status = "unknown"
    try:
        result = await run_script("database_debug.sh", timeout=15)
        if result["exit_code"] == 0 and "Integrity check: OK" in result["output"]:
            db_status = "healthy"
        else:
            db_status = "unhealthy"
            issues.append({
                "component": "database",
                "severity": "warning",
                "message": "Database integrity check failed"
            })
    except Exception as e:
        db_status = "error"
    
    # 检查前端（简化）
    frontend_status = "unknown"
    try:
        import urllib.request
        req = urllib.request.Request("http://localhost:60100", method='HEAD')
        try:
            urllib.request.urlopen(req, timeout=5)
            frontend_status = "healthy"
        except:
            frontend_status = "unhealthy"
            issues.append({
                "component": "frontend",
                "severity": "warning",
                "message": "Frontend not accessible"
            })
    except:
        pass
    
    # 确定整体状态
    statuses = [backend_status, db_status, frontend_status]
    if any(s == "error" for s in statuses):
        overall = "critical"
    elif any(s == "unhealthy" for s in statuses):
        overall = "degraded"
    elif all(s == "healthy" for s in statuses):
        overall = "healthy"
    else:
        overall = "unknown"
    
    duration = int((time.time() - start_time) * 1000)
    
    return HealthAggregation(
        overall_status=overall,
        backend_status=backend_status,
        frontend_status=frontend_status,
        database_status=db_status,
        last_check=datetime.now().isoformat(),
        issues=issues
    )


@router.get("/reports", dependencies=[Depends(verify_debug_auth)])
async def list_reports(limit: int = Query(default=20, le=100)):
    """
    获取历史报告列表
    
    Args:
        limit: 返回数量限制
        
    Returns:
        List[dict]: 报告列表
    """
    reports = []
    
    for report_file in sorted(REPORT_DIR.glob("*.json"), reverse=True)[:limit]:
        try:
            with open(report_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                reports.append({
                    "id": data.get("id", report_file.stem),
                    "tool_id": data.get("tool_id", "unknown"),
                    "status": data.get("status", "unknown"),
                    "start_time": data.get("start_time"),
                    "duration_ms": data.get("duration_ms", 0),
                    "file": str(report_file.name)
                })
        except Exception as e:
            logger.warning(f"Failed to read report {report_file}: {e}")
    
    return reports


@router.delete("/reports/{report_id}", dependencies=[Depends(verify_debug_auth)])
async def delete_report(report_id: str):
    """
    删除特定报告
    
    Args:
        report_id: 报告ID
        
    Returns:
        dict: 操作结果
    """
    report_file = REPORT_DIR / f"{report_id}.json"
    
    if report_file.exists():
        report_file.unlink()
        # 同时从内存中移除
        if report_id in execution_store:
            del execution_store[report_id]
        return {"code": 0, "message": f"Report {report_id} deleted"}
    
    return {"code": 1, "message": f"Report not found: {report_id}"}


@router.websocket("/ws")
async def debug_websocket(websocket: WebSocket):
    """
    WebSocket实时推送Debug结果
    
    前端连接后，可以发送命令执行Debug工具并实时接收输出
    
    消息格式:
        {"action": "execute", "tool_id": "quick_check", "options": {}}
        {"action": "ping"}
    """
    await websocket.accept()
    client_id = f"debug_{id(websocket)}"
    
    try:
        await websocket.send_json({
            "type": "connected",
            "client_id": client_id,
            "message": "Debug WebSocket connected"
        })
        
        while True:
            message = await websocket.receive_json()
            action = message.get("action")
            
            if action == "ping":
                await websocket.send_json({
                    "type": "pong",
                    "timestamp": datetime.now().isoformat()
                })
            
            elif action == "execute":
                tool_id = message.get("tool_id")
                options = message.get("options", {})
                
                tool = next((t for t in DEBUG_TOOLS if t["id"] == tool_id), None)
                if not tool:
                    await websocket.send_json({
                        "type": "error",
                        "message": f"Unknown tool: {tool_id}"
                    })
                    continue
                
                # 发送开始信号
                await websocket.send_json({
                    "type": "started",
                    "tool_id": tool_id,
                    "timestamp": datetime.now().isoformat()
                })
                
                # 执行脚本
                args = []
                if tool.get("supports_json", False):
                    args.append("--json")
                
                for key, value in options.items():
                    args.append(f"--{key}")
                    if value:
                        args.append(str(value))
                
                result = await run_script(
                    tool["script"],
                    args,
                    timeout=tool.get("timeout", 60)
                )
                
                # 解析JSON
                json_output = None
                if tool.get("supports_json", False):
                    json_output = parse_json_output(result["output"])
                
                # 发送结果
                await websocket.send_json({
                    "type": "completed",
                    "tool_id": tool_id,
                    "status": result["status"],
                    "duration_ms": result.get("duration_ms", 0),
                    "output": result["output"],
                    "json_output": json_output,
                    "timestamp": datetime.now().isoformat()
                })
            
            elif action == "health":
                # 快速健康检查
                health = await aggregate_health()
                await websocket.send_json({
                    "type": "health",
                    "data": health.dict()
                })
            
            else:
                await websocket.send_json({
                    "type": "error",
                    "message": f"Unknown action: {action}"
                })
    
    except WebSocketDisconnect:
        logger.info(f"Debug WebSocket disconnected: {client_id}")
    except Exception as e:
        logger.error(f"Debug WebSocket error: {e}")
        try:
            await websocket.send_json({
                "type": "error",
                "message": str(e)
            })
        except:
            pass


@router.get("/system/info", dependencies=[Depends(verify_debug_auth)])
async def system_info():
    """
    获取系统信息
    
    Returns:
        dict: 系统信息
    """
    import platform
    import psutil
    
    return {
        "code": 0,
        "data": {
            "platform": platform.platform(),
            "python_version": platform.python_version(),
            "cpu_count": psutil.cpu_count(),
            "cpu_percent": psutil.cpu_percent(interval=1),
            "memory": {
                "total_gb": round(psutil.virtual_memory().total / (1024**3), 2),
                "available_gb": round(psutil.virtual_memory().available / (1024**3), 2),
                "percent": psutil.virtual_memory().percent
            },
            "disk": {
                "total_gb": round(psutil.disk_usage('/').total / (1024**3), 2),
                "free_gb": round(psutil.disk_usage('/').free / (1024**3), 2),
                "percent": psutil.disk_usage('/').percent
            },
            "uptime": int(time.time() - psutil.boot_time()),
            "timestamp": datetime.now().isoformat()
        }
    }
