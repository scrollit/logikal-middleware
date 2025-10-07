# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError
from datetime import datetime


class MbioeProjectPhase(models.Model):
    _name = 'mbioe.project.phase'
    _description = 'MBIOE Project Phase (Read-Only Sync from Logikal)'
    _order = 'project_id, sequence, name'
    _rec_name = 'name'
    
    # Core phase information from MBIOE API
    name = fields.Char(
        string='Phase Name',
        required=True,
        readonly=True,
        help='Phase name from MBIOE API'
    )
    
    identifier = fields.Char(
        string='MBIOE Identifier',
        required=True,
        readonly=True,
        index=True,
        help='Unique GUID from MBIOE API'
    )
    
    project_id = fields.Many2one(
        'mbioe.project',
        string='Project',
        required=True,
        readonly=True,
        ondelete='cascade',
        help='Project containing this phase'
    )
    
    # Phase details from API
    description = fields.Text(
        string='Description',
        readonly=True,
        help='Phase description from MBIOE API'
    )
    
    sequence = fields.Integer(
        string='Sequence',
        default=10,
        readonly=True,
        help='Display order within project'
    )
    
    # Relations
    elevation_ids = fields.One2many(
        'mbioe.project.elevation',
        'phase_id',
        string='Elevations',
        readonly=True,
        help='Elevations within this phase'
    )
    
    elevation_count = fields.Integer(
        string='Elevation Count',
        compute='_compute_elevation_count',
        help='Number of elevations in this phase'
    )
    
    # API timestamp tracking for change detection
    api_created_date = fields.Datetime(
        string='API Created Date',
        readonly=True,
        help='Creation date from MBIOE API (Unix timestamp converted)'
    )
    
    api_changed_date = fields.Datetime(
        string='API Changed Date',
        readonly=True,
        help='Last modification date from MBIOE API (Unix timestamp converted)'
    )
    
    last_api_sync = fields.Datetime(
        string='Last API Sync',
        default=fields.Datetime.now,
        readonly=True,
        help='When this phase was last synchronized from MBIOE'
    )
    
    # Local tracking and status
    imported = fields.Boolean(
        string='Imported',
        default=False,
        readonly=True,
        help='Whether this phase has been imported into Odoo'
    )
    
    synced_at = fields.Datetime(
        string='Synced At',
        default=fields.Datetime.now,
        readonly=True,
        help='When this phase was last synchronized'
    )
    
    api_source = fields.Char(
        string='API Source',
        readonly=True,
        default='MBIOE',
        help='Source system for this phase data'
    )
    
    sync_status = fields.Selection([
        ('new', 'New'),
        ('updated', 'Updated'),
        ('unchanged', 'Unchanged'),
        ('error', 'Sync Error'),
        ('to_remove', 'To Remove'),
    ],
        string='Sync Status',
        default='new',
        readonly=True,
        help='Status of last synchronization'
    )
    
    # Computed fields for display and search
    project_name = fields.Char(
        string='Project Name',
        related='project_id.name',
        store=True,
        readonly=True,
        help='Name of containing project'
    )
    
    folder_path = fields.Char(
        string='Folder Path',
        related='project_id.folder_path',
        store=True,
        readonly=True,
        help='Full path of containing folder'
    )
    
    days_since_sync = fields.Integer(
        string='Days Since Sync',
        compute='_compute_days_since_sync',
        help='Number of days since last synchronization'
    )
    
    needs_sync = fields.Boolean(
        string='Needs Sync',
        compute='_compute_needs_sync',
        search='_search_needs_sync',
        help='Whether this phase needs to be synchronized'
    )
    
    @api.depends('elevation_ids')
    def _compute_elevation_count(self):
        """Compute number of elevations in this phase"""
        for record in self:
            record.elevation_count = len(record.elevation_ids)
    
    @api.depends('last_api_sync')
    def _compute_days_since_sync(self):
        """Compute days since last sync"""
        for record in self:
            if record.last_api_sync:
                delta = fields.Datetime.now() - record.last_api_sync
                record.days_since_sync = delta.days
            else:
                record.days_since_sync = 0
    
    @api.depends('api_changed_date', 'last_api_sync')
    def _compute_needs_sync(self):
        """Determine if phase needs synchronization"""
        for record in self:
            if not record.api_changed_date or not record.last_api_sync:
                record.needs_sync = True
            else:
                record.needs_sync = record.api_changed_date > record.last_api_sync
    
    def _search_needs_sync(self, operator, value):
        """Search method for needs_sync computed field"""
        # Get all phases and compute their sync status
        phases = self.search([])
        phases._compute_needs_sync()
        
        # Filter based on the search criteria
        if (operator == '=' and value) or (operator == '!=' and not value):
            # Looking for phases that need sync
            matching_ids = [p.id for p in phases if p.needs_sync]
        else:
            # Looking for phases that don't need sync
            matching_ids = [p.id for p in phases if not p.needs_sync]
        
        return [('id', 'in', matching_ids)]
    
    def name_get(self):
        """Return name with project context"""
        result = []
        for record in self:
            name = f"{record.project_name} - {record.name}"
            result.append((record.id, name))
        return result
    
    @api.model
    def convert_unix_timestamp(self, timestamp):
        """Convert Unix timestamp to Odoo datetime with robust validation"""
        if not timestamp:
            return None
            
        try:
            if isinstance(timestamp, str):
                timestamp = float(timestamp)
                
            if timestamp <= 0:
                return None
                
            # Handle both seconds and milliseconds
            original_timestamp = timestamp
            if timestamp > 10**10:  # Milliseconds
                timestamp = timestamp / 1000
                
            # Validate timestamp range (1970 to 2200)
            MIN_TIMESTAMP = 0  # 1970-01-01
            MAX_TIMESTAMP = 7258118400  # 2200-01-01
            
            if timestamp < MIN_TIMESTAMP or timestamp > MAX_TIMESTAMP:
                return None
                
            result_dt = datetime.fromtimestamp(timestamp)
            
            if result_dt.year < 1970 or result_dt.year > 2200:
                return None
                
            return result_dt
            
        except (ValueError, TypeError, OSError, OverflowError):
            return None
        except Exception:
            return None
    
    @api.model
    def create_from_api_data(self, api_data, project_id):
        """Create phase from MBIOE API data"""
        vals = {
            'name': api_data.get('name', 'Unnamed Phase'),
            'identifier': api_data.get('id'),
            'project_id': project_id,
            'description': api_data.get('description'),
            'api_created_date': self.convert_unix_timestamp(api_data.get('createdDate')),
            'api_changed_date': self.convert_unix_timestamp(api_data.get('changedDate')),
            'last_api_sync': fields.Datetime.now(),
            'synced_at': fields.Datetime.now(),
            'imported': True,
            'sync_status': 'new',
        }
        
        return self.with_context(from_mbioe_sync=True).create(vals)
    
    def update_from_api_data(self, api_data):
        """Update phase from MBIOE API data"""
        vals = {
            'name': api_data.get('name', self.name),
            'description': api_data.get('description'),
            'api_created_date': self.convert_unix_timestamp(api_data.get('createdDate')),
            'api_changed_date': self.convert_unix_timestamp(api_data.get('changedDate')),
            'last_api_sync': fields.Datetime.now(),
            'synced_at': fields.Datetime.now(),
            'sync_status': 'updated',
        }
        
        return self.with_context(from_mbioe_sync=True).write(vals)
    
    def mark_as_unchanged(self):
        """Mark phase as unchanged during sync"""
        return self.with_context(from_mbioe_sync=True).write({
            'last_api_sync': fields.Datetime.now(),
            'synced_at': fields.Datetime.now(),
            'sync_status': 'unchanged',
        })
    
    def action_view_elevations(self):
        """Open elevations view for this phase"""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': f'Elevations - {self.name}',
            'res_model': 'mbioe.project.elevation',
            'view_mode': 'list,form',
            'domain': [('phase_id', '=', self.id)],
            'context': {
                'default_phase_id': self.id,
                'default_project_id': self.project_id.id,
            },
        }
    
    def action_view_project(self):
        """Open the associated project"""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Project',
            'res_model': 'mbioe.project',
            'view_mode': 'form',
            'res_id': self.project_id.id,
        }
