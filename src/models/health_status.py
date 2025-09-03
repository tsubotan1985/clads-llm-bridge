"""Health status data model."""

from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field


class HealthStatus(BaseModel):
    """Health status of an LLM service configuration."""
    
    service_id: str = Field(..., description="ID of the LLM configuration")
    status: str = Field(..., description="Health status (OK, NG)")
    last_checked: datetime = Field(default_factory=datetime.utcnow, description="When the health check was performed")
    error_message: Optional[str] = Field(None, description="Error message if status is NG")
    response_time_ms: Optional[int] = Field(None, description="Response time in milliseconds")
    model_count: Optional[int] = Field(None, description="Number of available models")
    
    class Config:
        """Pydantic configuration."""
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }
    
    @property
    def is_healthy(self) -> bool:
        """Check if the service is healthy."""
        return self.status == "OK"
    
    @property
    def status_color(self) -> str:
        """Get color for status display."""
        return "green" if self.is_healthy else "red"
    
    def to_dict(self) -> dict:
        """Convert to dictionary for database storage."""
        data = self.dict()
        data['last_checked'] = self.last_checked.isoformat()
        return data
    
    @classmethod
    def from_dict(cls, data: dict) -> 'HealthStatus':
        """Create instance from dictionary."""
        if 'last_checked' in data and isinstance(data['last_checked'], str):
            data['last_checked'] = datetime.fromisoformat(data['last_checked'])
        return cls(**data)
    
    @classmethod
    def create_ok(cls, service_id: str, response_time_ms: int = None, model_count: int = None) -> 'HealthStatus':
        """Create a healthy status."""
        return cls(
            service_id=service_id,
            status="OK",
            response_time_ms=response_time_ms,
            model_count=model_count
        )
    
    @classmethod
    def create_error(cls, service_id: str, error_message: str) -> 'HealthStatus':
        """Create an error status."""
        return cls(
            service_id=service_id,
            status="NG",
            error_message=error_message
        )