"""Form validation utilities for web UI."""

import re
import urllib.parse
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass

from ..models.enums import ServiceType


@dataclass
class ValidationError:
    """Represents a validation error."""
    field: str
    message: str
    code: str


@dataclass
class ValidationResult:
    """Result of form validation."""
    is_valid: bool
    errors: List[ValidationError]
    warnings: List[ValidationError]
    
    def add_error(self, field: str, message: str, code: str = "invalid"):
        """Add a validation error."""
        self.errors.append(ValidationError(field, message, code))
        self.is_valid = False
    
    def add_warning(self, field: str, message: str, code: str = "warning"):
        """Add a validation warning."""
        self.warnings.append(ValidationError(field, message, code))
    
    def get_field_errors(self, field: str) -> List[ValidationError]:
        """Get errors for a specific field."""
        return [error for error in self.errors if error.field == field]
    
    def get_field_warnings(self, field: str) -> List[ValidationError]:
        """Get warnings for a specific field."""
        return [warning for warning in self.warnings if warning.field == field]


class ConfigurationValidator:
    """Validator for LLM configuration forms."""
    
    # URL validation regex
    URL_PATTERN = re.compile(
        r'^https?://'  # http:// or https://
        r'(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+[A-Z]{2,6}\.?|'  # domain...
        r'localhost|'  # localhost...
        r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})'  # ...or ip
        r'(?::\d+)?'  # optional port
        r'(?:/?|[/?]\S+)?$', re.IGNORECASE)
    
    # API key patterns for different services
    API_KEY_PATTERNS = {
        ServiceType.OPENAI: re.compile(r'^sk-[a-zA-Z0-9]{48,}$'),
        ServiceType.ANTHROPIC: re.compile(r'^sk-ant-[a-zA-Z0-9\-_]{95,}$'),
        ServiceType.GEMINI: re.compile(r'^[a-zA-Z0-9\-_]{39}$'),
        ServiceType.OPENROUTER: re.compile(r'^sk-or-[a-zA-Z0-9\-_]{48,}$'),
    }
    
    def validate_config_form(
        self,
        service_type: str,
        base_url: str,
        api_key: str,
        model_name: str,
        public_name: str,
        enabled: bool = False,
        config_id: str = "",
        existing_config=None
    ) -> ValidationResult:
        """Validate configuration form data.
        
        Args:
            service_type: Service type string
            base_url: Base URL for the service
            api_key: API key for authentication
            model_name: Model name to use
            public_name: Public name for the model
            enabled: Whether the configuration is enabled
            config_id: Configuration ID (for updates)
            
        Returns:
            ValidationResult with validation status and errors
        """
        result = ValidationResult(is_valid=True, errors=[], warnings=[])
        
        # Validate service type
        try:
            service_enum = ServiceType(service_type)
        except ValueError:
            result.add_error("service_type", f"Invalid service type: {service_type}", "invalid_service")
            # Continue validation even if service type is invalid
            service_enum = ServiceType.NONE
        
        # Validate base URL
        if service_enum != ServiceType.NONE:
            if not base_url or not base_url.strip():
                result.add_error("base_url", "Base URL is required for this service type", "required")
            else:
                base_url = base_url.strip()
                if not self._is_valid_url(base_url):
                    result.add_error("base_url", "Invalid URL format", "invalid_url")
                elif not self._is_secure_url(base_url):
                    result.add_warning("base_url", "HTTP URLs are not recommended for production use", "insecure_url")
        
        # Validate API key
        if service_enum not in [ServiceType.NONE, ServiceType.VSCODE_PROXY, ServiceType.LMSTUDIO]:
            if not api_key or not api_key.strip():
                # For existing configs, allow empty API key if one already exists
                if config_id and existing_config and existing_config.api_key:
                    # Skip validation - we'll keep the existing API key
                    pass
                else:
                    result.add_error("api_key", "API key is required for this service type", "required")
            else:
                api_key = api_key.strip()
                if not self._is_valid_api_key(service_enum, api_key):
                    result.add_warning("api_key", f"API key format doesn't match expected pattern for {service_enum.value}", "invalid_format")
        
        # Validate model name
        if not model_name or not model_name.strip():
            result.add_error("model_name", "Model name is required", "required")
        else:
            model_name = model_name.strip()
            if len(model_name) > 200:
                result.add_error("model_name", "Model name is too long (max 200 characters)", "too_long")
            elif not self._is_valid_model_name(model_name):
                result.add_error("model_name", "Model name contains invalid characters", "invalid_chars")
        
        # Validate public name
        if public_name and public_name.strip():
            public_name = public_name.strip()
            if len(public_name) > 200:
                result.add_error("public_name", "Public name is too long (max 200 characters)", "too_long")
            elif not self._is_valid_model_name(public_name):
                result.add_error("public_name", "Public name contains invalid characters", "invalid_chars")
        
        # Service-specific validations
        self._validate_service_specific(service_enum, base_url, api_key, model_name, result)
        
        return result
    
    def _is_valid_url(self, url: str) -> bool:
        """Check if URL is valid."""
        if not url:
            return False
        
        try:
            parsed = urllib.parse.urlparse(url)
            return bool(parsed.scheme and parsed.netloc)
        except Exception:
            return False
    
    def _is_secure_url(self, url: str) -> bool:
        """Check if URL uses HTTPS."""
        return url.lower().startswith('https://')
    
    def _is_valid_api_key(self, service_type: ServiceType, api_key: str) -> bool:
        """Check if API key matches expected pattern for service."""
        if service_type not in self.API_KEY_PATTERNS:
            return True  # No specific pattern to validate
        
        pattern = self.API_KEY_PATTERNS[service_type]
        return bool(pattern.match(api_key))
    
    def _is_valid_model_name(self, name: str) -> bool:
        """Check if model name contains only valid characters."""
        # Allow alphanumeric, hyphens, underscores, dots, colons, slashes, and spaces
        pattern = re.compile(r'^[a-zA-Z0-9\-_\.:/\s]+$')
        return bool(pattern.match(name))
    
    def _validate_service_specific(
        self,
        service_type: ServiceType,
        base_url: str,
        api_key: str,
        model_name: str,
        result: ValidationResult
    ):
        """Perform service-specific validations."""
        
        if service_type == ServiceType.VSCODE_PROXY:
            # VS Code LM Proxy specific validations
            if base_url and not base_url.endswith('/v1'):
                result.add_warning("base_url", "VS Code LM Proxy URLs typically end with '/v1'", "format_warning")
            
            if model_name and model_name != "vscode-lm-proxy":
                result.add_warning("model_name", "VS Code LM Proxy typically uses 'vscode-lm-proxy' as model name", "format_warning")
        
        elif service_type == ServiceType.LMSTUDIO:
            # LM Studio specific validations
            if base_url and not base_url.startswith('http://127.0.0.1:') and not base_url.startswith('http://localhost:'):
                result.add_warning("base_url", "LM Studio typically runs on localhost", "format_warning")
        
        elif service_type == ServiceType.OPENAI:
            # OpenAI specific validations
            if base_url and 'openai.com' not in base_url:
                result.add_warning("base_url", "This doesn't appear to be an official OpenAI URL", "format_warning")
        
        elif service_type == ServiceType.ANTHROPIC:
            # Anthropic specific validations
            if base_url and 'anthropic.com' not in base_url:
                result.add_warning("base_url", "This doesn't appear to be an official Anthropic URL", "format_warning")
        
        elif service_type == ServiceType.GEMINI:
            # Google AI Studio specific validations
            if base_url and 'googleapis.com' not in base_url:
                result.add_warning("base_url", "This doesn't appear to be an official Google AI Studio URL", "format_warning")


class AuthenticationValidator:
    """Validator for authentication forms."""
    
    def validate_login_form(self, password: str) -> ValidationResult:
        """Validate login form data.
        
        Args:
            password: Password to validate
            
        Returns:
            ValidationResult with validation status and errors
        """
        result = ValidationResult(is_valid=True, errors=[], warnings=[])
        
        if not password:
            result.add_error("password", "Password is required", "required")
        elif len(password.strip()) == 0:
            result.add_error("password", "Password cannot be empty", "empty")
        
        return result
    
    def validate_change_password_form(
        self,
        old_password: str,
        new_password: str,
        confirm_password: str
    ) -> ValidationResult:
        """Validate change password form data.
        
        Args:
            old_password: Current password
            new_password: New password
            confirm_password: Confirmation of new password
            
        Returns:
            ValidationResult with validation status and errors
        """
        result = ValidationResult(is_valid=True, errors=[], warnings=[])
        
        # Validate old password
        if not old_password:
            result.add_error("old_password", "Current password is required", "required")
        
        # Validate new password
        if not new_password:
            result.add_error("new_password", "New password is required", "required")
        else:
            # Check password strength
            if len(new_password) < 8:
                result.add_error("new_password", "Password must be at least 8 characters long", "too_short")
            elif new_password == old_password:
                result.add_error("new_password", "New password must be different from current password", "same_as_old")
            elif self._is_weak_password(new_password):
                result.add_warning("new_password", "Password is weak. Consider using a mix of letters, numbers, and symbols", "weak")
        
        # Validate password confirmation
        if not confirm_password:
            result.add_error("confirm_password", "Password confirmation is required", "required")
        elif new_password and confirm_password != new_password:
            result.add_error("confirm_password", "Passwords do not match", "mismatch")
        
        return result
    
    def _is_weak_password(self, password: str) -> bool:
        """Check if password is considered weak."""
        # Check for common weak patterns
        weak_patterns = ['password', '12345678', 'qwerty', 'admin', 'hakodate4']
        for pattern in weak_patterns:
            if pattern in password.lower():
                return True
        
        # Check for basic complexity
        has_lower = any(c.islower() for c in password)
        has_upper = any(c.isupper() for c in password)
        has_digit = any(c.isdigit() for c in password)
        has_special = any(c in '!@#$%^&*()_+-=[]{}|;:,.<>?' for c in password)
        
        complexity_score = sum([has_lower, has_upper, has_digit, has_special])
        return complexity_score < 2


def validate_config_form_data(form_data: Dict[str, str], existing_config=None) -> ValidationResult:
    """Validate configuration form data from request.
    
    Args:
        form_data: Dictionary of form data
        existing_config: Existing configuration object (for edits)
        
    Returns:
        ValidationResult with validation status and errors
    """
    validator = ConfigurationValidator()
    
    return validator.validate_config_form(
        service_type=form_data.get('service_type', ''),
        base_url=form_data.get('base_url', ''),
        api_key=form_data.get('api_key', ''),
        model_name=form_data.get('model_name', ''),
        public_name=form_data.get('public_name', ''),
        enabled=form_data.get('enabled', '').lower() in ['true', '1', 'on'],
        config_id=form_data.get('config_id', ''),
        existing_config=existing_config
    )


def validate_auth_form_data(form_data: Dict[str, str], form_type: str) -> ValidationResult:
    """Validate authentication form data from request.
    
    Args:
        form_data: Dictionary of form data
        form_type: Type of form ('login' or 'change_password')
        
    Returns:
        ValidationResult with validation status and errors
    """
    validator = AuthenticationValidator()
    
    if form_type == 'login':
        return validator.validate_login_form(form_data.get('password', ''))
    elif form_type == 'change_password':
        return validator.validate_change_password_form(
            old_password=form_data.get('old_password', ''),
            new_password=form_data.get('new_password', ''),
            confirm_password=form_data.get('confirm_password', '')
        )
    else:
        result = ValidationResult(is_valid=False, errors=[], warnings=[])
        result.add_error('form_type', f'Unknown form type: {form_type}', 'unknown_type')
        return result