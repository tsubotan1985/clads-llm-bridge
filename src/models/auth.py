"""Authentication data models."""

from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field


class AuthConfig(BaseModel):
    """Authentication configuration model."""
    
    id: int = Field(1, description="Always 1 for singleton config")
    password_hash: str = Field(..., description="Hashed password")
    created_at: datetime = Field(default_factory=datetime.utcnow, description="Creation timestamp")
    updated_at: datetime = Field(default_factory=datetime.utcnow, description="Last update timestamp")
    
    class Config:
        """Pydantic configuration."""
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }
    
    def to_dict(self) -> dict:
        """Convert to dictionary for database storage."""
        return {
            'id': self.id,
            'password_hash': self.password_hash,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat()
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> 'AuthConfig':
        """Create instance from dictionary."""
        if 'created_at' in data and isinstance(data['created_at'], str):
            data['created_at'] = datetime.fromisoformat(data['created_at'])
        if 'updated_at' in data and isinstance(data['updated_at'], str):
            data['updated_at'] = datetime.fromisoformat(data['updated_at'])
        return cls(**data)


class LoginRequest(BaseModel):
    """Login request model."""
    
    password: str = Field(..., description="Password for authentication")


class ChangePasswordRequest(BaseModel):
    """Change password request model."""
    
    old_password: str = Field(..., description="Current password")
    new_password: str = Field(..., description="New password")
    
    class Config:
        """Pydantic configuration."""
        min_anystr_length = 1


class AuthSession(BaseModel):
    """Authentication session model."""
    
    authenticated: bool = Field(False, description="Whether user is authenticated")
    login_time: Optional[datetime] = Field(None, description="When user logged in")
    
    class Config:
        """Pydantic configuration."""
        json_encoders = {
            datetime: lambda v: v.isoformat() if v else None
        }