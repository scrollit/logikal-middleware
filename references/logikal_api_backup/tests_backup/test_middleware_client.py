# -*- coding: utf-8 -*-

from unittest.mock import Mock, patch, MagicMock
from odoo.tests.common import TransactionCase
from odoo.exceptions import UserError
import requests


class TestMiddlewareClient(TransactionCase):
    
    def setUp(self):
        super().setUp()
        self.client = self.env['middleware.client']
        # Mock the client initialization
        with patch.object(self.client, '__init__', return_value=None):
            self.client.base_url = 'http://localhost:8001'
            self.client.client_id = 'test_client'
            self.client.client_secret = 'test_secret'
            self.client.env = self.env
    
    def test_authenticate_success(self):
        """Test successful authentication"""
        # Mock successful response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'access_token': 'test_token_123',
            'expires_in': 3600
        }
        
        with patch('requests.post', return_value=mock_response):
            result = self.client.authenticate()
            
            self.assertEqual(result, 'test_token_123')
            self.assertEqual(self.client.access_token, 'test_token_123')
    
    def test_authenticate_failure(self):
        """Test authentication failure"""
        # Mock failed response
        mock_response = Mock()
        mock_response.status_code = 401
        mock_response.text = 'Unauthorized'
        
        with patch('requests.post', return_value=mock_response):
            with self.assertRaises(UserError):
                self.client.authenticate()
    
    def test_get_all_projects_success(self):
        """Test successful project retrieval"""
        # Mock authentication
        self.client.access_token = 'test_token'
        self.client.token_expires_at = None
        
        # Mock successful response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'projects': [
                {'id': 'proj1', 'name': 'Project 1'},
                {'id': 'proj2', 'name': 'Project 2'}
            ]
        }
        
        with patch('requests.get', return_value=mock_response):
            result = self.client.get_all_projects()
            
            self.assertEqual(len(result), 2)
            self.assertEqual(result[0]['name'], 'Project 1')
    
    def test_get_project_complete_success(self):
        """Test successful complete project data retrieval"""
        # Mock authentication
        self.client.access_token = 'test_token'
        self.client.token_expires_at = None
        
        # Mock successful response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'project': {'id': 'proj1', 'name': 'Project 1'},
            'phases_with_elevations': [
                {
                    'phase': {'id': 'phase1', 'name': 'Phase 1'},
                    'elevations': [
                        {'id': 'elev1', 'name': 'Elevation 1'}
                    ]
                }
            ]
        }
        
        with patch('requests.get', return_value=mock_response):
            result = self.client.get_project_complete('proj1')
            
            self.assertEqual(result['project']['name'], 'Project 1')
            self.assertEqual(len(result['phases_with_elevations']), 1)
    
    def test_search_projects_success(self):
        """Test successful project search"""
        # Mock authentication
        self.client.access_token = 'test_token'
        self.client.token_expires_at = None
        
        # Mock successful response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'results': [
                {'id': 'proj1', 'name': 'Test Project'}
            ],
            'query': 'test',
            'count': 1
        }
        
        with patch('requests.get', return_value=mock_response):
            result = self.client.search_projects('test')
            
            self.assertEqual(len(result), 1)
            self.assertEqual(result[0]['name'], 'Test Project')
    
    def test_connection_error(self):
        """Test connection error handling"""
        with patch('requests.post', side_effect=requests.exceptions.ConnectionError('Connection failed')):
            with self.assertRaises(UserError):
                self.client.authenticate()
    
    def test_token_expiration_handling(self):
        """Test token expiration and re-authentication"""
        # Set expired token
        from datetime import datetime, timedelta
        self.client.access_token = 'expired_token'
        self.client.token_expires_at = datetime.now() - timedelta(minutes=1)
        
        # Mock re-authentication
        auth_response = Mock()
        auth_response.status_code = 200
        auth_response.json.return_value = {
            'access_token': 'new_token',
            'expires_in': 3600
        }
        
        # Mock project response
        project_response = Mock()
        project_response.status_code = 200
        project_response.json.return_value = {'projects': []}
        
        with patch('requests.post', return_value=auth_response):
            with patch('requests.get', return_value=project_response):
                result = self.client.get_all_projects()
                
                self.assertEqual(self.client.access_token, 'new_token')
                self.assertIsNotNone(self.client.token_expires_at)
