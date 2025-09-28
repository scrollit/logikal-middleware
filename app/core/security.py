from fastapi import HTTPException, status, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from typing import Dict, Optional
from core.database import get_db
from services.client_auth_service import ClientAuthService

# HTTP Bearer token scheme
security = HTTPBearer()


async def get_current_client(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db)
) -> Dict:
    """
    Dependency to get current authenticated client from JWT token
    """
    client_auth_service = ClientAuthService(db)
    
    # Extract token from Authorization header
    token = credentials.credentials
    
    # Validate token and get client info
    client_info = client_auth_service.validate_client_token(token)
    
    if client_info is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    return client_info


def require_permission(required_permission: str):
    """
    Decorator factory for permission-based access control
    """
    def permission_checker(current_client: Dict = Depends(get_current_client)) -> Dict:
        if required_permission not in current_client.get("permissions", []):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Permission '{required_permission}' required"
            )
        return current_client
    
    return permission_checker


# Common permission dependencies
def require_projects_read(current_client: Dict = Depends(get_current_client)) -> Dict:
    """Require projects:read permission"""
    if "projects:read" not in current_client.get("permissions", []):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Permission 'projects:read' required"
        )
    return current_client


def require_elevations_read(current_client: Dict = Depends(get_current_client)) -> Dict:
    """Require elevations:read permission"""
    if "elevations:read" not in current_client.get("permissions", []):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Permission 'elevations:read' required"
        )
    return current_client


def require_admin_access(current_client: Dict = Depends(get_current_client)) -> Dict:
    """Require admin:read permission"""
    if "admin:read" not in current_client.get("permissions", []):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Permission 'admin:read' required"
        )
    return current_client


# Optional client dependency (for endpoints that work with or without auth)
async def get_optional_client(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
    db: Session = Depends(get_db)
) -> Optional[Dict]:
    """
    Optional client authentication - returns None if no token provided
    """
    if not credentials:
        return None
    
    try:
        client_auth_service = ClientAuthService(db)
        token = credentials.credentials
        return client_auth_service.validate_client_token(token)
    except:
        return None
