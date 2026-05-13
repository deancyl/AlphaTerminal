"""
全局异常处理中间件

使用方式:
    from fastapi import FastAPI
    from app.utils.exception_handlers import setup_exception_handlers
    
    app = FastAPI()
    setup_exception_handlers(app)
"""
import logging
import traceback
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.utils.errors import (
    APIException,
    error_response,
    http_exception_handler,
    ErrorCode
)

logger = logging.getLogger(__name__)


# API错误码到HTTP状态码的映射
_HTTP_STATUS_MAP = {
    # 客户端错误 -> 4xx
    100: 400, 101: 401, 102: 403, 104: 404, 105: 405,
    110: 422, 120: 429,
    # 服务端错误 -> 5xx
    200: 500, 210: 500, 220: 500, 230: 500,
    # 第三方错误 -> 502/504
    302: 502, 310: 504, 320: 502, 330: 502,
    # 业务错误 -> 400
    400: 400, 410: 400, 420: 400, 430: 400,
}


async def api_exception_handler(request: Request, exc: APIException) -> JSONResponse:
    """处理自定义API异常"""
    logger.error(
        f"API Exception: {exc.message}",
        extra={
            "trace_id": exc.trace_id,
            "code": exc.code,
            "path": request.url.path,
            "method": request.method,
        }
    )
    
    # 使用映射表获取正确的HTTP状态码，避免AttributeError
    http_status = _HTTP_STATUS_MAP.get(exc.code, 500)
    
    return JSONResponse(
        status_code=http_status,
        content=exc.to_dict()
    )


async def http_exception_handler_wrapper(request: Request, exc: HTTPException) -> JSONResponse:
    """处理FastAPI HTTP异常"""
    logger.warning(
        f"HTTP Exception {exc.status_code}: {exc.detail}",
        extra={
            "status_code": exc.status_code,
            "path": request.url.path,
            "method": request.method,
        }
    )
    
    return JSONResponse(
        status_code=exc.status_code,
        content=http_exception_handler(exc)
    )


async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    """处理请求验证异常"""
    errors = []
    for error in exc.errors():
        errors.append({
            "field": error.get("loc", ["unknown"])[-1],
            "message": error.get("msg", "验证失败"),
            "type": error.get("type", "validation_error"),
        })
    
    logger.warning(
        f"Validation Error: {len(errors)} field(s) failed validation",
        extra={
            "path": request.url.path,
            "method": request.method,
            "errors": errors,
        }
    )
    
    return JSONResponse(
        status_code=422,
        content=error_response(
            code=ErrorCode.VALIDATION_ERROR,
            message="请求参数验证失败",
            details={"errors": errors}
        )
    )


async def general_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """处理通用异常"""
    trace_id = str(exc.trace_id) if hasattr(exc, 'trace_id') else None
    
    logger.error(
        f"Unhandled Exception: {str(exc)}",
        extra={
            "trace_id": trace_id,
            "path": request.url.path,
            "method": request.method,
            "traceback": traceback.format_exc(),
        }
    )
    
    return JSONResponse(
        status_code=500,
        content=error_response(
            code=ErrorCode.INTERNAL_ERROR,
            message="服务器内部错误",
            details={"detail": "请联系管理员"} if not __debug__ else {"error": str(exc)}
        )
    )


def setup_exception_handlers(app: FastAPI) -> None:
    """配置全局异常处理器
    
    Args:
        app: FastAPI应用实例
    """
    # 自定义API异常
    app.add_exception_handler(APIException, api_exception_handler)
    
    # FastAPI HTTP异常
    app.add_exception_handler(HTTPException, http_exception_handler_wrapper)
    app.add_exception_handler(StarletteHTTPException, http_exception_handler_wrapper)
    
    # 请求验证异常
    app.add_exception_handler(RequestValidationError, validation_exception_handler)
    
    # 通用异常（最后注册，作为兜底）
    app.add_exception_handler(Exception, general_exception_handler)
    
    logger.info("Exception handlers configured")
