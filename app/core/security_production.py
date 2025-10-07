from fastapi import Request, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response
import time
import hashlib
import secrets
from typing import Dict, List, Optional
from datetime import datetime, timedelta
import logging
from core.config import settings

logger = logging.getLogger(__name__)

# Rate limiting storage (in production, use Redis)
rate_limit_storage: Dict[str, List[float]] = {}
rate_limit_cleanup_threshold = 1000  # Clean up when storage gets too large


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """
    Middleware to add security headers to all responses
    """
    
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        
        # Add security headers
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"
        
        # Add HSTS header for HTTPS
        if request.url.scheme == "https":
            response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        
        # Add CSP header
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; "
            "script-src 'self' 'unsafe-inline'; "
            "style-src 'self' 'unsafe-inline'; "
            "img-src 'self' data: https:; "
            "font-src 'self'; "
            "connect-src 'self'; "
            "frame-ancestors 'none';"
        )
        
        return response


class RateLimitMiddleware(BaseHTTPMiddleware):
    """
    Rate limiting middleware
    """
    
    def __init__(self, app, calls_per_minute: int = 60, calls_per_hour: int = 1000):
        super().__init__(app)
        self.calls_per_minute = calls_per_minute
        self.calls_per_hour = calls_per_hour
    
    def _get_client_identifier(self, request: Request) -> str:
        """Get client identifier for rate limiting"""
        # Use client IP as primary identifier
        client_ip = request.client.host if request.client else "unknown"
        
        # If we have a client_id in headers, use that for authenticated requests
        auth_header = request.headers.get("authorization")
        if auth_header and auth_header.startswith("Bearer "):
            # Hash the token to create a stable identifier
            token = auth_header[7:]  # Remove "Bearer "
            client_id = hashlib.sha256(token.encode()).hexdigest()[:16]
            return f"{client_ip}:{client_id}"
        
        return client_ip
    
    def _is_rate_limited(self, client_id: str) -> bool:
        """Check if client is rate limited"""
        now = time.time()
        minute_ago = now - 60
        hour_ago = now - 3600
        
        # Get or create client's request history
        if client_id not in rate_limit_storage:
            rate_limit_storage[client_id] = []
        
        request_times = rate_limit_storage[client_id]
        
        # Remove old requests
        request_times[:] = [t for t in request_times if t > hour_ago]
        
        # Count requests in last minute and hour
        recent_requests = [t for t in request_times if t > minute_ago]
        
        # Add current request
        request_times.append(now)
        
        # Check rate limits
        if len(recent_requests) >= self.calls_per_minute:
            return True
        if len(request_times) >= self.calls_per_hour:
            return True
        
        # Cleanup old entries if storage gets too large
        if len(rate_limit_storage) > rate_limit_cleanup_threshold:
            self._cleanup_rate_limit_storage()
        
        return False
    
    def _cleanup_rate_limit_storage(self):
        """Clean up old rate limit entries"""
        now = time.time()
        hour_ago = now - 3600
        
        # Remove clients with no recent requests
        clients_to_remove = []
        for client_id, request_times in rate_limit_storage.items():
            recent_requests = [t for t in request_times if t > hour_ago]
            if not recent_requests:
                clients_to_remove.append(client_id)
        
        for client_id in clients_to_remove:
            del rate_limit_storage[client_id]
    
    async def dispatch(self, request: Request, call_next):
        # Skip rate limiting for health checks and metrics
        if request.url.path in ["/health", "/metrics", "/docs", "/openapi.json"]:
            return await call_next(request)
        
        client_id = self._get_client_identifier(request)
        
        if self._is_rate_limited(client_id):
            logger.warning(
                "Rate limit exceeded",
                client_id=client_id,
                path=request.url.path,
                method=request.method
            )
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail={
                    "code": "RATE_LIMIT_EXCEEDED",
                    "message": "Too many requests. Please try again later.",
                    "retry_after": 60
                },
                headers={"Retry-After": "60"}
            )
        
        response = await call_next(request)
        
        # Add rate limit headers
        now = time.time()
        minute_ago = now - 60
        hour_ago = now - 3600
        
        if client_id in rate_limit_storage:
            request_times = rate_limit_storage[client_id]
            recent_requests = [t for t in request_times if t > minute_ago]
            
            response.headers["X-RateLimit-Limit-Minute"] = str(self.calls_per_minute)
            response.headers["X-RateLimit-Remaining-Minute"] = str(max(0, self.calls_per_minute - len(recent_requests)))
            response.headers["X-RateLimit-Reset-Minute"] = str(int(minute_ago + 60))
            
            hour_requests = [t for t in request_times if t > hour_ago]
            response.headers["X-RateLimit-Limit-Hour"] = str(self.calls_per_hour)
            response.headers["X-RateLimit-Remaining-Hour"] = str(max(0, self.calls_per_hour - len(hour_requests)))
            response.headers["X-RateLimit-Reset-Hour"] = str(int(hour_ago + 3600))
        
        return response


class RequestValidationMiddleware(BaseHTTPMiddleware):
    """
    Middleware for request validation and sanitization
    """
    
    def __init__(self, app, max_request_size: int = 10 * 1024 * 1024):  # 10MB
        super().__init__(app)
        self.max_request_size = max_request_size
    
    async def dispatch(self, request: Request, call_next):
        # Check request size
        content_length = request.headers.get("content-length")
        if content_length and int(content_length) > self.max_request_size:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail={
                    "code": "REQUEST_TOO_LARGE",
                    "message": f"Request size exceeds maximum allowed size of {self.max_request_size} bytes"
                }
            )
        
        # Validate content type for POST/PUT requests
        if request.method in ["POST", "PUT", "PATCH"]:
            content_type = request.headers.get("content-type", "")
            if not content_type.startswith(("application/json", "multipart/form-data", "application/x-www-form-urlencoded")):
                logger.warning(
                    "Invalid content type",
                    content_type=content_type,
                    path=request.url.path,
                    method=request.method
                )
        
        # Check for suspicious patterns in URL
        suspicious_patterns = ["../", "./", "\\", "%2e%2e", "%2f", "%5c"]
        url_str = str(request.url)
        if any(pattern in url_str.lower() for pattern in suspicious_patterns):
            logger.warning(
                "Suspicious URL pattern detected",
                url=url_str,
                client_ip=request.client.host if request.client else None
            )
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "code": "INVALID_REQUEST",
                    "message": "Invalid request format"
                }
            )
        
        return await call_next(request)


class SecurityAuditMiddleware(BaseHTTPMiddleware):
    """
    Middleware for security audit logging
    """
    
    async def dispatch(self, request: Request, call_next):
        start_time = time.time()
        
        # Log security-relevant events
        security_headers = {
            "user_agent": request.headers.get("user-agent"),
            "x_forwarded_for": request.headers.get("x-forwarded-for"),
            "x_real_ip": request.headers.get("x-real-ip"),
            "authorization": "Bearer ***" if request.headers.get("authorization") else None
        }
        
        response = await call_next(request)
        
        # Log failed authentication attempts
        if response.status_code == status.HTTP_401_UNAUTHORIZED:
            logger.warning(
                "Authentication failure",
                path=request.url.path,
                method=request.method,
                client_ip=request.client.host if request.client else None,
                user_agent=security_headers["user_agent"]
            )
        
        # Log authorization failures
        elif response.status_code == status.HTTP_403_FORBIDDEN:
            logger.warning(
                "Authorization failure",
                path=request.url.path,
                method=request.method,
                client_ip=request.client.host if request.client else None,
                user_agent=security_headers["user_agent"]
            )
        
        # Log rate limiting events
        elif response.status_code == status.HTTP_429_TOO_MANY_REQUESTS:
            logger.warning(
                "Rate limit triggered",
                path=request.url.path,
                method=request.method,
                client_ip=request.client.host if request.client else None
            )
        
        # Log suspicious activity
        elif response.status_code >= 400:
            duration = time.time() - start_time
            logger.info(
                "Request error",
                path=request.url.path,
                method=request.method,
                status_code=response.status_code,
                duration_seconds=duration,
                client_ip=request.client.host if request.client else None
            )
        
        return response


def setup_security_middleware(app):
    """
    Setup all security middleware for the FastAPI application
    """
    from core.config_production import get_settings
    settings = get_settings()
    
    # Trusted hosts middleware
    trusted_hosts = settings.TRUSTED_HOSTS or ["*"]
    app.add_middleware(
        TrustedHostMiddleware,
        allowed_hosts=trusted_hosts
    )
    
    # CORS middleware
    cors_origins = settings.CORS_ORIGINS or ["*"]
    app.add_middleware(
        CORSMiddleware,
        allow_origins=cors_origins,
        allow_credentials=settings.CORS_ALLOW_CREDENTIALS,
        allow_methods=settings.CORS_ALLOW_METHODS,
        allow_headers=settings.CORS_ALLOW_HEADERS,
    )
    
    # Security headers middleware
    app.add_middleware(SecurityHeadersMiddleware)
    
    # Request validation middleware
    app.add_middleware(RequestValidationMiddleware, max_request_size=settings.MAX_REQUEST_SIZE)
    
    # Rate limiting middleware
    app.add_middleware(
        RateLimitMiddleware,
        calls_per_minute=settings.RATE_LIMIT_PER_MINUTE,
        calls_per_hour=settings.RATE_LIMIT_PER_HOUR
    )
    
    # Security audit middleware
    app.add_middleware(SecurityAuditMiddleware)
    
    logger.info("Security middleware setup completed")


class APIKeySecurity:
    """
    Enhanced API key security for production
    """
    
    @staticmethod
    def generate_secure_api_key() -> str:
        """Generate a secure API key"""
        return secrets.token_urlsafe(32)
    
    @staticmethod
    def hash_api_key(api_key: str) -> str:
        """Hash an API key for storage"""
        return hashlib.sha256(api_key.encode()).hexdigest()
    
    @staticmethod
    def verify_api_key(provided_key: str, stored_hash: str) -> bool:
        """Verify an API key against its hash"""
        provided_hash = hashlib.sha256(provided_key.encode()).hexdigest()
        return provided_hash == stored_hash


class SessionSecurity:
    """
    Session security utilities
    """
    
    @staticmethod
    def generate_session_token() -> str:
        """Generate a secure session token"""
        return secrets.token_urlsafe(32)
    
    @staticmethod
    def is_session_valid(created_at: datetime, max_age_hours: int = 24) -> bool:
        """Check if a session is still valid"""
        max_age = timedelta(hours=max_age_hours)
        return datetime.utcnow() - created_at < max_age


# Security configuration
SECURITY_CONFIG = {
    "max_request_size": 10 * 1024 * 1024,  # 10MB
    "rate_limit_per_minute": 60,
    "rate_limit_per_hour": 1000,
    "session_max_age_hours": 24,
    "api_key_length": 32,
    "trusted_hosts": ["localhost", "127.0.0.1", "*.yourdomain.com"],
    "cors_origins": ["http://localhost:3000", "https://yourdomain.com"],
}
