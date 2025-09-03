"""Model discovery service for LLM configurations."""

import asyncio
import aiohttp
from typing import List, Dict, Optional
from datetime import datetime

from ..models.llm_config import LLMConfig
from ..models.enums import ServiceType


class ModelDiscoveryService:
    """Service for discovering available models from LLM services."""
    
    def __init__(self):
        """Initialize the model discovery service."""
        self.timeout = 30  # 30 seconds timeout for API calls
    
    async def get_available_models(self, service_type: ServiceType, api_key: str, base_url: str) -> List[str]:
        """Get available models for a service.
        
        Args:
            service_type: The type of LLM service
            api_key: API key for authentication
            base_url: Base URL for the service
            
        Returns:
            List of model names
        """
        try:
            if service_type == ServiceType.OPENAI:
                return await self._get_openai_models(api_key, base_url)
            elif service_type == ServiceType.ANTHROPIC:
                return await self._get_anthropic_models(api_key, base_url)
            elif service_type == ServiceType.GEMINI:
                return await self._get_gemini_models(api_key, base_url)
            elif service_type == ServiceType.OPENROUTER:
                return await self._get_openrouter_models(api_key, base_url)
            elif service_type == ServiceType.VSCODE_PROXY:
                return await self._get_vscode_proxy_models(base_url)
            elif service_type == ServiceType.LMSTUDIO:
                return await self._get_lmstudio_models(base_url)
            elif service_type == ServiceType.OPENAI_COMPATIBLE:
                return await self._get_openai_compatible_models(api_key, base_url)
            elif service_type == ServiceType.NONE:
                return []
            else:
                return []
        except Exception as e:
            print(f"Error getting models for {service_type}: {e}")
            return []
    
    async def _get_openai_models(self, api_key: str, base_url: str) -> List[str]:
        """Get OpenAI models."""
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
        
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=self.timeout)) as session:
            async with session.get(f"{base_url}/models", headers=headers) as response:
                if response.status == 200:
                    data = await response.json()
                    models = [model["id"] for model in data.get("data", [])]
                    return sorted(models)
                else:
                    return []
    
    async def _get_anthropic_models(self, api_key: str, base_url: str) -> List[str]:
        """Get Anthropic models."""
        # Anthropic doesn't have a models endpoint, so we return known models
        return [
            "claude-3-5-sonnet-20241022",
            "claude-3-5-haiku-20241022",
            "claude-3-opus-20240229",
            "claude-3-sonnet-20240229",
            "claude-3-haiku-20240307",
            "claude-2.1",
            "claude-2.0",
            "claude-instant-1.2"
        ]
    
    async def _get_gemini_models(self, api_key: str, base_url: str) -> List[str]:
        """Get Google AI Studio (Gemini) models."""
        url = f"{base_url}/models?key={api_key}"
        
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=self.timeout)) as session:
            async with session.get(url) as response:
                if response.status == 200:
                    data = await response.json()
                    models = []
                    for model in data.get("models", []):
                        # Extract model name from full path
                        model_name = model.get("name", "").split("/")[-1]
                        if model_name and "generateContent" in model.get("supportedGenerationMethods", []):
                            models.append(model_name)
                    return sorted(models)
                else:
                    return []
    
    async def _get_openrouter_models(self, api_key: str, base_url: str) -> List[str]:
        """Get OpenRouter models."""
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
        
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=self.timeout)) as session:
            async with session.get(f"{base_url}/models", headers=headers) as response:
                if response.status == 200:
                    data = await response.json()
                    models = [model["id"] for model in data.get("data", [])]
                    return sorted(models)
                else:
                    return []
    
    async def _get_vscode_proxy_models(self, base_url: str) -> List[str]:
        """Get VS Code LM Proxy models."""
        # VS Code LM Proxy doesn't require authentication
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=self.timeout)) as session:
            async with session.get(f"{base_url}/v1/models") as response:
                if response.status == 200:
                    data = await response.json()
                    models = [model["id"] for model in data.get("data", [])]
                    return sorted(models)
                else:
                    return []
    
    async def _get_lmstudio_models(self, base_url: str) -> List[str]:
        """Get LM Studio models."""
        # LM Studio uses OpenAI-compatible API without authentication
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=self.timeout)) as session:
            async with session.get(f"{base_url}/models") as response:
                if response.status == 200:
                    data = await response.json()
                    models = [model["id"] for model in data.get("data", [])]
                    return sorted(models)
                else:
                    return []
    
    async def _get_openai_compatible_models(self, api_key: str, base_url: str) -> List[str]:
        """Get OpenAI-compatible API models."""
        headers = {}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"
        headers["Content-Type"] = "application/json"
        
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=self.timeout)) as session:
            async with session.get(f"{base_url}/models", headers=headers) as response:
                if response.status == 200:
                    data = await response.json()
                    models = [model["id"] for model in data.get("data", [])]
                    return sorted(models)
                else:
                    return []
    
    def get_default_models(self, service_type: ServiceType) -> List[str]:
        """Get default/known models for a service type when API is not available.
        
        Args:
            service_type: The type of LLM service
            
        Returns:
            List of default model names
        """
        defaults = {
            ServiceType.OPENAI: [
                "gpt-4o",
                "gpt-4o-mini",
                "gpt-4-turbo",
                "gpt-4",
                "gpt-3.5-turbo",
                "gpt-3.5-turbo-16k"
            ],
            ServiceType.ANTHROPIC: [
                "claude-3-5-sonnet-20241022",
                "claude-3-5-haiku-20241022",
                "claude-3-opus-20240229",
                "claude-3-sonnet-20240229",
                "claude-3-haiku-20240307",
                "claude-2.1",
                "claude-2.0",
                "claude-instant-1.2"
            ],
            ServiceType.GEMINI: [
                "gemini-1.5-pro",
                "gemini-1.5-flash",
                "gemini-1.0-pro",
                "gemini-pro-vision"
            ],
            ServiceType.OPENROUTER: [
                "openai/gpt-4o",
                "openai/gpt-4o-mini",
                "anthropic/claude-3.5-sonnet",
                "google/gemini-pro",
                "meta-llama/llama-3.1-405b-instruct"
            ],
            ServiceType.VSCODE_PROXY: [
                "vscode-lm-proxy"
            ],
            ServiceType.LMSTUDIO: [
                "local-model"
            ],
            ServiceType.OPENAI_COMPATIBLE: [
                "default-model"
            ],
            ServiceType.NONE: []
        }
        
        return defaults.get(service_type, [])
    
    async def get_models_with_fallback(self, service_type: ServiceType, api_key: str, base_url: str) -> List[str]:
        """Get models with fallback to defaults if API fails.
        
        Args:
            service_type: The type of LLM service
            api_key: API key for authentication
            base_url: Base URL for the service
            
        Returns:
            List of model names (from API or defaults)
        """
        # Try to get models from API
        models = await self.get_available_models(service_type, api_key, base_url)
        
        # If API fails, return defaults
        if not models:
            models = self.get_default_models(service_type)
        
        return models