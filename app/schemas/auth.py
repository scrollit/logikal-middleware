from pydantic import BaseModel
from typing import Optional
from datetime import datetime


class LoginRequest(BaseModel):
    """Request schema for authentication"""
    base_url: str
    username: str
    password: str


class LoginResponse(BaseModel):
    """Response schema for successful authentication"""
    success: bool = True
    token: str
    expires_at: datetime
    message: str = "Authentication successful"


class ErrorResponse(BaseModel):
    """Response schema for errors"""
    success: bool = False
    error: dict
    timestamp: datetime


class ConnectionTestResponse(BaseModel):
    """Response schema for connection test"""
    success: bool
    message: str
    timestamp: datetime
