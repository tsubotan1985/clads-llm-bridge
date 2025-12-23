"""LLM configuration data model."""

from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field, model_validator
from .enums import ServiceType


class LLMConfig(BaseModel):
    """Configuration for an LLM service."""
    
    id: str = Field(..., description="Unique identifier for the configuration")
    service_type: ServiceType = Field(..., description="Type of LLM service")
    base_url: str = Field(..., description="Base URL for the service API")
    api_key: str = Field("", description="API key for authentication")
    model_name: str = Field("", description="Name of the model to use")
    public_name: str = Field("", description="Public name to display for this model")
    enabled: bool = Field(True, description="Whether this configuration is enabled")
    available_on_4321: bool = Field(True, description="Available on port 4321 (general endpoint)")
    available_on_4333: bool = Field(True, description="Available on port 4333 (special endpoint)")
    created_at: datetime = Field(default_factory=datetime.utcnow, description="Creation timestamp")
    updated_at: datetime = Field(default_factory=datetime.utcnow, description="Last update timestamp")
    
    class Config:
        """Pydantic configuration."""
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }
    
    @model_validator(mode='before')
    @classmethod
    def set_defaults(cls, values):
        """Set default values based on other fields."""
        if isinstance(values, dict):
            # Set default base URL if not provided
            if not values.get('base_url') and values.get('service_type'):
                service_type = values['service_type']
                if isinstance(service_type, ServiceType):
                    values['base_url'] = service_type.get_default_base_url()
                elif isinstance(service_type, str):
                    try:
                        service_enum = ServiceType(service_type)
                        values['base_url'] = service_enum.get_default_base_url()
                    except ValueError:
                        pass
            
            # Set default public name if not provided
            if not values.get('public_name') and values.get('model_name'):
                values['public_name'] = values['model_name']
            
            # Always update the timestamp
            values['updated_at'] = datetime.utcnow()
        
        return values
    
    def to_dict(self) -> dict:
        """Convert to dictionary for database storage."""
        data = self.dict()
        data['service_type'] = self.service_type.value if isinstance(self.service_type, ServiceType) else self.service_type
        data['available_on_4321'] = int(self.available_on_4321)  # Convert to integer for SQLite
        data['available_on_4333'] = int(self.available_on_4333)  # Convert to integer for SQLite
        data['created_at'] = self.created_at.isoformat()
        data['updated_at'] = self.updated_at.isoformat()
        return data
    
    @classmethod
    def from_dict(cls, data: dict) -> 'LLMConfig':
        """Create instance from dictionary."""
        if 'service_type' in data and isinstance(data['service_type'], str):
            data['service_type'] = ServiceType(data['service_type'])
        if 'created_at' in data and isinstance(data['created_at'], str):
            data['created_at'] = datetime.fromisoformat(data['created_at'])
        if 'updated_at' in data and isinstance(data['updated_at'], str):
            data['updated_at'] = datetime.fromisoformat(data['updated_at'])
        return cls(**data)
    
    def mask_api_key(self) -> str:
        """Return masked API key for display."""
        if not self.api_key:
            return ""
        if len(self.api_key) <= 8:
            return "*" * len(self.api_key)
        return self.api_key[:4] + "*" * (len(self.api_key) - 8) + self.api_key[-4:]