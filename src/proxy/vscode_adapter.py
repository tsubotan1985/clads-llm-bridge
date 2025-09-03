"""VS Code LM Proxy adapter for CLADS LLM Bridge."""

import json
import logging
from typing import Dict, Any, Optional, AsyncGenerator
from datetime import datetime

import httpx
from fastapi import HTTPException
from fastapi.responses import JSONResponse, StreamingResponse

from ..models.llm_config import LLMConfig
from ..models.enums import ServiceType


logger = logging.getLogger(__name__)


class VSCodeLMProxyAdapter:
    """Adapter for VS Code LM Proxy special handling."""
    
    def __init__(self):
        """Initialize the VS Code LM Proxy adapter."""
        self.client = httpx.AsyncClient(timeout=30.0)
    
    async def is_vscode_proxy_request(self, model_name: str, config: LLMConfig) -> bool:
        """Check if this is a VS Code LM Proxy request.
        
        Args:
            model_name: Model name from request
            config: LLM configuration
            
        Returns:
            True if this is a VS Code LM Proxy request
        """
        return (
            config.service_type == ServiceType.VSCODE_PROXY or
            model_name == "vscode-lm-proxy"
        )
    
    async def handle_vscode_proxy_request(
        self,
        body: Dict[str, Any],
        config: LLMConfig,
        client_ip: str
    ) -> Dict[str, Any]:
        """Handle VS Code LM Proxy request.
        
        Args:
            body: Request body
            config: LLM configuration
            client_ip: Client IP address
            
        Returns:
            Response dictionary
        """
        try:
            # Prepare request for VS Code LM Proxy
            vscode_body = body.copy()
            
            # Handle special model name
            if body.get("model") == "vscode-lm-proxy":
                # Use the default model selected in VS Code
                vscode_body["model"] = "vscode-lm-proxy"
            else:
                # Use the specific model name
                vscode_body["model"] = body.get("model", "vscode-lm-proxy")
            
            # Make request to VS Code LM Proxy
            url = f"{config.base_url}/v1/chat/completions"
            
            response = await self.client.post(
                url,
                json=vscode_body,
                headers={"Content-Type": "application/json"}
            )
            
            if response.status_code != 200:
                error_text = await response.aread()
                logger.error(f"VS Code LM Proxy error: {response.status_code} - {error_text}")
                raise HTTPException(
                    status_code=response.status_code,
                    detail=f"VS Code LM Proxy error: {error_text.decode()}"
                )
            
            response_data = response.json()
            
            # Transform response to use public name
            if config.public_name and "model" in response_data:
                response_data["model"] = config.public_name
            
            return response_data
                
        except httpx.RequestError as e:
            logger.error(f"VS Code LM Proxy connection error: {e}")
            raise HTTPException(
                status_code=503,
                detail=f"VS Code LM Proxy unavailable: {str(e)}"
            )
        except Exception as e:
            logger.error(f"VS Code LM Proxy error: {e}")
            raise HTTPException(
                status_code=500,
                detail=f"VS Code LM Proxy error: {str(e)}"
            )
    
    async def handle_vscode_proxy_streaming(
        self,
        body: Dict[str, Any],
        config: LLMConfig,
        client_ip: str
    ) -> AsyncGenerator[str, None]:
        """Handle VS Code LM Proxy streaming request.
        
        Args:
            body: Request body
            config: LLM configuration
            client_ip: Client IP address
            
        Yields:
            Server-sent event strings
        """
        try:
            # Prepare request for VS Code LM Proxy
            vscode_body = body.copy()
            vscode_body["stream"] = True
            
            # Handle special model name
            if body.get("model") == "vscode-lm-proxy":
                vscode_body["model"] = "vscode-lm-proxy"
            else:
                vscode_body["model"] = body.get("model", "vscode-lm-proxy")
            
            # Make streaming request to VS Code LM Proxy
            url = f"{config.base_url}/v1/chat/completions"
            
            async with self.client.stream(
                "POST",
                url,
                json=vscode_body,
                headers={"Content-Type": "application/json"}
            ) as response:
                
                if response.status_code != 200:
                    error_text = await response.aread()
                    logger.error(f"VS Code LM Proxy streaming error: {response.status_code} - {error_text}")
                    error_chunk = {
                        "error": {
                            "message": f"VS Code LM Proxy error: {error_text.decode()}",
                            "type": "vscode_proxy_error"
                        }
                    }
                    yield f"data: {json.dumps(error_chunk)}\n\n"
                    return
                
                # Stream the response
                async for line in response.aiter_lines():
                    if line.startswith("data: "):
                        data_part = line[6:]  # Remove "data: " prefix
                        
                        if data_part == "[DONE]":
                            yield f"data: [DONE]\n\n"
                            break
                        
                        try:
                            # Parse and transform the chunk
                            chunk_data = json.loads(data_part)
                            
                            # Transform to use public name
                            if config.public_name and "model" in chunk_data:
                                chunk_data["model"] = config.public_name
                            
                            yield f"data: {json.dumps(chunk_data)}\n\n"
                            
                        except json.JSONDecodeError:
                            # Pass through non-JSON lines
                            yield f"data: {data_part}\n\n"
                
        except httpx.RequestError as e:
            logger.error(f"VS Code LM Proxy streaming connection error: {e}")
            error_chunk = {
                "error": {
                    "message": f"VS Code LM Proxy unavailable: {str(e)}",
                    "type": "connection_error"
                }
            }
            yield f"data: {json.dumps(error_chunk)}\n\n"
        except Exception as e:
            logger.error(f"VS Code LM Proxy streaming error: {e}")
            error_chunk = {
                "error": {
                    "message": f"VS Code LM Proxy error: {str(e)}",
                    "type": "internal_error"
                }
            }
            yield f"data: {json.dumps(error_chunk)}\n\n"
    
    async def get_vscode_models(self, config: LLMConfig) -> Dict[str, Any]:
        """Get available models from VS Code LM Proxy.
        
        Args:
            config: VS Code LM Proxy configuration
            
        Returns:
            Models list response
        """
        try:
            url = f"{config.base_url}/v1/models"
            
            response = await self.client.get(url)
            
            if response.status_code != 200:
                error_text = await response.aread()
                logger.error(f"VS Code LM Proxy models error: {response.status_code} - {error_text}")
                return {
                    "object": "list",
                    "data": []
                }
            
            return response.json()
                
        except Exception as e:
            logger.error(f"Error getting VS Code models: {e}")
            return {
                "object": "list",
                "data": []
            }
    
    async def test_vscode_connection(self, config: LLMConfig) -> bool:
        """Test connection to VS Code LM Proxy.
        
        Args:
            config: VS Code LM Proxy configuration
            
        Returns:
            True if connection successful, False otherwise
        """
        try:
            models = await self.get_vscode_models(config)
            return "data" in models and isinstance(models["data"], list)
        except Exception as e:
            logger.error(f"VS Code LM Proxy connection test failed: {e}")
            return False
    
    async def close(self):
        """Close the HTTP client."""
        await self.client.aclose()