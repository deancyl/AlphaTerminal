"""
Model Configuration Service

Multi-model configuration management with hot-reload support.

Key Features:
- Singleton pattern with thread-safe access
- Hot-reload: reads from DB on each request (no caching)
- Multi-model support: multiple models per provider
- Config versioning for session binding
- Connection testing

CRITICAL: No in-memory caching - always read from DB for hot-reload.
"""
import asyncio
import logging
import threading
import httpx
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, Any, Optional, List
from threading import RLock

from app.db import model_config_db
from app.db.seed_pricing_catalog import get_pricing_by_model

logger = logging.getLogger(__name__)


@dataclass
class ModelInstance:
    """Model instance configuration"""
    model_id: str
    provider: str
    api_key: str = ""
    base_url: str = ""
    enabled: bool = True
    is_default: bool = False
    max_concurrent: int = 10
    context_length: int = 4096
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "model_id": self.model_id,
            "provider": self.provider,
            "api_key": self.api_key,
            "base_url": self.base_url,
            "enabled": self.enabled,
            "is_default": self.is_default,
            "max_concurrent": self.max_concurrent,
            "context_length": self.context_length,
            "metadata": self.metadata
        }


@dataclass
class ProviderState:
    """Provider state with multiple models"""
    provider: str
    models: Dict[str, ModelInstance] = field(default_factory=dict)
    default_model: Optional[str] = None
    enabled: bool = True
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "provider": self.provider,
            "models": {k: v.to_dict() for k, v in self.models.items()},
            "default_model": self.default_model,
            "enabled": self.enabled,
            "model_count": len(self.models)
        }


class ModelConfigService:
    """
    Multi-model configuration service with hot-reload.
    
    CRITICAL: No in-memory caching - always read from DB.
    """
    
    def __init__(self):
        self._lock = RLock()
        self._initialized = False
        logger.info("[ModelConfigService] Initialized with hot-reload enabled")
    
    def get_model(self, provider: str, model_id: Optional[str] = None) -> Optional[ModelInstance]:
        """
        Get a specific model configuration.
        
        Hot-reload: Reads from DB on each request.
        
        Args:
            provider: Provider name (e.g., 'openai', 'deepseek')
            model_id: Model ID (optional, uses default if not specified)
            
        Returns:
            ModelInstance or None
        """
        provider_key = f"llm_{provider}"
        
        # Hot-reload: Read from DB
        config = model_config_db.get_model_config(provider_key)
        
        if not config:
            # Fallback to environment variables
            return self._get_fallback_model(provider, model_id)
        
        models = config.get("models", {})
        if not models:
            return self._get_fallback_model(provider, model_id)
        
        # Determine which model to use
        target_model_id = model_id or config.get("default_model")
        
        if not target_model_id:
            # Use first available model
            target_model_id = next(iter(models.keys()), None)
        
        if not target_model_id or target_model_id not in models:
            return self._get_fallback_model(provider, model_id)
        
        model_config = models[target_model_id]
        
        return ModelInstance(
            model_id=target_model_id,
            provider=provider,
            api_key=config.get("api_key", ""),
            base_url=config.get("base_url", ""),
            enabled=model_config.get("enabled", True),
            is_default=(target_model_id == config.get("default_model")),
            max_concurrent=model_config.get("max_concurrent", 10),
            context_length=model_config.get("context_length", 4096),
            metadata=model_config.get("metadata", {})
        )
    
    def _get_fallback_model(self, provider: str, model_id: Optional[str]) -> Optional[ModelInstance]:
        """Fallback to environment variables if DB config not found"""
        import os
        
        provider_key = f"llm_{provider}"
        env_key_map = {
            "llm_openai": ("OPENAI_API_KEY", "OPENAI_API_BASE", "OPENAI_MODEL", "gpt-3.5-turbo"),
            "llm_deepseek": ("DEEPSEEK_API_KEY", "DEEPSEEK_API_BASE", "DEEPSEEK_MODEL", "deepseek-chat"),
            "llm_qianwen": ("QIANWEN_API_KEY", "QIANWEN_API_BASE", "QIANWEN_MODEL", "qwen-plus"),
            "llm_minimax": ("MINIMAX_API_KEY", None, "MINIMAX_MODEL", "abab6.5s-chat"),
            "llm_kimi": ("KIMI_API_KEY", "KIMI_API_BASE", "KIMI_MODEL", "moonshot-v1-8k"),
            "llm_siliconflow": ("SILICONFLOW_API_KEY", "SILICONFLOW_API_BASE", "SILICONFLOW_MODEL", "deepseek-ai/DeepSeek-V3"),
        }
        
        if provider_key not in env_key_map:
            return None
        
        key_env, base_env, model_env, default_model = env_key_map[provider_key]
        api_key = os.getenv(key_env, "")
        
        if not api_key:
            return None
        
        base_url = os.getenv(base_env, "") if base_env else ""
        target_model = model_id or os.getenv(model_env, "") or default_model
        
        return ModelInstance(
            model_id=target_model,
            provider=provider,
            api_key=api_key,
            base_url=base_url,
            enabled=True,
            is_default=True,
            max_concurrent=10,
            context_length=4096,
            metadata={}
        )
    
    def get_all_providers(self) -> Dict[str, ProviderState]:
        """
        Get all provider configurations.
        
        Hot-reload: Reads from DB on each request.
        
        Returns:
            Dict of provider_name -> ProviderState
        """
        all_configs = model_config_db.get_all_model_configs()
        providers: Dict[str, ProviderState] = {}
        
        for key, config in all_configs.items():
            if not key.startswith("llm_"):
                continue
            
            provider = key[4:]  # Remove 'llm_' prefix
            models = config.get("models", {})
            default_model = config.get("default_model")
            
            model_instances = {}
            for model_id, model_cfg in models.items():
                model_instances[model_id] = ModelInstance(
                    model_id=model_id,
                    provider=provider,
                    api_key=config.get("api_key", ""),
                    base_url=config.get("base_url", ""),
                    enabled=model_cfg.get("enabled", True),
                    is_default=(model_id == default_model),
                    max_concurrent=model_cfg.get("max_concurrent", 10),
                    context_length=model_cfg.get("context_length", 4096),
                    metadata=model_cfg.get("metadata", {})
                )
            
            providers[provider] = ProviderState(
                provider=provider,
                models=model_instances,
                default_model=default_model,
                enabled=any(m.enabled for m in model_instances.values())
            )
        
        # Add fallback providers from environment
        self._add_fallback_providers(providers)
        
        return providers
    
    def _add_fallback_providers(self, providers: Dict[str, ProviderState]):
        """Add providers from environment variables if not in DB"""
        import os
        
        fallback_providers = ["openai", "deepseek", "qianwen", "minimax", "kimi", "siliconflow"]
        
        for provider in fallback_providers:
            if provider in providers:
                continue
            
            model = self._get_fallback_model(provider, None)
            if model and model.api_key:
                providers[provider] = ProviderState(
                    provider=provider,
                    models={model.model_id: model},
                    default_model=model.model_id,
                    enabled=True
                )
    
    def add_model(self, provider: str, model_id: str, config: Dict[str, Any]) -> bool:
        """
        Add a new model to a provider.
        
        Args:
            provider: Provider name
            model_id: Model ID
            config: Model configuration
            
        Returns:
            Success status
        """
        provider_key = f"llm_{provider}"
        
        model_config = {
            "enabled": config.get("enabled", True),
            "max_concurrent": config.get("max_concurrent", 10),
            "context_length": config.get("context_length", 4096),
            "metadata": config.get("metadata", {})
        }
        
        return model_config_db.add_model_to_config(provider_key, model_id, model_config)
    
    def update_model(self, provider: str, model_id: str, updates: Dict[str, Any]) -> bool:
        """
        Update model configuration.
        
        Args:
            provider: Provider name
            model_id: Model ID
            updates: Fields to update
            
        Returns:
            Success status
        """
        provider_key = f"llm_{provider}"
        return model_config_db.update_model_in_config(provider_key, model_id, updates)
    
    def remove_model(self, provider: str, model_id: str) -> bool:
        """
        Remove a model from a provider.
        
        Args:
            provider: Provider name
            model_id: Model ID
            
        Returns:
            Success status
        """
        provider_key = f"llm_{provider}"
        return model_config_db.remove_model_from_config(provider_key, model_id)
    
    def set_default(self, provider: str, model_id: str) -> bool:
        """
        Set the default model for a provider.
        
        Args:
            provider: Provider name
            model_id: Model ID to set as default
            
        Returns:
            Success status
        """
        provider_key = f"llm_{provider}"
        return model_config_db.set_default_model(provider_key, model_id)
    
    def test_connection(self, provider: str, model_id: str) -> Dict[str, Any]:
        """
        Test connection to a model.
        
        Args:
            provider: Provider name
            model_id: Model ID
            
        Returns:
            Connection test result
        """
        model = self.get_model(provider, model_id)
        
        if not model:
            return {
                "success": False,
                "error": "Model not found",
                "provider": provider,
                "model_id": model_id
            }
        
        if not model.api_key:
            return {
                "success": False,
                "error": "API key not configured",
                "provider": provider,
                "model_id": model_id
            }
        
        # Test with a simple API call
        try:
            base_url = (model.base_url or self._get_default_base_url(provider)).rstrip("/")
            url = f"{base_url}/chat/completions"
            
            headers = {
                "Authorization": f"Bearer {model.api_key}",
                "Content-Type": "application/json"
            }
            
            payload = {
                "model": model_id,
                "messages": [{"role": "user", "content": "test"}],
                "max_tokens": 1
            }
            
            with httpx.Client(timeout=10.0) as client:
                response = client.post(url, headers=headers, json=payload)
                
                if response.status_code == 200:
                    return {
                        "success": True,
                        "provider": provider,
                        "model_id": model_id,
                        "latency_ms": response.elapsed.total_seconds() * 1000
                    }
                else:
                    return {
                        "success": False,
                        "error": f"API returned {response.status_code}",
                        "provider": provider,
                        "model_id": model_id
                    }
                    
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "provider": provider,
                "model_id": model_id
            }
    
    def _get_default_base_url(self, provider: str) -> str:
        """Get default base URL for a provider"""
        defaults = {
            "openai": "https://api.openai.com/v1",
            "deepseek": "https://api.deepseek.com",
            "qianwen": "https://dashscope.aliyuncs.com/compatible-mode/v1",
            "minimax": "https://api.minimax.chat/v1",
            "kimi": "https://api.moonshot.cn/v1",
            "siliconflow": "https://api.siliconflow.cn/v1"
        }
        return defaults.get(provider, "")
    
    def get_config_version(self) -> int:
        """
        Get the latest config version number.
        
        Returns:
            Version number
        """
        version = model_config_db.get_latest_config_version()
        return version["version"] if version else 1
    
    def get_enabled_models(self, provider: str) -> List[str]:
        """
        Get list of enabled models for a provider.
        
        Args:
            provider: Provider name
            
        Returns:
            List of model IDs
        """
        provider_key = f"llm_{provider}"
        return model_config_db.get_enabled_models(provider_key)


# Singleton instance
_service_instance: Optional[ModelConfigService] = None
_service_lock = threading.Lock()


def get_model_config_service() -> ModelConfigService:
    """Get singleton ModelConfigService instance"""
    global _service_instance
    if _service_instance is None:
        with _service_lock:
            if _service_instance is None:
                _service_instance = ModelConfigService()
    return _service_instance
