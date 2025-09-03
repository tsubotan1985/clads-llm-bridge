"""Error message utilities for user-friendly error handling."""

from typing import Dict, Any, Optional
from enum import Enum


class ErrorCategory(Enum):
    """Categories of errors for better organization."""
    VALIDATION = "validation"
    AUTHENTICATION = "authentication"
    CONFIGURATION = "configuration"
    API_ERROR = "api_error"
    NETWORK = "network"
    SYSTEM = "system"
    RATE_LIMIT = "rate_limit"
    PERMISSION = "permission"


class ErrorMessageGenerator:
    """Generate user-friendly error messages."""
    
    # Error message templates
    ERROR_MESSAGES = {
        # Validation errors
        "required": "This field is required.",
        "invalid_url": "Please enter a valid URL (e.g., https://api.example.com).",
        "invalid_service": "Please select a valid service type.",
        "too_long": "This value is too long. Maximum length is {max_length} characters.",
        "invalid_chars": "This field contains invalid characters. Only letters, numbers, hyphens, underscores, dots, colons, and slashes are allowed.",
        "empty": "This field cannot be empty.",
        "too_short": "This value is too short. Minimum length is {min_length} characters.",
        "mismatch": "The values do not match.",
        "same_as_old": "The new value must be different from the current value.",
        
        # Authentication errors
        "invalid_password": "The password you entered is incorrect. Please try again.",
        "weak_password": "Your password is weak. Consider using a mix of uppercase letters, lowercase letters, numbers, and special characters.",
        "authentication_failed": "Authentication failed. Please check your credentials and try again.",
        "session_expired": "Your session has expired. Please log in again.",
        "access_denied": "You don't have permission to access this resource.",
        
        # Configuration errors
        "config_not_found": "The requested configuration was not found.",
        "config_limit_reached": "Maximum number of configurations (20) has been reached. Please delete an existing configuration first.",
        "config_save_failed": "Failed to save the configuration. Please check your input and try again.",
        "config_delete_failed": "Failed to delete the configuration. It may be in use or already deleted.",
        "config_test_failed": "Configuration test failed. Please check your settings and try again.",
        "invalid_api_key": "The API key format is invalid for the selected service.",
        "duplicate_config": "A configuration with these settings already exists.",
        
        # API errors
        "api_key_invalid": "The API key is invalid or has expired. Please check your API key in the service provider's dashboard.",
        "api_quota_exceeded": "API quota has been exceeded. Please check your usage limits or upgrade your plan.",
        "api_rate_limited": "Too many requests. Please wait a moment before trying again.",
        "api_service_unavailable": "The API service is temporarily unavailable. Please try again later.",
        "api_model_not_found": "The specified model is not available or doesn't exist.",
        "api_request_invalid": "The request format is invalid. Please check your configuration.",
        "api_timeout": "The request timed out. The service may be experiencing high load.",
        
        # Network errors
        "connection_failed": "Failed to connect to the service. Please check your internet connection and the service URL.",
        "dns_resolution_failed": "Could not resolve the service URL. Please check the URL and your network settings.",
        "ssl_error": "SSL/TLS connection error. The service certificate may be invalid or expired.",
        "proxy_error": "Proxy connection error. Please check your proxy settings.",
        
        # System errors
        "database_error": "Database error occurred. Please try again or contact support if the problem persists.",
        "file_system_error": "File system error. Please check disk space and permissions.",
        "memory_error": "Insufficient memory to complete the operation.",
        "internal_error": "An internal error occurred. Please try again or contact support.",
        "service_unavailable": "The service is temporarily unavailable. Please try again later.",
        
        # Service-specific errors
        "openai_error": "OpenAI API error: {message}",
        "anthropic_error": "Anthropic API error: {message}",
        "gemini_error": "Google AI Studio error: {message}",
        "openrouter_error": "OpenRouter API error: {message}",
        "vscode_proxy_error": "VS Code LM Proxy error: {message}",
        "lmstudio_error": "LM Studio error: {message}",
    }
    
    # Warning message templates
    WARNING_MESSAGES = {
        "insecure_url": "You're using an HTTP URL. HTTPS is recommended for security.",
        "format_warning": "The format doesn't match the typical pattern for this service.",
        "weak": "This value is weak. Consider strengthening it.",
        "deprecated": "This feature is deprecated and may be removed in future versions.",
        "performance": "This configuration may impact performance.",
    }
    
    # Success message templates
    SUCCESS_MESSAGES = {
        "config_saved": "Configuration saved successfully.",
        "config_deleted": "Configuration deleted successfully.",
        "config_tested": "Configuration test completed successfully.",
        "password_changed": "Password changed successfully.",
        "login_successful": "Login successful.",
        "logout_successful": "Logout successful.",
        "models_loaded": "Models loaded successfully.",
        "health_check_passed": "Health check passed.",
    }
    
    def get_error_message(
        self,
        error_code: str,
        category: ErrorCategory = ErrorCategory.SYSTEM,
        context: Optional[Dict[str, Any]] = None,
        custom_message: Optional[str] = None
    ) -> str:
        """Get a user-friendly error message.
        
        Args:
            error_code: Error code to look up
            category: Category of the error
            context: Additional context for message formatting
            custom_message: Custom message to use instead of template
            
        Returns:
            User-friendly error message
        """
        if custom_message:
            return custom_message
        
        template = self.ERROR_MESSAGES.get(error_code, "An unexpected error occurred.")
        
        if context:
            try:
                return template.format(**context)
            except (KeyError, ValueError):
                # If formatting fails, return the template as-is
                return template
        
        return template
    
    def get_warning_message(
        self,
        warning_code: str,
        context: Optional[Dict[str, Any]] = None
    ) -> str:
        """Get a user-friendly warning message.
        
        Args:
            warning_code: Warning code to look up
            context: Additional context for message formatting
            
        Returns:
            User-friendly warning message
        """
        template = self.WARNING_MESSAGES.get(warning_code, "Warning: Please review your input.")
        
        if context:
            try:
                return template.format(**context)
            except (KeyError, ValueError):
                return template
        
        return template
    
    def get_success_message(
        self,
        success_code: str,
        context: Optional[Dict[str, Any]] = None
    ) -> str:
        """Get a user-friendly success message.
        
        Args:
            success_code: Success code to look up
            context: Additional context for message formatting
            
        Returns:
            User-friendly success message
        """
        template = self.SUCCESS_MESSAGES.get(success_code, "Operation completed successfully.")
        
        if context:
            try:
                return template.format(**context)
            except (KeyError, ValueError):
                return template
        
        return template
    
    def format_api_error(
        self,
        service_name: str,
        error_message: str,
        error_code: Optional[str] = None,
        status_code: Optional[int] = None
    ) -> str:
        """Format API error message for display.
        
        Args:
            service_name: Name of the service that failed
            error_message: Original error message from the API
            error_code: Error code from the API
            status_code: HTTP status code
            
        Returns:
            Formatted error message
        """
        # Clean up common API error messages
        clean_message = self._clean_api_error_message(error_message)
        
        # Add context based on status code
        if status_code:
            if status_code == 401:
                return f"{service_name} authentication failed. Please check your API key."
            elif status_code == 403:
                return f"Access denied by {service_name}. Please check your permissions and API key."
            elif status_code == 429:
                return f"{service_name} rate limit exceeded. Please wait before trying again."
            elif status_code == 404:
                return f"Resource not found on {service_name}. Please check your configuration."
            elif status_code >= 500:
                return f"{service_name} is experiencing server issues. Please try again later."
        
        # Format with service name
        return f"{service_name} error: {clean_message}"
    
    def _clean_api_error_message(self, message: str) -> str:
        """Clean up API error messages for better readability.
        
        Args:
            message: Original error message
            
        Returns:
            Cleaned error message
        """
        if not message:
            return "Unknown error occurred"
        
        # Remove common prefixes
        prefixes_to_remove = [
            "Error: ",
            "Exception: ",
            "APIError: ",
            "HTTPError: ",
        ]
        
        for prefix in prefixes_to_remove:
            if message.startswith(prefix):
                message = message[len(prefix):]
        
        # Capitalize first letter
        if message and message[0].islower():
            message = message[0].upper() + message[1:]
        
        # Ensure it ends with a period
        if message and not message.endswith('.'):
            message += '.'
        
        return message
    
    def create_error_context(
        self,
        field_name: Optional[str] = None,
        service_name: Optional[str] = None,
        max_length: Optional[int] = None,
        min_length: Optional[int] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """Create context dictionary for error message formatting.
        
        Args:
            field_name: Name of the field that failed validation
            service_name: Name of the service
            max_length: Maximum allowed length
            min_length: Minimum required length
            **kwargs: Additional context variables
            
        Returns:
            Context dictionary for message formatting
        """
        context = {}
        
        if field_name:
            context['field_name'] = field_name
        if service_name:
            context['service_name'] = service_name
        if max_length is not None:
            context['max_length'] = max_length
        if min_length is not None:
            context['min_length'] = min_length
        
        context.update(kwargs)
        return context


# Global instance for easy access
error_messages = ErrorMessageGenerator()


def get_user_friendly_error(
    error_code: str,
    category: ErrorCategory = ErrorCategory.SYSTEM,
    **context
) -> str:
    """Convenience function to get user-friendly error message.
    
    Args:
        error_code: Error code to look up
        category: Category of the error
        **context: Context variables for message formatting
        
    Returns:
        User-friendly error message
    """
    return error_messages.get_error_message(error_code, category, context)


def format_validation_errors(errors: list) -> Dict[str, list]:
    """Format validation errors for template display.
    
    Args:
        errors: List of ValidationError objects
        
    Returns:
        Dictionary mapping field names to error messages
    """
    formatted_errors = {}
    
    for error in errors:
        if error.field not in formatted_errors:
            formatted_errors[error.field] = []
        
        message = error_messages.get_error_message(error.code)
        formatted_errors[error.field].append(message)
    
    return formatted_errors


def format_validation_warnings(warnings: list) -> Dict[str, list]:
    """Format validation warnings for template display.
    
    Args:
        warnings: List of ValidationError objects (used as warnings)
        
    Returns:
        Dictionary mapping field names to warning messages
    """
    formatted_warnings = {}
    
    for warning in warnings:
        if warning.field not in formatted_warnings:
            formatted_warnings[warning.field] = []
        
        message = error_messages.get_warning_message(warning.code)
        formatted_warnings[warning.field].append(message)
    
    return formatted_warnings