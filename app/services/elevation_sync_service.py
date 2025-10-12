import aiohttp
import time
import logging
import os
import aiofiles
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple
from sqlalchemy.orm import Session
from models.elevation import Elevation
from models.phase import Phase
from models.sync_log import SyncLog
from services.auth_service import AuthService
from services.elevation_service import ElevationService
from services.phase_service import PhaseService
from services.project_service import ProjectService
from services.directory_service import DirectoryService

logger = logging.getLogger(__name__)


class ElevationSyncService:
    """Service for syncing elevations from Logikal API"""
    
    def __init__(self, db: Session):
        self.db = db
        self.auth_service = AuthService(db)
        self.elevation_service = ElevationService("", "", "")  # Will be initialized per operation
    
    def normalize_guid(self, guid: str) -> str:
        """Convert GUID to API format with hyphens"""
        # All GUIDs are now stored with hyphens, so just return as-is
        return guid
    
    async def download_elevation_image(self, elevation_data: Dict, base_url: str, token: str) -> Optional[str]:
        """
        Download elevation thumbnail from the API endpoint.
        
        The Logikal API provides thumbnails via a separate endpoint:
        GET /elevations/{elevation_id}/thumbnail
        
        Query parameters:
        - width: Thumbnail width in pixels (default: 300)
        - height: Thumbnail height in pixels (default: 300)
        - format: Image format - 'PNG', 'JPG', 'EMF' (default: 'PNG')
        - view: Viewpoint - 'Interior', 'Exterior' (default: 'Interior')
        - withdimensions: Include dimensions - 'true', 'false' (default: 'true')
        - withdescription: Include description - 'true', 'false' (default: 'false')
        """
        try:
            elevation_id = elevation_data.get('id')
            elevation_name = elevation_data.get('name', 'unknown')
            
            if not elevation_id:
                logger.warning(f"No elevation ID for elevation {elevation_name}")
                return None
            
            # Create images directory if it doesn't exist
            images_dir = "/app/images/elevations"
            os.makedirs(images_dir, exist_ok=True)
            
            # Generate filename from elevation ID and name
            safe_name = elevation_name.replace(' ', '_').replace('/', '_')
            file_extension = 'png'  # Default to PNG
            filename = f"{elevation_id}_{safe_name}.{file_extension}"
            local_path = os.path.join(images_dir, filename)
            
            # Build thumbnail API endpoint
            thumbnail_url = f"{base_url}/elevations/{elevation_id}/thumbnail"
            params = {
                'width': '300',
                'height': '300',
                'format': 'PNG',
                'view': 'Interior',
                'withdimensions': 'true',
                'withdescription': 'false'
            }
            
            # Download the thumbnail
            headers = {
                'Authorization': f'Bearer {token}',
                'Accept': 'image/*'
            }
            
            logger.info(f"Fetching thumbnail for elevation {elevation_name} (ID: {elevation_id})")
            
            async with aiohttp.ClientSession() as session:
                async with session.get(thumbnail_url, params=params, headers=headers, timeout=30) as response:
                    if response.status == 200:
                        thumbnail_data = await response.read()
                        
                        # Save to file
                        async with aiofiles.open(local_path, 'wb') as f:
                            await f.write(thumbnail_data)
                        
                        thumbnail_size = len(thumbnail_data)
                        logger.info(f"Successfully downloaded thumbnail for elevation {elevation_name}: {local_path} ({thumbnail_size} bytes)")
                        return local_path
                    else:
                        error_text = await response.text()
                        logger.warning(f"Failed to download thumbnail for elevation {elevation_name}: HTTP {response.status} - {error_text}")
                        return None
                        
        except Exception as e:
            logger.error(f"Error downloading elevation thumbnail for {elevation_data.get('name', 'unknown')}: {str(e)}")
            return None
    
    async def phase_exists_in_api(self, db: Session, base_url: str, username: str, password: str, phase: Phase) -> bool:
        """Check if phase exists in Logikal API before syncing elevations"""
        try:
            # Create dedicated session for this phase
            success, token = await self.auth_service.authenticate(base_url, username, password)
            
            if not success:
                logger.warning(f"Authentication failed for phase validation: {token}")
                return False
            
            # Navigate to the phase's project directory first (required for folder-scoped API)
            if not phase.project:
                logger.warning(f"Phase {phase.name} has no project association")
                return False
            
            if not phase.project.directory:
                logger.warning(f"Project {phase.project.name} has no directory association")
                return False
            
            if not phase.project.directory.full_path:
                logger.warning(f"Directory '{phase.project.directory.name}' has no full_path")
                return False
            
            # Navigate to the directory using hierarchical navigation
            directory_service = DirectoryService(db, token, base_url)
            success, message = await directory_service.navigate_to_directory(phase.project.directory.full_path)
            
            if not success:
                logger.warning(f"Failed to navigate to directory {phase.project.directory.name}: {message}")
                return False
            
            # Select the project within the directory context
            project_service = ProjectService(db, token, base_url)
            success, message = await project_service.select_project(phase.project.logikal_id)
            
            if not success:
                logger.warning(f"Failed to select project {phase.project.name}: {message}")
                return False
            
            # Try to select the phase within the project context
            phase_service = PhaseService(db, token, base_url)
            normalized_phase_id = self.normalize_guid(phase.logikal_id)
            success, message = await phase_service.select_phase(normalized_phase_id)
            
            if not success:
                if "404" in message or "Could not retrieve" in message:
                    logger.warning(f"Phase {phase.name} ({phase.logikal_id}) not found in Logikal API")
                    return False
                else:
                    logger.warning(f"Failed to select phase {phase.name}: {message}")
                    return False
            
            logger.info(f"Phase {phase.name} exists in Logikal API - proceeding with elevation sync")
            return True
            
        except Exception as e:
            logger.error(f"Error validating phase existence in API: {str(e)}")
            return False
    
    async def sync_elevations_for_phase(self, db: Session, base_url: str, username: str, password: str, 
                                       phase: Phase) -> Dict:
        """
        Sync all elevations for a specific phase
        """
        sync_start_time = time.time()
        sync_log = None
        
        try:
            # Create sync log entry
            sync_log = SyncLog(
                sync_type='elevation',
                status='started',
                message=f'Elevation sync started for phase: {phase.name}',
                started_at=datetime.utcnow()
            )
            db.add(sync_log)
            db.commit()
            
            logger.info(f"Starting elevation sync for phase: {phase.name}")
            
            # Create dedicated session for this phase
            success, token = await self.auth_service.authenticate(base_url, username, password)
            
            if not success:
                raise Exception(f"Authentication failed: {token}")
            
            # Navigate to the phase's project directory first (required for folder-scoped API)
            if not phase.project:
                raise Exception(f"Phase {phase.name} has no project association")
            
            if not phase.project.directory:
                raise Exception(f"Project {phase.project.name} has no directory association")
            
            if not phase.project.directory.full_path:
                raise Exception(f"Directory '{phase.project.directory.name}' has no full_path")
            
            # Navigate to the directory using hierarchical navigation
            directory_service = DirectoryService(self.db, token, base_url)
            success, message = await directory_service.navigate_to_directory(phase.project.directory.full_path)
            
            if not success:
                raise Exception(f"Failed to navigate to directory {phase.project.directory.name}: {message}")
            
            # Select the project within the directory context
            project_service = ProjectService(self.db, token, base_url)
            success, message = await project_service.select_project(phase.project.logikal_id)
            
            if not success:
                raise Exception(f"Failed to select project {phase.project.name}: {message}")
            
            # Select the phase within the project context - normalize GUID for API
            phase_service = PhaseService(self.db, token, base_url)
            normalized_phase_id = self.normalize_guid(phase.logikal_id)
            success, message = await phase_service.select_phase(normalized_phase_id)
            
            if not success:
                # Check if this is a 404 error (phase not found)
                if "404" in message or "Could not retrieve" in message:
                    logger.warning(f"Phase {phase.name} ({phase.logikal_id}) no longer exists in Logikal API - skipping")
                    return {
                        'success': True,
                        'message': f'Phase {phase.name} no longer exists - skipped',
                        'count': 0,
                        'duration_seconds': 0,
                        'skipped': True
                    }
                else:
                    raise Exception(f"Failed to select phase {phase.name}: {message}")
            
            # Get elevations from the selected phase
            elevation_service = ElevationService(self.db, token, base_url)
            success, elevations_data, message = await elevation_service.get_elevations()
            
            if not success:
                raise Exception(f"Failed to get elevations for phase {phase.name}: {message}")
            
            # Process and cache elevations
            elevations_processed = 0
            parts_lists_synced = 0
            parts_lists_failed = 0
            
            for elevation_data in elevations_data:
                try:
                    elevation = await self._create_or_update_elevation(db, elevation_data, phase.id, base_url, token)
                    elevations_processed += 1
                    
                    # Track parts list sync status
                    if elevation and elevation.has_parts_data:
                        parts_lists_synced += 1
                    elif elevation and base_url and token:
                        # Parts list sync was attempted but failed
                        parts_lists_failed += 1
                except Exception as e:
                    logger.error(f"Failed to process elevation {elevation_data.get('name', 'Unknown')}: {str(e)}")
            
            # Calculate duration
            duration = int(time.time() - sync_start_time)
            
            # Update sync log
            sync_log.status = 'completed'
            sync_log.message = f'Elevation sync completed for phase: {phase.name}'
            sync_log.items_processed = elevations_processed
            sync_log.items_successful = elevations_processed
            sync_log.duration_seconds = duration
            sync_log.completed_at = datetime.utcnow()
            db.commit()
            
            logger.info(f"Elevation sync completed for phase {phase.name} in {duration} seconds")
            logger.info(f"Processed {elevations_processed} elevations")
            logger.info(f"Parts lists synced: {parts_lists_synced}, failed: {parts_lists_failed}")
            
            return {
                'success': True,
                'message': f'Elevation sync completed for phase: {phase.name}',
                'count': elevations_processed,
                'parts_lists_synced': parts_lists_synced,
                'parts_lists_failed': parts_lists_failed,
                'duration_seconds': duration
            }
            
        except Exception as e:
            duration = int(time.time() - sync_start_time)
            error_msg = f"Elevation sync failed for phase {phase.name}: {str(e)}"
            logger.error(error_msg, exc_info=True)
            
            # Update sync log with error
            if sync_log:
                sync_log.status = 'failed'
                sync_log.message = error_msg
                sync_log.duration_seconds = duration
                sync_log.completed_at = datetime.utcnow()
                sync_log.error_details = str(e)
                db.commit()
            
            return {
                'success': False,
                'message': error_msg,
                'count': 0,
                'duration_seconds': duration,
                'error': str(e)
            }
    
    async def _create_or_update_elevation(self, db: Session, elevation_data: Dict, phase_id: int, base_url: str = None, token: str = None) -> Elevation:
        """Create or update an elevation record from API data"""
        try:
            # Extract identifier - Logikal API uses 'id' field (GUID) as identifier
            identifier = elevation_data.get('id', '')
            name = elevation_data.get('name', 'Unnamed Elevation')
            
            # Store null GUIDs as-is from the API (00000000-0000-0000-0000-000000000000)
            # This is the default elevation in Logikal when no specific elevations are created
            if not identifier:
                identifier = '00000000-0000-0000-0000-000000000000'
            
            if not identifier:
                raise ValueError(f"Elevation data missing 'id' field: {elevation_data}")
            
            # Check if elevation already exists
            existing_elevation = db.query(Elevation).filter(
                Elevation.logikal_id == identifier
            ).first()
            
            if existing_elevation:
                # Update existing elevation
                existing_elevation.name = name
                existing_elevation.phase_id = phase_id
                existing_elevation.synced_at = datetime.utcnow()
                existing_elevation.sync_status = 'synced'
                existing_elevation.last_sync_date = datetime.utcnow()
                
                # Extract and store last_update_date from Logikal API
                if 'changedDate' in elevation_data and elevation_data['changedDate']:
                    try:
                        # Parse the Unix timestamp and store it
                        api_updated_at = datetime.fromtimestamp(elevation_data['changedDate'], tz=timezone.utc)
                        existing_elevation.last_update_date = api_updated_at
                        logger.info(f"Updated last_update_date for elevation {name}: {api_updated_at}")
                    except (ValueError, TypeError) as e:
                        logger.warning(f"Failed to parse changedDate for elevation {name}: {e}")
                
                # Download and store image if available
                if base_url and token:
                    image_path = await self.download_elevation_image(elevation_data, base_url, token)
                    if image_path:
                        existing_elevation.image_path = image_path
                
                db.commit()
                
                # Sync parts list if base_url and token provided
                if base_url and token:
                    try:
                        from services.parts_list_sync_service import PartsListSyncService
                        parts_service = PartsListSyncService(db)
                        logger.info(f"Starting parts list sync for existing elevation: {name} (inline, skipping navigation)")
                        success, message = await parts_service.sync_parts_for_elevation(
                            existing_elevation.id, base_url, token, skip_navigation=True
                        )
                        if success:
                            logger.info(f"Parts list synced for elevation {name}: {message}")
                        else:
                            logger.warning(f"Parts list sync failed for elevation {name}: {message}")
                    except Exception as e:
                        logger.error(f"Error syncing parts list for elevation {name}: {str(e)}")
                        # Don't fail the entire elevation sync if parts list fails
                
                logger.debug(f"Updated existing elevation: {name} (ID: {identifier})")
                return existing_elevation
            else:
                # Create new elevation
                
                # Check for duplicates before insert
                duplicate_check = db.query(Elevation).filter(
                    Elevation.logikal_id == identifier
                ).first()
                if duplicate_check:
                    logger.warning(f"Duplicate elevation ID detected: {identifier} - returning existing")
                    return duplicate_check
                
                # Extract last_update_date from Logikal API
                last_update_date = None
                if 'changedDate' in elevation_data and elevation_data['changedDate']:
                    try:
                        # Parse the Unix timestamp and store it
                        last_update_date = datetime.fromtimestamp(elevation_data['changedDate'], tz=timezone.utc)
                        logger.info(f"Setting last_update_date for new elevation {name}: {last_update_date}")
                    except (ValueError, TypeError) as e:
                        logger.warning(f"Failed to parse changedDate for new elevation {name}: {e}")
                
                # Download and store image if available
                image_path = None
                if base_url and token:
                    image_path = await self.download_elevation_image(elevation_data, base_url, token)
                
                new_elevation = Elevation(
                    logikal_id=identifier,
                    name=name,
                    phase_id=phase_id,
                    synced_at=datetime.utcnow(),
                    sync_status='synced',
                    last_sync_date=datetime.utcnow(),
                    last_update_date=last_update_date,
                    image_path=image_path
                )
                db.add(new_elevation)
                db.commit()
                
                # Verify the elevation was actually saved
                saved_elevation = db.query(Elevation).filter(Elevation.logikal_id == identifier).first()
                if saved_elevation:
                    logger.info(f"Successfully created new elevation: {name} (ID: {identifier}) - Verified in database")
                    
                    # Sync parts list if base_url and token provided
                    if base_url and token:
                        try:
                            from services.parts_list_sync_service import PartsListSyncService
                            parts_service = PartsListSyncService(db)
                            logger.info(f"Starting parts list sync for elevation: {name} (inline, skipping navigation)")
                            success, message = await parts_service.sync_parts_for_elevation(
                                saved_elevation.id, base_url, token, skip_navigation=True
                            )
                            if success:
                                logger.info(f"Parts list synced for elevation {name}: {message}")
                            else:
                                logger.warning(f"Parts list sync failed for elevation {name}: {message}")
                        except Exception as e:
                            logger.error(f"Error syncing parts list for elevation {name}: {str(e)}")
                            # Don't fail the entire elevation sync if parts list fails
                else:
                    logger.error(f"Elevation creation failed - elevation not found in database after commit: {name} (ID: {identifier})")
                
                logger.debug(f"Created new elevation: {name} (ID: {identifier})")
                return new_elevation
                
        except Exception as e:
            logger.error(f"Failed to create or update elevation: {str(e)}")
            # DO NOT rollback the entire transaction - just raise the exception
            # The rollback was causing all previous work to be lost
            raise
    
    async def get_all_elevations(self) -> List[Elevation]:
        """Get all elevations from the database"""
        try:
            elevations = self.db.query(Elevation).all()
            logger.info(f"Retrieved {len(elevations)} elevations from database")
            return elevations
        except Exception as e:
            logger.error(f"Failed to get elevations: {str(e)}")
            return []
    
    async def sync_all_elevations(self, db: Session, base_url: str, username: str, password: str) -> Dict:
        """
        Sync all elevations across all phases
        """
        sync_start_time = time.time()
        sync_log = None
        
        try:
            # Create sync log entry
            sync_log = SyncLog(
                sync_type='elevation_all',
                status='started',
                message='All elevations sync started',
                started_at=datetime.utcnow()
            )
            db.add(sync_log)
            db.commit()
            
            logger.info("Starting sync for all elevations across all phases")
            
            # Get all phases
            from services.phase_sync_service import PhaseSyncService
            phase_sync_service = PhaseSyncService(db)
            phases = await phase_sync_service.get_all_phases()
            
            if not phases:
                logger.warning("No phases found for elevation sync")
                return {
                    'success': True,
                    'message': 'No phases found for elevation sync',
                    'count': 0,
                    'duration_seconds': 0
                }
            
            total_elevations = 0
            successful_phases = 0
            failed_phases = 0
            skipped_phases = 0
            
            # Sync elevations for each phase
            for phase in phases:
                try:
                    logger.info(f"Syncing elevations for phase: {phase.name}")
                    
                    # Validate phase exists in API before syncing elevations
                    if not await self.phase_exists_in_api(db, base_url, username, password, phase):
                        skipped_phases += 1
                        logger.info(f"Skipped phase {phase.name} (not found in Logikal API)")
                        continue
                    
                    elevation_result = await self.sync_elevations_for_phase(
                        db, base_url, username, password, phase
                    )
                    
                    if elevation_result['success']:
                        if elevation_result.get('skipped', False):
                            skipped_phases += 1
                            logger.info(f"Skipped phase {phase.name} (no longer exists)")
                        else:
                            total_elevations += elevation_result['count']
                            successful_phases += 1
                            logger.info(f"Synced {elevation_result['count']} elevations for phase {phase.name}")
                    else:
                        failed_phases += 1
                        logger.warning(f"Failed to sync elevations for phase {phase.name}: {elevation_result['message']}")
                        
                except Exception as e:
                    failed_phases += 1
                    logger.error(f"Error syncing elevations for phase {phase.name}: {str(e)}")
            
            # Calculate duration
            duration = int(time.time() - sync_start_time)
            
            # Update sync log
            sync_log.status = 'completed'
            sync_log.message = f'All elevations sync completed: {total_elevations} elevations across {successful_phases} phases ({skipped_phases} skipped, {failed_phases} failed)'
            sync_log.items_processed = total_elevations
            sync_log.items_successful = total_elevations
            sync_log.duration_seconds = duration
            sync_log.completed_at = datetime.utcnow()
            db.commit()
            logger.info("TRANSACTION: Final commit successful")
            
            # Cross-session visibility check (critical)
            from core.database import SessionLocal
            count_in_same_session = db.query(Elevation).count()
            
            with SessionLocal() as verify_sess:
                count_in_new_session = verify_sess.query(Elevation).count()
            
            logger.info(
                "POST-COMMIT VISIBILITY: same_session=%s new_session=%s",
                count_in_same_session, count_in_new_session
            )
            
            logger.info(f"All elevations sync completed in {duration} seconds")
            logger.info(f"Processed {total_elevations} elevations across {successful_phases} phases ({skipped_phases} skipped, {failed_phases} failed)")
            
            return {
                'success': True,
                'message': f'All elevations sync completed: {total_elevations} elevations across {successful_phases} phases ({skipped_phases} skipped, {failed_phases} failed)',
                'count': total_elevations,
                'phases_processed': successful_phases,
                'phases_skipped': skipped_phases,
                'phases_failed': failed_phases,
                'duration_seconds': duration
            }
            
        except Exception as e:
            duration = int(time.time() - sync_start_time)
            error_msg = f"All elevations sync failed: {str(e)}"
            logger.error(error_msg, exc_info=True)
            
            # Update sync log with error
            if sync_log:
                sync_log.status = 'failed'
                sync_log.message = error_msg
                sync_log.duration_seconds = duration
                sync_log.completed_at = datetime.utcnow()
                sync_log.error_details = str(e)
                db.commit()
            
            return {
                'success': False,
                'message': error_msg,
                'count': 0,
                'duration_seconds': duration,
                'error': str(e)
            }