from pydantic import BaseModel
from typing import Optional
from datetime import datetime


class AdminLoginRequest(BaseModel):
    username: str
    password: str


class AdminLoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_at: datetime
    message: str


class AdminSession(BaseModel):
    username: str
    is_authenticated: bool = True
    login_time: datetime
    expires_at: datetime


class AdminLogoutResponse(BaseModel):
    message: str
