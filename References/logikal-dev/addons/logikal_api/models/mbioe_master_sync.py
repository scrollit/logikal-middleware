# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError
from datetime import datetime, timedelta
import time

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


class MbioeMasterSync(models.Model):
    _name = 'mbioe.master.sync'
    _description = 'Master Sync Orchestration Status'
    _order = 'create_date desc'
    
    # Basic identification
    name = fields.Char('Sync Name', required=True)
    sync_type = fields.Selection([
        ('phases', 'Phase Sync'),
        ('projects', 'Project Sync'),
        ('elevations', 'Elevation Sync'),
        ('full', 'Full Sync')
    ], required=True)
    
    # Status tracking
    state = fields.Selection([
        ('draft', 'Draft'),
        ('queued', 'Queued'),
        ('running', 'Running'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
        ('cancelled', 'Cancelled')
    ], default='draft')
    
    # Progress tracking
    total_folders = fields.Integer('Total Folders')
    completed_folders = fields.Integer('Completed Folders')
    running_folders = fields.Integer('Running Folders')
    failed_folders = fields.Integer('Failed Folders')
    pending_folders = fields.Integer('Pending Folders')
    progress_percentage = fields.Float('Progress %', default=0.0)
    
    # Timing
    start_time = fields.Datetime('Start Time')
    end_time = fields.Datetime('End Time')
    estimated_completion = fields.Datetime('Estimated Completion')
    last_update_time = fields.Datetime('Last Updated', default=fields.Datetime.now)
    
    # Results
    total_projects = fields.Integer('Total Projects')
    total_phases = fields.Integer('Total Phases')
    total_elevations = fields.Integer('Total Elevations')
    
    # Error tracking
    error_count = fields.Integer('Error Count')
    error_summary = fields.Text('Error Summary')
    
    # Job references
    master_job_id = fields.Many2one('queue.job', 'Master Job')
    master_job_uuid = fields.Char('Master Job UUID', help='UUID of the master sync job for tracking')
    folder_job_ids = fields.One2many('mbioe.folder.sync', 'master_sync_id', 'Folder Jobs')
    
    # Computed fields
    duration = fields.Float('Duration (seconds)', compute='_compute_duration', store=True)
    progress_summary = fields.Char('Progress Summary', compute='_compute_progress_summary', store=True)
    master_job_status = fields.Selection([
        ('pending', 'Pending'),
        ('started', 'Started'),
        ('done', 'Completed'),
        ('failed', 'Failed'),
        ('cancelled', 'Cancelled')
    ], string='Master Job Status', compute='_compute_master_job_status', store=True)
    
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
    
    @api.depends('completed_folders', 'total_folders', 'progress_percentage')
    def _compute_progress_summary(self):
        """Compute progress summary text"""
        for record in self:
            if record.total_folders > 0:
                record.progress_summary = f"{record.completed_folders}/{record.total_folders} folders completed ({record.progress_percentage:.1f}%)"
            else:
                record.progress_summary = "No folders to sync"
    
    @api.depends('master_job_uuid')
    def _compute_master_job_status(self):
        """Compute master job status from queue job UUID"""
        for record in self:
            if record.master_job_uuid:
                # Try to find the job in the queue
                job_record = self.env['queue.job'].search([('uuid', '=', record.master_job_uuid)], limit=1)
                if job_record:
                    record.master_job_status = job_record.state
                else:
                    record.master_job_status = 'pending'
            else:
                record.master_job_status = False
    
    def action_start_sync(self):
        """Start the master sync process"""
        self.ensure_one()
        if self.state != 'draft':
            raise UserError(_("Sync can only be started from draft state"))
        
        # Check if queue_job is available and job runner is working
        try:
            # First check if job runner is actually running (Odoo.Sh specific issue)
            if hasattr(self.env.registry, '_jobrunner'):
                # Job runner exists, try to enqueue
                job = self.with_delay(
                    description=f"Master {self.sync_type} sync: {self.name}",
                    channel='mbioe.sync.orchestrator',
                    priority=10
                )._execute_master_sync(self.id)
                
                self.write({
                    'state': 'queued',
                    'master_job_uuid': job.uuid,
                    'start_time': fields.Datetime.now()
                })
                
                return {
                    'type': 'ir.actions.client',
                    'tag': 'display_notification',
                    'params': {
                        'title': _('Sync Started'),
                        'message': _('Master sync has been queued and will start shortly.'),
                        'type': 'info',
                        'sticky': False,
                    }
                }
            else:
                # Job runner not available, force fallback to synchronous execution
                raise Exception("Job runner not detected in registry - falling back to synchronous execution")
                
        except (AttributeError, ImportError, Exception) as e:
            # Fallback to synchronous execution if queue_job is not available
            import logging
            _logger = logging.getLogger(__name__)
            _logger.warning(f"Queue job not available ({str(e)}), falling back to synchronous execution")
            
            # Execute sync directly
            try:
                result = self._execute_master_sync(self.id)
                
                # Update state to completed since we executed synchronously
                self.write({
                    'state': 'completed',
                    'start_time': fields.Datetime.now(),
                    'end_time': fields.Datetime.now()
                })
                
                return {
                    'type': 'ir.actions.client',
                    'tag': 'display_notification',
                    'params': {
                        'title': _('Sync Completed'),
                        'message': _('Master sync completed synchronously. Check sync details for results.'),
                        'type': 'success',
                        'sticky': False,
                    }
                }
            except Exception as sync_error:
                # Mark as failed
                self.write({
                    'state': 'failed',
                    'error_summary': str(sync_error),
                    'start_time': fields.Datetime.now(),
                    'end_time': fields.Datetime.now()
                })
                
                return {
                    'type': 'ir.actions.client',
                    'tag': 'display_notification',
                    'params': {
                        'title': _('Sync Failed'),
                        'message': _('Master sync failed: %s') % str(sync_error),
                        'type': 'danger',
                        'sticky': True,
                    }
                }
    
    def action_cancel_sync(self):
        """Cancel the sync process"""
        self.ensure_one()
        if self.state not in ['queued', 'running']:
            raise UserError(_("Sync can only be cancelled when queued or running"))
        
        # Cancel running folder jobs
        running_jobs = self.folder_job_ids.filtered(lambda j: j.job_id and j.job_id.state in ['pending', 'started'])
        for job in running_jobs:
            if job.job_id:
                job.job_id.button_cancelled()
        
        self.write({
            'state': 'cancelled',
            'end_time': fields.Datetime.now()
        })
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Sync Cancelled'),
                'message': _('Sync process has been cancelled.'),
                'type': 'warning',
                'sticky': False,
            }
        }
    
    def action_retry_failed(self):
        """Retry failed folder jobs"""
        self.ensure_one()
        failed_jobs = self.folder_job_ids.filtered(lambda j: j.sync_status == 'failed')
        
        if not failed_jobs:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('No Failed Jobs'),
                    'message': _('No failed jobs to retry.'),
                    'type': 'info',
                    'sticky': False,
                }
            }
        
        # Reset failed jobs and restart sync
        failed_jobs.write({
            'sync_status': 'not_started',
            'error_message': False,
            'retry_count': 0
        })
        
        # Restart master sync
        self.action_start_sync()
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Retry Started'),
                'message': _('Retrying failed jobs.'),
                'type': 'info',
                'sticky': False,
            }
        }
    
    def get_master_job_record(self):
        """Get the master job record from the queue using UUID"""
        self.ensure_one()
        if self.master_job_uuid:
            return self.env['queue.job'].search([('uuid', '=', self.master_job_uuid)], limit=1)
        return False
    
    def update_progress(self):
        """Update overall sync progress from folder jobs"""
        self.ensure_one()
        
        folder_jobs = self.folder_job_ids
        
        # Count jobs by status
        self.completed_folders = len(folder_jobs.filtered(lambda j: j.sync_status == 'completed'))
        self.running_folders = len(folder_jobs.filtered(lambda j: j.sync_status == 'in_progress'))
        self.failed_folders = len(folder_jobs.filtered(lambda j: j.sync_status == 'failed'))
        self.pending_folders = len(folder_jobs.filtered(lambda j: j.sync_status == 'not_started'))
        
        # Calculate progress percentage
        if self.total_folders > 0:
            self.progress_percentage = (self.completed_folders / self.total_folders) * 100
        
        # Update estimated completion
        self._update_estimated_completion()
        
        # Update overall state
        self._update_overall_state()
        
        # Update last update time
        self.last_update_time = fields.Datetime.now()
    
    def _update_estimated_completion(self):
        """Calculate estimated completion time based on progress"""
        if not self.start_time or self.progress_percentage == 0:
            return
            
        elapsed = fields.Datetime.now() - self.start_time
        if self.progress_percentage > 0:
            total_estimated = elapsed / (self.progress_percentage / 100)
            remaining = total_estimated - elapsed
            self.estimated_completion = fields.Datetime.now() + timedelta(seconds=remaining.total_seconds())
    
    def _update_overall_state(self):
        """Update master sync state based on folder jobs"""
        if self.failed_folders == self.total_folders:
            self.state = 'failed'
        elif self.completed_folders == self.total_folders:
            self.state = 'completed'
            self.end_time = fields.Datetime.now()
        elif self.running_folders > 0 or self.completed_folders > 0:
            self.state = 'running'
        else:
            self.state = 'queued'
    
    def start_background_monitoring(self):
        """Start background monitoring of sync progress"""
        self.ensure_one()
        
        # Check if job runner is available before creating monitoring job
        try:
            if hasattr(self.env.registry, '_jobrunner'):
                # Create monitoring job
                self.with_delay(
                    description=f"Monitor sync progress: {self.name}",
                    channel='mbioe.monitoring',
                    priority=30
                )._background_monitor_sync(self.id)
            else:
                # Job runner not available, skip background monitoring
                import logging
                _logger = logging.getLogger(__name__)
                _logger.warning("Job runner not available, skipping background monitoring")
        except Exception as e:
            import logging
            _logger = logging.getLogger(__name__)
            _logger.warning(f"Failed to start background monitoring: {str(e)}")
    
    @api.model
    def _background_monitor_sync(self, sync_id):
        """Background job to monitor sync progress"""
        sync = self.browse(sync_id)
        
        while sync.state in ['queued', 'running']:
            # Update progress
            sync.update_progress()
            
            # Check for completion
            if sync.state in ['completed', 'failed']:
                break
            
            # Wait before next update
            time.sleep(30)  # Update every 30 seconds
    
    @api.model
    def _execute_master_sync(self, sync_id):
        """Execute the master sync orchestration"""
        master_sync = self.browse(sync_id)
        
        try:
            # Start background monitoring
            master_sync.start_background_monitoring()
            
            # Execute sync based on type
            if master_sync.sync_type == 'phases':
                return self._execute_master_sync_phases(master_sync)
            elif master_sync.sync_type == 'projects':
                return self._execute_master_sync_projects(master_sync)
            elif master_sync.sync_type == 'elevations':
                return self._execute_master_sync_elevations(master_sync)
            else:
                raise UserError(_("Unsupported sync type: %s") % master_sync.sync_type)
                
        except Exception as e:
            master_sync.write({
                'state': 'failed',
                'error_summary': str(e),
                'end_time': fields.Datetime.now()
            })
            raise
    
    def _execute_master_sync_phases(self, master_sync):
        """Execute staged phase sync"""
        # Get folders with projects, excluding excluded folders
        folders = self.env['mbioe.folder'].search([
            ('project_ids', '!=', False),
            ('exclude_from_sync', '=', False)
        ])
        
        if not folders:
            master_sync.write({
                'state': 'completed',
                'total_folders': 0,
                'end_time': fields.Datetime.now()
            })
            return {'status': 'completed', 'message': 'No folders with projects found'}
        
        # Create folder sync records
        folder_syncs = []
        for folder in folders:
            project_count = len(folder.project_ids)
            if project_count > 0:
                folder_sync = self.env['mbioe.folder.sync'].create({
                    'master_sync_id': master_sync.id,
                    'folder_id': folder.id,
                    'total_projects': project_count,
                    'sync_status': 'not_started'
                })
                folder_syncs.append(folder_sync)
        
        # Update master sync with folder count
        master_sync.write({
            'total_folders': len(folder_syncs),
            'state': 'running'
        })
        
        # Create individual folder sync jobs
        for folder_sync in folder_syncs:
            try:
                if hasattr(self.env.registry, '_jobrunner'):
                    folder_sync.with_delay(
                        description=f"Sync phases for folder: {folder_sync.folder_id.name}",
                        channel='mbioe.sync.phases',
                        priority=20
                    )._sync_folder_phases(folder_sync.id)
                else:
                    # Job runner not available, execute synchronously
                    folder_sync._sync_folder_phases(folder_sync.id)
            except Exception as e:
                import logging
                _logger = logging.getLogger(__name__)
                _logger.warning(f"Failed to sync folder {folder_sync.folder_id.name}: {str(e)}")
                folder_sync.write({'sync_status': 'failed', 'error_message': str(e)})
        
        return {'status': 'started', 'folders': len(folder_syncs)}
    
    def _execute_master_sync_projects(self, master_sync):
        """Execute staged project sync"""
        # Get root folders, excluding excluded ones
        root_folders = self.env['mbioe.folder'].search([
            ('parent_id', '=', False),
            ('exclude_from_sync', '=', False)
        ])
        
        if not root_folders:
            master_sync.write({
                'state': 'completed',
                'total_folders': 0,
                'end_time': fields.Datetime.now()
            })
            return {'status': 'completed', 'message': 'No root folders found'}
        
        # Create folder sync records
        folder_syncs = []
        for folder in root_folders:
            folder_sync = self.env['mbioe.folder.sync'].create({
                'master_sync_id': master_sync.id,
                'folder_id': folder.id,
                'sync_status': 'not_started'
            })
            folder_syncs.append(folder_sync)
        
        # Update master sync with folder count
        master_sync.write({
            'total_folders': len(folder_syncs),
            'state': 'running'
        })
        
        # Create individual folder sync jobs
        for folder_sync in folder_syncs:
            try:
                if hasattr(self.env.registry, '_jobrunner'):
                    folder_sync.with_delay(
                        description=f"Sync projects for folder: {folder_sync.folder_id.name}",
                        channel='mbioe.sync.projects',
                        priority=20
                    )._sync_folder_projects(folder_sync.id)
                else:
                    # Job runner not available, execute synchronously
                    folder_sync._sync_folder_projects(folder_sync.id)
            except Exception as e:
                import logging
                _logger = logging.getLogger(__name__)
                _logger.warning(f"Failed to sync folder {folder_sync.folder_id.name}: {str(e)}")
                folder_sync.write({'sync_status': 'failed', 'error_message': str(e)})
        
        return {'status': 'started', 'folders': len(folder_syncs)}
    
    def _execute_master_sync_elevations(self, master_sync):
        """Execute staged elevation sync"""
        # Get all projects that have phases
        projects = self.env['mbioe.project'].search([
            ('id', 'in', self.env['mbioe.project.phase'].search([]).mapped('project_id.id'))
        ])
        
        if not projects:
            master_sync.write({
                'state': 'failed',
                'error_summary': 'No projects with phases found. Please sync phases first.',
                'end_time': fields.Datetime.now()
            })
            return {'status': 'failed', 'error': 'No projects with phases found'}
        
        # Update master sync with project count
        master_sync.write({
            'total_projects': len(projects),
            'state': 'running'
        })
        
        # Create individual project elevation sync jobs
        elevation_sync_service = self.env['mbioe.elevation.sync.service']
        for project in projects:
            try:
                if hasattr(self.env.registry, '_jobrunner'):
                    elevation_sync_service.with_delay(
                        description=f"Sync elevations for project: {project.name}",
                        channel='mbioe.sync.elevations',
                        priority=20
                    ).sync_elevations_for_project(project.id)
                else:
                    # Job runner not available, execute synchronously
                    elevation_sync_service.sync_elevations_for_project(project.id)
            except Exception as e:
                import logging
                _logger = logging.getLogger(__name__)
                _logger.warning(f"Failed to sync elevations for project {project.name}: {str(e)}")
        
        return {'status': 'started', 'projects': len(projects)}
