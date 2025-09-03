"""LiteLLM adapter for CLADS LLM Bridge."""

import asyncio
import json
import logging
from typing import Dict, List, Optional, Any
from datetime import datetime

import litellm
from litellm import completion, acompletion
from litellm.utils import ModelResponse

from ..models.llm_config import LLMConfig
from ..models.enums import ServiceType
from ..config.configuration_service import ConfigurationService


logger = logging.getLogger(__name__)


class LiteLLMAdapter:
    """Adapter for LiteLLM proxy functionality."""
    
    def __init__(self, config_service: ConfigurationService):
        """Initialize the LiteLLM adapter.
        
        Args:
            config_service: Configuration service instance
        """
        self.config_service = config_service
        self._model_mapping: Dict[str, LLMConfig] = {}
        self._litellm_config: Dict[str, Any] = {}
        
        # Configure LiteLLM logging
        litellm.set_verbose = False
        litellm.suppress_debug_info = True
        
    def configure_litellm(self) -> bool:
        """Configure LiteLLM with current database configurations.
        
        Returns:
            True if configuration successful, False otherwise
        """
        try:
            # Get enabled configurations
            configs = self.config_service.get_enabled_configs()
            
            if not configs:
                logger.warning("No enabled LLM configurations found")
                return False
            
            # Clear existing mappings
            self._model_mapping.clear()
            
            # Build model list for LiteLLM
            model_list = []
            
            for config in configs:
                if config.service_type == ServiceType.NONE:
                    continue
                
                # Store mapping for all configs (including VS Code LM Proxy)
                model_key = self._get_model_key(config)
                self._model_mapping[model_key] = config
                
                # Skip VS Code LM Proxy for LiteLLM configuration (handled separately)
                if config.service_type == ServiceType.VSCODE_PROXY:
                    continue
                
                # Create model entry for LiteLLM
                model_entry = self._create_model_entry(config)
                if model_entry:
                    model_list.append(model_entry)
            
            if not model_list:
                logger.warning("No valid model configurations found")
                return False
            
            # Configure LiteLLM
            self._litellm_config = {
                "model_list": model_list,
                "general_settings": {
                    "completion_model": "gpt-3.5-turbo",  # Default fallback
                    "disable_spend_logs": True,
                    "disable_master_key_return": True
                }
            }
            
            # Set LiteLLM configuration
            litellm.model_list = model_list
            
            logger.info(f"Configured LiteLLM with {len(model_list)} models")
            return True
            
        except Exception as e:
            logger.error(f"Error configuring LiteLLM: {e}")
            return False
    
    def _create_model_entry(self, config: LLMConfig) -> Optional[Dict[str, Any]]:
        """Create a model entry for LiteLLM configuration.
        
        Args:
            config: LLM configuration
            
        Returns:
            Model entry dictionary or None if invalid
        """
        try:
            model_key = self._get_model_key(config)
            
            # Base model entry
            model_entry = {
                "model_name": model_key,
                "litellm_params": {
                    "model": self._get_litellm_model_name(config),
                }
            }
            
            # Add service-specific parameters
            if config.service_type == ServiceType.OPENAI:
                model_entry["litellm_params"]["api_key"] = config.api_key
                if config.base_url != "https://api.openai.com/v1":
                    model_entry["litellm_params"]["api_base"] = config.base_url
                    
            elif config.service_type == ServiceType.ANTHROPIC:
                model_entry["litellm_params"]["api_key"] = config.api_key
                
            elif config.service_type == ServiceType.GEMINI:
                model_entry["litellm_params"]["api_key"] = config.api_key
                
            elif config.service_type == ServiceType.OPENROUTER:
                model_entry["litellm_params"]["api_key"] = config.api_key
                model_entry["litellm_params"]["api_base"] = config.base_url
                
            elif config.service_type == ServiceType.VSCODE_PROXY:
                # VS Code LM Proxy doesn't need API key
                model_entry["litellm_params"]["api_base"] = config.base_url
                
            elif config.service_type == ServiceType.LMSTUDIO:
                # LM Studio doesn't need API key
                model_entry["litellm_params"]["api_base"] = config.base_url
                
            elif config.service_type == ServiceType.OPENAI_COMPATIBLE:
                model_entry["litellm_params"]["api_key"] = config.api_key
                model_entry["litellm_params"]["api_base"] = config.base_url
            
            return model_entry
            
        except Exception as e:
            logger.error(f"Error creating model entry for {config.id}: {e}")
            return None
    
    def _get_model_key(self, config: LLMConfig) -> str:
        """Get the model key for LiteLLM.
        
        Args:
            config: LLM configuration
            
        Returns:
            Model key string
        """
        # Use public name if available, otherwise use model name
        return config.public_name or config.model_name or f"{config.service_type.value}_{config.id[:8]}"
    
    def _get_litellm_model_name(self, config: LLMConfig) -> str:
        """Get the LiteLLM model name for the configuration.
        
        Args:
            config: LLM configuration
            
        Returns:
            LiteLLM model name
        """
        # Special handling for VS Code LM Proxy - don't use LiteLLM for this
        if config.service_type == ServiceType.VSCODE_PROXY:
            return "vscode-lm-proxy"
        
        model_name = config.model_name
        
        # Special handling for specific services
        if config.service_type == ServiceType.ANTHROPIC:
            # Ensure Claude models have proper prefix
            if not model_name.startswith("claude-"):
                model_name = f"claude-{model_name}"
            return model_name
        elif config.service_type == ServiceType.GEMINI:
            # Debug logging for Gemini model name transformation
            logger.info(f"DEBUG: Processing Gemini model - input model_name: '{model_name}'")
            
            # Ensure Gemini models have proper prefix for Google AI Studio
            if model_name.startswith("gemini/"):
                # Already has correct format
                logger.info(f"DEBUG: Model already has gemini/ prefix, returning: '{model_name}'")
                return model_name
            
            # Construct proper Gemini model name: gemini/{original_model_name}
            # LiteLLM expects format like gemini/gemini-2.0-flash-exp
            full_model_name = f"gemini/{model_name}"
            logger.info(f"DEBUG: Final Gemini model name: '{full_model_name}'")
            return full_model_name
        
        # Map service types to LiteLLM model prefixes for other services
        service_prefixes = {
            ServiceType.OPENAI: "",  # No prefix for OpenAI
            ServiceType.OPENROUTER: "openrouter/",
            ServiceType.LMSTUDIO: "openai/",  # Treat as OpenAI-compatible
            ServiceType.OPENAI_COMPATIBLE: "openai/"
        }
        
        prefix = service_prefixes.get(config.service_type, "")
        return f"{prefix}{model_name}"
    
    def get_model_mapping(self) -> Dict[str, LLMConfig]:
        """Get the current model mapping.
        
        Returns:
            Dictionary mapping model keys to configurations
        """
        return self._model_mapping.copy()
    
    def get_config_for_model(self, model_name: str) -> Optional[LLMConfig]:
        """Get configuration for a model name.
        
        Args:
            model_name: Model name from request
            
        Returns:
            LLMConfig or None if not found
        """
        return self._model_mapping.get(model_name)
    
    def reload_configuration(self) -> bool:
        """Reload configuration from database.
        
        Returns:
            True if reload successful, False otherwise
        """
        return self.configure_litellm()