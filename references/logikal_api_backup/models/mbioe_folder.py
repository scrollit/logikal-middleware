# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError


class MbioeFolder(models.Model):
    _name = 'mbioe.folder'
    _description = 'MBIOE Folder Structure (Read-Only Sync from Logikal)'
    _order = 'full_path'
    _rec_name = 'name'
    
    # Core folder information from MBIOE API
    name = fields.Char(
        string='Folder Name',
        required=True,
        readonly=True,
        help='Folder name from MBIOE API'
    )
    
    identifier = fields.Char(
        string='MBIOE Identifier',
        required=True,
        readonly=True,
        index=True,
        help='Unique GUID from MBIOE API'
    )
    
    full_path = fields.Char(
        string='Full Path',
        required=True,
        readonly=True,
        index=True,
        help='Complete folder path from root'
    )
    
    # Hierarchical relationships
    parent_id = fields.Many2one(
        'mbioe.folder',
        string='Parent Folder',
        readonly=True,
        ondelete='cascade',
        help='Parent folder in the hierarchy'
    )
    
    child_ids = fields.One2many(
        'mbioe.folder',
        'parent_id',
        string='Child Folders',
        readonly=True,
        help='Subfolders within this folder'
    )
    
    # Related projects
    project_ids = fields.One2many(
        'mbioe.project',
        'folder_id',
        string='Projects',
        readonly=True,
        help='Projects contained in this folder'
    )
    
    # Sync tracking
    synced_at = fields.Datetime(
        string='Last Synced',
        default=fields.Datetime.now,
        readonly=True,
        help='When this folder was last synchronized from MBIOE'
    )
    
    api_source = fields.Char(
        string='API Source',
        readonly=True,
        default='MBIOE',
        help='Source system for this folder data'
    )
    
    # Sync control
    exclude_from_sync = fields.Boolean(
        string='Exclude from Sync',
        default=False,
        help='When enabled, this folder and all subfolders will be skipped in sync operations'
    )
    
    # Computed fields for display
    project_count = fields.Integer(
        string='Project Count',
        compute='_compute_project_count',
        store=True,
        help='Number of projects in this folder'
    )
    
    child_count = fields.Integer(
        string='Subfolder Count',
        compute='_compute_child_count',
        store=True,
        help='Number of subfolders'
    )
    
    level = fields.Integer(
        string='Hierarchy Level',
        compute='_compute_level',
        store=True,
        help='Depth level in folder hierarchy (0 = root)'
    )
    
    sync_status_display = fields.Selection([
        ('included', 'Included in Sync'),
        ('excluded', 'Excluded from Sync')
    ], string='Sync Status', compute='_compute_sync_status_display', store=True)
    
    @api.depends('project_ids')
    def _compute_project_count(self):
        """Compute number of projects in this folder"""
        for folder in self:
            folder.project_count = len(folder.project_ids)
    
    @api.depends('child_ids')
    def _compute_child_count(self):
        """Compute number of subfolders"""
        for folder in self:
            folder.child_count = len(folder.child_ids)
    
    @api.depends('parent_id')
    def _compute_level(self):
        """Compute hierarchy level"""
        for folder in self:
            level = 0
            current = folder
            while current.parent_id:
                level += 1
                current = current.parent_id
                # Prevent infinite loops
                if level > 50:
                    break
            folder.level = level
    
    @api.depends('exclude_from_sync')
    def _compute_sync_status_display(self):
        """Compute sync status display"""
        for folder in self:
            folder.sync_status_display = 'excluded' if folder.exclude_from_sync else 'included'
    
    @api.model
    def create(self, vals):
        """Override create to ensure only sync operations can create folders"""
        # Check if this is called from sync context
        if not self.env.context.get('from_mbioe_sync'):
            raise UserError(_(
                'Folders cannot be created manually. '
                'They are automatically synchronized from Logikal/MBIOE system.'
            ))
        return super(MbioeFolder, self).create(vals)
    
    def write(self, vals):
        """Override write to prevent manual modifications"""
        # Allow only sync operations, computed field updates, and exclude_from_sync
        allowed_fields = {'project_count', 'child_count', 'level', 'synced_at', 'exclude_from_sync', 'sync_status_display'}
        manual_fields = set(vals.keys()) - allowed_fields
        
        if manual_fields and not self.env.context.get('from_mbioe_sync'):
            raise UserError(_(
                'Folders cannot be modified manually. '
                'They are automatically synchronized from Logikal/MBIOE system.'
            ))
        return super(MbioeFolder, self).write(vals)
    
    def unlink(self):
        """Override unlink to prevent manual deletion"""
        if not self.env.context.get('from_mbioe_sync'):
            raise UserError(_(
                'Folders cannot be deleted manually. '
                'They are automatically managed by the synchronization process.'
            ))
        return super(MbioeFolder, self).unlink()
    
    @api.model
    def find_by_identifier(self, identifier):
        """Find folder by MBIOE identifier"""
        return self.search([('identifier', '=', identifier)], limit=1)
    
    @api.model
    def find_by_path(self, full_path):
        """Find folder by full path"""
        return self.search([('full_path', '=', full_path)], limit=1)
    
    def get_all_projects(self):
        """Get all projects in this folder and all subfolders"""
        project_model = self.env['mbioe.project']
        
        # Get projects in this folder
        projects = self.project_ids
        
        # Recursively get projects from subfolders
        for child in self.child_ids:
            projects += child.get_all_projects()
        
        return projects
    
    def get_root_folder(self):
        """Get the root folder for this folder"""
        current = self
        while current.parent_id:
            current = current.parent_id
        return current
    
    def name_get(self):
        """Custom name display with path context"""
        result = []
        for folder in self:
            if folder.parent_id:
                name = f"{folder.name} ({folder.full_path})"
            else:
                name = f"{folder.name} (Root)"
            result.append((folder.id, name))
        return result
    
    def is_excluded_from_sync(self):
        """Check if this folder or any parent folder is excluded from sync"""
        self.ensure_one()
        current = self
        while current:
            if current.exclude_from_sync:
                return True
            current = current.parent_id
        return False
    
    def get_excluded_subfolders(self):
        """Get all excluded subfolders in this folder tree"""
        excluded = self.env['mbioe.folder']
        
        def check_children(folder):
            if folder.exclude_from_sync:
                excluded |= folder
            for child in folder.child_ids:
                check_children(child)
        
        check_children(self)
        return excluded
    
    def action_toggle_sync_exclusion(self):
        """Action to toggle sync exclusion status"""
        self.ensure_one()
        self.exclude_from_sync = not self.exclude_from_sync
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Sync Status Updated'),
                'message': _('Folder "%s" is now %s') % (
                    self.name, 
                    'excluded from sync' if self.exclude_from_sync else 'included in sync'
                ),
                'type': 'success',
                'sticky': False,
            }
        }
    
    @api.model
    def action_bulk_exclude_from_sync(self):
        """Bulk action to exclude selected folders from sync"""
        active_ids = self.env.context.get('active_ids', [])
        folders = self.browse(active_ids)
        folders.write({'exclude_from_sync': True})
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Sync Status Updated'),
                'message': _('%d folders excluded from sync') % len(folders),
                'type': 'success',
                'sticky': False,
            }
        }
    
    @api.model
    def action_bulk_include_in_sync(self):
        """Bulk action to include selected folders in sync"""
        active_ids = self.env.context.get('active_ids', [])
        folders = self.browse(active_ids)
        folders.write({'exclude_from_sync': False})
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Sync Status Updated'),
                'message': _('%d folders included in sync') % len(folders),
                'type': 'success',
                'sticky': False,
            }
        }
    
    @api.model
    def _cleanup_orphaned_folders(self):
        """Utility method to cleanup folders not updated in recent sync"""
        # This would be called during sync to remove folders that no longer exist in MBIOE
        # Implementation depends on sync strategy
        pass
