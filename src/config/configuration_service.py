"""Configuration management service for LLM Bridge."""

import sqlite3
import uuid
from typing import List, Optional
from datetime import datetime
from cryptography.fernet import Fernet
import os
import base64

from ..database.connection import DatabaseConnection
from ..models.llm_config import LLMConfig
from ..models.enums import ServiceType
from ..models.health_status import HealthStatus


class ConfigurationService:
    """Service for managing LLM configurations."""
    
    def __init__(self, db_path: str = None):
        """Initialize the configuration service.
        
        Args:
            db_path: Path to the SQLite database file
        """
        self.db_path = db_path or "data/clads_llm_bridge.db"
        self.db = DatabaseConnection(self.db_path)
        self._encryption_key = self._get_or_create_encryption_key()
        self._cipher = Fernet(self._encryption_key)
    
    def _get_or_create_encryption_key(self) -> bytes:
        """Get or create encryption key for API keys."""
        key_file = os.path.join(os.path.dirname(self.db_path or ""), ".encryption_key")
        
        if os.path.exists(key_file):
            with open(key_file, 'rb') as f:
                return f.read()
        else:
            # Generate new key
            key = Fernet.generate_key()
            os.makedirs(os.path.dirname(key_file), exist_ok=True)
            with open(key_file, 'wb') as f:
                f.write(key)
            return key
    
    def _encrypt_api_key(self, api_key: str) -> str:
        """Encrypt API key for storage."""
        if not api_key:
            return ""
        return self._cipher.encrypt(api_key.encode()).decode()
    
    def _decrypt_api_key(self, encrypted_key: str) -> str:
        """Decrypt API key from storage."""
        if not encrypted_key:
            return ""
        try:
            return self._cipher.decrypt(encrypted_key.encode()).decode()
        except Exception:
            # If decryption fails, return empty string
            return ""
    
    def get_llm_configs(self) -> List[LLMConfig]:
        """Get all LLM configurations.
        
        Returns:
            List of LLMConfig objects
        """
        rows = self.db.execute_query("""
            SELECT id, service_type, base_url, api_key, model_name, 
                   public_name, enabled, created_at, updated_at
            FROM llm_configs
            ORDER BY created_at ASC
        """)
        
        configs = []
        for row in rows:
            config_data = {
                'id': row['id'],
                'service_type': row['service_type'],
                'base_url': row['base_url'],
                'api_key': self._decrypt_api_key(row['api_key']),
                'model_name': row['model_name'],
                'public_name': row['public_name'],
                'enabled': bool(row['enabled']),
                'created_at': row['created_at'],
                'updated_at': row['updated_at']
            }
            configs.append(LLMConfig.from_dict(config_data))
        
        return configs
    
    def get_llm_config(self, config_id: str) -> Optional[LLMConfig]:
        """Get a specific LLM configuration by ID.
        
        Args:
            config_id: The configuration ID
            
        Returns:
            LLMConfig object or None if not found
        """
        rows = self.db.execute_query("""
            SELECT id, service_type, base_url, api_key, model_name, 
                   public_name, enabled, created_at, updated_at
            FROM llm_configs
            WHERE id = ?
        """, (config_id,))
        
        if not rows:
            return None
        
        row = rows[0]
        config_data = {
            'id': row['id'],
            'service_type': row['service_type'],
            'base_url': row['base_url'],
            'api_key': self._decrypt_api_key(row['api_key']),
            'model_name': row['model_name'],
            'public_name': row['public_name'],
            'enabled': bool(row['enabled']),
            'created_at': row['created_at'],
            'updated_at': row['updated_at']
        }
        return LLMConfig.from_dict(config_data)
    
    def save_llm_config(self, config: LLMConfig) -> bool:
        """Save or update an LLM configuration.
        
        Args:
            config: LLMConfig object to save
            
        Returns:
            True if successful, False otherwise
        """
        try:
            # Validate configuration
            if not self._validate_config(config):
                return False
            
            # Check if we're at the limit (20 configs max)
            if not config.id or not self.get_llm_config(config.id):
                # New config - check limit
                existing_configs = self.get_llm_configs()
                if len(existing_configs) >= 20:
                    return False
            
            # Generate ID if not provided
            if not config.id:
                config.id = str(uuid.uuid4())
            
            # Update timestamp
            config.updated_at = datetime.utcnow()
            
            # Check if config exists
            existing_rows = self.db.execute_query("SELECT id FROM llm_configs WHERE id = ?", (config.id,))
            exists = len(existing_rows) > 0
            
            if exists:
                # Update existing config
                self.db.execute_update("""
                    UPDATE llm_configs 
                    SET service_type = ?, base_url = ?, api_key = ?, 
                        model_name = ?, public_name = ?, enabled = ?, 
                        updated_at = ?
                    WHERE id = ?
                """, (
                    config.service_type.value,
                    config.base_url,
                    self._encrypt_api_key(config.api_key),
                    config.model_name,
                    config.public_name,
                    config.enabled,
                    config.updated_at.isoformat(),
                    config.id
                ))
            else:
                # Insert new config
                self.db.execute_update("""
                    INSERT INTO llm_configs 
                    (id, service_type, base_url, api_key, model_name, 
                     public_name, enabled, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    config.id,
                    config.service_type.value,
                    config.base_url,
                    self._encrypt_api_key(config.api_key),
                    config.model_name,
                    config.public_name,
                    config.enabled,
                    config.created_at.isoformat(),
                    config.updated_at.isoformat()
                ))
            
            return True
                
        except Exception as e:
            print(f"Error saving LLM config: {e}")
            return False
    
    def delete_llm_config(self, config_id: str) -> bool:
        """Delete an LLM configuration.
        
        Args:
            config_id: The configuration ID to delete
            
        Returns:
            True if successful, False otherwise
        """
        try:
            affected_rows = self.db.execute_update("DELETE FROM llm_configs WHERE id = ?", (config_id,))
            return affected_rows > 0
        except Exception as e:
            print(f"Error deleting LLM config: {e}")
            return False
    
    def _validate_config(self, config: LLMConfig) -> bool:
        """Validate LLM configuration.
        
        Args:
            config: LLMConfig object to validate
            
        Returns:
            True if valid, False otherwise
        """
        from ..validation.form_validators import ConfigurationValidator
        
        validator = ConfigurationValidator()
        
        # Convert config to form data for validation
        form_data = {
            "service_type": config.service_type.value if config.service_type else "",
            "base_url": config.base_url or "",
            "api_key": config.api_key or "",
            "model_name": config.model_name or "",
            "public_name": config.public_name or "",
            "enabled": str(config.enabled).lower(),
            "config_id": config.id or ""
        }
        
        validation_result = validator.validate_config_form(
            service_type=form_data["service_type"],
            base_url=form_data["base_url"],
            api_key=form_data["api_key"],
            model_name=form_data["model_name"],
            public_name=form_data["public_name"],
            enabled=config.enabled,
            config_id=form_data["config_id"]
        )
        
        if not validation_result.is_valid:
            # Log validation errors
            from ..utils.logging_config import get_error_logger
            error_logger = get_error_logger()
            
            for error in validation_result.errors:
                error_logger.log_validation_error(
                    field=error.field,
                    value=form_data.get(error.field, ""),
                    error_message=error.message,
                    form_type="configuration"
                )
        
        return validation_result.is_valid
    
    def get_enabled_configs(self) -> List[LLMConfig]:
        """Get only enabled LLM configurations.
        
        Returns:
            List of enabled LLMConfig objects
        """
        return [config for config in self.get_llm_configs() if config.enabled]
    
    def get_configs_by_service_type(self, service_type: ServiceType) -> List[LLMConfig]:
        """Get configurations by service type.
        
        Args:
            service_type: The service type to filter by
            
        Returns:
            List of LLMConfig objects for the specified service type
        """
        return [config for config in self.get_llm_configs() 
                if config.service_type == service_type]
    
    def toggle_config_enabled(self, config_id: str) -> bool:
        """Toggle the enabled status of a configuration.
        
        Args:
            config_id: The configuration ID
            
        Returns:
            True if successful, False otherwise
        """
        config = self.get_llm_config(config_id)
        if not config:
            return False
        
        config.enabled = not config.enabled
        return self.save_llm_config(config)
    
    def save_config(self, config_data: dict) -> bool:
        """Save configuration from dictionary data (for backward compatibility).
        
        Args:
            config_data: Dictionary containing configuration data
            
        Returns:
            True if successful, False otherwise
        """
        try:
            from ..models.enums import ServiceType as ST
            from datetime import datetime
            import uuid
            
            # Create LLMConfig from dictionary
            config = LLMConfig(
                id=config_data.get('id') or str(uuid.uuid4()),
                service_type=ST(config_data['service_type']),
                base_url=config_data['base_url'],
                api_key=config_data.get('api_key', ''),
                model_name=config_data['model_name'],
                public_name=config_data.get('public_name', config_data['model_name']),
                enabled=config_data.get('enabled', True),
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow()
            )
            
            return self.save_llm_config(config)
            
        except Exception as e:
            print(f"Error saving config from dict: {e}")
            return False