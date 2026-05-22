"""
Market Radar Error Codes

P2-10: Standardized error codes for API responses.
Provides consistent error handling across all market radar endpoints.
"""

from enum import Enum
from typing import Optional, Dict, Any


class MarketRadarErrorCode(str, Enum):
    """Standardized error codes for Market Radar API."""

    # Success
    SUCCESS = "SUCCESS"

    # Client errors (4xx)
    INVALID_PARAMETER = "INVALID_PARAMETER"
    INVALID_ANOMALY_TYPE = "INVALID_ANOMALY_TYPE"
    RATE_LIMIT_EXCEEDED = "RATE_LIMIT_EXCEEDED"

    # Server errors (5xx)
    INTERNAL_ERROR = "INTERNAL_ERROR"
    TIMEOUT = "TIMEOUT"
    DATA_SOURCE_UNAVAILABLE = "DATA_SOURCE_UNAVAILABLE"
    NETWORK_ERROR = "NETWORK_ERROR"
    CACHE_ERROR = "CACHE_ERROR"

    # Data errors
    NO_DATA = "NO_DATA"
    INCOMPLETE_DATA = "INCOMPLETE_DATA"


class MarketRadarError:
    """
    Standardized error response for Market Radar API.
    
    Usage:
        error = MarketRadarError(
            code=MarketRadarErrorCode.TIMEOUT,
            message="数据加载超时",
            detail="Request exceeded 15 second timeout"
        )
        return error.to_dict()
    """

    # User-friendly messages in Chinese
    USER_MESSAGES = {
        MarketRadarErrorCode.SUCCESS: "操作成功",
        MarketRadarErrorCode.INVALID_PARAMETER: "参数错误，请检查输入",
        MarketRadarErrorCode.INVALID_ANOMALY_TYPE: "无效的异常类型",
        MarketRadarErrorCode.RATE_LIMIT_EXCEEDED: "请求过于频繁，请稍后重试",
        MarketRadarErrorCode.INTERNAL_ERROR: "服务暂时不可用，请稍后重试",
        MarketRadarErrorCode.TIMEOUT: "数据加载超时，请稍后重试",
        MarketRadarErrorCode.DATA_SOURCE_UNAVAILABLE: "数据源暂时不可用，正在使用备用数据",
        MarketRadarErrorCode.NETWORK_ERROR: "网络连接异常，请检查网络设置",
        MarketRadarErrorCode.CACHE_ERROR: "缓存服务异常",
        MarketRadarErrorCode.NO_DATA: "暂无数据",
        MarketRadarErrorCode.INCOMPLETE_DATA: "数据不完整",
    }

    # HTTP status code mapping
    HTTP_STATUS = {
        MarketRadarErrorCode.SUCCESS: 200,
        MarketRadarErrorCode.INVALID_PARAMETER: 400,
        MarketRadarErrorCode.INVALID_ANOMALY_TYPE: 400,
        MarketRadarErrorCode.RATE_LIMIT_EXCEEDED: 429,
        MarketRadarErrorCode.INTERNAL_ERROR: 500,
        MarketRadarErrorCode.TIMEOUT: 504,
        MarketRadarErrorCode.DATA_SOURCE_UNAVAILABLE: 503,
        MarketRadarErrorCode.NETWORK_ERROR: 502,
        MarketRadarErrorCode.CACHE_ERROR: 500,
        MarketRadarErrorCode.NO_DATA: 200,  # Return empty data, not error
        MarketRadarErrorCode.INCOMPLETE_DATA: 200,  # Return partial data
    }

    def __init__(
        self,
        code: MarketRadarErrorCode,
        message: Optional[str] = None,
        detail: Optional[str] = None,
        retry_after: Optional[int] = None
    ):
        self.code = code
        self.message = message or self.USER_MESSAGES.get(code, "未知错误")
        self.detail = detail  # For logging only, not exposed to users
        self.retry_after = retry_after  # For rate limiting

    def to_dict(self) -> Dict[str, Any]:
        """Convert to API response dictionary."""
        result = {
            "error": {
                "code": self.code.value,
                "message": self.message,
            }
        }
        if self.retry_after:
            result["error"]["retry_after"] = self.retry_after
        return result

    @property
    def http_status(self) -> int:
        """Get HTTP status code for this error."""
        return self.HTTP_STATUS.get(self.code, 500)

    @classmethod
    def from_exception(cls, exc: Exception) -> "MarketRadarError":
        """
        Create error from exception.
        
        Maps technical exceptions to user-friendly error codes.
        """
        error_str = str(exc).lower()

        if "timeout" in error_str or "timed out" in error_str:
            return cls(MarketRadarErrorCode.TIMEOUT)
        if "connection" in error_str or "network" in error_str:
            return cls(MarketRadarErrorCode.NETWORK_ERROR)
        if "akshare" in error_str or "data source" in error_str:
            return cls(MarketRadarErrorCode.DATA_SOURCE_UNAVAILABLE)
        if "cache" in error_str:
            return cls(MarketRadarErrorCode.CACHE_ERROR)

        return cls(MarketRadarErrorCode.INTERNAL_ERROR)


def success_response(data: Any, **kwargs) -> Dict[str, Any]:
    """
    Create a success response.
    
    Args:
        data: Response data
        **kwargs: Additional fields to include
        
    Returns:
        Standardized success response dictionary
    """
    result = {
        "success": True,
        "data": data,
    }
    result.update(kwargs)
    return result


def error_response(
    code: MarketRadarErrorCode,
    message: Optional[str] = None,
    detail: Optional[str] = None
) -> Dict[str, Any]:
    """
    Create an error response.
    
    Args:
        code: Error code
        message: Optional custom message
        detail: Optional detail for logging
        
    Returns:
        Standardized error response dictionary
    """
    error = MarketRadarError(code, message, detail)
    return error.to_dict()
