# -*- coding: utf-8 -*-

from unittest.mock import patch
from odoo.tests.common import TransactionCase
from odoo.exceptions import UserError


class TestLogikalProject(TransactionCase):
    
    def setUp(self):
        super().setUp()
        self.project_model = self.env['logikal.project']
    
    def test_create_project_manually_raises_error(self):
        """Test that creating projects manually raises an error"""
        with self.assertRaises(UserError):
            self.project_model.create({
                'name': 'Test Project',
                'logikal_id': 'test_id',
            })
    
    def test_create_project_from_middleware_success(self):
        """Test creating project from middleware data"""
        middleware_data = {
            'id': 'proj_123',
            'name': 'Test Project',
            'description': 'Test Description',
            'status': 'active',
            'created_at': '2023-01-01 10:00:00',
            'updated_at': '2023-01-01 10:00:00',
        }
        
        with patch.object(self.env, 'context', {'from_middleware_sync': True}):
            project = self.project_model.create_from_middleware_data(middleware_data)
            
            self.assertEqual(project.name, 'Test Project')
            self.assertEqual(project.logikal_id, 'proj_123')
            self.assertEqual(project.description, 'Test Description')
            self.assertEqual(project.status, 'active')
            self.assertTrue(project.is_synced)
            self.assertEqual(project.sync_status, 'synced')
    
    def test_update_project_from_middleware_success(self):
        """Test updating project from middleware data"""
        # Create project first
        with patch.object(self.env, 'context', {'from_middleware_sync': True}):
            project = self.project_model.create({
                'name': 'Original Project',
                'logikal_id': 'proj_123',
                'description': 'Original Description',
                'is_synced': True,
                'sync_status': 'synced',
            })
            
            # Update with new data
            middleware_data = {
                'name': 'Updated Project',
                'description': 'Updated Description',
                'status': 'active',
                'updated_at': '2023-01-02 10:00:00',
            }
            
            project.update_from_middleware_data(middleware_data)
            
            self.assertEqual(project.name, 'Updated Project')
            self.assertEqual(project.description, 'Updated Description')
            self.assertEqual(project.status, 'active')
            self.assertEqual(project.sync_status, 'synced')
    
    def test_find_by_logikal_id(self):
        """Test finding project by Logikal ID"""
        # Create project
        with patch.object(self.env, 'context', {'from_middleware_sync': True}):
            project = self.project_model.create({
                'name': 'Test Project',
                'logikal_id': 'proj_123',
                'is_synced': True,
                'sync_status': 'synced',
            })
            
            # Find by ID
            found_project = self.project_model.find_by_logikal_id('proj_123')
            self.assertEqual(found_project.id, project.id)
            
            # Find non-existent project
            not_found = self.project_model.find_by_logikal_id('nonexistent')
            self.assertFalse(not_found)
    
    def test_mark_sync_error(self):
        """Test marking project as having sync error"""
        with patch.object(self.env, 'context', {'from_middleware_sync': True}):
            project = self.project_model.create({
                'name': 'Test Project',
                'logikal_id': 'proj_123',
                'is_synced': True,
                'sync_status': 'synced',
            })
            
            project.mark_sync_error('Test error message')
            
            self.assertEqual(project.sync_status, 'error')
            self.assertIsNotNone(project.middleware_sync_date)


class TestLogikalPhase(TransactionCase):
    
    def setUp(self):
        super().setUp()
        self.phase_model = self.env['logikal.phase']
        self.project_model = self.env['logikal.project']
    
    def test_create_phase_manually_raises_error(self):
        """Test that creating phases manually raises an error"""
        with self.assertRaises(UserError):
            self.phase_model.create({
                'name': 'Test Phase',
                'logikal_id': 'phase_123',
            })
    
    def test_create_phase_from_middleware_success(self):
        """Test creating phase from middleware data"""
        # Create project first
        with patch.object(self.env, 'context', {'from_middleware_sync': True}):
            project = self.project_model.create({
                'name': 'Test Project',
                'logikal_id': 'proj_123',
                'is_synced': True,
                'sync_status': 'synced',
            })
            
            middleware_data = {
                'id': 'phase_123',
                'name': 'Test Phase',
                'description': 'Test Phase Description',
                'status': 'active',
                'created_at': '2023-01-01 10:00:00',
                'updated_at': '2023-01-01 10:00:00',
            }
            
            phase = self.phase_model.create_from_middleware_data(middleware_data, project.id)
            
            self.assertEqual(phase.name, 'Test Phase')
            self.assertEqual(phase.logikal_id, 'phase_123')
            self.assertEqual(phase.project_id.id, project.id)
            self.assertTrue(phase.is_synced)
            self.assertEqual(phase.sync_status, 'synced')


class TestLogikalElevation(TransactionCase):
    
    def setUp(self):
        super().setUp()
        self.elevation_model = self.env['logikal.elevation']
        self.phase_model = self.env['logikal.phase']
        self.project_model = self.env['logikal.project']
    
    def test_create_elevation_manually_raises_error(self):
        """Test that creating elevations manually raises an error"""
        with self.assertRaises(UserError):
            self.elevation_model.create({
                'name': 'Test Elevation',
                'logikal_id': 'elev_123',
            })
    
    def test_create_elevation_from_middleware_success(self):
        """Test creating elevation from middleware data"""
        # Create project and phase first
        with patch.object(self.env, 'context', {'from_middleware_sync': True}):
            project = self.project_model.create({
                'name': 'Test Project',
                'logikal_id': 'proj_123',
                'is_synced': True,
                'sync_status': 'synced',
            })
            
            phase = self.phase_model.create({
                'name': 'Test Phase',
                'logikal_id': 'phase_123',
                'project_id': project.id,
                'is_synced': True,
                'sync_status': 'synced',
            })
            
            middleware_data = {
                'id': 'elev_123',
                'name': 'Test Elevation',
                'description': 'Test Elevation Description',
                'width': 100.0,
                'height': 200.0,
                'depth': 50.0,
                'thumbnail_url': 'http://example.com/thumb.jpg',
                'created_at': '2023-01-01 10:00:00',
                'updated_at': '2023-01-01 10:00:00',
            }
            
            elevation = self.elevation_model.create_from_middleware_data(middleware_data, phase.id)
            
            self.assertEqual(elevation.name, 'Test Elevation')
            self.assertEqual(elevation.logikal_id, 'elev_123')
            self.assertEqual(elevation.phase_id.id, phase.id)
            self.assertEqual(elevation.project_id.id, project.id)
            self.assertEqual(elevation.width, 100.0)
            self.assertEqual(elevation.height, 200.0)
            self.assertEqual(elevation.depth, 50.0)
            self.assertEqual(elevation.thumbnail_url, 'http://example.com/thumb.jpg')
            self.assertTrue(elevation.is_synced)
            self.assertEqual(elevation.sync_status, 'synced')


class TestLogikalSessionLog(TransactionCase):
    
    def setUp(self):
        super().setUp()
        self.session_log_model = self.env['logikal.session.log']
    
    def test_create_session_log_success(self):
        """Test creating session log"""
        log = self.session_log_model.create({
            'operation': 'test_operation',
            'status': 'success',
            'response_code': 200,
            'duration_ms': 150,
            'request_url': 'http://test.com/api',
            'request_method': 'GET',
            'response_summary': 'Test response',
        })
        
        self.assertEqual(log.operation, 'test_operation')
        self.assertEqual(log.status, 'success')
        self.assertEqual(log.response_code, 200)
        self.assertEqual(log.duration_ms, 150)
    
    def test_cleanup_old_logs(self):
        """Test cleanup old logs functionality"""
        # Create some test logs
        for i in range(5):
            self.session_log_model.create({
                'operation': f'test_operation_{i}',
                'status': 'success',
                'response_code': 200,
                'duration_ms': 100,
            })
        
        # Test cleanup with 0 days (should return 0)
        cleaned_count = self.session_log_model.cleanup_old_logs(0)
        self.assertEqual(cleaned_count, 0)
        
        # Test cleanup with 30 days (should clean up all logs)
        cleaned_count = self.session_log_model.cleanup_old_logs(30)
        self.assertEqual(cleaned_count, 5)
    
    def test_get_recent_logs(self):
        """Test getting recent logs with filtering"""
        # Create test logs
        self.session_log_model.create({
            'operation': 'login',
            'status': 'success',
            'response_code': 200,
            'duration_ms': 100,
        })
        
        self.session_log_model.create({
            'operation': 'api_call',
            'status': 'failed',
            'response_code': 500,
            'duration_ms': 200,
        })
        
        # Get all recent logs
        logs = self.session_log_model.get_recent_logs()
        self.assertEqual(len(logs), 2)
        
        # Get only success logs
        success_logs = self.session_log_model.get_recent_logs(status='success')
        self.assertEqual(len(success_logs), 1)
        self.assertEqual(success_logs[0].operation, 'login')
        
        # Get only failed logs
        failed_logs = self.session_log_model.get_recent_logs(status='failed')
        self.assertEqual(len(failed_logs), 1)
        self.assertEqual(failed_logs[0].operation, 'api_call')
    
    def test_get_error_logs(self):
        """Test getting error logs"""
        # Create test logs
        self.session_log_model.create({
            'operation': 'login',
            'status': 'success',
            'response_code': 200,
            'duration_ms': 100,
        })
        
        self.session_log_model.create({
            'operation': 'api_call',
            'status': 'failed',
            'response_code': 500,
            'duration_ms': 200,
        })
        
        error_logs = self.session_log_model.get_error_logs()
        self.assertEqual(len(error_logs), 1)
        self.assertEqual(error_logs[0].operation, 'api_call')
        self.assertEqual(error_logs[0].status, 'failed')
