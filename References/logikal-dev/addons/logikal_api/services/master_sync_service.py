# -*- coding: utf-8 -*-

from odoo import models, api, fields, _
from odoo.exceptions import UserError
import time


class MbioeMasterSyncService(models.AbstractModel):
    _name = 'mbioe.master.sync.service'
    _description = 'Master Sync Orchestration Service'
    
    @api.model
    def create_phase_sync(self, name="Phase Sync"):
        """Create a new phase sync orchestration"""
        master_sync = self.env['mbioe.master.sync'].create({
            'name': name,
            'sync_type': 'phases',
            'state': 'draft'
        })
        
        return {
            'type': 'ir.actions.act_window',
            'name': 'Phase Sync',
            'res_model': 'mbioe.master.sync',
            'view_mode': 'form',
            'res_id': master_sync.id,
            'target': 'current',
        }
    
    @api.model
    def create_project_sync(self, name="Project Sync"):
        """Create a new project sync orchestration"""
        master_sync = self.env['mbioe.master.sync'].create({
            'name': name,
            'sync_type': 'projects',
            'state': 'draft'
        })
        
        return {
            'type': 'ir.actions.act_window',
            'name': 'Project Sync',
            'res_model': 'mbioe.master.sync',
            'view_mode': 'form',
            'res_id': master_sync.id,
            'target': 'current',
        }
    
    @api.model
    def get_sync_status(self):
        """Get overall sync status for dashboard"""
        master_syncs = self.env['mbioe.master.sync'].search([])
        
        total_syncs = len(master_syncs)
        running_syncs = len(master_syncs.filtered(lambda s: s.state == 'running'))
        completed_syncs = len(master_syncs.filtered(lambda s: s.state == 'completed'))
        failed_syncs = len(master_syncs.filtered(lambda s: s.state == 'failed'))
        
        return {
            'total_syncs': total_syncs,
            'running_syncs': running_syncs,
            'completed_syncs': completed_syncs,
            'failed_syncs': failed_syncs,
            'recent_syncs': master_syncs[:5]  # Last 5 syncs
        }
