import aiohttp
import time
import logging
from datetime import datetime
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
    
    async def sync_projects_for_directory(self, base_url: str, username: str, password: str, 
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
            self.db.add(sync_log)
            self.db.commit()
            
            logger.info(f"Starting project sync for directory: {directory.name}")
            
            # Create dedicated session for this directory
            success, token = await self.auth_service.authenticate(base_url, username, password)
            
            if not success:
                raise Exception(f"Authentication failed: {token}")
            
            # Select the directory
            directory_service = DirectoryService(self.db, token, base_url)
            success, message = await directory_service.select_directory(directory.logikal_id)
            
            if not success:
                raise Exception(f"Failed to select directory {directory.name}: {message}")
            
            # Get projects from the selected directory
            project_service = ProjectService(self.db, token, base_url)
            success, projects_data, message = await project_service.get_projects()
            
            if not success:
                raise Exception(f"Failed to get projects for directory {directory.name}: {message}")
            
            # Process and cache projects
            projects_processed = 0
            for project_data in projects_data:
                try:
                    await self._create_or_update_project(project_data, directory.id)
                    projects_processed += 1
                except Exception as e:
                    logger.error(f"Failed to process project {project_data.get('name', 'Unknown')}: {str(e)}")
            
            # Calculate duration
            duration = int(time.time() - sync_start_time)
            
            # Update sync log
            sync_log.status = 'completed'
            sync_log.message = f'Project sync completed for directory: {directory.name}'
            sync_log.items_processed = projects_processed
            sync_log.items_successful = projects_processed
            sync_log.duration_seconds = duration
            sync_log.completed_at = datetime.utcnow()
            self.db.commit()
            
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
                self.db.commit()
            
            return {
                'success': False,
                'message': error_msg,
                'count': 0,
                'duration_seconds': duration,
                'error': str(e)
            }
    
    async def _create_or_update_project(self, project_data: Dict, directory_id: int) -> Project:
        """Create or update a project record from API data"""
        try:
            # Extract identifier - Logikal API uses 'id' field (GUID) as identifier
            identifier = project_data.get('id', '')
            name = project_data.get('name', 'Unnamed Project')
            
            if not identifier:
                raise ValueError(f"Project data missing 'id' field: {project_data}")
            
            # Check if project already exists
            existing_project = self.db.query(Project).filter(
                Project.logikal_id == identifier
            ).first()
            
            if existing_project:
                # Update existing project
                existing_project.name = name
                existing_project.directory_id = directory_id
                existing_project.synced_at = datetime.utcnow()
                existing_project.sync_status = 'synced'
                self.db.commit()
                
                logger.debug(f"Updated existing project: {name} (ID: {identifier})")
                return existing_project
            else:
                # Create new project
                new_project = Project(
                    logikal_id=identifier,
                    name=name,
                    directory_id=directory_id,
                    synced_at=datetime.utcnow(),
                    sync_status='synced'
                )
                self.db.add(new_project)
                self.db.commit()
                
                logger.debug(f"Created new project: {name} (ID: {identifier})")
                return new_project
                
        except Exception as e:
            logger.error(f"Failed to create or update project: {str(e)}")
            self.db.rollback()
            raise
    
    async def get_all_projects(self) -> List[Project]:
        """Get all projects from the database"""
        try:
            projects = self.db.query(Project).all()
            logger.info(f"Retrieved {len(projects)} projects from database")
            return projects
        except Exception as e:
            logger.error(f"Failed to get projects: {str(e)}")
            return []
