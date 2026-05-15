"""
Error Sanitizer Utility

Sanitizes error messages before sending to frontend users.
- Redacts sensitive patterns (API keys, passwords, tokens, paths)
- Maps error types to user-friendly messages
- Preserves full error for backend logging

Security: This module is critical for preventing information disclosure.
"""
import re
import logging
from typing import Optional

logger = logging.getLogger(__name__)

# ═══════════════════════════════════════════════════════════════
# Sensitive Patterns - Regex patterns to redact
# ═══════════════════════════════════════════════════════════════

SENSITIVE_PATTERNS = [
    # API Keys and tokens
    r'sk-[a-zA-Z0-9]{20,}',                    # OpenAI-style keys
    r'sk-[a-zA-Z0-9_-]{48}',                   # OpenAI full keys
    r'api[_-]?key["\']?\s*[:=]\s*["\']?[a-zA-Z0-9_-]{10,}',  # api_key=xxx
    r'api[_-]?key["\']?\s*[:=]\s*["\']?sk-[a-zA-Z0-9_-]+',   # api_key: sk-xxx
    r'Bearer\s+[a-zA-Z0-9_-]{20,}',           # Bearer tokens
    r'token["\']?\s*[:=]\s*["\']?[a-zA-Z0-9_-]{10,}',        # token=xxx
    r'access_token["\']?\s*[:=]\s*["\']?[a-zA-Z0-9_-]{10,}', # access_token
    
    # Passwords and secrets
    r'password["\']?\s*[:=]\s*["\']?[^\s"\']{3,}',  # password=xxx
    r'secret["\']?\s*[:=]\s*["\']?[a-zA-Z0-9_-]{10,}',    # secret=xxx
    r'credential[s]?["\']?\s*[:=]\s*["\']?[a-zA-Z0-9_-]{10,}',
    
    # File paths (user info disclosure)
    r'/home/[a-zA-Z0-9_-]+',                   # Linux home paths
    r'/Users/[a-zA-Z0-9_-]+',                  # macOS user paths
    r'C:\\\\Users\\\\[a-zA-Z0-9_-]+',          # Windows user paths
    r'/var/www/[a-zA-Z0-9_-]+',                # Web server paths
    r'/etc/passwd',                            # Sensitive system files
    r'/etc/shadow',                            # Password files
    
    # IP addresses (internal network disclosure)
    r'192\.168\.\d{1,3}\.\d{1,3}',             # Private IPv4
    r'10\.\d{1,3}\.\d{1,3}\.\d{1,3}',          # Private IPv4
    r'172\.(1[6-9]|2[0-9]|3[0-1])\.\d{1,3}\.\d{1,3}',  # Private IPv4
    
    # Database connection strings
    r'postgres(?:ql)?://[^\s]+',               # PostgreSQL connection
    r'mysql://[^\s]+',                         # MySQL connection
    r'sqlite://[^\s]+',                        # SQLite connection
    r'mongodb://[^\s]+',                       # MongoDB connection
    
    # Email addresses
    r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}',
    
    # URLs with credentials
    r'https?://[^:]+:[^@]+@[^\s]+',            # URL with embedded credentials
]

# Compile patterns for performance
_COMPILED_PATTERNS = [re.compile(p, re.IGNORECASE) for p in SENSITIVE_PATTERNS]


# ═══════════════════════════════════════════════════════════════
# Error Type Mapping - User-friendly messages
# ═══════════════════════════════════════════════════════════════

ERROR_MAP = {
    # Network errors
    "ConnectionError": "网络连接失败，请检查网络设置",
    "ConnectError": "网络连接失败，请检查网络设置",
    "ConnectTimeout": "网络连接超时，请稍后重试",
    "TimeoutError": "请求超时，请稍后重试",
    "ReadTimeout": "读取数据超时，请稍后重试",
    "WriteTimeout": "写入数据超时，请稍后重试",
    
    # HTTP errors
    "HTTPStatusError": "服务暂时不可用，请稍后重试",
    "HTTPError": "服务暂时不可用，请稍后重试",
    
    # Rate limiting
    "RateLimitError": "请求过于频繁，请稍后重试",
    "RateLimitExceededError": "请求过于频繁，请稍后重试",
    "TooManyRequestsError": "请求过于频繁，请稍后重试",
    
    # Authentication errors
    "AuthenticationError": "API 认证失败，请检查配置",
    "UnauthorizedError": "API 认证失败，请检查配置",
    "PermissionError": "权限不足，无法执行此操作",
    "ForbiddenError": "访问被拒绝，请检查权限",
    
    # API errors
    "InvalidRequestError": "请求参数无效，请检查输入",
    "BadRequestError": "请求格式错误，请检查输入",
    "NotFoundError": "请求的资源不存在",
    "APIError": "服务暂时不可用，请稍后重试",
    
    # Server errors
    "InternalServerError": "服务器内部错误，请稍后重试",
    "ServiceUnavailableError": "服务暂时不可用，请稍后重试",
    "BadGatewayError": "网关错误，请稍后重试",
    "GatewayTimeoutError": "网关超时，请稍后重试",
    
    # Data errors
    "JSONDecodeError": "数据解析失败，请稍后重试",
    "ValueError": "数据格式错误，请检查输入",
    "KeyError": "数据字段缺失，请联系管理员",
    
    # Generic errors
    "Exception": "服务暂时不可用，请稍后重试",
    "RuntimeError": "运行时错误，请稍后重试",
}

# Provider-specific error prefixes for context
PROVIDER_CONTEXT = {
    "openai": "OpenAI",
    "deepseek": "DeepSeek",
    "qianwen": "通义千问",
    "minimax": "MiniMax",
    "siliconflow": "硅基流动",
    "opencode": "OpenCode",
    "opencode_go": "OpenCode Go",
    "opencode_zen": "OpenCode Zen",
    "kimi": "Kimi",
    "mock": "Mock",
}


def _redact_sensitive(msg: str) -> str:
    """Redact sensitive patterns from message."""
    for pattern in _COMPILED_PATTERNS:
        msg = pattern.sub('[REDACTED]', msg)
    return msg


def sanitize_error(
    error: Exception,
    context: str = "",
    provider: str = "",
    log_full_error: bool = True
) -> str:
    """
    Sanitize error message for frontend display.
    
    Args:
        error: The exception that occurred
        context: Additional context about the operation
        provider: LLM provider name (for context prefix)
        log_full_error: Whether to log the full error (default: True)
    
    Returns:
        Sanitized, user-friendly error message
    
    Example:
        >>> try:
        ...     raise ConnectionError("Failed to connect to api.openai.com with key sk-abc123")
        ... except Exception as e:
        ...     sanitize_error(e, provider="openai")
        'OpenAI API 调用失败: 网络连接失败，请检查网络设置'
    """
    error_type = type(error).__name__
    raw_message = str(error)
    lower_msg = raw_message.lower()
    
    if log_full_error:
        provider_name = PROVIDER_CONTEXT.get(provider, provider.upper() if provider else "API")
        logger.error(f"[{provider_name}] {error_type}: {raw_message}")
    
    user_message = None
    
    if "timeout" in lower_msg or "timed out" in lower_msg:
        user_message = "请求超时，请稍后重试"
    elif "connection" in lower_msg or "connect" in lower_msg:
        user_message = "网络连接失败，请检查网络设置"
    elif "unauthorized" in lower_msg or "401" in lower_msg or "403" in lower_msg:
        user_message = "API 认证失败，请检查配置"
    elif "rate limit" in lower_msg or "429" in lower_msg:
        user_message = "请求过于频繁，请稍后重试"
    elif "not found" in lower_msg or "404" in lower_msg:
        user_message = "请求的资源不存在"
    elif "invalid" in lower_msg or "400" in lower_msg:
        user_message = "请求参数无效，请检查输入"
    
    if not user_message:
        user_message = ERROR_MAP.get(error_type)
    
    if not user_message:
        user_message = _redact_sensitive(raw_message)
        if len(user_message) > 100:
            user_message = user_message[:100] + "..."
    
    # Build final message with context
    provider_name = PROVIDER_CONTEXT.get(provider, provider.upper() if provider else "")
    
    if provider_name:
        return f"{provider_name} API 调用失败: {user_message}"
    elif context:
        return f"{context}: {user_message}"
    else:
        return user_message


def sanitize_error_message(
    message: str,
    provider: str = "",
    log_full_message: bool = True
) -> str:
    """
    Sanitize a raw error message string (not an exception object).
    
    Args:
        message: Raw error message string
        provider: LLM provider name
        log_full_message: Whether to log the full message
    
    Returns:
        Sanitized message
    
    Example:
        >>> sanitize_error_message("HTTP 401 Unauthorized - Invalid API key sk-abc123")
        'HTTP 401 Unauthorized - Invalid API key [REDACTED]'
    """
    if log_full_message:
        provider_name = PROVIDER_CONTEXT.get(provider, provider.upper() if provider else "API")
        logger.error(f"[{provider_name}] {message}")
    
    return _redact_sensitive(message)


# ═══════════════════════════════════════════════════════════════
# Convenience functions for common use cases
# ═══════════════════════════════════════════════════════════════

def sanitize_openai_error(error: Exception) -> str:
    """Sanitize OpenAI API error."""
    return sanitize_error(error, provider="openai")


def sanitize_deepseek_error(error: Exception) -> str:
    """Sanitize DeepSeek API error."""
    return sanitize_error(error, provider="deepseek")


def sanitize_qianwen_error(error: Exception) -> str:
    """Sanitize Qianwen API error."""
    return sanitize_error(error, provider="qianwen")


def sanitize_minimax_error(error: Exception) -> str:
    """Sanitize MiniMax API error."""
    return sanitize_error(error, provider="minimax")


def sanitize_siliconflow_error(error: Exception) -> str:
    """Sanitize SiliconFlow API error."""
    return sanitize_error(error, provider="siliconflow")


def sanitize_opencode_error(error: Exception) -> str:
    """Sanitize OpenCode API error."""
    return sanitize_error(error, provider="opencode")


def sanitize_opencode_go_error(error: Exception) -> str:
    """Sanitize OpenCode Go API error."""
    return sanitize_error(error, provider="opencode_go")


def sanitize_opencode_zen_error(error: Exception) -> str:
    """Sanitize OpenCode Zen API error."""
    return sanitize_error(error, provider="opencode_zen")


def sanitize_kimi_error(error: Exception) -> str:
    """Sanitize Kimi API error."""
    return sanitize_error(error, provider="kimi")
