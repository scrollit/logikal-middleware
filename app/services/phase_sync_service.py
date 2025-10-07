import aiohttp
import time
import logging
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple
from sqlalchemy.orm import Session
from models.phase import Phase
from models.project import Project
from models.sync_log import SyncLog
from services.auth_service import AuthService
from services.phase_service import PhaseService
from services.project_service import ProjectService
from services.directory_service import DirectoryService

logger = logging.getLogger(__name__)


class PhaseSyncService:
    """Service for syncing phases from Logikal API"""
    
    def __init__(self, db: Session):
        self.db = db
        self.auth_service = AuthService(db)
        self.phase_service = PhaseService("", "", "")  # Will be initialized per operation
    
    def normalize_guid(self, guid: str) -> str:
        """Convert GUID to API format with hyphens"""
        if len(guid) == 32 and '-' not in guid:
            return f"{guid[:8]}-{guid[8:12]}-{guid[12:16]}-{guid[16:20]}-{guid[20:]}"
        return guid
    
    async def sync_phases_for_project(self, db: Session, base_url: str, username: str, password: str, 
                                     project: Project) -> Dict:
        """
        Sync all phases for a specific project
        """
        sync_start_time = time.time()
        sync_log = None
        
        try:
            # Create sync log entry
            sync_log = SyncLog(
                sync_type='phase',
                status='started',
                message=f'Phase sync started for project: {project.name}',
                started_at=datetime.utcnow()
            )
            db.add(sync_log)
            db.commit()
            
            logger.info(f"Starting phase sync for project: {project.name}")
            
            # Create dedicated session for this project
            success, token = await self.auth_service.authenticate(base_url, username, password)
            
            if not success:
                raise Exception(f"Authentication failed: {token}")
            
            # Navigate to the project's directory first (required for folder-scoped API)
            if not project.directory:
                raise Exception(f"Project {project.name} has no directory association")
            
            if not project.directory.full_path:
                raise Exception(f"Directory '{project.directory.name}' has no full_path")
            
            # Navigate to the directory using hierarchical navigation
            directory_service = DirectoryService(self.db, token, base_url)
            success, message = await directory_service.navigate_to_directory(project.directory.full_path)
            
            if not success:
                raise Exception(f"Failed to navigate to directory {project.directory.name}: {message}")
            
            # Select the project within the directory context
            project_service = ProjectService(self.db, token, base_url)
            success, message = await project_service.select_project(project.logikal_id)
            
            if not success:
                # Check if this is a 404 error (project not found)
                if "404" in message or "Could not retrieve" in message:
                    logger.warning(f"Project {project.name} ({project.logikal_id}) no longer exists in Logikal API - skipping")
                    return {
                        'success': True,
                        'message': f'Project {project.name} no longer exists - skipped',
                        'count': 0,
                        'duration_seconds': 0,
                        'skipped': True
                    }
                else:
                    raise Exception(f"Failed to select project {project.name}: {message}")
            
            # Get phases from the selected project
            phase_service = PhaseService(self.db, token, base_url)
            success, phases_data, message = await phase_service.get_phases()
            
            if not success:
                raise Exception(f"Failed to get phases for project {project.name}: {message}")
            
            # Process and cache phases
            phases_processed = 0
            for phase_data in phases_data:
                try:
                    logger.info(f"Processing phase data: {phase_data}")
                    phase = await self._create_or_update_phase(db, phase_data, project.id)
                    phases_processed += 1
                    logger.info(f"Successfully processed phase: {phase.name} (ID: {phase.logikal_id}) for project {project.id}")
                except Exception as e:
                    logger.error(f"Failed to process phase {phase_data.get('name', 'Unknown')}: {str(e)}")
            
            # Calculate duration
            duration = int(time.time() - sync_start_time)
            
            # Update sync log
            sync_log.status = 'completed'
            sync_log.message = f'Phase sync completed for project: {project.name}'
            sync_log.items_processed = phases_processed
            sync_log.items_successful = phases_processed
            sync_log.duration_seconds = duration
            sync_log.completed_at = datetime.utcnow()
            db.commit()
            
            logger.info(f"Phase sync completed for project {project.name} in {duration} seconds")
            logger.info(f"Processed {phases_processed} phases")
            
            return {
                'success': True,
                'message': f'Phase sync completed for project: {project.name}',
                'count': phases_processed,
                'duration_seconds': duration
            }
            
        except Exception as e:
            duration = int(time.time() - sync_start_time)
            error_msg = f"Phase sync failed for project {project.name}: {str(e)}"
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
    
    async def _create_or_update_phase(self, db: Session, phase_data: Dict, project_id: int) -> Phase:
        """Create or update a phase record from API data"""
        try:
            # Extract identifier - Logikal API uses 'id' field (GUID) as identifier
            identifier = phase_data.get('id', '')
            name = phase_data.get('name', 'Unnamed Phase')
            
            # Store null GUIDs as-is from the API (00000000-0000-0000-0000-000000000000)
            # This is the default phase in Logikal when no specific phases are created
            if not identifier:
                identifier = '00000000-0000-0000-0000-000000000000'
            
            if not identifier:
                raise ValueError(f"Phase data missing 'id' field: {phase_data}")
            
            # Check if phase already exists using composite key (project_id, logikal_id)
            existing_phase = db.query(Phase).filter(
                Phase.project_id == project_id,
                Phase.logikal_id == identifier
            ).first()
            
            if existing_phase:
                # Update existing phase
                logger.info(f"Updating existing phase: {name} (ID: {identifier}) for project {project_id}")
                existing_phase.name = name
                existing_phase.project_id = project_id
                existing_phase.synced_at = datetime.utcnow()
                existing_phase.sync_status = 'synced'
                existing_phase.last_sync_date = datetime.utcnow()
                
                # Extract and store last_update_date from Logikal API
                if 'changedDate' in phase_data and phase_data['changedDate']:
                    try:
                        # Parse the Unix timestamp and store it
                        api_updated_at = datetime.fromtimestamp(phase_data['changedDate'], tz=timezone.utc)
                        existing_phase.last_update_date = api_updated_at
                        logger.info(f"Updated last_update_date for phase {name}: {api_updated_at}")
                    except (ValueError, TypeError) as e:
                        logger.warning(f"Failed to parse changedDate for phase {name}: {e}")
                
                db.commit()
                
                logger.info(f"Successfully updated existing phase: {name} (ID: {identifier}) for project {project_id}")
                return existing_phase
            else:
                # Create new phase
                logger.info(f"Creating new phase: {name} (ID: {identifier}) for project {project_id}")
                
                # Check for duplicates before insert using composite key (project_id, logikal_id)
                duplicate_check = db.query(Phase).filter(
                    Phase.project_id == project_id,
                    Phase.logikal_id == identifier
                ).first()
                if duplicate_check:
                    logger.warning(f"Duplicate phase detected: {name} (ID: {identifier}) for project {project_id} - returning existing")
                    return duplicate_check
                
                # Extract last_update_date from Logikal API
                last_update_date = None
                if 'changedDate' in phase_data and phase_data['changedDate']:
                    try:
                        # Parse the Unix timestamp and store it
                        last_update_date = datetime.fromtimestamp(phase_data['changedDate'], tz=timezone.utc)
                        logger.info(f"Setting last_update_date for new phase {name}: {last_update_date}")
                    except (ValueError, TypeError) as e:
                        logger.warning(f"Failed to parse changedDate for new phase {name}: {e}")
                
                new_phase = Phase(
                    logikal_id=identifier,
                    name=name,
                    project_id=project_id,
                    synced_at=datetime.utcnow(),
                    sync_status='synced',
                    last_sync_date=datetime.utcnow(),
                    last_update_date=last_update_date
                )
                db.add(new_phase)
                db.commit()
                
                # Verify the phase was actually saved using composite key (project_id, logikal_id)
                saved_phase = db.query(Phase).filter(
                    Phase.project_id == project_id,
                    Phase.logikal_id == identifier
                ).first()
                if saved_phase:
                    logger.info(f"Successfully created new phase: {name} (ID: {identifier}) for project {project_id} - Verified in database")
                else:
                    logger.error(f"Phase creation failed - phase not found in database after commit: {name} (ID: {identifier}) for project {project_id}")
                
                logger.info(f"Successfully created new phase: {name} (ID: {identifier}) for project {project_id}")
                return new_phase
                
        except Exception as e:
            logger.error(f"Failed to create or update phase: {str(e)}")
            # DO NOT rollback the entire transaction - just raise the exception
            # The rollback was causing all previous work to be lost
            raise
    
    async def get_all_phases(self) -> List[Phase]:
        """Get all phases from the database"""
        try:
            phases = self.db.query(Phase).all()
            logger.info(f"Retrieved {len(phases)} phases from database")
            return phases
        except Exception as e:
            logger.error(f"Failed to get phases: {str(e)}")
            return []
    
    async def sync_all_phases(self, db: Session, base_url: str, username: str, password: str) -> Dict:
        """
        Sync all phases across all projects
        """
        sync_start_time = time.time()
        sync_log = None
        
        try:
            # Create sync log entry
            sync_log = SyncLog(
                sync_type='phase_all',
                status='started',
                message='All phases sync started',
                started_at=datetime.utcnow()
            )
            db.add(sync_log)
            db.commit()
            
            logger.info("Starting sync for all phases across all projects")
            
            # Get all projects
            from services.project_sync_service import ProjectSyncService
            project_sync_service = ProjectSyncService(db)
            projects = await project_sync_service.get_all_projects()
            
            if not projects:
                logger.warning("No projects found for phase sync")
                return {
                    'success': True,
                    'message': 'No projects found for phase sync',
                    'count': 0,
                    'duration_seconds': 0
                }
            
            total_phases = 0
            successful_projects = 0
            failed_projects = 0
            skipped_projects = 0
            
            # Sync phases for each project
            for project in projects:
                try:
                    logger.info(f"Syncing phases for project: {project.name}")
                    
                    phase_result = await self.sync_phases_for_project(
                        db, base_url, username, password, project
                    )
                    
                    if phase_result['success']:
                        if phase_result.get('skipped', False):
                            skipped_projects += 1
                            logger.info(f"Skipped project {project.name} (no longer exists)")
                        else:
                            total_phases += phase_result['count']
                            successful_projects += 1
                            logger.info(f"Synced {phase_result['count']} phases for project {project.name}")
                    else:
                        failed_projects += 1
                        logger.warning(f"Failed to sync phases for project {project.name}: {phase_result['message']}")
                        
                except Exception as e:
                    failed_projects += 1
                    logger.error(f"Error syncing phases for project {project.name}: {str(e)}")
            
            # Calculate duration
            duration = int(time.time() - sync_start_time)
            
            # Update sync log
            sync_log.status = 'completed'
            sync_log.message = f'All phases sync completed: {total_phases} phases across {successful_projects} projects ({skipped_projects} skipped, {failed_projects} failed)'
            sync_log.items_processed = total_phases
            sync_log.items_successful = total_phases
            sync_log.duration_seconds = duration
            sync_log.completed_at = datetime.utcnow()
            db.commit()
            logger.info("TRANSACTION: Final commit successful")
            
            # Cross-session visibility check (critical)
            from core.database import SessionLocal
            count_in_same_session = db.query(Phase).count()
            
            with SessionLocal() as verify_sess:
                count_in_new_session = verify_sess.query(Phase).count()
            
            logger.info(
                "POST-COMMIT VISIBILITY: same_session=%s new_session=%s",
                count_in_same_session, count_in_new_session
            )
            
            # Log all phases in database for debugging
            all_phases = db.query(Phase).all()
            logger.info(f"All phases in database after sync: {len(all_phases)}")
            for phase in all_phases:
                logger.info(f"  Phase: {phase.name} (ID: {phase.logikal_id}) for project {phase.project_id}")
            
            logger.info(f"All phases sync completed in {duration} seconds")
            logger.info(f"Processed {total_phases} phases across {successful_projects} projects ({skipped_projects} skipped, {failed_projects} failed)")
            
            return {
                'success': True,
                'message': f'All phases sync completed: {total_phases} phases across {successful_projects} projects ({skipped_projects} skipped, {failed_projects} failed)',
                'count': total_phases,
                'projects_processed': successful_projects,
                'projects_skipped': skipped_projects,
                'projects_failed': failed_projects,
                'duration_seconds': duration
            }
            
        except Exception as e:
            duration = int(time.time() - sync_start_time)
            error_msg = f"All phases sync failed: {str(e)}"
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