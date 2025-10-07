# -*- coding: utf-8 -*-

import logging
from datetime import datetime, timedelta
from odoo import models, api, fields, _
from odoo.exceptions import UserError
from .middleware_client import MiddlewareClient
from .exceptions import ConfigurationError, APIConnectionError, AuthenticationError

_logger = logging.getLogger(__name__)


class LogikalService(models.AbstractModel):
    _name = 'logikal.service'
    _description = 'Logikal Service (Unified API)'
    
    @api.model
    def _get_active_client(self):
        """Get the active client based on configuration"""
        try:
            config_settings = self.env['res.config.settings']
            active_config = config_settings.get_active_config()
            
            if active_config['type'] == 'middleware':
                config = active_config['config']
                return MiddlewareClient(
                    base_url=config['api_url'],
                    client_id=config['client_id'],
                    client_secret=config['client_secret'],
                    env=self.env
                )
            else:
                # Use existing MBIOE service for backward compatibility
                return self.env['mbioe.service']
                
        except ConfigurationError as e:
            raise UserError(str(e))
        except Exception as e:
            _logger.error(f"Error creating client: {str(e)}")
            raise UserError(_("Failed to create client. Please check your configuration."))
    
    @api.model
    def _get_active_config_type(self):
        """Get the active configuration type"""
        try:
            config_settings = self.env['res.config.settings']
            active_config = config_settings.get_active_config()
            return active_config['type']
        except:
            return 'mbioe'  # Default to MBIOE if configuration fails
    
    @api.model
    def test_connection(self):
        """Test connection to the active system (middleware or MBIOE)"""
        try:
            config_type = self._get_active_config_type()
            
            if config_type == 'middleware':
                client = self._get_active_client()
                success, message = client.test_connection()
                
                if success:
                    _logger.info("Middleware connection test successful")
                    return {
                        'type': 'ir.actions.client',
                        'tag': 'display_notification',
                        'params': {
                            'title': _('Connection Test'),
                            'message': _('Middleware connection successful'),
                            'type': 'success',
                            'sticky': False,
                        }
                    }
                else:
                    _logger.warning(f"Middleware connection test failed: {message}")
                    return {
                        'type': 'ir.actions.client',
                        'tag': 'display_notification',
                        'params': {
                            'title': _('Connection Test Failed'),
                            'message': _('Error: %s') % message,
                            'type': 'danger',
                            'sticky': True,
                        }
                    }
            else:
                # Use existing MBIOE service
                mbioe_service = self.env['mbioe.service']
                return mbioe_service.test_connection()
                
        except (ConfigurationError, AuthenticationError, APIConnectionError) as e:
            _logger.error(f"Connection test failed: {str(e)}")
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Connection Test Error'),
                    'message': _('Error: %s') % str(e),
                    'type': 'danger',
                    'sticky': True,
                }
            }
        except Exception as e:
            _logger.error(f"Unexpected error during connection test: {str(e)}")
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Connection Test Error'),
                    'message': _('Unexpected error: %s') % str(e),
                    'type': 'danger',
                    'sticky': True,
                }
            }
    
    @api.model
    def get_all_projects(self):
        """Get all projects from the active system"""
        try:
            config_type = self._get_active_config_type()
            
            if config_type == 'middleware':
                client = self._get_active_client()
                return client.get_all_projects()
            else:
                # For MBIOE, we would need to implement a similar method
                # For now, return empty list and log warning
                _logger.warning("get_all_projects not implemented for MBIOE system")
                return []
                
        except Exception as e:
            _logger.error(f"Error getting projects: {str(e)}")
            raise UserError(_("Failed to get projects: %s") % str(e))
    
    @api.model
    def get_project_complete(self, project_id):
        """Get complete project data from the active system"""
        try:
            config_type = self._get_active_config_type()
            
            if config_type == 'middleware':
                client = self._get_active_client()
                return client.get_project_complete(project_id)
            else:
                # For MBIOE, we would need to implement a similar method
                _logger.warning("get_project_complete not implemented for MBIOE system")
                return None
                
        except Exception as e:
            _logger.error(f"Error getting project complete data: {str(e)}")
            raise UserError(_("Failed to get project data: %s") % str(e))
    
    @api.model
    def search_projects(self, query):
        """Search projects in the active system"""
        try:
            config_type = self._get_active_config_type()
            
            if config_type == 'middleware':
                client = self._get_active_client()
                return client.search_projects(query)
            else:
                # For MBIOE, we would need to implement a similar method
                _logger.warning("search_projects not implemented for MBIOE system")
                return []
                
        except Exception as e:
            _logger.error(f"Error searching projects: {str(e)}")
            raise UserError(_("Failed to search projects: %s") % str(e))
    
    @api.model
    def get_project_stats(self):
        """Get project statistics from the active system"""
        try:
            config_type = self._get_active_config_type()
            
            if config_type == 'middleware':
                client = self._get_active_client()
                return client.get_project_stats()
            else:
                # For MBIOE, we would need to implement a similar method
                _logger.warning("get_project_stats not implemented for MBIOE system")
                return {}
                
        except Exception as e:
            _logger.error(f"Error getting project stats: {str(e)}")
            raise UserError(_("Failed to get project statistics: %s") % str(e))
    
    @api.model
    def sync_all_projects(self):
        """Sync all projects from the active system"""
        try:
            config_type = self._get_active_config_type()
            
            if config_type == 'middleware':
                # Get all projects from middleware
                projects_data = self.get_all_projects()
                
                # Sync each project
                synced_count = 0
                error_count = 0
                
                for project_data in projects_data:
                    try:
                        self.sync_single_project(project_data['id'])
                        synced_count += 1
                    except Exception as e:
                        _logger.error(f"Error syncing project {project_data.get('id', 'unknown')}: {str(e)}")
                        error_count += 1
                
                return {
                    'type': 'ir.actions.client',
                    'tag': 'display_notification',
                    'params': {
                        'title': _('Project Sync Complete'),
                        'message': _('Synced %d projects successfully. %d errors.') % (synced_count, error_count),
                        'type': 'success' if error_count == 0 else 'warning',
                        'sticky': False,
                    }
                }
            else:
                # For MBIOE, use existing sync methods
                _logger.warning("sync_all_projects not implemented for MBIOE system")
                return {
                    'type': 'ir.actions.client',
                    'tag': 'display_notification',
                    'params': {
                        'title': _('Sync Not Available'),
                        'message': _('Project sync not available for MBIOE system.'),
                        'type': 'warning',
                        'sticky': False,
                    }
                }
                
        except Exception as e:
            _logger.error(f"Error syncing projects: {str(e)}")
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Sync Error'),
                    'message': _('Failed to sync projects: %s') % str(e),
                    'type': 'danger',
                    'sticky': True,
                }
            }
    
    @api.model
    def sync_single_project(self, project_id):
        """Sync a single project from the active system"""
        try:
            config_type = self._get_active_config_type()
            
            if config_type == 'middleware':
                # Get complete project data
                complete_data = self.get_project_complete(project_id)
                
                if not complete_data:
                    raise UserError(_("Project not found: %s") % project_id)
                
                project_data = complete_data.get('project', {})
                phases_data = complete_data.get('phases_with_elevations', [])
                
                # Find or create project
                project_model = self.env['logikal.project']
                existing_project = project_model.find_by_logikal_id(project_id)
                
                if existing_project:
                    existing_project.update_from_middleware_data(project_data)
                    project = existing_project
                else:
                    project = project_model.create_from_middleware_data(project_data)
                
                # Sync phases and elevations
                for phase_data in phases_data:
                    phase_info = phase_data.get('phase', {})
                    elevations_data = phase_data.get('elevations', [])
                    
                    # Find or create phase
                    phase_model = self.env['logikal.phase']
                    existing_phase = phase_model.find_by_logikal_id(phase_info.get('id'))
                    
                    if existing_phase:
                        existing_phase.update_from_middleware_data(phase_info)
                        phase = existing_phase
                    else:
                        phase = phase_model.create_from_middleware_data(phase_info, project.id)
                    
                    # Sync elevations
                    for elevation_data in elevations_data:
                        elevation_model = self.env['logikal.elevation']
                        existing_elevation = elevation_model.find_by_logikal_id(elevation_data.get('id'))
                        
                        if existing_elevation:
                            existing_elevation.update_from_middleware_data(elevation_data)
                        else:
                            elevation_model.create_from_middleware_data(elevation_data, phase.id)
                
                return {
                    'type': 'ir.actions.client',
                    'tag': 'display_notification',
                    'params': {
                        'title': _('Project Sync Complete'),
                        'message': _('Successfully synced project: %s') % project_data.get('name', project_id),
                        'type': 'success',
                        'sticky': False,
                    }
                }
            else:
                # For MBIOE, we would need to implement a similar method
                _logger.warning("sync_single_project not implemented for MBIOE system")
                return {
                    'type': 'ir.actions.client',
                    'tag': 'display_notification',
                    'params': {
                        'title': _('Sync Not Available'),
                        'message': _('Project sync not available for MBIOE system.'),
                        'type': 'warning',
                        'sticky': False,
                    }
                }
                
        except Exception as e:
            _logger.error(f"Error syncing project {project_id}: {str(e)}")
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Sync Error'),
                    'message': _('Failed to sync project %s: %s') % (project_id, str(e)),
                    'type': 'danger',
                    'sticky': True,
                }
            }
    
    @api.model
    def get_session_logs(self, limit=100):
        """Get recent session logs for debugging"""
        try:
            config_type = self._get_active_config_type()
            
            if config_type == 'middleware':
                logs = self.env['logikal.session.log'].search([], limit=limit, order='create_date desc')
                return logs.read([
                    'create_date', 'operation', 'status', 'response_code', 
                    'error_message', 'duration_ms', 'user_id'
                ])
            else:
                # Use existing MBIOE session logs
                mbioe_service = self.env['mbioe.service']
                return mbioe_service.get_session_logs(limit)
                
        except Exception as e:
            _logger.error(f"Error getting session logs: {str(e)}")
            return []
    
    @api.model
    def cleanup_old_logs(self):
        """Cleanup old session logs based on configuration"""
        try:
            config_settings = self.env['res.config.settings']
            active_config = config_settings.get_active_config()
            config = active_config['config']
            
            if config.get('log_cleanup_days', 0) > 0:
                if active_config['type'] == 'middleware':
                    session_log_model = self.env['logikal.session.log']
                    cleaned_count = session_log_model.cleanup_old_logs(config['log_cleanup_days'])
                else:
                    # Use existing MBIOE cleanup
                    mbioe_service = self.env['mbioe.service']
                    cleaned_count = mbioe_service.cleanup_old_logs()
                
                _logger.info(f"Cleaned up {cleaned_count} old session logs")
                return cleaned_count
            else:
                _logger.info("Log cleanup is disabled")
                return 0
                
        except Exception as e:
            _logger.error(f"Error during log cleanup: {str(e)}")
            raise
