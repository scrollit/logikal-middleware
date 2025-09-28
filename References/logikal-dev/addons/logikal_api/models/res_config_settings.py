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
