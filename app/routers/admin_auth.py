from fastapi import APIRouter, Depends, HTTPException, status, Request, Response
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from typing import Optional
from core.database import get_db
from schemas.admin_auth import AdminLoginRequest, AdminLoginResponse, AdminLogoutResponse
from services.admin_auth_service import AdminAuthService

router = APIRouter(prefix="/admin", tags=["admin authentication"])
security = HTTPBearer(auto_error=False)


@router.post("/login", response_model=AdminLoginResponse)
async def admin_login(
    login_request: AdminLoginRequest,
    db: Session = Depends(get_db)
):
    """Authenticate admin user"""
    auth_service = AdminAuthService(db)
    
    result = await auth_service.authenticate_admin(login_request)
    if not result:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid admin credentials"
        )
    
    return result


@router.post("/logout", response_model=AdminLogoutResponse)
async def admin_logout():
    """Logout admin user (client should remove token)"""
    return AdminLogoutResponse(message="Admin logged out successfully")


@router.get("/verify")
async def verify_admin_session(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
    db: Session = Depends(get_db)
):
    """Verify admin session token"""
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="No authentication token provided"
        )
    
    auth_service = AdminAuthService(db)
    session = auth_service.validate_admin_session(credentials.credentials)
    
    if not session:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired admin session"
        )
    
    return {
        "username": session.username,
        "is_authenticated": session.is_authenticated,
        "expires_at": session.expires_at
    }
