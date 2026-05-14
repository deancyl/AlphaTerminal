"""
Centralized Application Settings using Pydantic BaseSettings.

All configuration values are loaded from environment variables with sensible defaults.
Sensitive values (API keys, secrets) should NEVER be hardcoded.

Environment Variables:
    HTTP_PROXY: HTTP proxy URL (e.g., http://192.168.1.50:7897)
    ALPHA_VANTAGE_API_KEY: Alpha Vantage API key for US/HK stock data
    ADMIN_API_KEY: Admin API key for protected endpoints
    ENV: Environment name (development, staging, production)
    DEBUG_MODE: Enable debug logging (default: False for security)
    ALLOWED_ORIGINS: CORS allowed origins (comma-separated)
    DATABASE_PATH: Path to SQLite database file
    LOG_LEVEL: Logging level (debug, info, warning, error)
"""
from typing import List, Optional
from pydantic_settings import BaseSettings
from pydantic import field_validator


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""
    
    # Proxy Configuration
    HTTP_PROXY: str = ""
    HTTPS_PROXY: str = ""
    
    # API Keys (NEVER hardcode defaults for sensitive values)
    ALPHA_VANTAGE_API_KEY: str = ""
    ADMIN_API_KEY: str = ""
    
    # Environment
    ENV: str = "development"
    
    # Debug Mode - DEFAULT TO FALSE for security
    DEBUG_MODE: bool = False
    
    # CORS
    ALLOWED_ORIGINS: str = "*"
    
    # Database
    DATABASE_PATH: str = ""
    
    # Logging
    LOG_LEVEL: str = "info"
    
    # Backend Server
    BACKEND_HOST: str = "0.0.0.0"
    BACKEND_PORT: int = 8002
    
    # Frontend Server
    FRONTEND_HOST: str = "0.0.0.0"
    FRONTEND_PORT: int = 60100
    
    # Agent Debug Flags - DEFAULT TO FALSE
    AGENT_DB_DEBUG: bool = False
    AGENT_AUTH_DEBUG: bool = False
    
    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "case_sensitive": True,
        "extra": "ignore",
    }
    
    @field_validator("DEBUG_MODE", "AGENT_DB_DEBUG", "AGENT_AUTH_DEBUG", mode="before")
    @classmethod
    def validate_bool_from_str(cls, v):
        """Convert string 'true'/'false' to boolean."""
        if isinstance(v, str):
            return v.lower() == "true"
        return v
    
    @field_validator("ALLOWED_ORIGINS", mode="before")
    @classmethod
    def validate_origins(cls, v):
        """Handle empty string as wildcard."""
        if not v:
            return "*"
        return v
    
    def get_allowed_origins_list(self) -> List[str]:
        """Parse ALLOWED_ORIGINS into a list."""
        if self.ALLOWED_ORIGINS == "*":
            return ["*"]
        return [origin.strip() for origin in self.ALLOWED_ORIGINS.split(",") if origin.strip()]
    
    def is_production(self) -> bool:
        """Check if running in production environment."""
        return self.ENV.lower() == "production"
    
    def is_development(self) -> bool:
        """Check if running in development environment."""
        return self.ENV.lower() == "development"
    
    def get_proxy_url(self) -> Optional[str]:
        """Get proxy URL (HTTP_PROXY or HTTPS_PROXY)."""
        return self.HTTP_PROXY or self.HTTPS_PROXY or None
    
    def has_alpha_vantage_key(self) -> bool:
        """Check if Alpha Vantage API key is configured."""
        return bool(self.ALPHA_VANTAGE_API_KEY and self.ALPHA_VANTAGE_API_KEY != "your_api_key_here")


# Global settings instance (singleton pattern)
_settings: Optional[Settings] = None


def get_settings() -> Settings:
    """Get the global settings instance (lazy initialization)."""
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings


def reload_settings() -> Settings:
    """Force reload settings from environment."""
    global _settings
    _settings = Settings()
    return _settings
