import hashlib
import secrets
from datetime import datetime, timedelta
from typing import Optional, Dict
from sqlalchemy.orm import Session
from jose import jwt, JWTError
from core.config import settings
from schemas.admin_auth import AdminLoginRequest, AdminLoginResponse, AdminSession
from passlib.context import CryptContext

# Password hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# JWT settings
SECRET_KEY = settings.JWT_SECRET_KEY
ALGORITHM = "HS256"
# Get session expire hours from environment or use default
import os
ACCESS_TOKEN_EXPIRE_HOURS = int(os.getenv("ADMIN_SESSION_EXPIRE_HOURS", "8"))  # Admin sessions expire in 8 hours


class AdminAuthService:
    """Service for managing admin authentication"""
    
    def __init__(self, db: Session):
        self.db = db
        # Get admin username from environment or use default
        import os
        self.admin_username = os.getenv("ADMIN_USERNAME", "admin")
        self.admin_password_hash = self._get_default_admin_hash()
    
    def _get_default_admin_hash(self) -> str:
        """Get the default admin password hash"""
        # Get admin password from environment or use default
        import os
        admin_password = os.getenv("ADMIN_PASSWORD", "admin123")
        return pwd_context.hash(admin_password)
    
    def verify_password(self, plain_password: str, hashed_password: str) -> bool:
        """Verify a password against its hash"""
        return pwd_context.verify(plain_password, hashed_password)
    
    def create_access_token(self, username: str) -> str:
        """Create a JWT access token for admin"""
        expire = datetime.utcnow() + timedelta(hours=ACCESS_TOKEN_EXPIRE_HOURS)
        to_encode = {
            "sub": username,
            "exp": expire,
            "type": "admin",
            "permissions": ["admin:read", "admin:write"]
        }
        encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
        return encoded_jwt
    
    def verify_token(self, token: str) -> Optional[Dict]:
        """Verify and decode a JWT token"""
        try:
            payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
            username: str = payload.get("sub")
            token_type: str = payload.get("type")
            
            if username is None or token_type != "admin":
                return None
                
            return {
                "username": username,
                "permissions": payload.get("permissions", []),
                "exp": payload.get("exp")
            }
        except JWTError:
            return None
    
    async def authenticate_admin(self, login_request: AdminLoginRequest) -> Optional[AdminLoginResponse]:
        """Authenticate admin user"""
        # Check username
        if login_request.username != self.admin_username:
            return None
        
        # Verify password
        if not self.verify_password(login_request.password, self.admin_password_hash):
            return None
        
        # Create access token
        access_token = self.create_access_token(login_request.username)
        expires_at = datetime.utcnow() + timedelta(hours=ACCESS_TOKEN_EXPIRE_HOURS)
        
        return AdminLoginResponse(
            access_token=access_token,
            expires_at=expires_at,
            message="Admin authentication successful"
        )
    
    def validate_admin_session(self, token: str) -> Optional[AdminSession]:
        """Validate admin session token"""
        token_data = self.verify_token(token)
        if not token_data:
            return None
        
        # Check if token is expired
        if datetime.utcnow().timestamp() > token_data["exp"]:
            return None
        
        return AdminSession(
            username=token_data["username"],
            login_time=datetime.utcnow(),  # This would be stored in a real session
            expires_at=datetime.fromtimestamp(token_data["exp"])
        )
