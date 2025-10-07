# -*- coding: utf-8 -*-

from unittest.mock import Mock, patch, MagicMock
from odoo.tests.common import TransactionCase
from odoo.exceptions import UserError


class TestLogikalService(TransactionCase):
    
    def setUp(self):
        super().setUp()
        self.service = self.env['logikal.service']
    
    def test_get_active_config_type_middleware(self):
        """Test getting active config type when middleware is enabled"""
        # Mock configuration to use middleware
        with patch.object(self.env['res.config.settings'], 'get_active_config') as mock_config:
            mock_config.return_value = {'type': 'middleware', 'config': {}}
            
            result = self.service._get_active_config_type()
            self.assertEqual(result, 'middleware')
    
    def test_get_active_config_type_mbioe(self):
        """Test getting active config type when MBIOE is enabled"""
        # Mock configuration to use MBIOE
        with patch.object(self.env['res.config.settings'], 'get_active_config') as mock_config:
            mock_config.return_value = {'type': 'mbioe', 'config': {}}
            
            result = self.service._get_active_config_type()
            self.assertEqual(result, 'mbioe')
    
    def test_test_connection_middleware_success(self):
        """Test connection test with middleware (success)"""
        # Mock middleware configuration
        with patch.object(self.service, '_get_active_config_type', return_value='middleware'):
            with patch.object(self.service, '_get_active_client') as mock_client:
                mock_client_instance = Mock()
                mock_client_instance.test_connection.return_value = (True, 'Success')
                mock_client.return_value = mock_client_instance
                
                result = self.service.test_connection()
                
                self.assertIsInstance(result, dict)
                self.assertEqual(result['params']['type'], 'success')
    
    def test_test_connection_middleware_failure(self):
        """Test connection test with middleware (failure)"""
        # Mock middleware configuration
        with patch.object(self.service, '_get_active_config_type', return_value='middleware'):
            with patch.object(self.service, '_get_active_client') as mock_client:
                mock_client_instance = Mock()
                mock_client_instance.test_connection.return_value = (False, 'Connection failed')
                mock_client.return_value = mock_client_instance
                
                result = self.service.test_connection()
                
                self.assertIsInstance(result, dict)
                self.assertEqual(result['params']['type'], 'danger')
    
    def test_get_all_projects_middleware(self):
        """Test getting all projects via middleware"""
        # Mock middleware configuration
        with patch.object(self.service, '_get_active_config_type', return_value='middleware'):
            with patch.object(self.service, '_get_active_client') as mock_client:
                mock_client_instance = Mock()
                mock_client_instance.get_all_projects.return_value = [
                    {'id': 'proj1', 'name': 'Project 1'}
                ]
                mock_client.return_value = mock_client_instance
                
                result = self.service.get_all_projects()
                
                self.assertEqual(len(result), 1)
                self.assertEqual(result[0]['name'], 'Project 1')
    
    def test_sync_single_project_middleware_success(self):
        """Test syncing single project via middleware (success)"""
        # Mock middleware configuration
        with patch.object(self.service, '_get_active_config_type', return_value='middleware'):
            with patch.object(self.service, 'get_project_complete') as mock_get_complete:
                mock_get_complete.return_value = {
                    'project': {'id': 'proj1', 'name': 'Project 1'},
                    'phases_with_elevations': []
                }
                
                # Mock project model
                with patch.object(self.env['logikal.project'], 'find_by_logikal_id') as mock_find:
                    mock_find.return_value = False  # Project doesn't exist
                    
                    with patch.object(self.env['logikal.project'], 'create_from_middleware_data') as mock_create:
                        mock_project = Mock()
                        mock_create.return_value = mock_project
                        
                        result = self.service.sync_single_project('proj1')
                        
                        self.assertIsInstance(result, dict)
                        self.assertEqual(result['params']['type'], 'success')
    
    def test_sync_single_project_middleware_update_existing(self):
        """Test syncing single project via middleware (update existing)"""
        # Mock middleware configuration
        with patch.object(self.service, '_get_active_config_type', return_value='middleware'):
            with patch.object(self.service, 'get_project_complete') as mock_get_complete:
                mock_get_complete.return_value = {
                    'project': {'id': 'proj1', 'name': 'Project 1 Updated'},
                    'phases_with_elevations': []
                }
                
                # Mock existing project
                mock_existing_project = Mock()
                
                with patch.object(self.env['logikal.project'], 'find_by_logikal_id') as mock_find:
                    mock_find.return_value = mock_existing_project
                    
                    with patch.object(mock_existing_project, 'update_from_middleware_data') as mock_update:
                        result = self.service.sync_single_project('proj1')
                        
                        mock_update.assert_called_once()
                        self.assertIsInstance(result, dict)
                        self.assertEqual(result['params']['type'], 'success')
    
    def test_get_session_logs_middleware(self):
        """Test getting session logs via middleware"""
        # Mock middleware configuration
        with patch.object(self.service, '_get_active_config_type', return_value='middleware'):
            # Mock session log model
            mock_log = Mock()
            mock_log.read.return_value = [{'operation': 'test', 'status': 'success'}]
            
            with patch.object(self.env['logikal.session.log'], 'search', return_value=mock_log):
                result = self.service.get_session_logs()
                
                self.assertEqual(len(result), 1)
                self.assertEqual(result[0]['operation'], 'test')
    
    def test_cleanup_old_logs_middleware(self):
        """Test cleanup old logs via middleware"""
        # Mock middleware configuration
        with patch.object(self.service, '_get_active_config_type', return_value='middleware'):
            with patch.object(self.env['res.config.settings'], 'get_active_config') as mock_config:
                mock_config.return_value = {
                    'type': 'middleware',
                    'config': {'log_cleanup_days': 30}
                }
                
                # Mock session log model
                mock_log = Mock()
                mock_log.cleanup_old_logs.return_value = 5
                
                with patch.object(self.env['logikal.session.log'], 'cleanup_old_logs', return_value=5):
                    result = self.service.cleanup_old_logs()
                    
                    self.assertEqual(result, 5)
    
    def test_configuration_error_handling(self):
        """Test handling of configuration errors"""
        # Mock configuration error
        with patch.object(self.env['res.config.settings'], 'get_active_config') as mock_config:
            mock_config.side_effect = UserError('Configuration error')
            
            with self.assertRaises(UserError):
                self.service._get_active_client()
    
    def test_mbioe_fallback(self):
        """Test fallback to MBIOE service when middleware is not configured"""
        # Mock MBIOE configuration
        with patch.object(self.service, '_get_active_config_type', return_value='mbioe'):
            with patch.object(self.env['mbioe.service'], 'test_connection') as mock_mbioe:
                mock_mbioe.return_value = {'type': 'ir.actions.client', 'tag': 'display_notification'}
                
                result = self.service.test_connection()
                
                mock_mbioe.assert_called_once()
                self.assertIsInstance(result, dict)
