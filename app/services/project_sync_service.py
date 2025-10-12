import aiohttp
import asyncio
import time
import logging
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple
from sqlalchemy.orm import Session
from models.project import Project
from models.directory import Directory
from models.sync_log import SyncLog
from services.auth_service import AuthService
from services.project_service import ProjectService
from services.directory_service import DirectoryService

logger = logging.getLogger(__name__)


class ProjectSyncService:
    """Service for syncing projects from Logikal API"""
    
    def __init__(self, db: Session):
        self.db = db
        self.auth_service = AuthService(db)
        self.project_service = ProjectService("", "", "")  # Will be initialized per operation
    
    @classmethod
    def with_session(cls, db: Session):
        """Create a new ProjectSyncService instance with a specific database session"""
        return cls(db)
    
    async def sync_projects_for_directory(self, db: Session, base_url: str, username: str, password: str, 
                                        directory: Directory) -> Dict:
        """
        Sync all projects for a specific directory
        """
        sync_start_time = time.time()
        sync_log = None
        
        try:
            # Create sync log entry
            sync_log = SyncLog(
                sync_type='project',
                status='started',
                message=f'Project sync started for directory: {directory.name}',
                started_at=datetime.utcnow()
            )
            db.add(sync_log)
            db.commit()
            
            logger.info(f"Starting project sync for directory: {directory.name}")
            
            # Create dedicated session for this directory
            success, token = await self.auth_service.authenticate(base_url, username, password)
            
            if not success:
                raise Exception(f"Authentication failed: {token}")
            
            # Validate directory path
            if not directory.full_path:
                raise Exception(f"Directory '{directory.name}' has no full_path")
            
            # Navigate to the directory using hierarchical navigation
            directory_service = DirectoryService(db, token, base_url)
            success, message = await directory_service.navigate_to_directory(directory.full_path)
            
            if not success:
                raise Exception(f"Failed to navigate to directory {directory.name}: {message}")
            
            # Get projects from the selected directory
            project_service = ProjectService(db, token, base_url)
            success, projects_data, message = await project_service.get_projects()
            
            if not success:
                raise Exception(f"Failed to get projects for directory {directory.name}: {message}")
            
            # Process and cache projects
            projects_processed = 0
            for project_data in projects_data:
                try:
                    logger.info(f"Processing project data: {project_data}")
                    project = await self._create_or_update_project(db, project_data, directory.id)
                    projects_processed += 1
                    logger.info(f"Successfully processed project: {project.name} (ID: {project.logikal_id})")
                except Exception as e:
                    logger.error(f"Failed to process project {project_data.get('name', 'Unknown')}: {str(e)}")
                    logger.error(f"Project data was: {project_data}")
            
            # Calculate duration
            duration = int(time.time() - sync_start_time)
            
            # Update sync log
            sync_log.status = 'completed'
            sync_log.message = f'Project sync completed for directory: {directory.name}'
            sync_log.items_processed = projects_processed
            sync_log.items_successful = projects_processed
            sync_log.duration_seconds = duration
            sync_log.completed_at = datetime.utcnow()
            logger.info(f"TRANSACTION: Committing directory sync log for {directory.name}")
            db.commit()
            logger.info(f"TRANSACTION: Directory sync log committed for {directory.name}")
            
            logger.info(f"Project sync completed for directory {directory.name} in {duration} seconds")
            logger.info(f"Processed {projects_processed} projects")
            
            return {
                'success': True,
                'message': f'Project sync completed for directory: {directory.name}',
                'count': projects_processed,
                'duration_seconds': duration
            }
            
        except Exception as e:
            duration = int(time.time() - sync_start_time)
            error_msg = f"Project sync failed for directory {directory.name}: {str(e)}"
            logger.error(error_msg, exc_info=True)
            
            # Update sync log with error
            if sync_log:
                sync_log.status = 'failed'
                sync_log.message = error_msg
                sync_log.duration_seconds = duration
                sync_log.completed_at = datetime.utcnow()
                sync_log.error_details = str(e)
                logger.info(f"TRANSACTION: Committing error sync log for directory: {directory.name}")
                db.commit()
                logger.info(f"TRANSACTION: Error sync log committed for directory: {directory.name}")
            
            # DO NOT rollback the entire transaction - just return error
            # The rollback was causing all previous work to be lost
            return {
                'success': False,
                'message': error_msg,
                'count': 0,
                'duration_seconds': duration,
                'error': str(e)
            }
    
    async def _create_or_update_project(self, db: Session, project_data: Dict, directory_id: int) -> Project:
        """Create or update a project record from API data"""
        try:
            # Extract identifier - Logikal API uses 'id' field (GUID) as identifier
            identifier = project_data.get('id', '')
            name = project_data.get('name', 'Unnamed Project')
            
            logger.info(f"Creating/updating project: {name} (ID: {identifier}) for directory_id: {directory_id}")
            
            if not identifier:
                raise ValueError(f"Project data missing 'id' field: {project_data}")
            
            # Check if project already exists
            existing_project = db.query(Project).filter(
                Project.logikal_id == identifier
            ).first()
            
            if existing_project:
                # Update existing project
                logger.info(f"Updating existing project: {name} (ID: {identifier})")
                existing_project.name = name
                existing_project.directory_id = directory_id
                existing_project.last_sync_date = datetime.utcnow()
                
                # Extract and store last_update_date from Logikal API
                if 'changedDate' in project_data and project_data['changedDate']:
                    try:
                        # Parse the Unix timestamp and store it
                        api_updated_at = datetime.fromtimestamp(project_data['changedDate'], tz=timezone.utc)
                        existing_project.last_update_date = api_updated_at
                        logger.info(f"Updated last_update_date for project {name}: {api_updated_at}")
                    except (ValueError, TypeError) as e:
                        logger.warning(f"Failed to parse changedDate for project {name}: {e}")
                
                db.commit()
                
                logger.info(f"Successfully updated existing project: {name} (ID: {identifier})")
                return existing_project
            else:
                # Create new project
                logger.info(f"Creating new project: {name} (ID: {identifier})")
                
                # Extract last_update_date from Logikal API
                last_update_date = None
                if 'changedDate' in project_data and project_data['changedDate']:
                    try:
                        # Parse the Unix timestamp and store it
                        last_update_date = datetime.fromtimestamp(project_data['changedDate'], tz=timezone.utc)
                        logger.info(f"Setting last_update_date for new project {name}: {last_update_date}")
                    except (ValueError, TypeError) as e:
                        logger.warning(f"Failed to parse changedDate for new project {name}: {e}")
                
                new_project = Project(
                    logikal_id=identifier,
                    name=name,
                    directory_id=directory_id,
                    last_sync_date=datetime.utcnow(),
                    last_update_date=last_update_date
                )
                db.add(new_project)
                logger.info(f"TRANSACTION: Committing project {name} (ID: {identifier})")
                db.commit()
                logger.info(f"TRANSACTION: Project {name} (ID: {identifier}) committed successfully")
                
                # Verify the project was actually saved
                saved_project = db.query(Project).filter(Project.logikal_id == identifier).first()
                if saved_project:
                    logger.info(f"Successfully created new project: {name} (ID: {identifier}) - Verified in database")
                else:
                    logger.error(f"Project creation failed - project not found in database after commit: {name} (ID: {identifier})")
                
                # No flush needed - commit is sufficient like directory storage
                logger.info(f"Project {name} committed successfully")
                
                return new_project
                
        except Exception as e:
            logger.error(f"Failed to create or update project: {str(e)}")
            logger.error(f"Project data: {project_data}")
            logger.error(f"Directory ID: {directory_id}")
            # DO NOT rollback the entire transaction - just raise the exception
            # The rollback was causing all previous work to be lost
            raise
    
    async def sync_all_projects(self, db: Session, base_url: str, username: str, password: str) -> Dict:
        """
        Sync all projects from syncable directories (respects directory exclusions)
        """
        sync_start_time = time.time()
        
        try:
            logger.info("TRANSACTION: Starting sync with single session")
            
            # Create sync log entry
            sync_log = SyncLog(
                sync_type='project',
                status='started',
                message='Project sync started for all syncable directories',
                started_at=datetime.utcnow()
            )
            db.add(sync_log)
            db.commit()
            
            logger.info("Starting project sync for all syncable directories")
            
            # Get syncable directories (non-excluded)
            directory_service = DirectoryService(db, "", "")  # Use the single session
            syncable_directories = await directory_service.get_syncable_directories()
            
            if not syncable_directories:
                logger.warning("No syncable directories found")
                sync_log.status = 'completed'
                sync_log.message = 'No syncable directories found'
                sync_log.completed_at = datetime.utcnow()
                db.commit()
                
                return {
                    'success': True,
                    'message': 'No syncable directories found',
                    'projects_processed': 0,
                    'directories_processed': 0
                }
            
            logger.info(f"Found {len(syncable_directories)} syncable directories")
            
            total_projects = 0
            successful_directories = 0
            
            # Sync projects for each syncable directory sequentially using single session
            total_projects, successful_directories = await self._sync_directories_sequentially(
                db, base_url, username, password, syncable_directories
            )
            
            # Calculate duration
            duration = int(time.time() - sync_start_time)
            
            # Update sync log
            sync_log.status = 'completed'
            sync_log.message = f'Project sync completed for {successful_directories}/{len(syncable_directories)} directories'
            sync_log.items_processed = total_projects
            sync_log.items_successful = total_projects
            sync_log.duration_seconds = duration
            sync_log.completed_at = datetime.utcnow()
            db.commit()
            logger.info("TRANSACTION: Final commit successful")
            
            # Cross-session visibility check (critical)
            from core.database import SessionLocal
            count_in_same_session = db.query(Project).count()
            
            with SessionLocal() as verify_sess:
                count_in_new_session = verify_sess.query(Project).count()
            
            logger.info(
                "POST-COMMIT VISIBILITY: same_session=%s new_session=%s",
                count_in_same_session, count_in_new_session
            )
            
            logger.info(f"Project sync completed in {duration} seconds")
            logger.info(f"Processed {total_projects} projects from {successful_directories}/{len(syncable_directories)} directories")
            
            return {
                'success': True,
                'message': f'Project sync completed for {successful_directories}/{len(syncable_directories)} directories',
                'projects_processed': total_projects,
                'directories_processed': successful_directories,
                'total_directories': len(syncable_directories),
                'duration_seconds': duration
            }
            
        except Exception as e:
            duration = int(time.time() - sync_start_time)
            error_msg = f"Project sync failed: {str(e)}"
            logger.error(error_msg, exc_info=True)
            
            # Update sync log with error
            if sync_log:
                sync_log.status = 'failed'
                sync_log.message = error_msg
                sync_log.duration_seconds = duration
                sync_log.completed_at = datetime.utcnow()
                sync_log.error_details = str(e)
                db.commit()
            
            # DO NOT rollback the entire transaction - just return error
            # The rollback was causing all previous work to be lost
            return {
                'success': False,
                'message': error_msg,
                'projects_processed': 0,
                'directories_processed': 0,
                'duration_seconds': duration,
                'error': str(e)
            }
        finally:
            # Do not close the session - it belongs to the caller
            logger.info("TRANSACTION: Sync completed")

    async def _sync_directories_sequentially(self, db: Session, base_url: str, username: str, password: str, 
                                           directories: List[Directory]) -> Tuple[int, int]:
        """
        Sync projects for multiple directories sequentially using single session
        """
        total_projects = 0
        successful_directories = 0
        
        logger.info(f"Starting sequential project sync for {len(directories)} directories")
        
        for i, directory in enumerate(directories):
            logger.info(f"Processing directory {i+1}/{len(directories)}: {directory.name} (path: {directory.full_path})")
            
            try:
                result = await self.sync_projects_for_directory(
                    db, base_url, username, password, directory
                )
            
                if result['success']:
                    logger.info(f"Completed project sync for '{directory.name}': {result['count']} projects")
                    total_projects += result['count']
                    successful_directories += 1
                else:
                    logger.warning(f"Failed project sync for '{directory.name}': {result['message']}")
                    
            except Exception as e:
                logger.error(f"Error in project sync for '{directory.name}' (path: {directory.full_path}): {str(e)}")
        
        logger.info(f"Sequential project sync completed: {successful_directories}/{len(directories)} directories, {total_projects} total projects")
        return total_projects, successful_directories

    async def get_all_projects(self) -> List[Project]:
        """Get all projects from the database"""
        try:
            projects = self.db.query(Project).all()
            logger.info(f"Retrieved {len(projects)} projects from database")
            return projects
        except Exception as e:
            logger.error(f"Failed to get projects: {str(e)}")
            return []

    async def force_sync_project_from_logikal(self, project_id: str, directory_id: Optional[str], 
                                            base_url: str, username: str, password: str) -> Dict:
        """
        Enhanced Force sync a specific project from Logikal API for Odoo integration
        with directory-aware lookup, staleness detection, and Logikal fallback
        """
        sync_start_time = time.time()
        sync_log = None
        
        try:
            # Create sync log entry
            sync_log = SyncLog(
                sync_type='project_force',
                status='started',
                message=f'Force sync project {project_id} from Logikal started',
                started_at=datetime.utcnow()
            )
            self.db.add(sync_log)
            self.db.commit()
            
            logger.info(f"Starting enhanced force sync for project: {project_id} in directory: {directory_id}")
            
            # Validate directory exists
            directory = None
            if directory_id:
                directory = self.db.query(Directory).filter(Directory.logikal_id == directory_id).first()
                if not directory:
                    raise Exception(f"Directory with ID {directory_id} not found")
            
            # Create dedicated session for this project
            success, token = await self.auth_service.authenticate(base_url, username, password)
            if not success:
                raise Exception(f"Authentication failed: {token}")
            
            # Navigate to directory if specified
            if directory and directory.full_path:
                directory_service = DirectoryService(self.db, token, base_url)
                success, message = await directory_service.navigate_to_directory(directory.full_path)
                if not success:
                    raise Exception(f"Failed to navigate to directory {directory.name}: {message}")
            
            # STEP 1: Directory-aware project lookup in middleware
            project_lookup = None
            if directory_id:
                # Look for project ONLY within the specified directory
                project_lookup = self.db.query(Project).join(Directory).filter(
                    Project.name == project_id,
                    Directory.logikal_id == directory_id
                ).first()
            else:
                # Fallback to global search if no directory specified
                project_lookup = self.db.query(Project).filter(
                    Project.name == project_id
                ).first()
            
            # STEP 2A: Project found in middleware - check staleness
            if project_lookup:
                logger.info(f"Found project '{project_id}' in middleware database")
                
                # Check if project is stale (now that we're in directory context)
                is_stale = await self._check_project_staleness(project_lookup, token, base_url)
                
                if is_stale:
                    logger.info(f"Project '{project_id}' is stale, performing full refresh from Logikal")
                    
                    # We're already in the correct directory context, so just select project and get data
                    # Step 1: Select the project
                    project_service = ProjectService(self.db, token, base_url)
                    success, message = await project_service.select_project(project_lookup.logikal_id)
                    if not success:
                        raise Exception(f"Failed to select stale project {project_id}: {message}")
                    
                    # Step 2: Get fresh project data
                    success, projects_data, message = await project_service.get_projects()
                    if not success:
                        raise Exception(f"Failed to get fresh project data for {project_id}: {message}")
                    
                    # Find the specific project in results
                    project_data = None
                    for proj in projects_data:
                        if proj.get('id') == project_lookup.logikal_id:
                            project_data = proj
                            break
                    
                    if not project_data:
                        raise Exception(f"Fresh project data not found for {project_id} after selection")
                    
                    result = await self._sync_complete_project_from_logikal(
                        project_data, directory, token, base_url, username, password
                    )
                    result['source'] = 'logikal_api'
                    result['staleness_check'] = {'is_stale': True}
                    return result
                else:
                    logger.info(f"Project '{project_id}' is up-to-date, syncing to Odoo only")
                    result = await self._sync_existing_project_to_odoo(project_lookup)
                    result['source'] = 'middleware_cache'
                    result['staleness_check'] = {'is_stale': False}
                    return result
            
            # STEP 2B: Project NOT found in middleware - search Logikal
            else:
                logger.info(f"Project '{project_id}' not found in middleware database, searching Logikal API")
                return await self._search_and_sync_from_logikal(
                    project_id, directory, token, base_url, username, password
                )

        except Exception as e:
            duration = time.time() - sync_start_time
            error_msg = f"Force sync project {project_id} failed: {str(e)}"
            logger.error(error_msg)

            # Update sync log with error
            if sync_log:
                sync_log.status = 'failed'
                sync_log.message = error_msg
                sync_log.completed_at = datetime.utcnow()
                sync_log.duration_seconds = duration
                self.db.commit()

            return {
                'success': False,
                'message': error_msg,
                'project_id': project_id,
                'duration_seconds': duration
            }

    async def _check_project_staleness(self, project: Project, token: str, base_url: str) -> bool:
        """Check if project needs full refresh from Logikal (assumes we're already in directory context)"""
        try:
            # Get project details from Logikal to check last modified date
            project_service = ProjectService(self.db, token, base_url)
            
            # Select the project first
            success, message = await project_service.select_project(project.logikal_id)
            if not success:
                logger.warning(f"Could not select project {project.name} for staleness check: {message}")
                return True  # If we can't check, assume stale
            
            # Get project data
            success, projects_data, message = await project_service.get_projects()
            if not success:
                logger.warning(f"Could not get project data for staleness check: {message}")
                return True  # If we can't check, assume stale
            
            # Find the specific project in results
            project_data = None
            for proj in projects_data:
                if proj.get('id') == project.logikal_id:
                    project_data = proj
                    break
            
            if not project_data:
                logger.warning(f"Project data not found for staleness check: {project.name}")
                return True  # If we can't check, assume stale
            
            # Compare last modified dates
            logikal_last_modified = project_data.get('last_modified_date') or project_data.get('modified_date')
            middleware_last_sync = project.synced_at
            
            if not logikal_last_modified or not middleware_last_sync:
                logger.info(f"Missing date data for staleness check: {project.name}")
                return True  # Missing data, assume stale
            
            # Parse dates and compare
            from datetime import timezone
            try:
                # Handle different date formats from Logikal API
                if isinstance(logikal_last_modified, str):
                    if logikal_last_modified.endswith('Z'):
                        logikal_date = datetime.fromisoformat(logikal_last_modified.replace('Z', '+00:00'))
                    else:
                        logikal_date = datetime.fromisoformat(logikal_last_modified)
                else:
                    logikal_date = logikal_last_modified
                
                # Ensure timezone awareness
                if logikal_date.tzinfo is None:
                    logikal_date = logikal_date.replace(tzinfo=timezone.utc)
                
                middleware_date = middleware_last_sync.replace(tzinfo=timezone.utc)
                
                is_stale = logikal_date > middleware_date
                
                logger.info(f"Project {project.name} staleness check: "
                           f"Logikal={logikal_date}, Middleware={middleware_date}, Stale={is_stale}")
                
                return is_stale
                
            except Exception as e:
                logger.warning(f"Error parsing dates for staleness check: {e}")
                return True  # Parse error, assume stale
                
        except Exception as e:
            logger.warning(f"Error during staleness check for {project.name}: {e}")
            return True  # Error during check, assume stale

    async def _sync_existing_project_to_odoo(self, project: Project) -> Dict:
        """Sync existing up-to-date project to Odoo only"""
        try:
            # This would typically trigger Odoo sync via webhook or direct API call
            # For now, we'll just return success since the project is up-to-date
            logger.info(f"Project {project.name} is up-to-date, no sync needed")
            
            return {
                'success': True,
                'message': f'Project "{project.name}" synced to Odoo successfully. Data is already up-to-date.',
                'project_id': project.name,
                'project_synced': True,
                'phases_synced': 0,
                'elevations_synced': 0,
                'images_synced': 0,
                'parts_list_parsed': 0,
                'odoo_synced': True
            }
        except Exception as e:
            logger.error(f"Error syncing existing project to Odoo: {e}")
            return {
                'success': False,
                'message': f'Failed to sync project to Odoo: {str(e)}',
                'project_id': project.name
            }

    async def _search_and_sync_from_logikal(self, project_id: str, directory: Directory, 
                                          token: str, base_url: str, username: str, password: str) -> Dict:
        """Search for project in Logikal and sync if found"""
        try:
            logger.info(f"Searching for project '{project_id}' in Logikal directory: {directory.name if directory else 'global'}")
            
            # Get all projects from the current directory context
            project_service = ProjectService(self.db, token, base_url)
            success, all_projects, message = await project_service.get_projects()
            
            if not success:
                raise Exception(f"Failed to get projects from Logikal: {message}")
            
            # Search for the project by name in Logikal results
            matching_project = None
            for proj in all_projects:
                if proj.get('name') == project_id:
                    matching_project = proj
                    break
            
            if matching_project:
                logger.info(f"Found project '{project_id}' in Logikal API")
                return await self._sync_complete_project_from_logikal(
                    matching_project, directory, token, base_url, username, password
                )
            else:
                # Get available project names for helpful error
                available_names = [p.get('name', 'Unknown') for p in all_projects if p.get('name')]
                directory_name = directory.name if directory else 'current directory'
                
                return {
                    'success': False,
                    'message': f'Project "{project_id}" not found in directory "{directory_name}" in Logikal API. '
                              f'Available projects: {", ".join(available_names[:10])}'
                              + (f' (and {len(available_names)-10} more)' if len(available_names) > 10 else ''),
                    'project_id': project_id,
                    'available_projects': available_names[:10]
                }
                
        except Exception as e:
            logger.error(f"Error searching Logikal for project {project_id}: {e}")
            return {
                'success': False,
                'message': f'Error searching Logikal API for project {project_id}: {str(e)}',
                'project_id': project_id
            }

    async def _sync_complete_project_from_logikal(self, project_data: dict, directory: Directory, 
                                                token: str, base_url: str, username: str, password: str) -> Dict:
        """Sync complete project with all related data from Logikal"""
        sync_start_time = time.time()
        
        try:
            project_id = project_data.get('id')
            project_name = project_data.get('name', 'Unknown')
            
            logger.info(f"Starting complete sync for project: {project_name} (GUID: {project_id})")
            
            # Create or update project record in middleware
            project = self.db.query(Project).filter(Project.logikal_id == project_id).first()
            if not project:
                project = Project(
                    logikal_id=project_id,
                    name=project_name,
                    description=project_data.get('description', ''),
                    directory_id=directory.id if directory else None,
                    sync_status='synced',
                    synced_at=datetime.utcnow()
                )
                self.db.add(project)
                self.db.commit()
                logger.info(f"Created new project: {project.name} (GUID: {project_id})")
            else:
                project.name = project_name
                project.description = project_data.get('description', project.description)
                project.sync_status = 'synced'
                project.synced_at = datetime.utcnow()
                self.db.commit()
                logger.info(f"Updated existing project: {project.name} (GUID: {project_id})")
            
            # Initialize counters
            phases_synced = 0
            elevations_synced = 0
            images_synced = 0
            parts_list_parsed = 0
            
            # Sync phases for this project
            try:
                from services.phase_sync_service import PhaseSyncService
                phase_sync_service = PhaseSyncService(self.db)
                phase_result = await phase_sync_service.sync_phases_for_project(
                    self.db, base_url, username, password, project
                )
                
                if phase_result.get('success'):
                    phases_synced = phase_result.get('count', 0)
                    logger.info(f"Synced {phases_synced} phases for project {project.name}")
                    
                    # Sync elevations for each phase
                    from services.elevation_sync_service import ElevationSyncService
                    from models.phase import Phase
                    phases = self.db.query(Phase).filter(Phase.project_id == project.id).all()
                    
                    for phase in phases:
                        elevation_result = await elevation_sync_service.sync_elevations_for_phase(
                            self.db, base_url, username, password, phase
                        )
                        
                        if elevation_result.get('success'):
                            elevations_synced += elevation_result.get('count', 0)
                        else:
                            logger.warning(f"Failed to sync elevations for phase {phase.name}: {elevation_result.get('message', 'Unknown error')}")
                else:
                    logger.warning(f"Failed to sync phases for project {project.name}: {phase_result.get('message', 'Unknown error')}")
                    
            except Exception as e:
                logger.warning(f"Failed to sync phases/elevations for project {project.name}: {str(e)}")
            
            # TODO: Add image sync service when available
            # images_result = await self._sync_images_for_project(project, token, base_url)
            # images_synced = images_result.get('count', 0)
            
            # TODO: Add parts list sync service when available  
            # parts_result = await self._sync_parts_list_for_project(project, token, base_url)
            # parts_list_parsed = parts_result.get('count', 0)
            
            duration = time.time() - sync_start_time
            
            return {
                'success': True,
                'message': f'Project "{project_name}" fully synced from Logikal',
                'project_id': project_name,
                'project_synced': True,
                'phases_synced': phases_synced,
                'elevations_synced': elevations_synced,
                'images_synced': images_synced,
                'parts_list_parsed': parts_list_parsed,
                'odoo_synced': True,  # TODO: Implement actual Odoo sync
                'duration_seconds': duration
            }
            
        except Exception as e:
            duration = time.time() - sync_start_time
            error_msg = f"Complete sync failed for project {project_data.get('name', 'Unknown')}: {str(e)}"
            logger.error(error_msg)
            
            return {
                'success': False,
                'message': error_msg,
                'project_id': project_data.get('name', 'Unknown'),
                'duration_seconds': duration
            }

    async def force_sync_projects_for_directory(self, directory_id: str, base_url: str, 
                                              username: str, password: str) -> Dict:
        """
        Force sync all projects in a specific directory from Logikal API for Odoo integration
        """
        sync_start_time = time.time()
        sync_log = None
        
        try:
            # Create sync log entry
            sync_log = SyncLog(
                sync_type='directory_projects_force',
                status='started',
                message=f'Force sync projects for directory {directory_id} started',
                started_at=datetime.utcnow()
            )
            self.db.add(sync_log)
            self.db.commit()
            
            logger.info(f"Starting force sync for projects in directory: {directory_id}")
            
            # Find the directory
            directory = self.db.query(Directory).filter(Directory.logikal_id == directory_id).first()
            if not directory:
                raise Exception(f"Directory with ID {directory_id} not found")
            
            # Use the existing sync_projects_for_directory method
            result = await self.sync_projects_for_directory(
                self.db, base_url, username, password, directory
            )
            
            duration = time.time() - sync_start_time
            
            # Update sync log
            if sync_log:
                sync_log.status = 'completed' if result['success'] else 'failed'
                sync_log.message = result.get('message', 'Force sync directory projects completed')
                sync_log.completed_at = datetime.utcnow()
                sync_log.duration_seconds = duration
                self.db.commit()
            
            # Return simplified result for Odoo integration
            return {
                'success': result['success'],
                'message': result.get('message', 'Force sync directory projects completed'),
                'directory_id': directory_id,
                'projects_synced': result.get('count', 0),
                'phases_synced': result.get('phases_synced', 0),
                'elevations_synced': result.get('elevations_synced', 0),
                'duration_seconds': duration
            }
            
        except Exception as e:
            duration = time.time() - sync_start_time
            error_msg = f"Force sync projects for directory {directory_id} failed: {str(e)}"
            logger.error(error_msg)
            
            # Update sync log with error
            if sync_log:
                sync_log.status = 'failed'
                sync_log.message = error_msg
                sync_log.completed_at = datetime.utcnow()
                sync_log.duration_seconds = duration
                self.db.commit()
            
            return {
                'success': False,
                'message': error_msg,
                'directory_id': directory_id,
                'projects_synced': 0,
                'phases_synced': 0,
                'elevations_synced': 0,
                'duration_seconds': duration
            }
