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
