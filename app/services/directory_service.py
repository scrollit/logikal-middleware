import aiohttp
import time
import logging
from typing import List, Optional, Tuple
from sqlalchemy.orm import Session
from core.retry import retry_async, default_retry_config, api_rate_limiter
from models.directory import Directory
from models.api_log import ApiLog
from schemas.directory import DirectoryCreate, DirectoryUpdate

logger = logging.getLogger(__name__)


class DirectoryService:
    """Service for handling Logikal directory operations"""
    
    def __init__(self, db: Session, session_token: str, base_url: str, enable_logging: bool = True):
        self.db = db
        self.session_token = session_token
        self.base_url = base_url.rstrip('/')
        self.current_directory: Optional[str] = None
        self.enable_logging = enable_logging
        
    @retry_async(config=default_retry_config, rate_limiter=api_rate_limiter)
    async def _get_directories_request(self, url: str, headers: dict) -> Tuple[bool, List[dict], str]:
        """Internal method to make the actual directories request with retry logic"""
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers, timeout=30) as response:
                response_text = await response.text()
                
                if response.status == 200:
                    data = await response.json()
                    directories = data.get('data', []) if isinstance(data, dict) else data
                    return True, directories, "Success"
                else:
                    error_msg = f"Failed to get directories: {response.status} - {response_text}"
                    raise Exception(error_msg)
    
    async def get_directories(self) -> Tuple[bool, List[dict], str]:
        """Get directories from current context (root or selected folder)"""
        if not self.session_token:
            return False, [], "No active session. Please authenticate first."
        
        url = f"{self.base_url}/directories"
        start_time = time.time()
        logger.info("Fetching directories from Logikal API")
        
        try:
            headers = {"Authorization": f"Bearer {self.session_token}"}
            success, directories, message = await self._get_directories_request(url, headers)
            duration = int((time.time() - start_time) * 1000)
            
            if success:
                logger.info(f"Retrieved {len(directories)} directories")
                
                # Log successful operation
                await self._log_api_call(
                    operation='get_directories',
                    status='success',
                    response_code=200,
                    duration=duration,
                    request_url=url,
                    request_method='GET',
                    response_body=str(directories),
                    response_summary=f"Retrieved {len(directories)} directories"
                )
                
                return True, directories, "Success"
            else:
                return False, [], message
                        
        except Exception as e:
            duration = int((time.time() - start_time) * 1000)
            error_msg = f"Error while getting directories: {str(e)}"
            logger.error(error_msg)
            await self._log_api_call(
                operation='get_directories',
                status='failed',
                response_code=0,
                error_message=error_msg,
                duration=duration,
                request_url=url,
                request_method='GET',
                response_body=None,
                response_summary="Error while getting directories"
            )
            return False, [], error_msg
    
    @retry_async(config=default_retry_config, rate_limiter=api_rate_limiter)
    async def _select_directory_request(self, url: str, payload: dict, headers: dict) -> Tuple[bool, str]:
        """Internal method to make the actual directory selection request with retry logic"""
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=payload, headers=headers, timeout=30) as response:
                response_text = await response.text()
                
                if response.status == 200:
                    return True, "Directory selected successfully"
                else:
                    error_msg = f"Failed to select directory: {response.status} - {response_text}"
                    raise Exception(error_msg)
    
    async def select_directory(self, identifier: str) -> Tuple[bool, str]:
        """Select a directory by identifier (required for folder-scoped operations)"""
        url = f"{self.base_url}/directories/select"
        payload = {"identifier": identifier}
        start_time = time.time()
        logger.info(f"Selecting directory: {identifier}")
        
        try:
            headers = {"Authorization": f"Bearer {self.session_token}"}
            success, message = await self._select_directory_request(url, payload, headers)
            duration = int((time.time() - start_time) * 1000)
            
            if success:
                logger.info(f"Successfully selected directory: {identifier}")
                
                # Track navigation state
                self.current_directory = identifier
                
                # Clear cached data when directory changes
                await self._clear_cached_data()
                
                # Log successful operation
                await self._log_api_call(
                    operation='select_directory',
                    status='success',
                    response_code=200,
                    duration=duration,
                    request_url=url,
                    request_method='POST',
                    request_payload=payload,
                    response_body=message,
                    response_summary=f"Selected directory: {identifier}"
                )
                
                return True, "Directory selected successfully"
            else:
                return False, message
                        
        except Exception as e:
            duration = int((time.time() - start_time) * 1000)
            error_msg = f"Error while selecting directory {identifier}: {str(e)}"
            logger.error(error_msg)
            await self._log_api_call(
                operation='select_directory',
                status='failed',
                response_code=0,
                error_message=error_msg,
                duration=duration,
                request_url=url,
                request_method='POST',
                request_payload=payload,
                response_body=None,
                response_summary=f"Error selecting directory {identifier}"
            )
            return False, error_msg
    
    async def _clear_cached_data(self):
        """Clear cached data when context changes"""
        try:
            # Clear projects, phases, and elevations when directory changes
            from models.project import Project
            from models.phase import Phase
            from models.elevation import Elevation
            
            self.db.query(Project).delete()
            self.db.query(Phase).delete()
            self.db.query(Elevation).delete()
            self.db.commit()
            logger.info("Cleared cached projects, phases, and elevations due to directory change")
        except Exception as e:
            logger.error(f"Failed to clear cached data: {str(e)}")
            self.db.rollback()
    
    async def cache_directories(self, directories: List[dict]) -> bool:
        """Cache directories in PostgreSQL database"""
        try:
            for dir_data in directories:
                # Extract identifier - Logikal API uses 'path' field as identifier
                identifier = dir_data.get('path', '')
                
                # Check if directory already exists
                existing_dir = self.db.query(Directory).filter(
                    Directory.logikal_id == identifier
                ).first()
                
                if existing_dir:
                    # Update existing directory
                    existing_dir.name = dir_data.get('name', existing_dir.name)
                    existing_dir.parent_id = dir_data.get('parent_id', existing_dir.parent_id)
                else:
                    # Create new directory
                    new_directory = Directory(
                        logikal_id=identifier,
                        name=dir_data.get('name', ''),
                        parent_id=dir_data.get('parent_id')
                    )
                    self.db.add(new_directory)
            
            self.db.commit()
            logger.info(f"Cached {len(directories)} directories in database")
            return True
            
        except Exception as e:
            logger.error(f"Failed to cache directories: {str(e)}")
            self.db.rollback()
            return False
    
    async def get_cached_directories(self) -> List[Directory]:
        """Get directories from database cache"""
        try:
            directories = self.db.query(Directory).all()
            logger.info(f"Retrieved {len(directories)} cached directories")
            return directories
        except Exception as e:
            logger.error(f"Failed to get cached directories: {str(e)}")
            return []
    
    async def get_syncable_directories(self) -> List[Directory]:
        """Get directories that should be included in sync operations"""
        try:
            # Get directories that are not excluded from sync
            directories = self.db.query(Directory).filter(
                Directory.exclude_from_sync == False
            ).all()
            logger.info(f"Retrieved {len(directories)} syncable directories")
            return directories
        except Exception as e:
            logger.error(f"Failed to get syncable directories: {str(e)}")
            return []
    
    async def update_directory_exclusion(self, directory_id: int, exclude: bool) -> Tuple[bool, str]:
        """Update directory exclusion status"""
        try:
            directory = self.db.query(Directory).filter(Directory.id == directory_id).first()
            if not directory:
                return False, f"Directory with ID {directory_id} not found"
            
            directory.exclude_from_sync = exclude
            self.db.commit()
            
            action = "excluded" if exclude else "included"
            logger.info(f"Directory '{directory.name}' {action} from sync")
            return True, f"Directory {action} from sync successfully"
            
        except Exception as e:
            logger.error(f"Failed to update directory exclusion: {str(e)}")
            self.db.rollback()
            return False, f"Failed to update directory exclusion: {str(e)}"
    
    async def bulk_update_directory_exclusion(self, directory_ids: List[int], exclude: bool) -> Tuple[bool, str, int]:
        """Bulk update directory exclusion status"""
        try:
            updated_count = 0
            for directory_id in directory_ids:
                directory = self.db.query(Directory).filter(Directory.id == directory_id).first()
                if directory:
                    directory.exclude_from_sync = exclude
                    updated_count += 1
            
            self.db.commit()
            
            action = "excluded" if exclude else "included"
            logger.info(f"Bulk {action} {updated_count} directories from sync")
            return True, f"Successfully {action} {updated_count} directories from sync", updated_count
            
        except Exception as e:
            logger.error(f"Failed to bulk update directory exclusion: {str(e)}")
            self.db.rollback()
            return False, f"Failed to bulk update directory exclusion: {str(e)}", 0
    
    async def _log_api_call(self, operation: str, status: str, response_code: int, 
                           duration: int, request_url: str = None, request_method: str = None,
                           request_payload: dict = None, response_body: str = None,
                           response_summary: str = None, error_message: str = None):
        """Log API call to database (only if logging is enabled)"""
        if not self.enable_logging:
            return  # Skip logging if disabled
        
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
