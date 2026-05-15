"""
Tests for ModelConfigService

Tests:
- test_singleton_pattern
- test_get_model_returns_correct_config
- test_add_model_creates_entry
- test_update_model_modifies_config
- test_remove_model_deletes_entry
- test_hot_reload_reads_from_db
"""
import pytest
from unittest.mock import Mock, patch, MagicMock
import threading

from app.services.model_config_service import (
    ModelConfigService,
    ModelInstance,
    ProviderState,
    get_model_config_service,
)


class TestModelConfigService:
    """Test suite for ModelConfigService."""

    @pytest.fixture
    def mock_model_config_db(self):
        """Mock model_config_db module."""
        with patch('app.services.model_config_service.model_config_db') as mock:
            yield mock

    @pytest.fixture
    def service(self):
        """Create a fresh service instance for each test."""
        return ModelConfigService()

    # ========================================================================
    # Test 1: Singleton Pattern
    # ========================================================================
    def test_singleton_pattern(self):
        """Singleton should return same instance across calls."""
        # Reset the singleton
        import app.services.model_config_service as module
        module._service_instance = None
        
        instance1 = get_model_config_service()
        instance2 = get_model_config_service()
        
        assert instance1 is instance2, "Singleton should return same instance"
        
        # Cleanup
        module._service_instance = None

    # ========================================================================
    # Test 2: Get Model Returns Correct Config
    # ========================================================================
    def test_get_model_returns_correct_config(self, service, mock_model_config_db):
        """get_model should return correct ModelInstance from DB config."""
        mock_model_config_db.get_model_config.return_value = {
            "api_key": "test-api-key",
            "base_url": "https://api.test.com/v1",
            "default_model": "gpt-4",
            "models": {
                "gpt-4": {
                    "enabled": True,
                    "max_concurrent": 5,
                    "context_length": 8192,
                    "metadata": {"description": "GPT-4"}
                }
            }
        }
        
        result = service.get_model("openai", "gpt-4")
        
        assert result is not None
        assert result.model_id == "gpt-4"
        assert result.provider == "openai"
        assert result.api_key == "test-api-key"
        assert result.base_url == "https://api.test.com/v1"
        assert result.enabled is True
        assert result.is_default is True
        assert result.max_concurrent == 5
        assert result.context_length == 8192

    # ========================================================================
    # Test 3: Add Model Creates Entry
    # ========================================================================
    def test_add_model_creates_entry(self, service, mock_model_config_db):
        """add_model should create new model entry in DB."""
        mock_model_config_db.add_model_to_config.return_value = True
        
        result = service.add_model(
            provider="openai",
            model_id="gpt-4-turbo",
            config={
                "enabled": True,
                "max_concurrent": 10,
                "context_length": 128000,
                "metadata": {"description": "GPT-4 Turbo"}
            }
        )
        
        assert result is True
        mock_model_config_db.add_model_to_config.assert_called_once()
        
        call_args = mock_model_config_db.add_model_to_config.call_args
        assert call_args[0][0] == "llm_openai"
        assert call_args[0][1] == "gpt-4-turbo"

    # ========================================================================
    # Test 4: Update Model Modifies Config
    # ========================================================================
    def test_update_model_modifies_config(self, service, mock_model_config_db):
        """update_model should modify existing model config."""
        mock_model_config_db.update_model_in_config.return_value = True
        
        result = service.update_model(
            provider="openai",
            model_id="gpt-4",
            updates={
                "max_concurrent": 20,
                "enabled": False
            }
        )
        
        assert result is True
        mock_model_config_db.update_model_in_config.assert_called_once_with(
            "llm_openai", "gpt-4", {"max_concurrent": 20, "enabled": False}
        )

    # ========================================================================
    # Test 5: Remove Model Deletes Entry
    # ========================================================================
    def test_remove_model_deletes_entry(self, service, mock_model_config_db):
        """remove_model should delete model from config."""
        mock_model_config_db.remove_model_from_config.return_value = True
        
        result = service.remove_model(provider="openai", model_id="gpt-4")
        
        assert result is True
        mock_model_config_db.remove_model_from_config.assert_called_once_with(
            "llm_openai", "gpt-4"
        )

    # ========================================================================
    # Test 6: Hot Reload Reads From DB
    # ========================================================================
    def test_hot_reload_reads_from_db(self, service, mock_model_config_db):
        """Each get_model call should read from DB (hot-reload)."""
        # First call returns config
        mock_model_config_db.get_model_config.return_value = {
            "api_key": "key1",
            "base_url": "url1",
            "default_model": "model1",
            "models": {
                "model1": {"enabled": True}
            }
        }
        
        result1 = service.get_model("openai")
        
        # Change DB config
        mock_model_config_db.get_model_config.return_value = {
            "api_key": "key2",
            "base_url": "url2",
            "default_model": "model2",
            "models": {
                "model2": {"enabled": True}
            }
        }
        
        result2 = service.get_model("openai")
        
        # Should have called DB twice (hot-reload)
        assert mock_model_config_db.get_model_config.call_count == 2
        
        # Results should reflect different DB values
        assert result1.api_key == "key1"
        assert result2.api_key == "key2"


class TestModelConfigServiceEdgeCases:
    """Test edge cases for ModelConfigService."""

    @pytest.fixture
    def mock_model_config_db(self):
        """Mock model_config_db module."""
        with patch('app.services.model_config_service.model_config_db') as mock:
            yield mock

    @pytest.fixture
    def service(self):
        """Create a fresh service instance."""
        return ModelConfigService()

    def test_get_model_returns_none_for_missing_provider(self, service, mock_model_config_db):
        """get_model should return None for non-existent provider."""
        mock_model_config_db.get_model_config.return_value = None
        
        # Without env fallback
        with patch.dict('os.environ', {}, clear=True):
            result = service.get_model("nonexistent_provider")
        
        assert result is None

    def test_get_all_providers_empty_db(self, service, mock_model_config_db):
        """get_all_providers should handle empty DB."""
        mock_model_config_db.get_all_model_configs.return_value = {}
        
        with patch.dict('os.environ', {}, clear=True):
            result = service.get_all_providers()
        
        assert isinstance(result, dict)
        # May have fallback providers from env

    def test_set_default_model(self, service, mock_model_config_db):
        """set_default should update default model."""
        mock_model_config_db.set_default_model.return_value = True
        
        result = service.set_default("openai", "gpt-4-turbo")
        
        assert result is True
        mock_model_config_db.set_default_model.assert_called_once_with(
            "llm_openai", "gpt-4-turbo"
        )

    def test_get_enabled_models(self, service, mock_model_config_db):
        """get_enabled_models should return list of enabled models."""
        mock_model_config_db.get_enabled_models.return_value = ["gpt-4", "gpt-3.5-turbo"]
        
        result = service.get_enabled_models("openai")
        
        assert result == ["gpt-4", "gpt-3.5-turbo"]
        mock_model_config_db.get_enabled_models.assert_called_once_with("llm_openai")


# ============================================================================
# Main Entry Point
# ============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
