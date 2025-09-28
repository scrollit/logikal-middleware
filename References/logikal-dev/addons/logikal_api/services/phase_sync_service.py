# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError
import logging
import time
from datetime import datetime, timedelta

_logger = logging.getLogger(__name__)

class MBIOEPhaseSyncService(models.AbstractModel):
    _name = 'mbioe.phase.sync.service'
    _description = 'MBIOE Phase Synchronization Service'

    @api.model
    def sync_phases_for_all_projects(self):
        """
        Initiates a staged sync using the new master sync orchestration.
        """
        # Create master sync record
        master_sync = self.env['mbioe.master.sync'].create({
            'name': f"Phase Sync {fields.Datetime.now().strftime('%Y-%m-%d %H:%M')}",
            'sync_type': 'phases',
            'state': 'draft'
        })
        
        # Start the master sync
        return master_sync.action_start_sync()

    @api.model
    def sync_single_project_phases(self, project_id):
        """
        Synchronizes phases for a single project.
        Uses the exact same navigation pattern as working folder/project sync.
        """
        project = self.env['mbioe.project'].browse(project_id)
        if not project.exists():
            raise UserError(_("Project not found."))

        _logger.info(f"Starting phase sync for project: {project.name} ({project.identifier})")
        
        start_time = time.time()
        errors = []
        total_phases = 0

        try:
            # Use the working navigation pattern from folder/project sync
            phases_count, _unused, project_errors = self._sync_project_using_working_pattern(project)
            total_phases += phases_count
            errors.extend(project_errors)
        except Exception as e:
            errors.append(f"Failed to sync project {project.name}: {str(e)}")
            _logger.error(f"Failed to sync project {project.name}: {str(e)}")

        duration = time.time() - start_time
        if not errors:
            message = _(f"Phase sync for project '{project.name}' completed: {total_phases} phases in {duration:.2f}s.")
            notification_type = 'success'
        else:
            message = _(f"Phase sync for project '{project.name}' completed with errors: {total_phases} phases in {duration:.2f}s. Errors: {'; '.join(errors)}")
            notification_type = 'warning'

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Phase Sync Complete'),
                'message': message,
                'type': notification_type,
                'sticky': True if errors else False,
            }
        }

    @api.model
    def sync_elevations_only_for_all_projects(self):
        """
        Initiates a staged sync using the new master sync orchestration.
        """
        # Create master sync record
        master_sync = self.env['mbioe.master.sync'].create({
            'name': f"Elevation Sync {fields.Datetime.now().strftime('%Y-%m-%d %H:%M')}",
            'sync_type': 'elevations',
            'state': 'draft'
        })
        
        # Start the master sync
        return master_sync.action_start_sync()

    @api.model
    def sync_phases_only_for_all_projects(self):
        """
        Initiates a staged sync using the new master sync orchestration.
        """
        master_sync = self.env['mbioe.master.sync'].create({
            'name': f"Phase Sync (Phases Only) {fields.Datetime.now().strftime('%Y-%m-%d %H:%M')}",
            'sync_type': 'phases',
            'state': 'draft'
        })
        
        # Start the master sync
        return master_sync.action_start_sync()

    def _sync_project_using_working_pattern(self, project):
        """
        Sync project phases using the EXACT SAME navigation pattern as working folder/project sync.
        
        This method follows the proven working approach:
        1. Navigate to root folder
        2. Navigate through folder hierarchy to project folder
        3. Select project within that folder context
        4. Access project data through MBIOE API (not file system)
        
        Args:
            project: mbioe.project record
            
        Returns:
            tuple: (phases_count, 0, errors_list) - elevation count always 0 for now
        """
        phases_count = 0
        errors = []
        
        try:
            if not project.folder_id:
                errors.append(f"Project {project.name} has no folder association")
                return 0, 0, errors
            
            # Get the root folder for this project
            root_folder = self._get_root_folder(project.folder_id)
            if not root_folder:
                errors.append(f"Could not determine root folder for project {project.name}")
                return 0, 0, errors
            
            _logger.info(f"Processing project {project.name} in root folder: {root_folder.name}")
            
            # Use the working navigation pattern from folder/project sync
            api_client = None
            try:
                # Step 1: Create API client and authenticate (same as working sync)
                api_client = self._get_api_client()
                
                # Step 2: Navigate to root folder (same as working sync)
                navigation_success = self._navigate_to_root_folder(api_client, root_folder)
                if not navigation_success:
                    raise Exception(f"Failed to navigate to root folder: {root_folder.name}")
                
                # Step 3: Navigate through folder hierarchy to project folder (same as working sync)
                project_navigation = self._navigate_to_project_folder(api_client, project)
                if not project_navigation:
                    raise Exception(f"Failed to navigate to project folder for {project.name}")
                
                # Step 4: Select project within folder context (same as working sync)
                project_selection = self._select_project_in_context(api_client, project)
                if not project_selection:
                    raise Exception(f"Failed to select project {project.name} in folder context")
                
                # Step 5: Access project data through MBIOE API (not file system)
                phases_count, _unused, errors = self._sync_project_data_through_api(
                    api_client, project
                )
                
                _logger.info(f"Successfully synced project {project.name}: {phases_count} phases")
                
            finally:
                # Always terminate the session (same as working sync)
                if api_client and api_client.session_token:
                    try:
                        api_client.logout()
                        _logger.info(f"Terminated MBIOE session for project {project.name}")
                    except Exception as logout_error:
                        _logger.warning(f"Failed to logout for project {project.name}: {logout_error}")

        except Exception as e:
            error_msg = f"Error syncing project {project.name} ({project.identifier}): {str(e)}"
            errors.append(error_msg)
            project.write({'sync_status': 'error'})
            _logger.error(error_msg)
            
        return phases_count, 0, errors

    def _get_root_folder(self, folder):
        """
        Get the root folder (level 0) for a given folder.
        Same logic as working folder sync.
        """
        current = folder
        while current.parent_id:
            current = current.parent_id
            # Safety check to prevent infinite loops
            if current.level == 0:
                break
        return current

    def _navigate_to_root_folder(self, api_client, root_folder):
        """
        Navigate to root folder using the working pattern from folder sync.
        """
        try:
            _logger.info(f"Navigating to root folder: {root_folder.name} (ID: {root_folder.identifier})")
            
            # Use the exact same method as working folder sync
            api_client.select_directory(root_folder.identifier)
            
            _logger.info(f"Successfully navigated to root folder: {root_folder.name}")
            return True

        except Exception as e:
            _logger.error(f"Failed to navigate to root folder {root_folder.name}: {str(e)}")
            return False

    def _navigate_to_project_folder(self, api_client, project):
        """
        Navigate through folder hierarchy to project folder using working pattern.
        """
        try:
            if not project.folder_id:
                _logger.error(f"Project {project.name} has no folder association")
                return False
            
            # Get the relative path from root to project folder
            relative_path = self._get_relative_path_from_root(project.folder_id)
            
            # Check if path calculation failed (None) vs empty path (project in root folder)
            if relative_path is None:
                _logger.error(f"Could not determine relative path for project {project.name}")
                return False
            
            # Empty path means project is directly in root folder - no navigation needed
            if not relative_path:
                _logger.info(f"Project {project.name} is in root folder {project.folder_id.name} - no navigation needed")
                return True
            
            _logger.info(f"Navigating to project folder: {project.folder_id.name} (relative path: {len(relative_path)} levels)")
            
            # Navigate through the relative path using the working pattern
            for folder in relative_path:
                try:
                    # Use the exact same method as working folder sync
                    api_client.select_directory(folder.identifier)
                    _logger.debug(f"Selected folder: {folder.name}")
                except Exception as e:
                    _logger.error(f"Failed to select folder {folder.name}: {str(e)}")
                    return False
            
            _logger.info(f"Successfully navigated to project folder: {project.folder_id.name}")
            return True

        except Exception as e:
            _logger.error(f"Failed to navigate to project folder for {project.name}: {str(e)}")
            return False

    def _get_relative_path_from_root(self, target_folder):
        """
        Get the relative path from root to target folder.
        Returns:
        - Empty list [] if target_folder is a root folder (no navigation needed)
        - List of folders if target_folder is nested (navigation path)
        - None if there's an error (folder doesn't exist, infinite loop, etc.)
        """
        try:
            if not target_folder or not target_folder.exists():
                _logger.error(f"Target folder does not exist: {target_folder}")
                return None
                
            path = []
            current = target_folder
            
            # Build path from target to root (reverse order)
            while current.parent_id:
                path.append(current)
                current = current.parent_id
                
                # Safety check to prevent infinite loops
                if len(path) > 20:
                    _logger.error(f"Folder hierarchy too deep (>20 levels) for folder {target_folder.name}")
                    return None
            
            # Return root-to-target order (excluding root)
            path.reverse()
            return path
            
        except Exception as e:
            _logger.error(f"Error calculating relative path for folder {target_folder}: {str(e)}")
            return None

    def _select_project_in_context(self, api_client, project):
        """
        Select project within the established folder context.
        This is the critical step that was missing - we must be in the correct folder context.
        """
        try:
            _logger.info(f"Selecting project {project.name} in folder context")
            
            # Use the exact same method as working project sync
            api_client.select_project(project.identifier)
            
            _logger.info(f"Successfully selected project {project.name} in folder context")
            return True

        except Exception as e:
            _logger.error(f"Failed to select project {project.name} in folder context: {str(e)}")
            return False

    def _sync_project_data_through_api(self, api_client, project):
        """
        Sync project data through MBIOE API (not file system).
        This method only calls MBIOE API endpoints, never file system paths.
        """
        phases_count = 0
        errors = []

        try:
            # Get phases through MBIOE API (not file system)
            api_phases = api_client.get_phases()
            if not api_phases:
                _logger.info(f"No phases found for project {project.name} ({project.identifier})")
                return 0, 0, []

            # Mark existing phases as 'to_remove'
            existing_phases = self.env['mbioe.project.phase'].search([('project_id', '=', project.id)])
            existing_phases.write({'sync_status': 'to_remove'})

            # Process each phase through MBIOE API
            for api_phase_data in api_phases:
                phase_identifier = api_phase_data.get('id')
                if not phase_identifier:
                    errors.append(f"Phase data missing identifier for project {project.name}")
                    continue

                phase = self.env['mbioe.project.phase'].search([
                    ('project_id', '=', project.id),
                    ('identifier', '=', phase_identifier)
                ], limit=1)

                if phase:
                    phase.update_from_api_data(api_phase_data)
                    _logger.debug(f"Updated phase: {phase.name} ({phase.identifier})")
                else:
                    phase = self.env['mbioe.project.phase'].create_from_api_data(api_phase_data, project.id)
                    _logger.debug(f"Created new phase: {phase.name} ({phase.identifier})")
                
                phases_count += 1

            # Remove phases not found in the latest API sync
            self.env['mbioe.project.phase'].search([
                ('project_id', '=', project.id),
                ('sync_status', '=', 'to_remove')
            ]).unlink()

            project.write({'last_api_sync': fields.Datetime.now(), 'sync_status': 'unchanged'})

        except Exception as e:
            error_msg = f"Error syncing project data through API for {project.name}: {str(e)}"
            errors.append(error_msg)
            project.write({'sync_status': 'error'})
            _logger.error(error_msg)

        return phases_count, 0, errors

    def _get_api_client(self):
        """Get configured API client - same as working sync services"""
        try:
            config_settings = self.env['res.config.settings']
            config = config_settings.get_mbioe_config()
            
            from .mbioe_api_client import MBIOEApiClient
            api_client = MBIOEApiClient(
                base_url=config['api_url'],
                username=config['username'],
                password=config['password'],
                env=self.env
            )
            
            # Authenticate
            api_client.authenticate()
            
            return api_client
        except Exception as e:
            from .exceptions import ConfigurationError
            raise ConfigurationError(f"Failed to create API client: {str(e)}")

    # Legacy methods for backward compatibility - these will be deprecated
    def _sync_phases_background(self, project_ids):
        """
        Background job to synchronize phases for a list of projects.
        DEPRECATED: Use the new MBIOE-compliant methods instead.
        """
        _logger.warning("Using deprecated _sync_phases_background method. Use new MBIOE-compliant methods.")
        
        total_phases = 0
        all_errors = []
        
        for project_id in project_ids:
            try:
                project = self.env['mbioe.project'].browse(project_id)
                if not project.exists():
                    continue
                
                phases, _unused, errors = self._sync_project_using_working_pattern(project)
                total_phases += phases
                all_errors.extend(errors)
                
            except Exception as e:
                error_msg = f"Failed to process project {project_id}: {str(e)}"
                all_errors.append(error_msg)
                _logger.error(error_msg)
        
        return total_phases, 0, all_errors