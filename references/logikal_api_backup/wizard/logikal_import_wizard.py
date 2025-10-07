# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError


class LogikalImportWizard(models.TransientModel):
    _name = 'logikal.import.wizard'
    _description = 'Logikal Project Import Wizard'
    
    # Sales Order Reference
    sale_order_id = fields.Many2one(
        'sale.order',
        string='Sales Order',
        required=True,
        readonly=True,
        help='The sales order to import data into'
    )
    
    # Project Selection with enhanced display
    mbioe_project_id = fields.Many2one(
        'mbioe.project',
        string='Logikal Project',
        domain="[('sync_status', '!=', 'error')]",
        help='Select the Logikal project to import from'
    )
    
    # Project Information Display
    project_folder_path = fields.Char(
        string='Project Folder',
        related='mbioe_project_id.folder_path',
        readonly=True,
        help='Folder path of the selected project'
    )
    
    available_phases_count = fields.Integer(
        string='Available Phases',
        compute='_compute_project_info',
        help='Number of phases available in the selected project'
    )
    
    total_elevations_count = fields.Integer(
        string='Total Elevations',
        compute='_compute_project_info', 
        help='Total number of elevations across all phases'
    )
    
    # Phase Selection
    mbioe_phase_ids = fields.Many2many(
        'mbioe.project.phase',
        string='Phases to Import',
        domain="[('project_id', '=', mbioe_project_id)]",
        help='Select which phases to import. All phases are selected by default.'
    )
    
    selected_elevations_count = fields.Integer(
        string='Selected Elevations',
        compute='_compute_selected_info',
        help='Number of elevations in selected phases'
    )
    
    # Import Configuration
    clear_existing = fields.Boolean(
        string='Clear Existing Import',
        default=True,
        help='Remove previously imported Logikal lines before importing'
    )
    
    # Wizard State
    state = fields.Selection([
        ('select', 'Select Project & Phases'),
        ('confirm', 'Confirm Import'),
    ], default='select', string='Progress')
    
    @api.depends('mbioe_project_id')
    def _compute_project_info(self):
        """Compute project information"""
        for wizard in self:
            if wizard.mbioe_project_id:
                wizard.available_phases_count = len(wizard.mbioe_project_id.phase_ids)
                wizard.total_elevations_count = sum(len(phase.elevation_ids) for phase in wizard.mbioe_project_id.phase_ids)
            else:
                wizard.available_phases_count = 0
                wizard.total_elevations_count = 0
    
    @api.depends('mbioe_phase_ids')
    def _compute_selected_info(self):
        """Compute selected phases information"""
        for wizard in self:
            if wizard.mbioe_phase_ids:
                wizard.selected_elevations_count = sum(len(phase.elevation_ids) for phase in wizard.mbioe_phase_ids)
            else:
                wizard.selected_elevations_count = 0
    
    @api.onchange('mbioe_project_id')
    def _onchange_project_id(self):
        """Auto-select all phases when project is selected"""
        if self.mbioe_project_id:
            self.mbioe_phase_ids = self.mbioe_project_id.phase_ids
        else:
            self.mbioe_phase_ids = False
    
    @api.model
    def default_get(self, fields_list):
        """Set default values including current sales order"""
        res = super().default_get(fields_list)
        
        # Get sales order from context
        if 'sale_order_id' in fields_list and self.env.context.get('active_model') == 'sale.order':
            res['sale_order_id'] = self.env.context.get('active_id')
        
        return res
    
    def action_next(self):
        """Move to confirmation step"""
        self.ensure_one()
        
        # Validation
        if not self.mbioe_project_id:
            raise UserError(_("Please select a Logikal project to import."))
        
        if not self.mbioe_phase_ids:
            raise UserError(_("Please select at least one phase to import."))
        
        # Check if phases have elevations
        phases_without_elevations = self.mbioe_phase_ids.filtered(lambda p: not p.elevation_ids)
        if phases_without_elevations:
            phase_names = ', '.join(phases_without_elevations.mapped('name'))
            raise UserError(_("The following phases have no elevations to import: %s") % phase_names)
        
        # Change state and refresh wizard view
        self.state = 'confirm'
        
        return {
            'type': 'ir.actions.act_window',
            'name': 'Logikal Import - Confirm',
            'res_model': 'logikal.import.wizard',
            'res_id': self.id,
            'view_mode': 'form',
            'view_id': self.env.ref('logikal_api.view_logikal_import_wizard_form').id,
            'target': 'new',
            'context': self.env.context,
        }
    
    def action_back(self):
        """Go back to selection step"""
        self.ensure_one()
        
        # Change state and refresh wizard view
        self.state = 'select'
        
        return {
            'type': 'ir.actions.act_window',
            'name': 'Logikal Import',
            'res_model': 'logikal.import.wizard',
            'res_id': self.id,
            'view_mode': 'form',
            'view_id': self.env.ref('logikal_api.view_logikal_import_wizard_form').id,
            'target': 'new',
            'context': self.env.context,
        }
    
    def action_import(self):
        """Execute the import process"""
        self.ensure_one()
        
        # Validate sales order state
        if self.sale_order_id.state in ['done', 'cancel']:
            raise UserError(_("Cannot import to confirmed or cancelled orders."))
        
        # Use existing import service
        import_service = self.env['mbioe.sales.import.service']
        
        try:
            # Execute import with wizard parameters
            import_result = import_service.import_phases_to_sales_order(
                self.sale_order_id, 
                self.mbioe_phase_ids
            )
            
            # Check if import was successful
            if not import_result.get('success', False):
                error_msg = import_result.get('error', 'Unknown import error')
                raise UserError(_("Import failed: %s") % error_msg)
            
            # Update sales order with wizard project selection
            self.sale_order_id.write({
                'mbioe_project_id': self.mbioe_project_id.id,
                'mbioe_phase_ids': [(6, 0, self.mbioe_phase_ids.ids)],
            })
            
            # Success message using statistics from service
            elevation_count = import_result.get('elevations_count', 0)
            section_count = import_result.get('phases_count', 0)
            total_lines = import_result.get('lines_created', 0)
            
            # Create detailed success message
            success_message = _("Logikal Import Completed Successfully") + "\n\n" + \
                            _("Project: %(project)s\n") % {'project': self.mbioe_project_id.name} + \
                            _("Imported: %(elevations)d elevations in %(sections)d phases\n") % {
                                'elevations': elevation_count,
                                'sections': section_count
                            } + \
                            _("Total lines created: %(total)d") % {'total': total_lines}
            
            # Add success message to sales order chatter for persistent record
            self.sale_order_id.message_post(
                body=success_message,
                message_type='notification',
                subtype_xmlid='mail.mt_note'
            )
            
            # Ensure data is committed before closing wizard
            self.env.cr.commit()
            
            # Close wizard and refresh parent sales order form
            return {
                'type': 'ir.actions.act_window_close',
                'infos': {'reload': True}
            }
            
        except Exception as e:
            raise UserError(_("Import failed: %s") % str(e))
    
    def action_cancel(self):
        """Cancel the wizard"""
        return {'type': 'ir.actions.act_window_close'}
    
    def name_get(self):
        """Custom name display"""
        result = []
        for wizard in self:
            if wizard.mbioe_project_id:
                name = _("Import: %s") % wizard.mbioe_project_id.name
            else:
                name = _("Logikal Import")
            result.append((wizard.id, name))
        return result
