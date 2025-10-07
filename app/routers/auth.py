from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
from core.database import get_db
from schemas.auth import LoginRequest, LoginResponse, ErrorResponse, ConnectionTestResponse
from services.auth_service import AuthService

router = APIRouter(prefix="/auth", tags=["authentication"])


@router.post("/login", response_model=LoginResponse)
async def login(request: LoginRequest, db: Session = Depends(get_db)):
    """Authenticate with Logikal API"""
    try:
        auth_service = AuthService(db)
        success, result = await auth_service.authenticate(
            base_url=request.base_url,
            username=request.username,
            password=request.password
        )
        
        if success:
            # Calculate expiration time (assuming 24 hours)
            expires_at = datetime.utcnow() + timedelta(hours=24)
            return LoginResponse(
                token=result,
                expires_at=expires_at,
                message="Authentication successful"
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail={
                    "code": "AUTHENTICATION_FAILED",
                    "message": "Invalid credentials",
                    "details": result
                }
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


@router.get("/test", response_model=ConnectionTestResponse)
async def test_connection(
    base_url: str,
    username: str,
    password: str,
    db: Session = Depends(get_db)
):
    """Test connection to Logikal API"""
    import logging
    logger = logging.getLogger(__name__)
    
    try:
        logger.info(f"Testing connection to: {base_url}")
        logger.info(f"Username: {username}")
        
        # Simple connection test without database logging for now
        import aiohttp
        import asyncio
        
        url = f"{base_url.rstrip('/')}/auth"
        payload = {
            "username": username,
            "password": password,
            "erp": True
        }
        
        logger.info(f"Making request to: {url}")
        
        async with aiohttp.ClientSession() as session:
            try:
                async with session.post(url, json=payload, timeout=10) as response:
                    logger.info(f"Response status: {response.status}")
                    
                    if response.status == 200:
                        data = await response.json()
                        logger.info(f"Response data keys: {list(data.keys()) if isinstance(data, dict) else 'Not a dict'}")
                        
                        if 'data' in data and 'token' in data['data']:
                            logger.info("Connection test successful")
                            return ConnectionTestResponse(
                                success=True,
                                message="Connection test successful",
                                timestamp=datetime.utcnow()
                            )
                        else:
                            logger.warning(f"Unexpected response structure: {data}")
                            return ConnectionTestResponse(
                                success=False,
                                message=f"Unexpected response structure: {data}",
                                timestamp=datetime.utcnow()
                            )
                    else:
                        response_text = await response.text()
                        logger.error(f"Authentication failed: {response.status} - {response_text}")
                        return ConnectionTestResponse(
                            success=False,
                            message=f"Authentication failed: {response.status} - {response_text}",
                            timestamp=datetime.utcnow()
                        )
            except asyncio.TimeoutError as e:
                logger.error(f"Connection timeout: {str(e)}")
                return ConnectionTestResponse(
                    success=False,
                    message="Connection timeout - server may be unreachable",
                    timestamp=datetime.utcnow()
                )
            except Exception as e:
                logger.error(f"Connection error: {str(e)}", exc_info=True)
                return ConnectionTestResponse(
                    success=False,
                    message=f"Connection error: {str(e)}",
                    timestamp=datetime.utcnow()
                )
                
    except Exception as e:
        logger.error(f"Connection test error: {str(e)}", exc_info=True)
        return ConnectionTestResponse(
            success=False,
            message=f"Connection test error: {str(e)}",
            timestamp=datetime.utcnow()
        )


@router.post("/logout")
async def logout(token: str, db: Session = Depends(get_db)):
    """Logout and terminate session"""
    try:
        auth_service = AuthService(db)
        auth_service.session_token = token
        await auth_service.logout()
        
        return {"success": True, "message": "Logged out successfully"}
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "code": "LOGOUT_ERROR",
                "message": "Failed to logout",
                "details": str(e)
            }
        )


@router.post("/reset-navigation", response_model=dict)
async def reset_navigation(
    base_url: str = Query(..., description="Base URL of the Logikal API"),
    username: str = Query(..., description="Logikal API username"),
    password: str = Query(..., description="Logikal API password"),
    db: Session = Depends(get_db)
):
    """Reset navigation by re-authenticating to return to root directory context"""
    try:
        auth_service = AuthService(db)
        success, message = await auth_service.reset_navigation(base_url, username, password)
        
        if success:
            return {"success": True, "message": message}
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"code": "NAVIGATION_RESET_FAILED", "message": "Failed to reset navigation", "details": message}
            )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"code": "INTERNAL_ERROR", "message": "Internal server error", "details": str(e)}
        )
