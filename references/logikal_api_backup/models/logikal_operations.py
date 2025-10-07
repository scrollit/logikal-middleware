# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError
import time


class LogikalOperations(models.TransientModel):
    _name = 'logikal.operations'
    _description = 'Logikal Operations Console'
    
    # Display name for Settings-style interface
    display_name = fields.Char(default="Logikal Operations", readonly=True)
    
    # Display fields for current status
    last_connection_test = fields.Datetime(string='Last Connection Test', readonly=True)
    last_sync_time = fields.Datetime(string='Last Sync', readonly=True)
    connection_status = fields.Char(string='Connection Status', readonly=True)
    
    # Fields for status messages
    connection_status_message = fields.Char(string="Connection Status Message", readonly=True)
    sync_status_message = fields.Char(string="Sync Status", readonly=True)
    
    # Project statistics
    total_projects = fields.Integer(string='Total Projects', readonly=True)
    synced_projects = fields.Integer(string='Synced Projects', readonly=True)
    error_projects = fields.Integer(string='Projects with Errors', readonly=True)
    
    # Phase and elevation statistics
    total_phases = fields.Integer(string='Total Phases', readonly=True)
    total_elevations = fields.Integer(string='Total Elevations', readonly=True)
    
    # Integration mode
    integration_mode = fields.Char(string='Integration Mode', readonly=True)
    
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
            "res_model": "logikal.operations",
            "view_mode": "form",
            "res_id": rec.id,
            "target": "current",
            "view_id": self.env.ref("logikal_api.view_logikal_operations_form").id,
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
            # Get integration mode
            config_settings = self.env['res.config.settings']
            active_config = config_settings.get_active_config()
            vals['integration_mode'] = active_config['type'].title()
            
            # Get project statistics
            project_model = self.env['logikal.project']
            vals['total_projects'] = project_model.search_count([])
            vals['synced_projects'] = project_model.search_count([('sync_status', '=', 'synced')])
            vals['error_projects'] = project_model.search_count([('sync_status', '=', 'error')])
            
            # Get phase and elevation statistics
            phase_model = self.env['logikal.phase']
            elevation_model = self.env['logikal.elevation']
            
            vals['total_phases'] = phase_model.search_count([])
            vals['total_elevations'] = elevation_model.search_count([])
            
            # Get last sync time (optimized query)
            last_sync_result = project_model.search_read([
                ('middleware_sync_date', '!=', False)
            ], fields=['middleware_sync_date'], order='middleware_sync_date desc', limit=1)
            
            if last_sync_result:
                vals['last_sync_time'] = last_sync_result[0]['middleware_sync_date']
            
            # Set default status
            vals['connection_status'] = 'unknown'
            vals['connection_status_message'] = 'Click "Test Connection" to check status'
            
            # Set sync status message
            if vals.get('last_sync_time'):
                vals['sync_status_message'] = f"Last sync: {vals['last_sync_time']}"
            else:
                vals['sync_status_message'] = 'No sync performed yet'
                
        except Exception:
            pass  # Don't fail if status can't be loaded
            
        return vals
    
    def action_test_connection(self):
        """Test connection to active system (middleware or MBIOE)"""
        self.ensure_one()
        
        # Validate configuration exists
        try:
            config_settings = self.env['res.config.settings']
            active_config = config_settings.get_active_config()
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
        
        # Use the unified service to test connection
        logikal_service = self.env['logikal.service']
        result = logikal_service.test_connection()
        
        # Update status fields based on test result
        if isinstance(result, dict) and 'params' in result:
            # Extract status from notification result
            message = result['params'].get('message', 'Connection test completed')
            is_success = result['params'].get('type') == 'success'
            
            self.write({
                'last_connection_test': fields.Datetime.now(),
                'connection_status': 'connected' if is_success else 'disconnected',
                'connection_status_message': message
            })
        else:
            self.write({'last_connection_test': fields.Datetime.now()})
        
        return result
    
    def action_sync_all_projects(self):
        """Synchronize all projects from active system"""
        self.ensure_one()
        
        # Validate configuration exists
        try:
            config_settings = self.env['res.config.settings']
            active_config = config_settings.get_active_config()
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
        
        # Use the unified service to sync projects
        logikal_service = self.env['logikal.service']
        result = logikal_service.sync_all_projects()
        
        # Refresh data after sync
        self.action_refresh_data()
        
        return result
    
    # def action_sync_single_project(self):
    #     """Synchronize a single project (opens wizard)"""
    #     self.ensure_one()
    #     
    #     return {
    #         'type': 'ir.actions.act_window',
    #         'name': _('Sync Single Project'),
    #         'res_model': 'logikal.sync.project.wizard',
    #         'view_mode': 'form',
    #         'target': 'new',
    #         'context': self.env.context,
    #     }
    
    def action_cleanup_session_logs(self):
        """Manually cleanup old session logs"""
        self.ensure_one()
        
        try:
            config_settings = self.env['res.config.settings']
            active_config = config_settings.get_active_config()
            config = active_config['config']
            
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
            
            logikal_service = self.env['logikal.service']
            cleaned_count = logikal_service.cleanup_old_logs()
            
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
    
    def action_refresh_data(self):
        """Refresh the current data display"""
        self.ensure_one()
        
        # Get updated data
        values = self.default_get([])
        self.write(values)
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Data Refreshed'),
                'message': _('Current status has been updated.'),
                'type': 'success',
                'sticky': False,
            }
        }
    
    def action_view_projects(self):
        """Open projects view"""
        return {
            'type': 'ir.actions.act_window',
            'name': _('Logikal Projects'),
            'res_model': 'logikal.project',
            'view_mode': 'tree,form',
            'target': 'current',
            'context': self.env.context,
        }
    
    def action_view_session_logs(self):
        """Open session logs view"""
        return {
            'type': 'ir.actions.act_window',
            'name': _('Session Logs'),
            'res_model': 'logikal.session.log',
            'view_mode': 'tree,form',
            'target': 'current',
            'context': self.env.context,
        }
    
    def action_switch_integration_mode(self):
        """Switch between middleware and MBIOE integration"""
        self.ensure_one()
        
        try:
            config_settings = self.env['res.config.settings']
            active_config = config_settings.get_active_config()
            current_mode = active_config['type']
            
            # Toggle the mode
            ICP = self.env['ir.config_parameter'].sudo()
            new_mode = 'middleware' if current_mode == 'mbioe' else 'mbioe'
            ICP.set_param('logikal.use_middleware', 'true' if new_mode == 'middleware' else 'false')
            
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Integration Mode Changed'),
                    'message': _('Switched to %s integration. Please refresh the page.') % new_mode.title(),
                    'type': 'info',
                    'sticky': True,
                }
            }
            
        except Exception as e:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Mode Switch Error'),
                    'message': _('Failed to switch integration mode: %s') % str(e),
                    'type': 'danger',
                    'sticky': True,
                }
            }
