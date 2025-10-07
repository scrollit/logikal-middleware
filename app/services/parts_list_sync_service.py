import aiohttp
import aiofiles
import base64
import os
import sqlite3
import time
import logging
from typing import List, Optional, Tuple, Dict
from datetime import datetime, timezone
from sqlalchemy.orm import Session, joinedload
from models.elevation import Elevation
from models.project import Project
from models.directory import Directory
from services.elevation_service import ElevationService
from services.auth_service import AuthService
from services.phase_service import PhaseService
from services.project_service import ProjectService
from services.directory_service import DirectoryService

logger = logging.getLogger(__name__)


class PartsListSyncService:
    """Service for syncing parts-list data from Logikal API"""
    
    def __init__(self, db: Session):
        self.db = db
    
    def normalize_guid(self, guid: str) -> str:
        """Convert GUID to API format with hyphens"""
        # All GUIDs are now stored with hyphens, so just return as-is
        return guid
        
    async def sync_parts_for_elevation(self, elevation_id: int, base_url: str, token: str) -> Tuple[bool, str]:
        """
        Sync parts-list for a specific elevation.
        
        Args:
            elevation_id: Database ID of the elevation
            base_url: Logikal API base URL
            token: Authentication token
            
        Returns:
            Tuple of (success, message)
        """
        try:
            # Get elevation from database
            elevation = self.db.query(Elevation).filter(Elevation.id == elevation_id).first()
            if not elevation:
                return False, f"Elevation with ID {elevation_id} not found"
            
            logger.info(f"Starting parts-list sync for elevation: {elevation.name} (ID: {elevation.logikal_id})")
            
            # Navigate to elevation context
            navigation_success = await self._navigate_to_elevation_context(
                elevation, base_url, token
            )
            
            if not navigation_success:
                return False, f"Failed to navigate to elevation context for {elevation.name}"
            
            # Fetch parts-list from API
            parts_data = await self._fetch_parts_list(base_url, token)
            
            if not parts_data:
                return False, f"No parts data available for elevation {elevation.name}"
            
            # Decode and save SQLite database
            db_path = await self._decode_and_save_sqlite(parts_data, elevation.logikal_id)
            
            if not db_path:
                return False, f"Failed to save parts database for elevation {elevation.name}"
            
            # Validate SQLite file and extract parts count
            parts_count = await self._validate_sqlite_file(db_path)
            
            # Update elevation record
            elevation.parts_data = base64.b64encode(parts_data).decode('utf-8')
            elevation.parts_db_path = db_path
            elevation.parts_count = parts_count
            elevation.has_parts_data = True
            elevation.parts_synced_at = datetime.utcnow()
            
            self.db.commit()
            
            # Trigger SQLite parsing asynchronously
            try:
                from tasks.sqlite_parser_tasks import parse_elevation_sqlite_task
                parse_elevation_sqlite_task.delay(elevation.id)
                logger.info(f"Triggered SQLite parsing for elevation {elevation.id}")
            except Exception as parse_error:
                logger.warning(f"Failed to trigger parsing for elevation {elevation.id}: {str(parse_error)}")
            
            logger.info(f"Successfully synced parts-list for elevation {elevation.name}: {parts_count} parts")
            return True, f"Parts-list synced successfully: {parts_count} parts"
            
        except Exception as e:
            logger.error(f"Error syncing parts-list for elevation {elevation_id}: {str(e)}")
            return False, f"Error: {str(e)}"
    
    async def sync_all_parts(self, base_url: str, username: str, password: str) -> Dict:
        """
        Sync parts-list for all elevations with improved session management.
        
        Args:
            base_url: Logikal API base URL
            username: API username
            password: API password
            
        Returns:
            Dictionary with sync results
        """
        start_time = time.time()
        processed_count = 0
        success_count = 0
        error_count = 0
        errors = []
        
        try:
            # Get all elevations grouped by directory to minimize session switches
            from services.phase_sync_service import PhaseSyncService
            from models.phase import Phase
            from models.project import Project
            from models.directory import Directory
            
            # Get all elevations with their relationships
            elevations_with_context = self.db.query(Elevation).join(
                Phase, Elevation.phase_id == Phase.id
            ).join(
                Project, Phase.project_id == Project.id
            ).join(
                Directory, Project.directory_id == Directory.id
            ).all()
            
            if not elevations_with_context:
                return {
                    'success': True,
                    'message': 'No elevations found to sync',
                    'processed': 0,
                    'successful': 0,
                    'errors': 0
                }
            
            logger.info(f"Starting parts-list sync for {len(elevations_with_context)} elevations")
            
            # Group elevations by directory to minimize session switches
            elevations_by_directory = {}
            for elevation in elevations_with_context:
                directory_name = elevation.phase.project.directory.name
                if directory_name not in elevations_by_directory:
                    elevations_by_directory[directory_name] = []
                elevations_by_directory[directory_name].append(elevation)
            
            logger.info(f"Processing elevations across {len(elevations_by_directory)} directories")
            
            # Process each directory group with fresh session
            for directory_name, elevations in elevations_by_directory.items():
                logger.info(f"Processing {len(elevations)} elevations for directory: {directory_name}")
                
                # Create fresh authentication for each directory
                auth_service = AuthService(self.db)
                auth_success, token_or_error = await auth_service.authenticate(base_url, username, password)
                
                if not auth_success:
                    logger.error(f"Authentication failed for directory {directory_name}: {token_or_error}")
                    # Skip this directory but continue with others
                    for elevation in elevations:
                        error_count += 1
                        processed_count += 1
                        errors.append(f"Elevation {elevation.name}: Authentication failed for directory {directory_name}")
                    continue
                
                token = token_or_error
                
                # Process elevations in this directory with session reset between each
                for elevation in elevations:
                    try:
                        processed_count += 1
                        
                        # Reset session before each elevation to prevent corruption
                        logger.debug(f"Resetting session before processing elevation {elevation.name}")
                        auth_service = AuthService(self.db)
                        auth_success, fresh_token = await auth_service.authenticate(base_url, username, password)
                        
                        if not auth_success:
                            logger.error(f"Session reset failed for elevation {elevation.name}: {fresh_token}")
                            error_count += 1
                            errors.append(f"Elevation {elevation.name}: Session reset failed")
                            continue
                        
                        # Process this elevation with fresh session
                        success, message = await self.sync_parts_for_elevation(
                            elevation.id, base_url, fresh_token
                        )
                        
                        if success:
                            success_count += 1
                            logger.info(f"Elevation {processed_count}: {message}")
                        else:
                            error_count += 1
                            error_msg = f"Elevation {elevation.name}: {message}"
                            errors.append(error_msg)
                            logger.warning(error_msg)
                            
                    except Exception as e:
                        error_count += 1
                        error_msg = f"Elevation {elevation.name}: {str(e)}"
                        errors.append(error_msg)
                        logger.error(error_msg)
                        continue
            
            # Logout
            try:
                await auth_service.logout()
            except Exception as e:
                logger.warning(f"Failed to logout: {e}")
            
            duration = time.time() - start_time
            
            return {
                'success': True,
                'message': f'Parts-list sync completed: {success_count} successful, {error_count} errors in {duration:.2f}s',
                'processed': processed_count,
                'successful': success_count,
                'errors': error_count,
                'error_details': errors[:10]  # Limit to first 10 errors
            }
            
        except Exception as e:
            logger.error(f"Error in sync_all_parts: {str(e)}")
            return {
                'success': False,
                'message': f"Sync failed: {str(e)}",
                'processed': processed_count,
                'successful': success_count,
                'errors': error_count
            }
    
    async def _navigate_to_elevation_context(self, elevation: Elevation, base_url: str, token: str) -> bool:
        """
        Navigate to the specific elevation context in the Logikal API.
        
        This follows the same navigation pattern as the elevation sync service:
        1. Navigate to directory
        2. Select project
        3. Select phase
        4. Select elevation
        """
        try:
            # Get related objects - use phase.project if elevation.project is not available
            if not elevation.phase:
                logger.error(f"Elevation {elevation.name} missing phase relationship")
                return False
            
            # Get project from phase relationship
            project = elevation.phase.project
            if not project:
                logger.error(f"Phase for elevation {elevation.name} has no project association")
                return False
            
            if not project.directory:
                logger.error(f"Project {project.name} has no directory association")
                return False
            
            if not project.directory.full_path:
                logger.error(f"Directory '{project.directory.name}' has no full_path")
                return False
            
            phase = elevation.phase
            directory = project.directory
            
            # Step 1: Navigate to directory using hierarchical navigation with retry
            directory_service = DirectoryService(self.db, token, base_url)
            max_retries = 2
            
            for attempt in range(max_retries):
                success, message = await directory_service.navigate_to_directory(directory.full_path)
                
                if success:
                    break
                    
                if "isn't valid in the current mapping" in message and attempt < max_retries - 1:
                    logger.warning(f"Directory navigation failed (attempt {attempt + 1}/{max_retries}): {message}")
                    logger.info(f"Session may be corrupted, continuing with next attempt...")
                    continue
                else:
                    logger.error(f"Failed to navigate to directory {directory.name} after {attempt + 1} attempts: {message}")
                    return False
            
            # Step 2: Select the project within the directory context
            project_service = ProjectService(self.db, token, base_url)
            success, message = await project_service.select_project(project.logikal_id)
            
            if not success:
                logger.error(f"Failed to select project {project.name}: {message}")
                return False
            
            # Step 3: Select the specific phase - normalize GUID for API
            phase_service = PhaseService(self.db, token, base_url)
            normalized_phase_id = self.normalize_guid(phase.logikal_id)
            success, message = await phase_service.select_phase(normalized_phase_id)
            
            if not success:
                logger.error(f"Failed to select phase {phase.name}: {message}")
                return False
            
            # Step 4: Select the specific elevation - normalize GUID for API
            url = f"{base_url.rstrip('/')}/elevations/select"
            headers = {
                'Authorization': f'Bearer {token}',
                'Content-Type': 'application/json'
            }
            normalized_elevation_id = self.normalize_guid(elevation.logikal_id)
            payload = {'identifier': normalized_elevation_id}
            
            async with aiohttp.ClientSession() as session:
                async with session.post(url, headers=headers, json=payload, timeout=30) as response:
                    if response.status == 200:
                        logger.info(f"Successfully selected elevation: {elevation.name}")
                    else:
                        error_text = await response.text()
                        logger.error(f"Failed to select elevation {elevation.name}: HTTP {response.status} - {error_text}")
                        return False
            
            logger.info(f"Successfully navigated to elevation context: {elevation.name}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to navigate to elevation context for {elevation.name}: {str(e)}")
            return False
    
    async def _fetch_parts_list(self, base_url: str, token: str) -> Optional[bytes]:
        """
        Fetch parts-list from the Logikal API.
        
        Args:
            base_url: Logikal API base URL
            token: Authentication token
            
        Returns:
            Binary parts data or None if failed
        """
        try:
            url = f"{base_url}/elevations/selected/parts-list"
            headers = {
                'Authorization': f'Bearer {token}',
                'Accept': 'application/json'
            }
            
            logger.info("Fetching parts-list from Logikal API")
            
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=headers, timeout=60) as response:
                    if response.status == 200:
                        data = await response.json()
                        
                        # Extract base64 data from response
                        if 'data' in data and data['data']:
                            base64_data = data['data']
                            # Decode base64 to binary
                            parts_data = base64.b64decode(base64_data)
                            
                            logger.info(f"Successfully retrieved parts-list: {len(parts_data)} bytes")
                            return parts_data
                        else:
                            logger.warning("No parts data in API response")
                            return None
                    else:
                        error_text = await response.text()
                        logger.warning(f"Failed to fetch parts-list: HTTP {response.status} - {error_text}")
                        return None
                        
        except Exception as e:
            logger.error(f"Error fetching parts-list: {str(e)}")
            return None
    
    async def _decode_and_save_sqlite(self, parts_data: bytes, elevation_logikal_id: str) -> Optional[str]:
        """
        Save the parts data as a SQLite file.
        
        Args:
            parts_data: Binary SQLite data
            elevation_logikal_id: Elevation's Logikal ID for filename
            
        Returns:
            File path if successful, None if failed
        """
        try:
            # Create parts database directory
            parts_dir = "/app/parts_db/elevations"
            os.makedirs(parts_dir, exist_ok=True)
            
            # Generate filename
            filename = f"{elevation_logikal_id}.db"
            file_path = os.path.join(parts_dir, filename)
            
            # Write binary data to file
            async with aiofiles.open(file_path, 'wb') as f:
                await f.write(parts_data)
            
            logger.info(f"Saved parts database: {file_path}")
            return file_path
            
        except Exception as e:
            logger.error(f"Error saving SQLite file: {str(e)}")
            return None
    
    async def _validate_sqlite_file(self, file_path: str) -> Optional[int]:
        """
        Validate SQLite file and extract parts count.
        
        Args:
            file_path: Path to SQLite file
            
        Returns:
            Parts count if successful, None if failed
        """
        try:
            # Connect to SQLite database
            conn = sqlite3.connect(file_path)
            cursor = conn.cursor()
            
            # Get table names
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
            tables = cursor.fetchall()
            
            # Try to find a table that might contain parts data
            parts_count = 0
            for table_name in tables:
                table_name = table_name[0]
                try:
                    # Get row count for this table
                    cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
                    count = cursor.fetchone()[0]
                    parts_count += count
                except Exception as e:
                    logger.debug(f"Could not count rows in table {table_name}: {e}")
                    continue
            
            conn.close()
            
            logger.info(f"SQLite validation successful: {parts_count} total records across {len(tables)} tables")
            return parts_count
            
        except Exception as e:
            logger.error(f"Error validating SQLite file {file_path}: {str(e)}")
            return None
