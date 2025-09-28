from pydantic import BaseModel, EmailStr
from typing import List, Optional
from datetime import datetime


class ClientCreate(BaseModel):
    """Schema for creating a new client"""
    client_id: str
    name: str
    description: Optional[str] = None
    permissions: Optional[List[str]] = ["projects:read", "elevations:read"]
    rate_limit_per_hour: Optional[int] = 1000


class ClientCreateResponse(BaseModel):
    """Response schema for client creation"""
    client_id: str
    client_secret: str  # Only returned once during creation
    name: str
    description: Optional[str]
    permissions: List[str]
    rate_limit_per_hour: int
    message: str = "Client created successfully. Store the client_secret securely."


class ClientAuthRequest(BaseModel):
    """Schema for client authentication"""
    client_id: str
    client_secret: str


class ClientAuthResponse(BaseModel):
    """Response schema for client authentication"""
    access_token: str
    token_type: str = "bearer"
    expires_in: int  # seconds
    client_info: dict


class ClientInfo(BaseModel):
    """Schema for client information"""
    client_id: str
    name: str
    description: Optional[str]
    permissions: List[str]
    rate_limit_per_hour: int
    is_active: bool
    created_at: datetime
    updated_at: datetime
    last_used_at: Optional[datetime]
    
    class Config:
        from_attributes = True


class ClientListResponse(BaseModel):
    """Response schema for client list"""
    clients: List[ClientInfo]
    count: int


class ClientUpdateRequest(BaseModel):
    """Schema for updating client permissions"""
    permissions: Optional[List[str]] = None
    rate_limit_per_hour: Optional[int] = None
    is_active: Optional[bool] = None
