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
                
                # Clear cached data when directory changes - DISABLED to prevent sync data loss
                # await self._clear_cached_data()
                
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
                # Enhanced error logging
                logger.error(f"Directory selection failed for '{identifier}': {message}")
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
    
    async def navigate_to_directory(self, target_path: str) -> Tuple[bool, str]:
        """
        Navigate to a directory by following the hierarchical path.
        This ensures we're in the correct context for API operations.
        
        Args:
            target_path: Full path to the target directory (e.g., "Demo Odoo/Sublevel 1 Testing")
            
        Returns:
            Tuple[bool, str]: (success, message)
        """
        if not target_path:
            return True, "Already at root directory"
        
        try:
            # Split path into components
            path_parts = target_path.split('/')
            current_path = ""
            
            logger.info(f"Starting hierarchical navigation to: {target_path}")
            
            for i, part in enumerate(path_parts):
                # Build current path
                if current_path:
                    current_path = f"{current_path}/{part}"
                else:
                    current_path = part
                
                logger.debug(f"Navigating to path component {i+1}/{len(path_parts)}: {current_path}")
                
                # Select this path component
                success, message = await self.select_directory(current_path)
                if not success:
                    error_msg = f"Failed to navigate to '{current_path}' (part of path to '{target_path}'): {message}"
                    logger.error(error_msg)
                    return False, error_msg
                
                logger.debug(f"Successfully navigated to: {current_path}")
            
            logger.info(f"Successfully completed hierarchical navigation to: {target_path}")
            return True, f"Successfully navigated to {target_path}"
            
        except Exception as e:
            error_msg = f"Error during hierarchical navigation to '{target_path}': {str(e)}"
            logger.error(error_msg)
            return False, error_msg
    
    async def _clear_cached_data(self):
        """Clear cached data when context changes"""
        try:
            # Clear projects, phases, and elevations when directory changes
            from models.project import Project
            from models.phase import Phase
            from models.elevation import Elevation
            
            # Count before deletion for logging
            project_count = self.db.query(Project).count()
            phase_count = self.db.query(Phase).count()
            elevation_count = self.db.query(Elevation).count()
            
            # DISABLED: This was deleting all projects during sync operations
            # The original intent was to clear API cache, not database records
            # self.db.query(Project).delete()
            # self.db.query(Phase).delete()
            # self.db.query(Elevation).delete()
            # self.db.commit()
            
            logger.info(f"SKIPPED DATA CLEAR: {project_count} projects, {phase_count} phases, {elevation_count} elevations (disabled to prevent sync data loss)")
        except Exception as e:
            logger.error(f"Failed to clear cached data: {str(e)}")
            # self.db.rollback()  # No longer needed since we're not deleting
    
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
    
    def _enrich_directory_with_cascade_info(self, directory: Directory) -> dict:
        """Enrich directory with cascade exclusion information"""
        is_excluded_by_parent = directory.is_excluded_from_sync() and not directory.exclude_from_sync
        can_toggle_exclusion = not is_excluded_by_parent
        
        return {
            "id": directory.id,
            "logikal_id": directory.logikal_id,
            "name": directory.name,
            "full_path": directory.full_path,
            "level": directory.level,
            "parent_id": directory.parent_id,
            "exclude_from_sync": directory.exclude_from_sync,
            "synced_at": directory.synced_at,
            "last_api_sync": directory.last_api_sync,
            "api_created_date": directory.api_created_date,
            "api_changed_date": directory.api_changed_date,
            "sync_status": directory.sync_status,
            "created_at": directory.created_at,
            "updated_at": directory.updated_at,
            "is_excluded_by_parent": is_excluded_by_parent,
            "can_toggle_exclusion": can_toggle_exclusion,
            "children": [self._enrich_directory_with_cascade_info(child) for child in directory.children]
        }
    
    async def get_directories_with_cascade_info(self) -> List[dict]:
        """Get all directories with cascade exclusion information in flat structure for tree building"""
        try:
            directories = self.db.query(Directory).all()
            logger.info(f"Retrieved {len(directories)} directories for cascade info")
            
            # Return flat list with cascade info - UI will build the tree
            enriched_directories = []
            for directory in directories:
                is_excluded_by_parent = directory.is_excluded_from_sync() and not directory.exclude_from_sync
                can_toggle_exclusion = not is_excluded_by_parent
                
                enriched_directories.append({
                    "id": directory.id,
                    "logikal_id": directory.logikal_id,
                    "name": directory.name,
                    "full_path": directory.full_path,
                    "level": directory.level,
                    "parent_id": directory.parent_id,
                    "exclude_from_sync": directory.exclude_from_sync,
                    "synced_at": directory.synced_at,
                    "last_api_sync": directory.last_api_sync,
                    "api_created_date": directory.api_created_date,
                    "api_changed_date": directory.api_changed_date,
                    "sync_status": directory.sync_status,
                    "created_at": directory.created_at,
                    "updated_at": directory.updated_at,
                    "is_excluded_by_parent": is_excluded_by_parent,
                    "can_toggle_exclusion": can_toggle_exclusion
                })
            
            return enriched_directories
        except Exception as e:
            logger.error(f"Failed to get directories with cascade info: {str(e)}")
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
        """Update directory exclusion status and cascade to all child directories"""
        try:
            directory = self.db.query(Directory).filter(Directory.id == directory_id).first()
            if not directory:
                return False, f"Directory with ID {directory_id} not found"
            
            # Update the directory itself
            directory.exclude_from_sync = exclude
            
            # If excluding, cascade to all child directories
            if exclude:
                child_count = await self._cascade_exclusion_to_children(directory, exclude)
                logger.info(f"Directory '{directory.name}' excluded from sync, cascaded to {child_count} child directories")
            else:
                # If including, we need to check if parent is still excluded
                # If parent is excluded, this directory should remain excluded
                if directory.parent and directory.parent.is_excluded_from_sync():
                    directory.exclude_from_sync = True
                    logger.info(f"Directory '{directory.name}' remains excluded because parent is excluded")
                else:
                    # Parent is not excluded, so we can include this directory
                    # But we need to be careful about children - they should only be included if their parents are not excluded
                    child_count = await self._cascade_inclusion_to_children(directory)
                    logger.info(f"Directory '{directory.name}' included from sync, updated {child_count} child directories")
            
            self.db.commit()
            
            action = "excluded" if exclude else "included"
            return True, f"Directory {action} from sync successfully"
            
        except Exception as e:
            logger.error(f"Failed to update directory exclusion: {str(e)}")
            self.db.rollback()
            return False, f"Failed to update directory exclusion: {str(e)}"
    
    async def bulk_update_directory_exclusion(self, directory_ids: List[int], exclude: bool) -> Tuple[bool, str, int]:
        """Bulk update directory exclusion status and cascade to all child directories"""
        try:
            updated_count = 0
            total_children_updated = 0
            
            for directory_id in directory_ids:
                directory = self.db.query(Directory).filter(Directory.id == directory_id).first()
                if directory:
                    # Update the directory itself
                    directory.exclude_from_sync = exclude
                    updated_count += 1
                    
                    # If excluding, cascade to all child directories
                    if exclude:
                        child_count = await self._cascade_exclusion_to_children(directory, exclude)
                        total_children_updated += child_count
                    else:
                        # If including, check parent exclusion and cascade inclusion
                        if directory.parent and directory.parent.is_excluded_from_sync():
                            directory.exclude_from_sync = True
                        else:
                            child_count = await self._cascade_inclusion_to_children(directory)
                            total_children_updated += child_count
            
            self.db.commit()
            
            action = "excluded" if exclude else "included"
            message = f"Bulk {action} completed: {updated_count} directories {action}, {total_children_updated} child directories updated"
            logger.info(message)
            
            return True, message, updated_count
            
        except Exception as e:
            logger.error(f"Failed to bulk update directory exclusion: {str(e)}")
            self.db.rollback()
            return False, f"Failed to bulk update directory exclusion: {str(e)}", 0
    
    async def _cascade_exclusion_to_children(self, directory: Directory, exclude: bool) -> int:
        """Cascade exclusion status to all child directories recursively"""
        child_count = 0
        visited = set()
        
        def cascade_to_children(current_dir):
            nonlocal child_count
            if current_dir.id in visited:
                return
            visited.add(current_dir.id)
            
            for child in current_dir.children:
                if child.exclude_from_sync != exclude:
                    child.exclude_from_sync = exclude
                    child_count += 1
                cascade_to_children(child)
        
        cascade_to_children(directory)
        return child_count
    
    async def _cascade_inclusion_to_children(self, directory: Directory) -> int:
        """Cascade inclusion status to child directories, respecting parent exclusions"""
        child_count = 0
        visited = set()
        
        def cascade_to_children(current_dir):
            nonlocal child_count
            if current_dir.id in visited:
                return
            visited.add(current_dir.id)
            
            for child in current_dir.children:
                # Only include child if its parent (current_dir) is not excluded
                if not current_dir.is_excluded_from_sync():
                    if child.exclude_from_sync:
                        child.exclude_from_sync = False
                        child_count += 1
                    cascade_to_children(child)
                else:
                    # Parent is excluded, so child should remain excluded
                    if not child.exclude_from_sync:
                        child.exclude_from_sync = True
                        child_count += 1
        
        cascade_to_children(directory)
        return child_count
    
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
            # DO NOT commit or rollback - let the main transaction handle it
            
        except Exception as e:
            logger.error(f"Failed to log API call: {str(e)}")
            # DO NOT rollback - let the main transaction handle it
