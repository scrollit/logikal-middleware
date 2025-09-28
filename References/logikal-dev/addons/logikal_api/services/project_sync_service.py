# -*- coding: utf-8 -*-

import logging
import time
from datetime import datetime, timedelta
from odoo import models, api, fields, _
from odoo.exceptions import UserError

# Import job decorator (with fallback)
try:
    from odoo.addons.queue_job.job import job
    QUEUE_JOB_AVAILABLE = True
except ImportError:
    # Fallback decorator if queue_job is not available
    def job(*args, **kwargs):
        def decorator(func):
            return func
        return decorator
    QUEUE_JOB_AVAILABLE = False

_logger = logging.getLogger(__name__)


class MBIOEProjectSyncService(models.AbstractModel):
    _name = 'mbioe.project.sync.service'
    _description = 'MBIOE Project Synchronization Service'

    @api.model
    def sync_projects_for_all_folders(self):
        """
        Initiates a staged sync using the new master sync orchestration.
        """
        # Create master sync record
        master_sync = self.env['mbioe.master.sync'].create({
            'name': f"Project Sync {fields.Datetime.now().strftime('%Y-%m-%d %H:%M')}",
            'sync_type': 'projects',
            'state': 'draft'
        })
        
        # Start the master sync
        return master_sync.action_start_sync()
    
    def _get_folder_tree(self, root_folder):
        """Get all folders in a tree starting from root folder, excluding excluded folders
        
        Args:
            root_folder: mbioe.folder record
            
        Returns:
            list: All folders in tree (including root) that are not excluded from sync
        """
        folders = []
        
        def add_children(folder):
            # Skip if folder is excluded from sync
            if folder.exclude_from_sync:
                _logger.info(f"Skipping excluded folder: {folder.name} ({folder.full_path})")
                return
            
            folders.append(folder)
            for child in folder.child_ids:
                add_children(child)
        
        add_children(root_folder)
        return folders
    
    def _sync_projects_for_folder(self, client, folder):
        """Sync projects for a specific folder
        
        Args:
            client: Authenticated MBIOE API client
            folder: mbioe.folder record
            
        Returns:
            dict: Sync results for this folder
        """
        processed = 0
        created = 0
        updated = 0
        errors = []
        
        try:
            # Fetch projects from API
            api_projects = client.get_projects()
            _logger.info(f"Retrieved {len(api_projects)} projects from API for folder {folder.name}")
            
            for project_data in api_projects:
                try:
                    result = self._process_project_data(project_data, folder)
                    processed += 1
                    
                    if result == 'created':
                        created += 1
                    elif result == 'updated':
                        updated += 1
                        
                except Exception as e:
                    error_msg = f"Error processing project {project_data.get('name', 'Unknown')}: {str(e)}"
                    _logger.error(error_msg)
                    errors.append(error_msg)
                    continue
            
        except Exception as e:
            error_msg = f"Error fetching projects for folder {folder.name}: {str(e)}"
            _logger.error(error_msg)
            errors.append(error_msg)
        
        return {
            'processed': processed,
            'created': created,
            'updated': updated,
            'errors': errors
        }
    
    def _process_project_data(self, project_data, folder):
        """Process a single project from API data
        
        Args:
            project_data (dict): Project data from MBIOE API
            folder: mbioe.folder record
            
        Returns:
            str: 'created', 'updated', or 'skipped'
        """
        # Extract project identifier
        project_identifier = project_data.get('id')
        if not project_identifier:
            raise ValueError("Project data missing 'id' field")
        
        # Check if project already exists
        existing_project = self.env['mbioe.project'].search([
            ('identifier', '=', project_identifier)
        ], limit=1)
        
        # Convert API timestamps
        api_created_date = self._convert_api_timestamp(project_data.get('createdDate'))
        api_changed_date = self._convert_api_timestamp(project_data.get('changedDate'))
        
        # Prepare project values with sync context
        project_values = {
            'name': project_data.get('name', 'Unnamed Project'),
            'identifier': project_identifier,
            'folder_id': folder.id,
            'job_number': project_data.get('jobNumber'),
            'offer_number': project_data.get('offerNumber'),
            'person_in_charge': project_data.get('personInCharge'),
            'estimated': project_data.get('estimated', False),
            'api_created_date': api_created_date,
            'api_changed_date': api_changed_date,
            'last_api_sync': fields.Datetime.now(),
            'synced_at': fields.Datetime.now(),
            'imported': True,
            'api_source': 'MBIOE',
        }
        
        if existing_project:
            # Check if update is needed (change detection)
            if self._should_update_project(existing_project, api_changed_date):
                # Add sync status for updates
                project_values['sync_status'] = 'updated'
                existing_project.with_context(from_mbioe_sync=True).write(project_values)
                _logger.debug(f"Updated project: {project_data.get('name')} [{project_identifier[:8]}]")
                return 'updated'
            else:
                # Just update sync timestamp and mark as unchanged
                existing_project.with_context(from_mbioe_sync=True).write({
                    'last_api_sync': fields.Datetime.now(),
                    'synced_at': fields.Datetime.now(),
                    'sync_status': 'unchanged',
                })
                _logger.debug(f"Skipped unchanged project: {project_data.get('name')} [{project_identifier[:8]}]")
                return 'skipped'
        else:
            # Create new project with sync context
            project_values['sync_status'] = 'new'
            new_project = self.env['mbioe.project'].with_context(from_mbioe_sync=True).create(project_values)
            _logger.debug(f"Created project: {project_data.get('name')} [{project_identifier[:8]}]")
            return 'created'
    
    def _should_update_project(self, existing_project, api_changed_date):
        """Determine if project should be updated based on change detection
        
        Args:
            existing_project: mbioe.project record
            api_changed_date: datetime from API
            
        Returns:
            bool: True if project should be updated
        """
        if not api_changed_date:
            return False  # No change date from API, skip update
        
        if not existing_project.last_api_sync:
            return True  # Never synced, definitely update
        
        # Update if API changed date is newer than last sync
        return api_changed_date > existing_project.last_api_sync
    
    def _convert_api_timestamp(self, timestamp):
        """Convert MBIOE API timestamp to Odoo datetime with robust validation
        
        Args:
            timestamp: Unix timestamp from API (seconds or milliseconds)
            
        Returns:
            datetime or None
        """
        if not timestamp:
            return None
        
        try:
            # Convert to float if it's a string
            if isinstance(timestamp, str):
                timestamp = float(timestamp)
            
            # Check for obviously invalid values (negative, zero, or extremely large)
            if timestamp <= 0:
                _logger.warning(f"Invalid timestamp {timestamp}: timestamp must be positive")
                return None
            
            # Handle both seconds and milliseconds timestamps
            original_timestamp = timestamp
            if timestamp > 10**10:  # Milliseconds
                timestamp = timestamp / 1000
            
            # Validate reasonable timestamp range
            # Unix epoch (1970-01-01) = 0
            # Year 2100 (Jan 1, 2100) = 4102444800
            # Year 2200 (Jan 1, 2200) = 7258118400 (extended upper bound for safety)
            MIN_TIMESTAMP = 0  # 1970-01-01
            MAX_TIMESTAMP = 7258118400  # 2200-01-01 (generous upper bound)
            
            if timestamp < MIN_TIMESTAMP:
                _logger.warning(f"Timestamp {original_timestamp} ({timestamp} seconds) before Unix epoch (1970), skipping")
                return None
            
            if timestamp > MAX_TIMESTAMP:
                _logger.warning(f"Timestamp {original_timestamp} ({timestamp} seconds) beyond reasonable range (year {datetime.fromtimestamp(MAX_TIMESTAMP).year}), skipping")
                return None
            
            # Additional validation: try to create datetime and check year
            result_dt = datetime.fromtimestamp(timestamp)
            
            # Final sanity check on the resulting year
            if result_dt.year < 1970 or result_dt.year > 2200:
                _logger.warning(f"Timestamp {original_timestamp} results in invalid year {result_dt.year}, skipping")
                return None
            
            return result_dt
            
        except (ValueError, OSError, OverflowError) as e:
            _logger.warning(f"Invalid timestamp {timestamp}: {str(e)}")
            return None
        except Exception as e:
            _logger.error(f"Unexpected error converting timestamp {timestamp}: {str(e)}")
            return None
    
    @api.model
    @job(default_channel='root.mbioe')
    def sync_projects_for_folder_tree(self, root_folder_id):
        """
        Sync projects for a specific folder tree (background job method).
        Respects exclude_from_sync settings and processes folder tree efficiently.
        """
        _logger.info(f"Starting project sync for folder tree (root folder ID: {root_folder_id})")
        start_time = time.time()
        
        processed = 0
        created = 0
        updated = 0
        errors = []
        
        try:
            # Get the root folder
            root_folder = self.env['mbioe.folder'].browse(root_folder_id)
            if not root_folder.exists():
                error_msg = f"Root folder with ID {root_folder_id} not found"
                _logger.error(error_msg)
                return {'status': 'failed', 'error': error_msg}
            
            # Check if root folder is excluded from sync
            if root_folder.exclude_from_sync:
                _logger.info(f"Skipping excluded root folder: {root_folder.name}")
                return {
                    'status': 'skipped',
                    'message': f'Root folder "{root_folder.name}" is excluded from sync',
                    'processed': 0,
                    'created': 0,
                    'updated': 0,
                    'errors': []
                }
            
            # Get API client
            mbioe_service = self.env['mbioe.service']
            client = mbioe_service._get_api_client()
            
            # Authenticate and navigate to root folder
            token = client.authenticate()
            client.select_directory(root_folder.identifier)
            
            # Get all folders in the tree that are not excluded
            folders_to_process = self._get_folder_tree(root_folder)
            _logger.info(f"Processing {len(folders_to_process)} folders in tree (excluding excluded folders)")
            
            # Process projects for each folder in the tree
            for folder in folders_to_process:
                try:
                    # Navigate to the folder
                    client.select_directory(folder.identifier)
                    
                    # Sync projects for this folder
                    folder_result = self._sync_projects_for_folder(client, folder)
                    processed += folder_result['processed']
                    created += folder_result['created']
                    updated += folder_result['updated']
                    errors.extend(folder_result['errors'])
                    
                    _logger.debug(f"Processed folder '{folder.name}': {folder_result['processed']} projects")
                    
                except Exception as e:
                    error_msg = f"Error processing folder '{folder.name}': {str(e)}"
                    _logger.error(error_msg)
                    errors.append(error_msg)
                    continue
            
            # Cleanup
            client.logout()
            
            duration = time.time() - start_time
            _logger.info(f"Completed project sync for folder tree '{root_folder.name}': "
                        f"{processed} projects processed, {created} created, {updated} updated, "
                        f"{len(errors)} errors in {duration:.2f}s")
            
            return {
                'status': 'completed' if len(errors) == 0 else 'completed_with_errors',
                'processed': processed,
                'created': created,
                'updated': updated,
                'errors': errors,
                'duration': duration
            }
            
        except Exception as e:
            # Ensure session cleanup
            try:
                if 'client' in locals() and client.session_token:
                    client.logout()
            except:
                pass
            
            duration = time.time() - start_time
            error_msg = f"Project sync failed for folder tree {root_folder_id}: {str(e)}"
            _logger.error(error_msg, exc_info=True)
            
            return {
                'status': 'failed',
                'error': error_msg,
                'duration': duration
            }
    
    def get_project_sync_statistics(self):
        """Get project synchronization statistics
        
        Returns:
            dict: Statistics for UI display
        """
        project_model = self.env['mbioe.project']
        
        # Get basic counts
        total_projects = project_model.search_count([])
        estimated_projects = project_model.search_count([('estimated', '=', True)])
        
        # Get recent sync info
        recent_sync = project_model.search([
            ('last_api_sync', '!=', False)
        ], order='last_api_sync desc', limit=1)
        
        last_sync_time = recent_sync.last_api_sync if recent_sync else None
        
        # Count projects by folder
        folder_stats = project_model.read_group(
            [], ['folder_id'], ['folder_id']
        )
        
        return {
            'total_projects': total_projects,
            'estimated_projects': estimated_projects,
            'last_sync': last_sync_time,
            'folders_with_projects': len(folder_stats),
        }
