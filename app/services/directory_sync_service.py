import aiohttp
import time
import logging
import asyncio
from datetime import datetime
from typing import Dict, List, Optional, Tuple
from sqlalchemy.orm import Session
from models.directory import Directory
from models.sync_log import SyncLog
from services.auth_service import AuthService
from services.directory_service import DirectoryService

logger = logging.getLogger(__name__)


class DirectorySyncService:
    """Optimized service for discovering and syncing directories recursively"""
    
    def __init__(self, db: Session):
        self.db = db
        self.auth_service = AuthService(db)
        self.directory_service = None  # Will be initialized per operation
    
    async def discover_and_sync_directories(self, base_url: str, username: str, password: str) -> Dict:
        """
        Optimized directory discovery and sync following the Odoo module pattern
        Uses one session per root folder tree with path-based navigation
        """
        sync_start_time = time.time()
        sync_log = None
        
        try:
            # Create sync log entry
            sync_log = SyncLog(
                sync_type='directory',
                status='started',
                message='Optimized directory discovery and sync started',
                started_at=datetime.utcnow()
            )
            self.db.add(sync_log)
            self.db.commit()
            
            logger.info("Starting optimized directory discovery and sync")
            
            # Step 1: Discovery session to find root directories (one-time auth)
            root_directories = await self._discover_root_directories(base_url, username, password)
            logger.info(f"Discovery session found {len(root_directories)} root directories")
            
            total_directories = 0
            
            # Step 2: Process each root directory tree with dedicated session
            for root_directory in root_directories:
                root_name = root_directory.get('name', 'Unknown')
                root_path = root_directory.get('path') or root_directory.get('name', '')
                
                logger.info(f"Processing root directory tree: {root_name} (path: {root_path})")
                
                # Check if this root directory is excluded
                if await self._is_directory_excluded(root_directory):
                    logger.info(f"Skipping excluded root directory: {root_name}")
                    continue
                
                # Process the complete directory tree for this root with one session
                directory_count = await self._process_root_directory_tree(
                    base_url, username, password, root_directory
                )
                total_directories += directory_count
                logger.info(f"Completed root directory '{root_name}': {directory_count} total directories")
            
            # Calculate duration
            duration = int(time.time() - sync_start_time)
            
            # Update sync log
            sync_log.status = 'completed'
            sync_log.message = f'Optimized directory discovery and sync completed successfully'
            sync_log.items_processed = total_directories
            sync_log.items_successful = total_directories
            sync_log.duration_seconds = duration
            sync_log.completed_at = datetime.utcnow()
            self.db.commit()
            
            logger.info(f"Optimized directory discovery and sync completed successfully in {duration} seconds")
            logger.info(f"Total directories processed: {total_directories}")
            
            return {
                'success': True,
                'message': 'Optimized directory discovery and sync completed successfully',
                'count': total_directories,
                'duration_seconds': duration,
                'directories_processed': total_directories
            }
            
        except Exception as e:
            duration = int(time.time() - sync_start_time)
            error_msg = f"Optimized directory discovery and sync failed: {str(e)}"
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
    
    async def discover_and_sync_directories_concurrent(self, base_url: str, username: str, password: str) -> Dict:
        """
        Concurrent directory discovery and sync with 2 workers for conservative testing
        Uses asyncio.gather to process root directory trees in parallel
        """
        sync_start_time = time.time()
        sync_log = None
        
        try:
            # Create sync log entry
            sync_log = SyncLog(
                sync_type='directory_concurrent',
                status='started',
                message='Concurrent directory discovery and sync started (2 workers)',
                started_at=datetime.utcnow()
            )
            self.db.add(sync_log)
            self.db.commit()
            
            logger.info("Starting concurrent directory discovery and sync (2 workers)")
            
            # Step 1: Discovery session to find root directories (one-time auth)
            root_directories = await self._discover_root_directories(base_url, username, password)
            logger.info(f"Discovery session found {len(root_directories)} root directories")
            
            # Step 2: Filter out excluded directories
            processable_roots = []
            for root_directory in root_directories:
                if not await self._is_directory_excluded(root_directory):
                    processable_roots.append(root_directory)
                else:
                    logger.info(f"Skipping excluded root directory: {root_directory.get('name', 'Unknown')}")
            
            logger.info(f"Processing {len(processable_roots)} root directories concurrently")
            
            # Step 3: Process root directory trees concurrently with semaphore limit
            total_directories = await self._process_root_trees_concurrently(
                base_url, username, password, processable_roots
            )
            
            # Calculate duration
            duration = int(time.time() - sync_start_time)
            
            # Update sync log
            sync_log.status = 'completed'
            sync_log.message = f'Concurrent directory discovery and sync completed successfully'
            sync_log.items_processed = total_directories
            sync_log.items_successful = total_directories
            sync_log.duration_seconds = duration
            sync_log.completed_at = datetime.utcnow()
            self.db.commit()
            
            logger.info(f"Concurrent directory discovery and sync completed successfully in {duration} seconds")
            logger.info(f"Total directories processed: {total_directories}")
            
            return {
                'success': True,
                'message': 'Concurrent directory discovery and sync completed successfully',
                'count': total_directories,
                'duration_seconds': duration,
                'directories_processed': total_directories,
                'concurrent_workers': 2
            }
            
        except Exception as e:
            duration = int(time.time() - sync_start_time)
            error_msg = f"Concurrent directory discovery and sync failed: {str(e)}"
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
    
    async def _process_root_trees_concurrently(self, base_url: str, username: str, password: str, 
                                             root_directories: List[Dict]) -> int:
        """
        Process root directory trees concurrently with conservative 2-worker limit
        """
        # Conservative limit of 2 concurrent workers to avoid API overload
        MAX_CONCURRENT_WORKERS = 2
        semaphore = asyncio.Semaphore(MAX_CONCURRENT_WORKERS)
        
        async def process_with_semaphore(root_directory):
            """Process a single root directory tree with semaphore protection"""
            async with semaphore:
                root_name = root_directory.get('name', 'Unknown')
                logger.info(f"Starting concurrent processing of root directory tree: {root_name}")
                
                try:
                    result = await self._process_root_directory_tree(
                        base_url, username, password, root_directory
                    )
                    logger.info(f"Completed concurrent processing of '{root_name}': {result} directories")
                    return result
                except Exception as e:
                    logger.error(f"Error in concurrent processing of '{root_name}': {str(e)}")
                    return 0
        
        # Create tasks for all root directories
        tasks = [process_with_semaphore(rd) for rd in root_directories]
        
        # Process all root directory trees concurrently
        logger.info(f"Launching {len(tasks)} concurrent tasks with {MAX_CONCURRENT_WORKERS} worker limit")
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Aggregate results and handle exceptions
        total_directories = 0
        successful_tasks = 0
        failed_tasks = 0
        
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                logger.error(f"Task {i} failed with exception: {str(result)}")
                failed_tasks += 1
            else:
                total_directories += result
                successful_tasks += 1
        
        logger.info(f"Concurrent processing completed: {successful_tasks} successful, {failed_tasks} failed")
        logger.info(f"Total directories processed concurrently: {total_directories}")
        
        return total_directories
    
    async def _discover_root_directories(self, base_url: str, username: str, password: str) -> List[Dict]:
        """Discover root directories using a temporary session"""
        try:
            # Create discovery session
            logger.info("Authenticating for root directory discovery")
            success, token = await self.auth_service.authenticate(base_url, username, password)
            
            if not success:
                raise Exception(f"Authentication failed: {token}")
            
            # Get root directories
            directory_service = DirectoryService(self.db, token, base_url)
            success, directories, message = await directory_service.get_directories()
            
            if not success:
                raise Exception(f"Failed to get root directories: {message}")
            
            logger.info(f"Discovery session retrieved {len(directories)} root directories")
            return directories
            
        except Exception as e:
            logger.error(f"Root directory discovery failed: {str(e)}")
            raise
    
    async def _process_root_directory_tree(self, base_url: str, username: str, password: str, 
                                         root_directory: Dict) -> int:
        """
        Process a complete root directory tree with dedicated session using path-based navigation
        Following the Odoo module pattern for optimized session management
        """
        directory_count = 0
        
        try:
            # Extract root directory information
            root_name = root_directory.get('name', 'Unknown')
            root_path = root_directory.get('path') or root_directory.get('name', '')
            
            if not root_path:
                raise ValueError(f"Root directory missing 'path' and 'name' fields: {root_directory}")
            
            logger.info(f"Starting dedicated session for root directory tree: {root_name} (path: {root_path})")
            
            # Create dedicated session for this root directory tree
            success, token = await self.auth_service.authenticate(base_url, username, password)
            
            if not success:
                logger.error(f"Failed to authenticate for root directory tree: {root_name}")
                return directory_count
            
            # Initialize directory service with the session
            directory_service = DirectoryService(self.db, token, base_url)
            
            # Select the root directory using path-based navigation
            logger.info(f"Selecting root directory using path: {root_path}")
            success, message = await directory_service.select_directory(root_path)
            
            if not success:
                logger.warning(f"Failed to select root directory {root_path}: {message}")
                # Continue anyway - the directory might still be accessible
            
            # Create the root directory record
            root_directory_record = await self._create_or_update_directory(root_directory, parent_id=None, level=0)
            directory_count += 1
            logger.debug(f"Created root directory record: {root_name} (path: {root_path})")
            
            # Process all children recursively within this session using path-based navigation
            child_count = await self._process_folder_children_optimized(
                directory_service, root_directory_record, root_path
            )
            directory_count += child_count
            
            logger.info(f"Completed root directory tree '{root_name}': {directory_count} total directories")
            return directory_count
            
        except Exception as e:
            logger.error(f"Error processing root directory tree '{root_name}': {str(e)}")
            raise
    
    async def _process_folder_children_optimized(self, directory_service: DirectoryService, 
                                               parent_folder_record: 'Directory', parent_path: str) -> int:
        """
        Process child folders using path-based navigation with state continuity
        Following the Odoo module pattern for recursive tree processing
        """
        child_count = 0
        
        try:
            # Get child directories of currently selected folder
            success, child_directories, message = await directory_service.get_directories()
            
            if not success:
                logger.warning(f"Failed to get children for folder {parent_folder_record.name}: {message}")
                return child_count
            
            logger.info(f"Found {len(child_directories)} children in folder: {parent_folder_record.name}")
            
            if not child_directories:
                logger.debug(f"No children found in folder: {parent_folder_record.name}")
                return child_count
            
            # Process children with path-based navigation (state continuity)
            logger.info(f"Processing {len(child_directories)} child folders with path-based navigation")
            
            for child_folder in child_directories:
                try:
                    # Use 'path' for navigation, 'name' for display (following Odoo pattern)
                    child_path = child_folder.get('path')  # Full path for API navigation
                    child_name = child_folder.get('name', 'Unknown')  # Display name
                    
                    if not child_path:
                        logger.warning(f"Child folder missing 'path' field, skipping: {child_folder}")
                        continue
                    
                    # Create child folder record
                    child_folder_record = await self._create_or_update_directory(
                        child_folder, 
                        parent_id=parent_folder_record.id,
                        level=parent_folder_record.level + 1
                    )
                    child_count += 1
                    logger.debug(f"Created child folder record: {child_name} (path: {child_path})")
                    
                    # Navigate to child using full path (state continuity)
                    try:
                        logger.info(f"Navigating to child folder using path: {child_path}")
                        success, message = await directory_service.select_directory(child_path)
                        
                        if not success:
                            logger.warning(f"Failed to navigate to child folder {child_path}: {message}")
                            # Continue with next child
                            continue
                        
                        logger.info(f"Successfully navigated to: {child_name} (path: {child_path})")
                        
                        # Recursively process grandchildren within same session
                        grandchild_count = await self._process_folder_children_optimized(
                            directory_service, child_folder_record, child_path
                        )
                        child_count += grandchild_count
                        
                        # Return to parent context using stored path (state management)
                        logger.debug(f"Returning to parent context using path: {parent_path}")
                        success, message = await directory_service.select_directory(parent_path)
                        
                        if not success:
                            logger.warning(f"Failed to return to parent context {parent_path}: {message}")
                            # Session state may be corrupted, but continue
                        
                        logger.debug(f"Successfully returned to parent: {parent_folder_record.name}")
                        
                    except Exception as nav_error:
                        logger.error(f"Path-based navigation failed for '{child_path}': {str(nav_error)}")
                        logger.error("This indicates API path format issue or access permissions")
                        
                        # Attempt to recover parent context using path
                        try:
                            success, message = await directory_service.select_directory(parent_path)
                            if success:
                                logger.info(f"Recovered parent context using path: {parent_path}")
                            else:
                                logger.error(f"Failed to recover parent context: {message}")
                        except Exception as recovery_error:
                            logger.error(f"Failed to recover parent context: {str(recovery_error)}")
                            # Continue with next child - session state may be corrupted
                        
                        # Continue with next child
                        continue
                    
                except Exception as e:
                    logger.error(f"Error processing child folder '{child_folder.get('name')}': {str(e)}")
                    # Continue with next child
            
            logger.info(f"Completed child processing for '{parent_folder_record.name}': {child_count} total folders")
            return child_count
            
        except Exception as e:
            logger.error(f"Error processing children of folder '{parent_folder_record.name}': {str(e)}")
            raise
    
    async def _process_directory_tree(self, base_url: str, username: str, password: str, 
                                    directory_data: Dict, parent_id: Optional[int], level: int) -> int:
        """
        Process a complete directory tree recursively
        Following the Odoo module pattern for path-based navigation
        """
        directory_count = 0
        
        try:
            # Validate directory data
            if not directory_data or not directory_data.get('name'):
                logger.warning(f"Skipping invalid directory data: {directory_data}")
                return directory_count
            
            # Create or update directory record
            directory_record = await self._create_or_update_directory(directory_data, parent_id, level)
            directory_count += 1
            
            # Create dedicated session for this directory tree
            logger.info(f"Creating session for directory: {directory_data.get('name', 'Unknown')}")
            success, token = await self.auth_service.authenticate(base_url, username, password)
            
            if not success:
                logger.error(f"Failed to authenticate for directory {directory_data.get('name', 'Unknown')}")
                return directory_count
            
            # Select the directory using path-based navigation
            directory_path = directory_data.get('path', directory_data.get('name', ''))
            if directory_path:
                directory_service = DirectoryService(self.db, token, base_url)
                
                # Try to select the directory, but don't fail if it doesn't exist
                success, message = await directory_service.select_directory(directory_path)
                
                if not success:
                    logger.warning(f"Failed to select directory {directory_path}: {message}")
                    # Don't return here - continue to process children if possible
                    # The directory might exist but not be accessible from current context
                
                # Get child directories regardless of selection success
                success, child_directories, message = await directory_service.get_directories()
                
                if success and child_directories:
                    logger.info(f"Found {len(child_directories)} children in directory: {directory_data.get('name', 'Unknown')}")
                    
                    # Process each child directory recursively
                    for child_directory in child_directories:
                        # Validate child directory data
                        if not child_directory or not child_directory.get('name'):
                            logger.warning(f"Skipping invalid child directory data: {child_directory}")
                            continue
                        
                        # Check if child directory is excluded
                        if await self._is_directory_excluded(child_directory):
                            logger.info(f"Skipping excluded child directory: {child_directory.get('name', 'Unknown')}")
                            continue
                        
                        # Recursively process child directory
                        child_count = await self._process_directory_tree(
                            base_url, username, password, child_directory, 
                            directory_record.id, level + 1
                        )
                        directory_count += child_count
                else:
                    logger.debug(f"No children found in directory: {directory_data.get('name', 'Unknown')}")
            
            return directory_count
            
        except Exception as e:
            logger.error(f"Error processing directory tree for {directory_data.get('name', 'Unknown')}: {str(e)}")
            return directory_count
    
    async def _create_or_update_directory(self, directory_data: Dict, parent_id: Optional[int], level: int) -> Directory:
        """Create or update a directory record from API data"""
        try:
            # Extract identifier - Logikal API uses 'path' field as identifier
            identifier = directory_data.get('path', directory_data.get('name', ''))
            name = directory_data.get('name', 'Unnamed Directory')
            full_path = directory_data.get('path', name)
            
            if not identifier:
                raise ValueError(f"Directory data missing both 'path' and 'name' fields: {directory_data}")
            
            # Check if directory already exists
            existing_directory = self.db.query(Directory).filter(
                Directory.logikal_id == identifier
            ).first()
            
            if existing_directory:
                # Update existing directory
                existing_directory.name = name
                existing_directory.full_path = full_path
                existing_directory.level = level
                existing_directory.parent_id = parent_id
                existing_directory.synced_at = datetime.utcnow()
                existing_directory.sync_status = 'synced'
                self.db.commit()
                
                logger.debug(f"Updated existing directory: {name} (path: {identifier})")
                return existing_directory
            else:
                # Create new directory
                new_directory = Directory(
                    logikal_id=identifier,
                    name=name,
                    full_path=full_path,
                    level=level,
                    parent_id=parent_id,
                    exclude_from_sync=False,  # Default to not excluded
                    synced_at=datetime.utcnow(),
                    sync_status='synced'
                )
                self.db.add(new_directory)
                self.db.commit()
                
                logger.debug(f"Created new directory: {name} (path: {identifier})")
                return new_directory
                
        except Exception as e:
            logger.error(f"Failed to create or update directory: {str(e)}")
            self.db.rollback()
            raise
    
    async def _is_directory_excluded(self, directory_data: Dict) -> bool:
        """Check if a directory should be excluded from sync"""
        try:
            # Extract identifier
            identifier = directory_data.get('path', directory_data.get('name', ''))
            
            if not identifier:
                return False
            
            # Check if directory is marked as excluded
            existing_directory = self.db.query(Directory).filter(
                Directory.logikal_id == identifier
            ).first()
            
            if existing_directory:
                return existing_directory.exclude_from_sync or existing_directory.is_excluded_from_sync()
            
            return False
            
        except Exception as e:
            logger.error(f"Error checking directory exclusion: {str(e)}")
            return False
    
    async def get_syncable_directories(self) -> List[Directory]:
        """Get directories that should be included in sync operations"""
        try:
            # Get directories that are not excluded from sync
            directories = self.db.query(Directory).filter(
                Directory.exclude_from_sync == False
            ).all()
            logger.info(f"Retrieved {len(directories)} syncable directories")
            return directories
        except Exception as e:
            logger.error(f"Failed to get syncable directories: {str(e)}")
            return []

    async def sync_directories_from_logikal(self, base_url: str, username: str, password: str) -> Dict:
        """
        Force sync directories from Logikal API for Odoo integration
        This method provides a simplified interface for forced directory sync
        """
        sync_start_time = time.time()
        sync_log = None
        
        try:
            # Create sync log entry
            sync_log = SyncLog(
                sync_type='directory_force',
                status='started',
                message='Force sync directories from Logikal started',
                started_at=datetime.utcnow()
            )
            self.db.add(sync_log)
            self.db.commit()
            
            logger.info("Starting force sync directories from Logikal")
            
            # Use the existing discover_and_sync_directories method
            result = await self.discover_and_sync_directories(base_url, username, password)
            
            duration = time.time() - sync_start_time
            
            # Update sync log
            if sync_log:
                sync_log.status = 'completed' if result['success'] else 'failed'
                sync_log.message = result.get('message', 'Force sync completed')
                sync_log.completed_at = datetime.utcnow()
                sync_log.duration_seconds = duration
                self.db.commit()
            
            # Return simplified result for Odoo integration
            return {
                'success': result['success'],
                'message': result.get('message', 'Force sync directories completed'),
                'directories_processed': result.get('directories_processed', 0),
                'duration_seconds': duration
            }
            
        except Exception as e:
            duration = time.time() - sync_start_time
            error_msg = f"Force sync directories failed: {str(e)}"
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
                'directories_processed': 0,
                'duration_seconds': duration
            }
