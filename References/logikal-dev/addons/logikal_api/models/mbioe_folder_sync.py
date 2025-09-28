# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError
import time
import logging
from datetime import datetime

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


class MbioeFolderSync(models.Model):
    _name = 'mbioe.folder.sync'
    _description = 'Individual Folder Sync Status'
    _order = 'create_date desc'
    
    # Relationships
    master_sync_id = fields.Many2one('mbioe.master.sync', 'Master Sync', required=True, ondelete='cascade')
    folder_id = fields.Many2one('mbioe.folder', 'Folder', required=True)
    
    # Job tracking
    job_id = fields.Many2one('queue.job', 'Queue Job')
    job_state = fields.Selection([
        ('pending', 'Pending'),
        ('started', 'Started'),
        ('done', 'Completed'),
        ('failed', 'Failed')
    ], related='job_id.state', store=True)
    
    # Progress tracking
    total_projects = fields.Integer('Total Projects')
    completed_projects = fields.Integer('Completed Projects')
    current_project = fields.Char('Current Project')
    
    # Results
    phases_created = fields.Integer('Phases Created')
    phases_updated = fields.Integer('Phases Updated')
    phases_deleted = fields.Integer('Phases Deleted')
    elevations_created = fields.Integer('Elevations Created')
    elevations_updated = fields.Integer('Elevations Updated')
    elevations_deleted = fields.Integer('Elevations Deleted')
    
    # Status
    sync_status = fields.Selection([
        ('not_started', 'Not Started'),
        ('in_progress', 'In Progress'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
        ('skipped', 'Skipped')
    ], default='not_started')
    
    # Timing
    start_time = fields.Datetime('Start Time')
    end_time = fields.Datetime('End Time')
    duration = fields.Float('Duration (seconds)', compute='_compute_duration', store=True)
    
    # Error tracking
    error_message = fields.Text('Error Message')
    retry_count = fields.Integer('Retry Count', default=0)
    
    # Computed fields
    folder_name = fields.Char('Folder Name', related='folder_id.name', store=True)
    folder_path = fields.Char('Folder Path', related='folder_id.full_path', store=True)
    master_sync_name = fields.Char('Master Sync Name', related='master_sync_id.name', store=True)
    sync_type = fields.Selection(related='master_sync_id.sync_type', store=True)
    
    @api.depends('start_time', 'end_time')
    def _compute_duration(self):
        """Compute sync duration in seconds"""
        for record in self:
            if record.start_time and record.end_time:
                delta = record.end_time - record.start_time
                record.duration = delta.total_seconds()
            elif record.start_time:
                delta = fields.Datetime.now() - record.start_time
                record.duration = delta.total_seconds()
            else:
                record.duration = 0.0
    
    @api.model
    def _sync_folder_phases(self, folder_sync_id):
        """Sync phases for a specific folder"""
        folder_sync = self.browse(folder_sync_id)
        
        # Check if folder is excluded from sync
        if folder_sync.folder_id.exclude_from_sync:
            folder_sync.write({
                'sync_status': 'skipped',
                'start_time': fields.Datetime.now(),
                'end_time': fields.Datetime.now()
            })
            _logger.info(f"Skipped excluded folder: {folder_sync.folder_id.name}")
            return
        
        try:
            folder_sync.write({
                'sync_status': 'in_progress',
                'start_time': fields.Datetime.now()
            })
            
            # Get API client
            api_client = self.env['mbioe.service']._get_api_client()
            
            # Process each project in the folder
            projects = folder_sync.folder_id.project_ids
            total_projects = len(projects)
            completed_projects = 0
            
            folder_sync.write({'total_projects': total_projects})
            
            for project in projects:
                try:
                    folder_sync.write({
                        'current_project': project.name,
                        'completed_projects': completed_projects
                    })
                    
                    # Sync phases for this project using existing logic
                    phases_count, elevations_count, errors = self._sync_project_phases(api_client, project)
                    
                    # Update results
                    folder_sync.write({
                        'phases_created': folder_sync.phases_created + phases_count,
                        'elevations_created': folder_sync.elevations_created + elevations_count
                    })
                    
                    completed_projects += 1
                    
                except Exception as e:
                    # Log error but continue with next project (partial success)
                    error_msg = f"Error syncing project {project.name}: {str(e)}"
                    _logger.error(error_msg)
                    continue
            
            # Mark as completed
            folder_sync.write({
                'sync_status': 'completed',
                'end_time': fields.Datetime.now(),
                'completed_projects': completed_projects
            })
            
        except Exception as e:
            # Mark as failed
            folder_sync.write({
                'sync_status': 'failed',
                'error_message': str(e),
                'end_time': fields.Datetime.now()
            })
            raise
        finally:
            # Cleanup API client
            if 'api_client' in locals() and api_client.session_token:
                try:
                    api_client.logout()
                except:
                    pass
    
    @api.model
    def _sync_folder_projects(self, folder_sync_id):
        """Sync projects for a specific folder"""
        folder_sync = self.browse(folder_sync_id)
        
        # Check if folder is excluded from sync
        if folder_sync.folder_id.exclude_from_sync:
            folder_sync.write({
                'sync_status': 'skipped',
                'start_time': fields.Datetime.now(),
                'end_time': fields.Datetime.now()
            })
            _logger.info(f"Skipped excluded folder: {folder_sync.folder_id.name}")
            return
        
        try:
            folder_sync.write({
                'sync_status': 'in_progress',
                'start_time': fields.Datetime.now()
            })
            
            # Get API client
            api_client = self.env['mbioe.service']._get_api_client()
            
            # Navigate to folder
            api_client.authenticate()
            api_client.select_directory(folder_sync.folder_id.identifier)
            
            # Get projects from API
            api_projects = api_client.get_projects()
            
            if api_projects:
                # Process projects
                for project_data in api_projects:
                    try:
                        # Create or update project
                        self._process_project_data(project_data, folder_sync.folder_id)
                    except Exception as e:
                        error_msg = f"Error processing project {project_data.get('name', 'Unknown')}: {str(e)}"
                        _logger.error(error_msg)
                        continue
                
                folder_sync.write({
                    'sync_status': 'completed',
                    'end_time': fields.Datetime.now()
                })
            else:
                folder_sync.write({
                    'sync_status': 'completed',
                    'end_time': fields.Datetime.now()
                })
            
        except Exception as e:
            # Mark as failed
            folder_sync.write({
                'sync_status': 'failed',
                'error_message': str(e),
                'end_time': fields.Datetime.now()
            })
            raise
        finally:
            # Cleanup API client
            if 'api_client' in locals() and api_client.session_token:
                try:
                    api_client.logout()
                except:
                    pass
    
    def _sync_project_phases(self, api_client, project):
        """Sync phases for a single project (adapted from existing logic)"""
        phases_count = 0
        elevations_count = 0
        errors = []
        
        try:
            # Navigate through folder hierarchy to reach project
            if not project.folder_id:
                errors.append(f"Project {project.name} has no folder association")
                return 0, 0, errors
            
            # Get the complete navigation path from root to target folder
            navigation_success = self._navigate_to_project_folder(api_client, project)
            if not navigation_success:
                errors.append(f"Failed to navigate to folder for project {project.name}")
                return 0, 0, errors
            
            # Now select the project in the API client session
            api_client.select_project(project.identifier)
            
            api_phases = api_client.get_phases()
            if not api_phases:
                _logger.info(f"No phases found for project {project.name} ({project.identifier})")
                return 0, 0, []

            # Mark existing phases as 'to_remove'
            existing_phases = self.env['mbioe.project.phase'].search([('project_id', '=', project.id)])
            existing_phases.write({'sync_status': 'to_remove'})

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
                
                # Sync elevations for this phase
                phase_elevations_count, phase_errors = self._sync_elevations_for_phase(api_client, project, phase)
                elevations_count += phase_elevations_count
                errors.extend(phase_errors)

            # Remove phases not found in the latest API sync
            self.env['mbioe.project.phase'].search([
                ('project_id', '=', project.id),
                ('sync_status', '=', 'to_remove')
            ]).unlink()

            project.write({'last_api_sync': fields.Datetime.now(), 'sync_status': 'unchanged'})

        except Exception as e:
            errors.append(f"Error syncing phases for project {project.name} ({project.identifier}): {str(e)}")
            project.write({'sync_status': 'error'})
            _logger.error(f"Error syncing phases for project {project.name} ({project.identifier}): {str(e)}")

        return phases_count, elevations_count, errors
    
    def _sync_elevations_for_phase(self, api_client, project, phase):
        """Sync elevations for a single phase (adapted from existing logic)"""
        elevations_count = 0
        errors = []
        
        try:
            # Get elevations for this phase
            api_elevations = api_client.get_elevations(phase.identifier)
            if not api_elevations:
                return 0, []

            # Mark existing elevations as 'to_remove'
            existing_elevations = self.env['mbioe.project.elevation'].search([('phase_id', '=', phase.id)])
            existing_elevations.write({'sync_status': 'to_remove'})

            for api_elevation_data in api_elevations:
                elevation_identifier = api_elevation_data.get('id')
                if not elevation_identifier:
                    errors.append(f"Elevation data missing identifier for phase {phase.name}")
                    continue

                elevation = self.env['mbioe.project.elevation'].search([
                    ('phase_id', '=', phase.id),
                    ('identifier', '=', elevation_identifier)
                ], limit=1)

                if elevation:
                    elevation.update_from_api_data(api_elevation_data)
                    _logger.debug(f"Updated elevation: {elevation.name} ({elevation.identifier})")
                else:
                    elevation = self.env['mbioe.project.elevation'].create_from_api_data(api_elevation_data, phase.id)
                    _logger.debug(f"Created new elevation: {elevation.name} ({elevation.identifier})")
                
                elevations_count += 1

            # Remove elevations not found in the latest API sync
            self.env['mbioe.project.elevation'].search([
                ('phase_id', '=', phase.id),
                ('sync_status', '=', 'to_remove')
            ]).unlink()

        except Exception as e:
            errors.append(f"Error syncing elevations for phase {phase.name}: {str(e)}")
            _logger.error(f"Error syncing elevations for phase {phase.name}: {str(e)}")

        return elevations_count, errors
    
    def _navigate_to_project_folder(self, api_client, project):
        """Navigate to project folder (adapted from existing logic)"""
        try:
            if not project.folder_id:
                return False
            
            # Navigate to the folder containing the project
            api_client.select_directory(project.folder_id.identifier)
            return True
            
        except Exception as e:
            _logger.error(f"Failed to navigate to folder for project {project.name}: {str(e)}")
            return False
    
    def _process_project_data(self, project_data, folder):
        """Process project data (adapted from existing logic)"""
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
        
        # Prepare project values
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
            # Check if update is needed
            if self._should_update_project(existing_project, api_changed_date):
                project_values['sync_status'] = 'updated'
                existing_project.with_context(from_mbioe_sync=True).write(project_values)
                _logger.debug(f"Updated project: {project_data.get('name')} [{project_identifier[:8]}]")
            else:
                # Just update sync timestamp
                existing_project.with_context(from_mbioe_sync=True).write({
                    'last_api_sync': fields.Datetime.now(),
                    'synced_at': fields.Datetime.now(),
                    'sync_status': 'unchanged',
                })
                _logger.debug(f"Skipped unchanged project: {project_data.get('name')} [{project_identifier[:8]}]")
        else:
            # Create new project
            project_values['sync_status'] = 'new'
            new_project = self.env['mbioe.project'].with_context(from_mbioe_sync=True).create(project_values)
            _logger.debug(f"Created project: {project_data.get('name')} [{project_identifier[:8]}]")
    
    def _should_update_project(self, existing_project, api_changed_date):
        """Determine if project should be updated"""
        if not api_changed_date:
            return False
        
        if not existing_project.last_api_sync:
            return True
        
        return api_changed_date > existing_project.last_api_sync
    
    def _convert_api_timestamp(self, timestamp):
        """Convert MBIOE API timestamp to Odoo datetime"""
        if not timestamp:
            return None
        
        try:
            if isinstance(timestamp, str):
                timestamp = float(timestamp)
            
            if timestamp <= 0:
                return None
            
            # Handle both seconds and milliseconds
            if timestamp > 10**10:  # Milliseconds
                timestamp = timestamp / 1000
            
            result_dt = datetime.fromtimestamp(timestamp)
            return result_dt
            
        except (ValueError, TypeError, OSError, OverflowError):
            return None
