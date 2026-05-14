"""
Simple API Key Authentication for Sensitive Endpoints.

Provides a lightweight authentication mechanism for portfolio, backtest,
strategy, and export endpoints using a shared ADMIN_API_KEY.

This is separate from the agent token system (agent_auth.py) which handles
multi-tenant API access with scopes and rate limiting.

Usage:
    @router.post("/sensitive")
    async def sensitive_endpoint(_: None = Depends(require_api_key)):
        ...
"""
import os
import logging
from typing import Optional

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from ..config.settings import get_settings

logger = logging.getLogger(__name__)

security = HTTPBearer(auto_error=False)


def _get_api_key() -> str:
    """Get the admin API key from settings."""
    settings = get_settings()
    return settings.ADMIN_API_KEY


def _is_auth_enabled() -> bool:
    """Check if authentication is enabled (API key is configured)."""
    api_key = _get_api_key()
    return bool(api_key and api_key.strip())


async def require_api_key(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
) -> None:
    """
    Dependency that requires a valid API key for access.
    
    If ADMIN_API_KEY is not configured, authentication is skipped (development mode).
    If ADMIN_API_KEY is configured, requests must include:
        Authorization: Bearer <ADMIN_API_KEY>
    
    Raises:
        HTTPException: 401 if missing/invalid API key
    """
    api_key = _get_api_key()
    
    if not _is_auth_enabled():
        logger.debug(f"[AUTH_SKIP] No ADMIN_API_KEY configured, skipping auth for {request.url.path}")
        return None
    
    if credentials is None:
        logger.warning(f"[AUTH_FAIL] Missing Authorization header for {request.url.path}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="API key required. Include Authorization: Bearer <key>",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    provided_key = credentials.credentials
    
    if provided_key != api_key:
        logger.warning(
            f"[AUTH_FAIL] Invalid API key for {request.url.path} "
            f"(provided: {provided_key[:8]}...)"
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    client_ip = request.client.host if request.client else "unknown"
    logger.info(f"[AUTH_OK] API key authenticated for {request.url.path} from {client_ip}")
    
    return None


async def optional_api_key(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
) -> bool:
    """
    Dependency that checks API key but doesn't require it.
    
    Returns:
        True if authenticated, False otherwise
    
    Use this for endpoints that have enhanced features when authenticated
    but are still accessible without authentication.
    """
    if not _is_auth_enabled():
        return False
    
    if credentials is None:
        return False
    
    api_key = _get_api_key()
    return credentials.credentials == api_key


class APIKeyAuth:
    """
    Class-based dependency for API key authentication.
    
    Useful for more complex scenarios where you need to pass
    authentication state to the endpoint handler.
    
    Usage:
        @router.post("/sensitive")
        async def sensitive_endpoint(auth: APIKeyAuth = Depends()):
            if not auth.is_authenticated:
                raise HTTPException(401)
            ...
    """
    
    def __init__(
        self,
        request: Request,
        credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
    ):
        self.request = request
        self.credentials = credentials
        self._is_authenticated = self._check_auth()
    
    def _check_auth(self) -> bool:
        """Check if the request is authenticated."""
        if not _is_auth_enabled():
            return True
        
        if self.credentials is None:
            return False
        
        api_key = _get_api_key()
        return self.credentials.credentials == api_key
    
    @property
    def is_authenticated(self) -> bool:
        """Check if authenticated."""
        return self._is_authenticated
    
    def require_auth(self) -> None:
        """Raise 401 if not authenticated."""
        if not self._is_authenticated:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="API key required",
                headers={"WWW-Authenticate": "Bearer"},
            )


__all__ = [
    "require_api_key",
    "optional_api_key",
    "APIKeyAuth",
]