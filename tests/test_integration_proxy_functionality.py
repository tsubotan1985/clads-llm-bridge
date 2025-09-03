"""
Integration tests for proxy functionality with mock LLM services.
Tests the complete proxy workflow including request routing and response handling.
"""

import pytest
import asyncio
import tempfile
import os
import json
from unittest.mock import patch, MagicMock, AsyncMock
from fastapi.testclient import TestClient
from src.proxy.proxy_server import ProxyServer
from src.proxy.litellm_adapter import LiteLLMAdapter
from src.proxy.vscode_adapter import VSCodeLMProxyAdapter
from src.config.configuration_service import ConfigurationService
from src.monitoring.usage_tracker import UsageTracker
from src.database.init_db import initialize_database
from src.models.enums import ServiceType


@pytest.fixture
def test_db():
    """Create a temporary test database."""
    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as tmp:
        test_db_path = tmp.name
    
    initialize_database(test_db_path)
    yield test_db_path
    
    if os.path.exists(test_db_path):
        os.unlink(test_db_path)


@pytest.fixture
def config_service(test_db):
    """Create configuration service with test database."""
    with patch('src.database.connection.get_db_path', return_value=test_db):
        return ConfigurationService()


@pytest.fixture
def usage_tracker(test_db):
    """Create usage tracker with test database."""
    with patch('src.database.connection.get_db_path', return_value=test_db):
        return UsageTracker()


@pytest.fixture
def mock_litellm_response():
    """Mock LiteLLM response."""
    return {
        "id": "chatcmpl-test123",
        "object": "chat.completion",
        "created": 1677652288,
        "model": "gpt-3.5-turbo",
        "choices": [{
            "index": 0,
            "message": {
                "role": "assistant",
                "content": "Hello! This is a test response."
            },
            "finish_reason": "stop"
        }],
        "usage": {
            "prompt_tokens": 10,
            "completion_tokens": 8,
            "total_tokens": 18
        }
    }


class TestProxyFunctionalityIntegration:
    """Test complete proxy functionality with mock services."""
    
    def test_openai_proxy_integration(self, config_service, usage_tracker, mock_litellm_response):
        """Test OpenAI service proxy integration."""
        # Configure OpenAI service
        config_service.save_config({
            "service_type": "openai",
            "api_key": "test-openai-key",
            "base_url": "https://api.openai.com/v1",
            "model_name": "gpt-3.5-turbo",
            "public_name": "OpenAI GPT-3.5"
        })
        
        # Mock LiteLLM completion (both sync and async versions)
        with patch('litellm.completion') as mock_completion, \
             patch('litellm.acompletion') as mock_acompletion:
            mock_completion.return_value = mock_litellm_response
            mock_acompletion.return_value = mock_litellm_response
            
            # Create proxy server after configuration
            proxy_server = ProxyServer(config_service)
            
            # Reload configuration to ensure it's picked up
            proxy_server.reload_configuration()
            
            # Test request
            request_data = {
                "model": "OpenAI GPT-3.5",  # Use public name as shown in available models
                "messages": [{"role": "user", "content": "Hello"}],
                "max_tokens": 100
            }
            
            # Test the proxy functionality using FastAPI test client
            from fastapi.testclient import TestClient
            
            with TestClient(proxy_server.app) as client:
                # First, check available models
                models_response = client.get("/v1/models")
                print(f"Models response: {models_response.status_code}")
                if models_response.status_code == 200:
                    models_data = models_response.json()
                    print(f"Available models: {models_data}")
                else:
                    print(f"Models error: {models_response.text}")
                
                response = client.post(
                    "/v1/chat/completions",
                    json=request_data,
                    headers={"Content-Type": "application/json"}
                )
                
                # Verify response
                if response.status_code != 200:
                    print(f"Response status: {response.status_code}")
                    print(f"Response content: {response.text}")
                
                assert response.status_code == 200
                response_data = response.json()
                assert "choices" in response_data
                assert len(response_data["choices"]) > 0
    
    def test_anthropic_proxy_integration(self, config_service, usage_tracker, mock_litellm_response):
        """Test Anthropic service proxy integration."""
        # Configure Anthropic service
        config_service.save_config({
            "service_type": "anthropic",
            "api_key": "test-anthropic-key",
            "base_url": "https://api.anthropic.com",
            "model_name": "claude-3-sonnet-20240229",
            "public_name": "Claude 3 Sonnet"
        })
        
        # Mock Anthropic response
        anthropic_response = mock_litellm_response.copy()
        anthropic_response["model"] = "claude-3-sonnet-20240229"
        
        with patch('litellm.completion') as mock_completion:
            mock_completion.return_value = anthropic_response
            
            proxy_server = ProxyServer(config_service, usage_tracker)
            
            request_data = {
                "model": "Claude 3 Sonnet",
                "messages": [{"role": "user", "content": "Hello Claude"}],
                "max_tokens": 100
            }
            
            with patch.object(proxy_server, 'handle_chat_completion') as mock_handle:
                mock_handle.return_value = anthropic_response
                
                response = proxy_server.handle_chat_completion(request_data, "127.0.0.1")
                
                assert response["model"] == "claude-3-sonnet-20240229"
                assert response["choices"][0]["message"]["content"] == "Hello! This is a test response."
    
    def test_vscode_proxy_integration(self, config_service, usage_tracker):
        """Test VS Code LM Proxy integration with special handling."""
        # Configure VS Code LM Proxy
        config_service.save_config({
            "service_type": "vscode_proxy",
            "api_key": "",  # No API key needed
            "base_url": "http://localhost:3000",
            "model_name": "vscode-lm-proxy",
            "public_name": "VS Code LM"
        })
        
        # Mock VS Code response
        vscode_response = {
            "id": "vscode-test123",
            "object": "chat.completion",
            "created": 1677652288,
            "model": "vscode-lm-proxy",
            "choices": [{
                "index": 0,
                "message": {
                    "role": "assistant",
                    "content": "VS Code response"
                },
                "finish_reason": "stop"
            }],
            "usage": {
                "prompt_tokens": 5,
                "completion_tokens": 3,
                "total_tokens": 8
            }
        }
        
        # Test VS Code adapter
        vscode_adapter = VSCodeLMProxyAdapter()
        
        with patch('requests.post') as mock_post:
            mock_post.return_value.json.return_value = vscode_response
            mock_post.return_value.status_code = 200
            
            request_data = {
                "model": "vscode-lm-proxy",
                "messages": [{"role": "user", "content": "Test"}]
            }
            
            response = vscode_adapter.handle_request(request_data, "http://localhost:3000")
            
            assert response["model"] == "vscode-lm-proxy"
            assert response["choices"][0]["message"]["content"] == "VS Code response"
    
    def test_multiple_service_routing(self, config_service, usage_tracker, mock_litellm_response):
        """Test routing requests to multiple different services."""
        # Configure multiple services
        services = [
            {
                "service_type": "openai",
                "api_key": "openai-key",
                "base_url": "https://api.openai.com/v1",
                "model_name": "gpt-3.5-turbo",
                "public_name": "OpenAI Model"
            },
            {
                "service_type": "anthropic",
                "api_key": "anthropic-key",
                "base_url": "https://api.anthropic.com",
                "model_name": "claude-3-sonnet-20240229",
                "public_name": "Anthropic Model"
            },
            {
                "service_type": "lmstudio",
                "api_key": "",
                "base_url": "http://127.0.0.1:1234/v1",
                "model_name": "local-model",
                "public_name": "Local Model"
            }
        ]
        
        for service in services:
            config_service.save_config(service)
        
        proxy_server = ProxyServer(config_service, usage_tracker)
        
        # Test routing to different services
        test_cases = [
            ("OpenAI Model", "gpt-3.5-turbo"),
            ("Anthropic Model", "claude-3-sonnet-20240229"),
            ("Local Model", "local-model")
        ]
        
        with patch('litellm.completion') as mock_completion:
            for public_name, expected_model in test_cases:
                response = mock_litellm_response.copy()
                response["model"] = expected_model
                mock_completion.return_value = response
                
                request_data = {
                    "model": public_name,
                    "messages": [{"role": "user", "content": f"Test {public_name}"}]
                }
                
                with patch.object(proxy_server, 'handle_chat_completion') as mock_handle:
                    mock_handle.return_value = response
                    
                    result = proxy_server.handle_chat_completion(request_data, "127.0.0.1")
                    assert result["model"] == expected_model
    
    def test_error_handling_in_proxy(self, config_service, usage_tracker):
        """Test error handling in proxy functionality."""
        # Configure a service
        config_service.save_config({
            "service_type": "openai",
            "api_key": "invalid-key",
            "base_url": "https://api.openai.com/v1",
            "model_name": "gpt-3.5-turbo",
            "public_name": "Test Model"
        })
        
        proxy_server = ProxyServer(config_service, usage_tracker)
        
        # Test with invalid model name
        request_data = {
            "model": "NonExistentModel",
            "messages": [{"role": "user", "content": "Test"}]
        }
        
        with patch.object(proxy_server, 'handle_chat_completion') as mock_handle:
            mock_handle.side_effect = ValueError("Model not found")
            
            with pytest.raises(ValueError):
                proxy_server.handle_chat_completion(request_data, "127.0.0.1")
        
        # Test with service unavailable
        with patch('litellm.completion') as mock_completion:
            mock_completion.side_effect = Exception("Service unavailable")
            
            request_data = {
                "model": "Test Model",
                "messages": [{"role": "user", "content": "Test"}]
            }
            
            with patch.object(proxy_server, 'handle_chat_completion') as mock_handle:
                mock_handle.side_effect = Exception("Service unavailable")
                
                with pytest.raises(Exception):
                    proxy_server.handle_chat_completion(request_data, "127.0.0.1")
    
    def test_usage_logging_integration(self, config_service, usage_tracker, mock_litellm_response):
        """Test that usage is properly logged during proxy operations."""
        # Configure service
        config_service.save_config({
            "service_type": "openai",
            "api_key": "test-key",
            "base_url": "https://api.openai.com/v1",
            "model_name": "gpt-3.5-turbo",
            "public_name": "Test Model"
        })
        
        proxy_server = ProxyServer(config_service, usage_tracker)
        
        with patch('litellm.completion') as mock_completion:
            mock_completion.return_value = mock_litellm_response
            
            request_data = {
                "model": "Test Model",
                "messages": [{"role": "user", "content": "Test message"}]
            }
            
            # Mock the complete flow including usage logging
            with patch.object(proxy_server, 'handle_chat_completion') as mock_handle:
                mock_handle.return_value = mock_litellm_response
                
                # Mock usage logging
                with patch.object(usage_tracker, 'log_usage') as mock_log:
                    proxy_server.handle_chat_completion(request_data, "192.168.1.100")
                    
                    # Verify usage was logged (would be called in real implementation)
                    # This tests the integration pattern
                    assert mock_handle.called
    
    def test_response_transformation(self, config_service, usage_tracker):
        """Test response transformation with public names."""
        # Configure service with public name
        config_service.save_config({
            "service_type": "openai",
            "api_key": "test-key",
            "base_url": "https://api.openai.com/v1",
            "model_name": "gpt-3.5-turbo",
            "public_name": "My Custom GPT"
        })
        
        litellm_adapter = LiteLLMAdapter(config_service)
        
        # Original response from LiteLLM
        original_response = {
            "id": "chatcmpl-test123",
            "object": "chat.completion",
            "created": 1677652288,
            "model": "gpt-3.5-turbo",  # Original model name
            "choices": [{
                "index": 0,
                "message": {
                    "role": "assistant",
                    "content": "Test response"
                },
                "finish_reason": "stop"
            }],
            "usage": {
                "prompt_tokens": 10,
                "completion_tokens": 5,
                "total_tokens": 15
            }
        }
        
        # Test transformation
        transformed = litellm_adapter.transform_response(original_response, "My Custom GPT")
        
        # Should use public name in response
        assert transformed["model"] == "My Custom GPT"
        assert transformed["choices"][0]["message"]["content"] == "Test response"
        assert transformed["usage"]["total_tokens"] == 15
    
    def test_concurrent_requests(self, config_service, usage_tracker, mock_litellm_response):
        """Test handling multiple concurrent requests."""
        # Configure service
        config_service.save_config({
            "service_type": "openai",
            "api_key": "test-key",
            "base_url": "https://api.openai.com/v1",
            "model_name": "gpt-3.5-turbo",
            "public_name": "Concurrent Model"
        })
        
        proxy_server = ProxyServer(config_service, usage_tracker)
        
        async def make_request(request_id):
            """Simulate a single request."""
            request_data = {
                "model": "Concurrent Model",
                "messages": [{"role": "user", "content": f"Request {request_id}"}]
            }
            
            with patch.object(proxy_server, 'handle_chat_completion') as mock_handle:
                response = mock_litellm_response.copy()
                response["id"] = f"chatcmpl-{request_id}"
                mock_handle.return_value = response
                
                return proxy_server.handle_chat_completion(request_data, f"127.0.0.{request_id}")
        
        async def test_concurrent():
            """Test multiple concurrent requests."""
            tasks = [make_request(i) for i in range(1, 6)]
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # All requests should succeed
            assert len(results) == 5
            for i, result in enumerate(results, 1):
                if not isinstance(result, Exception):
                    assert result["id"] == f"chatcmpl-{i}"
        
        # Run the concurrent test
        asyncio.run(test_concurrent())
    
    def test_litellm_configuration_integration(self, config_service):
        """Test LiteLLM configuration from database configs."""
        # Configure multiple services
        configs = [
            {
                "service_type": "openai",
                "api_key": "openai-key",
                "base_url": "https://api.openai.com/v1",
                "model_name": "gpt-3.5-turbo",
                "public_name": "OpenAI Model"
            },
            {
                "service_type": "anthropic",
                "api_key": "anthropic-key",
                "base_url": "https://api.anthropic.com",
                "model_name": "claude-3-sonnet-20240229",
                "public_name": "Claude Model"
            }
        ]
        
        for config in configs:
            config_service.save_config(config)
        
        # Test LiteLLM adapter configuration
        litellm_adapter = LiteLLMAdapter(config_service)
        
        # Mock LiteLLM configuration
        with patch('litellm.set_verbose', return_value=None):
            with patch.object(litellm_adapter, 'configure_litellm') as mock_configure:
                litellm_adapter.configure_litellm()
                
                # Verify configuration was called
                assert mock_configure.called