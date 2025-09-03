"""Error handlers for the web application."""

import traceback
import uuid
from typing import Dict, Any, Optional, Tuple
from datetime import datetime

from fastapi import Request, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from starlette.exceptions import HTTPException as StarletteHTTPException

from ..utils.logging_config import get_logger, get_error_logger
from ..utils.error_messages import error_messages, ErrorCategory


logger = get_logger(__name__)
error_logger = get_error_logger()


class WebErrorHandler:
    """Handle web application errors and render appropriate responses."""
    
    def __init__(self, templates: Jinja2Templates):
        """Initialize error handler.
        
        Args:
            templates: Jinja2Templates instance for rendering error pages
        """
        self.templates = templates
    
    def handle_404(self, request: Request, exc: HTTPException) -> HTMLResponse:
        """Handle 404 Not Found errors.
        
        Args:
            request: FastAPI request object
            exc: HTTP exception
            
        Returns:
            HTML response with 404 error page
        """
        logger.warning(f"404 Not Found: {request.url.path} from {request.client.host}")
        
        return self.templates.TemplateResponse(
            "error_404.html",
            {
                "request": request,
                "error_code": "404",
                "error_title": "Page Not Found",
                "requested_path": request.url.path
            },
            status_code=404
        )
    
    def handle_500(
        self,
        request: Request,
        exc: Exception,
        error_id: Optional[str] = None
    ) -> HTMLResponse:
        """Handle 500 Internal Server Error.
        
        Args:
            request: FastAPI request object
            exc: Exception that occurred
            error_id: Unique error ID for tracking
            
        Returns:
            HTML response with 500 error page
        """
        if not error_id:
            error_id = str(uuid.uuid4())[:8]
        
        # Log the error with full traceback
        error_logger.log_exception(
            exc,
            context=f"Web request error (ID: {error_id})",
            extra_data={
                "path": request.url.path,
                "method": request.method,
                "client_ip": request.client.host,
                "user_agent": request.headers.get("user-agent", "unknown")
            }
        )
        
        return self.templates.TemplateResponse(
            "error_500.html",
            {
                "request": request,
                "error_code": "500",
                "error_title": "Internal Server Error",
                "error_id": error_id
            },
            status_code=500
        )
    
    def handle_validation_error(
        self,
        request: Request,
        validation_result,
        form_data: Dict[str, Any],
        template_name: str,
        success_redirect: str = None
    ) -> HTMLResponse:
        """Handle form validation errors.
        
        Args:
            request: FastAPI request object
            validation_result: ValidationResult object
            form_data: Original form data
            template_name: Template to render
            success_redirect: URL to redirect on success
            
        Returns:
            HTML response with validation errors
        """
        from ..utils.error_messages import format_validation_errors, format_validation_warnings
        
        # Format errors and warnings for template
        field_errors = format_validation_errors(validation_result.errors)
        field_warnings = format_validation_warnings(validation_result.warnings)
        
        # Log validation errors
        for error in validation_result.errors:
            error_logger.log_validation_error(
                field=error.field,
                value=form_data.get(error.field, ""),
                error_message=error.message,
                form_type=template_name.replace('.html', '')
            )
        
        # Prepare template context
        context = {
            "request": request,
            "errors": field_errors,
            "warnings": field_warnings,
            "form_data": form_data,
            "validation_failed": True
        }
        
        # Add any additional context needed for specific templates
        if template_name == "config.html":
            context.update(self._get_config_template_context())
        
        return self.templates.TemplateResponse(
            template_name,
            context,
            status_code=400
        )
    
    def handle_api_error(
        self,
        request: Request,
        service_name: str,
        error_message: str,
        status_code: int = 500,
        error_code: str = None
    ) -> JSONResponse:
        """Handle API errors and return JSON response.
        
        Args:
            request: FastAPI request object
            service_name: Name of the service that failed
            error_message: Error message
            status_code: HTTP status code
            error_code: Specific error code
            
        Returns:
            JSON response with error details
        """
        error_id = str(uuid.uuid4())[:8]
        
        # Log the API error
        error_logger.log_api_error(
            service=service_name,
            endpoint=request.url.path,
            status_code=status_code,
            error_message=error_message,
            client_ip=request.client.host
        )
        
        # Format error message
        formatted_message = error_messages.format_api_error(
            service_name=service_name,
            error_message=error_message,
            error_code=error_code,
            status_code=status_code
        )
        
        return JSONResponse(
            content={
                "error": {
                    "message": formatted_message,
                    "service": service_name,
                    "code": error_code or "api_error",
                    "status_code": status_code,
                    "error_id": error_id,
                    "timestamp": datetime.utcnow().isoformat()
                }
            },
            status_code=status_code
        )
    
    def handle_configuration_error(
        self,
        request: Request,
        operation: str,
        error_message: str,
        config_id: str = None,
        service_type: str = None
    ) -> HTMLResponse:
        """Handle configuration-related errors.
        
        Args:
            request: FastAPI request object
            operation: Operation that failed
            error_message: Error message
            config_id: Configuration ID (if applicable)
            service_type: Service type (if applicable)
            
        Returns:
            HTML response with error page
        """
        error_id = str(uuid.uuid4())[:8]
        
        # Log configuration error
        error_logger.log_configuration_error(
            config_id=config_id or "unknown",
            service_type=service_type or "unknown",
            error_message=error_message,
            operation=operation
        )
        
        # Determine suggestions based on operation
        suggestions = self._get_configuration_suggestions(operation, error_message)
        
        return self.templates.TemplateResponse(
            "error.html",
            {
                "request": request,
                "error_title": f"Configuration {operation.title()} Failed",
                "error_message": error_message,
                "error_code": error_id,
                "error_details": f"Failed to {operation} configuration",
                "suggestions": suggestions,
                "back_url": "/config",
                "retry_url": "/config" if operation != "delete" else None,
                "contact_support": True
            },
            status_code=500
        )
    
    def handle_authentication_error(
        self,
        request: Request,
        error_type: str = "invalid_credentials"
    ) -> HTMLResponse:
        """Handle authentication errors.
        
        Args:
            request: FastAPI request object
            error_type: Type of authentication error
            
        Returns:
            HTML response with login page and error
        """
        error_message = error_messages.get_error_message(
            error_type,
            ErrorCategory.AUTHENTICATION
        )
        
        logger.warning(f"Authentication failed from {request.client.host}: {error_type}")
        
        return self.templates.TemplateResponse(
            "login.html",
            {
                "request": request,
                "error": error_message,
                "error_type": error_type
            },
            status_code=401
        )
    
    def _get_config_template_context(self) -> Dict[str, Any]:
        """Get additional context for configuration template.
        
        Returns:
            Dictionary with template context
        """
        try:
            from ..config.configuration_service import ConfigurationService
            from ..models.enums import ServiceType
            
            config_service = ConfigurationService()
            configs = config_service.get_llm_configs()
            
            # Create separate data for JavaScript (JSON serializable)
            configs_for_js = []
            for config in configs:
                config_dict = {
                    "id": config.id,
                    "service_type": config.service_type.value,
                    "base_url": config.base_url,
                    "api_key": "***" if config.api_key else "",
                    "model_name": config.model_name,
                    "public_name": config.public_name,
                    "enabled": config.enabled,
                    "created_at": config.created_at.isoformat() if config.created_at else None,
                    "updated_at": config.updated_at.isoformat() if config.updated_at else None
                }
                configs_for_js.append(config_dict)
            
            return {
                "configs": configs,  # Original objects for template
                "configs_js": configs_for_js,  # Serializable data for JavaScript
                "service_types": [
                    {"value": st.value, "name": st.value.replace("_", " ").title()}
                    for st in ServiceType
                ],
                "default_base_urls": ServiceType.get_default_base_urls()
            }
        except Exception as e:
            logger.error(f"Failed to get config template context: {e}")
            return {
                "configs": [],
                "configs_js": [],  # Add empty list for JS data
                "service_types": [],
                "default_base_urls": {}
            }
    
    def _get_configuration_suggestions(
        self,
        operation: str,
        error_message: str
    ) -> list:
        """Get suggestions for configuration errors.
        
        Args:
            operation: Operation that failed
            error_message: Error message
            
        Returns:
            List of suggestion strings
        """
        suggestions = []
        
        if operation == "save":
            suggestions.extend([
                "Check that all required fields are filled out correctly",
                "Verify that your API key is valid and has the correct permissions",
                "Ensure the base URL is accessible and correct",
                "Try testing the configuration before saving"
            ])
            
            if "api key" in error_message.lower():
                suggestions.append("Double-check your API key in the service provider's dashboard")
            
            if "url" in error_message.lower():
                suggestions.append("Verify the base URL format and ensure it's reachable")
        
        elif operation == "test":
            suggestions.extend([
                "Check your internet connection",
                "Verify that the service is not experiencing downtime",
                "Ensure your API key has the necessary permissions",
                "Try again in a few moments"
            ])
        
        elif operation == "delete":
            suggestions.extend([
                "Refresh the page and try again",
                "Check if the configuration is currently in use",
                "Ensure you have the necessary permissions"
            ])
        
        elif operation == "load_models":
            suggestions.extend([
                "Check your API key and permissions",
                "Verify the service is accessible",
                "Try using default models if available",
                "Check the service documentation for model availability"
            ])
        
        return suggestions


def create_error_handlers(app, templates: Jinja2Templates) -> WebErrorHandler:
    """Create and register error handlers for the FastAPI app.
    
    Args:
        app: FastAPI application instance
        templates: Jinja2Templates instance
        
    Returns:
        WebErrorHandler instance
    """
    error_handler = WebErrorHandler(templates)
    
    @app.exception_handler(404)
    async def not_found_handler(request: Request, exc: HTTPException):
        return error_handler.handle_404(request, exc)
    
    @app.exception_handler(500)
    async def internal_error_handler(request: Request, exc: Exception):
        return error_handler.handle_500(request, exc)
    
    @app.exception_handler(StarletteHTTPException)
    async def http_exception_handler(request: Request, exc: StarletteHTTPException):
        if exc.status_code == 404:
            return error_handler.handle_404(request, exc)
        elif exc.status_code == 500:
            return error_handler.handle_500(request, exc)
        else:
            # For other HTTP exceptions, return JSON if it's an API request
            if request.url.path.startswith('/api/'):
                return JSONResponse(
                    content={
                        "error": {
                            "message": exc.detail,
                            "status_code": exc.status_code,
                            "timestamp": datetime.utcnow().isoformat()
                        }
                    },
                    status_code=exc.status_code
                )
            else:
                # Return generic error page for web requests
                return error_handler.templates.TemplateResponse(
                    "error.html",
                    {
                        "request": request,
                        "error_title": f"Error {exc.status_code}",
                        "error_message": exc.detail,
                        "error_code": str(exc.status_code),
                        "back_url": "/",
                        "contact_support": exc.status_code >= 500
                    },
                    status_code=exc.status_code
                )
    
    return error_handler