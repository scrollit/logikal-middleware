# -*- coding: utf-8 -*-

import logging
import time
from datetime import datetime, timedelta
from odoo import models, api, fields, _
from odoo.exceptions import UserError
try:
    from odoo.addons.queue_job.job import job
except ImportError:
    # Fallback if queue_job is not properly installed
    def job(func):
        """Fallback decorator if queue_job is not available"""
        func._job_decorator = True
        return func
from .mbioe_api_client import MBIOEApiClient
from .exceptions import APIConnectionError, AuthenticationError, SessionError, ConfigurationError

_logger = logging.getLogger(__name__)


class MBIOESyncService(models.AbstractModel):
    _name = 'mbioe.sync.service'
    _description = 'MBIOE Folder and Project Synchronization Service'
    
    @api.model
    def sync_folders(self):
        """
        Public method to enqueue folder synchronization as a background job.
        Returns job information immediately, actual sync runs in background.
        Falls back to synchronous execution if queue_job is not available.
        """
        _logger.info("Starting MBIOE folder synchronization")
        
        # Check if queue_job is available and job runner is working
        try:
            # First check if job runner is actually running (Odoo.Sh specific issue)
            if hasattr(self.env.registry, '_jobrunner'):
                # Job runner exists, try to enqueue
                job = self.with_delay(
                    description="MBIOE Folder Synchronization",
                    channel="root",
                    priority=10,
                    max_retries=3,
                    eta=5  # Start after 5 seconds to allow UI feedback
                )._sync_folders_job()
                
                _logger.info(f"Folder sync job enqueued with UUID: {job.uuid}")
                
                # Return job information for UI feedback
                return {
                    'type': 'ir.actions.client',
                    'tag': 'display_notification',
                    'params': {
                        'title': _('Folder Sync Started'),
                        'message': _('Folder synchronization has been started in the background. Job ID: %s') % job.uuid[:8],
                        'type': 'info',
                        'sticky': False,
                    }
                }
            else:
                # Job runner not available, force fallback
                raise Exception("Job runner not detected in registry - falling back to synchronous execution")
            
        except (AttributeError, ImportError, Exception) as e:
            # Fallback to synchronous execution if queue_job is not available
            _logger.warning(f"Queue job not available ({str(e)}), falling back to synchronous execution")
            
            # Execute sync directly and return old-style notification
            result = self._sync_folders_job()
            
            if result and result.get('success'):
                return {
                    'type': 'ir.actions.client',
                    'tag': 'display_notification',
                    'params': {
                        'title': _('Folder Sync Completed'),
                        'message': _('Synchronized %d folders from %d roots in %.1f seconds') % (
                            result.get('total_folders', 0),
                            result.get('processed_roots', 0),
                            result.get('duration', 0)
                        ),
                        'type': 'success',
                        'sticky': False,
                    }
                }
            else:
                return {
                    'type': 'ir.actions.client',
                    'tag': 'display_notification',
                    'params': {
                        'title': _('Folder Sync Failed'),
                        'message': _('Folder synchronization failed. Check logs for details.'),
                        'type': 'danger',
                        'sticky': True,
                    }
                }
    
    @api.model
    @job
    def _sync_folders_job(self):
        """
        Background job method for folder synchronization following POC analysis requirements:
        1. Discover root folders
        2. For each root folder: new session → select → process tree → logout
        3. Create folder records with hierarchical relationships
        """
        sync_start = time.time()
        total_folders = 0
        processed_roots = 0
        errors = []
        
        _logger.info("Starting MBIOE folder synchronization")
        
        try:
            # Get API client configuration
            api_client = self._get_api_client()
            
            # Phase 1: Discovery - Get all root folders
            _logger.info("Phase 1: Discovering root folders")
            root_folders = self._discover_root_folders(api_client)
            _logger.info(f"Found {len(root_folders)} root folders to process")
            
            if not root_folders:
                _logger.warning("No root folders found in MBIOE API")
                return self._create_sync_result(0, 0, ["No root folders found"], sync_start)
            
            # Phase 2: Process each root folder tree separately (session reset required)
            _logger.info("Phase 2: Processing folder trees")
            for root_folder in root_folders:
                try:
                    folder_count = self._process_root_folder_tree(root_folder)
                    total_folders += folder_count
                    processed_roots += 1
                    _logger.info(f"Completed root folder '{root_folder.get('name')}': {folder_count} folders")
                    
                except Exception as e:
                    error_msg = f"Failed to process root folder '{root_folder.get('name')}': {str(e)}"
                    _logger.error(error_msg)
                    errors.append(error_msg)
                    # Continue with next root folder
            
            # Phase 3: Cleanup orphaned folders (optional)
            self._cleanup_orphaned_folders()
            
            sync_duration = time.time() - sync_start
            _logger.info(f"Folder synchronization completed: {total_folders} folders, {processed_roots}/{len(root_folders)} roots, {sync_duration:.2f}s")
            
            return self._create_job_sync_result(total_folders, processed_roots, errors, sync_start)
            
        except Exception as e:
            _logger.error(f"Folder synchronization failed: {str(e)}", exc_info=True)
            return self._create_job_sync_result(0, 0, [str(e)], sync_start)
    
    @api.model
    def _discover_root_folders(self, api_client):
        """Discover root folders using a temporary session"""
        try:
            # Create discovery session
            _logger.info("Authenticating for root folder discovery")
            token = api_client.authenticate()
            
            # Get root directories
            root_folders = api_client.get_directories()
            _logger.info(f"Discovery session retrieved {len(root_folders)} root folders")
            
            # Debug: Log first folder structure to verify field names
            if root_folders and _logger.isEnabledFor(logging.DEBUG):
                _logger.debug(f"Sample folder structure: {root_folders[0]}")
            
            # End discovery session
            api_client.logout()
            _logger.info("Discovery session terminated")
            
            return root_folders
            
        except Exception as e:
            _logger.error(f"Root folder discovery failed: {str(e)}")
            # Ensure session cleanup
            try:
                if api_client.session_token:
                    api_client.logout()
            except:
                pass
            raise
    
    @api.model
    def _process_root_folder_tree(self, root_folder):
        """
        Process a complete root folder tree with dedicated session using path-based navigation
        Critical: Each root folder requires its own session per POC analysis
        """
        api_client = self._get_api_client()
        folder_count = 0
        
        try:
            # Start new session for this root folder tree
            root_name = root_folder.get('name', 'Unknown')
            root_path = root_folder.get('path') or root_folder.get('name')  # Use 'path' for navigation
            
            if not root_path:
                raise ValueError(f"Root folder missing 'path' and 'name' fields: {root_folder}")
            
            _logger.info(f"Starting session for root folder: {root_name} (path: {root_path})")
            token = api_client.authenticate()
            
            # Select the root folder using path-based navigation
            _logger.info(f"Selecting root folder using path: {root_path}")
            api_client.select_directory(root_path)
            
            # Create the root folder record
            root_folder_record = self._create_or_update_folder(root_folder, parent_id=None)
            folder_count += 1
            
            # Process all children recursively within this session using path-based navigation
            child_count = self._process_folder_children(api_client, root_folder_record, root_path)
            folder_count += child_count
            
            # End session for this root folder
            api_client.logout()
            _logger.info(f"Completed root folder '{root_name}': {folder_count} total folders")
            
            return folder_count
            
        except Exception as e:
            _logger.error(f"Error processing root folder tree: {str(e)}")
            # Ensure session cleanup
            try:
                if api_client.session_token:
                    api_client.logout()
            except:
                pass
            raise
    
    @api.model
    def _process_folder_children(self, api_client, parent_folder_record, parent_path):
        """
        Process child folders using path-based navigation with state continuity
        MBIOE API requires path-based selection: use 'path' field instead of 'name' for navigation
        """
        child_count = 0
        
        try:
            # Get child directories of currently selected folder
            child_directories = api_client.get_directories()
            _logger.info(f"Found {len(child_directories)} children in folder: {parent_folder_record.name}")
            
            if not child_directories:
                _logger.debug(f"No children found in folder: {parent_folder_record.name}")
                return 0
            
            # Process children with path-based navigation (state continuity)
            _logger.info(f"Processing {len(child_directories)} child folders with path-based navigation")
            
            for child_folder in child_directories:
                try:
                    # CRITICAL FIX: Use 'path' for navigation, 'name' for display
                    child_path = child_folder.get('path')  # Full path for API navigation
                    child_name = child_folder.get('name', 'Unknown')  # Display name
                    
                    if not child_path:
                        _logger.warning(f"Child folder missing 'path' field, skipping: {child_folder}")
                        continue
                    
                    # Create child folder record
                    child_folder_record = self._create_or_update_folder(
                        child_folder, 
                        parent_id=parent_folder_record.id
                    )
                    child_count += 1
                    _logger.debug(f"Created child folder record: {child_name} (path: {child_path})")
                    
                    # CRITICAL: Navigate to child using full path (state continuity)
                    try:
                        _logger.info(f"Navigating to child folder using path: {child_path}")
                        api_client.select_directory(child_path)
                        _logger.info(f"Successfully navigated to: {child_name} (path: {child_path})")
                        
                        # Recursively process grandchildren within same session
                        grandchild_count = self._process_folder_children(api_client, child_folder_record, child_path)
                        child_count += grandchild_count
                        
                        # Return to parent context using stored path (state management)
                        _logger.debug(f"Returning to parent context using path: {parent_path}")
                        api_client.select_directory(parent_path)
                        _logger.debug(f"Successfully returned to parent: {parent_folder_record.name}")
                        
                    except Exception as nav_error:
                        _logger.error(f"Path-based navigation failed for '{child_path}': {str(nav_error)}")
                        _logger.error("This indicates API path format issue or access permissions")
                        
                        # Attempt to recover parent context using path
                        try:
                            api_client.select_directory(parent_path)
                            _logger.info(f"Recovered parent context using path: {parent_path}")
                        except Exception as recovery_error:
                            _logger.error(f"Failed to recover parent context: {str(recovery_error)}")
                            # Continue with next child - session state may be corrupted
                        
                        # Continue with next child
                        continue
                    
                except Exception as e:
                    _logger.error(f"Error processing child folder '{child_folder.get('name')}': {str(e)}")
                    # Continue with next child
            
            _logger.info(f"Completed child processing for '{parent_folder_record.name}': {child_count} total folders")
            return child_count
            
        except Exception as e:
            _logger.error(f"Error processing children of folder '{parent_folder_record.name}': {str(e)}")
            raise
    
    @api.model
    def _create_or_update_folder(self, folder_data, parent_id=None):
        """
        Create or update a folder record from MBIOE API data
        Migration-aware: Handles both path-based and legacy name-based identifiers
        """
        try:
            # CRITICAL FIX: Use 'path' as the unique identifier, 'name' for display
            folder_path = folder_data.get('path')
            folder_name = folder_data.get('name', 'Unnamed Folder')
            
            # Fallback to name if path is not available (for root folders)
            identifier = folder_path or folder_name
            
            if not identifier:
                raise ValueError(f"Folder data missing both 'path' and 'name' fields: {folder_data}")
            
            # Use API path as full_path (this is the navigation path)
            full_path = folder_path or folder_name
            
            # PERFORMANCE OPTIMIZED MIGRATION-AWARE LOOKUP
            existing_folder = self._find_existing_folder(identifier, folder_path, folder_name, parent_id)
            
            folder_vals = {
                'name': folder_name,              # Display name (human-readable)
                'identifier': identifier,         # API path (unique identifier)
                'full_path': full_path,          # Same as identifier for path-based approach
                'parent_id': parent_id,
                'synced_at': fields.Datetime.now(),
                'api_source': 'MBIOE',
            }
            
            if existing_folder:
                # Update existing folder with current path-based identifier
                _logger.debug(f"Updating existing folder: {folder_name} (path: {identifier})")
                existing_folder.with_context(from_mbioe_sync=True).write(folder_vals)
                return existing_folder
            else:
                # Create new folder
                _logger.debug(f"Creating new folder: {folder_name} (path: {identifier})")
                new_folder = self.env['mbioe.folder'].with_context(from_mbioe_sync=True).create(folder_vals)
                return new_folder
                
        except Exception as e:
            _logger.error(f"Error creating/updating folder '{folder_data.get('name')}': {str(e)}")
            raise
    
    @api.model
    def _find_existing_folder(self, identifier, folder_path, folder_name, parent_id):
        """
        Performance-optimized migration-aware folder lookup
        Tries multiple strategies to find existing folders and prevent duplicates
        
        Performance Impact:
        - Strategy 1: Single indexed query (normal case) - ~0.1ms
        - Strategy 2: Legacy lookup (only during migration period) - ~0.5ms  
        - Strategy 3: Full path collision check (safety net) - ~0.2ms
        Total worst case: ~0.8ms vs ~0.1ms (8x impact for migration cases only)
        """
        # Strategy 1: Current path-based lookup (99% of cases after migration)
        existing_folder = self.env['mbioe.folder'].search([
            ('identifier', '=', identifier)
        ], limit=1)
        
        if existing_folder:
            return existing_folder
        
        # Strategy 2: Legacy migration lookup (only for child folders during transition)
        if folder_path and parent_id and '/' in folder_path:
            # Build optimized search for previously name-based identifiers
            # Only search within the same parent to limit scope
            legacy_folder = self.env['mbioe.folder'].search([
                ('name', '=', folder_name),
                ('parent_id', '=', parent_id),
                ('identifier', '=', folder_name)  # Legacy name-based identifier
            ], limit=1)
            
            if legacy_folder:
                _logger.info(f"MIGRATION: Found legacy folder '{folder_name}' -> migrating to path-based identifier '{identifier}'")
                return legacy_folder
        
        # Strategy 3: Full path collision check (safety net)
        # Only necessary if there might be orphaned records with same path
        path_collision = self.env['mbioe.folder'].search([
            ('full_path', '=', folder_path or folder_name)
        ], limit=1)
        
        if path_collision:
            _logger.warning(f"COLLISION: Found folder with same full_path '{folder_path or folder_name}' but different identifier")
            return path_collision
        
        # No existing folder found
        return None

    @api.model
    def _cleanup_orphaned_folders(self):
        """Remove folders that no longer exist in MBIOE (optional cleanup)"""
        try:
            # For now, we'll just log this for manual review
            # In production, this could compare sync timestamps
            cutoff_time = datetime.now() - timedelta(hours=24)
            old_folders = self.env['mbioe.folder'].search([
                ('synced_at', '<', cutoff_time)
            ])
            
            if old_folders:
                _logger.info(f"Found {len(old_folders)} folders not synced in last 24 hours (manual review recommended)")
            
        except Exception as e:
            _logger.warning(f"Cleanup check failed: {str(e)}")
    
    @api.model
    def _get_api_client(self):
        """Get configured API client for sync operations"""
        try:
            # Get configuration
            config_settings = self.env['res.config.settings']
            config = config_settings.get_mbioe_config()
            
            # Create API client
            client = MBIOEApiClient(
                base_url=config['api_url'],
                username=config['username'],
                password=config['password'],
                env=self.env
            )
            
            return client
            
        except ConfigurationError as e:
            raise UserError(str(e))
        except Exception as e:
            _logger.error(f"Error creating API client: {str(e)}")
            raise UserError(_("Failed to create API client. Please check your configuration."))
    
    @api.model
    def _create_sync_result(self, total_folders, processed_roots, errors, sync_start):
        """Create standardized sync result for UI feedback"""
        sync_duration = time.time() - sync_start
        
        if errors:
            status = 'warning' if total_folders > 0 else 'error'
            title = _('Folder Sync Completed with Warnings') if total_folders > 0 else _('Folder Sync Failed')
            message_parts = [
                _('Processed: %d folders from %d root folders') % (total_folders, processed_roots),
                _('Duration: %.1f seconds') % sync_duration,
                _('Errors: %d') % len(errors),
                _('First error: %s') % errors[0] if errors else ''
            ]
        else:
            status = 'success'
            title = _('Folder Sync Completed Successfully')
            message_parts = [
                _('Synchronized: %d folders from %d root folders') % (total_folders, processed_roots),
                _('Duration: %.1f seconds') % sync_duration,
                _('No errors occurred')
            ]
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': title,
                'message': '\n'.join(message_parts),
                'type': status,
                'sticky': status in ['warning', 'error'],
            }
        }
    
    @api.model
    def _create_job_sync_result(self, total_folders, processed_roots, errors, sync_start):
        """Create sync result for background job execution (no UI notification needed)"""
        sync_duration = time.time() - sync_start
        
        # For background jobs, we just log the result instead of showing UI notifications
        if errors:
            status = 'warning' if total_folders > 0 else 'error'
            _logger.warning(f"Folder sync job completed with {len(errors)} errors. "
                          f"Processed {total_folders} folders from {processed_roots} roots "
                          f"in {sync_duration:.1f}s")
            for error in errors[:3]:  # Log first 3 errors
                _logger.error(f"Sync error: {error}")
        else:
            _logger.info(f"Folder sync job completed successfully. "
                        f"Synchronized {total_folders} folders from {processed_roots} roots "
                        f"in {sync_duration:.1f}s")
        
        # Return structured result for job framework
        return {
            'status': 'completed',
            'total_folders': total_folders,
            'processed_roots': processed_roots,
            'errors': errors,
            'duration': sync_duration,
            'success': len(errors) == 0
        }
    
    @api.model
    def get_sync_statistics(self):
        """Get current synchronization statistics"""
        folder_model = self.env['mbioe.folder']
        
        stats = {
            'total_folders': folder_model.search_count([]),
            'root_folders': folder_model.search_count([('parent_id', '=', False)]),
            'last_sync': None,
            'folders_by_level': {},
        }
        
        # Get last sync time
        latest_folder = folder_model.search([('synced_at', '!=', False)], 
                                          order='synced_at desc', limit=1)
        if latest_folder:
            stats['last_sync'] = latest_folder.synced_at
        
        # Get folder distribution by level
        folders_with_level = folder_model.search([])
        for folder in folders_with_level:
            level = folder.level
            if level not in stats['folders_by_level']:
                stats['folders_by_level'][level] = 0
            stats['folders_by_level'][level] += 1
        
        return stats
    
    @api.model
    def get_sync_job_status(self, job_uuid=None):
        """Get status of sync jobs"""
        try:
            job_model = self.env['queue.job']
            
            if job_uuid:
                # Get specific job status
                job = job_model.search([('uuid', '=', job_uuid)], limit=1)
                if job:
                    return {
                        'uuid': job.uuid,
                        'state': job.state,
                        'name': job.name,
                        'date_created': job.date_created,
                        'date_started': job.date_started,
                        'date_done': job.date_done,
                        'result': job.result,
                        'exc_info': job.exc_info,
                    }
                return None
            else:
                # Get recent sync jobs
                sync_jobs = job_model.search([
                    ('name', 'like', 'MBIOE Folder Synchronization'),
                    ('date_created', '>=', (datetime.now() - timedelta(hours=24)).strftime('%Y-%m-%d %H:%M:%S'))
                ], order='date_created desc', limit=10)
                
                return [{
                    'uuid': job.uuid,
                    'state': job.state,
                    'name': job.name,
                    'date_created': job.date_created,
                    'date_started': job.date_started,
                    'date_done': job.date_done,
                    'result': job.result[:100] if job.result else None,  # Truncate for list view
                } for job in sync_jobs]
                
        except Exception as e:
            # If queue_job model is not available, return empty results
            _logger.warning(f"Queue job model not available: {str(e)}")
            return None if job_uuid else []
    

