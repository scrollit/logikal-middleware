# -*- coding: utf-8 -*-

import requests
import time
import logging
from .exceptions import APIConnectionError, AuthenticationError, SessionError

_logger = logging.getLogger(__name__)


class MBIOEApiClient:
    """Client for interacting with the MBIOE API"""
    
    def __init__(self, base_url, username, password, env=None):
        self.base_url = base_url.rstrip('/')
        self.username = username
        self.password = password
        self.session_token = None
        self.env = env  # Odoo environment for database logging
        
        # Navigation state tracking for session restoration
        self.current_directory = None
        self.current_project = None
        
    def authenticate(self):
        """Authenticate with MBIOE API and return session token"""
        url = f"{self.base_url}/auth"
        payload = {
            "username": self.username,
            "password": self.password,
            "erp": True
        }
        
        start_time = time.time()
        _logger.info(f"Attempting authentication for user: {self.username}")
        
        try:
            response = requests.post(url, json=payload, timeout=30)
            duration = int((time.time() - start_time) * 1000)
            
            if response.status_code == 200:
                data = response.json()
                
                # Check if response has expected structure
                if 'data' in data and 'token' in data['data']:
                    self.session_token = data['data']['token']
                    # Reset navigation state on new authentication
                    self.current_directory = None
                    self.current_project = None
                    _logger.info("Authentication successful")
                    
                    # Log successful authentication with response details
                    self._log_session('login', 'success', response.status_code, None, duration,
                                    request_url=url, request_method='POST', 
                                    request_payload=payload, response_body=response.text,
                                    response_summary=f"Authenticated user: {data['data'].get('username', 'Unknown')}")
                    
                    return self.session_token
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
                
                # Log failed authentication
                self._log_session('login', 'failed', response.status_code, error_msg, duration,
                                request_url=url, request_method='POST', 
                                request_payload=payload, response_body=response.text,
                                response_summary=f"Authentication failed - HTTP {response.status_code}")
                
                raise AuthenticationError(error_msg)
                
        except requests.exceptions.RequestException as e:
            duration = int((time.time() - start_time) * 1000)
            error_msg = f"Connection error during authentication: {str(e)}"
            _logger.error(error_msg)
            
            # Log connection error
            self._log_session('login', 'failed', 0, error_msg, duration,
                            request_url=url, request_method='POST', 
                            request_payload=payload, response_body=None,
                            response_summary="Connection error during authentication")
            
            raise APIConnectionError(error_msg)
    
    def logout(self):
        """Terminate current session"""
        if not self.session_token:
            _logger.warning("No active session to logout")
            return
            
        url = f"{self.base_url}/auth"
        headers = {"Authorization": f"Bearer {self.session_token}"}
        
        start_time = time.time()
        _logger.info("Logging out of MBIOE session")
        
        try:
            # Reduce timeout to prevent hanging and add better error handling
            response = requests.delete(url, headers=headers, timeout=10)
            duration = int((time.time() - start_time) * 1000)
            
            if response.status_code == 200:
                _logger.info("Logout successful")
                self._log_session('logout', 'success', response.status_code, None, duration)
            else:
                error_msg = f"Logout failed: {response.status_code} - {response.text}"
                _logger.warning(error_msg)
                self._log_session('logout', 'failed', response.status_code, error_msg, duration)
                
        except requests.exceptions.Timeout as e:
            duration = int((time.time() - start_time) * 1000)
            error_msg = f"Logout timeout after 10 seconds: {str(e)}"
            _logger.warning(error_msg)
            self._log_session('logout', 'failed', 408, error_msg, duration)
            # Don't raise - session will be considered logged out
            
        except requests.exceptions.RequestException as e:
            duration = int((time.time() - start_time) * 1000)
            error_msg = f"Connection error during logout: {str(e)}"
            _logger.warning(error_msg)
            self._log_session('logout', 'failed', 0, error_msg, duration)
            
        finally:
            # Always clear the token
            self.session_token = None
    
    def test_connection(self):
        """Test API connectivity without maintaining session"""
        try:
            token = self.authenticate()
            if token:
                self.logout()
                return True, "Connection successful"
            else:
                return False, "Authentication failed - no token received"
        except Exception as e:
            return False, str(e)
    
    def _make_authenticated_request(self, method, endpoint, **kwargs):
        """Make an authenticated request to the API with session validation and recovery"""
        if not self.session_token:
            raise SessionError("No active session. Please authenticate first.")
        
        # Check if session is still valid before making request
        if not self._is_session_valid():
            _logger.warning("Session appears to be invalid, attempting re-authentication")
            try:
                # Store current navigation state before re-auth
                stored_directory = self.current_directory
                stored_project = self.current_project
                
                # Re-authenticate (this will reset navigation state)
                self.authenticate()
                _logger.info("Successfully re-authenticated session")
                
                # Restore navigation state after re-auth
                if stored_directory or stored_project:
                    self._restore_navigation_state(stored_directory, stored_project)
                    
            except Exception as e:
                _logger.error(f"Failed to re-authenticate session: {str(e)}")
                raise SessionError("Session expired and re-authentication failed")
        
        url = f"{self.base_url}{endpoint}"
        headers = kwargs.get('headers', {})
        headers['Authorization'] = f"Bearer {self.session_token}"
        kwargs['headers'] = headers
        
        try:
            response = requests.request(method, url, timeout=30, **kwargs)
            
            # Check for authentication-related errors
            if response.status_code == 401:
                _logger.warning("Received 401 Unauthorized, session may have expired")
                # Clear the invalid token
                self.session_token = None
                raise SessionError("Session expired - please re-authenticate")
            
            return response
            
        except requests.exceptions.RequestException as e:
            error_msg = f"Request failed: {str(e)}"
            _logger.error(error_msg)
            raise APIConnectionError(error_msg)

    def _is_session_valid(self):
        """
        Check if the current session is still valid by making a lightweight test request.
        
        Returns:
            bool: True if session is valid, False otherwise
        """
        if not self.session_token:
            return False
        
        # Skip validation if we're in project context to avoid context switching
        # The /directories endpoint changes session context from "project" back to "directory"
        # which would make subsequent project operations fail
        if self.current_project:
            _logger.debug(f"Skipping session validation - in project context: {self.current_project}")
            return True  # Assume valid when in project context
            
        try:
            # Only validate when in directory context or no context
            # Make a lightweight request to test session validity
            test_response = requests.get(
                f"{self.base_url}/directories",
                headers={'Authorization': f"Bearer {self.session_token}"},
                timeout=10
            )
            
            # If we get a 401, session is invalid
            if test_response.status_code == 401:
                return False
            
            # If we get a 200 or other success code, session is valid
            return test_response.status_code < 400
            
        except Exception as e:
            _logger.debug(f"Session validation check failed: {str(e)}")
            # If we can't check, assume session is valid to avoid unnecessary re-authentication
            return True

    def validate_session(self):
        """
        Validate the current session and re-authenticate if necessary.
        
        Returns:
            bool: True if session is valid or successfully re-authenticated, False otherwise
        """
        if not self.session_token:
            try:
                self.authenticate()
                return True
            except Exception as e:
                _logger.error(f"Failed to authenticate: {str(e)}")
                return False
        
        if self._is_session_valid():
            return True
        
        # Session is invalid, try to re-authenticate
        try:
            _logger.info("Session invalid, attempting re-authentication")
            self.authenticate()
            return True
        except Exception as e:
            _logger.error(f"Failed to re-authenticate: {str(e)}")
            return False
    
    def _restore_navigation_state(self, directory_identifier, project_identifier):
        """
        Restore navigation state after re-authentication.
        This ensures the session is in the correct context after token refresh.
        """
        try:
            _logger.info(f"Restoring navigation state - Directory: {directory_identifier}, Project: {project_identifier}")
            
            # First restore directory context if we had one
            if directory_identifier:
                _logger.info(f"Restoring directory context: {directory_identifier}")
                # Call select_directory without state tracking to avoid recursion
                self._select_directory_without_tracking(directory_identifier)
                self.current_directory = directory_identifier
                
            # Then restore project context if we had one
            if project_identifier:
                _logger.info(f"Restoring project context: {project_identifier}")
                # Call select_project without state tracking to avoid recursion
                self._select_project_without_tracking(project_identifier)
                self.current_project = project_identifier
                
            _logger.info("Successfully restored navigation state")
            
        except Exception as e:
            error_msg = f"Failed to restore navigation state: {str(e)}"
            _logger.error(error_msg)
            # Don't raise here - allow the original request to proceed and potentially fail gracefully
            # The caller will get a more specific error about the actual operation
    
    def get_directories(self):
        """Get directories from current context (root or selected folder)"""
        if not self.session_token:
            raise SessionError("No active session. Please authenticate first.")
        
        url = f"{self.base_url}/directories"
        start_time = time.time()
        _logger.info("Fetching directories from MBIOE API")
        
        try:
            response = self._make_authenticated_request('GET', '/directories')
            duration = int((time.time() - start_time) * 1000)
            
            if response.status_code == 200:
                data = response.json()
                directories = data.get('data', []) if isinstance(data, dict) else data
                _logger.info(f"Retrieved {len(directories)} directories")
                
                # Log successful operation
                self._log_session('api_call', 'success', response.status_code, None, duration,
                                request_url=url, request_method='GET', request_payload=None,
                                response_body=response.text, 
                                response_summary=f"Retrieved {len(directories)} directories")
                
                return directories
            else:
                error_msg = f"Failed to get directories: {response.status_code} - {response.text}"
                _logger.error(error_msg)
                self._log_session('api_call', 'failed', response.status_code, error_msg, duration,
                                request_url=url, request_method='GET', request_payload=None,
                                response_body=response.text, 
                                response_summary=f"Failed to get directories - HTTP {response.status_code}")
                raise APIConnectionError(error_msg)
                
        except requests.exceptions.RequestException as e:
            duration = int((time.time() - start_time) * 1000)
            error_msg = f"Connection error while getting directories: {str(e)}"
            _logger.error(error_msg)
            self._log_session('api_call', 'failed', 0, error_msg, duration,
                            request_url=url, request_method='GET', request_payload=None,
                            response_body=None, response_summary="Connection error while getting directories")
            raise APIConnectionError(error_msg)
    
    def select_directory(self, identifier):
        """Select a directory by identifier (required for folder-scoped operations)"""
        # Validate session before making request
        if not self.validate_session():
            raise SessionError("Failed to validate or re-authenticate session")
        
        url = f"{self.base_url}/directories/select"
        payload = {"identifier": identifier}
        start_time = time.time()
        _logger.info(f"Selecting directory: {identifier}")
        
        try:
            response = self._make_authenticated_request('POST', '/directories/select', json=payload)
            duration = int((time.time() - start_time) * 1000)
            
            if response.status_code == 200:
                _logger.info(f"Successfully selected directory: {identifier}")
                
                # Track navigation state
                self.current_directory = identifier
                self.current_project = None  # Reset project when changing directory
                
                # Log successful operation
                self._log_session('api_call', 'success', response.status_code, None, duration,
                                request_url=url, request_method='POST', request_payload=payload,
                                response_body=response.text, 
                                response_summary=f"Selected directory: {identifier}")
                
                return response.json()
            else:
                error_msg = f"Failed to select directory {identifier}: {response.status_code} - {response.text}"
                _logger.error(error_msg)
                self._log_session('api_call', 'failed', response.status_code, error_msg, duration,
                                request_url=url, request_method='POST', request_payload=payload,
                                response_body=response.text, 
                                response_summary=f"Failed to select directory {identifier} - HTTP {response.status_code}")
                raise APIConnectionError(error_msg)
                
        except requests.exceptions.RequestException as e:
            duration = int((time.time() - start_time) * 1000)
            error_msg = f"Connection error while selecting directory {identifier}: {str(e)}"
            _logger.error(error_msg)
            self._log_session('api_call', 'failed', 0, error_msg, duration,
                            request_url=url, request_method='POST', request_payload=payload,
                            response_body=None, response_summary=f"Connection error selecting directory {identifier}")
            raise APIConnectionError(error_msg)
    
    def _select_directory_without_tracking(self, identifier):
        """
        Select directory without updating navigation state (used for restoration).
        This prevents infinite recursion during state restoration.
        """
        url = f"{self.base_url}/directories/select"
        payload = {"identifier": identifier}
        start_time = time.time()
        
        try:
            # Use direct request instead of _make_authenticated_request to avoid validation loop
            headers = {'Authorization': f"Bearer {self.session_token}"}
            response = requests.post(url, json=payload, headers=headers, timeout=30)
            duration = int((time.time() - start_time) * 1000)
            
            if response.status_code == 200:
                _logger.info(f"Successfully restored directory: {identifier}")
                return response.json()
            else:
                error_msg = f"Failed to restore directory {identifier}: {response.status_code} - {response.text}"
                _logger.error(error_msg)
                raise APIConnectionError(error_msg)
                
        except requests.exceptions.RequestException as e:
            error_msg = f"Connection error while restoring directory {identifier}: {str(e)}"
            _logger.error(error_msg)
            raise APIConnectionError(error_msg)
    
    def select_project(self, project_identifier):
        """Select a project by identifier (required for phase/elevation operations)"""
        # Validate session before making request
        if not self.validate_session():
            raise SessionError("Failed to validate or re-authenticate session")
        
        url = f"{self.base_url}/projects/select"
        payload = {"identifier": project_identifier}
        start_time = time.time()
        _logger.info(f"Selecting project: {project_identifier}")
        
        try:
            response = self._make_authenticated_request('POST', '/projects/select', json=payload)
            duration = int((time.time() - start_time) * 1000)
            
            if response.status_code == 200:
                _logger.info(f"Successfully selected project: {project_identifier}")
                
                # Track navigation state
                self.current_project = project_identifier
                
                # Log successful operation
                self._log_session('api_call', 'success', response.status_code, None, duration,
                                request_url=url, request_method='POST', request_payload=payload,
                                response_body=response.text, 
                                response_summary=f"Selected project: {project_identifier}")
                
                return response.json()
            else:
                error_msg = f"Failed to select project {project_identifier}: {response.status_code} - {response.text}"
                _logger.error(error_msg)
                self._log_session('api_call', 'failed', response.status_code, error_msg, duration,
                                request_url=url, request_method='POST', request_payload=payload,
                                response_body=response.text, 
                                response_summary=f"Failed to select project {project_identifier} - HTTP {response.status_code}")
                raise APIConnectionError(error_msg)
                
        except requests.exceptions.RequestException as e:
            duration = int((time.time() - start_time) * 1000)
            error_msg = f"Connection error while selecting project {project_identifier}: {str(e)}"
            _logger.error(error_msg)
            self._log_session('api_call', 'failed', 0, error_msg, duration,
                            request_url=url, request_method='POST', request_payload=payload,
                            response_body=None, response_summary=f"Connection error selecting project {project_identifier}")
            raise APIConnectionError(error_msg)
    
    def get_projects(self):
        """Get projects from current selected directory context"""
        if not self.session_token:
            raise SessionError("No active session. Please authenticate first.")
        
        url = f"{self.base_url}/projects"
        start_time = time.time()
        _logger.info("Fetching projects from MBIOE API")
        
        try:
            response = self._make_authenticated_request('GET', '/projects')
            duration = int((time.time() - start_time) * 1000)
            
            if response.status_code == 200:
                data = response.json()
                projects = data.get('data', []) if isinstance(data, dict) else data
                _logger.info(f"Retrieved {len(projects)} projects")
                
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
    
    def get_project_details(self, project_identifier):
        """Get detailed information for a specific project
        
        Args:
            project_identifier (str): Project GUID from MBIOE API
            
        Returns:
            dict: Detailed project information
        """
        if not self.session_token:
            raise SessionError("No active session. Please authenticate first.")
        
        url = f"{self.base_url}/projects/{project_identifier}"
        start_time = time.time()
        _logger.info(f"Fetching project details for {project_identifier}")
        
        try:
            response = self._make_authenticated_request('GET', f'/projects/{project_identifier}')
            duration = int((time.time() - start_time) * 1000)
            
            if response.status_code == 200:
                data = response.json()
                project_data = data.get('data', data) if isinstance(data, dict) else data
                _logger.info(f"Retrieved project details for {project_identifier}")
                
                # Log successful operation
                self._log_session('api_call', 'success', response.status_code, None, duration,
                                request_url=url, request_method='GET', request_payload=None,
                                response_body=response.text, 
                                response_summary=f"Retrieved project details for {project_identifier}")
                
                return project_data
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
    
    def select_project(self, project_identifier):
        """Select a project by identifier (required for phase/elevation operations)"""
        if not self.session_token:
            raise SessionError("No active session. Please authenticate first.")
        
        url = f"{self.base_url}/projects/select"
        payload = {"identifier": project_identifier}
        start_time = time.time()
        _logger.info(f"Selecting project: {project_identifier}")
        
        try:
            response = self._make_authenticated_request('POST', '/projects/select', json=payload)
            duration = int((time.time() - start_time) * 1000)
            
            if response.status_code == 200:
                _logger.info(f"Successfully selected project: {project_identifier}")
                
                # Track navigation state
                self.current_project = project_identifier
                
                # Log successful operation
                self._log_session('api_call', 'success', response.status_code, None, duration,
                                request_url=url, request_method='POST', request_payload=payload,
                                response_body=response.text, 
                                response_summary=f"Selected project: {project_identifier}")
                
                return response.json()
            else:
                error_msg = f"Failed to select project {project_identifier}: {response.status_code} - {response.text}"
                _logger.error(error_msg)
                self._log_session('api_call', 'failed', response.status_code, error_msg, duration,
                                request_url=url, request_method='POST', request_payload=payload,
                                response_body=response.text, 
                                response_summary=f"Failed to select project {project_identifier} - HTTP {response.status_code}")
                raise APIConnectionError(error_msg)
                
        except requests.exceptions.RequestException as e:
            duration = int((time.time() - start_time) * 1000)
            error_msg = f"Connection error while selecting project {project_identifier}: {str(e)}"
            _logger.error(error_msg)
            self._log_session('api_call', 'failed', 0, error_msg, duration,
                            request_url=url, request_method='POST', request_payload=payload,
                            response_body=None, response_summary=f"Connection error selecting project {project_identifier}")
            raise APIConnectionError(error_msg)
    
    def _select_project_without_tracking(self, project_identifier):
        """
        Select project without updating navigation state (used for restoration).
        This prevents infinite recursion during state restoration.
        """
        url = f"{self.base_url}/projects/select"
        payload = {"identifier": project_identifier}
        start_time = time.time()
        
        try:
            # Use direct request instead of _make_authenticated_request to avoid validation loop
            headers = {'Authorization': f"Bearer {self.session_token}"}
            response = requests.post(url, json=payload, headers=headers, timeout=30)
            duration = int((time.time() - start_time) * 1000)
            
            if response.status_code == 200:
                _logger.info(f"Successfully restored project: {project_identifier}")
                return response.json()
            else:
                error_msg = f"Failed to restore project {project_identifier}: {response.status_code} - {response.text}"
                _logger.error(error_msg)
                raise APIConnectionError(error_msg)
                
        except requests.exceptions.RequestException as e:
            error_msg = f"Connection error while restoring project {project_identifier}: {str(e)}"
            _logger.error(error_msg)
            raise APIConnectionError(error_msg)
    
    def test_directory_operations(self):
        """Test directory and project operations without maintaining session"""
        try:
            # Authenticate
            token = self.authenticate()
            
            # Test directory listing
            directories = self.get_directories()
            _logger.info(f"Directory test: Found {len(directories)} root directories")
            
            # Test directory selection if we have directories
            if directories:
                first_dir = directories[0]
                identifier = first_dir.get('identifier') or first_dir.get('id')
                if identifier:
                    self.select_directory(identifier)
                    _logger.info(f"Successfully selected directory: {first_dir.get('name', 'Unknown')}")
                    
                    # Test project listing in selected directory
                    projects = self.get_projects()
                    _logger.info(f"Project test: Found {len(projects)} projects in selected directory")
            
            # Cleanup
            self.logout()
            
            return True, f"Directory operations successful. Found {len(directories)} directories."
            
        except Exception as e:
            _logger.error(f"Directory operations test failed: {str(e)}")
            # Try to cleanup session on error
            try:
                if self.session_token:
                    self.logout()
            except:
                pass
            return False, str(e)
    
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
            
            self.env['mbioe.session.log'].sudo().create({
                'session_token': self.session_token or 'N/A',
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
        """Mask sensitive data like passwords in request payload"""
        import json
        try:
            if isinstance(payload, str):
                data = json.loads(payload)
            else:
                data = payload
            
            # Create a copy to avoid modifying original
            safe_data = data.copy() if isinstance(data, dict) else data
            
            # Mask password fields
            if isinstance(safe_data, dict):
                for key in safe_data:
                    if 'password' in key.lower():
                        safe_data[key] = '***'
            
            return json.dumps(safe_data, indent=2) if isinstance(safe_data, dict) else str(safe_data)
        except:
            # If anything fails, return truncated string
            return str(payload)[:500] + "..." if len(str(payload)) > 500 else str(payload)
    
    def get_phases(self):
        """Get all phases in the current project"""
        url = f"{self.base_url}/phases"
        start_time = time.time()
        _logger.info("Fetching phases for current project")
        
        try:
            response = self._make_authenticated_request('GET', '/phases')
            duration = int((time.time() - start_time) * 1000)
            
            if response.status_code == 200:
                data = response.json()
                phases_data = data.get('data', data) if isinstance(data, dict) else data
                _logger.info(f"Retrieved {len(phases_data) if isinstance(phases_data, list) else 'unknown'} phases")
                
                # Log successful operation
                self._log_session('api_call', 'success', response.status_code, None, duration,
                                request_url=url, request_method='GET', request_payload=None,
                                response_body=response.text, 
                                response_summary=f"Retrieved phases for current project")
                
                return phases_data
            else:
                error_msg = f"Failed to get phases: {response.status_code} - {response.text}"
                _logger.error(error_msg)
                self._log_session('api_call', 'failed', response.status_code, error_msg, duration,
                                request_url=url, request_method='GET', request_payload=None,
                                response_body=response.text, 
                                response_summary=f"Failed to get phases - HTTP {response.status_code}")
                raise APIConnectionError(error_msg)
                
        except requests.exceptions.RequestException as e:
            duration = int((time.time() - start_time) * 1000)
            error_msg = f"Connection error while getting phases: {str(e)}"
            _logger.error(error_msg)
            self._log_session('api_call', 'failed', None, error_msg, duration,
                            request_url=url, request_method='GET', request_payload=None,
                            response_body=None, response_summary="Connection error during phases fetch")
            raise APIConnectionError(error_msg)
    
    def select_phase(self, phase_identifier):
        """Select a phase from the current project"""
        # Validate session before making request
        if not self.validate_session():
            raise SessionError("Failed to validate or re-authenticate session")
        
        url = f"{self.base_url}/phases/select"
        start_time = time.time()
        _logger.info(f"Selecting phase {phase_identifier}")
        
        payload = {'identifier': phase_identifier}
        
        try:
            response = self._make_authenticated_request('POST', '/phases/select', json=payload)
            duration = int((time.time() - start_time) * 1000)
            
            if response.status_code == 200:
                _logger.info(f"Successfully selected phase {phase_identifier}")
                
                # Log successful operation
                self._log_session('api_call', 'success', response.status_code, None, duration,
                                request_url=url, request_method='POST', request_payload=payload,
                                response_body=response.text, 
                                response_summary=f"Selected phase {phase_identifier}")
                
                return True
            else:
                error_msg = f"Failed to select phase: {response.status_code} - {response.text}"
                _logger.error(error_msg)
                self._log_session('api_call', 'failed', response.status_code, error_msg, duration,
                                request_url=url, request_method='POST', request_payload=payload,
                                response_body=response.text, 
                                response_summary=f"Failed to select phase - HTTP {response.status_code}")
                raise APIConnectionError(error_msg)
                
        except requests.exceptions.RequestException as e:
            duration = int((time.time() - start_time) * 1000)
            error_msg = f"Connection error while selecting phase: {str(e)}"
            _logger.error(error_msg)
            self._log_session('api_call', 'failed', None, error_msg, duration,
                            request_url=url, request_method='POST', request_payload=payload,
                            response_body=None, response_summary="Connection error during phase selection")
            raise APIConnectionError(error_msg)
    
    def get_elevations(self):
        """Get all elevations in the current project"""
        url = f"{self.base_url}/elevations"
        start_time = time.time()
        _logger.info("Fetching elevations for current project")
        
        try:
            response = self._make_authenticated_request('GET', '/elevations')
            duration = int((time.time() - start_time) * 1000)
            
            if response.status_code == 200:
                data = response.json()
                elevations_data = data.get('data', data) if isinstance(data, dict) else data
                _logger.info(f"Retrieved {len(elevations_data) if isinstance(elevations_data, list) else 'unknown'} elevations")
                
                # Log successful operation
                self._log_session('api_call', 'success', response.status_code, None, duration,
                                request_url=url, request_method='GET', request_payload=None,
                                response_body=response.text, 
                                response_summary=f"Retrieved elevations for current project")
                
                return elevations_data
            else:
                error_msg = f"Failed to get elevations: {response.status_code} - {response.text}"
                _logger.error(error_msg)
                self._log_session('api_call', 'failed', response.status_code, error_msg, duration,
                                request_url=url, request_method='GET', request_payload=None,
                                response_body=response.text, 
                                response_summary=f"Failed to get elevations - HTTP {response.status_code}")
                raise APIConnectionError(error_msg)
                
        except requests.exceptions.RequestException as e:
            duration = int((time.time() - start_time) * 1000)
            error_msg = f"Connection error while getting elevations: {str(e)}"
            _logger.error(error_msg)
            self._log_session('api_call', 'failed', None, error_msg, duration,
                            request_url=url, request_method='GET', request_payload=None,
                            response_body=None, response_summary="Connection error during elevations fetch")
            raise APIConnectionError(error_msg)
    
    def get_elevation_thumbnail(self, elevation_id, width=300, height=300, format="PNG", 
                              view="Exterior", withdimensions="true", withdescription="false"):
        """
        Get thumbnail for specific elevation with specified parameters.
        Must be called while in the correct phase context.
        
        Args:
            elevation_id (str): ID of the elevation to get thumbnail for
            width (int): Thumbnail width in pixels (default: 300)
            height (int): Thumbnail height in pixels (default: 300)
            format (str): Image format - 'PNG', 'JPG', 'EMF' (default: 'PNG')
            view (str): Viewpoint - 'Interior', 'Exterior' (default: 'Exterior')
            withdimensions (str): Include dimensions - 'true', 'false' (default: 'true')
            withdescription (str): Include description - 'true', 'false' (default: 'false')
            
        Returns:
            bytes: Binary image data
            
        Raises:
            APIConnectionError: If thumbnail cannot be retrieved
            SessionError: If session is invalid
        """
        if not self.session_token:
            raise SessionError("No active session. Please authenticate first.")
        
        url = f"{self.base_url}/elevations/{elevation_id}/thumbnail"
        params = {
            'width': str(width),
            'height': str(height),
            'format': format,
            'view': view,
            'withdimensions': withdimensions,
            'withdescription': withdescription
        }
        start_time = time.time()
        _logger.info(f"Fetching thumbnail for elevation {elevation_id} ({width}x{height}, {format}, {view})")
        
        try:
            # Use direct request with session token to get binary data
            headers = {'Authorization': f"Bearer {self.session_token}"}
            response = requests.get(url, params=params, headers=headers, timeout=30)
            duration = int((time.time() - start_time) * 1000)
            
            if response.status_code == 200:
                thumbnail_size = len(response.content)
                _logger.info(f"Successfully retrieved thumbnail for elevation {elevation_id} ({thumbnail_size} bytes)")
                
                # Log successful operation
                self._log_session('api_call', 'success', response.status_code, None, duration,
                                request_url=url, request_method='GET', request_payload=params,
                                response_body=f"Binary image data ({thumbnail_size} bytes)", 
                                response_summary=f"Retrieved thumbnail for elevation {elevation_id}")
                
                return response.content
            else:
                error_msg = f"Failed to get thumbnail for elevation {elevation_id}: {response.status_code} - {response.text}"
                _logger.error(error_msg)
                self._log_session('api_call', 'failed', response.status_code, error_msg, duration,
                                request_url=url, request_method='GET', request_payload=params,
                                response_body=response.text, 
                                response_summary=f"Failed to get thumbnail for elevation {elevation_id} - HTTP {response.status_code}")
                raise APIConnectionError(error_msg)
                
        except requests.exceptions.RequestException as e:
            duration = int((time.time() - start_time) * 1000)
            error_msg = f"Connection error while getting thumbnail for elevation {elevation_id}: {str(e)}"
            _logger.error(error_msg)
            self._log_session('api_call', 'failed', None, error_msg, duration,
                            request_url=url, request_method='GET', request_payload=params,
                            response_body=None, response_summary=f"Connection error getting thumbnail for elevation {elevation_id}")
            raise APIConnectionError(error_msg)


def log_api_request(method, url, headers=None, payload=None):
    """Log outgoing API requests"""
    _logger.info(f"MBIOE API {method} {url}")
    if headers:
        # Mask authorization header for security
        safe_headers = headers.copy()
        if 'Authorization' in safe_headers:
            safe_headers['Authorization'] = 'Bearer ***'
        _logger.debug(f"Headers: {safe_headers}")
    if payload:
        # Mask password in login requests
        safe_payload = payload.copy() if isinstance(payload, dict) else payload
        if isinstance(safe_payload, dict) and 'password' in safe_payload:
            safe_payload['password'] = '***'
        _logger.debug(f"Payload: {safe_payload}")


def log_api_response(response, duration):
    """Log API responses"""
    _logger.info(f"API Response: {response.status_code} ({duration}ms)")
    if response.status_code >= 400:
        _logger.error(f"API Error: {response.text}")
    elif response.status_code == 200:
        _logger.debug("API call successful")
