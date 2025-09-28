import hashlib
import secrets
from datetime import datetime, timedelta
from typing import Optional, Dict, List
from sqlalchemy.orm import Session
from jose import jwt, JWTError
from core.config import settings
from models.client import Client

# JWT settings
SECRET_KEY = settings.JWT_SECRET_KEY
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_HOURS = 24


class ClientAuthService:
    """Service for managing client authentication and JWT tokens"""
    
    def __init__(self, db: Session):
        self.db = db
    
    def hash_client_secret(self, client_secret: str) -> str:
        """Hash a client secret for storage using SHA256"""
        return hashlib.sha256(client_secret.encode()).hexdigest()
    
    def verify_client_secret(self, plain_secret: str, hashed_secret: str) -> bool:
        """Verify a client secret against its hash"""
        return self.hash_client_secret(plain_secret) == hashed_secret
    
    def generate_client_secret(self) -> str:
        """Generate a secure random client secret"""
        # Generate 24 bytes (48 characters base64) to stay under bcrypt's 72 byte limit
        return secrets.token_urlsafe(24)
    
    def create_client(self, client_id: str, name: str, description: str = None, 
                     permissions: List[str] = None, rate_limit_per_hour: int = 1000) -> Dict:
        """Create a new client with generated secret"""
        if permissions is None:
            permissions = ["projects:read", "elevations:read"]
        
        # Generate client secret
        client_secret = self.generate_client_secret()
        client_secret_hash = self.hash_client_secret(client_secret)
        
        # Create client record
        client = Client(
            client_id=client_id,
            client_secret_hash=client_secret_hash,
            name=name,
            description=description,
            permissions=permissions,
            rate_limit_per_hour=rate_limit_per_hour,
            is_active=True
        )
        
        self.db.add(client)
        self.db.commit()
        self.db.refresh(client)
        
        return {
            "client_id": client_id,
            "client_secret": client_secret,  # Only returned once during creation
            "name": name,
            "permissions": permissions,
            "rate_limit_per_hour": rate_limit_per_hour
        }
    
    def authenticate_client(self, client_id: str, client_secret: str) -> Optional[Dict]:
        """Authenticate a client and return client info if valid"""
        client = self.db.query(Client).filter(
            Client.client_id == client_id,
            Client.is_active == True
        ).first()
        
        if not client:
            return None
        
        if not self.verify_client_secret(client_secret, client.client_secret_hash):
            return None
        
        # Update last used timestamp
        client.last_used_at = datetime.utcnow()
        self.db.commit()
        
        return {
            "client_id": client.client_id,
            "name": client.name,
            "permissions": client.permissions,
            "rate_limit_per_hour": client.rate_limit_per_hour
        }
    
    def generate_client_token(self, client_info: Dict) -> str:
        """Generate JWT token for authenticated client"""
        now = datetime.utcnow()
        expire = now + timedelta(hours=ACCESS_TOKEN_EXPIRE_HOURS)
        
        payload = {
            "client_id": client_info["client_id"],
            "name": client_info["name"],
            "permissions": client_info["permissions"],
            "rate_limit_per_hour": client_info["rate_limit_per_hour"],
            "exp": expire,
            "iat": now
        }
        
        return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)
    
    def validate_client_token(self, token: str) -> Optional[Dict]:
        """Validate JWT token and return client info"""
        try:
            payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
            client_id = payload.get("client_id")
            
            if client_id is None:
                return None
            
            # Verify client still exists and is active
            client = self.db.query(Client).filter(
                Client.client_id == client_id,
                Client.is_active == True
            ).first()
            
            if not client:
                return None
            
            return {
                "client_id": payload["client_id"],
                "name": payload["name"],
                "permissions": payload["permissions"],
                "rate_limit_per_hour": payload["rate_limit_per_hour"]
            }
        except JWTError:
            return None
    
    def get_client_by_id(self, client_id: str) -> Optional[Client]:
        """Get client record by client_id"""
        return self.db.query(Client).filter(Client.client_id == client_id).first()
    
    def update_client_permissions(self, client_id: str, permissions: List[str]) -> bool:
        """Update client permissions"""
        client = self.get_client_by_id(client_id)
        if not client:
            return False
        
        client.permissions = permissions
        client.updated_at = datetime.utcnow()
        self.db.commit()
        return True
    
    def deactivate_client(self, client_id: str) -> bool:
        """Deactivate a client"""
        client = self.get_client_by_id(client_id)
        if not client:
            return False
        
        client.is_active = False
        client.updated_at = datetime.utcnow()
        self.db.commit()
        return True
    
    def list_active_clients(self) -> List[Client]:
        """List all active clients"""
        return self.db.query(Client).filter(Client.is_active == True).all()
