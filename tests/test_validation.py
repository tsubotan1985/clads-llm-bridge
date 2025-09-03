"""Tests for validation and error handling."""

import pytest
from unittest.mock import Mock, patch

from src.validation.form_validators import (
    ConfigurationValidator, 
    AuthenticationValidator,
    validate_config_form_data,
    validate_auth_form_data
)
from src.utils.error_messages import ErrorMessageGenerator, ErrorCategory
from src.models.enums import ServiceType


class TestConfigurationValidator:
    """Test configuration form validation."""
    
    def setup_method(self):
        """Setup test fixtures."""
        self.validator = ConfigurationValidator()
    
    def test_valid_openai_config(self):
        """Test valid OpenAI configuration."""
        result = self.validator.validate_config_form(
            service_type="openai",
            base_url="https://api.openai.com/v1",
            api_key="sk-1234567890abcdef1234567890abcdef1234567890abcdef12",
            model_name="gpt-4",
            public_name="GPT-4",
            enabled=True
        )
        
        assert result.is_valid
        assert len(result.errors) == 0
    
    def test_missing_required_fields(self):
        """Test validation with missing required fields."""
        result = self.validator.validate_config_form(
            service_type="",
            base_url="",
            api_key="",
            model_name="",
            public_name="",
            enabled=False
        )
        
        assert not result.is_valid
        assert len(result.errors) > 0
        
        # Check for specific required field errors
        error_fields = [error.field for error in result.errors]
        assert "service_type" in error_fields
        assert "model_name" in error_fields
    
    def test_invalid_url_format(self):
        """Test validation with invalid URL format."""
        result = self.validator.validate_config_form(
            service_type="openai",
            base_url="not-a-valid-url",
            api_key="sk-1234567890abcdef1234567890abcdef1234567890abcdef12",
            model_name="gpt-4",
            public_name="GPT-4",
            enabled=True
        )
        
        assert not result.is_valid
        url_errors = [error for error in result.errors if error.field == "base_url"]
        assert len(url_errors) > 0
        assert url_errors[0].code == "invalid_url"
    
    def test_insecure_url_warning(self):
        """Test warning for HTTP URLs."""
        result = self.validator.validate_config_form(
            service_type="openai",
            base_url="http://api.openai.com/v1",
            api_key="sk-1234567890abcdef1234567890abcdef1234567890abcdef12",
            model_name="gpt-4",
            public_name="GPT-4",
            enabled=True
        )
        
        assert result.is_valid  # Should be valid but with warnings
        assert len(result.warnings) > 0
        
        url_warnings = [warning for warning in result.warnings if warning.field == "base_url"]
        assert len(url_warnings) > 0
        assert url_warnings[0].code == "insecure_url"
    
    def test_vscode_proxy_no_api_key_required(self):
        """Test VS Code LM Proxy doesn't require API key."""
        result = self.validator.validate_config_form(
            service_type="vscode_proxy",
            base_url="http://localhost:3000/v1",
            api_key="",  # No API key required
            model_name="vscode-lm-proxy",
            public_name="VS Code LM Proxy",
            enabled=True
        )
        
        assert result.is_valid
        assert len(result.errors) == 0
    
    def test_invalid_model_name_characters(self):
        """Test validation with invalid model name characters."""
        result = self.validator.validate_config_form(
            service_type="openai",
            base_url="https://api.openai.com/v1",
            api_key="sk-1234567890abcdef1234567890abcdef1234567890abcdef12",
            model_name="invalid model name with spaces and @#$%",
            public_name="GPT-4",
            enabled=True
        )
        
        assert not result.is_valid
        model_errors = [error for error in result.errors if error.field == "model_name"]
        assert len(model_errors) > 0
        assert model_errors[0].code == "invalid_chars"
    
    def test_service_specific_warnings(self):
        """Test service-specific validation warnings."""
        # Test VS Code LM Proxy warning
        result = self.validator.validate_config_form(
            service_type="vscode_proxy",
            base_url="http://localhost:3000",  # Missing /v1
            api_key="",
            model_name="custom-model",  # Not typical vscode-lm-proxy
            public_name="Custom Model",
            enabled=True
        )
        
        assert result.is_valid  # Should be valid but with warnings
        assert len(result.warnings) > 0


class TestAuthenticationValidator:
    """Test authentication form validation."""
    
    def setup_method(self):
        """Setup test fixtures."""
        self.validator = AuthenticationValidator()
    
    def test_valid_login(self):
        """Test valid login form."""
        result = self.validator.validate_login_form("validpassword")
        
        assert result.is_valid
        assert len(result.errors) == 0
    
    def test_empty_password(self):
        """Test empty password validation."""
        result = self.validator.validate_login_form("")
        
        assert not result.is_valid
        assert len(result.errors) == 1
        assert result.errors[0].field == "password"
        assert result.errors[0].code == "required"
    
    def test_valid_password_change(self):
        """Test valid password change form."""
        result = self.validator.validate_change_password_form(
            old_password="oldpassword",
            new_password="newstrongpassword123!",
            confirm_password="newstrongpassword123!"
        )
        
        assert result.is_valid
        assert len(result.errors) == 0
    
    def test_password_mismatch(self):
        """Test password confirmation mismatch."""
        result = self.validator.validate_change_password_form(
            old_password="oldpassword",
            new_password="newpassword",
            confirm_password="differentpassword"
        )
        
        assert not result.is_valid
        mismatch_errors = [error for error in result.errors if error.field == "confirm_password"]
        assert len(mismatch_errors) > 0
        assert mismatch_errors[0].code == "mismatch"
    
    def test_short_password(self):
        """Test password too short validation."""
        result = self.validator.validate_change_password_form(
            old_password="oldpassword",
            new_password="short",
            confirm_password="short"
        )
        
        assert not result.is_valid
        short_errors = [error for error in result.errors if error.field == "new_password"]
        assert len(short_errors) > 0
        assert short_errors[0].code == "too_short"
    
    def test_weak_password_warning(self):
        """Test weak password warning."""
        result = self.validator.validate_change_password_form(
            old_password="oldpassword",
            new_password="password123",  # Weak but meets minimum requirements
            confirm_password="password123"
        )
        
        assert result.is_valid  # Should be valid but with warnings
        assert len(result.warnings) > 0
        
        weak_warnings = [warning for warning in result.warnings if warning.field == "new_password"]
        assert len(weak_warnings) > 0
        assert weak_warnings[0].code == "weak"
    
    def test_same_as_old_password(self):
        """Test new password same as old password."""
        result = self.validator.validate_change_password_form(
            old_password="samepassword",
            new_password="samepassword",
            confirm_password="samepassword"
        )
        
        assert not result.is_valid
        same_errors = [error for error in result.errors if error.field == "new_password"]
        assert len(same_errors) > 0
        assert same_errors[0].code == "same_as_old"


class TestErrorMessageGenerator:
    """Test error message generation."""
    
    def setup_method(self):
        """Setup test fixtures."""
        self.generator = ErrorMessageGenerator()
    
    def test_get_error_message(self):
        """Test getting error messages."""
        message = self.generator.get_error_message("required")
        assert message == "This field is required."
        
        # Test with context
        message = self.generator.get_error_message(
            "too_long", 
            context={"max_length": 100}
        )
        assert "100" in message
    
    def test_get_warning_message(self):
        """Test getting warning messages."""
        message = self.generator.get_warning_message("insecure_url")
        assert "HTTP" in message
        assert "HTTPS" in message
    
    def test_get_success_message(self):
        """Test getting success messages."""
        message = self.generator.get_success_message("config_saved")
        assert "saved successfully" in message.lower()
    
    def test_format_api_error(self):
        """Test API error formatting."""
        message = self.generator.format_api_error(
            service_name="OpenAI",
            error_message="Invalid API key",
            status_code=401
        )
        
        assert "OpenAI" in message
        assert "authentication failed" in message.lower()
    
    def test_clean_api_error_message(self):
        """Test API error message cleaning."""
        # Test prefix removal
        cleaned = self.generator._clean_api_error_message("Error: Something went wrong")
        assert cleaned == "Something went wrong."
        
        # Test capitalization
        cleaned = self.generator._clean_api_error_message("something went wrong")
        assert cleaned == "Something went wrong."
        
        # Test period addition
        cleaned = self.generator._clean_api_error_message("Something went wrong")
        assert cleaned == "Something went wrong."


class TestFormValidationHelpers:
    """Test form validation helper functions."""
    
    def test_validate_config_form_data(self):
        """Test config form data validation helper."""
        form_data = {
            "service_type": "openai",
            "base_url": "https://api.openai.com/v1",
            "api_key": "sk-1234567890abcdef1234567890abcdef1234567890abcdef12",
            "model_name": "gpt-4",
            "public_name": "GPT-4",
            "enabled": "true"
        }
        
        result = validate_config_form_data(form_data)
        assert result.is_valid
    
    def test_validate_auth_form_data_login(self):
        """Test auth form data validation helper for login."""
        form_data = {"password": "validpassword"}
        
        result = validate_auth_form_data(form_data, "login")
        assert result.is_valid
    
    def test_validate_auth_form_data_change_password(self):
        """Test auth form data validation helper for password change."""
        form_data = {
            "old_password": "oldpassword",
            "new_password": "newstrongpassword123!",
            "confirm_password": "newstrongpassword123!"
        }
        
        result = validate_auth_form_data(form_data, "change_password")
        assert result.is_valid
    
    def test_validate_auth_form_data_unknown_type(self):
        """Test auth form data validation with unknown form type."""
        form_data = {"password": "password"}
        
        result = validate_auth_form_data(form_data, "unknown_type")
        assert not result.is_valid
        assert len(result.errors) == 1
        assert result.errors[0].field == "form_type"


if __name__ == "__main__":
    pytest.main([__file__])