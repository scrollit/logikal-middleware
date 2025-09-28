from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime
from core.database import get_db
from schemas.project import ProjectListResponse, ProjectResponse
from services.project_service import ProjectService
from models.project import Project

router = APIRouter(prefix="/projects", tags=["projects"])


@router.get("/cached", response_model=ProjectListResponse)
async def get_cached_projects(db: Session = Depends(get_db)):
    """Get all cached projects from middleware database (no authentication required)"""
    try:
        cached_projects = db.query(Project).all()
        from datetime import datetime, timedelta
        
        # Calculate stale projects
        from datetime import timezone
        stale_threshold = datetime.now(timezone.utc) - timedelta(hours=24)
        stale_count = sum(1 for project in cached_projects if project.last_sync_date and project.last_sync_date.replace(tzinfo=timezone.utc) < stale_threshold)
        
        return ProjectListResponse(
            data=[ProjectResponse.from_orm(project) for project in cached_projects],
            count=len(cached_projects),
            last_updated=max([project.last_sync_date for project in cached_projects if project.last_sync_date]) if cached_projects else None,
            sync_status="cached",
            stale_count=stale_count
        )
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.get("/", response_model=ProjectListResponse)
async def get_projects(
    token: str = Query(..., description="Authentication token"),
    base_url: str = Query(..., description="Logikal API base URL"),
    use_cache: bool = Query(True, description="Use cached data if available"),
    db: Session = Depends(get_db)
):
    """Get projects from Logikal API or cache"""
    try:
        # If use_cache is True, try to get from database first
        if use_cache:
            cached_projects = db.query(Project).all()
            if cached_projects:
                return ProjectListResponse(
                    data=[ProjectResponse.from_orm(project) for project in cached_projects],
                    count=len(cached_projects)
                )
        
        # Get from API if no cache or cache disabled
        project_service = ProjectService(db, token, base_url)
        success, projects_data, message = await project_service.get_projects()
        
        if success:
            # Cache the projects
            await project_service.cache_projects(projects_data)
            
            # Convert to response format
            project_responses = []
            for project_data in projects_data:
                # Extract identifier - Projects use 'id' field (GUID) as identifier
                identifier = project_data.get('id', '')
                if identifier:  # Only add projects with valid identifiers
                    project_responses.append(ProjectResponse(
                        id=0,  # Will be set by database
                        logikal_id=identifier,
                        name=project_data.get('name', ''),
                        description=project_data.get('description', ''),
                        status=project_data.get('status', ''),
                        directory_id=None,  # Will be set by database
                        created_at=datetime.utcnow(),
                        updated_at=datetime.utcnow()
                    ))
            
            return ProjectListResponse(
                data=project_responses,
                count=len(project_responses)
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "code": "PROJECT_FETCH_FAILED",
                    "message": "Failed to fetch projects",
                    "details": message
                }
            )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "code": "INTERNAL_ERROR",
                "message": "Internal server error",
                "details": str(e)
            }
        )


@router.get("/{project_id}", response_model=ProjectResponse)
async def get_project(
    project_id: str,
    token: str = Query(..., description="Authentication token"),
    base_url: str = Query(..., description="Logikal API base URL"),
    db: Session = Depends(get_db)
):
    """Get a specific project by ID"""
    try:
        # First try to get from cache
        cached_project = db.query(Project).filter(
            Project.logikal_id == project_id
        ).first()
        
        if cached_project:
            return ProjectResponse.from_orm(cached_project)
        
        # If not in cache, get from API
        project_service = ProjectService(db, token, base_url)
        success, projects_data, message = await project_service.get_projects()
        
        if success:
            # Find the specific project
            target_project = None
            for project_data in projects_data:
                identifier = project_data.get('id', '')
                if identifier == project_id:
                    target_project = project_data
                    break
            
            if target_project:
                # Extract identifier - Projects use 'id' field (GUID) as identifier
                identifier = target_project.get('id', '')
                return ProjectResponse(
                    id=0,  # Will be set by database
                    logikal_id=identifier,
                    name=target_project.get('name', ''),
                    description=target_project.get('description', ''),
                    status=target_project.get('status', ''),
                    directory_id=None,  # Will be set by database
                    created_at=datetime.utcnow(),
                    updated_at=datetime.utcnow()
                )
            else:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail={
                        "code": "PROJECT_NOT_FOUND",
                        "message": f"Project with ID {project_id} not found",
                        "details": "The requested project does not exist"
                    }
                )
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "code": "PROJECT_FETCH_FAILED",
                    "message": "Failed to fetch projects",
                    "details": message
                }
            )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "code": "INTERNAL_ERROR",
                "message": "Internal server error",
                "details": str(e)
            }
        )


@router.post("/{project_id}/select")
async def select_project(
    project_id: str,
    token: str = Query(..., description="Authentication token"),
    base_url: str = Query(..., description="Logikal API base URL"),
    db: Session = Depends(get_db)
):
    """Select a project for further operations"""
    try:
        project_service = ProjectService(db, token, base_url)
        success, message = await project_service.select_project(project_id)
        
        if success:
            return {"success": True, "message": message}
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "code": "PROJECT_SELECT_FAILED",
                    "message": "Failed to select project",
                    "details": message
                }
            )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "code": "INTERNAL_ERROR",
                "message": "Internal server error",
                "details": str(e)
            }
        )
