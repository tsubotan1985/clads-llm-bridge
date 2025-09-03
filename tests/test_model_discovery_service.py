"""Tests for model discovery service."""

import pytest
import asyncio
from unittest.mock import AsyncMock, patch, MagicMock

from src.config.model_discovery_service import ModelDiscoveryService
from src.models.enums import ServiceType


class TestModelDiscoveryService:
    """Test cases for ModelDiscoveryService."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.service = ModelDiscoveryService()
    
    @pytest.mark.asyncio
    async def test_get_available_models_openai(self):
        """Test get_available_models for OpenAI service."""
        with patch.object(self.service, '_get_openai_models', return_value=["gpt-4o", "gpt-3.5-turbo"]):
            models = await self.service.get_available_models(ServiceType.OPENAI, "test-key", "https://api.openai.com/v1")
            assert models == ["gpt-4o", "gpt-3.5-turbo"]
    
    @pytest.mark.asyncio
    async def test_get_available_models_anthropic(self):
        """Test get_available_models for Anthropic service."""
        models = await self.service.get_available_models(ServiceType.ANTHROPIC, "test-key", "https://api.anthropic.com")
        # Anthropic returns predefined models
        assert "claude-3-5-sonnet-20241022" in models
        assert "claude-3-opus-20240229" in models
    
    @pytest.mark.asyncio
    async def test_get_available_models_gemini(self):
        """Test get_available_models for Gemini service."""
        with patch.object(self.service, '_get_gemini_models', return_value=["gemini-1.5-pro", "gemini-1.5-flash"]):
            models = await self.service.get_available_models(ServiceType.GEMINI, "test-key", "https://generativelanguage.googleapis.com/v1")
            assert models == ["gemini-1.5-pro", "gemini-1.5-flash"]
    
    @pytest.mark.asyncio
    async def test_get_available_models_openrouter(self):
        """Test get_available_models for OpenRouter service."""
        with patch.object(self.service, '_get_openrouter_models', return_value=["openai/gpt-4o", "anthropic/claude-3.5-sonnet"]):
            models = await self.service.get_available_models(ServiceType.OPENROUTER, "test-key", "https://openrouter.ai/api/v1")
            assert models == ["openai/gpt-4o", "anthropic/claude-3.5-sonnet"]
    
    @pytest.mark.asyncio
    async def test_get_available_models_vscode_proxy(self):
        """Test get_available_models for VS Code LM Proxy service."""
        with patch.object(self.service, '_get_vscode_proxy_models', return_value=["vscode-lm-proxy", "copilot-chat"]):
            models = await self.service.get_available_models(ServiceType.VSCODE_PROXY, "", "http://localhost:3000")
            assert models == ["vscode-lm-proxy", "copilot-chat"]
    
    @pytest.mark.asyncio
    async def test_get_available_models_lmstudio(self):
        """Test get_available_models for LM Studio service."""
        with patch.object(self.service, '_get_lmstudio_models', return_value=["llama-3.1-8b-instruct"]):
            models = await self.service.get_available_models(ServiceType.LMSTUDIO, "", "http://127.0.0.1:1234/v1")
            assert models == ["llama-3.1-8b-instruct"]
    
    @pytest.mark.asyncio
    async def test_get_available_models_openai_compatible(self):
        """Test get_available_models for OpenAI-compatible service."""
        with patch.object(self.service, '_get_openai_compatible_models', return_value=["custom-model"]):
            models = await self.service.get_available_models(ServiceType.OPENAI_COMPATIBLE, "test-key", "https://custom-api.com/v1")
            assert models == ["custom-model"]
    
    @pytest.mark.asyncio
    async def test_get_available_models_none(self):
        """Test get_available_models for NONE service type."""
        models = await self.service.get_available_models(ServiceType.NONE, "", "")
        assert models == []
    
    @pytest.mark.asyncio
    async def test_get_available_models_exception_handling(self):
        """Test that exceptions are handled gracefully."""
        with patch.object(self.service, '_get_openai_models', side_effect=Exception("API Error")):
            models = await self.service.get_available_models(ServiceType.OPENAI, "test-key", "https://api.openai.com/v1")
            assert models == []
    
    def test_get_default_models_openai(self):
        """Test getting default models for OpenAI."""
        models = self.service.get_default_models(ServiceType.OPENAI)
        assert "gpt-4o" in models
        assert "gpt-4o-mini" in models
        assert "gpt-3.5-turbo" in models
    
    def test_get_default_models_anthropic(self):
        """Test getting default models for Anthropic."""
        models = self.service.get_default_models(ServiceType.ANTHROPIC)
        assert "claude-3-5-sonnet-20241022" in models
        assert "claude-3-opus-20240229" in models
    
    def test_get_default_models_gemini(self):
        """Test getting default models for Gemini."""
        models = self.service.get_default_models(ServiceType.GEMINI)
        assert "gemini-1.5-pro" in models
        assert "gemini-1.5-flash" in models
    
    def test_get_default_models_openrouter(self):
        """Test getting default models for OpenRouter."""
        models = self.service.get_default_models(ServiceType.OPENROUTER)
        assert "openai/gpt-4o" in models
        assert "anthropic/claude-3.5-sonnet" in models
    
    def test_get_default_models_vscode_proxy(self):
        """Test getting default models for VS Code LM Proxy."""
        models = self.service.get_default_models(ServiceType.VSCODE_PROXY)
        assert models == ["vscode-lm-proxy"]
    
    def test_get_default_models_lmstudio(self):
        """Test getting default models for LM Studio."""
        models = self.service.get_default_models(ServiceType.LMSTUDIO)
        assert models == ["local-model"]
    
    def test_get_default_models_openai_compatible(self):
        """Test getting default models for OpenAI-compatible."""
        models = self.service.get_default_models(ServiceType.OPENAI_COMPATIBLE)
        assert models == ["default-model"]
    
    def test_get_default_models_none(self):
        """Test getting default models for NONE service type."""
        models = self.service.get_default_models(ServiceType.NONE)
        assert models == []
    
    def test_get_default_models_unknown_service(self):
        """Test getting default models for unknown service type."""
        # Create a mock service type that doesn't exist in defaults
        models = self.service.get_default_models("unknown_service")
        assert models == []
    
    @pytest.mark.asyncio
    async def test_get_models_with_fallback_api_success(self):
        """Test get_models_with_fallback when API succeeds."""
        with patch.object(self.service, 'get_available_models', return_value=["api-model-1", "api-model-2"]):
            models = await self.service.get_models_with_fallback(ServiceType.OPENAI, "test-key", "https://api.openai.com/v1")
            assert models == ["api-model-1", "api-model-2"]
    
    @pytest.mark.asyncio
    async def test_get_models_with_fallback_api_failure(self):
        """Test get_models_with_fallback when API fails."""
        with patch.object(self.service, 'get_available_models', return_value=[]):
            models = await self.service.get_models_with_fallback(ServiceType.OPENAI, "test-key", "https://api.openai.com/v1")
            # Should return default models
            assert "gpt-4o" in models
            assert "gpt-3.5-turbo" in models
    
    @pytest.mark.asyncio
    async def test_anthropic_models_predefined(self):
        """Test that Anthropic models are predefined and don't require API call."""
        models = await self.service._get_anthropic_models("test-key", "https://api.anthropic.com")
        expected_models = [
            "claude-3-5-sonnet-20241022",
            "claude-3-5-haiku-20241022",
            "claude-3-opus-20240229",
            "claude-3-sonnet-20240229",
            "claude-3-haiku-20240307",
            "claude-2.1",
            "claude-2.0",
            "claude-instant-1.2"
        ]
        assert models == expected_models
    
    def test_timeout_configuration(self):
        """Test that timeout is properly configured."""
        assert self.service.timeout == 30
    
    @pytest.mark.asyncio
    async def test_service_type_routing(self):
        """Test that different service types are routed to correct methods."""
        # Mock all the individual service methods
        with patch.object(self.service, '_get_openai_models', return_value=["openai-model"]) as mock_openai, \
             patch.object(self.service, '_get_anthropic_models', return_value=["anthropic-model"]) as mock_anthropic, \
             patch.object(self.service, '_get_gemini_models', return_value=["gemini-model"]) as mock_gemini, \
             patch.object(self.service, '_get_openrouter_models', return_value=["openrouter-model"]) as mock_openrouter, \
             patch.object(self.service, '_get_vscode_proxy_models', return_value=["vscode-model"]) as mock_vscode, \
             patch.object(self.service, '_get_lmstudio_models', return_value=["lmstudio-model"]) as mock_lmstudio, \
             patch.object(self.service, '_get_openai_compatible_models', return_value=["compatible-model"]) as mock_compatible:
            
            # Test each service type
            await self.service.get_available_models(ServiceType.OPENAI, "key", "url")
            mock_openai.assert_called_once_with("key", "url")
            
            await self.service.get_available_models(ServiceType.ANTHROPIC, "key", "url")
            mock_anthropic.assert_called_once_with("key", "url")
            
            await self.service.get_available_models(ServiceType.GEMINI, "key", "url")
            mock_gemini.assert_called_once_with("key", "url")
            
            await self.service.get_available_models(ServiceType.OPENROUTER, "key", "url")
            mock_openrouter.assert_called_once_with("key", "url")
            
            await self.service.get_available_models(ServiceType.VSCODE_PROXY, "key", "url")
            mock_vscode.assert_called_once_with("url")
            
            await self.service.get_available_models(ServiceType.LMSTUDIO, "key", "url")
            mock_lmstudio.assert_called_once_with("url")
            
            await self.service.get_available_models(ServiceType.OPENAI_COMPATIBLE, "key", "url")
            mock_compatible.assert_called_once_with("key", "url")


if __name__ == "__main__":
    pytest.main([__file__])