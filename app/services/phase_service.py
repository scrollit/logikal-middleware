import aiohttp
import time
import logging
from typing import List, Optional, Tuple
from sqlalchemy.orm import Session
from core.retry import retry_async, default_retry_config, api_rate_limiter
from models.phase import Phase
from models.api_log import ApiLog
from schemas.phase import PhaseCreate

logger = logging.getLogger(__name__)


class PhaseService:
    """Service for handling Logikal phase operations"""
    
    def __init__(self, db: Session, session_token: str, base_url: str):
        self.db = db
        self.session_token = session_token
        self.base_url = base_url.rstrip('/')
        self.current_phase: Optional[str] = None
        
    @retry_async(config=default_retry_config, rate_limiter=api_rate_limiter)
    async def _get_phases_request(self, url: str, headers: dict) -> Tuple[bool, List[dict], str]:
        """Internal method to make the actual phases request with retry logic"""
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers, timeout=30) as response:
                response_text = await response.text()
                
                if response.status == 200:
                    data = await response.json()
                    phases_data = data.get('data', data) if isinstance(data, dict) else data
                    return True, phases_data, "Success"
                else:
                    error_msg = f"Failed to get phases: {response.status} - {response_text}"
                    raise Exception(error_msg)
    
    async def get_phases(self) -> Tuple[bool, List[dict], str]:
        """Get all phases in the current project"""
        if not self.session_token:
            return False, [], "No active session. Please authenticate first."
        
        url = f"{self.base_url}/phases"
        start_time = time.time()
        logger.info("Fetching phases from Logikal API")
        
        try:
            headers = {"Authorization": f"Bearer {self.session_token}"}
            success, phases_data, message = await self._get_phases_request(url, headers)
            duration = int((time.time() - start_time) * 1000)
            
            if success:
                logger.info(f"Retrieved {len(phases_data) if isinstance(phases_data, list) else 'unknown'} phases")
                
                # Log successful operation
                await self._log_api_call(
                    operation='get_phases',
                    status='success',
                    response_code=200,
                    duration=duration,
                    request_url=url,
                    request_method='GET',
                    response_body=str(phases_data),
                    response_summary=f"Retrieved phases for current project"
                )
                
                return True, phases_data, "Success"
            else:
                return False, [], message
                        
        except Exception as e:
            duration = int((time.time() - start_time) * 1000)
            error_msg = f"Error while getting phases: {str(e)}"
            logger.error(error_msg)
            await self._log_api_call(
                operation='get_phases',
                status='failed',
                response_code=0,
                error_message=error_msg,
                duration=duration,
                request_url=url,
                request_method='GET',
                response_body=None,
                response_summary="Error while getting phases"
            )
            return False, [], error_msg
    
    @retry_async(config=default_retry_config, rate_limiter=api_rate_limiter)
    async def _select_phase_request(self, url: str, payload: dict, headers: dict) -> Tuple[bool, str]:
        """Internal method to make the actual phase selection request with retry logic"""
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=payload, headers=headers, timeout=30) as response:
                response_text = await response.text()
                
                if response.status == 200:
                    return True, "Phase selected successfully"
                else:
                    error_msg = f"Failed to select phase: {response.status} - {response_text}"
                    raise Exception(error_msg)
    
    async def select_phase(self, phase_identifier: str) -> Tuple[bool, str]:
        """Select a phase by identifier (required for elevation operations)"""
        url = f"{self.base_url}/phases/select"
        payload = {"identifier": phase_identifier}
        start_time = time.time()
        logger.info(f"Selecting phase: {phase_identifier}")
        
        try:
            headers = {"Authorization": f"Bearer {self.session_token}"}
            success, message = await self._select_phase_request(url, payload, headers)
            duration = int((time.time() - start_time) * 1000)
            
            if success:
                logger.info(f"Successfully selected phase: {phase_identifier}")
                
                # Track navigation state
                self.current_phase = phase_identifier
                
                # Clear cached data when phase changes - DISABLED to prevent sync data loss
                # await self._clear_cached_data()
                
                # Log successful operation
                await self._log_api_call(
                    operation='select_phase',
                    status='success',
                    response_code=200,
                    duration=duration,
                    request_url=url,
                    request_method='POST',
                    request_payload=payload,
                    response_body=message,
                    response_summary=f"Selected phase: {phase_identifier}"
                )
                
                return True, "Phase selected successfully"
            else:
                return False, message
                        
        except Exception as e:
            duration = int((time.time() - start_time) * 1000)
            error_msg = f"Error while selecting phase {phase_identifier}: {str(e)}"
            logger.error(error_msg)
            await self._log_api_call(
                operation='select_phase',
                status='failed',
                response_code=0,
                error_message=error_msg,
                duration=duration,
                request_url=url,
                request_method='POST',
                request_payload=payload,
                response_body=None,
                response_summary=f"Error selecting phase {phase_identifier}"
            )
            return False, error_msg
    
    async def _clear_cached_data(self):
        """Clear cached data when context changes"""
        try:
            # Clear elevations when phase changes
            from models.elevation import Elevation
            
            self.db.query(Elevation).delete()
            self.db.commit()
            logger.info("Cleared cached elevations due to phase change")
        except Exception as e:
            logger.error(f"Failed to clear cached data: {str(e)}")
            self.db.rollback()
    
    async def cache_phases(self, phases: List[dict]) -> bool:
        """Cache phases in PostgreSQL database"""
        try:
            for phase_data in phases:
                # Extract identifier - Logikal API uses 'id' field (GUID) as identifier
                identifier = phase_data.get('id', '')
                
                # Skip phases without valid identifiers
                if not identifier:
                    logger.warning(f"Skipping phase without identifier: {phase_data}")
                    continue
                
                # Check if phase already exists
                existing_phase = self.db.query(Phase).filter(
                    Phase.logikal_id == identifier
                ).first()
                
                if existing_phase:
                    # Update existing phase
                    existing_phase.name = phase_data.get('name', existing_phase.name)
                    existing_phase.description = phase_data.get('description', existing_phase.description)
                    existing_phase.status = phase_data.get('status', existing_phase.status)
                else:
                    # Create new phase
                    new_phase = Phase(
                        logikal_id=identifier,
                        name=phase_data.get('name', ''),
                        description=phase_data.get('description', ''),
                        status=phase_data.get('status', '')
                    )
                    self.db.add(new_phase)
            
            self.db.commit()
            logger.info(f"Cached {len(phases)} phases in database")
            return True
            
        except Exception as e:
            logger.error(f"Failed to cache phases: {str(e)}")
            self.db.rollback()
            return False
    
    async def get_cached_phases(self) -> List[Phase]:
        """Get phases from database cache"""
        try:
            phases = self.db.query(Phase).all()
            logger.info(f"Retrieved {len(phases)} cached phases")
            return phases
        except Exception as e:
            logger.error(f"Failed to get cached phases: {str(e)}")
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
