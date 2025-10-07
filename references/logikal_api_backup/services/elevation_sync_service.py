# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError
import time
import logging

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


class MbioeElevationSyncService(models.Model):
    _name = 'mbioe.elevation.sync.service'
    _description = 'MBIOE Elevation Synchronization Service'

    @api.model
    @job(default_channel='mbioe.sync.elevations')
    def sync_elevations_for_project(self, project_id):
        """
        Main entry point - sync all elevations for a specific project.
        Returns user-friendly response for UI display.
        """
        project = self.env['mbioe.project'].browse(project_id)
        if not project.exists():
            raise UserError(_("Project not found."))

        _logger.info(f"Starting elevation sync for project: {project.name} ({project.identifier})")
        
        start_time = time.time()
        errors = []
        total_elevations = 0
        total_thumbnails = 0

        try:
            # Use the working navigation pattern from phase sync
            elevations_count, thumbnails_count, sync_errors = self._sync_elevations_for_single_project(project)
            total_elevations += elevations_count
            total_thumbnails += thumbnails_count
            errors.extend(sync_errors)
        except Exception as e:
            errors.append(f"Failed to sync elevations for project {project.name}: {str(e)}")
            _logger.error(f"Failed to sync elevations for project {project.name}: {str(e)}")

        duration = time.time() - start_time
        if not errors:
            message = _(f"Elevation sync for project '{project.name}' completed: {total_elevations} elevations and {total_thumbnails} thumbnails processed in {duration:.2f}s.")
            notification_type = 'success'
        else:
            message = _(f"Elevation sync for project '{project.name}' completed with errors: {total_elevations} elevations and {total_thumbnails} thumbnails processed, {len(errors)} errors in {duration:.2f}s.")
            notification_type = 'warning'

        _logger.info(message)
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Elevation Sync'),
                'message': message,
                'type': notification_type,
                'sticky': False,
            }
        }

    def _sync_elevations_for_single_project(self, project):
        """
        Sync elevations for one project through all its phases.
        Uses the same navigation pattern as phase sync service.
        
        Returns:
            tuple: (elevations_count, thumbnails_count, errors)
        """
        elevations_count = 0
        thumbnails_count = 0
        errors = []
        
        try:
            if not project.folder_id:
                errors.append(f"Project {project.name} has no folder association")
                return 0, 0, errors
            
            # Get phases for this project
            phases = self.env['mbioe.project.phase'].search([
                ('project_id', '=', project.id)
            ])
            
            if not phases:
                _logger.info(f"No phases found for project {project.name}")
                return 0, 0, []
            
            _logger.info(f"Processing elevations for {len(phases)} phases in project {project.name}")
            
            # Use the working navigation pattern from phase sync service
            api_client = None
            try:
                # Step 1: Create API client and authenticate 
                api_client = self._get_api_client()
                
                # Step 2: Navigate to project context (reuse phase sync logic)
                navigation_success = self._navigate_to_project_context(api_client, project)
                if not navigation_success:
                    raise Exception(f"Failed to navigate to project context for {project.name}")
                
                # Step 3: Process elevations for each phase
                for phase in phases:
                    try:
                        phase_elevations_count, phase_thumbnails_count, phase_errors = self._sync_elevations_for_phase(
                            api_client, project, phase
                        )
                        elevations_count += phase_elevations_count
                        thumbnails_count += phase_thumbnails_count
                        errors.extend(phase_errors)
                        
                        _logger.debug(f"Processed {phase_elevations_count} elevations and {phase_thumbnails_count} thumbnails for phase {phase.name}")
                        
                    except Exception as e:
                        error_msg = f"Failed to sync elevations for phase {phase.name}: {str(e)}"
                        errors.append(error_msg)
                        _logger.error(error_msg)
                        continue
                
                _logger.info(f"Successfully synced elevations for project {project.name}: {elevations_count} total elevations, {thumbnails_count} total thumbnails")
                
            finally:
                # Always terminate the session
                if api_client and api_client.session_token:
                    try:
                        api_client.logout()
                        _logger.info(f"Terminated MBIOE session for elevation sync of {project.name}")
                    except Exception as logout_error:
                        _logger.warning(f"Failed to logout for project {project.name}: {logout_error}")

        except Exception as e:
            error_msg = f"Error syncing elevations for project {project.name} ({project.identifier}): {str(e)}"
            errors.append(error_msg)
            project.write({'sync_status': 'error'})
            _logger.error(error_msg)
            
        return elevations_count, thumbnails_count, errors

    def _navigate_to_project_context(self, api_client, project):
        """
        Navigate to project context using phase sync service navigation logic.
        Reuses the proven navigation pattern.
        """
        try:
            # Get the phase sync service to reuse navigation logic
            phase_sync_service = self.env['mbioe.phase.sync.service']
            
            # Get the root folder for this project
            root_folder = phase_sync_service._get_root_folder(project.folder_id)
            if not root_folder:
                _logger.error(f"Could not determine root folder for project {project.name}")
                return False
                
            # Step 1: Navigate to root folder
            navigation_success = phase_sync_service._navigate_to_root_folder(api_client, root_folder)
            if not navigation_success:
                _logger.error(f"Failed to navigate to root folder: {root_folder.name}")
                return False
            
            # Step 2: Navigate through folder hierarchy to project folder
            project_navigation = phase_sync_service._navigate_to_project_folder(api_client, project)
            if not project_navigation:
                _logger.error(f"Failed to navigate to project folder for {project.name}")
                return False
            
            # Step 3: Select project within folder context
            project_selection = phase_sync_service._select_project_in_context(api_client, project)
            if not project_selection:
                _logger.error(f"Failed to select project {project.name} in folder context")
                return False
                
            _logger.info(f"Successfully navigated to project context for {project.name}")
            return True
            
        except Exception as e:
            _logger.error(f"Failed to navigate to project context for {project.name}: {str(e)}")
            return False

    def _sync_elevations_for_phase(self, api_client, project, phase):
        """
        Sync elevations for a specific phase.
        
        Returns:
            tuple: (elevations_count, thumbnails_count, errors)
        """
        elevations_count = 0
        thumbnails_count = 0
        errors = []
        
        try:
            _logger.info(f"Syncing elevations for phase: {phase.name} ({phase.identifier})")
            
            # Select the specific phase
            success = api_client.select_phase(phase.identifier)
            if not success:
                error_msg = f"Failed to select phase {phase.name}"
                errors.append(error_msg)
                return 0, 0, errors
            
            # Get elevations for this phase
            api_elevations = api_client.get_elevations()
            if not api_elevations:
                _logger.info(f"No elevations found for phase {phase.name}")
                return 0, 0, []
            
            # Process elevation data
            processed_count = self._process_elevation_data(api_elevations, project, phase)
            elevations_count += processed_count
            
            # Fetch thumbnails for all elevations in this phase
            thumbnail_count, thumbnail_errors = self._fetch_thumbnails_for_phase(
                api_client, project, phase, api_elevations
            )
            thumbnails_count += thumbnail_count
            errors.extend(thumbnail_errors)
            
            _logger.info(f"Successfully processed {processed_count} elevations and {thumbnail_count} thumbnails for phase {phase.name}")
            
        except Exception as e:
            error_msg = f"Error syncing elevations for phase {phase.name}: {str(e)}"
            errors.append(error_msg)
            _logger.error(error_msg)
            
        return elevations_count, thumbnails_count, errors

    def _process_elevation_data(self, api_elevations, project, phase):
        """
        Process and store elevation data from API using existing model methods.
        """
        if not api_elevations:
            return 0
        
        _logger.info(f"Processing {len(api_elevations)} elevations for phase {phase.name}")
        
        # Mark existing elevations for this phase as 'to_remove'
        existing_elevations = self.env['mbioe.project.elevation'].search([
            ('project_id', '=', project.id),
            ('phase_id', '=', phase.id)
        ])
        existing_elevations.write({'sync_status': 'to_remove'})
        
        processed_count = 0
        for api_elevation in api_elevations:
            try:
                elevation_id = api_elevation.get('id')
                if not elevation_id:
                    _logger.warning(f"Elevation data missing identifier for phase {phase.name}")
                    continue
                
                # Check if elevation already exists
                existing_elevation = self.env['mbioe.project.elevation'].search([
                    ('identifier', '=', elevation_id),
                    ('project_id', '=', project.id),
                    ('phase_id', '=', phase.id)
                ], limit=1)
                
                if existing_elevation:
                    # Update existing elevation
                    existing_elevation.update_from_api_data(api_elevation)
                    _logger.debug(f"Updated elevation: {existing_elevation.name}")
                else:
                    # Create new elevation
                    new_elevation = self.env['mbioe.project.elevation'].create_from_api_data(
                        api_elevation, project.id, phase.id
                    )
                    _logger.debug(f"Created elevation: {new_elevation.name}")
                
                processed_count += 1
                
            except Exception as e:
                _logger.error(f"Failed to process elevation {elevation_id}: {str(e)}")
                continue
        
        # Remove elevations that were not found in the API response
        elevations_to_remove = self.env['mbioe.project.elevation'].search([
            ('project_id', '=', project.id),
            ('phase_id', '=', phase.id),
            ('sync_status', '=', 'to_remove')
        ])
        
        if elevations_to_remove:
            _logger.info(f"Removing {len(elevations_to_remove)} elevations no longer in API for phase {phase.name}")
            elevations_to_remove.unlink()
        
        return processed_count

    def _fetch_thumbnails_for_phase(self, api_client, project, phase, api_elevations):
        """
        Fetch thumbnails for all elevations in the current phase.
        Must be called while in the correct phase context.
        
        Args:
            api_client: Authenticated API client in correct phase context
            project: Project record
            phase: Phase record
            api_elevations: List of elevation data from API
            
        Returns:
            tuple: (thumbnail_count, thumbnail_errors)
        """
        thumbnail_count = 0
        thumbnail_errors = []
        
        _logger.info(f"Fetching thumbnails for {len(api_elevations)} elevations in phase {phase.name}")
        
        for api_elevation in api_elevations:
            try:
                elevation_id = api_elevation.get('id')
                if not elevation_id:
                    continue
                
                # Fetch thumbnail with specified parameters (300x300, PNG, Interior, with dimensions, without description)
                thumbnail_data = api_client.get_elevation_thumbnail(
                    elevation_id=elevation_id,
                    width=300,
                    height=300,
                    format="PNG",
                    view="Interior", 
                    withdimensions="true",
                    withdescription="false"
                )
                
                # Update elevation record with thumbnail
                success = self._update_elevation_thumbnail(project, phase, elevation_id, thumbnail_data, api_elevation)
                if success:
                    thumbnail_count += 1
                    _logger.debug(f"Successfully fetched and stored thumbnail for elevation {elevation_id}")
                
            except Exception as e:
                error_msg = f"Failed to fetch thumbnail for elevation {elevation_id} in phase {phase.name}: {str(e)}"
                thumbnail_errors.append(error_msg)
                _logger.warning(error_msg)
                # Continue processing other thumbnails
                continue
        
        _logger.info(f"Fetched {thumbnail_count} thumbnails for phase {phase.name}, {len(thumbnail_errors)} errors")
        return thumbnail_count, thumbnail_errors

    def _update_elevation_thumbnail(self, project, phase, elevation_id, thumbnail_data, api_elevation_data):
        """
        Update elevation record with thumbnail data.
        
        Args:
            project: Project record
            phase: Phase record 
            elevation_id: Elevation identifier
            thumbnail_data: Binary thumbnail data
            api_elevation_data: Original elevation data from API
            
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            if not thumbnail_data:
                return False
                
            # Find the elevation record
            elevation = self.env['mbioe.project.elevation'].search([
                ('identifier', '=', elevation_id),
                ('project_id', '=', project.id),
                ('phase_id', '=', phase.id)
            ], limit=1)
            
            if not elevation:
                _logger.warning(f"Elevation {elevation_id} not found in database for thumbnail update")
                return False
            
            # Update with thumbnail data
            import base64
            elevation.write({
                'thumbnail': base64.b64encode(thumbnail_data),
                'thumbnail_filename': f"{api_elevation_data.get('name', 'elevation')}_thumbnail.png"
            })
            
            return True
            
        except Exception as e:
            _logger.error(f"Failed to update elevation {elevation_id} with thumbnail: {str(e)}")
            return False

    def _get_api_client(self):
        """Get configured API client - same as phase sync service"""
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
