"""Error handling utilities for CLADS LLM Bridge proxy."""

import logging
from typing import Dict, Any, Optional
from datetime import datetime, timedelta
from enum import Enum

from fastapi import HTTPException
from fastapi.responses import JSONResponse

from ..models.llm_config import LLMConfig
from ..models.enums import ServiceType


logger = logging.getLogger(__name__)


class ErrorType(Enum):
    """Types of errors that can occur."""
    SERVICE_UNAVAILABLE = "service_unavailable"
    AUTHENTICATION_ERROR = "authentication_error"
    RATE_LIMIT_ERROR = "rate_limit_error"
    INVALID_REQUEST = "invalid_request"
    MODEL_NOT_FOUND = "model_not_found"
    TIMEOUT_ERROR = "timeout_error"
    INTERNAL_ERROR = "internal_error"
    CONFIGURATION_ERROR = "configuration_error"


class ServiceHealthTracker:
    """Track service health and availability."""
    
    def __init__(self):
        """Initialize the service health tracker."""
        self._service_status: Dict[str, Dict[str, Any]] = {}
        self._failure_counts: Dict[str, int] = {}
        self._last_failure_time: Dict[str, datetime] = {}
        
        # Configuration
        self.max_failures = 5  # Max failures before marking service as down
        self.failure_window = timedelta(minutes=5)  # Time window for failure counting
        self.recovery_time = timedelta(minutes=10)  # Time to wait before retrying failed service
    
    def record_success(self, service_id: str):
        """Record a successful request for a service.
        
        Args:
            service_id: Service identifier
        """
        self._failure_counts[service_id] = 0
        self._service_status[service_id] = {
            "status": "healthy",
            "last_success": datetime.utcnow(),
            "consecutive_failures": 0
        }
    
    def record_failure(self, service_id: str, error_type: ErrorType, error_message: str):
        """Record a failed request for a service.
        
        Args:
            service_id: Service identifier
            error_type: Type of error
            error_message: Error message
        """
        now = datetime.utcnow()
        
        # Reset failure count if outside failure window
        if (service_id in self._last_failure_time and 
            now - self._last_failure_time[service_id] > self.failure_window):
            self._failure_counts[service_id] = 0
        
        # Increment failure count
        self._failure_counts[service_id] = self._failure_counts.get(service_id, 0) + 1
        self._last_failure_time[service_id] = now
        
        # Update service status
        consecutive_failures = self._failure_counts[service_id]
        status = "unhealthy" if consecutive_failures >= self.max_failures else "degraded"
        
        self._service_status[service_id] = {
            "status": status,
            "last_failure": now,
            "consecutive_failures": consecutive_failures,
            "error_type": error_type.value,
            "error_message": error_message
        }
        
        logger.warning(f"Service {service_id} failure #{consecutive_failures}: {error_message}")
    
    def is_service_available(self, service_id: str) -> bool:
        """Check if a service is available for requests.
        
        Args:
            service_id: Service identifier
            
        Returns:
            True if service is available, False otherwise
        """
        if service_id not in self._service_status:
            return True  # Unknown services are assumed available
        
        status_info = self._service_status[service_id]
        
        # If service is healthy, it's available
        if status_info["status"] == "healthy":
            return True
        
        # If service is unhealthy, check if recovery time has passed
        if status_info["status"] == "unhealthy":
            last_failure = status_info.get("last_failure")
            if last_failure and datetime.utcnow() - last_failure > self.recovery_time:
                # Reset status to allow retry
                self._failure_counts[service_id] = 0
                return True
            return False
        
        # Degraded services are still available but with warnings
        return True
    
    def get_service_status(self, service_id: str) -> Dict[str, Any]:
        """Get the current status of a service.
        
        Args:
            service_id: Service identifier
            
        Returns:
            Service status information
        """
        return self._service_status.get(service_id, {
            "status": "unknown",
            "consecutive_failures": 0
        })
    
    def get_all_service_status(self) -> Dict[str, Dict[str, Any]]:
        """Get status of all tracked services.
        
        Returns:
            Dictionary of service statuses
        """
        return self._service_status.copy()


class ErrorHandler:
    """Handle and format errors for the proxy server."""
    
    def __init__(self):
        """Initialize the error handler."""
        self.health_tracker = ServiceHealthTracker()
    
    def handle_service_error(
        self,
        config: LLMConfig,
        error: Exception,
        request_data: Optional[Dict[str, Any]] = None
    ) -> HTTPException:
        """Handle service-specific errors.
        
        Args:
            config: LLM configuration
            error: The exception that occurred
            request_data: Original request data
            
        Returns:
            HTTPException with appropriate status and message
        """
        service_id = f"{config.service_type.value}_{config.id}"
        error_message = str(error)
        
        # Determine error type and appropriate response
        if "authentication" in error_message.lower() or "api key" in error_message.lower():
            error_type = ErrorType.AUTHENTICATION_ERROR
            status_code = 401
            client_message = "Authentication failed. Please check your API key configuration."
            
        elif "rate limit" in error_message.lower() or "quota" in error_message.lower():
            error_type = ErrorType.RATE_LIMIT_ERROR
            status_code = 429
            client_message = "Rate limit exceeded. Please try again later."
            
        elif "timeout" in error_message.lower():
            error_type = ErrorType.TIMEOUT_ERROR
            status_code = 504
            client_message = "Request timeout. The service took too long to respond."
            
        elif "connection" in error_message.lower() or "unreachable" in error_message.lower():
            error_type = ErrorType.SERVICE_UNAVAILABLE
            status_code = 503
            client_message = f"Service temporarily unavailable: {config.service_type.value}"
            
        elif "model" in error_message.lower() and "not found" in error_message.lower():
            error_type = ErrorType.MODEL_NOT_FOUND
            status_code = 404
            client_message = f"Model not found or not available: {config.model_name}"
            
        else:
            error_type = ErrorType.INTERNAL_ERROR
            status_code = 500
            client_message = "Internal server error occurred."
        
        # Record the failure
        self.health_tracker.record_failure(service_id, error_type, error_message)
        
        # Log the error with context
        from ..utils.logging_config import get_error_logger
        error_logger = get_error_logger()
        error_logger.log_api_error(
            service=config.service_type.value,
            endpoint="proxy_request",
            status_code=status_code,
            error_message=error_message
        )
        
        # Format user-friendly error message
        from ..utils.error_messages import error_messages
        formatted_message = error_messages.format_api_error(
            service_name=config.service_type.value,
            error_message=client_message,
            status_code=status_code
        )
        
        # Create error response
        error_response = {
            "error": {
                "message": formatted_message,
                "type": error_type.value,
                "code": status_code,
                "service": config.service_type.value,
                "model": config.public_name or config.model_name,
                "timestamp": datetime.utcnow().isoformat()
            }
        }
        
        return HTTPException(status_code=status_code, detail=error_response)
    
    def handle_configuration_error(self, message: str) -> HTTPException:
        """Handle configuration-related errors.
        
        Args:
            message: Error message
            
        Returns:
            HTTPException with configuration error details
        """
        error_response = {
            "error": {
                "message": message,
                "type": ErrorType.CONFIGURATION_ERROR.value,
                "code": 500
            }
        }
        
        return HTTPException(status_code=500, detail=error_response)
    
    def handle_request_validation_error(self, message: str) -> HTTPException:
        """Handle request validation errors.
        
        Args:
            message: Error message
            
        Returns:
            HTTPException with validation error details
        """
        error_response = {
            "error": {
                "message": message,
                "type": ErrorType.INVALID_REQUEST.value,
                "code": 400
            }
        }
        
        return HTTPException(status_code=400, detail=error_response)
    
    def check_service_availability(self, config: LLMConfig) -> Optional[HTTPException]:
        """Check if a service is available before making requests.
        
        Args:
            config: LLM configuration
            
        Returns:
            HTTPException if service is unavailable, None if available
        """
        service_id = f"{config.service_type.value}_{config.id}"
        
        if not self.health_tracker.is_service_available(service_id):
            status_info = self.health_tracker.get_service_status(service_id)
            
            error_response = {
                "error": {
                    "message": f"Service {config.service_type.value} is currently unavailable due to repeated failures.",
                    "type": ErrorType.SERVICE_UNAVAILABLE.value,
                    "code": 503,
                    "service": config.service_type.value,
                    "model": config.public_name or config.model_name,
                    "details": {
                        "consecutive_failures": status_info.get("consecutive_failures", 0),
                        "last_error": status_info.get("error_message", "Unknown error")
                    }
                }
            }
            
            return HTTPException(status_code=503, detail=error_response)
        
        return None
    
    def record_success(self, config: LLMConfig):
        """Record a successful request for a service.
        
        Args:
            config: LLM configuration
        """
        service_id = f"{config.service_type.value}_{config.id}"
        self.health_tracker.record_success(service_id)
    
    def get_service_health_status(self) -> Dict[str, Any]:
        """Get health status of all services.
        
        Returns:
            Dictionary with service health information
        """
        return {
            "services": self.health_tracker.get_all_service_status(),
            "timestamp": datetime.utcnow().isoformat()
        }
    
    def create_openai_error_response(self, error_type: str, message: str, code: int = 500) -> Dict[str, Any]:
        """Create an OpenAI-compatible error response.
        
        Args:
            error_type: Type of error
            message: Error message
            code: HTTP status code
            
        Returns:
            OpenAI-compatible error response
        """
        return {
            "error": {
                "message": message,
                "type": error_type,
                "param": None,
                "code": code
            }
        }