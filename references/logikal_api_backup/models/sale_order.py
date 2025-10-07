# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError


class SaleOrder(models.Model):
    _inherit = 'sale.order'
    
    # Project Selection
    mbioe_project_id = fields.Many2one(
        'mbioe.project',
        string='MBIOE Project',
        help='Selected MBIOE project for import',
        domain=[('sync_status', '!=', 'error')]
    )
    
    # Phase Selection (Many2many for multi-selection)
    mbioe_phase_ids = fields.Many2many(
        'mbioe.project.phase',
        'sale_order_mbioe_phase_rel',
        'order_id',
        'phase_id',
        string='Selected Phases',
        help='Phases to import from the selected project'
    )
    
    # Import Status Tracking
    mbioe_import_status = fields.Selection([
        ('none', 'Not Imported'),
        ('partial', 'Partially Imported'),
        ('complete', 'Fully Imported'),
        ('error', 'Import Error')
    ], default='none', string='Import Status')
    
    # Import Metadata
    mbioe_last_import = fields.Datetime(string='Last Import Date')
    mbioe_imported_lines_count = fields.Integer(string='Imported Lines Count')
    mbioe_imported_elevations_count = fields.Integer(
        string='Imported Elevations Count',
        compute='_compute_mbioe_import_metrics',
        help='Number of elevations (products) imported from MBIOE'
    )
    
    # Computed fields
    has_mbioe_project = fields.Boolean(
        compute='_compute_mbioe_status',
        string='Has MBIOE Project'
    )
    
    available_phases_count = fields.Integer(
        compute='_compute_mbioe_status',
        string='Available Phases'
    )
    
    @api.depends('mbioe_project_id')
    def _compute_mbioe_status(self):
        for order in self:
            order.has_mbioe_project = bool(order.mbioe_project_id)
            order.available_phases_count = len(order.mbioe_project_id.phase_ids) if order.mbioe_project_id else 0
    
    @api.depends('order_line.imported_from_mbioe', 'order_line.display_type')
    def _compute_mbioe_import_metrics(self):
        """Compute import metrics including elevation count"""
        for order in self:
            mbioe_lines = order.order_line.filtered('imported_from_mbioe')
            # Count only product lines (not sections)
            elevation_lines = mbioe_lines.filtered(lambda l: not l.display_type)
            order.mbioe_imported_elevations_count = len(elevation_lines)
    
    @api.onchange('mbioe_project_id')
    def _onchange_mbioe_project_id(self):
        """Auto-select all phases when project is selected"""
        if self.mbioe_project_id:
            # Auto-select all phases by default
            self.mbioe_phase_ids = self.mbioe_project_id.phase_ids
            # Clear previous import status if project changed
            if self.mbioe_import_status != 'none':
                self.mbioe_import_status = 'none'
        else:
            self.mbioe_phase_ids = False
            self.mbioe_import_status = 'none'
    
    def action_logikal_import_wizard(self):
        """Open Logikal Import Wizard"""
        self.ensure_one()
        
        return {
            'type': 'ir.actions.act_window',
            'name': 'Logikal Import',
            'res_model': 'logikal.import.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_sale_order_id': self.id,
                'default_state': 'select',
            }
        }
    
    def action_import_mbioe_data(self):
        """Import selected MBIOE phases and elevations to sales order"""
        self.ensure_one()
        
        if not self.mbioe_project_id or not self.mbioe_phase_ids:
            raise UserError(_("Please select a project and at least one phase to import."))
        
        if self.state in ['done', 'cancel']:
            raise UserError(_("Cannot import to confirmed or cancelled orders."))
        
        # Call the import service
        import_service = self.env['mbioe.sales.import.service']
        result = import_service.import_phases_to_sales_order(self, self.mbioe_phase_ids)
        
        # Show result message
        if result['success']:
            message = _(
                "Successfully imported %(phases)d phases with %(elevations)d elevations (%(lines)d lines created)."
            ) % {
                'phases': result['phases_count'],
                'elevations': result['elevations_count'], 
                'lines': result['lines_created']
            }
            
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Import Successful'),
                    'message': message,
                    'type': 'success',
                    'sticky': False,
                }
            }
        else:
            raise UserError(_("Import failed: %s") % result['error'])
    
    def action_clear_mbioe_import(self):
        """Clear all MBIOE imported lines"""
        self.ensure_one()
        
        if self.mbioe_import_status == 'none':
            raise UserError(_("No MBIOE data to clear."))
        
        # Remove MBIOE lines
        mbioe_lines = self.order_line.filtered('imported_from_mbioe')
        if mbioe_lines:
            mbioe_lines.unlink()
        
        # Reset import status
        self.write({
            'mbioe_import_status': 'none',
            'mbioe_last_import': False,
            'mbioe_imported_lines_count': 0,
        })
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Import Cleared'),
                'message': _('All MBIOE imported lines have been removed.'),
                'type': 'info',
                'sticky': False,
            }
        }
    
    def _get_mbioe_phases_domain(self):
        """Get domain for phase selection based on selected project"""
        if self.mbioe_project_id:
            return [('project_id', '=', self.mbioe_project_id.id)]
        return [('id', '=', False)]  # Empty domain if no project selected
