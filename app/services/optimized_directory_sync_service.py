import asyncio
import time
import logging
from datetime import datetime
from typing import Dict, List, Optional, Tuple, Set
from sqlalchemy.orm import Session
from sqlalchemy import and_
from models.directory import Directory
from models.sync_log import SyncLog
from services.auth_service import AuthService
from services.directory_service import DirectoryService

logger = logging.getLogger(__name__)


class OptimizedDirectorySyncService:
    """Highly optimized directory sync service with batch operations and minimal SQL"""
    
    def __init__(self, db: Session):
        self.db = db
        self.auth_service = AuthService(db)
    
    async def discover_and_sync_directories_optimized(self, base_url: str, username: str, password: str) -> Dict:
        """
        Optimized directory discovery and sync with batch database operations
        """
        sync_start_time = time.time()
        sync_log = None
        
        try:
            # Create sync log entry
            sync_log = SyncLog(
                sync_type='directory_optimized',
                status='started',
                message='Optimized directory discovery and sync started (batch operations)',
                started_at=datetime.utcnow()
            )
            self.db.add(sync_log)
            self.db.commit()
            
            logger.info("Starting optimized directory discovery and sync with batch operations")
            
            # Step 1: Discovery session
            root_directories = await self._discover_root_directories_optimized(base_url, username, password)
            logger.info(f"Discovery session found {len(root_directories)} root directories")
            
            # Step 2: Collect all directories for batch processing
            all_directories = []
            await self._collect_all_directories_optimized(
                base_url, username, password, root_directories, all_directories
            )
            
            logger.info(f"Collected {len(all_directories)} total directories for batch processing")
            
            # Step 3: Batch database operations
            total_directories = await self._batch_process_directories(all_directories)
            
            # Calculate duration
            duration = int(time.time() - sync_start_time)
            
            # Update sync log
            sync_log.status = 'completed'
            sync_log.message = f'Optimized directory sync completed successfully'
            sync_log.items_processed = total_directories
            sync_log.items_successful = total_directories
            sync_log.duration_seconds = duration
            sync_log.completed_at = datetime.utcnow()
            self.db.commit()
            
            logger.info(f"Optimized directory sync completed successfully in {duration} seconds")
            logger.info(f"Total directories processed: {total_directories}")
            
            return {
                'success': True,
                'message': 'Optimized directory discovery and sync completed successfully',
                'count': total_directories,
                'duration_seconds': duration,
                'directories_processed': total_directories,
                'optimization': 'batch_operations'
            }
            
        except Exception as e:
            duration = int(time.time() - sync_start_time)
            error_msg = f"Optimized directory discovery and sync failed: {str(e)}"
            logger.error(error_msg, exc_info=True)
            
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
    
    async def _discover_root_directories_optimized(self, base_url: str, username: str, password: str) -> List[Dict]:
        """Discover root directories with minimal logging and timeout handling"""
        try:
            # Create discovery session with minimal logging
            logger.info("Authenticating for root directory discovery")
            
            # Add timeout for authentication
            import asyncio
            success, token = await asyncio.wait_for(
                self.auth_service.authenticate(base_url, username, password),
                timeout=30.0  # 30 second timeout
            )
            
            if not success:
                raise Exception(f"Authentication failed: {token}")
            
            # Get root directories with logging disabled
            directory_service = DirectoryService(self.db, token, base_url, enable_logging=False)
            
            # Add timeout for directory retrieval
            logger.info("Fetching root directories")
            success, directories, message = await asyncio.wait_for(
                directory_service.get_directories(),
                timeout=60.0  # 60 second timeout
            )
            
            if not success:
                raise Exception(f"Failed to get root directories: {message}")
            
            logger.info(f"Discovery session retrieved {len(directories)} root directories")
            return directories
            
        except asyncio.TimeoutError:
            error_msg = "Root directory discovery timed out"
            logger.error(error_msg)
            raise Exception(error_msg)
        except Exception as e:
            logger.error(f"Root directory discovery failed: {str(e)}")
            raise
    
    async def _collect_all_directories_optimized(self, base_url: str, username: str, password: str,
                                              root_directories: List[Dict], all_directories: List[Dict]):
        """Collect all directories without database operations"""
        
        # Process each root directory tree with dedicated session
        for root_directory in root_directories:
            root_name = root_directory.get('name', 'Unknown')
            root_path = root_directory.get('path') or root_directory.get('name', '')
            
            logger.info(f"Collecting directories from root tree: {root_name}")
            
            # Check if excluded
            if await self._is_directory_excluded(root_directory):
                logger.info(f"Skipping excluded root directory: {root_name}")
                continue
            
            # Create dedicated session for this root tree
            success, token = await self.auth_service.authenticate(base_url, username, password)
            if not success:
                logger.error(f"Failed to authenticate for root directory tree: {root_name}")
                continue
            
            # Initialize directory service with minimal logging
            directory_service = DirectoryService(self.db, token, base_url, enable_logging=False)
            
            # Add root directory to collection
            all_directories.append({
                'data': root_directory,
                'parent_id': None,
                'level': 0
            })
            
            # Collect children recursively
            await self._collect_children_optimized(
                directory_service, root_directory, root_path, 0, all_directories
            )
    
    async def _collect_children_optimized(self, directory_service: DirectoryService, 
                                        parent_directory: Dict, parent_path: str, 
                                        parent_level: int, all_directories: List[Dict]):
        """Recursively collect child directories without database operations"""
        
        try:
            # Navigate to parent directory
            success, message = await directory_service.select_directory(parent_path)
            if not success:
                logger.warning(f"Failed to navigate to {parent_path}: {message}")
                return
            
            # Get children
            success, child_directories, message = await directory_service.get_directories()
            if not success or not child_directories:
                return
            
            # Process each child
            for child_directory in child_directories:
                child_path = child_directory.get('path')
                child_name = child_directory.get('name', 'Unknown')
                
                if not child_path:
                    logger.warning(f"Child folder missing 'path' field, skipping: {child_directory}")
                    continue
                
                # Add child to collection
                all_directories.append({
                    'data': child_directory,
                    'parent_path': parent_path,
                    'level': parent_level + 1
                })
                
                # Recursively collect grandchildren
                await self._collect_children_optimized(
                    directory_service, child_directory, child_path, parent_level + 1, all_directories
                )
                
        except Exception as e:
            logger.error(f"Error collecting children for {parent_directory.get('name', 'Unknown')}: {str(e)}")
    
    async def _batch_process_directories(self, all_directories: List[Dict]) -> int:
        """Process all directories with batch database operations"""
        
        if not all_directories:
            return 0
        
        logger.info(f"Starting batch processing of {len(all_directories)} directories")
        
        try:
            # Step 1: Get all existing directory identifiers for batch lookup
            identifiers = []
            for dir_info in all_directories:
                directory_data = dir_info['data']
                identifier = directory_data.get('path', directory_data.get('name', ''))
                if identifier:
                    identifiers.append(identifier)
            
            # Step 2: Batch SELECT existing directories
            existing_directories = {}
            if identifiers:
                existing_dirs = self.db.query(Directory).filter(
                    Directory.logikal_id.in_(identifiers)
                ).all()
                existing_directories = {dir.logikal_id: dir for dir in existing_dirs}
            
            logger.info(f"Found {len(existing_directories)} existing directories")
            
            # Step 3: Prepare batch operations
            updates = []
            inserts = []
            
            for dir_info in all_directories:
                directory_data = dir_info['data']
                identifier = directory_data.get('path', directory_data.get('name', ''))
                name = directory_data.get('name', 'Unnamed Directory')
                full_path = directory_data.get('path', name)
                level = dir_info['level']
                
                if not identifier:
                    continue
                
                # Determine parent_id (will be resolved in second pass)
                parent_identifier = dir_info.get('parent_path')
                parent_id = None  # Will be resolved later
                
                if identifier in existing_directories:
                    # Prepare for update
                    existing_dir = existing_directories[identifier]
                    updates.append({
                        'logikal_id': identifier,
                        'id': existing_dir.id,
                        'name': name,
                        'full_path': full_path,
                        'level': level,
                        'synced_at': datetime.utcnow(),
                        'sync_status': 'synced'
                    })
                else:
                    # Prepare for insert
                    inserts.append({
                        'logikal_id': identifier,
                        'name': name,
                        'full_path': full_path,
                        'level': level,
                        'parent_identifier': parent_identifier,  # Will resolve to parent_id
                        'exclude_from_sync': False,
                        'synced_at': datetime.utcnow(),
                        'sync_status': 'synced'
                    })
            
            # Step 4: Resolve parent_id relationships
            await self._resolve_parent_relationships(updates, inserts, existing_directories, all_directories)
            
            # Step 5: Execute batch operations
            await self._execute_batch_operations(updates, inserts)
            
            total_processed = len(updates) + len(inserts)
            logger.info(f"Batch processing completed: {len(updates)} updates, {len(inserts)} inserts")
            
            return total_processed
            
        except Exception as e:
            logger.error(f"Batch processing failed: {str(e)}")
            self.db.rollback()
            raise
    
    async def _resolve_parent_relationships(self, updates: List[Dict], inserts: List[Dict], 
                                          existing_directories: Dict[str, Directory], all_directories: List[Dict]):
        """Resolve parent_id relationships for batch operations"""
        
        # Create identifier to ID mapping for existing directories
        id_mapping = {dir.logikal_id: dir.id for dir in existing_directories.values()}
        
        # Create identifier to parent identifier mapping from collected data
        parent_mapping = {}
        for dir_info in all_directories:
            directory_data = dir_info['data']
            identifier = directory_data.get('path', directory_data.get('name', ''))
            parent_identifier = dir_info.get('parent_path')
            if identifier:
                parent_mapping[identifier] = parent_identifier
        
        # Resolve parent_id for updates (existing directories)
        for update_data in updates:
            existing_dir = existing_directories.get(update_data.get('logikal_id', ''))
            if existing_dir:
                # Keep existing parent_id for updates
                update_data['parent_id'] = existing_dir.parent_id
        
        # Resolve parent_id for inserts (new directories)
        for insert_data in inserts:
            identifier = insert_data.get('logikal_id', '')
            parent_identifier = parent_mapping.get(identifier)
            
            if parent_identifier and parent_identifier in id_mapping:
                insert_data['parent_id'] = id_mapping[parent_identifier]
            else:
                insert_data['parent_id'] = None
    
    async def _execute_batch_operations(self, updates: List[Dict], inserts: List[Dict]):
        """Execute batch database operations with proper error handling"""
        
        try:
            logger.info(f"Starting batch operations: {len(updates)} updates, {len(inserts)} inserts")
            
            # Batch updates - get all directories to update in one query
            if updates:
                update_ids = [update_data['id'] for update_data in updates]
                directories_to_update = self.db.query(Directory).filter(
                    Directory.id.in_(update_ids)
                ).all()
                
                # Create lookup for faster updates
                update_lookup = {update_data['id']: update_data for update_data in updates}
                
                for directory in directories_to_update:
                    if directory.id in update_lookup:
                        update_data = update_lookup[directory.id]
                        directory.name = update_data['name']
                        directory.full_path = update_data['full_path']
                        directory.level = update_data['level']
                        directory.synced_at = update_data['synced_at']
                        directory.sync_status = update_data['sync_status']
                        directory.parent_id = update_data.get('parent_id', directory.parent_id)
            
            # Batch inserts
            for insert_data in inserts:
                new_directory = Directory(
                    logikal_id=insert_data['logikal_id'],
                    name=insert_data['name'],
                    full_path=insert_data['full_path'],
                    level=insert_data['level'],
                    parent_id=insert_data.get('parent_id'),
                    exclude_from_sync=insert_data['exclude_from_sync'],
                    synced_at=insert_data['synced_at'],
                    sync_status=insert_data['sync_status']
                )
                self.db.add(new_directory)
            
            # Single commit for all operations
            self.db.commit()
            logger.info(f"Batch operations committed successfully: {len(updates)} updates, {len(inserts)} inserts")
            
        except Exception as e:
            logger.error(f"Batch operations failed: {str(e)}", exc_info=True)
            self.db.rollback()
            raise
    
    async def _is_directory_excluded(self, directory_data: Dict) -> bool:
        """Check if directory should be excluded from sync"""
        # Simple implementation - can be enhanced with database lookup if needed
        return False
