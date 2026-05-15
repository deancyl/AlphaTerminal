"""
Tests for error_sanitizer.py

Verifies:
- Sensitive patterns are redacted
- Error types map to user-friendly messages
- Provider context is added correctly
- Full errors are logged (not exposed to users)
"""
import pytest
import logging
from app.utils.error_sanitizer import (
    sanitize_error,
    sanitize_error_message,
    _redact_sensitive,
    SENSITIVE_PATTERNS,
    ERROR_MAP,
    PROVIDER_CONTEXT,
)


class TestRedactSensitive:
    """Tests for _redact_sensitive function."""

    def test_redact_openai_key(self):
        msg = "HTTP 401 Unauthorized - Invalid API key sk-1234567890abcdefghijklmnop"
        result = _redact_sensitive(msg)
        assert "sk-1234567890" not in result
        assert "[REDACTED]" in result

    def test_redact_bearer_token(self):
        msg = "Bearer abcdefghij1234567890abcdefghij failed"
        result = _redact_sensitive(msg)
        assert "Bearer abcdefghij1234567890abcdefghij" not in result
        assert "[REDACTED]" in result

    def test_redact_password(self):
        msg = 'password="mysecretpassword123" is invalid'
        result = _redact_sensitive(msg)
        assert "mysecretpassword123" not in result
        assert "[REDACTED]" in result

    def test_redact_file_paths(self):
        msg = "File not found: /home/john/project/config.json"
        result = _redact_sensitive(msg)
        assert "/home/john" not in result
        assert "[REDACTED]" in result

    def test_redact_macos_path(self):
        msg = "Error in /Users/alice/.config/app/settings.json"
        result = _redact_sensitive(msg)
        assert "/Users/alice" not in result
        assert "[REDACTED]" in result

    def test_redact_private_ip(self):
        msg = "Connection failed to 192.168.1.50:8080"
        result = _redact_sensitive(msg)
        assert "192.168.1.50" not in result
        assert "[REDACTED]" in result

    def test_redact_email(self):
        msg = "User john.doe@example.com not found"
        result = _redact_sensitive(msg)
        assert "john.doe@example.com" not in result
        assert "[REDACTED]" in result

    def test_redact_url_with_credentials(self):
        msg = "postgres://user:password123@localhost:5432/db"
        result = _redact_sensitive(msg)
        assert "user:password123" not in result
        assert "[REDACTED]" in result

    def test_no_redaction_for_safe_message(self):
        msg = "Connection timeout after 30 seconds"
        result = _redact_sensitive(msg)
        assert result == msg


class TestSanitizeError:
    """Tests for sanitize_error function."""

    def test_connection_error_mapping(self):
        e = ConnectionError("Failed to connect to api.openai.com")
        result = sanitize_error(e, provider="openai", log_full_error=False)
        assert result == "OpenAI API 调用失败: 网络连接失败，请检查网络设置"

    def test_timeout_error_mapping(self):
        e = TimeoutError("Request timed out after 60s")
        result = sanitize_error(e, provider="deepseek", log_full_error=False)
        assert result == "DeepSeek API 调用失败: 请求超时，请稍后重试"

    def test_json_decode_error_mapping(self):
        import json
        e = json.JSONDecodeError("Expecting value", "", 0)
        result = sanitize_error(e, provider="qianwen", log_full_error=False)
        assert result == "通义千问 API 调用失败: 数据解析失败，请稍后重试"

    def test_unknown_error_fallback(self):
        e = RuntimeError("Unknown internal error occurred")
        result = sanitize_error(e, provider="minimax", log_full_error=False)
        assert "MiniMax API 调用失败" in result

    def test_no_provider_context(self):
        e = ConnectionError("Connection failed")
        result = sanitize_error(e, log_full_error=False)
        assert result == "网络连接失败，请检查网络设置"

    def test_custom_context(self):
        e = ValueError("Invalid input")
        result = sanitize_error(e, context="数据处理", log_full_error=False)
        assert "数据处理" in result

    def test_redacts_sensitive_in_fallback(self):
        e = Exception("Error with key sk-1234567890abcdefghijklmnopqrst")
        result = sanitize_error(e, provider="openai", log_full_error=False)
        assert "sk-1234567890" not in result

    def test_truncates_long_messages(self):
        long_msg = "A" * 200
        e = Exception(long_msg)
        result = sanitize_error(e, log_full_error=False)
        assert len(result) <= 103  # 100 + "..."

    def test_pattern_detection_timeout(self):
        e = Exception("Request timed out after 30 seconds")
        result = sanitize_error(e, provider="openai", log_full_error=False)
        assert "请求超时" in result

    def test_pattern_detection_unauthorized(self):
        e = Exception("HTTP 401 Unauthorized - Invalid credentials")
        result = sanitize_error(e, provider="deepseek", log_full_error=False)
        assert "认证失败" in result

    def test_pattern_detection_rate_limit(self):
        e = Exception("Rate limit exceeded: 429 Too Many Requests")
        result = sanitize_error(e, provider="qianwen", log_full_error=False)
        assert "请求过于频繁" in result

    def test_pattern_detection_connection(self):
        e = Exception("Failed to establish connection to server")
        result = sanitize_error(e, provider="minimax", log_full_error=False)
        assert "网络连接失败" in result


class TestSanitizeErrorMessage:
    """Tests for sanitize_error_message function."""

    def test_redacts_api_key(self):
        msg = "Invalid API key sk-1234567890abcdefghijklmnop"
        result = sanitize_error_message(msg, log_full_message=False)
        assert "sk-1234567890" not in result
        assert "[REDACTED]" in result

    def test_redacts_password(self):
        msg = 'password="secret123" is incorrect'
        result = sanitize_error_message(msg, log_full_message=False)
        assert "secret123" not in result
        assert "[REDACTED]" in result

    def test_no_redaction_for_safe_message(self):
        msg = "Service temporarily unavailable"
        result = sanitize_error_message(msg, log_full_message=False)
        assert result == msg


class TestProviderContext:
    """Tests for provider context mapping."""

    def test_all_providers_have_context(self):
        providers = [
            "openai", "deepseek", "qianwen", "minimax",
            "siliconflow", "opencode", "opencode_go", "opencode_zen", "kimi"
        ]
        for provider in providers:
            assert provider in PROVIDER_CONTEXT
            assert PROVIDER_CONTEXT[provider] != ""

    def test_provider_context_names(self):
        assert PROVIDER_CONTEXT["openai"] == "OpenAI"
        assert PROVIDER_CONTEXT["deepseek"] == "DeepSeek"
        assert PROVIDER_CONTEXT["qianwen"] == "通义千问"
        assert PROVIDER_CONTEXT["siliconflow"] == "硅基流动"


class TestErrorMap:
    """Tests for error type mapping."""

    def test_connection_error_in_map(self):
        assert "ConnectionError" in ERROR_MAP
        assert ERROR_MAP["ConnectionError"] == "网络连接失败，请检查网络设置"

    def test_timeout_error_in_map(self):
        assert "TimeoutError" in ERROR_MAP
        assert ERROR_MAP["TimeoutError"] == "请求超时，请稍后重试"

    def test_rate_limit_error_in_map(self):
        assert "RateLimitError" in ERROR_MAP
        assert ERROR_MAP["RateLimitError"] == "请求过于频繁，请稍后重试"

    def test_authentication_error_in_map(self):
        assert "AuthenticationError" in ERROR_MAP
        assert ERROR_MAP["AuthenticationError"] == "API 认证失败，请检查配置"


class TestIntegration:
    """Integration tests matching success criteria."""

    def test_api_key_redacted(self):
        e = Exception("HTTP 401 Unauthorized - Invalid API key sk-1234567890")
        result = sanitize_error(e, provider="openai", log_full_error=False)
        assert "sk-1234567890" not in result

    def test_connection_error_user_friendly(self):
        e = ConnectionError("Failed to connect")
        result = sanitize_error(e, provider="deepseek", log_full_error=False)
        assert result == "DeepSeek API 调用失败: 网络连接失败，请检查网络设置"

    def test_full_error_logged(self, caplog):
        with caplog.at_level(logging.ERROR):
            e = Exception("Full error with sensitive key sk-1234567890")
            result = sanitize_error(e, provider="openai", log_full_error=True)
            
            assert any("sk-1234567890" in record.message for record in caplog.records)
            assert "sk-1234567890" not in result

    def test_multiple_sensitive_patterns(self):
        e = Exception(
            "Error: api_key=sk-abc123, password=secret123, "
            "user at /home/john, ip 192.168.1.50"
        )
        result = sanitize_error(e, log_full_error=False)
        assert "sk-abc123" not in result
        assert "secret123" not in result
        assert "/home/john" not in result
        assert "192.168.1.50" not in result
