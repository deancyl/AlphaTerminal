"""
Backend utility modules

v0.6.64: Updated imports to use errors.py instead of deprecated response.py
"""

from .errors import (
    ErrorCode,
    ErrorCodeMessage,
    success_response,
    error_response,
    APIException,
    ValidationError,
    NotFoundError,
    DatabaseError,
    ThirdPartyError,
    TimeoutError,
)

from .response import generate_trace_id

from .error_sanitizer import (
    sanitize_error,
    sanitize_error_message,
)

from .exception_handlers import setup_exception_handlers

__all__ = [
    # Error codes and responses
    'ErrorCode',
    'ErrorCodeMessage',
    'success_response',
    'error_response',
    'generate_trace_id',
    
    # Exception classes
    'APIException',
    'ValidationError',
    'NotFoundError',
    'DatabaseError',
    'ThirdPartyError',
    'TimeoutError',
    
    # Error sanitization
    'sanitize_error',
    'sanitize_error_message',
    
    # Exception handlers
    'setup_exception_handlers',
]
