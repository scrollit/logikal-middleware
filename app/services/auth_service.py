import aiohttp
import time
import logging
from datetime import datetime, timedelta
from typing import Optional, Tuple
from sqlalchemy.orm import Session
from core.config import settings
from core.retry import retry_async, auth_retry_config, auth_rate_limiter
from models.session import Session as SessionModel
from models.api_log import ApiLog

logger = logging.getLogger(__name__)


class AuthService:
    """Service for handling Logikal API authentication"""
    
    def __init__(self, db: Session):
        self.db = db
        self.session_token: Optional[str] = None
        self.current_directory: Optional[str] = None
        self.current_project: Optional[str] = None
        
    @retry_async(config=auth_retry_config, rate_limiter=auth_rate_limiter)
    async def _authenticate_request(self, url: str, payload: dict) -> Tuple[bool, str, dict]:
        """Internal method to make the actual authentication request with retry logic"""
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=payload, timeout=30) as response:
                response_text = await response.text()
                
                if response.status == 200:
                    data = await response.json()
                    return True, "Authentication successful", data
                else:
                    error_msg = f"Authentication failed: {response.status} - {response_text}"
                    raise Exception(error_msg)
    
    async def authenticate(self, base_url: str, username: str, password: str) -> Tuple[bool, str]:
        """Authenticate with Logikal API and return session token"""
        url = f"{base_url.rstrip('/')}/auth"
        payload = {
            "username": username,
            "password": password,
            "erp": True
        }
        
        start_time = time.time()
        logger.info(f"Attempting authentication for user: {username}")
        
        try:
            success, message, data = await self._authenticate_request(url, payload)
            duration = int((time.time() - start_time) * 1000)
            
            if success:
                # Check if response has expected structure
                if 'data' in data and 'token' in data['data']:
                    self.session_token = data['data']['token']
                    # Reset navigation state on new authentication
                    self.current_directory = None
                    self.current_project = None
                    logger.info("Authentication successful")
                    
                    # Calculate expiration time (assuming 24 hours)
                    expires_at = datetime.utcnow() + timedelta(hours=24)
                    
                    # Store session in database
                    await self._store_session(
                        token=self.session_token,
                        username=username,
                        base_url=base_url,
                        expires_at=expires_at
                    )
                    
                    # Log successful authentication
                    await self._log_api_call(
                        operation='login',
                        status='success',
                        response_code=200,
                        duration=duration,
                        request_url=url,
                        request_method='POST',
                        request_payload=payload,
                        response_body=str(data),
                        response_summary=f"Authenticated user: {data['data'].get('username', 'Unknown')}"
                    )
                    
                    return True, self.session_token
                else:
                    error_msg = f"Unexpected response structure: {data}"
                    logger.error(error_msg)
                    await self._log_api_call(
                        operation='login',
                        status='failed',
                        response_code=200,
                        error_message=error_msg,
                        duration=duration,
                        request_url=url,
                        request_method='POST',
                        request_payload=payload,
                        response_body=str(data),
                        response_summary="Authentication failed - unexpected response structure"
                    )
                    return False, error_msg
            else:
                return False, message
                        
        except Exception as e:
            duration = int((time.time() - start_time) * 1000)
            error_msg = f"Authentication error: {str(e)}"
            logger.error(error_msg)
            
            # Log connection error
            await self._log_api_call(
                operation='login',
                status='failed',
                response_code=0,
                error_message=error_msg,
                duration=duration,
                request_url=url,
                request_method='POST',
                request_payload=payload,
                response_body=None,
                response_summary="Authentication error"
            )
            
            return False, error_msg
    
    async def test_connection(self, base_url: str, username: str, password: str) -> Tuple[bool, str]:
        """Test connection to Logikal API"""
        try:
            success, message = await self.authenticate(base_url, username, password)
            if success:
                await self.logout()
                return True, "Connection test successful"
            else:
                return False, f"Connection test failed: {message}"
        except Exception as e:
            return False, f"Connection test error: {str(e)}"
    
    async def logout(self):
        """Terminate current session"""
        if not self.session_token:
            logger.warning("No active session to logout")
            return
            
        # Mark session as inactive in database
        session_record = self.db.query(SessionModel).filter(
            SessionModel.token == self.session_token
        ).first()
        
        if session_record:
            session_record.is_active = False
            self.db.commit()
        
        self.session_token = None
        self.current_directory = None
        self.current_project = None
        logger.info("Session terminated")
    
    async def _store_session(self, token: str, username: str, base_url: str, expires_at: datetime):
        """Store session information in database"""
        try:
            # Check if session already exists
            existing_session = self.db.query(SessionModel).filter(
                SessionModel.token == token
            ).first()
            
            if existing_session:
                # Update existing session
                existing_session.username = username
                existing_session.base_url = base_url
                existing_session.expires_at = expires_at
                existing_session.is_active = True
            else:
                # Create new session
                session_record = SessionModel(
                    token=token,
                    username=username,
                    base_url=base_url,
                    expires_at=expires_at,
                    is_active=True
                )
                self.db.add(session_record)
            
            self.db.commit()
            logger.info("Session stored in database")
            
        except Exception as e:
            logger.error(f"Failed to store session: {str(e)}")
            self.db.rollback()
    
    async def _log_api_call(self, operation: str, status: str, response_code: int, 
                           duration: int, request_url: str = None, request_method: str = None,
                           request_payload: dict = None, response_body: str = None,
                           response_summary: str = None, error_message: str = None):
        """Log API call to database"""
        try:
            # Extract endpoint from URL
            endpoint = request_url.split('/')[-1] if request_url else operation
            
            api_log = ApiLog(
                endpoint=endpoint,
                method=request_method or 'POST',
                status_code=response_code,
                response_time_ms=duration,
                success=(status == 'success'),
                error_message=error_message,
                request_url=request_url,
                request_method=request_method,
                request_payload=str(request_payload) if request_payload else None,
                response_body=response_body,
                response_summary=response_summary
            )
            
            self.db.add(api_log)
            self.db.commit()
            
        except Exception as e:
            logger.error(f"Failed to log API call: {str(e)}")
            self.db.rollback()
    
    async def reset_navigation(self, base_url: str, username: str, password: str) -> Tuple[bool, str]:
        """Reset navigation by re-authenticating to return to root directory context"""
        logger.info("Resetting navigation by re-authenticating")
        
        # Clear current session state
        self.session_token = None
        self.token_expires_at = None
        self.current_directory = None
        self.current_project = None
        
        # Re-authenticate to get fresh session
        success, message = await self.authenticate(base_url, username, password)
        
        if success:
            logger.info("Navigation reset successful - returned to root directory context")
            return True, "Navigation reset successfully"
        else:
            logger.error(f"Navigation reset failed: {message}")
            return False, f"Navigation reset failed: {message}"
