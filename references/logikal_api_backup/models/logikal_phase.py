# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError


class LogikalPhase(models.Model):
    _name = 'logikal.phase'
    _description = 'Logikal Phase (from Middleware)'
    _order = 'name'
    _rec_name = 'name'
    
    # Core phase information from middleware
    name = fields.Char(
        string='Phase Name',
        required=True,
        readonly=True,
        help='Phase name from Logikal via middleware'
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
        help='Phase description from Logikal'
    )
    
    project_id = fields.Many2one(
        'logikal.project',
        string='Project',
        required=True,
        readonly=True,
        ondelete='cascade',
        help='Project containing this phase'
    )
    
    status = fields.Char(
        string='Status',
        readonly=True,
        help='Phase status from Logikal'
    )
    
    # Metadata from middleware
    middleware_sync_date = fields.Datetime(
        string='Middleware Sync Date',
        readonly=True,
        help='When this phase was last synced from middleware'
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
    elevation_ids = fields.One2many(
        'logikal.elevation',
        'phase_id',
        string='Elevations',
        readonly=True,
        help='Elevations within this phase'
    )
    
    # Computed fields
    elevation_count = fields.Integer(
        string='Elevation Count',
        compute='_compute_elevation_count',
        help='Number of elevations in this phase'
    )
    
    # Status fields
    is_synced = fields.Boolean(
        string='Is Synced',
        default=False,
        readonly=True,
        help='Whether this phase is synced from middleware'
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
    
    @api.depends('elevation_ids')
    def _compute_elevation_count(self):
        """Compute number of elevations in this phase"""
        for record in self:
            record.elevation_count = len(record.elevation_ids)
    
    @api.model
    def create(self, vals):
        """Override create to ensure only sync operations can create phases"""
        if not self.env.context.get('from_middleware_sync'):
            raise UserError(_(
                'Phases cannot be created manually. '
                'They are automatically synchronized from Logikal middleware.'
            ))
        return super(LogikalPhase, self).create(vals)
    
    def write(self, vals):
        """Override write to prevent manual modifications"""
        # Allow only sync operations and computed field updates  
        allowed_fields = {
            'elevation_count', 'middleware_sync_date', 
            'is_synced', 'sync_status', 'updated_at'
        }
        manual_fields = set(vals.keys()) - allowed_fields
        
        if manual_fields and not self.env.context.get('from_middleware_sync'):
            raise UserError(_(
                'Phases cannot be modified manually. '
                'They are automatically synchronized from Logikal middleware.'
            ))
        return super(LogikalPhase, self).write(vals)
    
    def unlink(self):
        """Override unlink to prevent manual deletion"""
        if not self.env.context.get('from_middleware_sync'):
            raise UserError(_(
                'Phases cannot be deleted manually. '
                'They are automatically managed by the middleware synchronization process.'
            ))
        return super(LogikalPhase, self).unlink()
    
    @api.model
    def find_by_logikal_id(self, logikal_id):
        """Find phase by Logikal ID"""
        return self.search([('logikal_id', '=', logikal_id)], limit=1)
    
    @api.model
    def create_from_middleware_data(self, middleware_data, project_id):
        """Create phase from middleware data"""
        vals = {
            'name': middleware_data.get('name', 'Unnamed Phase'),
            'logikal_id': middleware_data.get('id'),
            'description': middleware_data.get('description'),
            'project_id': project_id,
            'status': middleware_data.get('status'),
            'middleware_sync_date': fields.Datetime.now(),
            'created_at': middleware_data.get('created_at'),
            'updated_at': middleware_data.get('updated_at'),
            'is_synced': True,
            'sync_status': 'synced',
        }
        
        return self.with_context(from_middleware_sync=True).create(vals)
    
    def update_from_middleware_data(self, middleware_data):
        """Update phase from middleware data"""
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
        """Mark phase as having sync error"""
        vals = {
            'sync_status': 'error',
            'middleware_sync_date': fields.Datetime.now(),
        }
        return self.with_context(from_middleware_sync=True).write(vals)
    
    def name_get(self):
        """Custom name display with project context"""
        result = []
        for phase in self:
            name = phase.name
            if phase.project_id:
                name += f" ({phase.project_id.name})"
            
            result.append((phase.id, name))
        return result
    
    def action_view_elevations(self):
        """Open elevations view for this phase"""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': f'Elevations - {self.name}',
            'res_model': 'logikal.elevation',
            'view_mode': 'list,form',
            'domain': [('phase_id', '=', self.id)],
            'context': {
                'default_phase_id': self.id,
                'default_project_id': self.project_id.id,
            },
        }
