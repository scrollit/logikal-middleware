import aiohttp
import time
import logging
from datetime import datetime
from typing import Dict, List, Optional, Tuple
from sqlalchemy.orm import Session
from models.phase import Phase
from models.project import Project
from models.sync_log import SyncLog
from services.auth_service import AuthService
from services.phase_service import PhaseService
from services.project_service import ProjectService

logger = logging.getLogger(__name__)


class PhaseSyncService:
    """Service for syncing phases from Logikal API"""
    
    def __init__(self, db: Session):
        self.db = db
        self.auth_service = AuthService(db)
        self.phase_service = PhaseService("", "", "")  # Will be initialized per operation
    
    async def sync_phases_for_project(self, base_url: str, username: str, password: str, 
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
            self.db.add(sync_log)
            self.db.commit()
            
            logger.info(f"Starting phase sync for project: {project.name}")
            
            # Create dedicated session for this project
            success, token = await self.auth_service.authenticate(base_url, username, password)
            
            if not success:
                raise Exception(f"Authentication failed: {token}")
            
            # Select the project
            project_service = ProjectService(self.db, token, base_url)
            success, message = await project_service.select_project(project.logikal_id)
            
            if not success:
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
                    await self._create_or_update_phase(phase_data, project.id)
                    phases_processed += 1
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
            self.db.commit()
            
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
                self.db.commit()
            
            return {
                'success': False,
                'message': error_msg,
                'count': 0,
                'duration_seconds': duration,
                'error': str(e)
            }
    
    async def _create_or_update_phase(self, phase_data: Dict, project_id: int) -> Phase:
        """Create or update a phase record from API data"""
        try:
            # Extract identifier - Logikal API uses 'id' field (GUID) as identifier
            identifier = phase_data.get('id', '')
            name = phase_data.get('name', 'Unnamed Phase')
            
            if not identifier:
                raise ValueError(f"Phase data missing 'id' field: {phase_data}")
            
            # Check if phase already exists
            existing_phase = self.db.query(Phase).filter(
                Phase.logikal_id == identifier
            ).first()
            
            if existing_phase:
                # Update existing phase
                existing_phase.name = name
                existing_phase.project_id = project_id
                existing_phase.synced_at = datetime.utcnow()
                existing_phase.sync_status = 'synced'
                self.db.commit()
                
                logger.debug(f"Updated existing phase: {name} (ID: {identifier})")
                return existing_phase
            else:
                # Create new phase
                new_phase = Phase(
                    logikal_id=identifier,
                    name=name,
                    project_id=project_id,
                    synced_at=datetime.utcnow(),
                    sync_status='synced'
                )
                self.db.add(new_phase)
                self.db.commit()
                
                logger.debug(f"Created new phase: {name} (ID: {identifier})")
                return new_phase
                
        except Exception as e:
            logger.error(f"Failed to create or update phase: {str(e)}")
            self.db.rollback()
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
