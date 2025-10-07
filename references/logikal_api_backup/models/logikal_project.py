# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError
from datetime import datetime


class LogikalProject(models.Model):
    _name = 'logikal.project'
    _description = 'Logikal Project (from Middleware)'
    _order = 'name'
    _rec_name = 'name'
    
    # Core project information from middleware
    name = fields.Char(
        string='Project Name',
        required=True,
        readonly=True,
        help='Project name from Logikal via middleware'
    )
    
    logikal_id = fields.Char(
        string='Logikal ID',
        required=True,
        readonly=True,
        index=True,
        help='Unique identifier from Logikal API'
    )
    
    description = fields.Text(
        string='Description',
        readonly=True,
        help='Project description from Logikal'
    )
    
    status = fields.Char(
        string='Status',
        readonly=True,
        help='Project status from Logikal'
    )
    
    # Metadata from middleware
    middleware_sync_date = fields.Datetime(
        string='Middleware Sync Date',
        readonly=True,
        help='When this project was last synced from middleware'
    )
    
    created_at = fields.Datetime(
        string='Created At',
        readonly=True,
        help='Creation date from Logikal'
    )
    
    updated_at = fields.Datetime(
        string='Updated At',
        readonly=True,
        help='Last update date from Logikal'
    )
    
    # Relations
    phase_ids = fields.One2many(
        'logikal.phase',
        'project_id',
        string='Phases',
        readonly=True,
        help='Phases within this project'
    )
    
    # Computed fields
    phase_count = fields.Integer(
        string='Phase Count',
        compute='_compute_phase_count',
        help='Number of phases in this project'
    )
    
    elevation_count = fields.Integer(
        string='Total Elevations',
        compute='_compute_elevation_count',
        help='Total number of elevations across all phases'
    )
    
    # Status fields
    is_synced = fields.Boolean(
        string='Is Synced',
        default=False,
        readonly=True,
        help='Whether this project is synced from middleware'
    )
    
    sync_status = fields.Selection([
        ('pending', 'Pending'),
        ('synced', 'Synced'),
        ('error', 'Error'),
    ],
        string='Sync Status',
        default='pending',
        readonly=True,
        help='Status of last synchronization'
    )
    
    @api.depends('phase_ids')
    def _compute_phase_count(self):
        """Compute number of phases in this project"""
        for record in self:
            record.phase_count = len(record.phase_ids)
    
    @api.depends('phase_ids.elevation_ids')
    def _compute_elevation_count(self):
        """Compute total number of elevations across all phases"""
        for record in self:
            record.elevation_count = sum(len(phase.elevation_ids) for phase in record.phase_ids)
    
    @api.model
    def create(self, vals):
        """Override create to ensure only sync operations can create projects"""
        if not self.env.context.get('from_middleware_sync'):
            raise UserError(_(
                'Projects cannot be created manually. '
                'They are automatically synchronized from Logikal middleware.'
            ))
        return super(LogikalProject, self).create(vals)
    
    def write(self, vals):
        """Override write to prevent manual modifications"""
        # Allow only sync operations and computed field updates  
        allowed_fields = {
            'phase_count', 'elevation_count', 'middleware_sync_date', 
            'is_synced', 'sync_status', 'updated_at'
        }
        manual_fields = set(vals.keys()) - allowed_fields
        
        if manual_fields and not self.env.context.get('from_middleware_sync'):
            raise UserError(_(
                'Projects cannot be modified manually. '
                'They are automatically synchronized from Logikal middleware.'
            ))
        return super(LogikalProject, self).write(vals)
    
    def unlink(self):
        """Override unlink to prevent manual deletion"""
        if not self.env.context.get('from_middleware_sync'):
            raise UserError(_(
                'Projects cannot be deleted manually. '
                'They are automatically managed by the middleware synchronization process.'
            ))
        return super(LogikalProject, self).unlink()
    
    @api.model
    def find_by_logikal_id(self, logikal_id):
        """Find project by Logikal ID"""
        return self.search([('logikal_id', '=', logikal_id)], limit=1)
    
    @api.model
    def create_from_middleware_data(self, middleware_data):
        """Create project from middleware data"""
        vals = {
            'name': middleware_data.get('name', 'Unnamed Project'),
            'logikal_id': middleware_data.get('id'),
            'description': middleware_data.get('description'),
            'status': middleware_data.get('status'),
            'middleware_sync_date': fields.Datetime.now(),
            'created_at': middleware_data.get('created_at'),
            'updated_at': middleware_data.get('updated_at'),
            'is_synced': True,
            'sync_status': 'synced',
        }
        
        return self.with_context(from_middleware_sync=True).create(vals)
    
    def update_from_middleware_data(self, middleware_data):
        """Update project from middleware data"""
        vals = {
            'name': middleware_data.get('name', self.name),
            'description': middleware_data.get('description'),
            'status': middleware_data.get('status'),
            'middleware_sync_date': fields.Datetime.now(),
            'updated_at': middleware_data.get('updated_at'),
            'sync_status': 'synced',
        }
        
        return self.with_context(from_middleware_sync=True).write(vals)
    
    def mark_sync_error(self, error_message=None):
        """Mark project as having sync error"""
        vals = {
            'sync_status': 'error',
            'middleware_sync_date': fields.Datetime.now(),
        }
        return self.with_context(from_middleware_sync=True).write(vals)
    
    def name_get(self):
        """Custom name display with status context"""
        result = []
        for project in self:
            name = project.name
            if project.status:
                name += f" [{project.status}]"
            
            result.append((project.id, name))
        return result
    
    def action_view_phases(self):
        """Open phases view for this project"""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': f'Phases - {self.name}',
            'res_model': 'logikal.phase',
            'view_mode': 'list,form',
            'domain': [('project_id', '=', self.id)],
            'context': {
                'default_project_id': self.id,
            },
        }
    
    def action_view_elevations(self):
        """Open all elevations view for this project"""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': f'All Elevations - {self.name}',
            'res_model': 'logikal.elevation',
            'view_mode': 'list,form',
            'domain': [('project_id', '=', self.id)],
            'context': {
                'default_project_id': self.id,
            },
        }
    
    def action_sync_from_middleware(self):
        """Sync this specific project from middleware"""
        self.ensure_one()
        
        # Use the logikal service to sync this project
        logikal_service = self.env['logikal.service']
        return logikal_service.sync_single_project(self.logikal_id)
    
    def action_get_complete_data(self):
        """Get complete project data from middleware"""
        self.ensure_one()
        
        # Use the logikal service to get complete data
        logikal_service = self.env['logikal.service']
        return logikal_service.get_project_complete(self.logikal_id)
