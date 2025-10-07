# -*- coding: utf-8 -*-

from odoo import models, fields, api


class SaleOrderLine(models.Model):
    _inherit = 'sale.order.line'
    
    # MBIOE Relationship Tracking
    mbioe_phase_id = fields.Many2one(
        'mbioe.project.phase',
        string='MBIOE Phase',
        help='Associated MBIOE phase (for sections and elevations)',
        index=True
    )
    
    mbioe_elevation_id = fields.Many2one(
        'mbioe.project.elevation',
        string='MBIOE Elevation', 
        help='Associated MBIOE elevation (for product lines only)',
        index=True
    )
    
    # Import Source Tracking
    imported_from_mbioe = fields.Boolean(
        default=False,
        string='Imported from MBIOE',
        help='Indicates this line was imported from MBIOE',
        index=True
    )
    
    mbioe_import_sequence = fields.Integer(
        string='Import Sequence',
        help='Original sequence from MBIOE import'
    )
    
    # Product image for easy identification in sales order lines
    product_image_256 = fields.Binary(
        string='Product Image',
        compute='_compute_product_image',
        help='Product thumbnail for visual identification'
    )
    
    @api.depends('product_id.image_256')
    def _compute_product_image(self):
        """Compute product image from product"""
        for line in self:
            if line.product_id:
                line.product_image_256 = line.product_id.image_256
            else:
                line.product_image_256 = False
    
    # Computed fields for display
    mbioe_line_type = fields.Selection([
        ('section', 'Phase Section'),
        ('elevation', 'Elevation Line'),
        ('regular', 'Regular Line')
    ], compute='_compute_mbioe_line_type', string='MBIOE Line Type')
    
    @api.depends('display_type', 'mbioe_phase_id', 'mbioe_elevation_id', 'imported_from_mbioe')
    def _compute_mbioe_line_type(self):
        for line in self:
            if not line.imported_from_mbioe:
                line.mbioe_line_type = 'regular'
            elif line.display_type == 'line_section' and line.mbioe_phase_id:
                line.mbioe_line_type = 'section'
            elif line.mbioe_elevation_id:
                line.mbioe_line_type = 'elevation'
            else:
                line.mbioe_line_type = 'regular'
    
    def name_get(self):
        """Enhanced name_get to show MBIOE context"""
        result = super().name_get()
        
        # Create a mapping for easier lookup
        name_dict = {line_id: name for line_id, name in result}
        
        for line in self:
            if line.imported_from_mbioe and line.id in name_dict:
                if line.mbioe_line_type == 'section':
                    name_dict[line.id] = f"📁 {name_dict[line.id]}"
                elif line.mbioe_line_type == 'elevation':
                    name_dict[line.id] = f"🏗️ {name_dict[line.id]}"
        
        return [(line_id, name_dict[line_id]) for line_id, _ in result]
