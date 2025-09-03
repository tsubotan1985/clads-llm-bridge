"""Usage record data model."""

from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field


class UsageRecord(BaseModel):
    """Record of API usage for monitoring and statistics."""
    
    id: str = Field(..., description="Unique identifier for the usage record")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="When the request was made")
    client_ip: str = Field(..., description="IP address of the client")
    model_name: str = Field(..., description="Name of the model used")
    public_name: str = Field("", description="Public name of the model")
    input_tokens: int = Field(0, description="Number of input tokens")
    output_tokens: int = Field(0, description="Number of output tokens")
    total_tokens: int = Field(0, description="Total number of tokens")
    response_time_ms: int = Field(0, description="Response time in milliseconds")
    status: str = Field("success", description="Request status (success, error)")
    error_message: Optional[str] = Field(None, description="Error message if status is error")
    
    class Config:
        """Pydantic configuration."""
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }
    
    def model_post_init(self, __context) -> None:
        """Calculate total tokens if not provided."""
        if self.total_tokens == 0:
            self.total_tokens = self.input_tokens + self.output_tokens
    
    def to_dict(self) -> dict:
        """Convert to dictionary for database storage."""
        data = self.dict()
        data['timestamp'] = self.timestamp.isoformat()
        return data
    
    @classmethod
    def from_dict(cls, data: dict) -> 'UsageRecord':
        """Create instance from dictionary."""
        if 'timestamp' in data and isinstance(data['timestamp'], str):
            data['timestamp'] = datetime.fromisoformat(data['timestamp'])
        return cls(**data)


class UsageStats(BaseModel):
    """Aggregated usage statistics."""
    
    total_requests: int = Field(0, description="Total number of requests")
    total_tokens: int = Field(0, description="Total number of tokens")
    total_input_tokens: int = Field(0, description="Total input tokens")
    total_output_tokens: int = Field(0, description="Total output tokens")
    average_response_time: float = Field(0.0, description="Average response time in milliseconds")
    success_rate: float = Field(0.0, description="Success rate as percentage")
    period_start: datetime = Field(..., description="Start of the statistics period")
    period_end: datetime = Field(..., description="End of the statistics period")
    
    class Config:
        """Pydantic configuration."""
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class ClientUsage(BaseModel):
    """Usage statistics for a specific client."""
    
    client_ip: str = Field(..., description="Client IP address")
    total_requests: int = Field(0, description="Total requests from this client")
    total_tokens: int = Field(0, description="Total tokens used by this client")
    total_input_tokens: int = Field(0, description="Total input tokens")
    total_output_tokens: int = Field(0, description="Total output tokens")
    average_response_time: float = Field(0.0, description="Average response time")
    last_request: datetime = Field(..., description="Timestamp of last request")
    
    class Config:
        """Pydantic configuration."""
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class ModelUsage(BaseModel):
    """Usage statistics for a specific model."""
    
    model_name: str = Field(..., description="Model name")
    public_name: str = Field("", description="Public name of the model")
    total_requests: int = Field(0, description="Total requests for this model")
    total_tokens: int = Field(0, description="Total tokens used by this model")
    total_input_tokens: int = Field(0, description="Total input tokens")
    total_output_tokens: int = Field(0, description="Total output tokens")
    average_response_time: float = Field(0.0, description="Average response time")
    unique_clients: int = Field(0, description="Number of unique clients using this model")
    last_request: datetime = Field(..., description="Timestamp of last request")
    
    class Config:
        """Pydantic configuration."""
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }