# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError
from datetime import datetime, timedelta


class MbioeProject(models.Model):
    _name = 'mbioe.project'
    _description = 'MBIOE Project Data (Read-Only Sync from Logikal)'
    _order = 'name'
    _rec_name = 'name'
    
    # Core project information from MBIOE API
    name = fields.Char(
        string='Project Name',
        required=True,
        readonly=True,
        help='Project name from MBIOE API'
    )
    
    identifier = fields.Char(
        string='MBIOE Identifier',
        required=True,
        readonly=True,
        index=True,
        help='Unique GUID from MBIOE API'
    )
    
    folder_id = fields.Many2one(
        'mbioe.folder',
        string='Folder',
        required=True,
        readonly=True,
        ondelete='cascade',
        help='Folder containing this project'
    )
    
    # Project metadata from MBIOE (metadata-only for POC)
    job_number = fields.Char(
        string='Job Number',
        readonly=True,
        help='Job number from MBIOE'
    )
    
    offer_number = fields.Char(
        string='Offer Number',
        readonly=True,
        help='Offer number from MBIOE'
    )
    
    person_in_charge = fields.Char(
        string='Person in Charge',
        readonly=True,
        help='Person responsible for this project'
    )
    
    estimated = fields.Boolean(
        string='Estimated',
        readonly=True,
        default=False,
        help='Whether this project has been estimated'
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
        help='When this project was last synchronized from MBIOE'
    )
    
    # Local tracking and status
    imported = fields.Boolean(
        string='Imported',
        default=False,
        readonly=True,
        help='Whether this project has been imported into Odoo'
    )
    
    synced_at = fields.Datetime(
        string='Synced At',
        default=fields.Datetime.now,
        readonly=True,
        help='When this project was last synchronized'
    )
    
    api_source = fields.Char(
        string='API Source',
        readonly=True,
        default='MBIOE',
        help='Source system for this project data'
    )
    
    sync_status = fields.Selection([
        ('new', 'New'),
        ('updated', 'Updated'),
        ('unchanged', 'Unchanged'),
        ('error', 'Sync Error'),
    ],
        string='Sync Status',
        default='new',
        readonly=True,
        help='Status of last synchronization'
    )
    
    # Relations
    phase_ids = fields.One2many(
        'mbioe.project.phase',
        'project_id',
        string='Phases',
        readonly=True,
        help='Phases within this project'
    )
    
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
    
    # Computed fields for display and search
    folder_path = fields.Char(
        string='Folder Path',
        related='folder_id.full_path',
        store=True,
        readonly=True,
        help='Full path of containing folder'
    )
    
    folder_name = fields.Char(
        string='Folder Name',
        related='folder_id.name',
        store=True,
        readonly=True,
        help='Name of containing folder'
    )
    
    days_since_sync = fields.Integer(
        string='Days Since Sync',
        compute='_compute_days_since_sync',
        search='_search_days_since_sync',
        help='Number of days since last synchronization'
    )
    
    needs_sync = fields.Boolean(
        string='Needs Sync',
        compute='_compute_needs_sync',
        search='_search_needs_sync',
        help='Whether this project needs to be synchronized'
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
    
    @api.depends('last_api_sync')
    def _compute_days_since_sync(self):
        """Compute days since last sync"""
        now = fields.Datetime.now()
        for project in self:
            if project.last_api_sync:
                delta = now - project.last_api_sync
                project.days_since_sync = delta.days
            else:
                project.days_since_sync = 999
    
    def _search_days_since_sync(self, operator, value):
        """Enable searching on days_since_sync computed field"""
        # Convert days to actual date for comparison with last_api_sync field
        # Note: Records with no last_api_sync are treated as having 999 days since sync
        
        if operator == '<=':
            # "days_since_sync <= 7" means "synced within last 7 days"
            if value >= 999:
                # Include records with no sync date
                return ['|', ('last_api_sync', '>=', datetime.now() - timedelta(days=value)), ('last_api_sync', '=', False)]
            else:
                date_threshold = datetime.now() - timedelta(days=value)
                return [('last_api_sync', '>=', date_threshold)]
        
        elif operator == '>=':
            # "days_since_sync >= 7" means "synced more than 7 days ago or never"
            if value <= 999:
                date_threshold = datetime.now() - timedelta(days=value)
                return ['|', ('last_api_sync', '<=', date_threshold), ('last_api_sync', '=', False)]
            else:
                # Only records that have never been synced
                return [('last_api_sync', '=', False)]
        
        elif operator == '<':
            # "days_since_sync < 7" means "synced within last 7 days (exclusive)"
            date_threshold = datetime.now() - timedelta(days=value)
            return [('last_api_sync', '>', date_threshold)]
        
        elif operator == '>':
            # "days_since_sync > 7" means "synced more than 7 days ago (exclusive) or never"
            if value < 999:
                date_threshold = datetime.now() - timedelta(days=value)
                return ['|', ('last_api_sync', '<', date_threshold), ('last_api_sync', '=', False)]
            else:
                # Value > 999 means no records match (since max is 999)
                return [('id', '=', -1)]  # No records match
        
        elif operator == '=':
            # "days_since_sync = 7" means "synced exactly 7 days ago"
            if value == 999:
                # Records that have never been synced
                return [('last_api_sync', '=', False)]
            else:
                date_from = datetime.now() - timedelta(days=value+1)
                date_to = datetime.now() - timedelta(days=value)
                return [('last_api_sync', '>=', date_from), ('last_api_sync', '<', date_to)]
        
        elif operator == '!=':
            # "days_since_sync != 7" means "not synced exactly 7 days ago"
            if value == 999:
                # All records except those that have never been synced
                return [('last_api_sync', '!=', False)]
            else:
                date_from = datetime.now() - timedelta(days=value+1)
                date_to = datetime.now() - timedelta(days=value)
                return ['|', ('last_api_sync', '<', date_from), ('last_api_sync', '>=', date_to)]
        
        else:
            raise NotImplementedError(f"Operator '{operator}' not implemented for days_since_sync search")
    
    @api.depends('api_changed_date', 'last_api_sync')
    def _compute_needs_sync(self):
        """Determine if project needs synchronization"""
        for project in self:
            if not project.api_changed_date or not project.last_api_sync:
                project.needs_sync = True
            else:
                project.needs_sync = project.api_changed_date > project.last_api_sync
    
    def _search_needs_sync(self, operator, value):
        """Search method for needs_sync field"""
        projects = self.search([])
        projects._compute_needs_sync()
        
        if (operator == '=' and value) or (operator == '!=' and not value):
            return [('id', 'in', projects.filtered('needs_sync').ids)]
        else:
            return [('id', 'in', projects.filtered(lambda p: not p.needs_sync).ids)]
    
    @api.model
    def create(self, vals):
        """Override create to ensure only sync operations can create projects"""
        if not self.env.context.get('from_mbioe_sync'):
            raise UserError(_(
                'Projects cannot be created manually. '
                'They are automatically synchronized from Logikal/MBIOE system.'
            ))
        return super(MbioeProject, self).create(vals)
    
    def write(self, vals):
        """Override write to prevent manual modifications"""
        # Allow only sync operations and computed field updates  
        allowed_fields = {
            'days_since_sync', 'needs_sync', 'folder_path', 'folder_name',
            'last_api_sync', 'synced_at', 'imported', 'sync_status'
        }
        manual_fields = set(vals.keys()) - allowed_fields
        
        if manual_fields and not self.env.context.get('from_mbioe_sync'):
            raise UserError(_(
                'Projects cannot be modified manually. '
                'They are automatically synchronized from Logikal/MBIOE system.'
            ))
        return super(MbioeProject, self).write(vals)
    
    def unlink(self):
        """Override unlink to prevent manual deletion"""
        if not self.env.context.get('from_mbioe_sync'):
            raise UserError(_(
                'Projects cannot be deleted manually. '
                'They are automatically managed by the synchronization process.'
            ))
        return super(MbioeProject, self).unlink()
    
    @api.model
    def find_by_identifier(self, identifier):
        """Find project by MBIOE identifier"""
        return self.search([('identifier', '=', identifier)], limit=1)
    
    @api.model
    def convert_unix_timestamp(self, timestamp):
        """Convert Unix timestamp to Odoo datetime with robust validation"""
        if not timestamp:
            return None
            
        try:
            # Convert to float if it's a string
            if isinstance(timestamp, str):
                timestamp = float(timestamp)
            
            # Check for obviously invalid values (negative, zero, or extremely large)
            if timestamp <= 0:
                return None
            
            # Handle both seconds and milliseconds timestamps
            original_timestamp = timestamp
            if timestamp > 10**10:  # Milliseconds
                timestamp = timestamp / 1000
            
            # Validate reasonable timestamp range
            # Unix epoch (1970-01-01) = 0
            # Year 2200 (Jan 1, 2200) = 7258118400 (generous upper bound)
            MIN_TIMESTAMP = 0  # 1970-01-01
            MAX_TIMESTAMP = 7258118400  # 2200-01-01 (generous upper bound)
            
            if timestamp < MIN_TIMESTAMP or timestamp > MAX_TIMESTAMP:
                return None
            
            # Additional validation: try to create datetime and check year
            result_dt = datetime.fromtimestamp(timestamp)
            
            # Final sanity check on the resulting year
            if result_dt.year < 1970 or result_dt.year > 2200:
                return None
            
            return result_dt
            
        except (ValueError, TypeError, OSError, OverflowError):
            return None
        except Exception:
            return None
    
    @api.model
    def create_from_api_data(self, api_data, folder_id):
        """Create project from MBIOE API data"""
        vals = {
            'name': api_data.get('name', 'Unnamed Project'),
            'identifier': api_data.get('id'),
            'folder_id': folder_id,
            'job_number': api_data.get('jobNumber'),
            'offer_number': api_data.get('offerNumber'),
            'person_in_charge': api_data.get('personInCharge'),
            'estimated': api_data.get('estimated', False),
            'api_created_date': self.convert_unix_timestamp(api_data.get('createdDate')),
            'api_changed_date': self.convert_unix_timestamp(api_data.get('changedDate')),
            'last_api_sync': fields.Datetime.now(),
            'synced_at': fields.Datetime.now(),
            'imported': True,
            'sync_status': 'new',
        }
        
        return self.with_context(from_mbioe_sync=True).create(vals)
    
    def update_from_api_data(self, api_data):
        """Update project from MBIOE API data"""
        vals = {
            'name': api_data.get('name', self.name),
            'job_number': api_data.get('jobNumber'),
            'offer_number': api_data.get('offerNumber'),
            'person_in_charge': api_data.get('personInCharge'),
            'estimated': api_data.get('estimated', False),
            'api_created_date': self.convert_unix_timestamp(api_data.get('createdDate')),
            'api_changed_date': self.convert_unix_timestamp(api_data.get('changedDate')),
            'last_api_sync': fields.Datetime.now(),
            'synced_at': fields.Datetime.now(),
            'sync_status': 'updated',
        }
        
        return self.with_context(from_mbioe_sync=True).write(vals)
    
    def mark_as_unchanged(self):
        """Mark project as unchanged during sync"""
        return self.with_context(from_mbioe_sync=True).write({
            'last_api_sync': fields.Datetime.now(),
            'sync_status': 'unchanged',
        })
    
    def name_get(self):
        """Custom name display with folder context"""
        result = []
        for project in self:
            if project.job_number:
                name = f"{project.name} [{project.job_number}]"
            else:
                name = project.name
            
            if project.folder_path:
                name += f" ({project.folder_path})"
            
            result.append((project.id, name))
        return result
    
    def action_view_folder(self):
        """Open the folder containing this project"""
        self.ensure_one()
        if not self.folder_id:
            return False
        
        return {
            'type': 'ir.actions.act_window',
            'name': f'Folder: {self.folder_id.name}',
            'res_model': 'mbioe.folder',
            'res_id': self.folder_id.id,
            'view_mode': 'form',
            'target': 'current',
        }
    
    def action_view_phases(self):
        """Open phases view for this project"""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': f'Phases - {self.name}',
            'res_model': 'mbioe.project.phase',
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
            'res_model': 'mbioe.project.elevation',
            'view_mode': 'list,form',
            'domain': [('project_id', '=', self.id)],
            'context': {
                'default_project_id': self.id,
            },
        }
    
    def action_sync_phases(self):
        """Sync phases for this specific project"""
        self.ensure_one()
        
        # Use the phase sync service
        phase_sync_service = self.env['mbioe.phase.sync.service']
        return phase_sync_service.sync_single_project_phases(self.id)

    def action_sync_elevations(self):
        """Sync elevations for this specific project"""
        self.ensure_one()
        
        # Use the elevation sync service
        elevation_sync_service = self.env['mbioe.elevation.sync.service']
        return elevation_sync_service.sync_elevations_for_project(self.id)