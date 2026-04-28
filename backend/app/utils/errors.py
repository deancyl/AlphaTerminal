"""
统一错误码定义和错误处理工具

使用方式:
    from app.utils.errors import ErrorCode, error_response, success_response, APIException
    
    # 成功响应
    return success_response(data={"key": "value"})
    
    # 错误响应
    return error_response(ErrorCode.BAD_REQUEST, "参数错误")
    
    # 抛出异常
    raise APIException(ErrorCode.NOT_FOUND, "资源不存在")
"""
import time
import uuid
from typing import Optional, Dict, Any
from fastapi import HTTPException


class ErrorCode:
    """标准错误码枚举
    
    错误码规则:
    - 0: 成功
    - 1xx: 客户端错误 (参数、认证等)
    - 2xx: 服务端错误 (内部错误、数据库等)
    - 3xx: 第三方服务错误 (API、数据源等)
    - 4xx: 业务逻辑错误
    """
    
    # 成功
    SUCCESS = 0
    
    # 客户端错误 (1xx)
    BAD_REQUEST = 100           # 请求参数错误
    UNAUTHORIZED = 101            # 未授权
    FORBIDDEN = 102               # 禁止访问
    NOT_FOUND = 104               # 资源不存在
    METHOD_NOT_ALLOWED = 105      # 方法不允许
    VALIDATION_ERROR = 110        # 数据验证错误
    RATE_LIMITED = 120            # 请求频率限制
    
    # 服务端错误 (2xx)
    INTERNAL_ERROR = 200          # 内部服务器错误
    DATABASE_ERROR = 210          # 数据库错误
    CACHE_ERROR = 220             # 缓存错误
    CONFIG_ERROR = 230            # 配置错误
    
    # 第三方服务错误 (3xx)
    THIRD_PARTY_ERROR = 302       # 第三方服务通用错误
    TIMEOUT_ERROR = 310           # 请求超时
    API_ERROR = 320               # API调用错误
    DATA_SOURCE_ERROR = 330       # 数据源错误
    
    # 业务逻辑错误 (4xx)
    BUSINESS_ERROR = 400          # 业务通用错误
    INSUFFICIENT_DATA = 410       # 数据不足
    CALCULATION_ERROR = 420       # 计算错误
    STRATEGY_ERROR = 430          # 策略错误


class ErrorCodeMessage:
    """错误码对应的消息模板"""
    MESSAGES = {
        ErrorCode.SUCCESS: "success",
        ErrorCode.BAD_REQUEST: "请求参数错误",
        ErrorCode.UNAUTHORIZED: "未授权访问",
        ErrorCode.FORBIDDEN: "禁止访问",
        ErrorCode.NOT_FOUND: "资源不存在",
        ErrorCode.METHOD_NOT_ALLOWED: "请求方法不允许",
        ErrorCode.VALIDATION_ERROR: "数据验证失败",
        ErrorCode.RATE_LIMITED: "请求过于频繁，请稍后再试",
        ErrorCode.INTERNAL_ERROR: "服务器内部错误",
        ErrorCode.DATABASE_ERROR: "数据库操作失败",
        ErrorCode.CACHE_ERROR: "缓存操作失败",
        ErrorCode.CONFIG_ERROR: "配置错误",
        ErrorCode.THIRD_PARTY_ERROR: "第三方服务错误",
        ErrorCode.TIMEOUT_ERROR: "请求超时",
        ErrorCode.API_ERROR: "API调用失败",
        ErrorCode.DATA_SOURCE_ERROR: "数据源错误",
        ErrorCode.BUSINESS_ERROR: "业务处理错误",
        ErrorCode.INSUFFICIENT_DATA: "数据不足",
        ErrorCode.CALCULATION_ERROR: "计算错误",
        ErrorCode.STRATEGY_ERROR: "策略执行错误",
    }
    
    @classmethod
    def get_message(cls, code: int) -> str:
        """获取错误码对应的消息"""
        return cls.MESSAGES.get(code, "未知错误")


class APIException(Exception):
    """API异常类
    
    用于在业务逻辑中抛出异常，由全局异常处理器捕获并转换为标准响应
    
    Attributes:
        code: 错误码
        message: 错误消息
        data: 附加数据
        trace_id: 追踪ID
    """
    
    def __init__(
        self,
        code: int = ErrorCode.INTERNAL_ERROR,
        message: Optional[str] = None,
        data: Optional[Dict[str, Any]] = None,
        trace_id: Optional[str] = None
    ):
        self.code = code
        self.message = message or ErrorCodeMessage.get_message(code)
        self.data = data
        self.trace_id = trace_id or str(uuid.uuid4())[:8]
        super().__init__(self.message)
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "code": self.code,
            "message": self.message,
            "data": self.data,
            "trace_id": self.trace_id,
            "timestamp": int(time.time() * 1000)
        }


def success_response(
    data: Optional[Dict[str, Any]] = None,
    message: str = "success",
    trace_id: Optional[str] = None
) -> Dict[str, Any]:
    """创建标准成功响应
    
    Args:
        data: 响应数据
        message: 成功消息
        trace_id: 追踪ID
        
    Returns:
        标准响应格式字典
    """
    return {
        "code": ErrorCode.SUCCESS,
        "message": message,
        "data": data,
        "trace_id": trace_id or str(uuid.uuid4())[:8],
        "timestamp": int(time.time() * 1000)
    }


def error_response(
    code: int = ErrorCode.INTERNAL_ERROR,
    message: Optional[str] = None,
    data: Optional[Dict[str, Any]] = None,
    trace_id: Optional[str] = None
) -> Dict[str, Any]:
    """创建标准错误响应
    
    Args:
        code: 错误码
        message: 错误消息，默认使用错误码对应的消息
        data: 附加数据
        trace_id: 追踪ID
        
    Returns:
        标准响应格式字典
    """
    return {
        "code": code,
        "message": message or ErrorCodeMessage.get_message(code),
        "data": data,
        "trace_id": trace_id or str(uuid.uuid4())[:8],
        "timestamp": int(time.time() * 1000)
    }


def http_exception_handler(exc: HTTPException) -> Dict[str, Any]:
    """转换FastAPI HTTPException为标准响应
    
    Args:
        exc: FastAPI HTTPException
        
    Returns:
        标准错误响应
    """
    code_map = {
        400: ErrorCode.BAD_REQUEST,
        401: ErrorCode.UNAUTHORIZED,
        403: ErrorCode.FORBIDDEN,
        404: ErrorCode.NOT_FOUND,
        405: ErrorCode.METHOD_NOT_ALLOWED,
        422: ErrorCode.VALIDATION_ERROR,
        429: ErrorCode.RATE_LIMITED,
        500: ErrorCode.INTERNAL_ERROR,
    }
    
    code = code_map.get(exc.status_code, ErrorCode.INTERNAL_ERROR)
    return error_response(code, exc.detail)


class ValidationError(APIException):
    """数据验证错误"""
    def __init__(self, message: str = "数据验证失败", data: Optional[Dict[str, Any]] = None):
        super().__init__(ErrorCode.VALIDATION_ERROR, message, data)


class NotFoundError(APIException):
    """资源不存在错误"""
    def __init__(self, resource: str = "资源", data: Optional[Dict[str, Any]] = None):
        super().__init__(ErrorCode.NOT_FOUND, f"{resource}不存在", data)


class DatabaseError(APIException):
    """数据库错误"""
    def __init__(self, message: str = "数据库操作失败", data: Optional[Dict[str, Any]] = None):
        super().__init__(ErrorCode.DATABASE_ERROR, message, data)


class ThirdPartyError(APIException):
    """第三方服务错误"""
    def __init__(self, service: str = "第三方服务", message: str = "服务调用失败", data: Optional[Dict[str, Any]] = None):
        super().__init__(ErrorCode.THIRD_PARTY_ERROR, f"{service}: {message}", data)


class TimeoutError(APIException):
    """超时错误"""
    def __init__(self, service: str = "服务", data: Optional[Dict[str, Any]] = None):
        super().__init__(ErrorCode.TIMEOUT_ERROR, f"{service}请求超时", data)
