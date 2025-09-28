# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError
import time


class MbioeOperations(models.TransientModel):
    _name = 'mbioe.operations'
    _description = 'Logikal Operations Console'
    
    # Display name for Settings-style interface
    display_name = fields.Char(default="Logikal Operations", readonly=True)
    
    # Display fields for current status
    last_connection_test = fields.Datetime(string='Last Connection Test', readonly=True)
    last_sync_time = fields.Datetime(string='Last Sync', readonly=True)
    total_folders = fields.Integer(string='Total Folders', readonly=True)
    root_folders = fields.Integer(string='Root Folders', readonly=True)
    connection_status = fields.Char(string='Connection Status', readonly=True)
    
    # Fields for status messages
    connection_status_message = fields.Char(string="Connection Status Message", readonly=True)
    sync_status_message = fields.Char(string="Sync Status", readonly=True)
    job_queue_diagnosis_message = fields.Text(string="Job Queue Diagnosis", readonly=True)
    
    # Project statistics
    total_projects = fields.Integer(string='Total Projects', readonly=True)
    estimated_projects = fields.Integer(string='Estimated Projects', readonly=True)
    last_project_sync = fields.Datetime(string='Last Project Sync', readonly=True)
    
    # Phase and elevation statistics
    total_phases = fields.Integer(string='Total Phases', readonly=True)
    total_elevations = fields.Integer(string='Total Elevations', readonly=True)
    last_phase_sync = fields.Datetime(string='Last Phase Sync', readonly=True)
    
    def name_get(self):
        return [(rec.id, "Logikal Operations") for rec in self]
    
    @api.model
    def action_open_console(self):
        """Open the operations console as a singleton - re-use existing record to avoid 'New' header"""
        # Per-user scoping to avoid cross-user edits
        domain = [('create_uid', '=', self.env.uid)]
        rec = self.search(domain, limit=1)
        if not rec:
            rec = self.create({})
        return {
            "type": "ir.actions.act_window",
            "name": "Logikal Operations",
            "res_model": "mbioe.operations",
            "view_mode": "form",
            "res_id": rec.id,
            "target": "current",
            "view_id": self.env.ref("logikal_api.view_mbioe_operations_form").id,
            "context": {"form_view_initial_mode": "edit", "clear_breadcrumbs": True},
        }
    
    @api.model
    def default_get(self, fields_list):
        """Load current status when opening the operations view - singleton pattern"""
        vals = super().default_get(fields_list)
        
        # Singleton pattern: reuse existing record if available
        existing = self.search([], limit=1)
        if existing:
            return existing.read(fields_list)[0]
        
        # Load current status for new record
        
        try:
            # Get folder statistics with optimized queries
            folder_model = self.env['mbioe.folder']
            
            # Use read_group for efficient counting
            folder_stats = folder_model.read_group(
                [], ['parent_id'], ['parent_id']
            )
            
            total_folders = sum(stat['parent_id_count'] for stat in folder_stats)
            root_folders = next(
                (stat['parent_id_count'] for stat in folder_stats if not stat['parent_id']), 
                0
            )
            
            vals['total_folders'] = total_folders
            vals['root_folders'] = root_folders
            
            # Get last sync time (optimized query)
            last_sync_valsult = folder_model.search_read([
                ('synced_at', '!=', False)
            ], fields=['synced_at'], order='synced_at desc', limit=1)
            
            if last_sync_valsult:
                vals['last_sync_time'] = last_sync_valsult[0]['synced_at']
            
            # Get project statistics
            project_model = self.env['mbioe.project']
            project_stats = project_model.read_group(
                [], ['estimated'], ['estimated']
            )
            
            total_projects = sum(stat['estimated_count'] for stat in project_stats)
            estimated_projects = next(
                (stat['estimated_count'] for stat in project_stats if stat['estimated']), 
                0
            )
            
            vals['total_projects'] = total_projects
            vals['estimated_projects'] = estimated_projects
            
            # Get last project sync time
            last_project_sync = project_model.search_read([
                ('last_api_sync', '!=', False)
            ], fields=['last_api_sync'], order='last_api_sync desc', limit=1)
            
            if last_project_sync:
                vals['last_project_sync'] = last_project_sync[0]['last_api_sync']
            
            # Get phase and elevation statistics
            phase_model = self.env['mbioe.project.phase']
            elevation_model = self.env['mbioe.project.elevation']
            
            vals['total_phases'] = phase_model.search_count([])
            vals['total_elevations'] = elevation_model.search_count([])
            
            # Get last phase sync time
            last_phase_sync = phase_model.search_read([
                ('last_api_sync', '!=', False)
            ], fields=['last_api_sync'], order='last_api_sync desc', limit=1)
            
            if last_phase_sync:
                vals['last_phase_sync'] = last_phase_sync[0]['last_api_sync']
            
            # Set default status (no blocking API calls)
            vals['connection_status'] = 'unknown'
            vals['connection_status_message'] = 'Click "Test Connection" to check status'
            
            # Set sync status message
            if vals.get('last_sync_time'):
                vals['sync_status_message'] = f"Last sync: {vals['last_sync_time']}"
            else:
                vals['sync_status_message'] = 'No sync performed yet'
            
            # Initialize job queue diagnosis
            vals['job_queue_diagnosis_message'] = 'Click "Diagnose Job Queue" to check status'
                
        except Exception:
            pass  # Don't fail if status can't be loaded
            
        return vals
    
    def action_test_mbioe_connection(self):
        """Test connection to MBIOE API"""
        self.ensure_one()
        
        # Validate configuration exists
        try:
            config_settings = self.env['res.config.settings']
            config = config_settings.get_mbioe_config()
        except Exception as e:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Configuration Error'),
                    'message': _('Please configure API settings first: %s') % str(e),
                    'type': 'danger',
                    'sticky': True,
                }
            }
        
        # Use the service layer to test connection
        mbioe_service = self.env['mbioe.service']
        valsult = mbioe_service.test_connection()
        
        # Update status fields based on test valsult
        if isinstance(valsult, dict) and 'params' in valsult:
            # Extract status from notification valsult
            message = valsult['params'].get('message', 'Connection test completed')
            is_success = valsult['params'].get('type') == 'success'
            
            self.write({
                'last_connection_test': fields.Datetime.now(),
                'connection_status': 'connected' if is_success else 'disconnected',
                'connection_status_message': message
            })
        else:
            self.write({'last_connection_test': fields.Datetime.now()})
        
        return valsult
    
    def action_test_directory_operations(self):
        """Test directory and project operations with MBIOE API"""
        self.ensure_one()
        
        # Validate configuration exists
        try:
            config_settings = self.env['res.config.settings']
            config = config_settings.get_mbioe_config()
        except Exception as e:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Configuration Error'),
                    'message': _('Please configure API settings first: %s') % str(e),
                    'type': 'danger',
                    'sticky': True,
                }
            }
        
        # Use the service layer to test directory operations
        mbioe_service = self.env['mbioe.service']
        return mbioe_service.test_directory_operations()
    
    def action_sync_mbioe_folders(self):
        """Synchronize folders from MBIOE API"""
        self.ensure_one()
        
        # Validate configuration exists
        try:
            config_settings = self.env['res.config.settings']
            config = config_settings.get_mbioe_config()
        except Exception as e:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Configuration Error'),
                    'message': _('Please configure API settings first: %s') % str(e),
                    'type': 'danger',
                    'sticky': True,
                }
            }
        
        # Use the service layer to sync folders
        mbioe_service = self.env['mbioe.service']
        valsult = mbioe_service.sync_folders()
        
        # Don't refvalsh data immediately - background job will complete later
        # Data will be refvalshed when user manually refvalshes or checks job status
        
        return valsult
    
    def action_sync_mbioe_projects(self):
        """Synchronize projects from MBIOE API (requivals folders to be synced first)"""
        self.ensure_one()
        
        # Validate configuration exists
        try:
            config_settings = self.env['res.config.settings']
            config = config_settings.get_mbioe_config()
        except Exception as e:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Configuration Error'),
                    'message': _('Please configure API settings first: %s') % str(e),
                    'type': 'danger',
                    'sticky': True,
                }
            }
        
        # Check if folders exist
        folder_count = self.env['mbioe.folder'].search_count([])
        if folder_count == 0:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('No Folders Found'),
                    'message': _('Please sync folders first before syncing projects.'),
                    'type': 'warning',
                    'sticky': True,
                }
            }
        
        # Use the project sync service
        project_sync_service = self.env['mbioe.project.sync.service']
        valsult = project_sync_service.sync_projects_for_all_folders()
        
        # Don't refvalsh data immediately - background jobs will complete later
        # Data will be refvalshed when user manually refvalshes or checks job status
        
        return valsult
    

    def action_sync_mbioe_phases_elevations(self):
        """Synchronize phases and elevations from MBIOE API (requivals projects to be synced first)"""
        self.ensure_one()
        
        # Validate configuration exists
        try:
            config_settings = self.env['res.config.settings']
            config = config_settings.get_mbioe_config()
        except Exception as e:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Configuration Error'),
                    'message': _('Please configure API settings first: %s') % str(e),
                    'type': 'danger',
                    'sticky': True,
                }
            }
        
        # Check if projects exist
        project_count = self.env['mbioe.project'].search_count([])
        if project_count == 0:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('No Projects Found'),
                    'message': _('Please sync projects first before syncing phases and elevations.'),
                    'type': 'warning',
                    'sticky': True,
                }
            }
        
        # Use the phase sync service to sync both phases and elevations
        phase_sync_service = self.env['mbioe.phase.sync.service']
        
        # Sync phases first
        phase_result = phase_sync_service.sync_phases_for_all_projects()
        
        # Then sync elevations
        elevation_result = phase_sync_service.sync_elevations_only_for_all_projects()
        
        # Return a combined result
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Phase & Elevation Sync Started'),
                'message': _('Both phase and elevation synchronization jobs have been queued. Check the job status for progress updates.'),
                'type': 'success',
                'sticky': True,
            }
        }

    def action_sync_mbioe_phases_only(self):
        """Synchronize phases only (without elevations) from MBIOE API (requivals projects to be synced first)"""
        self.ensure_one()
        
        # Validate configuration exists
        try:
            config_settings = self.env['res.config.settings']
            config = config_settings.get_mbioe_config()
        except Exception as e:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Configuration Error'),
                    'message': _('Please configure API settings first: %s') % str(e),
                    'type': 'danger',
                    'sticky': True,
                }
            }
        
        # Check if projects exist
        project_count = self.env['mbioe.project'].search_count([])
        if project_count == 0:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('No Projects Found'),
                    'message': _('Please sync projects first before syncing phases.'),
                    'type': 'warning',
                    'sticky': True,
                }
            }
        
        # Use the phase sync service
        phase_sync_service = self.env['mbioe.phase.sync.service']
        valsult = phase_sync_service.sync_phases_only_for_all_projects()
        
        # Don't refvalsh data immediately - background jobs will complete later
        # Data will be refvalshed when user manually refvalshes or checks job status
        
        return valsult

    def action_sync_mbioe_elevations_only(self):
        """Synchronize elevations only (requivals phases to exist) from MBIOE API"""
        self.ensure_one()
        
        # Validate configuration exists
        try:
            config_settings = self.env['res.config.settings']
            config = config_settings.get_mbioe_config()
        except Exception as e:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Configuration Error'),
                    'message': _('Please configure API settings first: %s') % str(e),
                    'type': 'danger',
                    'sticky': True,
                }
            }
        
        # Check if projects exist
        project_count = self.env['mbioe.project'].search_count([])
        if project_count == 0:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('No Projects Found'),
                    'message': _('Please sync projects first before syncing elevations.'),
                    'type': 'warning',
                    'sticky': True,
                }
            }
        
        # Check if phases exist
        phase_count = self.env['mbioe.project.phase'].search_count([])
        if phase_count == 0:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('No Phases Found'),
                    'message': _('Please sync phases first before syncing elevations.'),
                    'type': 'warning',
                    'sticky': True,
                }
            }
        
        # Use the phase sync service
        phase_sync_service = self.env['mbioe.phase.sync.service']
        valsult = phase_sync_service.sync_elevations_only_for_all_projects()
        
        # Don't refvalsh data immediately - background jobs will complete later
        # Data will be refvalshed when user manually refvalshes or checks job status
        
        return valsult
    
    def action_check_sync_jobs(self):
        """Check status of recent sync jobs"""
        self.ensure_one()
        
        try:
            mbioe_service = self.env['mbioe.service']
            recent_jobs = mbioe_service.get_sync_job_status()
            
            if not recent_jobs:
                return {
                    'type': 'ir.actions.client',
                    'tag': 'display_notification',
                    'params': {
                        'title': _('Sync Job Status'),
                        'message': _('No recent sync jobs found. Note: Job queue may not be installed.'),
                        'type': 'info',
                        'sticky': False,
                    }
                }
            
            # Format job status message
            job_status_lines = []
            for job in recent_jobs[:5]:  # Show last 5 jobs
                state_status = {
                    'pending': '[PENDING]',
                    'enqueued': '[ENQUEUED]',
                    'started': '[RUNNING]',
                    'done': '[COMPLETED]',
                    'failed': '[FAILED]',
                }.get(job['state'], '[UNKNOWN]')
                
                job_status_lines.append(
                    f"{state_status} {job['state'].title()} - {job['date_created']}"
                )
            
            message = "Recent sync jobs:\n" + "\n".join(job_status_lines)
            
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Recent Sync Jobs'),
                    'message': message,
                    'type': 'info',
                    'sticky': True,
                }
            }
            
        except Exception as e:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Job Status Error'),
                    'message': _('Failed to check job status: %s') % str(e),
                    'type': 'danger',
                    'sticky': True,
                }
            }
    
    def action_diagnose_job_queue(self):
        """Diagnose job queue configuration and status"""
        self.ensure_one()
        
        diagnostic_info = []
        
        try:
            # Check if queue_job model exists
            if 'queue.job' in self.env:
                diagnostic_info.append("[OK] queue.job model is available")
                
                # Count pending jobs
                pending_jobs = self.env['queue.job'].search_count([('state', '=', 'pending')])
                enqueued_jobs = self.env['queue.job'].search_count([('state', '=', 'enqueued')])
                started_jobs = self.env['queue.job'].search_count([('state', '=', 'started')])
                
                diagnostic_info.append(f"Jobs: {pending_jobs} pending, {enqueued_jobs} enqueued, {started_jobs} started")
                
                # Check for recent job activity
                from datetime import datetime, timedelta
                recent_jobs = self.env['queue.job'].search([
                    ('date_created', '>=', datetime.now() - timedelta(hours=1))
                ])
                diagnostic_info.append(f"[INFO] {len(recent_jobs)} jobs created in last hour")
                
                # Check if any jobs have been processed recently
                completed_jobs = self.env['queue.job'].search_count([
                    ('state', '=', 'done'),
                    ('date_done', '>=', datetime.now() - timedelta(hours=24))
                ])
                diagnostic_info.append(f"[OK] {completed_jobs} jobs completed in last 24 hours")
                
            else:
                diagnostic_info.append("[ERROR] queue.job model not found")
                
            # Check if job runner methods are available
            if hasattr(self.env.registry, '_jobrunner'):
                diagnostic_info.append("[OK] Job runner registry found")
            else:
                diagnostic_info.append("[ERROR] Job runner not detected in registry")
                
            # Try to check worker configuration
            try:
                import odoo
                if hasattr(odoo.tools.config, 'options') and 'workers' in odoo.tools.config.options:
                    workers = odoo.tools.config.options.get('workers', 0)
                    diagnostic_info.append(f"[INFO] Workers configured: {workers}")
                    if workers < 2:
                        diagnostic_info.append("[WARNING] Workers < 2, job queue needs workers >= 2")
                else:
                    diagnostic_info.append("[INFO] Cannot determine worker configuration")
            except:
                diagnostic_info.append("[INFO] Cannot access Odoo configuration")
                
        except Exception as e:
            diagnostic_info.append(f"[ERROR] Error during diagnosis: {str(e)}")
        
        message = "Job Queue Diagnosis:\n" + "\n".join(diagnostic_info)
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Job Queue Diagnosis'),
                'message': message,
                'type': 'info',
                'sticky': True,
            }
        }
    
    def action_force_job_processing(self):
        """Manually trigger job processing for testing"""
        self.ensure_one()
        
        try:
            # Try to manually process pending jobs
            if 'queue.job' in self.env:
                pending_jobs = self.env['queue.job'].search([
                    ('state', '=', 'pending')
                ], limit=5)
                
                if not pending_jobs:
                    return {
                        'type': 'ir.actions.client',
                        'tag': 'display_notification',
                        'params': {
                            'title': _('No Pending Jobs'),
                            'message': _('No pending jobs found to process.'),
                            'type': 'info',
                            'sticky': False,
                        }
                    }
                
                processed_count = 0
                for job in pending_jobs:
                    try:
                        # Try to manually execute the job
                        job.perform()
                        processed_count += 1
                    except Exception as e:
                        # Log the error but continue with other jobs
                        import logging
                        _logger = logging.getLogger(__name__)
                        _logger.error(f"Manual job execution failed for job {job.uuid}: {str(e)}")
                
                return {
                    'type': 'ir.actions.client',
                    'tag': 'display_notification',
                    'params': {
                        'title': _('Manual Job Processing'),
                        'message': _('Manually processed %d jobs out of %d pending jobs.') % (processed_count, len(pending_jobs)),
                        'type': 'success' if processed_count > 0 else 'warning',
                        'sticky': False,
                    }
                }
            else:
                return {
                    'type': 'ir.actions.client',
                    'tag': 'display_notification',
                    'params': {
                        'title': _('Job Queue Not Available'),
                        'message': _('queue.job model not found.'),
                        'type': 'danger',
                        'sticky': True,
                    }
                }
                
        except Exception as e:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Manual Processing Error'),
                    'message': _('Error during manual job processing: %s') % str(e),
                    'type': 'danger',
                    'sticky': True,
                }
            }
    
    def action_cleanup_session_logs(self):
        """Manually cleanup old session logs"""
        self.ensure_one()
        
        try:
            config_settings = self.env['res.config.settings']
            config = config_settings.get_mbioe_config()
            
            cleanup_days = config.get('log_cleanup_days', 30)
            if cleanup_days <= 0:
                return {
                    'type': 'ir.actions.client',
                    'tag': 'display_notification',
                    'params': {
                        'title': _('Log Cleanup Disabled'),
                        'message': _('Log cleanup is disabled (days set to 0). Configure cleanup days in Settings.'),
                        'type': 'warning',
                        'sticky': True,
                    }
                }
            
            session_log_model = self.env['mbioe.session.log']
            cleaned_count = session_log_model.cleanup_old_logs(cleanup_days)
            
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Log Cleanup Complete'),
                    'message': _('Cleaned up %d old session log entries.') % cleaned_count,
                    'type': 'success',
                    'sticky': False,
                }
            }
            
        except Exception as e:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Log Cleanup Error'),
                    'message': _('Failed to cleanup logs: %s') % str(e),
                    'type': 'danger',
                    'sticky': True,
                }
            }
    
    def action_refvalsh_data(self):
        """Refvalsh the current data display"""
        self.ensure_one()
        
        # Get updated data
        values = self.default_get([])
        self.write(values)
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Data Refvalshed'),
                'message': _('Current status has been updated.'),
                'type': 'success',
                'sticky': False,
            }
        }
    
    @api.model
    def action_open_operations(self):
        """Action to open the operations view"""
        operations_record = self.create({})
        
        return {
            'type': 'ir.actions.act_window',
            'name': _('MBIOE Operations'),
            'vals_model': 'mbioe.operations',
            'vals_id': operations_record.id,
            'view_mode': 'form',
            'target': 'current',
            'context': self.env.context,
        }
