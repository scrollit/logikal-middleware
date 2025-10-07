# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from datetime import datetime, timedelta


class LogikalSessionLog(models.Model):
    _name = 'logikal.session.log'
    _description = 'Logikal Middleware Session Log'
    _order = 'create_date desc'
    _rec_name = 'operation'
    
    # Session information
    session_token = fields.Char(
        string='Session Token',
        readonly=True,
        help='Session token used for the operation'
    )
    
    operation = fields.Char(
        string='Operation',
        required=True,
        readonly=True,
        help='Type of operation performed'
    )
    
    status = fields.Selection([
        ('success', 'Success'),
        ('failed', 'Failed'),
    ],
        string='Status',
        required=True,
        readonly=True,
        help='Status of the operation'
    )
    
    response_code = fields.Integer(
        string='Response Code',
        readonly=True,
        help='HTTP response code'
    )
    
    error_message = fields.Text(
        string='Error Message',
        readonly=True,
        help='Error message if operation failed'
    )
    
    duration_ms = fields.Integer(
        string='Duration (ms)',
        readonly=True,
        help='Duration of the operation in milliseconds'
    )
    
    # Request details
    request_url = fields.Char(
        string='Request URL',
        readonly=True,
        help='URL of the request'
    )
    
    request_method = fields.Char(
        string='Request Method',
        readonly=True,
        help='HTTP method used'
    )
    
    request_payload = fields.Text(
        string='Request Payload',
        readonly=True,
        help='Request payload (sensitive data masked)'
    )
    
    # Response details
    response_body = fields.Text(
        string='Response Body',
        readonly=True,
        help='Response body (truncated if too large)'
    )
    
    response_summary = fields.Text(
        string='Response Summary',
        readonly=True,
        help='Summary of the response'
    )
    
    # User and timestamp
    user_id = fields.Many2one(
        'res.users',
        string='User',
        default=lambda self: self.env.user,
        readonly=True,
        help='User who performed the operation'
    )
    
    create_date = fields.Datetime(
        string='Created',
        default=fields.Datetime.now,
        readonly=True,
        help='When the log entry was created'
    )
    
    @api.model
    def cleanup_old_logs(self, days=30):
        """Cleanup old session logs"""
        if days <= 0:
            return 0
        
        cutoff_date = datetime.now() - timedelta(days=days)
        old_logs = self.search([('create_date', '<', cutoff_date)])
        count = len(old_logs)
        old_logs.unlink()
        
        return count
    
    @api.model
    def get_recent_logs(self, limit=50, operation=None, status=None):
        """Get recent session logs with optional filtering"""
        domain = []
        
        if operation:
            domain.append(('operation', '=', operation))
        
        if status:
            domain.append(('status', '=', status))
        
        return self.search(domain, limit=limit)
    
    @api.model
    def get_error_logs(self, limit=20):
        """Get recent error logs"""
        return self.get_recent_logs(limit=limit, status='failed')
    
    @api.model
    def get_success_rate(self, hours=24):
        """Get success rate for the specified period"""
        cutoff_date = datetime.now() - timedelta(hours=hours)
        logs = self.search([('create_date', '>=', cutoff_date)])
        
        if not logs:
            return 0
        
        success_count = len(logs.filtered(lambda log: log.status == 'success'))
        return (success_count / len(logs)) * 100
