"""Unit tests for ConfigurationService."""

import pytest
import tempfile
import os
from datetime import datetime

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.config.configuration_service import ConfigurationService
from src.models.llm_config import LLMConfig
from src.models.enums import ServiceType
from src.database.migrations import DatabaseMigrations
from src.database.connection import DatabaseConnection


class TestConfigurationService:
    """Test cases for ConfigurationService."""
    
    @pytest.fixture
    def temp_db(self):
        """Create a temporary database for testing."""
        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
            db_path = f.name
        
        # Initialize the database
        db_conn = DatabaseConnection(db_path)
        migrations = DatabaseMigrations(db_conn)
        migrations.initialize_database()
        
        yield db_path
        
        # Cleanup
        os.unlink(db_path)
        # Also cleanup encryption key file
        key_file = os.path.join(os.path.dirname(db_path), ".encryption_key")
        if os.path.exists(key_file):
            os.unlink(key_file)
    
    @pytest.fixture
    def config_service(self, temp_db):
        """Create a ConfigurationService instance with temporary database."""
        return ConfigurationService(temp_db)
    
    @pytest.fixture
    def sample_config(self):
        """Create a sample LLM configuration."""
        return LLMConfig(
            id="test-config-1",
            service_type=ServiceType.OPENAI,
            base_url="https://api.openai.com/v1",
            api_key="sk-test123",
            model_name="gpt-4",
            public_name="GPT-4",
            enabled=True
        )
    
    def test_save_and_get_config(self, config_service, sample_config):
        """Test saving and retrieving a configuration."""
        # Save config
        result = config_service.save_llm_config(sample_config)
        assert result is True
        
        # Retrieve config
        retrieved = config_service.get_llm_config(sample_config.id)
        assert retrieved is not None
        assert retrieved.id == sample_config.id
        assert retrieved.service_type == sample_config.service_type
        assert retrieved.base_url == sample_config.base_url
        assert retrieved.api_key == sample_config.api_key
        assert retrieved.model_name == sample_config.model_name
        assert retrieved.public_name == sample_config.public_name
        assert retrieved.enabled == sample_config.enabled
    
    def test_get_all_configs(self, config_service, sample_config):
        """Test retrieving all configurations."""
        # Initially empty
        configs = config_service.get_llm_configs()
        assert len(configs) == 0
        
        # Save a config
        config_service.save_llm_config(sample_config)
        
        # Should have one config
        configs = config_service.get_llm_configs()
        assert len(configs) == 1
        assert configs[0].id == sample_config.id
    
    def test_update_config(self, config_service, sample_config):
        """Test updating an existing configuration."""
        # Save initial config
        config_service.save_llm_config(sample_config)
        
        # Update the config
        sample_config.model_name = "gpt-3.5-turbo"
        sample_config.public_name = "GPT-3.5 Turbo"
        
        result = config_service.save_llm_config(sample_config)
        assert result is True
        
        # Retrieve and verify update
        retrieved = config_service.get_llm_config(sample_config.id)
        assert retrieved.model_name == "gpt-3.5-turbo"
        assert retrieved.public_name == "GPT-3.5 Turbo"
    
    def test_delete_config(self, config_service, sample_config):
        """Test deleting a configuration."""
        # Save config
        config_service.save_llm_config(sample_config)
        
        # Verify it exists
        retrieved = config_service.get_llm_config(sample_config.id)
        assert retrieved is not None
        
        # Delete config
        result = config_service.delete_llm_config(sample_config.id)
        assert result is True
        
        # Verify it's gone
        retrieved = config_service.get_llm_config(sample_config.id)
        assert retrieved is None
    
    def test_config_limit(self, config_service):
        """Test the 20 configuration limit."""
        # Create 20 configs
        for i in range(20):
            config = LLMConfig(
                id=f"config-{i}",
                service_type=ServiceType.OPENAI,
                base_url="https://api.openai.com/v1",
                api_key=f"sk-test{i}",
                model_name="gpt-4",
                public_name=f"GPT-4-{i}",
                enabled=True
            )
            result = config_service.save_llm_config(config)
            assert result is True
        
        # Try to add 21st config
        config_21 = LLMConfig(
            id="config-21",
            service_type=ServiceType.OPENAI,
            base_url="https://api.openai.com/v1",
            api_key="sk-test21",
            model_name="gpt-4",
            public_name="GPT-4-21",
            enabled=True
        )
        result = config_service.save_llm_config(config_21)
        assert result is False
    
    def test_get_enabled_configs(self, config_service):
        """Test getting only enabled configurations."""
        # Create enabled config
        enabled_config = LLMConfig(
            id="enabled-config",
            service_type=ServiceType.OPENAI,
            base_url="https://api.openai.com/v1",
            api_key="sk-test1",
            model_name="gpt-4",
            public_name="GPT-4",
            enabled=True
        )
        
        # Create disabled config
        disabled_config = LLMConfig(
            id="disabled-config",
            service_type=ServiceType.ANTHROPIC,
            base_url="https://api.anthropic.com",
            api_key="sk-test2",
            model_name="claude-3-sonnet",
            public_name="Claude 3 Sonnet",
            enabled=False
        )
        
        config_service.save_llm_config(enabled_config)
        config_service.save_llm_config(disabled_config)
        
        # Get enabled configs
        enabled_configs = config_service.get_enabled_configs()
        assert len(enabled_configs) == 1
        assert enabled_configs[0].id == "enabled-config"
    
    def test_get_configs_by_service_type(self, config_service):
        """Test getting configurations by service type."""
        # Create OpenAI config
        openai_config = LLMConfig(
            id="openai-config",
            service_type=ServiceType.OPENAI,
            base_url="https://api.openai.com/v1",
            api_key="sk-test1",
            model_name="gpt-4",
            public_name="GPT-4",
            enabled=True
        )
        
        # Create Anthropic config
        anthropic_config = LLMConfig(
            id="anthropic-config",
            service_type=ServiceType.ANTHROPIC,
            base_url="https://api.anthropic.com",
            api_key="sk-test2",
            model_name="claude-3-sonnet",
            public_name="Claude 3 Sonnet",
            enabled=True
        )
        
        config_service.save_llm_config(openai_config)
        config_service.save_llm_config(anthropic_config)
        
        # Get OpenAI configs
        openai_configs = config_service.get_configs_by_service_type(ServiceType.OPENAI)
        assert len(openai_configs) == 1
        assert openai_configs[0].id == "openai-config"
        
        # Get Anthropic configs
        anthropic_configs = config_service.get_configs_by_service_type(ServiceType.ANTHROPIC)
        assert len(anthropic_configs) == 1
        assert anthropic_configs[0].id == "anthropic-config"
    
    def test_toggle_config_enabled(self, config_service, sample_config):
        """Test toggling configuration enabled status."""
        # Save config (enabled by default)
        config_service.save_llm_config(sample_config)
        assert sample_config.enabled is True
        
        # Toggle to disabled
        result = config_service.toggle_config_enabled(sample_config.id)
        assert result is True
        
        # Verify it's disabled
        retrieved = config_service.get_llm_config(sample_config.id)
        assert retrieved.enabled is False
        
        # Toggle back to enabled
        result = config_service.toggle_config_enabled(sample_config.id)
        assert result is True
        
        # Verify it's enabled
        retrieved = config_service.get_llm_config(sample_config.id)
        assert retrieved.enabled is True
    
    def test_api_key_encryption(self, config_service, sample_config):
        """Test that API keys are encrypted in storage."""
        # Save config
        config_service.save_llm_config(sample_config)
        
        # Check that the API key is encrypted in the database
        rows = config_service.db.execute_query("SELECT api_key FROM llm_configs WHERE id = ?", (sample_config.id,))
        encrypted_key = rows[0]['api_key']
        
        # The encrypted key should be different from the original
        assert encrypted_key != sample_config.api_key
        assert len(encrypted_key) > len(sample_config.api_key)
        
        # But when retrieved through the service, it should be decrypted
        retrieved = config_service.get_llm_config(sample_config.id)
        assert retrieved.api_key == sample_config.api_key
    
    def test_validation(self, config_service):
        """Test configuration validation."""
        # Test invalid service type - Pydantic will raise ValidationError
        with pytest.raises(Exception):  # ValidationError from pydantic
            invalid_config = LLMConfig(
                id="invalid-config",
                service_type=None,
                base_url="https://api.openai.com/v1",
                api_key="sk-test",
                model_name="gpt-4",
                public_name="GPT-4",
                enabled=True
            )
        
        # Test missing API key for service that requires it
        no_key_config = LLMConfig(
            id="no-key-config",
            service_type=ServiceType.OPENAI,
            base_url="https://api.openai.com/v1",
            api_key="",
            model_name="gpt-4",
            public_name="GPT-4",
            enabled=True
        )
        
        result = config_service.save_llm_config(no_key_config)
        assert result is False
        
        # Test VS Code Proxy (doesn't require API key)
        vscode_config = LLMConfig(
            id="vscode-config",
            service_type=ServiceType.VSCODE_PROXY,
            base_url="http://localhost:3000",
            api_key="",
            model_name="vscode-lm-proxy",
            public_name="VS Code LM Proxy",
            enabled=True
        )
        
        result = config_service.save_llm_config(vscode_config)
        assert result is True