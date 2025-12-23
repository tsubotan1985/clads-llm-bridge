"""LiteLLM proxy server for CLADS LLM Bridge."""

import asyncio
import json
import logging
from typing import Dict, Any, Optional
from datetime import datetime
import traceback

from fastapi import FastAPI, Request, Response, HTTPException
from fastapi.responses import JSONResponse, StreamingResponse
import uvicorn

from ..config.configuration_service import ConfigurationService
from ..monitoring.usage_tracker import UsageTracker
from .litellm_adapter import LiteLLMAdapter
from .vscode_adapter import VSCodeLMProxyAdapter
from .error_handler import ErrorHandler


logger = logging.getLogger(__name__)


class ProxyServer:
    """LiteLLM proxy server."""
    
    def __init__(self, config_service: ConfigurationService, port: int = 4321, endpoint_type: str = 'general'):
        """Initialize the proxy server.
        
        Args:
            config_service: Configuration service instance
            port: Port to run the server on
            endpoint_type: Type of endpoint ('general' for 4321, 'special' for 4333)
        """
        self.config_service = config_service
        self.port = port
        self.endpoint_type = endpoint_type
        self.adapter = LiteLLMAdapter(config_service)
        self.vscode_adapter = VSCodeLMProxyAdapter()
        self.usage_tracker = UsageTracker(config_service.db_path)
        self.error_handler = ErrorHandler()
        self.app = FastAPI(
            title=f"CLADS LLM Bridge Proxy ({endpoint_type.title()})",
            version="1.0.0"
        )
        
        # Setup routes
        self._setup_routes()
        
        # Configure logging
        logging.basicConfig(level=logging.INFO)
        logger.info(f"Proxy server initialized for endpoint type: {endpoint_type} on port {port}")
    
    def _filter_models_by_endpoint(self, configs: list) -> list:
        """Filter models based on endpoint type.
        
        Args:
            configs: List of LLM configurations
            
        Returns:
            Filtered list of configurations
        """
        if self.endpoint_type == 'general':
            # Port 4321: Only models with available_on_4321=True
            filtered = [c for c in configs if getattr(c, 'available_on_4321', True)]
            logger.debug(f"Filtered {len(filtered)}/{len(configs)} models for general endpoint (4321)")
            return filtered
        elif self.endpoint_type == 'special':
            # Port 4333: Only models with available_on_4333=True
            filtered = [c for c in configs if getattr(c, 'available_on_4333', True)]
            logger.debug(f"Filtered {len(filtered)}/{len(configs)} models for special endpoint (4333)")
            return filtered
        else:
            # Unknown endpoint type, return all
            logger.warning(f"Unknown endpoint type: {self.endpoint_type}, returning all models")
            return configs
        
    def _setup_routes(self):
        """Setup FastAPI routes."""
        
        @self.app.get("/health")
        async def health_check():
            """Health check endpoint."""
            return {"status": "ok", "timestamp": datetime.utcnow().isoformat()}
        
        @self.app.get("/health/services")
        async def service_health():
            """Service health status endpoint."""
            return self.error_handler.get_service_health_status()
        
        @self.app.post("/admin/reload")
        async def reload_configuration():
            """Reload configuration from database."""
            try:
                success = self.adapter.reload_configuration()
                if success:
                    logger.info("Configuration reloaded successfully from Web UI request")
                    return {
                        "status": "success",
                        "message": "Configuration reloaded successfully",
                        "timestamp": datetime.utcnow().isoformat()
                    }
                else:
                    logger.error("Failed to reload configuration from Web UI request")
                    return JSONResponse(
                        status_code=500,
                        content={
                            "status": "error",
                            "message": "Failed to reload configuration",
                            "timestamp": datetime.utcnow().isoformat()
                        }
                    )
            except Exception as e:
                logger.error(f"Error reloading configuration: {e}")
                return JSONResponse(
                    status_code=500,
                    content={
                        "status": "error",
                        "message": f"Error reloading configuration: {str(e)}",
                        "timestamp": datetime.utcnow().isoformat()
                    }
                )
        
        @self.app.get("/v1/models")
        async def list_models():
            """List available models."""
            try:
                model_mapping = self.adapter.get_model_mapping()
                models = []
                
                # Filter models based on endpoint type
                for model_key, config in model_mapping.items():
                    # Apply endpoint filter
                    if self.endpoint_type == 'general' and not getattr(config, 'available_on_4321', True):
                        continue
                    if self.endpoint_type == 'special' and not getattr(config, 'available_on_4333', True):
                        continue
                    
                    models.append({
                        "id": model_key,
                        "object": "model",
                        "created": int(config.created_at.timestamp()),
                        "owned_by": config.service_type.value,
                        "permission": [],
                        "root": model_key,
                        "parent": None
                    })
                
                logger.info(f"Listed {len(models)} models for {self.endpoint_type} endpoint (port {self.port})")
                
                return {
                    "object": "list",
                    "data": models
                }
                
            except Exception as e:
                logger.error(f"Error listing models: {e}")
                raise HTTPException(status_code=500, detail="Internal server error")
        
        @self.app.post("/v1/chat/completions")
        async def chat_completions(request: Request):
            """Handle chat completions requests."""
            try:
                # Parse request body
                body = await request.json()
                
                # Extract model name
                model_name = body.get("model")
                if not model_name:
                    raise self.error_handler.handle_request_validation_error("Model name is required")
                
                # Get configuration for model
                config = self.adapter.get_config_for_model(model_name)
                if not config:
                    raise self.error_handler.handle_request_validation_error(f"Model '{model_name}' not found")
                
                # Check endpoint availability
                if self.endpoint_type == 'general' and not getattr(config, 'available_on_4321', True):
                    logger.warning(f"Model '{model_name}' not available on general endpoint (4321)")
                    raise self.error_handler.handle_request_validation_error(
                        f"Model '{model_name}' is not available on this endpoint. Please use the special endpoint (4333)."
                    )
                elif self.endpoint_type == 'special' and not getattr(config, 'available_on_4333', True):
                    logger.warning(f"Model '{model_name}' not available on special endpoint (4333)")
                    raise self.error_handler.handle_request_validation_error(
                        f"Model '{model_name}' is not available on this endpoint."
                    )
                
                # Check service availability
                availability_error = self.error_handler.check_service_availability(config)
                if availability_error:
                    raise availability_error
                
                # Check if this is a VS Code LM Proxy request
                if await self.vscode_adapter.is_vscode_proxy_request(model_name, config):
                    return await self._handle_vscode_request(body, config, request)
                
                # Handle streaming vs non-streaming for regular LiteLLM
                stream = body.get("stream", False)
                
                if stream:
                    return await self._handle_streaming_request(body, config, request)
                else:
                    return await self._handle_non_streaming_request(body, config, request)
                    
            except HTTPException:
                raise
            except Exception as e:
                logger.error(f"Error in chat completions: {e}")
                logger.error(traceback.format_exc())
                raise self.error_handler.handle_service_error(config if 'config' in locals() else None, e)
        
        @self.app.post("/v1/completions")
        async def completions(request: Request):
            """Handle completions requests (legacy)."""
            try:
                # Parse request body
                body = await request.json()
                
                # Extract model name
                model_name = body.get("model")
                if not model_name:
                    raise self.error_handler.handle_request_validation_error("Model name is required")
                
                # Get configuration for model
                config = self.adapter.get_config_for_model(model_name)
                if not config:
                    raise self.error_handler.handle_request_validation_error(f"Model '{model_name}' not found")
                
                # Check service availability
                availability_error = self.error_handler.check_service_availability(config)
                if availability_error:
                    raise availability_error
                
                # Convert to chat format for consistency
                prompt = body.get("prompt", "")
                if isinstance(prompt, list):
                    prompt = "\n".join(prompt)
                
                chat_body = {
                    "model": model_name,
                    "messages": [{"role": "user", "content": prompt}],
                    "max_tokens": body.get("max_tokens"),
                    "temperature": body.get("temperature"),
                    "stream": body.get("stream", False)
                }
                
                # Remove None values
                chat_body = {k: v for k, v in chat_body.items() if v is not None}
                
                if chat_body["stream"]:
                    return await self._handle_streaming_request(chat_body, config, request)
                else:
                    return await self._handle_non_streaming_request(chat_body, config, request)
                    
            except HTTPException:
                raise
            except Exception as e:
                logger.error(f"Error in completions: {e}")
                logger.error(traceback.format_exc())
                raise HTTPException(status_code=500, detail="Internal server error")
    
    async def _handle_non_streaming_request(self, body: Dict[str, Any], config, request: Request) -> JSONResponse:
        """Handle non-streaming completion request.
        
        Args:
            body: Request body
            config: LLM configuration
            request: FastAPI request object
            
        Returns:
            JSON response
        """
        start_time = datetime.utcnow()
        response_dict = None
        status = "success"
        error_message = None
        
        try:
            # Import here to avoid circular imports
            import litellm
            
            # Prepare request for LiteLLM
            litellm_model = self.adapter._get_litellm_model_name(config)
            
            # Create completion request
            completion_kwargs = {
                "model": litellm_model,
                "messages": body["messages"],
            }
            
            # Add optional parameters
            if "max_tokens" in body:
                completion_kwargs["max_tokens"] = body["max_tokens"]
            if "temperature" in body:
                completion_kwargs["temperature"] = body["temperature"]
            if "top_p" in body:
                completion_kwargs["top_p"] = body["top_p"]
            
            # Add service-specific parameters
            if config.api_key:
                completion_kwargs["api_key"] = config.api_key
            if config.base_url and config.base_url != config.service_type.get_default_base_url():
                completion_kwargs["api_base"] = config.base_url
            
            # Make the completion request
            response = await litellm.acompletion(**completion_kwargs)
            
            # Transform response to use public name
            if hasattr(response, 'model') and config.public_name:
                response.model = config.public_name
            
            # Convert to dict for JSON response
            response_dict = response.dict() if hasattr(response, 'dict') else dict(response)
            
            # Ensure public name is used in response
            if config.public_name and "model" in response_dict:
                response_dict["model"] = config.public_name
            
            # Record success
            self.error_handler.record_success(config)
            
            return JSONResponse(content=response_dict)
            
        except Exception as e:
            status = "error"
            error_message = str(e)
            logger.error(f"Error in non-streaming request: {e}")
            logger.error(traceback.format_exc())
            raise self.error_handler.handle_service_error(config, e)
            
        finally:
            # Calculate response time and log usage
            end_time = datetime.utcnow()
            response_time_ms = int((end_time - start_time).total_seconds() * 1000)
            
            await self._log_usage(
                request, config, response_dict, 
                response_time_ms=response_time_ms,
                status=status,
                error_message=error_message
            )
    
    async def _handle_streaming_request(self, body: Dict[str, Any], config, request: Request):
        """Handle streaming completion request.
        
        Args:
            body: Request body
            config: LLM configuration
            request: FastAPI request object
            
        Returns:
            Streaming response
        """
        start_time = datetime.utcnow()
        status = "success"
        error_message = None
        total_tokens = 0
        
        try:
            # Import here to avoid circular imports
            import litellm
            
            # Prepare request for LiteLLM
            litellm_model = self.adapter._get_litellm_model_name(config)
            
            # Create completion request
            completion_kwargs = {
                "model": litellm_model,
                "messages": body["messages"],
                "stream": True
            }
            
            # Add optional parameters
            if "max_tokens" in body:
                completion_kwargs["max_tokens"] = body["max_tokens"]
            if "temperature" in body:
                completion_kwargs["temperature"] = body["temperature"]
            if "top_p" in body:
                completion_kwargs["top_p"] = body["top_p"]
            
            # Add service-specific parameters
            if config.api_key:
                completion_kwargs["api_key"] = config.api_key
            if config.base_url and config.base_url != config.service_type.get_default_base_url():
                completion_kwargs["api_base"] = config.base_url
            
            async def generate_stream():
                """Generate streaming response."""
                nonlocal status, error_message, total_tokens
                
                try:
                    response_stream = await litellm.acompletion(**completion_kwargs)
                    
                    async for chunk in response_stream:
                        # Transform chunk to use public name
                        if hasattr(chunk, 'model') and config.public_name:
                            chunk.model = config.public_name
                        
                        # Convert to dict and format as SSE
                        chunk_dict = chunk.dict() if hasattr(chunk, 'dict') else dict(chunk)
                        
                        # Ensure public name is used in chunk
                        if config.public_name and "model" in chunk_dict:
                            chunk_dict["model"] = config.public_name
                        
                        # Track token usage from final chunk
                        if "usage" in chunk_dict:
                            usage = chunk_dict["usage"]
                            total_tokens = usage.get("total_tokens", 0)
                        
                        chunk_json = json.dumps(chunk_dict)
                        yield f"data: {chunk_json}\n\n"
                    
                    # Send final chunk
                    yield "data: [DONE]\n\n"
                    
                except Exception as e:
                    status = "error"
                    error_message = str(e)
                    logger.error(f"Error in streaming: {e}")
                    error_chunk = {
                        "error": {
                            "message": str(e),
                            "type": "internal_error"
                        }
                    }
                    yield f"data: {json.dumps(error_chunk)}\n\n"
                
                finally:
                    # Log usage after streaming completes
                    end_time = datetime.utcnow()
                    response_time_ms = int((end_time - start_time).total_seconds() * 1000)
                    
                    # Create a mock response dict for logging
                    mock_response = {
                        "usage": {
                            "total_tokens": total_tokens,
                            "prompt_tokens": 0,  # Not available in streaming
                            "completion_tokens": total_tokens
                        }
                    } if total_tokens > 0 else {}
                    
                    await self._log_usage(
                        request, config, mock_response,
                        response_time_ms=response_time_ms,
                        status=status,
                        error_message=error_message
                    )
            
            return StreamingResponse(
                generate_stream(),
                media_type="text/plain",
                headers={
                    "Cache-Control": "no-cache",
                    "Connection": "keep-alive",
                    "Content-Type": "text/event-stream"
                }
            )
            
        except Exception as e:
            status = "error"
            error_message = str(e)
            logger.error(f"Error in streaming request: {e}")
            logger.error(traceback.format_exc())
            
            # Log error usage
            end_time = datetime.utcnow()
            response_time_ms = int((end_time - start_time).total_seconds() * 1000)
            await self._log_usage(
                request, config, {},
                response_time_ms=response_time_ms,
                status=status,
                error_message=error_message
            )
            
            raise HTTPException(status_code=500, detail=str(e))
    
    async def _handle_vscode_request(self, body: Dict[str, Any], config, request: Request):
        """Handle VS Code LM Proxy request.
        
        Args:
            body: Request body
            config: LLM configuration
            request: FastAPI request object
            
        Returns:
            Response (JSON or Streaming)
        """
        start_time = datetime.utcnow()
        response_dict = None
        status = "success"
        error_message = None
        
        try:
            client_ip = request.client.host if request.client else "unknown"
            
            # Check if streaming is requested
            stream = body.get("stream", False)
            
            if stream:
                # Handle streaming VS Code request
                async def generate_vscode_stream():
                    nonlocal status, error_message, response_dict
                    
                    try:
                        async for chunk in self.vscode_adapter.handle_vscode_proxy_streaming(body, config, client_ip):
                            yield chunk
                    except Exception as e:
                        status = "error"
                        error_message = str(e)
                        logger.error(f"VS Code streaming error: {e}")
                    finally:
                        # Log usage after streaming completes
                        end_time = datetime.utcnow()
                        response_time_ms = int((end_time - start_time).total_seconds() * 1000)
                        
                        await self._log_usage(
                            request, config, response_dict or {},
                            response_time_ms=response_time_ms,
                            status=status,
                            error_message=error_message
                        )
                
                return StreamingResponse(
                    generate_vscode_stream(),
                    media_type="text/plain",
                    headers={
                        "Cache-Control": "no-cache",
                        "Connection": "keep-alive",
                        "Content-Type": "text/event-stream"
                    }
                )
            else:
                # Handle non-streaming VS Code request
                response_dict = await self.vscode_adapter.handle_vscode_proxy_request(body, config, client_ip)
                
                # Record success
                self.error_handler.record_success(config)
                
                return JSONResponse(content=response_dict)
                
        except HTTPException:
            raise
        except Exception as e:
            status = "error"
            error_message = str(e)
            logger.error(f"Error in VS Code request: {e}")
            logger.error(traceback.format_exc())
            raise self.error_handler.handle_service_error(config, e)
            
        finally:
            # Log usage for non-streaming requests
            if not body.get("stream", False):
                end_time = datetime.utcnow()
                response_time_ms = int((end_time - start_time).total_seconds() * 1000)
                
                await self._log_usage(
                    request, config, response_dict or {},
                    response_time_ms=response_time_ms,
                    status=status,
                    error_message=error_message
                )
    
    async def _log_usage(self, request: Request, config, response: Dict[str, Any], response_time_ms: int = 0, status: str = "success", error_message: str = None):
        """Log usage data for monitoring.
        
        Args:
            request: FastAPI request object
            config: LLM configuration
            response: Response data
            response_time_ms: Response time in milliseconds
            status: Request status
            error_message: Error message if any
        """
        try:
            # Get client IP
            client_ip = request.client.host if request.client else "unknown"
            
            # Extract token usage from response
            input_tokens = 0
            output_tokens = 0
            
            if response and "usage" in response:
                usage = response["usage"]
                input_tokens = usage.get("prompt_tokens", 0)
                output_tokens = usage.get("completion_tokens", 0)
            
            # Log the usage
            self.usage_tracker.log_request(
                client_ip=client_ip,
                model_name=config.model_name,
                public_name=config.public_name or config.model_name,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                response_time_ms=response_time_ms,
                status=status,
                error_message=error_message
            )
            
        except Exception as e:
            logger.error(f"Error logging usage: {e}")
    
    def start_server(self):
        """Start the proxy server."""
        try:
            # Configure LiteLLM
            if not self.adapter.configure_litellm():
                logger.error("Failed to configure LiteLLM")
                return False
            
            logger.info(f"Starting proxy server on port {self.port}")
            
            # Run the server
            uvicorn.run(
                self.app,
                host="0.0.0.0",
                port=self.port,
                log_level="info"
            )
            
        except Exception as e:
            logger.error(f"Error starting proxy server: {e}")
            logger.exception("Full error details:")
            return False
    
    async def start_server_async(self):
        """Start the proxy server asynchronously."""
        try:
            # Configure LiteLLM
            if not self.adapter.configure_litellm():
                logger.error("Failed to configure LiteLLM")
                return False
            
            logger.info(f"Starting proxy server on port {self.port}")
            
            # Create server config
            config = uvicorn.Config(
                self.app,
                host="0.0.0.0",
                port=self.port,
                log_level="info",
                access_log=True
            )
            
            # Create and start server
            server = uvicorn.Server(config)
            logger.info(f"Proxy server configured successfully on 0.0.0.0:{self.port}")
            await server.serve()
            
        except Exception as e:
            logger.error(f"Error starting proxy server: {e}")
            logger.exception("Full error details:")
            return False
    
    def reload_configuration(self):
        """Reload configuration from database."""
        return self.adapter.reload_configuration()