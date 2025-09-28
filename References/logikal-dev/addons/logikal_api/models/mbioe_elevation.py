# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError
from datetime import datetime
import base64
import logging

_logger = logging.getLogger(__name__)


class MbioeProjectElevation(models.Model):
    _name = 'mbioe.project.elevation'
    _description = 'MBIOE Project Elevation (Read-Only Sync from Logikal)'
    _order = 'phase_id, sequence, name'
    _rec_name = 'name'
    
    # Core elevation information from MBIOE API
    name = fields.Char(
        string='Elevation Name',
        required=True,
        readonly=True,
        help='Elevation name from MBIOE API'
    )
    
    identifier = fields.Char(
        string='MBIOE Identifier',
        required=True,
        readonly=True,
        index=True,
        help='Unique GUID from MBIOE API'
    )
    
    version_id = fields.Char(
        string='Version ID',
        readonly=True,
        help='Version identifier from MBIOE API'
    )
    
    project_id = fields.Many2one(
        'mbioe.project',
        string='Project',
        required=True,
        readonly=True,
        ondelete='cascade',
        help='Project containing this elevation'
    )
    
    phase_id = fields.Many2one(
        'mbioe.project.phase',
        string='Phase',
        required=True,
        readonly=True,
        ondelete='cascade',
        help='Phase containing this elevation'
    )
    
    # Elevation details from API
    elevation_type = fields.Char(
        string='Type',
        readonly=True,
        help='Elevation type from MBIOE API'
    )
    
    state = fields.Char(
        string='State',
        readonly=True,
        help='Current state from MBIOE API'
    )
    
    sequence = fields.Integer(
        string='Sequence',
        default=10,
        readonly=True,
        help='Display order within phase'
    )
    
    amount = fields.Float(
        string='Amount/Quantity',
        readonly=True,
        help='Amount or quantity from MBIOE API'
    )
    
    # Dimensions
    width = fields.Float(
        string='Width',
        readonly=True,
        help='Width dimension from MBIOE API'
    )
    
    height = fields.Float(
        string='Height',
        readonly=True,
        help='Height dimension from MBIOE API'
    )
    
    area = fields.Float(
        string='Area (m²)',
        compute='_compute_area',
        help='Calculated area from width and height'
    )
    
    # Descriptions from API
    automatic_description = fields.Text(
        string='Automatic Description',
        readonly=True,
        help='Auto-generated description from MBIOE'
    )
    
    system_description = fields.Text(
        string='System Description',
        readonly=True,
        help='System description from MBIOE'
    )
    
    model_description = fields.Text(
        string='Model Description',
        readonly=True,
        help='Model description from MBIOE'
    )
    
    user_description = fields.Text(
        string='User Description',
        readonly=True,
        help='User description from MBIOE'
    )
    
    created_by_user = fields.Char(
        string='Created By',
        readonly=True,
        help='User who created this elevation'
    )
    
    # Element pricelist information
    is_element_pricelist_elevation = fields.Boolean(
        string='Is Element Pricelist Elevation',
        readonly=True,
        help='Whether this is an element pricelist elevation'
    )
    
    element_pricelist_id = fields.Char(
        string='Element Pricelist ID',
        readonly=True,
        help='Element pricelist identifier from MBIOE'
    )
    
    is_in_recycle_bin = fields.Boolean(
        string='In Recycle Bin',
        readonly=True,
        help='Whether this elevation is in recycle bin'
    )
    
    # Visual assets
    thumbnail = fields.Binary(
        string='Thumbnail Image',
        readonly=True,
        help='Thumbnail image from MBIOE API'
    )
    
    thumbnail_filename = fields.Char(
        string='Thumbnail Filename',
        readonly=True,
        help='Filename for the thumbnail'
    )
    
    has_drawing = fields.Boolean(
        string='Has Technical Drawing',
        default=False,
        readonly=True,
        help='Whether technical drawing is available'
    )
    
    # Pricing information (from API)
    quotation_price = fields.Monetary(
        string='Quotation Price',
        readonly=True,
        help='Price from MBIOE quotation-price endpoint'
    )
    
    quotation_price_raw = fields.Char(
        string='Raw Quotation Price',
        readonly=True,
        help='Raw price string from API before parsing'
    )
    
    currency_id = fields.Many2one(
        'res.currency',
        string='Currency',
        readonly=True,
        help='Currency for pricing'
    )
    
    price_last_updated = fields.Datetime(
        string='Price Last Updated',
        readonly=True,
        help='When the price was last fetched from API'
    )
    
    # Parts/Components (from parts-list endpoint)
    parts_data = fields.Text(
        string='Parts List JSON',
        readonly=True,
        help='Raw parts data from API (base64 sqlite database)'
    )
    
    parts_count = fields.Integer(
        string='Parts Count',
        readonly=True,
        help='Number of parts/components'
    )
    
    has_parts_data = fields.Boolean(
        string='Has Parts Data',
        readonly=True,
        help='Whether parts list has been fetched'
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
        help='When this elevation was last synchronized from MBIOE'
    )
    
    # Local tracking and status
    imported = fields.Boolean(
        string='Imported',
        default=False,
        readonly=True,
        help='Whether this elevation has been imported into Odoo'
    )
    
    synced_at = fields.Datetime(
        string='Synced At',
        default=fields.Datetime.now,
        readonly=True,
        help='When this elevation was last synchronized'
    )
    
    api_source = fields.Char(
        string='API Source',
        readonly=True,
        default='MBIOE',
        help='Source system for this elevation data'
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
    
    # Sales Integration (for future use)
    imported_to_sale = fields.Boolean(
        string='Imported to Sales',
        default=False,
        help='Whether this elevation has been imported to sales orders'
    )
    
    # Note: sale_order_line_ids will be added when sales integration is implemented
    # and the corresponding mbioe_elevation_id field is added to sale.order.line
    
    # Computed fields for display and search
    project_name = fields.Char(
        string='Project Name',
        related='project_id.name',
        store=True,
        readonly=True,
        help='Name of containing project'
    )
    
    phase_name = fields.Char(
        string='Phase Name',
        related='phase_id.name',
        store=True,
        readonly=True,
        help='Name of containing phase'
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
        help='Whether this elevation needs to be synchronized'
    )
    
    @api.depends('width', 'height')
    def _compute_area(self):
        """Compute area from width and height (convert mm to m²)"""
        for record in self:
            if record.width and record.height:
                # Convert from mm² to m²
                area_mm2 = record.width * record.height
                record.area = area_mm2 / 1000000  # mm² to m²
            else:
                record.area = 0.0
    
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
        """Determine if elevation needs synchronization"""
        for record in self:
            if not record.api_changed_date or not record.last_api_sync:
                record.needs_sync = True
            else:
                record.needs_sync = record.api_changed_date > record.last_api_sync
    
    def _search_needs_sync(self, operator, value):
        """Search method for needs_sync computed field"""
        # Get all elevations and compute their sync status
        elevations = self.search([])
        elevations._compute_needs_sync()
        
        # Filter based on the search criteria
        if (operator == '=' and value) or (operator == '!=' and not value):
            # Looking for elevations that need sync
            matching_ids = [e.id for e in elevations if e.needs_sync]
        else:
            # Looking for elevations that don't need sync
            matching_ids = [e.id for e in elevations if not e.needs_sync]
        
        return [('id', 'in', matching_ids)]
    
    def name_get(self):
        """Return name with project and phase context"""
        result = []
        for record in self:
            name = f"{record.project_name} - {record.phase_name} - {record.name}"
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
    
    def _parse_quotation_price(self, price_string):
        """Parse quotation price string to float value"""
        if not price_string:
            return 0.0
            
        try:
            # Remove common currency symbols and separators
            cleaned_price = price_string.replace('€', '').replace('$', '').replace(',', '').strip()
            return float(cleaned_price)
        except (ValueError, TypeError):
            _logger.warning(f"Could not parse quotation price: {price_string}")
            return 0.0
    
    @api.model
    def create_from_api_data(self, api_data, project_id, phase_id, pricing_data=None, thumbnail_data=None, parts_data=None):
        """Create elevation from MBIOE API data"""
        vals = {
            'name': api_data.get('name', 'Unnamed Elevation'),
            'identifier': api_data.get('id'),
            'version_id': api_data.get('versionId'),
            'project_id': project_id,
            'phase_id': phase_id,
            'elevation_type': api_data.get('type'),
            'state': api_data.get('state'),
            'amount': api_data.get('amount', 0.0),
            'width': api_data.get('width', 0.0),
            'height': api_data.get('height', 0.0),
            'automatic_description': api_data.get('automaticDescription'),
            'system_description': api_data.get('systemDescription'),
            'model_description': api_data.get('modelDescription'),
            'user_description': api_data.get('userDescription'),
            'created_by_user': api_data.get('createdByUser'),
            'is_element_pricelist_elevation': api_data.get('isElementPricelistElevation', False),
            'element_pricelist_id': api_data.get('elementPricelistId'),
            'is_in_recycle_bin': api_data.get('isInRecycleBin', False),
            'api_created_date': self.convert_unix_timestamp(api_data.get('createdDate')),
            'api_changed_date': self.convert_unix_timestamp(api_data.get('changedDate')),
            'last_api_sync': fields.Datetime.now(),
            'synced_at': fields.Datetime.now(),
            'imported': True,
            'sync_status': 'new',
        }
        
        # Add pricing data if provided
        if pricing_data:
            price_string = pricing_data.get('quotationPrice', '')
            vals.update({
                'quotation_price_raw': price_string,
                'quotation_price': self._parse_quotation_price(price_string),
                'price_last_updated': fields.Datetime.now(),
            })
            
        # Add thumbnail if provided
        if thumbnail_data:
            vals.update({
                'thumbnail': base64.b64encode(thumbnail_data),
                'thumbnail_filename': f"{api_data.get('name', 'elevation')}_thumbnail.png",
            })
            
        # Add parts data if provided
        if parts_data:
            vals.update({
                'parts_data': base64.b64encode(parts_data).decode('utf-8'),
                'has_parts_data': True,
            })
        
        return self.with_context(from_mbioe_sync=True).create(vals)
    
    def update_from_api_data(self, api_data, pricing_data=None, thumbnail_data=None, parts_data=None):
        """Update elevation from MBIOE API data"""
        vals = {
            'name': api_data.get('name', self.name),
            'version_id': api_data.get('versionId'),
            'elevation_type': api_data.get('type'),
            'state': api_data.get('state'),
            'amount': api_data.get('amount', 0.0),
            'width': api_data.get('width', 0.0),
            'height': api_data.get('height', 0.0),
            'automatic_description': api_data.get('automaticDescription'),
            'system_description': api_data.get('systemDescription'),
            'model_description': api_data.get('modelDescription'),
            'user_description': api_data.get('userDescription'),
            'created_by_user': api_data.get('createdByUser'),
            'is_element_pricelist_elevation': api_data.get('isElementPricelistElevation', False),
            'element_pricelist_id': api_data.get('elementPricelistId'),
            'is_in_recycle_bin': api_data.get('isInRecycleBin', False),
            'api_created_date': self.convert_unix_timestamp(api_data.get('createdDate')),
            'api_changed_date': self.convert_unix_timestamp(api_data.get('changedDate')),
            'last_api_sync': fields.Datetime.now(),
            'synced_at': fields.Datetime.now(),
            'sync_status': 'updated',
        }
        
        # Update pricing data if provided
        if pricing_data:
            price_string = pricing_data.get('quotationPrice', '')
            vals.update({
                'quotation_price_raw': price_string,
                'quotation_price': self._parse_quotation_price(price_string),
                'price_last_updated': fields.Datetime.now(),
            })
            
        # Update thumbnail if provided
        if thumbnail_data:
            vals.update({
                'thumbnail': base64.b64encode(thumbnail_data),
                'thumbnail_filename': f"{api_data.get('name', 'elevation')}_thumbnail.png",
            })
            
        # Update parts data if provided
        if parts_data:
            vals.update({
                'parts_data': base64.b64encode(parts_data).decode('utf-8'),
                'has_parts_data': True,
            })
        
        return self.with_context(from_mbioe_sync=True).write(vals)
    
    def mark_as_unchanged(self):
        """Mark elevation as unchanged during sync"""
        return self.with_context(from_mbioe_sync=True).write({
            'last_api_sync': fields.Datetime.now(),
            'synced_at': fields.Datetime.now(),
            'sync_status': 'unchanged',
        })
    
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
    
    def action_view_phase(self):
        """Open the associated phase"""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Phase',
            'res_model': 'mbioe.project.phase',
            'view_mode': 'form',
            'res_id': self.phase_id.id,
        }
