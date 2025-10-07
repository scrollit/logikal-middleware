# -*- coding: utf-8 -*-

import requests
import time
import logging
from datetime import datetime, timedelta
from odoo import models, api, fields, _
from odoo.exceptions import UserError
from .exceptions import ConfigurationError, APIConnectionError, AuthenticationError

_logger = logging.getLogger(__name__)


class MiddlewareClient:
    """Client for interacting with the Logikal Middleware API"""
    
    def __init__(self, base_url, client_id, client_secret, env=None):
        self.base_url = base_url.rstrip('/')
        self.client_id = client_id
        self.client_secret = client_secret
        self.access_token = None
        self.token_expires_at = None
        self.env = env  # Odoo environment for database logging
        
    def authenticate(self):
        """Authenticate with Middleware API and return access token"""
        url = f"{self.base_url}/api/v1/client-auth/login"
        payload = {
            "client_id": self.client_id,
            "client_secret": self.client_secret
        }
        
        start_time = time.time()
        _logger.info(f"Attempting middleware authentication for client: {self.client_id}")
        
        try:
            response = requests.post(url, json=payload, timeout=30)
            duration = int((time.time() - start_time) * 1000)
            
            if response.status_code == 200:
                data = response.json()
                
                if 'access_token' in data:
                    self.access_token = data['access_token']
                    # Set token expiration (default 1 hour if not provided)
                    expires_in = data.get('expires_in', 3600)
                    self.token_expires_at = datetime.now() + timedelta(seconds=expires_in)
                    
                    _logger.info("Middleware authentication successful")
                    
                    # Log successful authentication
                    self._log_session('login', 'success', response.status_code, None, duration,
                                    request_url=url, request_method='POST', 
                                    request_payload=payload, response_body=response.text,
                                    response_summary=f"Authenticated client: {self.client_id}")
                    
                    return self.access_token
                else:
                    error_msg = f"Unexpected response structure: {data}"
                    _logger.error(error_msg)
                    self._log_session('login', 'failed', response.status_code, error_msg, duration,
                                    request_url=url, request_method='POST', 
                                    request_payload=payload, response_body=response.text,
                                    response_summary="Authentication failed - unexpected response structure")
                    raise AuthenticationError(error_msg)
            else:
                error_msg = f"Authentication failed: {response.status_code} - {response.text}"
                _logger.error(error_msg)
                
                self._log_session('login', 'failed', response.status_code, error_msg, duration,
                                request_url=url, request_method='POST', 
                                request_payload=payload, response_body=response.text,
                                response_summary=f"Authentication failed - HTTP {response.status_code}")
                
                raise AuthenticationError(error_msg)
                
        except requests.exceptions.RequestException as e:
            duration = int((time.time() - start_time) * 1000)
            error_msg = f"Connection error during authentication: {str(e)}"
            _logger.error(error_msg)
            
            self._log_session('login', 'failed', 0, error_msg, duration,
                            request_url=url, request_method='POST', 
                            request_payload=payload, response_body=None,
                            response_summary="Connection error during authentication")
            
            raise APIConnectionError(error_msg)
    
    def test_connection(self):
        """Test API connectivity without maintaining session"""
        try:
            token = self.authenticate()
            if token:
                return True, "Middleware connection successful"
            else:
                return False, "Authentication failed - no token received"
        except Exception as e:
            return False, str(e)
    
    def _ensure_authenticated(self):
        """Ensure we have a valid access token"""
        if not self.access_token or (self.token_expires_at and datetime.now() >= self.token_expires_at):
            self.authenticate()
    
    def _make_authenticated_request(self, method, endpoint, **kwargs):
        """Make an authenticated request to the middleware API"""
        self._ensure_authenticated()
        
        if not self.access_token:
            raise AuthenticationError("No valid access token available")
        
        url = f"{self.base_url}{endpoint}"
        headers = kwargs.get('headers', {})
        headers['Authorization'] = f"Bearer {self.access_token}"
        kwargs['headers'] = headers
        
        try:
            response = requests.request(method, url, timeout=30, **kwargs)
            
            # Check for authentication-related errors
            if response.status_code == 401:
                _logger.warning("Received 401 Unauthorized, token may have expired")
                # Clear the invalid token and try to re-authenticate
                self.access_token = None
                self.token_expires_at = None
                self._ensure_authenticated()
                
                # Retry the request once
                headers['Authorization'] = f"Bearer {self.access_token}"
                response = requests.request(method, url, timeout=30, **kwargs)
            
            return response
            
        except requests.exceptions.RequestException as e:
            error_msg = f"Request failed: {str(e)}"
            _logger.error(error_msg)
            raise APIConnectionError(error_msg)
    
    def get_all_projects(self):
        """Get all projects from middleware (Odoo-optimized endpoint)"""
        url = f"{self.base_url}/api/v1/odoo/projects"
        start_time = time.time()
        _logger.info("Fetching all projects from middleware")
        
        try:
            response = self._make_authenticated_request('GET', '/api/v1/odoo/projects')
            duration = int((time.time() - start_time) * 1000)
            
            if response.status_code == 200:
                data = response.json()
                projects = data.get('projects', [])
                _logger.info(f"Retrieved {len(projects)} projects from middleware")
                
                # Log successful operation
                self._log_session('api_call', 'success', response.status_code, None, duration,
                                request_url=url, request_method='GET', request_payload=None,
                                response_body=response.text, 
                                response_summary=f"Retrieved {len(projects)} projects")
                
                return projects
            else:
                error_msg = f"Failed to get projects: {response.status_code} - {response.text}"
                _logger.error(error_msg)
                self._log_session('api_call', 'failed', response.status_code, error_msg, duration,
                                request_url=url, request_method='GET', request_payload=None,
                                response_body=response.text, 
                                response_summary=f"Failed to get projects - HTTP {response.status_code}")
                raise APIConnectionError(error_msg)
                
        except requests.exceptions.RequestException as e:
            duration = int((time.time() - start_time) * 1000)
            error_msg = f"Connection error while getting projects: {str(e)}"
            _logger.error(error_msg)
            self._log_session('api_call', 'failed', 0, error_msg, duration,
                            request_url=url, request_method='GET', request_payload=None,
                            response_body=None, response_summary="Connection error while getting projects")
            raise APIConnectionError(error_msg)
    
    def get_project_complete(self, project_id):
        """Get complete project data including phases and elevations"""
        url = f"{self.base_url}/api/v1/odoo/projects/{project_id}/complete"
        start_time = time.time()
        _logger.info(f"Fetching complete project data for {project_id}")
        
        try:
            response = self._make_authenticated_request('GET', f'/api/v1/odoo/projects/{project_id}/complete')
            duration = int((time.time() - start_time) * 1000)
            
            if response.status_code == 200:
                data = response.json()
                _logger.info(f"Retrieved complete project data for {project_id}")
                
                # Log successful operation
                self._log_session('api_call', 'success', response.status_code, None, duration,
                                request_url=url, request_method='GET', request_payload=None,
                                response_body=response.text, 
                                response_summary=f"Retrieved complete project data for {project_id}")
                
                return data
            else:
                error_msg = f"Failed to get project details: {response.status_code} - {response.text}"
                _logger.error(error_msg)
                self._log_session('api_call', 'failed', response.status_code, error_msg, duration,
                                request_url=url, request_method='GET', request_payload=None,
                                response_body=response.text, 
                                response_summary=f"Failed to get project details - HTTP {response.status_code}")
                raise APIConnectionError(error_msg)
                
        except requests.exceptions.RequestException as e:
            duration = int((time.time() - start_time) * 1000)
            error_msg = f"Connection error while getting project details: {str(e)}"
            _logger.error(error_msg)
            self._log_session('api_call', 'failed', 0, error_msg, duration,
                            request_url=url, request_method='GET', request_payload=None,
                            response_body=None, response_summary="Connection error while getting project details")
            raise APIConnectionError(error_msg)
    
    def search_projects(self, query):
        """Search projects by name or description"""
        url = f"{self.base_url}/api/v1/odoo/search"
        params = {'q': query}
        start_time = time.time()
        _logger.info(f"Searching projects with query: {query}")
        
        try:
            response = self._make_authenticated_request('GET', '/api/v1/odoo/search', params=params)
            duration = int((time.time() - start_time) * 1000)
            
            if response.status_code == 200:
                data = response.json()
                results = data.get('results', [])
                _logger.info(f"Search returned {len(results)} results")
                
                # Log successful operation
                self._log_session('api_call', 'success', response.status_code, None, duration,
                                request_url=url, request_method='GET', request_payload=params,
                                response_body=response.text, 
                                response_summary=f"Search returned {len(results)} results")
                
                return results
            else:
                error_msg = f"Search failed: {response.status_code} - {response.text}"
                _logger.error(error_msg)
                self._log_session('api_call', 'failed', response.status_code, error_msg, duration,
                                request_url=url, request_method='GET', request_payload=params,
                                response_body=response.text, 
                                response_summary=f"Search failed - HTTP {response.status_code}")
                raise APIConnectionError(error_msg)
                
        except requests.exceptions.RequestException as e:
            duration = int((time.time() - start_time) * 1000)
            error_msg = f"Connection error during search: {str(e)}"
            _logger.error(error_msg)
            self._log_session('api_call', 'failed', 0, error_msg, duration,
                            request_url=url, request_method='GET', request_payload=params,
                            response_body=None, response_summary="Connection error during search")
            raise APIConnectionError(error_msg)
    
    def get_project_stats(self):
        """Get project statistics from middleware"""
        url = f"{self.base_url}/api/v1/odoo/stats"
        start_time = time.time()
        _logger.info("Fetching project statistics from middleware")
        
        try:
            response = self._make_authenticated_request('GET', '/api/v1/odoo/stats')
            duration = int((time.time() - start_time) * 1000)
            
            if response.status_code == 200:
                data = response.json()
                _logger.info("Retrieved project statistics")
                
                # Log successful operation
                self._log_session('api_call', 'success', response.status_code, None, duration,
                                request_url=url, request_method='GET', request_payload=None,
                                response_body=response.text, 
                                response_summary="Retrieved project statistics")
                
                return data
            else:
                error_msg = f"Failed to get statistics: {response.status_code} - {response.text}"
                _logger.error(error_msg)
                self._log_session('api_call', 'failed', response.status_code, error_msg, duration,
                                request_url=url, request_method='GET', request_payload=None,
                                response_body=response.text, 
                                response_summary=f"Failed to get statistics - HTTP {response.status_code}")
                raise APIConnectionError(error_msg)
                
        except requests.exceptions.RequestException as e:
            duration = int((time.time() - start_time) * 1000)
            error_msg = f"Connection error while getting statistics: {str(e)}"
            _logger.error(error_msg)
            self._log_session('api_call', 'failed', 0, error_msg, duration,
                            request_url=url, request_method='GET', request_payload=None,
                            response_body=None, response_summary="Connection error while getting statistics")
            raise APIConnectionError(error_msg)
    
    def _log_session(self, operation, status, response_code, error_message, duration, 
                     request_url=None, request_method=None, request_payload=None, 
                     response_body=None, response_summary=None):
        """Log session activity to database with enhanced details"""
        if not self.env:
            return
            
        try:
            # Mask sensitive data in request payload
            safe_payload = None
            if request_payload:
                safe_payload = self._mask_sensitive_data(request_payload)
            
            # Truncate response body if too large (keep first 5000 chars)
            safe_response_body = None
            if response_body:
                if len(response_body) > 5000:
                    safe_response_body = response_body[:5000] + "\n... (truncated)"
                else:
                    safe_response_body = response_body
            
            self.env['logikal.session.log'].sudo().create({
                'session_token': self.access_token or 'N/A',
                'operation': operation,
                'status': status,
                'response_code': response_code,
                'error_message': error_message,
                'duration_ms': duration,
                'request_url': request_url,
                'request_method': request_method,
                'request_payload': safe_payload,
                'response_body': safe_response_body,
                'response_summary': response_summary,
            })
        except Exception as e:
            # Don't let logging errors break the main flow
            _logger.warning(f"Failed to log session activity: {str(e)}")
    
    def _mask_sensitive_data(self, payload):
        """Mask sensitive data like client secrets in request payload"""
        import json
        try:
            if isinstance(payload, str):
                data = json.loads(payload)
            else:
                data = payload
            
            # Create a copy to avoid modifying original
            safe_data = data.copy() if isinstance(data, dict) else data
            
            # Mask sensitive fields
            if isinstance(safe_data, dict):
                for key in safe_data:
                    if any(sensitive in key.lower() for sensitive in ['secret', 'password', 'token']):
                        safe_data[key] = '***'
            
            return json.dumps(safe_data, indent=2) if isinstance(safe_data, dict) else str(safe_data)
        except:
            # If anything fails, return truncated string
            return str(payload)[:500] + "..." if len(str(payload)) > 500 else str(payload)
