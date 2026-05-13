"""
统一 API 响应格式工具模块

所有 API 端点应使用此模块的 success_response 和 error_response，
确保响应格式一致，便于前端统一处理。

响应格式:
{
    "code": 0,           # 0 表示成功，非 0 表示错误
    "message": "success", # 响应消息
    "data": {...},        # 响应数据
    "error": {            # 错误详情（成功时为 null）
        "details": {},    # 附加错误详情
        "trace_id": "abc123",  # 请求追踪ID
        "timestamp": "2024-01-01T00:00:00"  # ISO格式时间戳
    }
}
"""

import uuid
from datetime import datetime
from typing import Any, Optional, Dict


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


def generate_trace_id() -> str:
    """Generate unique trace ID for debugging (8 chars)."""
    return str(uuid.uuid4())[:8]


def success_response(
    data: Any,
    message: str = "success"
) -> dict:
    """
    Standardized success response format.
    
    Args:
        data: Response data
        message: Response message, defaults to "success"
    
    Returns:
        JSON response with consistent structure
    """
    return {
        "code": ErrorCode.SUCCESS,
        "message": message,
        "data": data,
        "error": None,
    }


def error_response(
    code_or_message,
    message: Optional[str] = None,
    details: Optional[Dict[str, Any]] = None,
    code: Optional[int] = None
) -> dict:
    """
    Standardized error response format.
    
    Supports two calling conventions:
    1. error_response(code, message, details) - standard form
    2. error_response(message, code=X) - shorthand form
    
    Args:
        code_or_message: Error code (int) or message (str)
        message: Error message (when first arg is code)
        details: Optional additional error details (e.g., validation errors)
        code: Error code (when using shorthand form)
    
    Returns:
        JSON response with consistent structure including trace_id
    """
    # Detect calling convention
    if isinstance(code_or_message, int):
        # Standard form: error_response(code, message, details)
        actual_code = code_or_message
        actual_message = message or "Error"
    else:
        # Shorthand form: error_response(message, code=X)
        actual_code = code if code is not None else ErrorCode.INTERNAL_ERROR
        actual_message = str(code_or_message)
    
    return {
        "code": actual_code,
        "message": actual_message,
        "data": None,
        "error": {
            "details": details or {},
            "trace_id": generate_trace_id(),
            "timestamp": datetime.now().isoformat(),
        }
    }



