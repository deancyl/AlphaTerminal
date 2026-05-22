"""
Error Handling Decorator

v0.6.64: 统一异常处理装饰器
- 自动捕获异常
- 调用 error_logger.log_error()
- 调用 error_sanitizer 清洗错误消息
- 持久化到 error_history 表
- 返回标准错误响应
"""

import functools
import traceback
import logging
from typing import Optional, Callable, Any
from fastapi import HTTPException, Request

from app.utils.errors import error_response, ErrorCode
from app.utils.error_sanitizer import sanitize_error
from app.services.error_logger import log_error
from app.db.error_history_db import log_error_to_db

logger = logging.getLogger(__name__)


def handle_errors(
    module: str,
    function: Optional[str] = None,
    log_to_db: bool = True,
    reraise: bool = False,
):
    """
    统一异常处理装饰器

    Args:
        module: 模块名（如 'stocks', 'portfolio'）
        function: 函数名（默认使用被装饰函数的 __name__）
        log_to_db: 是否记录到数据库
        reraise: 是否重新抛出异常（用于测试）

    Usage:
        @router.get("/quote/{symbol}")
        @handle_errors(module="stocks")
        async def get_quote(symbol: str):
            data = await fetch_quote(symbol)
            return success_response(data)
    """

    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs) -> Any:
            func_name = function or func.__name__

            request_path = None
            request_method = None

            for arg in args:
                if isinstance(arg, Request):
                    request_path = arg.url.path
                    request_method = arg.method
                    break

            try:
                return await func(*args, **kwargs)
            except HTTPException:
                # Let FastAPI HTTPException pass through (for validation errors)
                raise
            except Exception as e:
                error_type = type(e).__name__
                error_message = str(e)
                sanitized_message = sanitize_error(e, log_full_error=True)
                trace_id = str(getattr(e, "trace_id", None) or "")
                tb_str = traceback.format_exc()

                log_error(
                    exception=e,
                    module=module,
                    function=func_name,
                    context={"path": request_path, "method": request_method},
                )

                if log_to_db:
                    try:
                        log_error_to_db(
                            module=module,
                            function=func_name,
                            error_type=error_type,
                            error_message=error_message,
                            sanitized_message=sanitized_message,
                            traceback_str=tb_str,
                            trace_id=trace_id,
                            request_path=request_path,
                            request_method=request_method,
                        )
                    except Exception as db_error:
                        logger.warning(
                            f"Failed to log error to DB: {db_error}", exc_info=True
                        )

                if reraise:
                    raise

                return error_response(
                    ErrorCode.INTERNAL_ERROR,
                    sanitized_message,
                    {"trace_id": trace_id} if trace_id else None,
                )

        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs) -> Any:
            func_name = function or func.__name__

            request_path = None
            request_method = None

            for arg in args:
                if isinstance(arg, Request):
                    request_path = arg.url.path
                    request_method = arg.method
                    break

            try:
                return func(*args, **kwargs)
            except HTTPException:
                # Let FastAPI HTTPException pass through (for validation errors)
                raise
            except Exception as e:
                error_type = type(e).__name__
                error_message = str(e)
                sanitized_message = sanitize_error(e, log_full_error=True)
                trace_id = str(getattr(e, "trace_id", None) or "")
                tb_str = traceback.format_exc()

                log_error(
                    exception=e,
                    module=module,
                    function=func_name,
                    context={"path": request_path, "method": request_method},
                )

                if log_to_db:
                    try:
                        log_error_to_db(
                            module=module,
                            function=func_name,
                            error_type=error_type,
                            error_message=error_message,
                            sanitized_message=sanitized_message,
                            traceback_str=tb_str,
                            trace_id=trace_id,
                            request_path=request_path,
                            request_method=request_method,
                        )
                    except Exception as db_error:
                        logger.warning(
                            f"Failed to log error to DB: {db_error}", exc_info=True
                        )

                if reraise:
                    raise

                return error_response(
                    code=ErrorCode.INTERNAL_ERROR,
                    message=sanitized_message,
                    details={"trace_id": trace_id} if trace_id else None,
                )

        import asyncio

        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper

    return decorator
