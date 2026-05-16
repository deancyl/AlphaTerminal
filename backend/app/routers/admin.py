"""
Admin 系统控制路由 - 数据源、调度器、缓存、数据库、网络控制
"""

import asyncio
import json
import logging
import time
import os
import psutil
import sqlite3
import hashlib
import secrets
import jwt
from datetime import datetime, timedelta
from pathlib import Path

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, HTTPException, Depends, Header, Body, Query
from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field

from app.services import quote_source
from app.services.scheduler import scheduler
from app.services.sectors_cache import is_ready as sectors_cache_ready
from app.db.database import _get_conn, _db_path
from app.config.settings import get_settings

# ── 动态路径配置（解决硬编码路径问题）────────────────────────────────────────
# BASE_DIR = AlphaTerminal 项目根目录
BASE_DIR = Path(__file__).resolve().parent.parent.parent   # app/routers/admin.py → app/ → backend/ → AlphaTerminal/
# 默认日志目录
_DEFAULT_LOG_DIR = BASE_DIR / "logs"

logger = logging.getLogger(__name__)

# ═══════════════════════════════════════════════════════════════
# Admin Session Token Management
# ═══════════════════════════════════════════════════════════════

# In-memory session store (expires after ADMIN_SESSION_EXPIRY_HOURS)
_admin_sessions: Dict[str, Dict[str, Any]] = {}
ADMIN_SESSION_EXPIRY_HOURS = 24

# JWT Configuration
JWT_SECRET_KEY = secrets.token_hex(32)  # Generated once at startup
JWT_ALGORITHM = "HS256"
JWT_EXPIRY_HOURS = 24

def _generate_session_token(admin_key: str) -> str:
    """Generate a secure session token using HMAC-SHA256."""
    timestamp = str(int(time.time()))
    random_bytes = secrets.token_hex(16)
    payload = f"{admin_key}:{timestamp}:{random_bytes}"
    return hashlib.sha256(payload.encode()).hexdigest()

def _create_admin_session(admin_key: str) -> str:
    """Create a new admin session and return the session token."""
    session_token = _generate_session_token(admin_key)
    expires_at = datetime.now() + timedelta(hours=ADMIN_SESSION_EXPIRY_HOURS)
    _admin_sessions[session_token] = {
        "created_at": datetime.now().isoformat(),
        "expires_at": expires_at.isoformat(),
        "ip": "unknown",  # Will be updated on first use
    }
    logger.info(f"[Admin] Created new admin session, expires at {expires_at}")
    return session_token

def _validate_admin_session(session_token: str, client_ip: str = "unknown") -> bool:
    """Validate an admin session token. Returns True if valid, False otherwise."""
    if not session_token:
        return False
    
    session = _admin_sessions.get(session_token)
    if not session:
        return False
    
    # Check expiry
    expires_at = datetime.fromisoformat(session["expires_at"])
    if datetime.now() > expires_at:
        del _admin_sessions[session_token]
        logger.info(f"[Admin] Session expired for IP {client_ip}")
        return False
    
    # Update IP on first use
    if session["ip"] == "unknown":
        session["ip"] = client_ip
    
    return True

def _cleanup_expired_sessions():
    """Remove expired sessions from memory."""
    now = datetime.now()
    expired = [
        token for token, session in _admin_sessions.items()
        if now > datetime.fromisoformat(session["expires_at"])
    ]
    for token in expired:
        del _admin_sessions[token]
    if expired:
        logger.info(f"[Admin] Cleaned up {len(expired)} expired sessions")

def _generate_jwt_token(admin_key: str) -> tuple[str, datetime]:
    """Generate a JWT token with expiry."""
    expires_at = datetime.now() + timedelta(hours=JWT_EXPIRY_HOURS)
    payload = {
        "admin_key_hash": hashlib.sha256(admin_key.encode()).hexdigest()[:16],
        "iat": datetime.now(),
        "exp": expires_at,
        "type": "admin_access"
    }
    token = jwt.encode(payload, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)
    return token, expires_at

def _validate_jwt_token(token: str) -> tuple[bool, str]:
    """
    Validate a JWT token.
    Returns (is_valid, error_message).
    """
    try:
        payload = jwt.decode(token, JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM])
        if payload.get("type") != "admin_access":
            return False, "Invalid token type"
        return True, ""
    except jwt.ExpiredSignatureError:
        return False, "Token expired"
    except jwt.InvalidTokenError as e:
        return False, f"Invalid token: {str(e)}"

# ═══════════════════════════════════════════════════════════════
# Pydantic Request Models
# ═══════════════════════════════════════════════════════════════

class LLMSettingsRequest(BaseModel):
    provider: str = Field(..., pattern="^(deepseek|qianwen|openai|anthropic|local|siliconflow|opencode|opencode_go|opencode_zen|kimi)$")
    api_key: Optional[str] = Field(default=None, max_length=200)
    base_url: Optional[str] = Field(default=None, max_length=500)
    model: str = Field(..., max_length=100)

class LLMTestRequest(BaseModel):
    provider: str = Field(..., pattern="^(deepseek|qianwen|openai|anthropic|local|siliconflow|opencode|opencode_go|opencode_zen|kimi)$")
    api_key: str = Field(..., min_length=1, max_length=200)
    base_url: str = Field(..., min_length=1, max_length=500)
    model: Optional[str] = Field(default=None, max_length=100)

class WatchdogToggleRequest(BaseModel):
    enabled: bool

class SchedulerControlRequest(BaseModel):
    action: str = Field(..., pattern="^(start|stop|pause|resume|run)$")

class CacheInvalidateRequest(BaseModel):
    cache_type: str = Field(..., pattern="^(all|market|news|macro|f9|sectors|quotes)$")

class CacheWarmupRequest(BaseModel):
    data_type: str = Field(..., pattern="^(all|overview|sectors|macro|quotes)$")

class DatabaseMaintenanceRequest(BaseModel):
    action: str = Field(..., pattern="^(vacuum|analyze|backup|cleanup|integrity_check)$")

# ═══════════════════════════════════════════════════════════════
# Multi-Model Management Request Models
# ═══════════════════════════════════════════════════════════════

class ModelConfigRequest(BaseModel):
    provider: str = Field(..., min_length=1, max_length=50)
    model_id: str = Field(..., min_length=1, max_length=100)
    api_key: Optional[str] = Field(default=None, max_length=500)
    base_url: Optional[str] = Field(default=None, max_length=500)
    context_length: Optional[int] = Field(default=128000, ge=1, le=10000000)
    concurrency_limit: Optional[int] = Field(default=10, ge=1, le=1000)
    enabled: Optional[bool] = Field(default=True)

class ModelUpdateRequest(BaseModel):
    provider: str = Field(..., min_length=1, max_length=50)
    model_id: str = Field(..., min_length=1, max_length=100)
    context_length: Optional[int] = Field(default=None, ge=1, le=10000000)
    concurrency_limit: Optional[int] = Field(default=None, ge=1, le=1000)
    enabled: Optional[bool] = Field(default=None)

class SetDefaultModelRequest(BaseModel):
    provider: str = Field(..., min_length=1, max_length=50)
    model_id: str = Field(..., min_length=1, max_length=100)

class TestConnectionRequest(BaseModel):
    provider: str = Field(..., min_length=1, max_length=50)
    model_id: str = Field(..., min_length=1, max_length=100)

class CustomPricingRequest(BaseModel):
    model_id: str = Field(..., min_length=1, max_length=100)
    provider: str = Field(..., min_length=1, max_length=50)
    input_price_per_million: float = Field(..., ge=0)
    output_price_per_million: float = Field(..., ge=0)
    currency: str = Field(default="USD", max_length=10)

# ═══════════════════════════════════════════════════════════════
# 认证机制（必须在 router 定义之前，否则 NameError）
# ═══════════════════════════════════════════════════════════════

# 简单内存速率限制器（防暴力猜解）
_auth_failures = {}  # {ip: [timestamp1, timestamp2, ...]}
_AUTH_RATE_LIMIT = 5  # 每分钟最多 5 次失败
_AUTH_WINDOW_SEC = 60  # 窗口 60 秒

def _check_rate_limit(client_ip: str) -> bool:
    """检查是否超过速率限制，返回 True 表示允许继续"""
    import time as _time
    now = _time.time()
    failures = _auth_failures.get(client_ip, [])
    # 清理过期记录
    failures = [t for t in failures if now - t < _AUTH_WINDOW_SEC]
    _auth_failures[client_ip] = failures
    return len(failures) < _AUTH_RATE_LIMIT

def _record_failure(client_ip: str):
    """记录一次失败"""
    import time as _time
    if client_ip not in _auth_failures:
        _auth_failures[client_ip] = []
    _auth_failures[client_ip].append(_time.time())

def verify_admin_key(api_key: Optional[str] = None, x_forwarded_for: str = Header(None)):
    """Admin API 密钥校验（带速率限制）"""
    # 获取客户端 IP（支持代理）
    client_ip = x_forwarded_for.split(",")[0].strip() if x_forwarded_for else "unknown"
    
    configured_key = os.environ.get("ADMIN_API_KEY", "")
    
    # 未配置 key 时跳过认证（本机开发环境）
    if not configured_key:
        return True
    
    # 速率限制检查
    if not _check_rate_limit(client_ip):
        raise HTTPException(status_code=429, detail="Too many failed attempts, please try again later")
    
    if api_key != configured_key:
        _record_failure(client_ip)
        raise HTTPException(status_code=401, detail="Invalid API key")
    return True

def admin_read_auth(api_key: Optional[str] = None):
    """读操作认证 - GET 类接口"""
    return verify_admin_key(api_key)

def admin_write_auth(api_key: Optional[str] = None):
    """写操作认证 - POST/PUT/DELETE 类接口"""
    return verify_admin_key(api_key)

# Unauthenticated router for session token endpoint
session_router = APIRouter(prefix="/admin", tags=["admin"])

@session_router.post("/session")
def get_admin_session(
    x_forwarded_for: str = Header(None),
    x_admin_api_key: str = Header(None, alias="X-Admin-Api-Key"),
):
    """
    Get admin session token for UI authentication.
    
    Requires X-Admin-Api-Key header with the configured ADMIN_API_KEY.
    Returns a session token valid for 24 hours.
    
    This endpoint is intentionally unauthenticated (no Depends) because
    it's the authentication entry point for the admin UI.
    """
    client_ip = x_forwarded_for.split(",")[0].strip() if x_forwarded_for else "unknown"
    
    settings = get_settings()
    configured_key = settings.ADMIN_API_KEY
    
    if not configured_key:
        raise HTTPException(status_code=400, detail="ADMIN_API_KEY not configured")
    
    if not _check_rate_limit(client_ip):
        raise HTTPException(status_code=429, detail="Too many failed attempts, please try again later")
    
    if x_admin_api_key != configured_key:
        _record_failure(client_ip)
        logger.warning(f"[Admin] Invalid API key attempt from IP {client_ip}")
        raise HTTPException(status_code=401, detail="Invalid API key")
    
    _cleanup_expired_sessions()
    session_token = _create_admin_session(configured_key)
    
    logger.info(f"[Admin] Session token issued for IP {client_ip}")
    
    return {
        "code": 0,
        "message": "success",
        "data": {
            "session_token": session_token,
            "expires_at": _admin_sessions[session_token]["expires_at"],
            "expires_in_hours": ADMIN_SESSION_EXPIRY_HOURS,
        }
    }

@session_router.get("/session/validate")
def validate_admin_session(
    x_forwarded_for: str = Header(None),
    x_admin_session: str = Header(None, alias="X-Admin-Session"),
):
    """Validate an admin session token."""
    client_ip = x_forwarded_for.split(",")[0].strip() if x_forwarded_for else "unknown"
    
    if not x_admin_session:
        return {"code": 1, "message": "No session token provided", "data": {"valid": False}}
    
    _cleanup_expired_sessions()
    is_valid = _validate_admin_session(x_admin_session, client_ip)
    
    if is_valid:
        session = _admin_sessions.get(x_admin_session, {})
        return {
            "code": 0,
            "message": "success",
            "data": {
                "valid": True,
                "expires_at": session.get("expires_at"),
                "ip": session.get("ip"),
            }
        }
    else:
        return {"code": 1, "message": "Session expired or invalid", "data": {"valid": False}}

@session_router.post("/token")
def get_admin_token(
    x_forwarded_for: str = Header(None),
    x_admin_api_key: str = Header(None, alias="X-Admin-Api-Key"),
):
    """
    Get admin JWT token for UI authentication.
    
    Requires X-Admin-Api-Key header with the configured ADMIN_API_KEY.
    Returns a JWT token valid for 24 hours.
    """
    client_ip = x_forwarded_for.split(",")[0].strip() if x_forwarded_for else "unknown"
    
    settings = get_settings()
    configured_key = settings.ADMIN_API_KEY
    
    if not configured_key:
        raise HTTPException(status_code=400, detail="ADMIN_API_KEY not configured")
    
    if not _check_rate_limit(client_ip):
        raise HTTPException(status_code=429, detail="Too many failed attempts, please try again later")
    
    if x_admin_api_key != configured_key:
        _record_failure(client_ip)
        logger.warning(f"[Admin] Invalid API key attempt from IP {client_ip}")
        raise HTTPException(status_code=401, detail="Invalid API key")
    
    _cleanup_expired_sessions()
    jwt_token, expires_at = _generate_jwt_token(configured_key)
    
    logger.info(f"[Admin] JWT token issued for IP {client_ip}, expires at {expires_at}")
    
    return {
        "code": 0,
        "message": "success",
        "data": {
            "token": jwt_token,
            "expires_at": expires_at.isoformat(),
            "expires_in_hours": JWT_EXPIRY_HOURS,
        }
    }

@session_router.get("/token/validate")
def validate_admin_token(
    x_forwarded_for: str = Header(None),
    x_admin_token: str = Header(None, alias="X-Admin-Token"),
):
    """
    Validate an admin JWT token.
    Returns 401 if token is invalid or expired.
    """
    client_ip = x_forwarded_for.split(",")[0].strip() if x_forwarded_for else "unknown"
    
    if not x_admin_token:
        raise HTTPException(status_code=401, detail="No token provided")
    
    _cleanup_expired_sessions()
    is_valid, error_msg = _validate_jwt_token(x_admin_token)
    
    if is_valid:
        return {
            "code": 0,
            "message": "success",
            "data": {"valid": True}
        }
    else:
        logger.info(f"[Admin] Token validation failed for IP {client_ip}: {error_msg}")
        raise HTTPException(status_code=401, detail=error_msg)

# router 定义（在 verify_admin_key 之后）
router = APIRouter(
    prefix="/admin", 
    tags=["admin"],
    dependencies=[Depends(verify_admin_key)]
)


# ═══════════════════════════════════════════════════════════════
# LLM 配置管理（API Key 可视化配置）
# ═══════════════════════════════════════════════════════════════

def _mask_key(key: str) -> str:
    """掩码处理 API Key"""
    if not key:
        return ""
    if len(key) <= 8:
        return key
    return f"{key[:6]}...{key[-4:]}"

@router.get("/settings/llm")
def get_llm_settings():
    """获取 LLM 配置（API Key 已掩码）。优先级：数据库 > .env > 默认值"""
    from app.db.database import get_admin_config
    providers = ["deepseek", "qianwen", "openai", "siliconflow", "opencode", "opencode_go", "opencode_zen", "kimi"]
    defaults = {
        "deepseek": {"base_url": "https://api.deepseek.com", "model": "deepseek-chat"},
        "qianwen":  {"base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1", "model": "qwen-plus"},
        "openai":   {"base_url": "https://api.openai.com/v1", "model": "gpt-3.5-turbo"},
        "siliconflow": {"base_url": "https://api.siliconflow.cn/v1", "model": "deepseek-ai/DeepSeek-V3"},
        "opencode": {"base_url": "https://api.opencode.ai/v1", "model": "opencode-chat"},
        "opencode_go": {"base_url": "https://opencode.ai/zen/go/v1", "model": "minimax-m2.7"},
        "opencode_zen": {"base_url": "https://opencode.ai/zen/v1", "model": "minimax-m2.5-free"},
        "kimi":     {"base_url": "https://api.moonshot.cn/v1", "model": "moonshot-v1-8k"},
    }
    result = {}
    for p in providers:
        db  = get_admin_config(f"llm_{p}") or {}
        env = os.getenv(f"{p.upper()}_API_KEY", "")
        result[p] = {
            "api_key":       _mask_key(db.get("api_key") or env),
            "base_url":      db.get("base_url") or defaults[p]["base_url"],
            "model":          db.get("model")    or defaults[p]["model"],
            "has_db_config":  bool(db.get("api_key")),
        }
    return {"code": 0, "data": result}

@router.post("/settings/llm")
def save_llm_settings(body: LLMSettingsRequest):
    """保存 LLM 配置到数据库（永久生效）"""
    from app.db.database import get_admin_config, set_admin_config
    provider = body.provider.lower()
    key_map  = {
        "deepseek": "llm_deepseek", 
        "qianwen": "llm_qianwen", 
        "openai": "llm_openai", 
        "siliconflow": "llm_siliconflow", 
        "opencode": "llm_opencode",
        "opencode_go": "llm_opencode_go",
        "opencode_zen": "llm_opencode_zen",
        "kimi": "llm_kimi",
    }
    if provider not in key_map:
        return {"code": 1, "error": f"Unknown provider: {provider}"}
    set_admin_config(key_map[provider], {
        "api_key":  (body.api_key or "").strip(),
        "base_url": (body.base_url or "").strip(),
        "model":    body.model.strip(),
    })
    return {"code": 0, "message": f"{provider} 配置已保存"}

# ═══════════════════════════════════════════════════════════════
# Multi-Model Management Endpoints
# ═══════════════════════════════════════════════════════════════

@router.get("/models/all")
def get_all_models():
    """Get all configured models across all providers"""
    from app.services.model_config_service import get_model_config_service
    
    service = get_model_config_service()
    providers = service.get_all_providers()
    
    result = {}
    for provider_name, provider_state in providers.items():
        models_data = []
        for model_id, model in provider_state.models.items():
            models_data.append({
                "model_id": model.model_id,
                "enabled": model.enabled,
                "is_default": model.is_default,
                "max_concurrent": model.max_concurrent,
                "context_length": model.context_length,
                "api_key_masked": _mask_key(model.api_key),
                "base_url": model.base_url
            })
        result[provider_name] = {
            "provider": provider_name,
            "enabled": provider_state.enabled,
            "default_model": provider_state.default_model,
            "model_count": len(models_data),
            "models": models_data
        }
    
    return {"code": 0, "data": result}

@router.get("/models/{provider}")
def get_provider_models(provider: str):
    """Get models for a specific provider"""
    from app.services.model_config_service import get_model_config_service
    
    service = get_model_config_service()
    providers = service.get_all_providers()
    
    provider_lower = provider.lower()
    if provider_lower not in providers:
        return {"code": 1, "error": f"Provider '{provider}' not found"}
    
    provider_state = providers[provider_lower]
    models_data = []
    for model_id, model in provider_state.models.items():
        models_data.append({
            "model_id": model.model_id,
            "enabled": model.enabled,
            "is_default": model.is_default,
            "max_concurrent": model.max_concurrent,
            "context_length": model.context_length,
            "api_key_masked": _mask_key(model.api_key),
            "base_url": model.base_url
        })
    
    return {
        "code": 0,
        "data": {
            "provider": provider_lower,
            "enabled": provider_state.enabled,
            "default_model": provider_state.default_model,
            "models": models_data
        }
    }

@router.post("/models/add")
def add_model(body: ModelConfigRequest):
    """Add a new model configuration"""
    from app.services.model_config_service import get_model_config_service
    
    service = get_model_config_service()
    
    config = {
        "enabled": body.enabled,
        "max_concurrent": body.concurrency_limit,
        "context_length": body.context_length,
        "metadata": {}
    }
    
    success = service.add_model(body.provider.lower(), body.model_id, config)
    
    if success:
        return {"code": 0, "message": f"Model '{body.model_id}' added to provider '{body.provider}'"}
    else:
        return {"code": 1, "error": f"Failed to add model '{body.model_id}'"}

@router.patch("/models/update")
def update_model(body: ModelUpdateRequest):
    """Update model configuration"""
    from app.services.model_config_service import get_model_config_service
    
    service = get_model_config_service()
    
    updates = {}
    if body.context_length is not None:
        updates["context_length"] = body.context_length
    if body.concurrency_limit is not None:
        updates["max_concurrent"] = body.concurrency_limit
    if body.enabled is not None:
        updates["enabled"] = body.enabled
    
    if not updates:
        return {"code": 1, "error": "No fields to update"}
    
    success = service.update_model(body.provider.lower(), body.model_id, updates)
    
    if success:
        return {"code": 0, "message": f"Model '{body.model_id}' updated"}
    else:
        return {"code": 1, "error": f"Failed to update model '{body.model_id}'"}

@router.delete("/models/{provider}/{model_id}")
def remove_model(provider: str, model_id: str):
    """Remove a model from a provider"""
    from app.services.model_config_service import get_model_config_service
    
    service = get_model_config_service()
    success = service.remove_model(provider.lower(), model_id)
    
    if success:
        return {"code": 0, "message": f"Model '{model_id}' removed from '{provider}'"}
    else:
        return {"code": 1, "error": f"Failed to remove model '{model_id}'"}

@router.post("/models/set-default")
def set_default_model(body: SetDefaultModelRequest):
    """Set the default model for a provider"""
    from app.services.model_config_service import get_model_config_service
    
    service = get_model_config_service()
    success = service.set_default(body.provider.lower(), body.model_id)
    
    if success:
        return {"code": 0, "message": f"Default model set to '{body.model_id}' for '{body.provider}'"}
    else:
        return {"code": 1, "error": f"Failed to set default model"}

@router.post("/models/test")
def test_model_connection(body: TestConnectionRequest):
    """Test connection to a model"""
    from app.services.model_config_service import get_model_config_service
    
    service = get_model_config_service()
    result = service.test_connection(body.provider.lower(), body.model_id)
    
    if result.get("success"):
        return {"code": 0, "data": result}
    else:
        return {"code": 1, "error": result.get("error", "Connection test failed"), "data": result}

@router.get("/models/pricing/catalog")
def get_pricing_catalog():
    """Get pricing catalog for all models"""
    from app.db.seed_pricing_catalog import get_all_pricing
    
    pricing = get_all_pricing()
    return {"code": 0, "data": pricing}

@router.post("/models/pricing/add")
def add_custom_pricing(body: CustomPricingRequest):
    """Add custom pricing for a model"""
    from app.db.seed_pricing_catalog import seed_pricing_catalog
    
    custom_model = {
        "model_id": body.model_id,
        "provider": body.provider,
        "display_name": body.model_id,
        "input_cost_per_token": body.input_price_per_million / 1e6,
        "output_cost_per_token": body.output_price_per_million / 1e6,
        "context_length": 4096,
        "metadata": json.dumps({"currency": body.currency, "custom": True})
    }
    
    result = seed_pricing_catalog(models=[custom_model], force=True)
    
    if result.get("inserted", 0) > 0 or result.get("updated", 0) > 0:
        return {"code": 0, "message": f"Custom pricing added for '{body.model_id}'", "data": result}
    else:
        return {"code": 1, "error": f"Failed to add custom pricing", "data": result}


@router.post("/settings/llm/test")
def test_llm_connection(body: LLMTestRequest):
    """探测 LLM Provider 连接"""
    import httpx
    provider = body.provider.lower()
    api_key  = body.api_key.strip()
    base_url = body.base_url.strip()
    model    = (body.model or "").strip()
    defaults = {
        "deepseek": "deepseek-chat", 
        "qianwen": "qwen-plus", 
        "openai": "gpt-3.5-turbo", 
        "siliconflow": "deepseek-ai/DeepSeek-V3", 
        "opencode": "opencode-chat",
        "opencode_go": "minimax-m2.7",
        "opencode_zen": "minimax-m2.5-free",
        "kimi": "moonshot-v1-8k",
    }
    test_url  = f"{base_url.rstrip('/')}/chat/completions"
    headers   = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    payload   = {"model": model or defaults.get(provider, "gpt-3.5-turbo"),
                 "messages": [{"role": "user", "content": "Hi"}], "max_tokens": 5}
    try:
        resp = httpx.post(test_url, headers=headers, json=payload, timeout=15)
        if resp.status_code == 200:
            return {"code": 0, "message": "连接成功 ✅", "status": resp.status_code}
        err = resp.json().get("error", {}) if "json" in resp.headers.get("content-type","") else {}
        return {"code": 1, "error": f"HTTP {resp.status_code}: {err.get('message', resp.text[:80])}"}
    except httpx.TimeoutException:
        return {"code": 1, "error": "连接超时，请检查 URL"}
    except Exception as e:
        return {"code": 1, "error": str(e)[:100]}


# ═══════════════════════════════════════════════════════════════
# 数据源控制
# ═══════════════════════════════════════════════════════════════

class SourceBalanceConfig(BaseModel):
    strategy: str = "weighted_round_robin"  # weighted_round_robin | priority | failover
    weights: Dict[str, int] = {"tencent": 50, "sina": 30, "eastmoney": 20}
    health_check: Dict[str, Any] = {
        "interval": 10,
        "timeout": 3,
        "fail_threshold": 3
    }

class CircuitBreakerControl(BaseModel):
    source: str
    action: str  # "open" | "close" | "half_open"

@router.get("/sources/status")
async def get_sources_status():
    """获取所有数据源实时状态（合并 SQLite 持久化的熔断状态）"""
    from app.services import quote_source
    
    # 从 quote_source 获取实时状态
    status_data = quote_source.get_source_status()
    real_time = status_data.get("sources", {})
    
    # 从 SQLite 获取持久化熔断状态
    try:
        conn = _get_conn()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT source, state, fail_count, last_fail_time FROM circuit_breaker")
            db_states = {row[0]: {"state": row[1], "fail_count": row[2], "last_fail_time": row[3]} for row in cursor.fetchall()}
        finally:
            conn.close()
    except sqlite3.OperationalError:
        # 表不存在，返回空状态
        db_states = {}
    
    # 合并状态
    merged = {}
    for source, status in real_time.items():
        db_state = db_states.get(source, {})
        merged[source] = {
            **status,
            "state": db_state.get("state", status.get("state", "unknown")),
            "fail_count": db_state.get("fail_count", 0),
            "last_fail_time": db_state.get("last_fail_time")
        }
    
    return {"sources": merged, "timestamp": int(time.time())}

@router.post("/sources/circuit_breaker")
async def control_circuit_breaker(control: CircuitBreakerControl):
    """手动控制熔断器"""
    from app.services import quote_source

    if control.action == "open":
        quote_source.open_circuit(control.source)
        return {"message": f"已熔断 {control.source}", "state": "open"}

    elif control.action == "close":
        quote_source.close_circuit(control.source)
        return {"message": f"已恢复 {control.source}", "state": "closed"}

    else:
        raise HTTPException(status_code=400, detail=f"Unknown action: {control.action}")

@router.post("/sources/probe")
async def probe_all_sources():
    """主动探测所有数据源并返回实时延迟（包含熔断状态、主源标记和历史）"""
    import asyncio
    from app.services import quote_source

    sources = quote_source.DATA_SOURCES.keys()
    results = {}
    current_source = quote_source._current_source

    for name in sources:
        try:
            result = await quote_source.test_source_async(name)
            current_state = quote_source._source_status.get(name, {})
            history = current_state.get("history", [])
            results[name] = {
                **result,
                "state": current_state.get("state", "unknown"),
                "fail_count": current_state.get("fail_count", 0),
                "is_primary": name == current_source,
                "history": history[-5:] if history else []
            }
        except Exception as e:
            results[name] = {"status": "error", "latency": None, "state": "unknown", "fail_count": 0, "is_primary": name == current_source, "history": [], "error": str(e)}

    return {"sources": results, "current_source": current_source, "timestamp": int(time.time())}

@router.get("/sources/balance")
async def get_balance_config():
    """获取负载均衡配置"""
    conn = _get_conn()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT value FROM admin_config WHERE key = 'source_balance'")
        row = cursor.fetchone()
    finally:
        conn.close()
    if row:
        import json
        return json.loads(row[0])
    return SourceBalanceConfig().dict()

@router.post("/sources/balance")
async def set_balance_config(config: SourceBalanceConfig):
    """设置负载均衡配置"""
    import json
    conn = _get_conn()
    try:
        cursor = conn.cursor()
        cursor.execute(
            "INSERT OR REPLACE INTO admin_config (key, value, updated_at) VALUES (?, ?, ?)",
            ("source_balance", json.dumps(config.dict()), datetime.now().isoformat())
        )
        conn.commit()
    finally:
        conn.close()
    return {"message": "负载均衡配置已更新", "config": config.dict()}


# ═══════════════════════════════════════════════════════════════
# 调度器控制
# ═══════════════════════════════════════════════════════════════

@router.get("/scheduler/jobs")
async def get_scheduler_jobs():
    """获取所有定时任务状态"""
    jobs = scheduler.get_jobs()
    return {
        "jobs": [
            {
                "id": job.id,
                "name": job.name,
                "next_run_time": job.next_run_time.isoformat() if job.next_run_time else None,
                "trigger": str(job.trigger),
                "state": "running" if job.next_run_time is not None else "paused",
            }
            for job in jobs
        ]
    }

@router.post("/scheduler/jobs/{job_id}/control")
async def control_scheduler_job(job_id: str, body: SchedulerControlRequest):
    """控制定时任务（pause/resume/run）"""
    action = body.action
    if action == "pause":
        scheduler.pause_job(job_id)
        return {"message": f"任务 {job_id} 已暂停"}
    elif action == "resume":
        scheduler.resume_job(job_id)
        return {"message": f"任务 {job_id} 已恢复"}
    elif action == "run":
        job = scheduler.get_job(job_id)
        if job:
            job.modify(next_run_time=datetime.now())
            return {"message": f"任务 {job_id} 已触发立即执行"}
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found")
    else:
        raise HTTPException(status_code=400, detail=f"Unknown action: {action}")


# ═══════════════════════════════════════════════════════════════
# 缓存控制
# ═══════════════════════════════════════════════════════════════

@router.post("/cache/invalidate")
async def invalidate_cache(body: CacheInvalidateRequest):
    """清空指定缓存"""
    cache_type = body.cache_type
    if cache_type == "sectors":
        from app.services.sectors_cache import invalidate
        invalidate()
        return {"message": "板块缓存已清空"}
    elif cache_type == "quotes":
        from app.services.quote_source import clear_cache
        clear_cache()
        return {"message": "行情缓存已清空"}
    elif cache_type == "all":
        from app.services.sectors_cache import invalidate as invalidate_sectors
        from app.services.quote_source import clear_cache as clear_quotes
        invalidate_sectors()
        clear_quotes()
        return {"message": "所有缓存已清空"}
    else:
        raise HTTPException(status_code=400, detail=f"Unknown cache type: {cache_type}")

@router.post("/cache/warmup")
async def warmup_cache(body: CacheWarmupRequest):
    """预热缓存"""
    data_type = body.data_type
    if data_type == "sectors":
        from app.services.sectors_cache import warmup
        await warmup()
        return {"message": "板块缓存预热已启动"}
    elif data_type == "quotes":
        from app.services.quote_source import warmup
        await warmup()
        return {"message": "行情缓存预热已启动"}
    else:
        raise HTTPException(status_code=400, detail=f"Unknown data type: {data_type}")


# ═══════════════════════════════════════════════════════════════
# 数据库维护
# ═══════════════════════════════════════════════════════════════

@router.post("/database/maintenance")
async def database_maintenance(body: DatabaseMaintenanceRequest):
    """数据库维护操作"""
    action = body.action
    conn = _get_conn()
    try:
        if action == "vacuum":
            conn.execute("VACUUM")
            return {"message": "数据库已优化 (VACUUM)"}
        elif action == "analyze":
            conn.execute("ANALYZE")
            return {"message": "数据库统计信息已更新 (ANALYZE)"}
        elif action == "integrity_check":
            cursor = conn.execute("PRAGMA integrity_check")
            result = cursor.fetchone()[0]
            return {"message": f"完整性检查结果: {result}", "status": result}
        else:
            raise HTTPException(status_code=400, detail=f"Unknown action: {action}")
    finally:
        conn.close()

@router.get("/database/stats")
async def get_database_stats():
    """获取数据库统计信息"""
    conn = _get_conn()
    try:
        cursor = conn.cursor()
        
        # 获取所有表的大小
        cursor.execute("""
            SELECT name, 
                   (SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name=name) as count
            FROM sqlite_master 
            WHERE type='table'
        """)
        tables = cursor.fetchall()
        
        stats = {}
        _ALLOWED_TABLES = frozenset({
            'market_data_realtime', 'market_data_daily', 'market_data_periodic',
            'write_buffer', 'portfolios', 'positions', 'portfolio_snapshots',
            'admin_config', 'market_all_stocks', 'transactions',
            'position_lots', 'position_summary',
        })
        for table_name, _ in tables:
            if table_name not in _ALLOWED_TABLES:
                continue
            try:
                cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
                count = cursor.fetchone()[0]
                stats[table_name] = count
            except sqlite3.OperationalError:
                stats[table_name] = -1  # 表存在于 master 但无法查询
        
        # 获取数据库文件大小
        db_size = os.path.getsize(_db_path) if os.path.exists(_db_path) else 0
    finally:
        conn.close()
    
    return {
        "tables": stats,
        "total_tables": len(tables),
        "db_size_bytes": db_size,
        "db_size_mb": round(db_size / (1024 * 1024), 2)
    }


# ═══════════════════════════════════════════════════════════════
# 系统监控
# ═══════════════════════════════════════════════════════════════

@router.get("/system/metrics")
async def get_system_metrics():
    """获取系统资源使用情况"""
    cpu_percent = psutil.cpu_percent(interval=1)
    memory = psutil.virtual_memory()
    disk = psutil.disk_usage('/')
    
    return {
        "cpu_percent": cpu_percent,
        "memory": {
            "total": memory.total,
            "available": memory.available,
            "percent": memory.percent,
            "used": memory.used
        },
        "disk": {
            "total": disk.total,
            "used": disk.used,
            "free": disk.free,
            "percent": (disk.used / disk.total) * 100
        },
        "timestamp": int(time.time())
    }

@router.get("/system/logs")
@router.get("/logs/recent")  # 兼容旧接口
async def get_recent_logs(lines: int = Query(default=100, ge=1, le=1000)):
    """获取最近日志"""
    log_file = _DEFAULT_LOG_DIR / "app.log"
    if not log_file.exists():
        return {"logs": [], "message": "日志文件不存在"}
    
    with open(log_file, 'r') as f:
        all_lines = f.readlines()
    
    recent_lines = all_lines[-lines:] if len(all_lines) > lines else all_lines
    return {"logs": recent_lines}


# ═══════════════════════════════════════════════════════════════
# Token Usage Query Endpoints
# ═══════════════════════════════════════════════════════════════

@router.get("/tokens/stats")
def get_token_stats(
    start_time: Optional[str] = Query(default=None),
    end_time: Optional[str] = Query(default=None)
):
    """Get total token usage statistics"""
    from app.services.token_tracking_service import get_token_tracking_service
    
    service = get_token_tracking_service()
    stats = service.get_total_stats(start_time, end_time)
    
    return {"code": 0, "data": stats}

@router.get("/tokens/history")
def get_token_history(
    model_id: Optional[str] = Query(default=None),
    session_id: Optional[str] = Query(default=None),
    user_id: Optional[str] = Query(default=None),
    start_date: Optional[str] = Query(default=None),
    end_date: Optional[str] = Query(default=None),
    limit: int = Query(default=100, ge=1, le=1000)
):
    """Get token usage history with filters"""
    from app.services.token_tracking_service import get_token_tracking_service
    
    service = get_token_tracking_service()
    history = service.get_usage_history(
        model_id=model_id,
        session_id=session_id,
        user_id=user_id,
        start_date=start_date,
        end_date=end_date,
        limit=limit
    )
    
    return {"code": 0, "data": history, "count": len(history)}

@router.get("/tokens/aggregated")
def get_token_aggregated(
    aggregate_type: str = Query(default="daily", pattern="^(hourly|daily|weekly)$"),
    limit: int = Query(default=30, ge=1, le=365)
):
    """Get aggregated token usage statistics for charts"""
    from app.services.token_tracking_service import get_token_tracking_service
    
    service = get_token_tracking_service()
    aggregated = service.get_aggregated_stats(aggregate_type, limit)
    
    return {"code": 0, "data": aggregated, "count": len(aggregated)}

@router.get("/tokens/breakdown/models")
def get_token_breakdown_models(
    start_time: Optional[str] = Query(default=None),
    end_time: Optional[str] = Query(default=None)
):
    """Get token usage breakdown by model"""
    from app.services.token_tracking_service import get_token_tracking_service
    
    service = get_token_tracking_service()
    breakdown = service.get_model_breakdown(start_time, end_time)
    
    return {"code": 0, "data": breakdown, "count": len(breakdown)}

@router.get("/tokens/breakdown/providers")
def get_token_breakdown_providers(
    days: int = Query(default=30, ge=1, le=365)
):
    """Get token usage breakdown by provider"""
    from app.services.token_tracking_service import get_token_tracking_service
    
    service = get_token_tracking_service()
    breakdown = service.get_provider_breakdown(days)
    
    return {"code": 0, "data": breakdown, "count": len(breakdown)}

@router.get("/tokens/session/{session_id}")
def get_session_token_usage(session_id: str):
    """Get token usage for a specific session"""
    from app.services.token_tracking_service import get_token_tracking_service
    
    service = get_token_tracking_service()
    history = service.get_usage_history(session_id=session_id, limit=1000)
    
    total_tokens = sum(r.get("total_tokens", 0) for r in history)
    total_cost = sum(r.get("cost_usd", 0) for r in history)
    total_requests = len(history)
    
    return {
        "code": 0,
        "data": {
            "session_id": session_id,
            "total_requests": total_requests,
            "total_tokens": total_tokens,
            "total_cost_usd": total_cost,
            "history": history[:100]
        }
    }


# ═══════════════════════════════════════════════════════════════
# Session Management Endpoints
# ═══════════════════════════════════════════════════════════════

@router.get("/sessions/active")
def get_active_sessions(
    limit: int = Query(default=100, ge=1, le=1000)
):
    """Get all active sessions"""
    from app.services.session_manager import get_session_manager
    
    manager = get_session_manager()
    sessions = manager.get_active_sessions(limit)
    
    return {
        "code": 0,
        "data": [s.to_dict() for s in sessions],
        "count": len(sessions)
    }

@router.get("/sessions/stats")
def get_sessions_stats():
    """Get global session statistics"""
    from app.services.session_manager import get_session_manager
    
    manager = get_session_manager()
    stats = manager.get_global_stats()
    
    return {"code": 0, "data": stats}

@router.get("/sessions/{session_id}")
def get_session_details(session_id: str):
    """Get session details by ID"""
    from app.services.session_manager import get_session_manager
    
    manager = get_session_manager()
    session = manager.get_session(session_id)
    
    if not session:
        return {"code": 1, "error": f"Session '{session_id}' not found"}
    
    return {"code": 0, "data": session.to_dict()}

@router.delete("/sessions/{session_id}")
def terminate_session(session_id: str):
    """Terminate a session"""
    from app.services.session_manager import get_session_manager
    
    manager = get_session_manager()
    success = manager.delete_session(session_id)
    
    if success:
        return {"code": 0, "message": f"Session '{session_id}' terminated"}
    else:
        return {"code": 1, "error": f"Failed to terminate session '{session_id}'"}

@router.post("/sessions/cleanup")
def trigger_session_cleanup():
    """Manually trigger session cleanup"""
    from app.db import session_db
    
    deleted = session_db.cleanup_expired_sessions()
    
    return {"code": 0, "message": f"Cleaned up {deleted} expired sessions", "data": {"deleted_count": deleted}}

@router.get("/sessions/{session_id}/conversations")
def get_session_conversations(session_id: str):
    """Get conversation history for a session"""
    from app.db import session_db
    
    session = session_db.get_session(session_id)
    if not session:
        return {"code": 1, "error": f"Session '{session_id}' not found"}
    
    conversations = session_db.get_session_conversations(session_id) if hasattr(session_db, 'get_session_conversations') else []
    
    return {"code": 0, "data": conversations, "count": len(conversations)}


# ═══════════════════════════════════════════════════════════════
# WebSocket Real-time Token Updates
# ═══════════════════════════════════════════════════════════════

_token_stream_connections: set = set()
_token_stream_queue: asyncio.Queue = asyncio.Queue(maxsize=200)

@router.websocket("/tokens/stream")
async def token_stream_ws(websocket: WebSocket):
    """WebSocket for real-time token usage updates"""
    await websocket.accept()
    conn_id = f"token_ws_{int(time.time())}_{secrets.token_hex(4)}"
    _token_stream_connections.add(conn_id)
    
    await websocket.send_json({
        "type": "connected",
        "conn_id": conn_id,
        "timestamp": int(time.time())
    })
    
    try:
        while True:
            try:
                update = await asyncio.wait_for(_token_stream_queue.get(), timeout=30.0)
                await websocket.send_json(update)
            except asyncio.TimeoutError:
                await websocket.send_json({
                    "type": "heartbeat",
                    "timestamp": int(time.time())
                })
    except WebSocketDisconnect:
        _token_stream_connections.discard(conn_id)


# ═══════════════════════════════════════════════════════════════
# WebSocket 实时日志流
# ═══════════════════════════════════════════════════════════════

@router.websocket("/logs/stream")
async def log_stream_ws(websocket: WebSocket):
    """WebSocket实时日志流"""
    await websocket.accept()
    
    # 使用模块级日志队列
    queue = _log_queue
    
    async def log_writer():
        """日志写入队列的 handler（供外部调用）"""
        pass  # 实际实现在 services/logging_queue.py
    
    # 发送欢迎消息
    await websocket.send_json({
        "timestamp": int(time.time()),
        "level": "INFO",
        "message": "Log stream connected. Waiting for logs..."
    })
    
    try:
        while True:
            try:
                # 从队列获取日志（5秒超时）
                log_msg = await asyncio.wait_for(queue.get(), timeout=5.0)
                await websocket.send_json(log_msg)
            except asyncio.TimeoutError:
                # 超时发送心跳
                await websocket.send_json({
                    "timestamp": int(time.time()),
                    "level": "HEARTBEAT",
                    "message": "heartbeat"
                })
    except WebSocketDisconnect:
        pass

# 预先创建日志队列供外部导入使用
_log_queue = asyncio.Queue(maxsize=100)

# 初始化 error_logger 的队列引用
try:
    from app.services.error_logger import init_log_queue
    init_log_queue(_log_queue)
    logger.info("[Admin] error_logger 队列已初始化")
except Exception as e:
    logger.warning(f"[Admin] error_logger 初始化失败: {e}")


# ═══════════════════════════════════════════════════════════════
# 进程保活监控 (Watchdog)
# ═══════════════════════════════════════════════════════════════

@router.get("/watchdog/status")
async def get_watchdog_status():
    """获取进程保活监控状态"""
    from app.services.watchdog import get_watchdog_state
    return {
        "code": 0,
        "message": "success",
        "data": get_watchdog_state()
    }


@router.post("/watchdog/toggle")
async def toggle_watchdog_endpoint(body: WatchdogToggleRequest):
    """切换进程保活开关
    
    请求体: {"enabled": true/false}
    """
    from app.services.watchdog import toggle_watchdog
    
    success = toggle_watchdog(body.enabled)
    if success:
        return {
            "code": 0,
            "message": f"进程保活已{'启用' if body.enabled else '禁用'}",
            "data": {"enabled": body.enabled}
        }
    else:
        return {"code": 500, "message": "切换失败，请检查日志"}


@router.post("/watchdog/restart")
async def manual_restart_backend():
    """手动触发后端重启（用于紧急恢复）"""
    from app.services.watchdog import _restart_backend, _watchdog_state

    logger.warning("[Admin] 收到手动重启后端请求")
    success = _restart_backend()

    if success:
        _watchdog_state.record_restart()
        return {
            "code": 0,
            "message": "后端重启指令已发送，请等待 5-10 秒后刷新页面",
            "data": {"restart_time": datetime.now().isoformat()}
        }
    else:
        return {"code": 500, "message": "重启失败，请检查后端日志"}


# ═══════════════════════════════════════════════════════════════
# WebSocket 指标
# ═══════════════════════════════════════════════════════════════

@router.get("/ws/metrics")
async def get_ws_metrics():
    """获取 WebSocket 连接指标"""
    from app.services.ws_manager import ws_manager

    metrics = await ws_manager.get_metrics()
    return {
        "code": 0,
        "data": {
            "active_connections": metrics.get("active_connections", 0),
            "latency_avg": metrics.get("latency_avg"),
            "latency_min": metrics.get("latency_min"),
            "latency_max": metrics.get("latency_max"),
            "subscribed_symbols": metrics.get("subscribed_symbols", 0),
        }
    }


# ═══════════════════════════════════════════════════════════════
# Rate Limiting 管理
# ═══════════════════════════════════════════════════════════════

@router.get("/ratelimit/stats")
async def get_rate_limit_stats():
    """获取速率限制统计信息"""
    from app.middleware.rate_limit import get_limiter
    from app.config.rate_limit import ENDPOINT_LIMITS
    
    limiter = get_limiter()
    stats = limiter.get_stats()
    
    endpoint_limits = {
        name: {"requests": limit.requests, "period": limit.period}
        for name, limit in ENDPOINT_LIMITS.items()
    }
    
    blocked_ips = []
    now = time.time()
    for key, entry in stats.get("entries", {}).items():
        if entry.get("count", 0) >= 10:
            ip = key.split(":")[0] if ":" in key else key
            blocked_ips.append({
                "ip": ip,
                "path": key.split(":", 1)[1] if ":" in key else "",
                "count": entry.get("count", 0),
                "reset_at": entry.get("reset_at", 0),
                "remaining_seconds": max(0, int(entry.get("reset_at", 0) - now))
            })
    
    return {
        "code": 0,
        "data": {
            "total_tracked_ips": stats.get("total_keys", 0),
            "endpoint_limits": endpoint_limits,
            "blocked_requests": blocked_ips[:50],
            "enabled": True
        }
    }


@router.post("/ratelimit/reset")
async def reset_rate_limit(ip: Optional[str] = None):
    """重置速率限制（可选指定IP）"""
    from app.middleware.rate_limit import get_limiter
    
    limiter = get_limiter()
    
    if ip:
        keys_to_reset = [k for k in limiter._storage.keys() if k.startswith(f"{ip}:")]
        for key in keys_to_reset:
            limiter.reset(key)
        logger.info(f"[Admin] Reset rate limit for IP: {ip}")
        return {
            "code": 0,
            "message": f"已重置 {ip} 的速率限制",
            "data": {"reset_count": len(keys_to_reset)}
        }
    else:
        limiter.reset()
        logger.info("[Admin] Reset all rate limits")
        return {
            "code": 0,
            "message": "已重置所有速率限制",
            "data": {"reset_count": stats.get("total_keys", 0) if (stats := get_limiter().get_stats()) else 0}
        }


# ═══════════════════════════════════════════════════════════════
# Web Vitals Collection (Performance Metrics)
# ═══════════════════════════════════════════════════════════════

_web_vitals_buffer: List[Dict[str, Any]] = []
WEB_VITALS_MAX_BUFFER = 100

class WebVitalsMetric(BaseModel):
    name: str
    value: float
    rating: str
    timestamp: int
    page: str

@router.post("/web-vitals")
async def collect_web_vitals(metric: WebVitalsMetric):
    _web_vitals_buffer.append(metric.dict())
    if len(_web_vitals_buffer) > WEB_VITALS_MAX_BUFFER:
        _web_vitals_buffer.pop(0)
    
    if metric.rating == "poor":
        logger.warning(f"[WebVitals] Poor metric: {metric.name}={metric.value}ms on {metric.page}")
    
    return {"code": 0, "message": "Metric recorded"}

@router.get("/web-vitals")
async def get_web_vitals_stats():
    if not _web_vitals_buffer:
        return {"code": 0, "data": {"metrics": [], "summary": "No metrics collected"}}
    
    summary = {}
    for m in _web_vitals_buffer:
        name = m["name"]
        if name not in summary:
            summary[name] = {"count": 0, "avg": 0, "poor_count": 0, "values": []}
        summary[name]["count"] += 1
        summary[name]["values"].append(m["value"])
        if m["rating"] == "poor":
            summary[name]["poor_count"] += 1
    
    for name, stats in summary.items():
        stats["avg"] = sum(stats["values"]) / len(stats["values"])
        stats["values"] = stats["values"][-10:]
    
    return {
        "code": 0,
        "data": {
            "metrics": _web_vitals_buffer[-20:],
            "summary": summary,
            "total_collected": len(_web_vitals_buffer)
        }
    }
