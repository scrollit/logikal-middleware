# -*- coding: utf-8 -*-

from unittest.mock import patch
from odoo.tests.common import TransactionCase
from odoo.exceptions import UserError


class TestConfiguration(TransactionCase):
    
    def setUp(self):
        super().setUp()
        self.config_model = self.env['res.config.settings']
    
    def test_get_mbioe_config_success(self):
        """Test getting MBIOE configuration successfully"""
        # Set up configuration parameters
        self.env['ir.config_parameter'].sudo().set_param('mbioe.api_url', 'http://test.com/api/v3')
        self.env['ir.config_parameter'].sudo().set_param('mbioe.username', 'testuser')
        self.env['ir.config_parameter'].sudo().set_param('mbioe.password', 'testpass')
        self.env['ir.config_parameter'].sudo().set_param('mbioe.connection_timeout', '60')
        self.env['ir.config_parameter'].sudo().set_param('mbioe.log_cleanup_days', '7')
        self.env['ir.config_parameter'].sudo().set_param('mbioe.enable_debug_logging', 'true')
        
        config = self.config_model.get_mbioe_config()
        
        self.assertEqual(config['api_url'], 'http://test.com/api/v3')
        self.assertEqual(config['username'], 'testuser')
        self.assertEqual(config['password'], 'testpass')
        self.assertEqual(config['connection_timeout'], 60)
        self.assertEqual(config['log_cleanup_days'], 7)
        self.assertTrue(config['enable_debug_logging'])
    
    def test_get_mbioe_config_incomplete_raises_error(self):
        """Test that incomplete MBIOE configuration raises an error"""
        # Set up incomplete configuration
        self.env['ir.config_parameter'].sudo().set_param('mbioe.api_url', 'http://test.com/api/v3')
        # Missing username and password
        
        with self.assertRaises(UserError):
            self.config_model.get_mbioe_config()
    
    def test_get_middleware_config_success(self):
        """Test getting middleware configuration successfully"""
        # Set up configuration parameters
        self.env['ir.config_parameter'].sudo().set_param('logikal.middleware_api_url', 'http://localhost:8001')
        self.env['ir.config_parameter'].sudo().set_param('logikal.middleware_client_id', 'test_client')
        self.env['ir.config_parameter'].sudo().set_param('logikal.middleware_client_secret', 'test_secret')
        self.env['ir.config_parameter'].sudo().set_param('logikal.middleware_connection_timeout', '45')
        self.env['ir.config_parameter'].sudo().set_param('logikal.middleware_log_cleanup_days', '14')
        self.env['ir.config_parameter'].sudo().set_param('logikal.use_middleware', 'true')
        
        config = self.config_model.get_middleware_config()
        
        self.assertEqual(config['api_url'], 'http://localhost:8001')
        self.assertEqual(config['client_id'], 'test_client')
        self.assertEqual(config['client_secret'], 'test_secret')
        self.assertEqual(config['connection_timeout'], 45)
        self.assertEqual(config['log_cleanup_days'], 14)
        self.assertTrue(config['use_middleware'])
    
    def test_get_middleware_config_incomplete_when_enabled_raises_error(self):
        """Test that incomplete middleware configuration raises an error when middleware is enabled"""
        # Set up incomplete configuration with middleware enabled
        self.env['ir.config_parameter'].sudo().set_param('logikal.use_middleware', 'true')
        self.env['ir.config_parameter'].sudo().set_param('logikal.middleware_api_url', 'http://localhost:8001')
        # Missing client_id and client_secret
        
        with self.assertRaises(UserError):
            self.config_model.get_middleware_config()
    
    def test_get_middleware_config_incomplete_when_disabled_does_not_raise_error(self):
        """Test that incomplete middleware configuration does not raise an error when middleware is disabled"""
        # Set up incomplete configuration with middleware disabled
        self.env['ir.config_parameter'].sudo().set_param('logikal.use_middleware', 'false')
        self.env['ir.config_parameter'].sudo().set_param('logikal.middleware_api_url', 'http://localhost:8001')
        # Missing client_id and client_secret
        
        # Should not raise an error
        config = self.config_model.get_middleware_config()
        self.assertFalse(config['use_middleware'])
    
    def test_get_active_config_middleware(self):
        """Test getting active configuration when middleware is enabled"""
        # Set up middleware configuration
        self.env['ir.config_parameter'].sudo().set_param('logikal.use_middleware', 'true')
        self.env['ir.config_parameter'].sudo().set_param('logikal.middleware_api_url', 'http://localhost:8001')
        self.env['ir.config_parameter'].sudo().set_param('logikal.middleware_client_id', 'test_client')
        self.env['ir.config_parameter'].sudo().set_param('logikal.middleware_client_secret', 'test_secret')
        
        active_config = self.config_model.get_active_config()
        
        self.assertEqual(active_config['type'], 'middleware')
        self.assertEqual(active_config['config']['api_url'], 'http://localhost:8001')
        self.assertEqual(active_config['config']['client_id'], 'test_client')
    
    def test_get_active_config_mbioe(self):
        """Test getting active configuration when MBIOE is enabled"""
        # Set up MBIOE configuration
        self.env['ir.config_parameter'].sudo().set_param('logikal.use_middleware', 'false')
        self.env['ir.config_parameter'].sudo().set_param('mbioe.api_url', 'http://test.com/api/v3')
        self.env['ir.config_parameter'].sudo().set_param('mbioe.username', 'testuser')
        self.env['ir.config_parameter'].sudo().set_param('mbioe.password', 'testpass')
        
        active_config = self.config_model.get_active_config()
        
        self.assertEqual(active_config['type'], 'mbioe')
        self.assertEqual(active_config['config']['api_url'], 'http://test.com/api/v3')
        self.assertEqual(active_config['config']['username'], 'testuser')
    
    def test_config_validation_api_url(self):
        """Test API URL validation"""
        config = self.config_model.create({
            'mbioe_api_url': 'invalid-url',  # Should start with http:// or https://
        })
        
        with self.assertRaises(UserError):
            config._check_api_url()
    
    def test_config_validation_api_url_auto_fix_trailing_slash(self):
        """Test that trailing slash is automatically removed from API URL"""
        config = self.config_model.create({
            'mbioe_api_url': 'http://test.com/api/',  # Has trailing slash
        })
        
        config._check_api_url()
        self.assertEqual(config.mbioe_api_url, 'http://test.com/api')
    
    def test_config_validation_timeout_range(self):
        """Test timeout validation range"""
        # Test too low
        config = self.config_model.create({
            'mbioe_connection_timeout': 3,  # Too low (minimum 5)
        })
        
        with self.assertRaises(UserError):
            config._check_timeout()
        
        # Test too high
        config = self.config_model.create({
            'mbioe_connection_timeout': 350,  # Too high (maximum 300)
        })
        
        with self.assertRaises(UserError):
            config._check_timeout()
    
    def test_config_validation_log_cleanup_days_negative(self):
        """Test log cleanup days validation for negative values"""
        config = self.config_model.create({
            'mbioe_log_cleanup_days': -1,  # Negative value
        })
        
        with self.assertRaises(UserError):
            config._check_log_cleanup_days()
    
    def test_config_validation_middleware_api_url(self):
        """Test middleware API URL validation"""
        config = self.config_model.create({
            'middleware_api_url': 'invalid-url',  # Should start with http:// or https://
        })
        
        with self.assertRaises(UserError):
            config._check_middleware_api_url()
    
    def test_config_validation_middleware_timeout_range(self):
        """Test middleware timeout validation range"""
        # Test too low
        config = self.config_model.create({
            'middleware_connection_timeout': 3,  # Too low (minimum 5)
        })
        
        with self.assertRaises(UserError):
            config._check_middleware_timeout()
        
        # Test too high
        config = self.config_model.create({
            'middleware_connection_timeout': 350,  # Too high (maximum 300)
        })
        
        with self.assertRaises(UserError):
            config._check_middleware_timeout()
    
    def test_config_validation_middleware_log_cleanup_days_negative(self):
        """Test middleware log cleanup days validation for negative values"""
        config = self.config_model.create({
            'middleware_log_cleanup_days': -1,  # Negative value
        })
        
        with self.assertRaises(UserError):
            config._check_middleware_log_cleanup_days()
    
    def test_default_values(self):
        """Test default configuration values"""
        # Test MBIOE defaults
        self.assertEqual(self.config_model._fields['mbioe_api_url'].default, 'https://api.example.com/api/v3')
        self.assertEqual(self.config_model._fields['mbioe_connection_timeout'].default, 30)
        self.assertEqual(self.config_model._fields['mbioe_log_cleanup_days'].default, 30)
        self.assertFalse(self.config_model._fields['mbioe_enable_debug_logging'].default)
        
        # Test middleware defaults
        self.assertFalse(self.config_model._fields['use_middleware'].default)
        self.assertEqual(self.config_model._fields['middleware_api_url'].default, 'http://localhost:8001')
        self.assertEqual(self.config_model._fields['middleware_connection_timeout'].default, 30)
        self.assertEqual(self.config_model._fields['middleware_log_cleanup_days'].default, 30)
