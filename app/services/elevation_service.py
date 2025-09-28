import aiohttp
import time
import logging
from typing import List, Optional, Tuple
from sqlalchemy.orm import Session
from core.retry import retry_async, default_retry_config, api_rate_limiter
from models.elevation import Elevation
from models.api_log import ApiLog
from schemas.elevation import ElevationCreate

logger = logging.getLogger(__name__)


class ElevationService:
    """Service for handling Logikal elevation operations"""
    
    def __init__(self, db: Session, session_token: str, base_url: str):
        self.db = db
        self.session_token = session_token
        self.base_url = base_url.rstrip('/')
        
    @retry_async(config=default_retry_config, rate_limiter=api_rate_limiter)
    async def _get_elevations_request(self, url: str, headers: dict) -> Tuple[bool, List[dict], str]:
        """Internal method to make the actual elevations request with retry logic"""
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers, timeout=30) as response:
                response_text = await response.text()
                
                if response.status == 200:
                    data = await response.json()
                    elevations_data = data.get('data', data) if isinstance(data, dict) else data
                    return True, elevations_data, "Success"
                else:
                    error_msg = f"Failed to get elevations: {response.status} - {response_text}"
                    raise Exception(error_msg)
    
    async def get_elevations(self) -> Tuple[bool, List[dict], str]:
        """Get all elevations in the current project"""
        if not self.session_token:
            return False, [], "No active session. Please authenticate first."
        
        url = f"{self.base_url}/elevations"
        start_time = time.time()
        logger.info("Fetching elevations from Logikal API")
        
        try:
            headers = {"Authorization": f"Bearer {self.session_token}"}
            success, elevations_data, message = await self._get_elevations_request(url, headers)
            duration = int((time.time() - start_time) * 1000)
            
            if success:
                logger.info(f"Retrieved {len(elevations_data) if isinstance(elevations_data, list) else 'unknown'} elevations")
                
                # Log successful operation
                await self._log_api_call(
                    operation='get_elevations',
                    status='success',
                    response_code=200,
                    duration=duration,
                    request_url=url,
                    request_method='GET',
                    response_body=str(elevations_data),
                    response_summary=f"Retrieved elevations for current project"
                )
                
                return True, elevations_data, "Success"
            else:
                return False, [], message
                        
        except Exception as e:
            duration = int((time.time() - start_time) * 1000)
            error_msg = f"Error while getting elevations: {str(e)}"
            logger.error(error_msg)
            await self._log_api_call(
                operation='get_elevations',
                status='failed',
                response_code=0,
                error_message=error_msg,
                duration=duration,
                request_url=url,
                request_method='GET',
                response_body=None,
                response_summary="Error while getting elevations"
            )
            return False, [], error_msg
    
    @retry_async(config=default_retry_config, rate_limiter=api_rate_limiter)
    async def _get_elevation_thumbnail_request(self, url: str, params: dict, headers: dict) -> Tuple[bool, str, str]:
        """Internal method to make the actual thumbnail request with retry logic"""
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers, params=params, timeout=30) as response:
                response_text = await response.text()
                
                if response.status == 200:
                    # Get the image data
                    image_data = await response.read()
                    # Convert to base64 for storage
                    import base64
                    base64_data = base64.b64encode(image_data).decode('utf-8')
                    return True, base64_data, "Success"
                else:
                    error_msg = f"Failed to get thumbnail: {response.status} - {response_text}"
                    raise Exception(error_msg)
    
    async def get_elevation_thumbnail(self, elevation_id: str, width: int = 300, height: int = 300, 
                                    format: str = "PNG", view: str = "Exterior", 
                                    withdimensions: str = "true", withdescription: str = "false") -> Tuple[bool, str, str]:
        """Get thumbnail for a specific elevation"""
        if not self.session_token:
            return False, "", "No active session. Please authenticate first."
        
        url = f"{self.base_url}/elevations/{elevation_id}/thumbnail"
        params = {
            'width': str(width),
            'height': str(height),
            'format': format,
            'view': view,
            'withdimensions': withdimensions,
            'withdescription': withdescription
        }
        start_time = time.time()
        logger.info(f"Fetching thumbnail for elevation: {elevation_id} ({width}x{height}, {format}, {view})")
        
        try:
            headers = {"Authorization": f"Bearer {self.session_token}"}
            success, base64_data, message = await self._get_elevation_thumbnail_request(url, params, headers)
            duration = int((time.time() - start_time) * 1000)
            
            if success:
                logger.info(f"Successfully retrieved thumbnail for elevation: {elevation_id}")
                
                # Log successful operation
                await self._log_api_call(
                    operation='get_elevation_thumbnail',
                    status='success',
                    response_code=200,
                    duration=duration,
                    request_url=url,
                    request_method='GET',
                    response_body=f"Image data ({len(base64_data)} characters)",
                    response_summary=f"Retrieved thumbnail for elevation {elevation_id}"
                )
                
                return True, base64_data, "Success"
            else:
                return False, "", message
                        
        except Exception as e:
            duration = int((time.time() - start_time) * 1000)
            error_msg = f"Error while getting thumbnail for elevation {elevation_id}: {str(e)}"
            logger.error(error_msg)
            await self._log_api_call(
                operation='get_elevation_thumbnail',
                status='failed',
                response_code=0,
                error_message=error_msg,
                duration=duration,
                request_url=url,
                request_method='GET',
                response_body=None,
                response_summary=f"Error getting thumbnail for elevation {elevation_id}"
            )
            return False, "", error_msg
    
    async def cache_elevations(self, elevations: List[dict]) -> bool:
        """Cache elevations in PostgreSQL database"""
        try:
            for elevation_data in elevations:
                # Extract identifier - Logikal API uses 'id' field (GUID) as identifier
                identifier = elevation_data.get('id', '')
                
                # Skip elevations without valid identifiers
                if not identifier:
                    logger.warning(f"Skipping elevation without identifier: {elevation_data}")
                    continue
                
                # Check if elevation already exists
                existing_elevation = self.db.query(Elevation).filter(
                    Elevation.logikal_id == identifier
                ).first()
                
                if existing_elevation:
                    # Update existing elevation
                    existing_elevation.name = elevation_data.get('name', existing_elevation.name)
                    existing_elevation.description = elevation_data.get('description', existing_elevation.description)
                    existing_elevation.phase_id = elevation_data.get('phase_id', existing_elevation.phase_id)
                    existing_elevation.width = elevation_data.get('width', existing_elevation.width)
                    existing_elevation.height = elevation_data.get('height', existing_elevation.height)
                    existing_elevation.depth = elevation_data.get('depth', existing_elevation.depth)
                else:
                    # Create new elevation
                    new_elevation = Elevation(
                        logikal_id=identifier,
                        name=elevation_data.get('name', ''),
                        description=elevation_data.get('description', ''),
                        phase_id=elevation_data.get('phase_id', ''),
                        width=elevation_data.get('width'),
                        height=elevation_data.get('height'),
                        depth=elevation_data.get('depth')
                    )
                    self.db.add(new_elevation)
            
            self.db.commit()
            logger.info(f"Cached {len(elevations)} elevations in database")
            return True
            
        except Exception as e:
            logger.error(f"Failed to cache elevations: {str(e)}")
            self.db.rollback()
            return False
    
    async def get_cached_elevations(self) -> List[Elevation]:
        """Get elevations from database cache"""
        try:
            elevations = self.db.query(Elevation).all()
            logger.info(f"Retrieved {len(elevations)} cached elevations")
            return elevations
        except Exception as e:
            logger.error(f"Failed to get cached elevations: {str(e)}")
            return []
    
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
                method=request_method or 'GET',
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
