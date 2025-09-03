"""FastAPI web application for configuration UI."""

from fastapi import FastAPI, Request, Form, Depends, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware
import os
import time
from pathlib import Path

from ..auth.authentication_service import AuthenticationService
from ..auth.middleware import AuthMiddleware, SessionManager
from ..database.connection import DatabaseConnection
from ..config.configuration_service import ConfigurationService
from ..config.health_service import HealthService
from ..config.model_discovery_service import ModelDiscoveryService
from ..monitoring.usage_tracker import UsageTracker, TimePeriod
from ..models.enums import ServiceType
from ..validation.form_validators import validate_config_form_data, validate_auth_form_data
from ..utils.logging_config import setup_logging, get_logger, get_request_logger, get_error_logger
from ..utils.error_messages import error_messages, ErrorCategory
from .error_handlers import create_error_handlers


class WebApp:
    """FastAPI web application for configuration UI."""
    
    def __init__(self):
        """Initialize web application."""
        # Setup logging first
        setup_logging()
        self.logger = get_logger(__name__)
        self.request_logger = get_request_logger()
        self.error_logger = get_error_logger()
        
        self.app = FastAPI(title="CLADS LLM Bridge Configuration")
        
        # Initialize services
        self.db_connection = DatabaseConnection()
        self.auth_service = AuthenticationService(self.db_connection)
        self.config_service = ConfigurationService()
        self.health_service = HealthService()
        self.model_discovery_service = ModelDiscoveryService()
        self.usage_tracker = UsageTracker()
        
        # Initialize default password
        self.auth_service.initialize_default_password()
        
        # Setup middleware
        self._setup_middleware()
        
        # Setup templates and static files
        self._setup_templates()
        
        # Setup error handlers
        self.error_handler = create_error_handlers(self.app, self.templates)
        
        # Setup routes
        self._setup_routes()
        
        self.logger.info("Web application initialized successfully")
    
    def _setup_middleware(self):
        """Setup middleware for the application."""
        # Authentication middleware (added first so it runs after SessionMiddleware)
        self.app.add_middleware(AuthMiddleware, auth_service=self.auth_service)
        
        # Session middleware for authentication (added last so it runs first)
        self.app.add_middleware(
            SessionMiddleware,
            secret_key=os.getenv("SESSION_SECRET", "your-secret-key-change-in-production")
        )
    
    def _setup_templates(self):
        """Setup Jinja2 templates and static files."""
        # Create templates directory if it doesn't exist
        templates_dir = Path(__file__).parent / "templates"
        templates_dir.mkdir(exist_ok=True)
        
        # Create static directory if it doesn't exist
        static_dir = Path(__file__).parent / "static"
        static_dir.mkdir(exist_ok=True)
        
        self.templates = Jinja2Templates(directory=str(templates_dir))
        
        # Mount static files
        self.app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")
    
    def _setup_routes(self):
        """Setup application routes."""
        
        @self.app.get("/", response_class=HTMLResponse)
        async def dashboard(request: Request):
            """Main dashboard page."""
            return self.templates.TemplateResponse(
                "dashboard.html",
                {"request": request}
            )
        
        @self.app.get("/login", response_class=HTMLResponse)
        async def login_page(request: Request):
            """Login page."""
            # If already authenticated, redirect to dashboard
            if SessionManager.is_authenticated(request):
                return RedirectResponse(url="/", status_code=302)
            
            return self.templates.TemplateResponse(
                "login.html",
                {"request": request, "error": None}
            )
        
        @self.app.post("/login")
        async def login(request: Request, password: str = Form(...)):
            """Handle login form submission."""
            try:
                # Validate form data
                form_data = {"password": password}
                validation_result = validate_auth_form_data(form_data, "login")
                
                if not validation_result.is_valid:
                    return self.error_handler.handle_validation_error(
                        request, validation_result, form_data, "login.html"
                    )
                
                if self.auth_service.authenticate(password):
                    # Set session as authenticated
                    self.auth_service.set_session_authenticated(request.session)
                    self.logger.info(f"Successful login from {request.client.host}")
                    return RedirectResponse(url="/", status_code=302)
                else:
                    self.logger.warning(f"Failed login attempt from {request.client.host}")
                    return self.error_handler.handle_authentication_error(request, "invalid_password")
            except Exception as e:
                self.error_logger.log_exception(e, "Login form processing")
                return self.error_handler.handle_500(request, e)
        
        @self.app.post("/logout")
        async def logout(request: Request):
            """Handle logout."""
            SessionManager.clear_session(request)
            return RedirectResponse(url="/login", status_code=302)
        
        @self.app.get("/change-password", response_class=HTMLResponse)
        async def change_password_page(request: Request):
            """Change password page."""
            return self.templates.TemplateResponse(
                "change_password.html",
                {"request": request, "error": None, "success": None}
            )
        
        @self.app.post("/change-password")
        async def change_password(
            request: Request,
            old_password: str = Form(...),
            new_password: str = Form(...),
            confirm_password: str = Form(...)
        ):
            """Handle password change form submission."""
            try:
                # Validate form data
                form_data = {
                    "old_password": old_password,
                    "new_password": new_password,
                    "confirm_password": confirm_password
                }
                validation_result = validate_auth_form_data(form_data, "change_password")
                
                if not validation_result.is_valid:
                    return self.error_handler.handle_validation_error(
                        request, validation_result, form_data, "change_password.html"
                    )
                
                if self.auth_service.change_password(old_password, new_password):
                    self.logger.info(f"Password changed successfully for user from {request.client.host}")
                    success_message = error_messages.get_success_message("password_changed")
                    return self.templates.TemplateResponse(
                        "change_password.html",
                        {"request": request, "error": None, "success": success_message}
                    )
                else:
                    error_message = error_messages.get_error_message("invalid_password", ErrorCategory.AUTHENTICATION)
                    return self.templates.TemplateResponse(
                        "change_password.html",
                        {"request": request, "error": error_message, "success": None}
                    )
            except Exception as e:
                self.error_logger.log_exception(e, "Change password form processing")
                return self.error_handler.handle_500(request, e)
        
        @self.app.get("/config", response_class=HTMLResponse)
        async def config_page(request: Request):
            """Configuration page."""
            configs = self.config_service.get_llm_configs()
            
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
            
            return self.templates.TemplateResponse(
                "config.html",
                {
                    "request": request,
                    "configs": configs,  # Original objects for template
                    "configs_js": configs_for_js,  # Serializable data for JavaScript
                    "service_types": [
                        {"value": st.value, "name": st.value.replace("_", " ").title()}
                        for st in ServiceType
                    ],
                    "default_base_urls": ServiceType.get_default_base_urls()
                }
            )
        
        @self.app.post("/config/save")
        async def save_config(
            request: Request,
            config_id: str = Form(""),
            service_type: str = Form(...),
            base_url: str = Form(...),
            api_key: str = Form(""),
            model_name: str = Form(""),
            public_name: str = Form(""),
            enabled: bool = Form(False)
        ):
            """Save LLM configuration."""
            try:
                # Get existing config if editing
                existing_config = None
                if config_id:
                    existing_config = self.config_service.get_llm_config(config_id)
                
                # Validate form data
                form_data = {
                    "config_id": config_id,
                    "service_type": service_type,
                    "base_url": base_url,
                    "api_key": api_key,
                    "model_name": model_name,
                    "public_name": public_name,
                    "enabled": str(enabled).lower()
                }
                
                validation_result = validate_config_form_data(form_data, existing_config)
                
                if not validation_result.is_valid:
                    return self.error_handler.handle_validation_error(
                        request, validation_result, form_data, "config.html"
                    )
                
                from ..models.llm_config import LLMConfig
                from ..models.enums import ServiceType as ST
                import uuid
                from datetime import datetime
                
                # Create or update config
                if config_id:
                    config = self.config_service.get_llm_config(config_id)
                    if not config:
                        return self.error_handler.handle_configuration_error(
                            request, "update", "Configuration not found", config_id, service_type
                        )
                else:
                    # Check if we're at the limit
                    existing_configs = self.config_service.get_llm_configs()
                    if len(existing_configs) >= 20:
                        error_message = error_messages.get_error_message("config_limit_reached", ErrorCategory.CONFIGURATION)
                        return self.error_handler.handle_configuration_error(
                            request, "create", error_message, None, service_type
                        )
                    
                    config = LLMConfig(
                        id=str(uuid.uuid4()),
                        service_type=ST(service_type),
                        base_url=base_url,
                        api_key=api_key,
                        model_name=model_name,
                        public_name=public_name,
                        enabled=enabled,
                        created_at=datetime.utcnow(),
                        updated_at=datetime.utcnow()
                    )
                
                # Update fields
                config.service_type = ST(service_type)
                config.base_url = base_url
                if api_key:  # Only update API key if provided
                    config.api_key = api_key
                config.model_name = model_name
                config.public_name = public_name or model_name
                config.enabled = enabled
                
                # Save configuration
                if self.config_service.save_llm_config(config):
                    self.logger.info(f"Configuration saved successfully: {config.id} ({service_type})")
                    
                    # Trigger configuration reload in proxy server
                    await self._trigger_proxy_config_reload()
                    
                    return RedirectResponse(url="/config?success=1", status_code=302)
                else:
                    error_message = error_messages.get_error_message("config_save_failed", ErrorCategory.CONFIGURATION)
                    return self.error_handler.handle_configuration_error(
                        request, "save", error_message, config.id, service_type
                    )
                    
            except Exception as e:
                self.error_logger.log_exception(e, "Configuration save")
                return self.error_handler.handle_configuration_error(
                    request, "save", str(e), config_id, service_type
                )
        
        @self.app.post("/config/delete/{config_id}")
        async def delete_config(config_id: str):
            """Delete LLM configuration."""
            if self.config_service.delete_llm_config(config_id):
                # Trigger configuration reload in proxy server
                await self._trigger_proxy_config_reload()
                return RedirectResponse(url="/config?success=deleted", status_code=302)
            else:
                return RedirectResponse(url="/config?error=delete_failed", status_code=302)
        
        @self.app.post("/config/toggle/{config_id}")
        async def toggle_config(config_id: str):
            """Toggle configuration enabled status."""
            if self.config_service.toggle_config_enabled(config_id):
                # Trigger configuration reload in proxy server
                await self._trigger_proxy_config_reload()
                return RedirectResponse(url="/config", status_code=302)
            else:
                return RedirectResponse(url="/config?error=toggle_failed", status_code=302)
        
        @self.app.get("/api/models/{service_type}")
        async def get_models(request: Request, service_type: str, api_key: str = "", base_url: str = ""):
            """Get available models for a service type."""
            try:
                from ..models.enums import ServiceType as ST
                service_enum = ST(service_type)
                
                # Use fallback method to get models with defaults if API fails
                models = await self.model_discovery_service.get_models_with_fallback(
                    service_enum, api_key, base_url or service_enum.get_default_base_url()
                )
                
                self.logger.info(f"Successfully loaded {len(models)} models for {service_type}")
                return {"models": models}
            except Exception as e:
                self.error_logger.log_exception(e, f"Model discovery for {service_type}")
                
                # Return default models if everything fails
                try:
                    from ..models.enums import ServiceType as ST
                    service_enum = ST(service_type)
                    default_models = self.model_discovery_service.get_default_models(service_enum)
                    
                    warning_message = error_messages.format_api_error(
                        service_name=service_type,
                        error_message=str(e)
                    )
                    
                    return {
                        "models": default_models, 
                        "warning": f"Using default models. {warning_message}"
                    }
                except Exception as fallback_error:
                    self.error_logger.log_exception(fallback_error, f"Default model fallback for {service_type}")
                    return self.error_handler.handle_api_error(
                        request, service_type, str(e), 500, "model_discovery_failed"
                    )
        
        @self.app.post("/api/test-config/{config_id}")
        async def test_config(request: Request, config_id: str):
            """Test a specific LLM configuration."""
            try:
                config = self.config_service.get_llm_config(config_id)
                if not config:
                    error_message = error_messages.get_error_message("config_not_found", ErrorCategory.CONFIGURATION)
                    return self.error_handler.handle_api_error(
                        request, "configuration", error_message, 404, "config_not_found"
                    )
                
                # Test the configuration
                health_status = await self.health_service.test_llm_config(config)
                
                # Save the health status
                self.health_service.save_health_status(health_status)
                
                if health_status.status == "OK":
                    self.logger.info(f"Configuration test passed: {config_id} ({config.service_type.value})")
                else:
                    self.logger.warning(f"Configuration test failed: {config_id} ({config.service_type.value}) - {health_status.error_message}")
                
                return {
                    "status": health_status.status,
                    "error_message": health_status.error_message,
                    "response_time_ms": health_status.response_time_ms,
                    "model_count": health_status.model_count,
                    "last_checked": health_status.last_checked.isoformat()
                }
            except Exception as e:
                self.error_logger.log_exception(e, f"Configuration test for {config_id}")
                return self.error_handler.handle_api_error(
                    request, "configuration", str(e), 500, "config_test_failed"
                )
        
        @self.app.post("/api/test-all-configs")
        async def test_all_configs():
            """Test all LLM configurations."""
            try:
                configs = self.config_service.get_enabled_configs()
                if not configs:
                    return {"message": "No enabled configurations to test", "results": []}
                
                # Test all configurations
                health_statuses = await self.health_service.test_all_configs(configs)
                
                # Save all health statuses
                for status in health_statuses:
                    self.health_service.save_health_status(status)
                
                results = []
                for status in health_statuses:
                    results.append({
                        "service_id": status.service_id,
                        "status": status.status,
                        "error_message": status.error_message,
                        "response_time_ms": status.response_time_ms,
                        "model_count": status.model_count,
                        "last_checked": status.last_checked.isoformat()
                    })
                
                return {"results": results}
            except Exception as e:
                return {"error": str(e)}
        
        @self.app.post("/api/reload-config")
        async def reload_config_manual():
            """Manual configuration reload endpoint for Web UI."""
            try:
                # Trigger configuration reload in proxy server
                await self._trigger_proxy_config_reload()
                
                return {
                    "status": "success",
                    "message": "設定の再読み込みを実行しました",
                    "timestamp": time.time()
                }
            except Exception as e:
                self.logger.error(f"Manual config reload error: {e}")
                return {
                    "status": "error",
                    "message": f"設定の再読み込みに失敗しました: {str(e)}",
                    "timestamp": time.time()
                }
        
        @self.app.get("/api/health-status")
        async def get_health_status():
            """Get all health statuses."""
            try:
                statuses = self.health_service.get_all_health_status()
                result = {}
                for service_id, status in statuses.items():
                    result[service_id] = {
                        "status": status.status,
                        "error_message": status.error_message,
                        "response_time_ms": status.response_time_ms,
                        "model_count": status.model_count,
                        "last_checked": status.last_checked.isoformat()
                    }
                return result
            except Exception as e:
                return {"error": str(e)}
        
        @self.app.get("/monitoring", response_class=HTMLResponse)
        async def monitoring_page(request: Request, period: str = "daily"):
            """Monitoring dashboard page."""
            try:
                # Validate period parameter
                if period not in ["hourly", "daily", "weekly"]:
                    period = "daily"
                
                time_period = TimePeriod(period)
                
                # Get usage statistics
                usage_stats = self.usage_tracker.get_usage_stats(time_period)
                
                # Get leaderboards
                client_leaderboard = self.usage_tracker.get_client_leaderboard(time_period, limit=10)
                model_leaderboard = self.usage_tracker.get_model_leaderboard(time_period, limit=10)
                
                # Get real-time stats
                real_time_stats = self.usage_tracker.get_real_time_stats()
                
                return self.templates.TemplateResponse(
                    "monitoring.html",
                    {
                        "request": request,
                        "period": period,
                        "usage_stats": usage_stats,
                        "client_leaderboard": client_leaderboard,
                        "model_leaderboard": model_leaderboard,
                        "real_time_stats": real_time_stats
                    }
                )
            except Exception as e:
                return self.templates.TemplateResponse(
                    "monitoring.html",
                    {
                        "request": request,
                        "period": period,
                        "error": str(e),
                        "usage_stats": None,
                        "client_leaderboard": [],
                        "model_leaderboard": [],
                        "real_time_stats": {}
                    }
                )
        
        @self.app.get("/api/monitoring/stats")
        async def get_monitoring_stats(period: str = "daily"):
            """Get monitoring statistics API endpoint."""
            try:
                if period not in ["hourly", "daily", "weekly"]:
                    period = "daily"
                
                time_period = TimePeriod(period)
                
                # Get usage statistics
                usage_stats = self.usage_tracker.get_usage_stats(time_period)
                
                # Get leaderboards
                client_leaderboard = self.usage_tracker.get_client_leaderboard(time_period, limit=10)
                model_leaderboard = self.usage_tracker.get_model_leaderboard(time_period, limit=10)
                
                # Get real-time stats
                real_time_stats = self.usage_tracker.get_real_time_stats()
                
                return {
                    "period": period,
                    "usage_stats": {
                        "total_requests": usage_stats.total_requests,
                        "total_tokens": usage_stats.total_tokens,
                        "total_input_tokens": usage_stats.total_input_tokens,
                        "total_output_tokens": usage_stats.total_output_tokens,
                        "average_response_time": usage_stats.average_response_time,
                        "success_rate": usage_stats.success_rate,
                        "period_start": usage_stats.period_start.isoformat() if usage_stats.period_start else None,
                        "period_end": usage_stats.period_end.isoformat() if usage_stats.period_end else None
                    },
                    "client_leaderboard": [
                        {
                            "client_ip": client.client_ip,
                            "total_requests": client.total_requests,
                            "total_tokens": client.total_tokens,
                            "total_input_tokens": client.total_input_tokens,
                            "total_output_tokens": client.total_output_tokens,
                            "average_response_time": client.average_response_time,
                            "last_request": client.last_request.isoformat() if client.last_request else None
                        }
                        for client in client_leaderboard
                    ],
                    "model_leaderboard": [
                        {
                            "model_name": model.model_name,
                            "public_name": model.public_name,
                            "total_requests": model.total_requests,
                            "total_tokens": model.total_tokens,
                            "total_input_tokens": model.total_input_tokens,
                            "total_output_tokens": model.total_output_tokens,
                            "average_response_time": model.average_response_time,
                            "unique_clients": model.unique_clients,
                            "last_request": model.last_request.isoformat() if model.last_request else None
                        }
                        for model in model_leaderboard
                    ],
                    "real_time_stats": real_time_stats
                }
            except Exception as e:
                return {"error": str(e)}
        
        @self.app.get("/api/monitoring/clients")
        async def get_client_leaderboard_api(period: str = "daily", limit: int = 10):
            """Get client leaderboard API endpoint."""
            try:
                if period not in ["hourly", "daily", "weekly"]:
                    period = "daily"
                
                time_period = TimePeriod(period)
                client_leaderboard = self.usage_tracker.get_client_leaderboard(time_period, limit=limit)
                
                return {
                    "period": period,
                    "clients": [
                        {
                            "rank": idx + 1,
                            "client_ip": client.client_ip,
                            "total_requests": client.total_requests,
                            "total_tokens": client.total_tokens,
                            "total_input_tokens": client.total_input_tokens,
                            "total_output_tokens": client.total_output_tokens,
                            "average_response_time": client.average_response_time,
                            "last_request": client.last_request.isoformat() if client.last_request else None
                        }
                        for idx, client in enumerate(client_leaderboard)
                    ]
                }
            except Exception as e:
                return {"error": str(e)}
        
        @self.app.get("/api/monitoring/models")
        async def get_model_leaderboard_api(period: str = "daily", limit: int = 10):
            """Get model leaderboard API endpoint."""
            try:
                if period not in ["hourly", "daily", "weekly"]:
                    period = "daily"
                
                time_period = TimePeriod(period)
                model_leaderboard = self.usage_tracker.get_model_leaderboard(time_period, limit=limit)
                
                return {
                    "period": period,
                    "models": [
                        {
                            "rank": idx + 1,
                            "model_name": model.model_name,
                            "public_name": model.public_name,
                            "total_requests": model.total_requests,
                            "total_tokens": model.total_tokens,
                            "total_input_tokens": model.total_input_tokens,
                            "total_output_tokens": model.total_output_tokens,
                            "average_response_time": model.average_response_time,
                            "unique_clients": model.unique_clients,
                            "last_request": model.last_request.isoformat() if model.last_request else None
                        }
                        for idx, model in enumerate(model_leaderboard)
                    ]
                }
            except Exception as e:
                return {"error": str(e)}
        
        @self.app.get("/api/monitoring/models/comparison")
        async def get_model_comparison_api(period: str = "daily"):
            """Get model comparison statistics API endpoint."""
            try:
                if period not in ["hourly", "daily", "weekly"]:
                    period = "daily"
                
                time_period = TimePeriod(period)
                comparison_data = self.usage_tracker.get_model_comparison(time_period)
                
                return {
                    "period": period,
                    **comparison_data
                }
            except Exception as e:
                return {"error": str(e)}
        
        @self.app.get("/api/monitoring/models/trends")
        async def get_model_trends_api(period: str = "daily", model_name: str = None):
            """Get model usage trends API endpoint."""
            try:
                if period not in ["hourly", "daily", "weekly"]:
                    period = "daily"
                
                time_period = TimePeriod(period)
                trends = self.usage_tracker.get_model_usage_trends(time_period, model_name)
                
                return {
                    "period": period,
                    "model_name": model_name,
                    "trends": trends
                }
            except Exception as e:
                return {"error": str(e)}
        
        @self.app.get("/health")
        async def health_check():
            """Health check endpoint for container orchestration."""
            try:
                # Check database connectivity
                db_healthy = True
                try:
                    configs = self.config_service.get_llm_configs()
                except Exception as e:
                    db_healthy = False
                    logger.error(f"Database health check failed: {e}")
                
                # Check if we have any configurations
                config_count = len(configs) if db_healthy else 0
                
                return {
                    "status": "healthy" if db_healthy else "unhealthy",
                    "timestamp": time.time(),
                    "services": {
                        "database": "healthy" if db_healthy else "unhealthy",
                        "web_ui": "healthy",
                        "configuration_count": config_count
                    }
                }
            except Exception as e:
                return {
                    "status": "error",
                    "error": str(e),
                    "timestamp": time.time()
                }
        
        @self.app.get("/health/ready")
        async def readiness_check():
            """Readiness probe for Kubernetes."""
            try:
                # Check if all services are ready
                configs = self.config_service.get_llm_configs()
                return {
                    "status": "ready",
                    "timestamp": time.time(),
                    "configuration_count": len(configs)
                }
            except Exception as e:
                return {
                    "status": "not_ready",
                    "error": str(e),
                    "timestamp": time.time()
                }
        
        @self.app.get("/health/live")
        async def liveness_check():
            """Liveness probe for Kubernetes."""
            return {
                "status": "alive",
                "timestamp": time.time()
            }
    
    async def _trigger_proxy_config_reload(self):
        """Trigger configuration reload in proxy server.
        
        Sends an HTTP POST request to the proxy server's reload endpoint
        to ensure configuration changes are immediately reflected.
        """
        try:
            import httpx
            import os
            
            # Get proxy server port from environment or use default
            proxy_port = int(os.getenv('PROXY_PORT', '4321'))
            proxy_url = f"http://localhost:{proxy_port}/admin/reload"
            
            # Send reload request with timeout
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.post(proxy_url)
                
                if response.status_code == 200:
                    result = response.json()
                    self.logger.info(f"Configuration reload triggered successfully: {result.get('message', 'No message')}")
                else:
                    self.logger.warning(f"Configuration reload request failed with status {response.status_code}: {response.text}")
                    
        except httpx.ConnectError:
            self.logger.warning("Could not connect to proxy server for configuration reload - proxy may not be running")
        except httpx.TimeoutException:
            self.logger.warning("Timeout while trying to reload proxy configuration")
        except Exception as e:
            self.logger.error(f"Unexpected error during configuration reload: {e}")


def create_app() -> FastAPI:
    """Create and configure FastAPI application."""
    web_app = WebApp()
    return web_app.app