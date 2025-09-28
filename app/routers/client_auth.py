from fastapi import APIRouter, Depends, HTTPException, status, Body
from sqlalchemy.orm import Session
from typing import List
from core.database import get_db
from services.client_auth_service import ClientAuthService
from schemas.client import (
    ClientCreate, ClientCreateResponse, ClientAuthRequest, ClientAuthResponse,
    ClientInfo, ClientListResponse, ClientUpdateRequest
)
from core.security import require_admin_access

router = APIRouter(prefix="/client-auth", tags=["client-authentication"])


@router.post("/register", response_model=ClientCreateResponse)
async def register_client(
    request: ClientCreate = Body(...),
    db: Session = Depends(get_db)
):
    """Register a new client (Odoo instance)"""
    try:
        client_auth_service = ClientAuthService(db)
        
        # Check if client_id already exists
        existing_client = client_auth_service.get_client_by_id(request.client_id)
        if existing_client:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "code": "CLIENT_ID_EXISTS",
                    "message": "Client ID already exists",
                    "details": f"Client ID '{request.client_id}' is already registered"
                }
            )
        
        # Create new client
        client_data = client_auth_service.create_client(
            client_id=request.client_id,
            name=request.name,
            description=request.description,
            permissions=request.permissions,
            rate_limit_per_hour=request.rate_limit_per_hour
        )
        
        return ClientCreateResponse(
            client_id=client_data["client_id"],
            client_secret=client_data["client_secret"],
            name=client_data["name"],
            description=request.description,
            permissions=client_data["permissions"],
            rate_limit_per_hour=client_data["rate_limit_per_hour"]
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "code": "INTERNAL_ERROR",
                "message": "Internal server error",
                "details": str(e)
            }
        )


@router.post("/login", response_model=ClientAuthResponse)
async def authenticate_client(
    request: ClientAuthRequest = Body(...),
    db: Session = Depends(get_db)
):
    """Authenticate a client and return JWT token"""
    try:
        client_auth_service = ClientAuthService(db)
        
        # Authenticate client
        client_info = client_auth_service.authenticate_client(
            request.client_id,
            request.client_secret
        )
        
        if not client_info:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail={
                    "code": "INVALID_CREDENTIALS",
                    "message": "Invalid client credentials",
                    "details": "Client ID or secret is incorrect, or client is inactive"
                }
            )
        
        # Generate JWT token
        access_token = client_auth_service.generate_client_token(client_info)
        
        return ClientAuthResponse(
            access_token=access_token,
            expires_in=24 * 60 * 60,  # 24 hours in seconds
            client_info=client_info
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "code": "INTERNAL_ERROR",
                "message": "Internal server error",
                "details": str(e)
            }
        )


@router.get("/me")
async def get_current_client_info(
    current_client: dict = Depends(require_admin_access)
):
    """Get current client information"""
    return {
        "client_id": current_client["client_id"],
        "name": current_client["name"],
        "permissions": current_client["permissions"],
        "rate_limit_per_hour": current_client["rate_limit_per_hour"]
    }


@router.get("/clients", response_model=ClientListResponse)
async def list_clients(
    current_client: dict = Depends(require_admin_access),
    db: Session = Depends(get_db)
):
    """List all clients (admin only)"""
    try:
        client_auth_service = ClientAuthService(db)
        clients = client_auth_service.list_active_clients()
        
        client_infos = [
            ClientInfo(
                client_id=client.client_id,
                name=client.name,
                description=client.description,
                permissions=client.permissions,
                rate_limit_per_hour=client.rate_limit_per_hour,
                is_active=client.is_active,
                created_at=client.created_at,
                updated_at=client.updated_at,
                last_used_at=client.last_used_at
            )
            for client in clients
        ]
        
        return ClientListResponse(clients=client_infos, count=len(client_infos))
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "code": "INTERNAL_ERROR",
                "message": "Internal server error",
                "details": str(e)
            }
        )


@router.put("/clients/{client_id}")
async def update_client(
    client_id: str,
    request: ClientUpdateRequest = Body(...),
    current_client: dict = Depends(require_admin_access),
    db: Session = Depends(get_db)
):
    """Update client settings (admin only)"""
    try:
        client_auth_service = ClientAuthService(db)
        
        # Get client to update
        client = client_auth_service.get_client_by_id(client_id)
        if not client:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={
                    "code": "CLIENT_NOT_FOUND",
                    "message": f"Client '{client_id}' not found"
                }
            )
        
        # Update fields if provided
        if request.permissions is not None:
            client_auth_service.update_client_permissions(client_id, request.permissions)
        
        if request.is_active is not None:
            if request.is_active:
                client.is_active = True
            else:
                client_auth_service.deactivate_client(client_id)
        
        return {
            "success": True,
            "message": f"Client '{client_id}' updated successfully"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "code": "INTERNAL_ERROR",
                "message": "Internal server error",
                "details": str(e)
            }
        )
