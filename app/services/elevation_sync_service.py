import aiohttp
import time
import logging
from datetime import datetime
from typing import Dict, List, Optional, Tuple
from sqlalchemy.orm import Session
from models.elevation import Elevation
from models.phase import Phase
from models.sync_log import SyncLog
from services.auth_service import AuthService
from services.elevation_service import ElevationService
from services.phase_service import PhaseService

logger = logging.getLogger(__name__)


class ElevationSyncService:
    """Service for syncing elevations from Logikal API"""
    
    def __init__(self, db: Session):
        self.db = db
        self.auth_service = AuthService(db)
        self.elevation_service = ElevationService("", "", "")  # Will be initialized per operation
    
    async def sync_elevations_for_phase(self, base_url: str, username: str, password: str, 
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
            self.db.add(sync_log)
            self.db.commit()
            
            logger.info(f"Starting elevation sync for phase: {phase.name}")
            
            # Create dedicated session for this phase
            success, token = await self.auth_service.authenticate(base_url, username, password)
            
            if not success:
                raise Exception(f"Authentication failed: {token}")
            
            # Select the phase
            phase_service = PhaseService(self.db, token, base_url)
            success, message = await phase_service.select_phase(phase.logikal_id)
            
            if not success:
                raise Exception(f"Failed to select phase {phase.name}: {message}")
            
            # Get elevations from the selected phase
            elevation_service = ElevationService(self.db, token, base_url)
            success, elevations_data, message = await elevation_service.get_elevations()
            
            if not success:
                raise Exception(f"Failed to get elevations for phase {phase.name}: {message}")
            
            # Process and cache elevations
            elevations_processed = 0
            for elevation_data in elevations_data:
                try:
                    await self._create_or_update_elevation(elevation_data, phase.id)
                    elevations_processed += 1
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
            self.db.commit()
            
            logger.info(f"Elevation sync completed for phase {phase.name} in {duration} seconds")
            logger.info(f"Processed {elevations_processed} elevations")
            
            return {
                'success': True,
                'message': f'Elevation sync completed for phase: {phase.name}',
                'count': elevations_processed,
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
                self.db.commit()
            
            return {
                'success': False,
                'message': error_msg,
                'count': 0,
                'duration_seconds': duration,
                'error': str(e)
            }
    
    async def _create_or_update_elevation(self, elevation_data: Dict, phase_id: int) -> Elevation:
        """Create or update an elevation record from API data"""
        try:
            # Extract identifier - Logikal API uses 'id' field (GUID) as identifier
            identifier = elevation_data.get('id', '')
            name = elevation_data.get('name', 'Unnamed Elevation')
            
            if not identifier:
                raise ValueError(f"Elevation data missing 'id' field: {elevation_data}")
            
            # Check if elevation already exists
            existing_elevation = self.db.query(Elevation).filter(
                Elevation.logikal_id == identifier
            ).first()
            
            if existing_elevation:
                # Update existing elevation
                existing_elevation.name = name
                existing_elevation.phase_id = phase_id
                existing_elevation.synced_at = datetime.utcnow()
                existing_elevation.sync_status = 'synced'
                self.db.commit()
                
                logger.debug(f"Updated existing elevation: {name} (ID: {identifier})")
                return existing_elevation
            else:
                # Create new elevation
                new_elevation = Elevation(
                    logikal_id=identifier,
                    name=name,
                    phase_id=phase_id,
                    synced_at=datetime.utcnow(),
                    sync_status='synced'
                )
                self.db.add(new_elevation)
                self.db.commit()
                
                logger.debug(f"Created new elevation: {name} (ID: {identifier})")
                return new_elevation
                
        except Exception as e:
            logger.error(f"Failed to create or update elevation: {str(e)}")
            self.db.rollback()
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
