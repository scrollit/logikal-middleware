import aiohttp
import time
import logging
from typing import List, Optional, Tuple
from sqlalchemy.orm import Session
from core.retry import retry_async, default_retry_config, api_rate_limiter
from models.project import Project
from models.api_log import ApiLog
from schemas.project import ProjectCreate

logger = logging.getLogger(__name__)


class ProjectService:
    """Service for handling Logikal project operations"""
    
    def __init__(self, db: Session, session_token: str, base_url: str):
        self.db = db
        self.session_token = session_token
        self.base_url = base_url.rstrip('/')
        self.current_project: Optional[str] = None
        
    @retry_async(config=default_retry_config, rate_limiter=api_rate_limiter)
    async def _get_projects_request(self, url: str, headers: dict) -> Tuple[bool, List[dict], str]:
        """Internal method to make the actual projects request with retry logic"""
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers, timeout=30) as response:
                response_text = await response.text()
                
                if response.status == 200:
                    data = await response.json()
                    projects = data.get('data', []) if isinstance(data, dict) else data
                    return True, projects, "Success"
                else:
                    error_msg = f"Failed to get projects: {response.status} - {response_text}"
                    raise Exception(error_msg)
    
    async def get_projects(self) -> Tuple[bool, List[dict], str]:
        """Get projects from current selected directory context"""
        if not self.session_token:
            return False, [], "No active session. Please authenticate first."
        
        url = f"{self.base_url}/projects"
        start_time = time.time()
        logger.info("Fetching projects from Logikal API")
        
        try:
            headers = {"Authorization": f"Bearer {self.session_token}"}
            success, projects, message = await self._get_projects_request(url, headers)
            duration = int((time.time() - start_time) * 1000)
            
            if success:
                logger.info(f"Retrieved {len(projects)} projects")
                
                # Log successful operation
                await self._log_api_call(
                    operation='get_projects',
                    status='success',
                    response_code=200,
                    duration=duration,
                    request_url=url,
                    request_method='GET',
                    response_body=str(projects),
                    response_summary=f"Retrieved {len(projects)} projects"
                )
                
                return True, projects, "Success"
            else:
                return False, [], message
                        
        except Exception as e:
            duration = int((time.time() - start_time) * 1000)
            error_msg = f"Error while getting projects: {str(e)}"
            logger.error(error_msg)
            await self._log_api_call(
                operation='get_projects',
                status='failed',
                response_code=0,
                error_message=error_msg,
                duration=duration,
                request_url=url,
                request_method='GET',
                response_body=None,
                response_summary="Error while getting projects"
            )
            return False, [], error_msg
    
    @retry_async(config=default_retry_config, rate_limiter=api_rate_limiter)
    async def _select_project_request(self, url: str, payload: dict, headers: dict) -> Tuple[bool, str]:
        """Internal method to make the actual project selection request with retry logic"""
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=payload, headers=headers, timeout=30) as response:
                response_text = await response.text()
                
                if response.status == 200:
                    return True, "Project selected successfully"
                else:
                    error_msg = f"Failed to select project: {response.status} - {response_text}"
                    raise Exception(error_msg)
    
    async def select_project(self, project_identifier: str) -> Tuple[bool, str]:
        """Select a project by identifier (required for phase/elevation operations)"""
        url = f"{self.base_url}/projects/select"
        payload = {"identifier": project_identifier}
        start_time = time.time()
        logger.info(f"Selecting project: {project_identifier}")
        
        try:
            headers = {"Authorization": f"Bearer {self.session_token}"}
            success, message = await self._select_project_request(url, payload, headers)
            duration = int((time.time() - start_time) * 1000)
            
            if success:
                logger.info(f"Successfully selected project: {project_identifier}")
                
                # Track navigation state
                self.current_project = project_identifier
                
                # Clear cached data when project changes - DISABLED to prevent sync data loss
                # await self._clear_cached_data()
                
                # Log successful operation
                await self._log_api_call(
                    operation='select_project',
                    status='success',
                    response_code=200,
                    duration=duration,
                    request_url=url,
                    request_method='POST',
                    request_payload=payload,
                    response_body=message,
                    response_summary=f"Selected project: {project_identifier}"
                )
                
                return True, "Project selected successfully"
            else:
                return False, message
                        
        except Exception as e:
            duration = int((time.time() - start_time) * 1000)
            error_msg = f"Error while selecting project {project_identifier}: {str(e)}"
            logger.error(error_msg)
            await self._log_api_call(
                operation='select_project',
                status='failed',
                response_code=0,
                error_message=error_msg,
                duration=duration,
                request_url=url,
                request_method='POST',
                request_payload=payload,
                response_body=None,
                response_summary=f"Error selecting project {project_identifier}"
            )
            return False, error_msg
    
    async def _clear_cached_data(self):
        """Clear cached data when context changes"""
        try:
            # Clear phases and elevations when project changes
            from models.phase import Phase
            from models.elevation import Elevation
            
            self.db.query(Phase).delete()
            self.db.query(Elevation).delete()
            self.db.commit()
            logger.info("Cleared cached phases and elevations due to project change")
        except Exception as e:
            logger.error(f"Failed to clear cached data: {str(e)}")
            self.db.rollback()
    
    async def cache_projects(self, projects: List[dict]) -> bool:
        """Cache projects in PostgreSQL database"""
        try:
            for project_data in projects:
                # Extract identifier - Projects use 'id' field (GUID) as identifier
                identifier = project_data.get('id', '')
                
                # Skip projects without valid identifiers
                if not identifier:
                    logger.warning(f"Skipping project without identifier: {project_data}")
                    continue
                
                # Check if project already exists
                existing_project = self.db.query(Project).filter(
                    Project.logikal_id == identifier
                ).first()
                
                if existing_project:
                    # Update existing project
                    existing_project.name = project_data.get('name', existing_project.name)
                    existing_project.description = project_data.get('description', existing_project.description)
                    existing_project.status = project_data.get('status', existing_project.status)
                else:
                    # Create new project
                    new_project = Project(
                        logikal_id=identifier,
                        name=project_data.get('name', ''),
                        description=project_data.get('description', ''),
                        status=project_data.get('status', '')
                    )
                    self.db.add(new_project)
            
            self.db.commit()
            logger.info(f"Cached {len(projects)} projects in database")
            return True
            
        except Exception as e:
            logger.error(f"Failed to cache projects: {str(e)}")
            self.db.rollback()
            return False
    
    async def get_cached_projects(self) -> List[Project]:
        """Get projects from database cache"""
        try:
            projects = self.db.query(Project).all()
            logger.info(f"Retrieved {len(projects)} cached projects")
            return projects
        except Exception as e:
            logger.error(f"Failed to get cached projects: {str(e)}")
            return []
    
    async def _log_api_call(self, operation: str, status: str, response_code: int, 
                           duration: int, request_url: str = None, request_method: str = None,
                           request_payload: dict = None, response_body: str = None,
                           response_summary: str = None, error_message: str = None):
        """Log API call to database"""
        try:
            # Extract endpoint from URL
            endpoint = request_url.split('/')[-1] if request_url else operation
            
            api_log = ApiLog(
                endpoint=endpoint,
                method=request_method or 'GET',
                status_code=response_code,
                response_time_ms=duration,
                success=(status == 'success'),
                error_message=error_message,
                request_url=request_url,
                request_method=request_method,
                request_payload=str(request_payload) if request_payload else None,
                response_body=response_body,
                response_summary=response_summary
            )
            
            self.db.add(api_log)
            # DO NOT commit or rollback - let the main transaction handle it
            
        except Exception as e:
            logger.error(f"Failed to log API call: {str(e)}")
            # DO NOT rollback - let the main transaction handle it
