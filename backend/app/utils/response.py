"""
统一 API 响应格式工具模块

所有 API 端点应使用此模块的 success_response 和 error_response，
确保响应格式一致，便于前端统一处理。

响应格式:
{
    "code": 0,           # 0 表示成功，非 0 表示错误
    "message": "success", # 响应消息
    "data": {...},        # 响应数据
    "timestamp": 1234567890,  # 时间戳（毫秒）
    "trace_id": "abc123"  # 请求追踪ID（可选）
}
"""

import time
import uuid
from typing import Any, Optional


class ErrorCode:
    """统一错误码定义"""
    SUCCESS = 0
    BAD_REQUEST = 100
    UNAUTHORIZED = 101
    FORBIDDEN = 102
    NOT_FOUND = 104
    VALIDATION_ERROR = 110
    INTERNAL_ERROR = 200
    THIRD_PARTY_ERROR = 302
    TIMEOUT_ERROR = 310
    CALCULATION_ERROR = 320


def success_response(
    data: Any,
    message: str = "success",
    trace_id: Optional[str] = None
) -> dict:
    """
    创建成功响应
    
    Args:
        data: 响应数据
        message: 响应消息，默认 "success"
        trace_id: 请求追踪ID，可选
    
    Returns:
        标准格式的成功响应字典
    
    Example:
        >>> success_response({"user": "Alice"})
        {"code": 0, "message": "success", "data": {"user": "Alice"}, "timestamp": 1234567890}
    """
    response = {
        "code": ErrorCode.SUCCESS,
        "message": message,
        "data": data,
        "timestamp": int(time.time() * 1000)
    }
    
    if trace_id:
        response["trace_id"] = trace_id
    
    return response


def error_response(
    code: int,
    message: str,
    data: Optional[Any] = None,
    trace_id: Optional[str] = None
) -> dict:
    """
    创建错误响应
    
    Args:
        code: 错误码，使用 ErrorCode 常量
        message: 错误消息
        data: 附加错误数据，可选
        trace_id: 请求追踪ID，可选
    
    Returns:
        标准格式的错误响应字典
    
    Example:
        >>> error_response(ErrorCode.NOT_FOUND, "用户不存在")
        {"code": 104, "message": "用户不存在", "data": None, "timestamp": 1234567890}
    """
    response = {
        "code": code,
        "message": message,
        "data": data,
        "timestamp": int(time.time() * 1000)
    }
    
    if trace_id:
        response["trace_id"] = trace_id
    
    return response


def generate_trace_id() -> str:
    """
    生成请求追踪ID
    
    Returns:
        UUID 格式的追踪ID
    
    Example:
        >>> generate_trace_id()
        "550e8400-e29b-41d4-a716-446655440000"
    """
    return str(uuid.uuid4())
