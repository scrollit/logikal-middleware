from fastapi import APIRouter, Depends, HTTPException, Body
from sqlalchemy.orm import Session
from typing import List, Optional
from pydantic import BaseModel
from core.database import get_db
from models.client import Client
from services.client_auth_service import ClientAuthService
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/admin/clients", tags=["client-management"])


# Pydantic schemas
class ClientResponse(BaseModel):
    id: int
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


class ClientCreateRequest(BaseModel):
    name: str
    description: Optional[str] = None
    permissions: List[str] = []
    rate_limit_per_hour: int = 1000


class ClientCreateResponse(BaseModel):
    client: ClientResponse
    client_secret: str  # Only returned on creation
    message: str


class ClientUpdateRequest(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    permissions: Optional[List[str]] = None
    rate_limit_per_hour: Optional[int] = None
    is_active: Optional[bool] = None


class ClientRegenerateSecretResponse(BaseModel):
    client_id: str
    client_secret: str
    message: str


@router.get("/", response_model=List[ClientResponse])
async def list_clients(
    skip: int = 0,
    limit: int = 100,
    active_only: bool = False,
    db: Session = Depends(get_db)
):
    """Get all registered clients"""
    try:
        query = db.query(Client)
        
        if active_only:
            query = query.filter(Client.is_active == True)
        
        clients = query.offset(skip).limit(limit).all()
        return clients
        
    except Exception as e:
        logger.error(f"Error fetching clients: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{client_id}", response_model=ClientResponse)
async def get_client(
    client_id: str,
    db: Session = Depends(get_db)
):
    """Get a specific client by client_id"""
    try:
        client = db.query(Client).filter(Client.client_id == client_id).first()
        
        if not client:
            raise HTTPException(status_code=404, detail=f"Client {client_id} not found")
        
        return client
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching client {client_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/", response_model=ClientCreateResponse)
async def create_client(
    request: ClientCreateRequest = Body(...),
    db: Session = Depends(get_db)
):
    """Create a new client with auto-generated credentials"""
    try:
        client_auth_service = ClientAuthService(db)
        
        # Create client with generated credentials
        result = client_auth_service.create_client(
            client_id=f"client_{datetime.utcnow().timestamp()}".replace(".", "_"),
            name=request.name,
            description=request.description,
            permissions=request.permissions,
            rate_limit_per_hour=request.rate_limit_per_hour
        )
        
        # Fetch the created client
        client = db.query(Client).filter(Client.client_id == result["client_id"]).first()
        
        return ClientCreateResponse(
            client=client,
            client_secret=result["client_secret"],
            message="Client created successfully. Save the client_secret as it cannot be retrieved later."
        )
        
    except Exception as e:
        logger.error(f"Error creating client: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/{client_id}", response_model=ClientResponse)
async def update_client(
    client_id: str,
    request: ClientUpdateRequest = Body(...),
    db: Session = Depends(get_db)
):
    """Update an existing client"""
    try:
        client = db.query(Client).filter(Client.client_id == client_id).first()
        
        if not client:
            raise HTTPException(status_code=404, detail=f"Client {client_id} not found")
        
        # Update fields if provided
        if request.name is not None:
            client.name = request.name
        if request.description is not None:
            client.description = request.description
        if request.permissions is not None:
            client.permissions = request.permissions
        if request.rate_limit_per_hour is not None:
            client.rate_limit_per_hour = request.rate_limit_per_hour
        if request.is_active is not None:
            client.is_active = request.is_active
        
        client.updated_at = datetime.utcnow()
        db.commit()
        db.refresh(client)
        
        return client
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating client {client_id}: {str(e)}")
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{client_id}/regenerate-secret", response_model=ClientRegenerateSecretResponse)
async def regenerate_client_secret(
    client_id: str,
    db: Session = Depends(get_db)
):
    """Regenerate the client secret for a client"""
    try:
        client = db.query(Client).filter(Client.client_id == client_id).first()
        
        if not client:
            raise HTTPException(status_code=404, detail=f"Client {client_id} not found")
        
        client_auth_service = ClientAuthService(db)
        
        # Generate new secret
        new_secret = client_auth_service.generate_client_secret()
        client.client_secret_hash = client_auth_service.hash_client_secret(new_secret)
        client.updated_at = datetime.utcnow()
        
        db.commit()
        
        return ClientRegenerateSecretResponse(
            client_id=client_id,
            client_secret=new_secret,
            message="Client secret regenerated successfully. Save it as it cannot be retrieved later."
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error regenerating secret for client {client_id}: {str(e)}")
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{client_id}")
async def delete_client(
    client_id: str,
    db: Session = Depends(get_db)
):
    """Delete a client"""
    try:
        client = db.query(Client).filter(Client.client_id == client_id).first()
        
        if not client:
            raise HTTPException(status_code=404, detail=f"Client {client_id} not found")
        
        db.delete(client)
        db.commit()
        
        return {"message": f"Client {client_id} deleted successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting client {client_id}: {str(e)}")
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))

