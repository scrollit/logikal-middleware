# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError


class LogikalSyncProjectWizard(models.TransientModel):
    _name = 'logikal.sync.project.wizard'
    _description = 'Sync Single Project Wizard'
    
    project_id = fields.Many2one(
        'logikal.project',
        string='Project',
        required=True,
        help='Select the project to sync from middleware'
    )
    
    @api.model
    def default_get(self, fields_list):
        """Set default values"""
        vals = super().default_get(fields_list)
        return vals
    
    def action_sync_project(self):
        """Sync the selected project"""
        self.ensure_one()
        
        if not self.project_id:
            raise UserError(_('Please select a project to sync.'))
        
        try:
            # Use the unified service to sync the project
            logikal_service = self.env['logikal.service']
            result = logikal_service.sync_single_project(self.project_id.logikal_id)
            
            # Close the wizard
            return {
                'type': 'ir.actions.client',
                'tag': 'reload',
            }
            
        except Exception as e:
            raise UserError(_('Failed to sync project: %s') % str(e))
