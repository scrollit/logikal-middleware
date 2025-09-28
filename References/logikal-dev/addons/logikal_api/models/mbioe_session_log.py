# -*- coding: utf-8 -*-

from odoo import models, fields, api


class MbioeSessionLog(models.Model):
    _name = 'mbioe.session.log'
    _description = 'MBIOE API Session Log'
    _order = 'create_date desc'
    _rec_name = 'operation'
    
    session_token = fields.Char(
        string='Session Token',
        required=True,
        help='Session token used for the API operation'
    )
    
    operation = fields.Selection([
        ('login', 'Login'),
        ('logout', 'Logout'),
        ('test', 'Connection Test'),
        ('api_call', 'API Call'),
    ], 
        string='Operation',
        required=True,
        index=True,  # Index for better search performance
        help='Type of operation performed'
    )
    
    status = fields.Selection([
        ('success', 'Success'),
        ('failed', 'Failed'),
        ('warning', 'Warning'),
    ],
        string='Status',
        required=True,
        index=True,  # Index for better search performance
        help='Result status of the operation'
    )
    
    response_code = fields.Integer(
        string='Response Code',
        help='HTTP response code from the API'
    )
    
    error_message = fields.Text(
        string='Error Message',
        help='Error message if the operation failed'
    )
    
    duration_ms = fields.Integer(
        string='Duration (ms)',
        help='Time taken for the operation in milliseconds'
    )
    
    request_url = fields.Char(
        string='Request URL',
        help='API endpoint that was called'
    )
    
    request_method = fields.Char(
        string='HTTP Method',
        help='HTTP method used (GET, POST, DELETE, etc.)'
    )
    
    request_payload = fields.Text(
        string='Request Payload',
        help='Request body sent to the API (passwords masked)'
    )
    
    response_body = fields.Text(
        string='Response Body',
        help='Response body received from the API'
    )
    
    response_summary = fields.Char(
        string='Response Summary',
        help='Brief summary of the response (e.g., "Found 5 directories")'
    )
    
    user_id = fields.Many2one(
        'res.users',
        string='User',
        default=lambda self: self.env.user,
        help='User who initiated the operation'
    )
    
    @api.model
    def cleanup_old_logs(self, days=30):
        """Remove session logs older than specified days"""
        from datetime import datetime, timedelta
        cutoff_date = datetime.now() - timedelta(days=days)
        domain = [
            ('create_date', '<', cutoff_date)
        ]
        # Use search_count for efficiency first
        count = self.search_count(domain)
        if count > 0:
            # Batch delete for performance with large datasets
            old_logs = self.search(domain, limit=1000)
            while old_logs:
                old_logs.unlink()
                old_logs = self.search(domain, limit=1000)
            return count
        return 0
    
    def name_get(self):
        """Custom name_get to display meaningful information"""
        result = []
        for record in self:
            name = f"{record.operation.title()} - {record.status.title()}"
            if record.create_date:
                name += f" ({record.create_date.strftime('%Y-%m-%d %H:%M')})"
            result.append((record.id, name))
        return result
