"""
Agent Authentication Middleware for AlphaTerminal.

Comprehensive debug logging for 20 debug cycles.

This middleware provides:
- Bearer token authentication for agent API requests
- Scope-based authorization
- Request context injection
- Audit logging
- Rate limiting enforcement

Author: AlphaTerminal Team
Version: 0.6.12
"""

import logging
import os
import time
import traceback
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Any, Callable, Optional

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

from ..services.agent.token_service import AgentToken, AgentTokenService, TokenScope, get_token_service

# Configure comprehensive logging for 20 debug cycles
logger = logging.getLogger(__name__)

# Set DEBUG level for detailed logging during development
DEBUG_MODE = os.getenv("AGENT_AUTH_DEBUG", "false").lower() == "true"

if DEBUG_MODE:
    logger.setLevel(logging.DEBUG)
    if not logger.handlers:
        handler = logging.StreamHandler()
        handler.setLevel(logging.DEBUG)
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - [%(funcName)s:%(lineno)d] - %(message)s'
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)

# HTTP Bearer scheme for token extraction
security = HTTPBearer(auto_error=False)


# ============================================================================
# Request Context Injection
# ============================================================================

class RequestContext:
    """Request context for storing token information."""
    
    def __init__(self, token: Optional[AgentToken] = None, ip_address: str = "", user_agent: str = ""):
        self.token = token
        self.ip_address = ip_address
        self.user_agent = user_agent
        self.request_start_time = time.time()
    
    def to_dict(self) -> dict:
        """Convert context to dictionary."""
        return {
            "token_id": self.token.id if self.token else None,
            "token_name": self.token.name if self.token else None,
            "ip_address": self.ip_address,
            "user_agent": self.user_agent,
            "request_duration": time.time() - self.request_start_time,
        }


# Global request context storage (thread-local)
_request_contexts = {}


def get_request_context(request: Request) -> RequestContext:
    """Get request context from request state."""
    logger.debug(f"[AUTH_CONTEXT] Getting request context for request_id={id(request)}")
    
    context = getattr(request.state, "auth_context", None)
    if context is None:
        logger.warning(f"[AUTH_CONTEXT] No context found, creating empty context")
        context = RequestContext()
    
    logger.debug(f"[AUTH_CONTEXT] Context retrieved: token_id={context.token.id if context.token else 'None'}")
    return context


def get_current_token(request: Request) -> Optional[AgentToken]:
    """Get current token from request context."""
    logger.debug(f"[AUTH_TOKEN_GET] Getting current token from request")
    
    context = get_request_context(request)
    token = context.token
    
    if token:
        logger.debug(f"[AUTH_TOKEN_GET] Token found: id={token.id}, name={token.name}")
    else:
        logger.debug(f"[AUTH_TOKEN_GET] No token in context")
    
    return token


# ============================================================================
# Token Verification Dependency
# ============================================================================

async def verify_agent_token(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
) -> AgentToken:
    """
    Verify Bearer token from Authorization header.
    
    This dependency:
    1. Extracts Bearer token from Authorization header
    2. Verifies token using TokenService
    3. Checks expiration
    4. Checks rate limit
    5. Injects token info into request state
    
    Returns:
        AgentToken if valid
        
    Raises:
        HTTPException: 401 if invalid/expired, 429 if rate limited
    """
    request_id = id(request)
    logger.info(f"[AUTH_VERIFY] Starting token verification for request_id={request_id}")
    logger.debug(f"[AUTH_VERIFY] Request path: {request.url.path}")
    logger.debug(f"[AUTH_VERIFY] Request method: {request.method}")
    logger.debug(f"[AUTH_VERIFY] Client IP: {request.client.host if request.client else 'unknown'}")
    
    # Extract client info
    ip_address = request.client.host if request.client else "unknown"
    user_agent = request.headers.get("user-agent", "unknown")
    logger.debug(f"[AUTH_VERIFY] Client info: ip={ip_address}, user_agent={user_agent[:50]}")
    
    # Check if Authorization header exists
    if credentials is None:
        logger.warning(f"[AUTH_VERIFY] Missing Authorization header for request_id={request_id}")
        logger.debug(f"[AUTH_VERIFY] Available headers: {list(request.headers.keys())}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing Authorization header",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Extract token
    raw_token = credentials.credentials
    token_prefix = raw_token[:12] if len(raw_token) >= 12 else raw_token
    logger.debug(f"[AUTH_VERIFY] Token extracted: prefix={token_prefix}***, length={len(raw_token)}")
    
    # Get token service
    service = get_token_service()
    logger.debug(f"[AUTH_VERIFY] Token service instance obtained")
    
    # Verify token
    logger.info(f"[AUTH_VERIFY] Verifying token: prefix={token_prefix}***")
    token = service.verify_token(raw_token)
    
    if token is None:
        logger.warning(f"[AUTH_VERIFY] Token verification failed: prefix={token_prefix}***")
        logger.debug(f"[AUTH_VERIFY] Token may be invalid, expired, or rate limited")
        
        # Log audit event for failed authentication
        service.log_audit(
            token_id="unknown",
            action="auth_failed",
            endpoint=request.url.path,
            details={
                "token_prefix": token_prefix,
                "ip_address": ip_address,
                "user_agent": user_agent,
                "reason": "invalid_or_expired_token",
            }
        )
        
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    logger.info(f"[AUTH_VERIFY] Token verified successfully: id={token.id}, name={token.name}")
    logger.debug(f"[AUTH_VERIFY] Token details: scopes={[s.value for s in token.scopes]}, markets={token.markets}")
    logger.debug(f"[AUTH_VERIFY] Token usage: access_count={token.access_count}, last_used={token.last_used_at}")
    
    # Check expiration explicitly
    if token.expires_at:
        now = datetime.now()
        is_expired = token.expires_at <= now
        logger.debug(f"[AUTH_VERIFY] Expiration check: expires_at={token.expires_at.isoformat()}, now={now.isoformat()}, is_expired={is_expired}")
        
        if is_expired:
            logger.warning(f"[AUTH_VERIFY] Token expired: id={token.id}, expired_at={token.expires_at.isoformat()}")
            
            # Log audit event
            service.log_audit(
                token_id=token.id,
                action="auth_expired",
                endpoint=request.url.path,
                details={
                    "expired_at": token.expires_at.isoformat(),
                    "ip_address": ip_address,
                }
            )
            
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token expired",
                headers={"WWW-Authenticate": "Bearer"},
            )
    
    # Check rate limit
    logger.debug(f"[AUTH_VERIFY] Checking rate limit: limit={token.rate_limit} requests/minute")
    rate_allowed = service.check_rate_limit(token)
    
    if not rate_allowed:
        logger.warning(f"[AUTH_VERIFY] Rate limit exceeded: id={token.id}, limit={token.rate_limit}")
        
        # Log audit event
        service.log_audit(
            token_id=token.id,
            action="rate_limit_exceeded",
            endpoint=request.url.path,
            details={
                "rate_limit": token.rate_limit,
                "ip_address": ip_address,
            }
        )
        
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Rate limit exceeded. Max {token.rate_limit} requests per minute.",
            headers={"Retry-After": "60"},
        )
    
    logger.debug(f"[AUTH_VERIFY] Rate limit check passed")
    
    # Create request context
    context = RequestContext(
        token=token,
        ip_address=ip_address,
        user_agent=user_agent,
    )
    
    # Inject context into request state
    request.state.auth_context = context
    logger.debug(f"[AUTH_VERIFY] Context injected into request state")
    
    # Log successful authentication
    service.log_audit(
        token_id=token.id,
        action="auth_success",
        endpoint=request.url.path,
        details={
            "method": request.method,
            "ip_address": ip_address,
            "user_agent": user_agent[:100],
        }
    )
    
    logger.info(f"[AUTH_VERIFY] Authentication successful: token_id={token.id}, request_id={request_id}")
    
    return token


# ============================================================================
# Scope Authorization Dependency Factory
# ============================================================================

def require_scope(required_scope: TokenScope) -> Callable:
    """
    Create a dependency that checks if token has required scope.
    
    Args:
        required_scope: Required scope (TokenScope enum)
        
    Returns:
        Dependency function that validates scope
        
    Usage:
        @router.get("/protected")
        async def protected_endpoint(
            token: AgentToken = Depends(require_scope(TokenScope.READ))
        ):
            ...
    """
    logger.debug(f"[AUTH_SCOPE_FACTORY] Creating scope checker for: {required_scope.value}")
    
    async def scope_checker(
        request: Request,
        token: AgentToken = Depends(verify_agent_token)
    ) -> AgentToken:
        """Check if token has required scope."""
        request_id = id(request)
        logger.info(f"[AUTH_SCOPE] Checking scope: required={required_scope.value}, token_id={token.id}, request_id={request_id}")
        logger.debug(f"[AUTH_SCOPE] Token scopes: {[s.value for s in token.scopes]}")
        
        # Get request context for IP and user agent
        context = get_request_context(request)
        
        # Check scope
        service = get_token_service()
        has_scope = service.check_scope(token, required_scope)
        
        if not has_scope:
            logger.warning(f"[AUTH_SCOPE] Scope check failed: required={required_scope.value}, available={[s.value for s in token.scopes]}")
            
            # Log audit event
            service.log_audit(
                token_id=token.id,
                action="scope_denied",
                endpoint=request.url.path,
                details={
                    "required_scope": required_scope.value,
                    "available_scopes": [s.value for s in token.scopes],
                    "ip_address": context.ip_address,
                }
            )
            
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Insufficient scope. Required: {required_scope.value}, Available: {[s.value for s in token.scopes]}",
            )
        
        logger.info(f"[AUTH_SCOPE] Scope check passed: token_id={token.id}, scope={required_scope.value}")
        
        # Log successful scope check
        service.log_audit(
            token_id=token.id,
            action="scope_granted",
            endpoint=request.url.path,
            details={
                "required_scope": required_scope.value,
                "ip_address": context.ip_address,
            }
        )
        
        return token
    
    return scope_checker


# ============================================================================
# Audit Middleware
# ============================================================================

class AuditMiddleware(BaseHTTPMiddleware):
    """
    Middleware for logging all agent API requests.
    
    Logs:
    - Request start/end
    - Token ID, action, resource
    - IP address, user agent
    - Request duration
    - Response status code
    """
    
    async def dispatch(self, request: Request, call_next):
        """Process request and log audit trail."""
        request_id = id(request)
        request_start_time = time.time()
        
        # Only log agent API requests
        is_agent_api = request.url.path.startswith("/api/agent/")
        
        if not is_agent_api:
            logger.debug(f"[AUDIT_SKIP] Non-agent API request: {request.url.path}")
            return await call_next(request)
        
        logger.info(f"[AUDIT_START] Request started: path={request.url.path}, method={request.method}, request_id={request_id}")
        logger.debug(f"[AUDIT_START] Headers: {dict(request.headers)}")
        
        # Extract client info
        ip_address = request.client.host if request.client else "unknown"
        user_agent = request.headers.get("user-agent", "unknown")
        
        logger.debug(f"[AUDIT_START] Client: ip={ip_address}, user_agent={user_agent[:50]}")
        
        # Process request
        try:
            response = await call_next(request)
            
            # Calculate duration
            duration = time.time() - request_start_time
            logger.debug(f"[AUDIT_END] Request completed: status={response.status_code}, duration={duration:.3f}s")
            
            # Get token from request state (if authenticated)
            token = get_current_token(request)
            
            if token:
                logger.info(f"[AUDIT_LOG] Logging audit: token_id={token.id}, path={request.url.path}, status={response.status_code}")
                
                # Log to audit service
                service = get_token_service()
                service.log_audit(
                    token_id=token.id,
                    action=f"{request.method.lower()}_{request.url.path.split('/')[-1] or 'root'}",
                    resource=request.url.path,
                    details={
                        "method": request.method,
                        "status_code": response.status_code,
                        "duration_seconds": round(duration, 3),
                        "ip_address": ip_address,
                        "user_agent": user_agent[:200],
                        "request_id": request_id,
                    }
                )
                
                logger.info(f"[AUDIT_COMPLETE] Audit logged: token_id={token.id}, duration={duration:.3f}s, status={response.status_code}")
            else:
                logger.debug(f"[AUDIT_NO_TOKEN] No token in request state, skipping audit log")
            
            return response
            
        except HTTPException as e:
            # Log HTTP exceptions (authentication/authorization errors)
            duration = time.time() - request_start_time
            logger.warning(f"[AUDIT_ERROR] HTTP exception: status={e.status_code}, detail={e.detail}, duration={duration:.3f}s")
            
            # Get token if available
            token = get_current_token(request)
            token_id = token.id if token else "unknown"
            
            # Log error
            service = get_token_service()
            service.log_audit(
                token_id=token_id,
                action="request_error",
                resource=request.url.path,
                details={
                    "method": request.method,
                    "status_code": e.status_code,
                    "error_detail": str(e.detail),
                    "duration_seconds": round(duration, 3),
                    "ip_address": ip_address,
                    "user_agent": user_agent[:200],
                    "request_id": request_id,
                }
            )
            
            raise
            
        except AttributeError as e:
            # Log attribute errors (e.g., missing request state attributes)
            duration = time.time() - request_start_time
            logger.error(f"[AUDIT_ATTR_ERROR] Attribute error: {e}\n{traceback.format_exc()}")
            
            # Get token if available
            token = get_current_token(request)
            token_id = token.id if token else "unknown"
            
            # Log error
            service = get_token_service()
            service.log_audit(
                token_id=token_id,
                action="request_attr_error",
                resource=request.url.path,
                details={
                    "method": request.method,
                    "error_type": "AttributeError",
                    "error_message": str(e),
                    "duration_seconds": round(duration, 3),
                    "ip_address": ip_address,
                    "user_agent": user_agent[:200],
                    "request_id": request_id,
                }
            )
            
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Internal server error: attribute access failed",
            )
            
        except (KeyError, ValueError, TypeError) as e:
            # Log data processing errors
            duration = time.time() - request_start_time
            logger.error(f"[AUDIT_DATA_ERROR] Data processing error: {type(e).__name__}: {e}\n{traceback.format_exc()}")
            
            # Get token if available
            token = get_current_token(request)
            token_id = token.id if token else "unknown"
            
            # Log error
            service = get_token_service()
            service.log_audit(
                token_id=token_id,
                action="request_data_error",
                resource=request.url.path,
                details={
                    "method": request.method,
                    "error_type": type(e).__name__,
                    "error_message": str(e),
                    "duration_seconds": round(duration, 3),
                    "ip_address": ip_address,
                    "user_agent": user_agent[:200],
                    "request_id": request_id,
                }
            )
            
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Internal server error: {type(e).__name__}",
            )
            
        except Exception as e:
            # Log unexpected exceptions (fallback)
            duration = time.time() - request_start_time
            logger.error(f"[AUDIT_EXCEPTION] Unexpected exception: {e}\n{traceback.format_exc()}")
            
            # Get token if available
            token = get_current_token(request)
            token_id = token.id if token else "unknown"
            
            # Log error
            service = get_token_service()
            service.log_audit(
                token_id=token_id,
                action="request_exception",
                resource=request.url.path,
                details={
                    "method": request.method,
                    "error_type": type(e).__name__,
                    "error_message": str(e),
                    "duration_seconds": round(duration, 3),
                    "ip_address": ip_address,
                    "user_agent": user_agent[:200],
                    "request_id": request_id,
                }
            )
            
            raise


# Convenience function for adding middleware
def audit_middleware(app):
    """Add audit middleware to FastAPI app."""
    logger.info("[AUDIT_MIDDLEWARE] Adding audit middleware to app")
    app.add_middleware(AuditMiddleware)
    logger.info("[AUDIT_MIDDLEWARE] Audit middleware added successfully")


# ============================================================================
# Export
# ============================================================================

__all__ = [
    "verify_agent_token",
    "require_scope",
    "audit_middleware",
    "get_current_token",
    "get_request_context",
    "RequestContext",
    "AuditMiddleware",
]