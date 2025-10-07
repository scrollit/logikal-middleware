# -*- coding: utf-8 -*-

import logging
from datetime import datetime, timedelta
from odoo import models, api, fields, _
from odoo.exceptions import UserError
from .mbioe_api_client import MBIOEApiClient
from .exceptions import ConfigurationError, APIConnectionError, AuthenticationError

_logger = logging.getLogger(__name__)


class MBIOEService(models.AbstractModel):
    _name = 'mbioe.service'
    _description = 'MBIOE API Service'
    
    @api.model
    def _get_api_client(self):
        """Create configured API client instance"""
        try:
            # Get configuration from settings
            config_settings = self.env['res.config.settings']
            config = config_settings.get_mbioe_config()
            
            # Create and configure client
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
    def test_connection(self):
        """Test MBIOE API connection and return notification action"""
        try:
            client = self._get_api_client()
            success, message = client.test_connection()
            
            if success:
                _logger.info("MBIOE API connection test successful")
                return {
                    'type': 'ir.actions.client',
                    'tag': 'display_notification',
                    'params': {
                        'title': _('Connection Test'),
                        'message': _('MBIOE API connection successful'),
                        'type': 'success',
                        'sticky': False,
                    }
                }
            else:
                _logger.warning(f"MBIOE API connection test failed: {message}")
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
    def authenticate_and_get_client(self):
        """Get an authenticated API client"""
        client = self._get_api_client()
        try:
            client.authenticate()
            return client
        except (AuthenticationError, APIConnectionError) as e:
            _logger.error(f"Authentication failed: {str(e)}")
            raise UserError(_("Authentication failed: %s") % str(e))
    
    @api.model
    def get_session_logs(self, limit=100):
        """Get recent session logs for debugging"""
        logs = self.env['mbioe.session.log'].search([], limit=limit, order='create_date desc')
        return logs.read([
            'create_date', 'operation', 'status', 'response_code', 
            'error_message', 'duration_ms', 'user_id'
        ])
    
    @api.model
    def get_api_status(self):
        """Get API connection status and recent activity"""
        try:
            # Test current connection
            client = self._get_api_client()
            success, message = client.test_connection()
            
            # Get recent logs
            recent_logs = self.env['mbioe.session.log'].search([
                ('create_date', '>=', (datetime.now() - timedelta(hours=24)).strftime('%Y-%m-%d %H:%M:%S'))
            ], limit=10, order='create_date desc')
            
            # Calculate success rate
            if recent_logs:
                success_count = len(recent_logs.filtered(lambda log: log.status == 'success'))
                success_rate = (success_count / len(recent_logs)) * 100
            else:
                success_rate = 0
            
            return {
                'connection_status': 'connected' if success else 'disconnected',
                'last_test_message': message,
                'recent_activity_count': len(recent_logs),
                'success_rate_24h': success_rate,
                'recent_logs': recent_logs.read([
                    'create_date', 'operation', 'status', 'response_code', 'duration_ms'
                ])
            }
            
        except Exception as e:
            _logger.error(f"Error getting API status: {str(e)}")
            return {
                'connection_status': 'error',
                'last_test_message': str(e),
                'recent_activity_count': 0,
                'success_rate_24h': 0,
                'recent_logs': []
            }
    
    @api.model
    def test_directory_operations(self):
        """Test directory and project API operations"""
        try:
            client = self._get_api_client()
            success, message = client.test_directory_operations()
            
            if success:
                _logger.info("Directory operations test successful")
                return {
                    'type': 'ir.actions.client',
                    'tag': 'display_notification',
                    'params': {
                        'title': _('Directory Operations Test'),
                        'message': _('Directory and project operations successful: %s') % message,
                        'type': 'success',
                        'sticky': False,
                    }
                }
            else:
                _logger.warning(f"Directory operations test failed: {message}")
                return {
                    'type': 'ir.actions.client',
                    'tag': 'display_notification',
                    'params': {
                        'title': _('Directory Operations Test Failed'),
                        'message': _('Error: %s') % message,
                        'type': 'danger',
                        'sticky': True,
                    }
                }
                
        except Exception as e:
            _logger.error(f"Directory operations test error: {str(e)}")
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Directory Operations Test Error'),
                    'message': _('Unexpected error: %s') % str(e),
                    'type': 'danger',
                    'sticky': True,
                }
            }
    
    @api.model
    def sync_folders(self):
        """Initiate folder synchronization using the sync service (now runs as background job)"""
        try:
            sync_service = self.env['mbioe.sync.service']
            return sync_service.sync_folders()  # This now enqueues a job
            
        except Exception as e:
            _logger.error(f"Folder sync initiation failed: {str(e)}")
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Folder Sync Error'),
                    'message': _('Failed to start folder synchronization: %s') % str(e),
                    'type': 'danger',
                    'sticky': True,
                }
            }
    
    @api.model
    def get_sync_statistics(self):
        """Get folder synchronization statistics"""
        try:
            sync_service = self.env['mbioe.sync.service']
            return sync_service.get_sync_statistics()
        except Exception as e:
            _logger.error(f"Failed to get sync statistics: {str(e)}")
            return {}
    
    @api.model
    def get_sync_job_status(self, job_uuid=None):
        """Get status of sync jobs"""
        try:
            sync_service = self.env['mbioe.sync.service']
            return sync_service.get_sync_job_status(job_uuid)
        except Exception as e:
            _logger.error(f"Failed to get sync job status: {str(e)}")
            return None if job_uuid else []
    
    @api.model
    def cleanup_old_logs(self):
        """Cleanup old session logs based on configuration"""
        try:
            config_settings = self.env['res.config.settings']
            config = config_settings.get_mbioe_config()
            
            if config['log_cleanup_days'] > 0:
                session_log_model = self.env['mbioe.session.log']
                cleaned_count = session_log_model.cleanup_old_logs(config['log_cleanup_days'])
                _logger.info(f"Cleaned up {cleaned_count} old session logs")
                return cleaned_count
            else:
                _logger.info("Log cleanup is disabled")
                return 0
                
        except Exception as e:
            _logger.error(f"Error during log cleanup: {str(e)}")
            raise
