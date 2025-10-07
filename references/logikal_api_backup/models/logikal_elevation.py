# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError


class LogikalElevation(models.Model):
    _name = 'logikal.elevation'
    _description = 'Logikal Elevation (from Middleware)'
    _order = 'name'
    _rec_name = 'name'
    
    # Core elevation information from middleware
    name = fields.Char(
        string='Elevation Name',
        required=True,
        readonly=True,
        help='Elevation name from Logikal via middleware'
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
        help='Elevation description from Logikal'
    )
    
    phase_id = fields.Many2one(
        'logikal.phase',
        string='Phase',
        required=True,
        readonly=True,
        ondelete='cascade',
        help='Phase containing this elevation'
    )
    
    project_id = fields.Many2one(
        'logikal.project',
        string='Project',
        related='phase_id.project_id',
        readonly=True,
        store=True,
        help='Project containing this elevation'
    )
    
    # Physical dimensions
    width = fields.Float(
        string='Width',
        readonly=True,
        help='Width of the elevation'
    )
    
    height = fields.Float(
        string='Height',
        readonly=True,
        help='Height of the elevation'
    )
    
    depth = fields.Float(
        string='Depth',
        readonly=True,
        help='Depth of the elevation'
    )
    
    # Thumbnail and media
    thumbnail_url = fields.Char(
        string='Thumbnail URL',
        readonly=True,
        help='URL to elevation thumbnail image'
    )
    
    # Metadata from middleware
    middleware_sync_date = fields.Datetime(
        string='Middleware Sync Date',
        readonly=True,
        help='When this elevation was last synced from middleware'
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
    
    # Status fields
    is_synced = fields.Boolean(
        string='Is Synced',
        default=False,
        readonly=True,
        help='Whether this elevation is synced from middleware'
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
    
    @api.model
    def create(self, vals):
        """Override create to ensure only sync operations can create elevations"""
        if not self.env.context.get('from_middleware_sync'):
            raise UserError(_(
                'Elevations cannot be created manually. '
                'They are automatically synchronized from Logikal middleware.'
            ))
        return super(LogikalElevation, self).create(vals)
    
    def write(self, vals):
        """Override write to prevent manual modifications"""
        # Allow only sync operations and computed field updates  
        allowed_fields = {
            'middleware_sync_date', 'is_synced', 'sync_status', 'updated_at'
        }
        manual_fields = set(vals.keys()) - allowed_fields
        
        if manual_fields and not self.env.context.get('from_middleware_sync'):
            raise UserError(_(
                'Elevations cannot be modified manually. '
                'They are automatically synchronized from Logikal middleware.'
            ))
        return super(LogikalElevation, self).write(vals)
    
    def unlink(self):
        """Override unlink to prevent manual deletion"""
        if not self.env.context.get('from_middleware_sync'):
            raise UserError(_(
                'Elevations cannot be deleted manually. '
                'They are automatically managed by the middleware synchronization process.'
            ))
        return super(LogikalElevation, self).unlink()
    
    @api.model
    def find_by_logikal_id(self, logikal_id):
        """Find elevation by Logikal ID"""
        return self.search([('logikal_id', '=', logikal_id)], limit=1)
    
    @api.model
    def create_from_middleware_data(self, middleware_data, phase_id):
        """Create elevation from middleware data"""
        # Get project_id from phase
        phase = self.env['logikal.phase'].browse(phase_id)
        
        vals = {
            'name': middleware_data.get('name', 'Unnamed Elevation'),
            'logikal_id': middleware_data.get('id'),
            'description': middleware_data.get('description'),
            'phase_id': phase_id,
            'project_id': phase.project_id.id if phase.project_id else False,
            'width': middleware_data.get('width', 0.0),
            'height': middleware_data.get('height', 0.0),
            'depth': middleware_data.get('depth', 0.0),
            'thumbnail_url': middleware_data.get('thumbnail_url'),
            'middleware_sync_date': fields.Datetime.now(),
            'created_at': middleware_data.get('created_at'),
            'updated_at': middleware_data.get('updated_at'),
            'is_synced': True,
            'sync_status': 'synced',
        }
        
        return self.with_context(from_middleware_sync=True).create(vals)
    
    def update_from_middleware_data(self, middleware_data):
        """Update elevation from middleware data"""
        vals = {
            'name': middleware_data.get('name', self.name),
            'description': middleware_data.get('description'),
            'width': middleware_data.get('width', self.width),
            'height': middleware_data.get('height', self.height),
            'depth': middleware_data.get('depth', self.depth),
            'thumbnail_url': middleware_data.get('thumbnail_url'),
            'middleware_sync_date': fields.Datetime.now(),
            'updated_at': middleware_data.get('updated_at'),
            'sync_status': 'synced',
        }
        
        return self.with_context(from_middleware_sync=True).write(vals)
    
    def mark_sync_error(self, error_message=None):
        """Mark elevation as having sync error"""
        vals = {
            'sync_status': 'error',
            'middleware_sync_date': fields.Datetime.now(),
        }
        return self.with_context(from_middleware_sync=True).write(vals)
    
    def name_get(self):
        """Custom name display with phase and project context"""
        result = []
        for elevation in self:
            name = elevation.name
            if elevation.phase_id and elevation.phase_id.project_id:
                name += f" ({elevation.phase_id.project_id.name} - {elevation.phase_id.name})"
            
            result.append((elevation.id, name))
        return result
    
    def action_view_thumbnail(self):
        """Open thumbnail in new window"""
        self.ensure_one()
        if not self.thumbnail_url:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('No Thumbnail'),
                    'message': _('No thumbnail available for this elevation.'),
                    'type': 'warning',
                    'sticky': False,
                }
            }
        
        return {
            'type': 'ir.actions.act_url',
            'url': self.thumbnail_url,
            'target': 'new',
        }
