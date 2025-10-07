# -*- coding: utf-8 -*-

from odoo import models, fields, api


class MbioeImportConfig(models.Model):
    _name = 'mbioe.import.config'
    _description = 'MBIOE Import Configuration'
    _rec_name = 'name'
    
    name = fields.Char(
        string='Configuration Name',
        required=True,
        default='Default MBIOE Import Configuration'
    )
    
    active = fields.Boolean(
        string='Active',
        default=True
    )
    
    # Product creation settings
    auto_create_products = fields.Boolean(
        string='Auto-create Products',
        default=True,
        help='Automatically create products for elevations if they do not exist'
    )
    
    product_category_id = fields.Many2one(
        'product.category',
        string='Default Product Category',
        help='Default category for auto-created elevation products'
    )
    
    product_name_template = fields.Char(
        string='Product Name Template',
        default='Elevation - {elevation_name}',
        help='Template for auto-created product names. Available variables: {elevation_type}, {elevation_name}, {project_name}'
    )
    
    product_code_template = fields.Char(
        string='Product Code Template', 
        default='ELEV_{project_name}_{identifier}',
        help='Template for auto-created product codes. Available variables: {elevation_type}, {elevation_name}, {project_name}, {identifier}'
    )
    
    # Pricing settings
    use_mbioe_pricing = fields.Boolean(
        string='Use MBIOE Quotation Prices',
        default=True,
        help='Use quotation prices from MBIOE elevations when available'
    )
    
    default_price_when_missing = fields.Float(
        string='Default Price When Missing',
        default=0.0,
        help='Default price to use when MBIOE quotation price is not available'
    )
    
    # Import behavior
    clear_existing_on_reimport = fields.Boolean(
        string='Clear Existing MBIOE Lines on Re-import',
        default=True,
        help='Automatically clear existing MBIOE lines when importing again'
    )
    
    section_name_template = fields.Char(
        string='Section Name Template',
        default='Phase: {phase_name}',
        help='Template for phase section names. Available variables: {phase_name}, {sequence}'
    )
    
    elevation_description_template = fields.Text(
        string='Elevation Description Template',
        default='{elevation_name}\n{system_description}\n\n{automatic_description}\nDimensions: {width}mm x {height}mm',
        help='Template for elevation line descriptions. Available variables: {elevation_name}, {elevation_type}, {project_name}, {width}, {height}, {area}, {automatic_description}, {system_description}'
    )
    
    # Advanced settings
    import_sequence_increment = fields.Integer(
        string='Sequence Increment',
        default=10,
        help='Increment value for line sequences during import'
    )
    
    @api.model
    def get_default_config(self):
        """Get the default active configuration"""
        config = self.search([('active', '=', True)], limit=1)
        if not config:
            # Create default configuration if none exists
            config = self.create({
                'name': 'Default MBIOE Import Configuration',
                'active': True,
            })
        return config
    
    def format_product_name(self, elevation):
        """Format product name using template and elevation data"""
        return self.product_name_template.format(
            elevation_type=elevation.elevation_type or 'Unknown',
            elevation_name=elevation.name or 'Unnamed',
            project_name=elevation.project_name or 'Unknown Project'
        )
    
    def format_product_code(self, elevation):
        """Format product code using template and elevation data"""
        # Format project name for use in product code
        project_name = elevation.project_name or 'NOPROJECT'
        project_name_formatted = project_name.replace(' ', '_').replace('-', '_').upper()[:12]
        
        return self.product_code_template.format(
            elevation_type=(elevation.elevation_type or 'UNK').replace(' ', '_').upper(),
            elevation_name=(elevation.name or 'UNNAMED').replace(' ', '_').upper(),
            project_name=project_name_formatted,
            identifier=elevation.identifier[:8].upper() if elevation.identifier else 'NOID'
        )
    
    def format_section_name(self, phase):
        """Format section name using template and phase data"""
        return self.section_name_template.format(
            phase_name=phase.name or 'Unnamed Phase',
            sequence=phase.sequence or 0
        )
    
    def format_elevation_description(self, elevation):
        """Format elevation description using template and elevation data"""
        # Format additional descriptions - these are now used directly in template
        automatic_desc = f"Description:\n{elevation.automatic_description}" if elevation.automatic_description else ""
        system_desc = elevation.system_description or ""
        
        return self.elevation_description_template.format(
            elevation_name=elevation.name or 'Unnamed Elevation',
            elevation_type=elevation.elevation_type or 'Unknown Type',
            project_name=elevation.project_name or 'Unknown Project',
            width=elevation.width or 0,
            height=elevation.height or 0,
            area=elevation.area or 0.0,
            automatic_description=automatic_desc,
            system_description=system_desc
        )
