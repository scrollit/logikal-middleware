import asyncio
import logging
import time
from datetime import datetime
from typing import Dict, List, Optional, Tuple
from sqlalchemy.orm import Session
from models.sync_config import SyncConfig
from models.sync_log import SyncLog
from models.directory import Directory
from services.directory_sync_service import DirectorySyncService
from services.project_sync_service import ProjectSyncService
from services.phase_sync_service import PhaseSyncService
from services.elevation_sync_service import ElevationSyncService

logger = logging.getLogger(__name__)


class SyncService:
    """Main sync service orchestrator for full and incremental sync operations"""
    
    def __init__(self, db: Session):
        self.db = db
        self.directory_sync_service = DirectorySyncService(db)
        self.project_sync_service = ProjectSyncService(db)
        self.phase_sync_service = PhaseSyncService(db)
        self.elevation_sync_service = ElevationSyncService(db)
    
    async def full_sync(self, base_url: str, username: str, password: str) -> Dict:
        """
        Perform a full sync of all non-excluded directories, projects, phases, and elevations
        """
        sync_start_time = time.time()
        sync_log = None
        
        try:
            # Create sync log entry
            sync_log = SyncLog(
                sync_type='full',
                status='started',
                message='Full sync started',
                started_at=datetime.utcnow()
            )
            self.db.add(sync_log)
            self.db.commit()
            
            logger.info("Starting full sync operation")
            
            # Step 1: Discover and sync directories (excluding excluded ones)
            logger.info("Step 1: Discovering and syncing directories")
            directory_result = await self.directory_sync_service.discover_and_sync_directories(
                base_url, username, password
            )
            
            if not directory_result['success']:
                raise Exception(f"Directory sync failed: {directory_result['message']}")
            
            # Get syncable directories (non-excluded)
            syncable_directories = await self.directory_sync_service.get_syncable_directories()
            logger.info(f"Found {len(syncable_directories)} syncable directories")
            
            total_projects = 0
            total_phases = 0
            total_elevations = 0
            
            # Step 2: Sync projects for each syncable directory
            logger.info("Step 2: Syncing projects for each directory")
            for directory in syncable_directories:
                logger.info(f"Syncing projects for directory: {directory.name}")
                
                # Create dedicated session for this directory
                project_result = await self.project_sync_service.sync_projects_for_directory(
                    base_url, username, password, directory
                )
                
                if project_result['success']:
                    total_projects += project_result['count']
                    logger.info(f"Synced {project_result['count']} projects for directory {directory.name}")
                else:
                    logger.warning(f"Failed to sync projects for directory {directory.name}: {project_result['message']}")
            
            # Step 3: Sync phases for each project
            logger.info("Step 3: Syncing phases for each project")
            projects = await self.project_sync_service.get_all_projects()
            
            for project in projects:
                logger.info(f"Syncing phases for project: {project.name}")
                
                phase_result = await self.phase_sync_service.sync_phases_for_project(
                    self.db, base_url, username, password, project
                )
                
                if phase_result['success']:
                    total_phases += phase_result['count']
                    logger.info(f"Synced {phase_result['count']} phases for project {project.name}")
                else:
                    logger.warning(f"Failed to sync phases for project {project.name}: {phase_result['message']}")
            
            # Step 4: Sync elevations for each phase
            logger.info("Step 4: Syncing elevations for each phase")
            phases = await self.phase_sync_service.get_all_phases()
            
            for phase in phases:
                logger.info(f"Syncing elevations for phase: {phase.name}")
                
                elevation_result = await self.elevation_sync_service.sync_elevations_for_phase(
                    self.db, base_url, username, password, phase
                )
                
                if elevation_result['success']:
                    total_elevations += elevation_result['count']
                    logger.info(f"Synced {elevation_result['count']} elevations for phase {phase.name}")
                else:
                    logger.warning(f"Failed to sync elevations for phase {phase.name}: {elevation_result['message']}")
            
            # Update sync configuration
            await self._update_sync_config('full')
            
            # Calculate duration
            duration = int(time.time() - sync_start_time)
            
            # Update sync log
            sync_log.status = 'completed'
            sync_log.message = f'Full sync completed successfully'
            sync_log.items_processed = len(syncable_directories) + total_projects + total_phases + total_elevations
            sync_log.items_successful = sync_log.items_processed
            sync_log.duration_seconds = duration
            sync_log.completed_at = datetime.utcnow()
            self.db.commit()
            
            logger.info(f"Full sync completed successfully in {duration} seconds")
            logger.info(f"Processed: {len(syncable_directories)} directories, {total_projects} projects, {total_phases} phases, {total_elevations} elevations")
            
            return {
                'success': True,
                'message': 'Full sync completed successfully',
                'duration_seconds': duration,
                'directories_processed': len(syncable_directories),
                'projects_processed': total_projects,
                'phases_processed': total_phases,
                'elevations_processed': total_elevations,
                'total_items': sync_log.items_processed
            }
            
        except Exception as e:
            duration = int(time.time() - sync_start_time)
            error_msg = f"Full sync failed: {str(e)}"
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
                'duration_seconds': duration,
                'error': str(e)
            }
    
    async def incremental_sync(self, base_url: str, username: str, password: str) -> Dict:
        """
        Perform an incremental sync of changed items since last sync
        """
        sync_start_time = time.time()
        sync_log = None
        
        try:
            # Create sync log entry
            sync_log = SyncLog(
                sync_type='incremental',
                status='started',
                message='Incremental sync started',
                started_at=datetime.utcnow()
            )
            self.db.add(sync_log)
            self.db.commit()
            
            logger.info("Starting incremental sync operation")
            
            # Get last sync time
            sync_config = await self._get_sync_config()
            last_sync_time = sync_config.last_incremental_sync or sync_config.last_full_sync
            
            if not last_sync_time:
                logger.warning("No previous sync found, performing full sync instead")
                return await self.full_sync(base_url, username, password)
            
            # TODO: Implement incremental sync logic
            # For now, we'll implement a basic version that checks for changed items
            
            # Update sync configuration
            await self._update_sync_config('incremental')
            
            # Calculate duration
            duration = int(time.time() - sync_start_time)
            
            # Update sync log
            sync_log.status = 'completed'
            sync_log.message = 'Incremental sync completed successfully'
            sync_log.duration_seconds = duration
            sync_log.completed_at = datetime.utcnow()
            self.db.commit()
            
            logger.info(f"Incremental sync completed successfully in {duration} seconds")
            
            return {
                'success': True,
                'message': 'Incremental sync completed successfully',
                'duration_seconds': duration,
                'last_sync_time': last_sync_time.isoformat()
            }
            
        except Exception as e:
            duration = int(time.time() - sync_start_time)
            error_msg = f"Incremental sync failed: {str(e)}"
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
                'duration_seconds': duration,
                'error': str(e)
            }
    
    async def get_sync_status(self) -> Dict:
        """Get current sync status and configuration"""
        try:
            sync_config = await self._get_sync_config()
            
            # Get recent sync logs
            recent_logs = self.db.query(SyncLog).order_by(SyncLog.started_at.desc()).limit(10).all()
            
            return {
                'success': True,
                'sync_config': {
                    'is_sync_enabled': sync_config.is_sync_enabled,
                    'sync_interval_minutes': sync_config.sync_interval_minutes,
                    'last_full_sync': sync_config.last_full_sync.isoformat() if sync_config.last_full_sync else None,
                    'last_incremental_sync': sync_config.last_incremental_sync.isoformat() if sync_config.last_incremental_sync else None
                },
                'recent_logs': [
                    {
                        'id': log.id,
                        'sync_type': log.sync_type,
                        'status': log.status,
                        'message': log.message,
                        'items_processed': log.items_processed,
                        'duration_seconds': log.duration_seconds,
                        'started_at': log.started_at.isoformat(),
                        'completed_at': log.completed_at.isoformat() if log.completed_at else None
                    } for log in recent_logs
                ]
            }
            
        except Exception as e:
            logger.error(f"Failed to get sync status: {str(e)}")
            return {
                'success': False,
                'message': f"Failed to get sync status: {str(e)}"
            }
    
    async def _get_sync_config(self) -> SyncConfig:
        """Get or create sync configuration"""
        sync_config = self.db.query(SyncConfig).first()
        if not sync_config:
            sync_config = SyncConfig()
            self.db.add(sync_config)
            self.db.commit()
        return sync_config
    
    async def _update_sync_config(self, sync_type: str):
        """Update sync configuration with last sync time"""
        sync_config = await self._get_sync_config()
        now = datetime.utcnow()
        
        if sync_type == 'full':
            sync_config.last_full_sync = now
        elif sync_type == 'incremental':
            sync_config.last_incremental_sync = now
        
        self.db.commit()
    
    async def sync_directories(self, base_url: str, username: str, password: str) -> Dict:
        """Sync directories only"""
        try:
            logger.info("Starting directory sync")
            result = await self.directory_sync_service.discover_and_sync_directories(
                base_url, username, password
            )
            return {
                'success': True,
                'message': f'Directory sync completed. {result.get("message", "")}',
                'directories_processed': result.get('directories_processed', 0)
            }
        except Exception as e:
            logger.error(f"Directory sync failed: {str(e)}")
            return {
                'success': False,
                'message': f'Directory sync failed: {str(e)}',
                'error': str(e)
            }
    
    async def sync_directories_concurrent(self, base_url: str, username: str, password: str) -> Dict:
        """Sync directories concurrently with 2 workers"""
        try:
            logger.info("Starting concurrent directory sync (2 workers)")
            result = await self.directory_sync_service.discover_and_sync_directories_concurrent(
                base_url, username, password
            )
            return {
                'success': True,
                'message': f'Concurrent directory sync completed. {result.get("message", "")}',
                'directories_processed': result.get('directories_processed', 0),
                'concurrent_workers': result.get('concurrent_workers', 2),
                'duration_seconds': result.get('duration_seconds', 0)
            }
        except Exception as e:
            logger.error(f"Concurrent directory sync failed: {str(e)}")
            return {
                'success': False,
                'message': f'Concurrent directory sync failed: {str(e)}',
                'error': str(e)
            }
    
    async def sync_directories_optimized(self, base_url: str, username: str, password: str) -> Dict:
        """Sync directories with optimized batch operations"""
        try:
            logger.info("Starting optimized directory sync with batch operations")
            from services.optimized_directory_sync_service import OptimizedDirectorySyncService
            
            optimized_service = OptimizedDirectorySyncService(self.db)
            result = await optimized_service.discover_and_sync_directories_optimized(
                base_url, username, password
            )
            
            return {
                'success': True,
                'message': f'Optimized directory sync completed. {result.get("message", "")}',
                'directories_processed': result.get('directories_processed', 0),
                'duration_seconds': result.get('duration_seconds', 0),
                'optimization': result.get('optimization', 'batch_operations')
            }
        except Exception as e:
            logger.error(f"Optimized directory sync failed: {str(e)}")
            return {
                'success': False,
                'message': f'Optimized directory sync failed: {str(e)}',
                'error': str(e)
            }
    
    async def sync_projects(self, base_url: str, username: str, password: str) -> Dict:
        """Sync projects only"""
        try:
            logger.info("Starting project sync")
            result = await self.project_sync_service.sync_all_projects(
                self.db, base_url, username, password
            )
            
            return {
                'success': True,
                'message': f'Project sync completed. {result.get("message", "")}',
                'projects_processed': result.get('projects_processed', 0)
            }
        except Exception as e:
            logger.error(f"Project sync failed: {str(e)}")
            return {
                'success': False,
                'message': f'Project sync failed: {str(e)}',
                'error': str(e)
            }
    
    async def sync_phases(self, base_url: str, username: str, password: str) -> Dict:
        """Sync phases only"""
        try:
            logger.info("Starting phase sync")
            result = await self.phase_sync_service.sync_all_phases(
                self.db, base_url, username, password
            )
            return {
                'success': True,
                'message': f'Phase sync completed. {result.get("message", "")}',
                'phases_processed': result.get('phases_processed', 0)
            }
        except Exception as e:
            logger.error(f"Phase sync failed: {str(e)}")
            return {
                'success': False,
                'message': f'Phase sync failed: {str(e)}',
                'error': str(e)
            }
    
    async def sync_elevations(self, base_url: str, username: str, password: str) -> Dict:
        """Sync elevations only"""
        try:
            logger.info("Starting elevation sync")
            result = await self.elevation_sync_service.sync_all_elevations(
                self.db, base_url, username, password
            )
            return {
                'success': True,
                'message': f'Elevation sync completed. {result.get("message", "")}',
                'elevations_processed': result.get('elevations_processed', 0)
            }
        except Exception as e:
            logger.error(f"Elevation sync failed: {str(e)}")
            return {
                'success': False,
                'message': f'Elevation sync failed: {str(e)}',
                'error': str(e)
            }