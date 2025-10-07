# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError
import logging

_logger = logging.getLogger(__name__)


class MbioeSalesImportService(models.TransientModel):
    _name = 'mbioe.sales.import.service'
    _description = 'MBIOE Sales Import Service'
    
    def import_phases_to_sales_order(self, sales_order, phases):
        """Main import orchestration method"""
        try:
            # Get import configuration
            config = self.env['mbioe.import.config'].get_default_config()
            
            # Validation
            self._validate_import_prerequisites(sales_order, phases, config)
            
            # Clear existing MBIOE lines if configured
            if config.clear_existing_on_reimport and sales_order.mbioe_import_status != 'none':
                self._clear_existing_mbioe_lines(sales_order)
            
            # Track import statistics
            stats = {
                'phases_count': 0,
                'elevations_count': 0,
                'lines_created': 0,
                'errors': []
            }
            
            # Import process
            imported_lines = []
            for phase in phases.sorted('sequence'):
                try:
                    # Create phase section
                    section_line = self._create_phase_section(sales_order, phase, config)
                    imported_lines.append(section_line)
                    stats['phases_count'] += 1
                    stats['lines_created'] += 1
                    
                    # Create elevation lines under section
                    elevation_lines = self._create_elevation_lines(sales_order, phase, config)
                    imported_lines.extend(elevation_lines)
                    stats['elevations_count'] += len(elevation_lines)
                    stats['lines_created'] += len(elevation_lines)
                    
                    _logger.info(f"Successfully imported phase '{phase.name}' with {len(elevation_lines)} elevations")
                    
                except Exception as phase_error:
                    error_msg = f"Error importing phase '{phase.name}': {str(phase_error)}"
                    stats['errors'].append(error_msg)
                    _logger.error(error_msg)
            
            # Create integration record
            integration_record = self._create_integration_record(sales_order, phases[0].project_id, stats)
            
            # Update sales order import status
            self._update_import_status(sales_order, stats)
            
            # Prepare result
            result = {
                'success': True,
                'phases_count': stats['phases_count'],
                'elevations_count': stats['elevations_count'],
                'lines_created': stats['lines_created'],
                'integration_id': integration_record.id,
                'errors': stats['errors']
            }
            
            if stats['errors']:
                result['success'] = False
                result['error'] = '; '.join(stats['errors'])
            
            return result
            
        except Exception as e:
            _logger.error(f"Import failed: {str(e)}")
            return {
                'success': False,
                'error': str(e),
                'phases_count': 0,
                'elevations_count': 0,
                'lines_created': 0
            }
    
    def _validate_import_prerequisites(self, sales_order, phases, config):
        """Validate prerequisites before import"""
        errors = []
        
        # Sales order state validation
        if sales_order.state in ['done', 'cancel']:
            errors.append(_("Cannot import to confirmed or cancelled orders"))
        
        # Phase data validation
        for phase in phases:
            if not phase.elevation_ids:
                errors.append(_("Phase '%s' has no elevations to import") % phase.name)
            
            # Check for sync status
            if phase.sync_status == 'error':
                errors.append(_("Phase '%s' has sync errors") % phase.name)
        
        # Configuration validation
        if config.auto_create_products and not config.product_category_id:
            errors.append(_("Product category must be configured for auto-creation"))
        
        if errors:
            raise UserError('\n'.join(errors))
    
    def _clear_existing_mbioe_lines(self, sales_order):
        """Remove existing MBIOE imported lines"""
        mbioe_lines = sales_order.order_line.filtered('imported_from_mbioe')
        if mbioe_lines:
            _logger.info(f"Clearing {len(mbioe_lines)} existing MBIOE lines from order {sales_order.name}")
            mbioe_lines.unlink()
        
        # Reset import status
        sales_order.write({
            'mbioe_import_status': 'none',
            'mbioe_last_import': False,
            'mbioe_imported_lines_count': 0,
        })
    
    def _create_phase_section(self, sales_order, phase, config):
        """Create a section header for a phase"""
        section_name = config.format_section_name(phase)
        
        section_line = self.env['sale.order.line'].create({
            'order_id': sales_order.id,
            'sequence': self._get_next_sequence(sales_order, config),
            'display_type': 'line_section',
            'name': section_name,
            'product_id': False,
            'product_uom_qty': 0,
            'price_unit': 0.0,
            
            # MBIOE relationship
            'mbioe_phase_id': phase.id,
            'imported_from_mbioe': True,
            'mbioe_import_sequence': phase.sequence,
        })
        
        _logger.debug(f"Created phase section: {section_name}")
        return section_line
    
    def _create_elevation_lines(self, sales_order, phase, config):
        """Create product lines for elevations in a phase"""
        elevation_lines = []
        
        for elevation in phase.elevation_ids.sorted('sequence'):
            try:
                # Find or create product for elevation
                product = self._get_elevation_product(elevation, config)
                
                # Format elevation description
                description = config.format_elevation_description(elevation)
                
                # Determine price
                price = self._get_elevation_price(elevation, config)
                
                elevation_line = self.env['sale.order.line'].create({
                    'order_id': sales_order.id,
                    'sequence': self._get_next_sequence(sales_order, config),
                    'product_id': product.id,
                    'name': description,
                    'product_uom_qty': 1,
                    'price_unit': price,
                    
                    # MBIOE relationships
                    'mbioe_phase_id': phase.id,
                    'mbioe_elevation_id': elevation.id,
                    'imported_from_mbioe': True,
                    'mbioe_import_sequence': elevation.sequence,
                })
                
                elevation_lines.append(elevation_line)
                _logger.debug(f"Created elevation line: {elevation.name}")
                
            except Exception as elevation_error:
                error_msg = f"Failed to create line for elevation '{elevation.name}': {str(elevation_error)}"
                _logger.error(error_msg)
                # Continue with next elevation rather than failing entire phase
                continue
        
        return elevation_lines
    
    def _get_elevation_product(self, elevation, config):
        """Get or create product for elevation"""
        if not config.auto_create_products:
            # Use a generic product if auto-creation is disabled
            generic_product = self.env['product.product'].search([
                ('default_code', '=', 'MBIOE_ELEVATION_GENERIC')
            ], limit=1)
            
            if not generic_product:
                generic_product = self.env['product.product'].create({
                    'name': 'MBIOE Elevation (Generic)',
                    'default_code': 'MBIOE_ELEVATION_GENERIC',
                    'type': 'service',
                    'list_price': 0.0,
                })
            
            return generic_product
        
        # Auto-create product based on elevation
        product_code = config.format_product_code(elevation)
        
        # Check if product already exists
        existing_product = self.env['product.product'].search([
            ('default_code', '=', product_code)
        ], limit=1)
        
        if existing_product:
            # Build update data for existing product if needed
            update_data = {}
            
            # Update existing product with elevation thumbnail if missing
            if elevation.thumbnail and not existing_product.image_1920:
                update_data['image_1920'] = elevation.thumbnail
            
            # Update description if missing and we have elevation descriptions
            if not existing_product.description:
                product_description_parts = []
                if elevation.automatic_description:
                    product_description_parts.append(f"Description: {elevation.automatic_description}")
                if elevation.system_description:
                    product_description_parts.append(f"System: {elevation.system_description}")
                
                if product_description_parts:
                    update_data['description'] = '\n'.join(product_description_parts)
            
            # Apply updates if any
            if update_data:
                existing_product.write(update_data)
                _logger.debug(f"Updated existing product: {existing_product.name} with {list(update_data.keys())}")
            
            return existing_product
        
        # Create new product
        product_name = config.format_product_name(elevation)
        
        # Build product description from elevation descriptions
        product_description_parts = []
        if elevation.automatic_description:
            product_description_parts.append(f"Description: {elevation.automatic_description}")
        if elevation.system_description:
            product_description_parts.append(f"System: {elevation.system_description}")
        
        product_data = {
            'name': product_name,
            'default_code': product_code,
            'type': 'service',  # Default to service type
            'list_price': elevation.quotation_price or config.default_price_when_missing,
        }
        
        # Add description if we have elevation descriptions
        if product_description_parts:
            product_data['description'] = '\n'.join(product_description_parts)
        
        if config.product_category_id:
            product_data['categ_id'] = config.product_category_id.id
        
        # Transfer elevation thumbnail to product image
        if elevation.thumbnail:
            product_data['image_1920'] = elevation.thumbnail
        
        product = self.env['product.product'].create(product_data)
        if elevation.thumbnail:
            _logger.debug(f"Created product with image: {product_name} ({product_code})")
        else:
            _logger.debug(f"Created product: {product_name} ({product_code})")
        
        return product
    
    def _get_elevation_price(self, elevation, config):
        """Get price for elevation based on configuration"""
        if config.use_mbioe_pricing and elevation.quotation_price:
            return elevation.quotation_price
        return config.default_price_when_missing
    
    def _get_next_sequence(self, sales_order, config):
        """Get next sequence number for new line"""
        last_line = sales_order.order_line.search([
            ('order_id', '=', sales_order.id)
        ], order='sequence desc', limit=1)
        
        base_sequence = last_line.sequence if last_line else 0
        return base_sequence + config.import_sequence_increment
    
    def _create_integration_record(self, sales_order, project, stats):
        """Create integration record for tracking"""
        integration_data = {
            'name': f"Import: {project.name} → {sales_order.name}",
            'sales_order_id': sales_order.id,
            'mbioe_project_id': project.id,
            'imported_phases': stats['phases_count'],
            'imported_elevations': stats['elevations_count'],
            'total_lines_created': stats['lines_created'],
            'import_state': 'imported' if not stats['errors'] else 'error',
            'import_errors': '\n'.join(stats['errors']) if stats['errors'] else False,
        }
        
        return self.env['mbioe.sales.integration'].create(integration_data)
    
    def _update_import_status(self, sales_order, stats):
        """Update sales order import status"""
        if stats['errors']:
            status = 'error' if stats['phases_count'] == 0 else 'partial'
        else:
            status = 'complete'
        
        sales_order.write({
            'mbioe_import_status': status,
            'mbioe_last_import': fields.Datetime.now(),
            'mbioe_imported_lines_count': stats['lines_created'],
        })
