# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError
from ..services.exceptions import ConfigurationError
import time


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'
    
    # Logikal API Configuration
    mbioe_api_url = fields.Char(
        string="Logikal API URL",
        config_parameter='mbioe.api_url',
        default='https://api.example.com/api/v3',
        help='Base URL for the Logikal API (e.g., https://your-server.com/api/v3)'
    )
    
    mbioe_username = fields.Char(
        string="Logikal Username",
        config_parameter='mbioe.username',
        help='Username for Logikal API authentication'
    )
    
    mbioe_password = fields.Char(
        string="Logikal Password",
        config_parameter='mbioe.password',
        help='Password for Logikal API authentication'
    )
    
    mbioe_connection_timeout = fields.Integer(
        string="Connection Timeout (seconds)",
        config_parameter='mbioe.connection_timeout',
        default=30,
        help='Timeout for API connections in seconds'
    )
    
    mbioe_log_cleanup_days = fields.Integer(
        string="Log Cleanup Days",
        config_parameter='mbioe.log_cleanup_days',
        default=30,
        help='Number of days to keep session logs (0 = keep forever)'
    )
    
    mbioe_enable_debug_logging = fields.Boolean(
        string="Enable Debug Logging",
        config_parameter='mbioe.enable_debug_logging',
        default=False,
        help='Enable detailed debug logging for API calls'
    )
    
    # Integration Mode Selection
    use_middleware = fields.Boolean(
        string="Use Middleware Integration",
        config_parameter='logikal.use_middleware',
        default=False,
        help='Use Logikal Middleware instead of direct API connection'
    )
    
    # Middleware Configuration
    middleware_api_url = fields.Char(
        string="Middleware API URL",
        config_parameter='logikal.middleware_api_url',
        default='http://localhost:8001',
        help='Base URL for the Logikal Middleware API'
    )
    
    middleware_client_id = fields.Char(
        string="Middleware Client ID",
        config_parameter='logikal.middleware_client_id',
        help='Client ID for middleware authentication'
    )
    
    middleware_client_secret = fields.Char(
        string="Middleware Client Secret",
        config_parameter='logikal.middleware_client_secret',
        help='Client Secret for middleware authentication'
    )
    
    middleware_connection_timeout = fields.Integer(
        string="Middleware Connection Timeout (seconds)",
        config_parameter='logikal.middleware_connection_timeout',
        default=30,
        help='Timeout for middleware connections in seconds'
    )
    
    middleware_log_cleanup_days = fields.Integer(
        string="Middleware Log Cleanup Days",
        config_parameter='logikal.middleware_log_cleanup_days',
        default=30,
        help='Number of days to keep middleware session logs (0 = keep forever)'
    )
    
    @api.constrains('mbioe_api_url')
    def _check_api_url(self):
        """Validate API URL format"""
        for record in self:
            if record.mbioe_api_url:
                url = record.mbioe_api_url.strip()
                if not url.startswith(('http://', 'https://')):
                    raise UserError(_('API URL must start with http:// or https://'))
                if url.endswith('/'):
                    # Auto-fix trailing slash
                    record.mbioe_api_url = url.rstrip('/')
    
    @api.constrains('mbioe_connection_timeout')
    def _check_timeout(self):
        """Validate timeout value"""
        for record in self:
            if record.mbioe_connection_timeout < 5 or record.mbioe_connection_timeout > 300:
                raise UserError(_('Connection timeout must be between 5 and 300 seconds'))
    
    @api.constrains('mbioe_log_cleanup_days')
    def _check_log_cleanup_days(self):
        """Validate log cleanup days"""
        for record in self:
            if record.mbioe_log_cleanup_days < 0:
                raise UserError(_('Log cleanup days cannot be negative'))
    
    @api.constrains('middleware_api_url')
    def _check_middleware_api_url(self):
        """Validate middleware API URL format"""
        for record in self:
            if record.middleware_api_url:
                url = record.middleware_api_url.strip()
                if not url.startswith(('http://', 'https://')):
                    raise UserError(_('Middleware API URL must start with http:// or https://'))
                if url.endswith('/'):
                    # Auto-fix trailing slash
                    record.middleware_api_url = url.rstrip('/')
    
    @api.constrains('middleware_connection_timeout')
    def _check_middleware_timeout(self):
        """Validate middleware timeout value"""
        for record in self:
            if record.middleware_connection_timeout < 5 or record.middleware_connection_timeout > 300:
                raise UserError(_('Middleware connection timeout must be between 5 and 300 seconds'))
    
    @api.constrains('middleware_log_cleanup_days')
    def _check_middleware_log_cleanup_days(self):
        """Validate middleware log cleanup days"""
        for record in self:
            if record.middleware_log_cleanup_days < 0:
                raise UserError(_('Middleware log cleanup days cannot be negative'))
    
    def get_mbioe_config(self):
        """Get Logikal configuration values"""
        ICP = self.env['ir.config_parameter'].sudo()
        
        config = {
            'api_url': ICP.get_param('mbioe.api_url'),
            'username': ICP.get_param('mbioe.username'),
            'password': ICP.get_param('mbioe.password'),
            'connection_timeout': int(ICP.get_param('mbioe.connection_timeout', 30)),
            'log_cleanup_days': int(ICP.get_param('mbioe.log_cleanup_days', 30)),
            'enable_debug_logging': ICP.get_param('mbioe.enable_debug_logging', 'False').lower() == 'true',
        }
        
        # Validate required configuration
        if not all([config['api_url'], config['username'], config['password']]):
            raise ConfigurationError(
                "Logikal API configuration is incomplete. Please configure API URL, username, and password in Settings > General Settings > Logikal API."
            )
        
        return config
    
    def get_middleware_config(self):
        """Get middleware configuration values"""
        ICP = self.env['ir.config_parameter'].sudo()
        
        config = {
            'api_url': ICP.get_param('logikal.middleware_api_url', 'http://localhost:8001'),
            'client_id': ICP.get_param('logikal.middleware_client_id'),
            'client_secret': ICP.get_param('logikal.middleware_client_secret'),
            'connection_timeout': int(ICP.get_param('logikal.middleware_connection_timeout', 30)),
            'log_cleanup_days': int(ICP.get_param('logikal.middleware_log_cleanup_days', 30)),
            'use_middleware': ICP.get_param('logikal.use_middleware', 'False').lower() == 'true',
        }
        
        # Validate required configuration when middleware is enabled
        if config['use_middleware'] and not all([config['api_url'], config['client_id'], config['client_secret']]):
            raise ConfigurationError(
                "Middleware configuration is incomplete. Please configure API URL, Client ID, and Client Secret in Settings > General Settings > Logikal API."
            )
        
        return config
    
    def get_active_config(self):
        """Get the active configuration (MBIOE or Middleware)"""
        middleware_config = self.get_middleware_config()
        
        if middleware_config['use_middleware']:
            return {
                'type': 'middleware',
                'config': middleware_config
            }
        else:
            return {
                'type': 'mbioe',
                'config': self.get_mbioe_config()
            }
