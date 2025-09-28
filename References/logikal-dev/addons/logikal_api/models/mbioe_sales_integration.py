# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from datetime import datetime


class MbioeSalesIntegration(models.Model):
    _name = 'mbioe.sales.integration'
    _description = 'MBIOE Sales Integration Record'
    _order = 'import_date desc'
    
    name = fields.Char(
        string='Integration Name',
        required=True,
        default=lambda self: _('MBIOE Import %s') % fields.Datetime.now().strftime('%Y-%m-%d %H:%M')
    )
    
    # Core Relationships
    sales_order_id = fields.Many2one(
        'sale.order', 
        string='Sales Order',
        required=True, 
        ondelete='cascade'
    )
    
    mbioe_project_id = fields.Many2one(
        'mbioe.project', 
        string='MBIOE Project',
        required=True
    )
    
    # Import Results
    imported_phases = fields.Integer(
        string='Imported Phases',
        default=0
    )
    
    imported_elevations = fields.Integer(
        string='Imported Elevations',
        default=0
    )
    
    total_lines_created = fields.Integer(
        string='Total Lines Created',
        default=0
    )
    
    # Status and Errors
    import_state = fields.Selection([
        ('draft', 'Draft'),
        ('imported', 'Imported'),
        ('error', 'Error')
    ], string='Import State', default='draft')
    
    import_errors = fields.Text(string='Import Errors')
    
    # Timestamps
    import_date = fields.Datetime(
        string='Import Date',
        default=fields.Datetime.now
    )
    
    # Related fields for display
    project_name = fields.Char(
        related='mbioe_project_id.name',
        string='Project Name',
        readonly=True
    )
    
    order_name = fields.Char(
        related='sales_order_id.name',
        string='Sales Order',
        readonly=True
    )
    
    # Computed fields
    success_rate = fields.Float(
        compute='_compute_success_rate',
        string='Success Rate (%)',
        help='Percentage of successful imports'
    )
    
    @api.depends('imported_elevations', 'import_errors')
    def _compute_success_rate(self):
        for record in self:
            if record.imported_elevations > 0:
                errors_count = len(record.import_errors.split('\n')) if record.import_errors else 0
                total_attempted = record.imported_elevations + errors_count
                record.success_rate = (record.imported_elevations / total_attempted) * 100 if total_attempted > 0 else 0
            else:
                record.success_rate = 0.0
    
    def name_get(self):
        result = []
        for record in self:
            name = f"{record.project_name} → {record.order_name} ({record.import_date.strftime('%Y-%m-%d')})"
            result.append((record.id, name))
        return result
    
    def action_view_sales_order(self):
        """Navigate to the related sales order"""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Sales Order'),
            'res_model': 'sale.order',
            'res_id': self.sales_order_id.id,
            'view_mode': 'form',
            'target': 'current',
        }
    
    def action_view_project(self):
        """Navigate to the related MBIOE project"""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('MBIOE Project'),
            'res_model': 'mbioe.project',
            'res_id': self.mbioe_project_id.id,
            'view_mode': 'form',
            'target': 'current',
        }
