"""
Tests for backend/app/config/settings.py

Tests cover:
- Environment variable loading
- Default values
- Validation logic
- Helper methods
"""
import os
import sys
import pytest
from unittest.mock import patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))))
from app.config.settings import Settings, get_settings, reload_settings


class TestSettingsDefaults:
    """Test default values when no environment variables are set."""
    
    def test_default_http_proxy_is_empty(self):
        settings = Settings()
        assert settings.HTTP_PROXY == ""
    
    def test_default_alpha_vantage_key_is_empty(self):
        settings = Settings()
        assert settings.ALPHA_VANTAGE_API_KEY == ""
    
    def test_default_admin_api_key_is_empty(self):
        settings = Settings()
        assert settings.ADMIN_API_KEY == ""
    
    def test_default_env_is_development(self):
        settings = Settings()
        assert settings.ENV == "development"
    
    def test_default_debug_mode_is_false(self):
        settings = Settings()
        assert settings.DEBUG_MODE is False
    
    def test_default_allowed_origins_is_wildcard(self):
        settings = Settings()
        assert settings.ALLOWED_ORIGINS == "*"
    
    def test_default_log_level_is_info(self):
        settings = Settings()
        assert settings.LOG_LEVEL == "info"
    
    def test_default_backend_port_is_8002(self):
        settings = Settings()
        assert settings.BACKEND_PORT == 8002
    
    def test_default_frontend_port_is_60100(self):
        settings = Settings()
        assert settings.FRONTEND_PORT == 60100
    
    def test_default_agent_db_debug_is_false(self):
        settings = Settings()
        assert settings.AGENT_DB_DEBUG is False
    
    def test_default_agent_auth_debug_is_false(self):
        settings = Settings()
        assert settings.AGENT_AUTH_DEBUG is False


class TestSettingsEnvironmentLoading:
    """Test loading settings from environment variables."""
    
    def test_load_http_proxy_from_env(self):
        with patch.dict(os.environ, {"HTTP_PROXY": "http://192.168.1.50:7897"}, clear=False):
            settings = Settings()
            assert settings.HTTP_PROXY == "http://192.168.1.50:7897"
    
    def test_load_alpha_vantage_key_from_env(self):
        with patch.dict(os.environ, {"ALPHA_VANTAGE_API_KEY": "test_key_123"}, clear=False):
            settings = Settings()
            assert settings.ALPHA_VANTAGE_API_KEY == "test_key_123"
    
    def test_load_admin_api_key_from_env(self):
        with patch.dict(os.environ, {"ADMIN_API_KEY": "admin_secret_key"}, clear=False):
            settings = Settings()
            assert settings.ADMIN_API_KEY == "admin_secret_key"
    
    def test_load_env_from_env(self):
        with patch.dict(os.environ, {"ENV": "production"}, clear=False):
            settings = Settings()
            assert settings.ENV == "production"
    
    def test_load_debug_mode_true_from_env(self):
        with patch.dict(os.environ, {"DEBUG_MODE": "true"}, clear=False):
            settings = Settings()
            assert settings.DEBUG_MODE is True
    
    def test_load_debug_mode_false_from_env(self):
        with patch.dict(os.environ, {"DEBUG_MODE": "false"}, clear=False):
            settings = Settings()
            assert settings.DEBUG_MODE is False
    
    def test_load_allowed_origins_from_env(self):
        with patch.dict(os.environ, {"ALLOWED_ORIGINS": "http://localhost:3000,http://example.com"}, clear=False):
            settings = Settings()
            assert settings.ALLOWED_ORIGINS == "http://localhost:3000,http://example.com"


class TestSettingsValidation:
    """Test validation logic in settings."""
    
    def test_validate_bool_from_str_true(self):
        settings = Settings()
        result = settings.validate_bool_from_str("true")
        assert result is True
    
    def test_validate_bool_from_str_false(self):
        settings = Settings()
        result = settings.validate_bool_from_str("false")
        assert result is False
    
    def test_validate_bool_from_str_case_insensitive(self):
        settings = Settings()
        assert settings.validate_bool_from_str("TRUE") is True
        assert settings.validate_bool_from_str("FALSE") is False
        assert settings.validate_bool_from_str("True") is True
        assert settings.validate_bool_from_str("False") is False
    
    def test_validate_bool_from_bool(self):
        settings = Settings()
        assert settings.validate_bool_from_str(True) is True
        assert settings.validate_bool_from_str(False) is False
    
    def test_validate_origins_empty_string(self):
        settings = Settings()
        result = settings.validate_origins("")
        assert result == "*"
    
    def test_validate_origins_non_empty(self):
        settings = Settings()
        result = settings.validate_origins("http://localhost:3000")
        assert result == "http://localhost:3000"


class TestSettingsHelperMethods:
    """Test helper methods in Settings class."""
    
    def test_get_allowed_origins_list_wildcard(self):
        settings = Settings(ALLOWED_ORIGINS="*")
        result = settings.get_allowed_origins_list()
        assert result == ["*"]
    
    def test_get_allowed_origins_list_multiple(self):
        settings = Settings(ALLOWED_ORIGINS="http://localhost:3000, http://example.com, http://test.com")
        result = settings.get_allowed_origins_list()
        assert result == ["http://localhost:3000", "http://example.com", "http://test.com"]
    
    def test_get_allowed_origins_list_empty_parts(self):
        settings = Settings(ALLOWED_ORIGINS="http://localhost:3000,,http://example.com,")
        result = settings.get_allowed_origins_list()
        assert result == ["http://localhost:3000", "http://example.com"]
    
    def test_is_production_true(self):
        settings = Settings(ENV="production")
        assert settings.is_production() is True
    
    def test_is_production_false(self):
        settings = Settings(ENV="development")
        assert settings.is_production() is False
    
    def test_is_production_case_insensitive(self):
        settings = Settings(ENV="PRODUCTION")
        assert settings.is_production() is True
    
    def test_is_development_true(self):
        settings = Settings(ENV="development")
        assert settings.is_development() is True
    
    def test_is_development_false(self):
        settings = Settings(ENV="production")
        assert settings.is_development() is False
    
    def test_get_proxy_url_from_http_proxy(self):
        settings = Settings(HTTP_PROXY="http://192.168.1.50:7897", HTTPS_PROXY="")
        assert settings.get_proxy_url() == "http://192.168.1.50:7897"
    
    def test_get_proxy_url_from_https_proxy(self):
        settings = Settings(HTTP_PROXY="", HTTPS_PROXY="http://192.168.1.50:7897")
        assert settings.get_proxy_url() == "http://192.168.1.50:7897"
    
    def test_get_proxy_url_none_when_empty(self):
        settings = Settings(HTTP_PROXY="", HTTPS_PROXY="")
        assert settings.get_proxy_url() is None
    
    def test_has_alpha_vantage_key_true(self):
        settings = Settings(ALPHA_VANTAGE_API_KEY="test_key_123")
        assert settings.has_alpha_vantage_key() is True
    
    def test_has_alpha_vantage_key_false_empty(self):
        settings = Settings(ALPHA_VANTAGE_API_KEY="")
        assert settings.has_alpha_vantage_key() is False
    
    def test_has_alpha_vantage_key_false_placeholder(self):
        settings = Settings(ALPHA_VANTAGE_API_KEY="your_api_key_here")
        assert settings.has_alpha_vantage_key() is False


class TestSettingsSingleton:
    """Test singleton pattern for settings."""
    
    def test_get_settings_returns_settings_instance(self):
        settings = get_settings()
        assert isinstance(settings, Settings)
    
    def test_get_settings_returns_same_instance(self):
        settings1 = get_settings()
        settings2 = get_settings()
        assert settings1 is settings2
    
    def test_reload_settings_creates_new_instance(self):
        settings1 = get_settings()
        settings2 = reload_settings()
        # After reload, should be a new instance
        assert settings1 is not settings2
        # But subsequent calls return the new instance
        settings3 = get_settings()
        assert settings2 is settings3


class TestSettingsSecurityDefaults:
    """Test security-critical default values."""
    
    def test_debug_mode_defaults_to_false(self):
        settings = Settings()
        assert settings.DEBUG_MODE is False, "DEBUG_MODE must default to False for security"
    
    def test_agent_db_debug_defaults_to_false(self):
        settings = Settings()
        assert settings.AGENT_DB_DEBUG is False, "AGENT_DB_DEBUG must default to False for security"
    
    def test_agent_auth_debug_defaults_to_false(self):
        settings = Settings()
        assert settings.AGENT_AUTH_DEBUG is False, "AGENT_AUTH_DEBUG must default to False for security"
    
    def test_api_keys_default_to_empty(self):
        settings = Settings()
        assert settings.ALPHA_VANTAGE_API_KEY == "", "ALPHA_VANTAGE_API_KEY must default to empty string"
        assert settings.ADMIN_API_KEY == "", "ADMIN_API_KEY must default to empty string"
    
    def test_no_hardcoded_api_keys(self):
        settings = Settings()
        # Ensure no hardcoded API keys in defaults
        assert settings.ALPHA_VANTAGE_API_KEY not in ["4M3YTMFEMBOPM1W2", "demo", "test"]
        assert settings.ADMIN_API_KEY not in ["admin", "secret", "password"]
