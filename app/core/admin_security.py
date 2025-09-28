from fastapi import HTTPException, status, Depends, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from typing import Optional, Dict
from services.admin_auth_service import AdminAuthService
from core.database import get_db
from sqlalchemy.orm import Session

# HTTP Bearer token scheme
security = HTTPBearer(auto_error=False)


async def get_current_admin(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
    db: Session = Depends(get_db)
) -> Dict:
    """
    Dependency to get current authenticated admin from JWT token or session
    """
    # First try to get token from Authorization header
    if credentials:
        auth_service = AdminAuthService(db)
        session = auth_service.validate_admin_session(credentials.credentials)
        if session:
            return {
                "username": session.username,
                "permissions": ["admin:read", "admin:write"],
                "is_authenticated": True
            }
    
    # If no valid token, check for session cookie
    session_token = request.cookies.get("admin_session")
    if session_token:
        auth_service = AdminAuthService(db)
        session = auth_service.validate_admin_session(session_token)
        if session:
            return {
                "username": session.username,
                "permissions": ["admin:read", "admin:write"],
                "is_authenticated": True
            }
    
    # No valid authentication found
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Admin authentication required",
        headers={"WWW-Authenticate": "Bearer"},
    )


def require_admin_auth(current_admin: Dict = Depends(get_current_admin)) -> Dict:
    """Require admin authentication"""
    if not current_admin.get("is_authenticated", False):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Admin authentication required"
        )
    return current_admin
