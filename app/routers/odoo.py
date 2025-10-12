from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from core.database import get_db
from services.direct_project_service import DirectProjectService
from services.smart_sync_service import SmartSyncService
from core.security import require_permission, get_current_client, require_projects_read, require_elevations_read
from schemas.odoo.project_response import (
    OdooProjectListResponse, OdooProjectResponse, OdooProjectCompleteResponse,
    OdooProjectSummaryResponse, OdooSearchResponse, OdooStatsResponse,
    OdooPhaseResponse, OdooElevationResponse, OdooGlassSpecification
)
from models.project import Project
from models.phase import Phase
from models.elevation import Elevation

router = APIRouter(prefix="/odoo", tags=["odoo-integration"])


@router.get("/projects", response_model=OdooProjectListResponse)
async def get_all_projects_for_odoo(
    current_client: dict = Depends(require_projects_read),
    db: Session = Depends(get_db)
):
    """Get all projects for Odoo (no Logikal credentials needed)"""
    try:
        direct_service = DirectProjectService(db)
        projects = await direct_service.get_all_projects()
        
        # Convert to Odoo-friendly format
        project_summaries = []
        for project in projects:
            # Get phase and elevation counts
            phases_count = db.query(Phase).filter(Phase.project_id == project.id).count()
            total_elevations = 0
            for phase in db.query(Phase).filter(Phase.project_id == project.id).all():
                total_elevations += db.query(Elevation).filter(Elevation.phase_id == phase.id).count()
            
            project_summaries.append(OdooProjectSummaryResponse(
                id=project.logikal_id,
                name=project.name,
                description=project.description,
                status=project.status,
                phases_count=phases_count,
                total_elevations=total_elevations,
                created_at=project.created_at
            ))
        
        return OdooProjectListResponse(
            projects=project_summaries,
            count=len(project_summaries),
            summary={
                "total_projects": len(project_summaries),
                "client_id": current_client["client_id"]
            }
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "code": "INTERNAL_ERROR",
                "message": "Internal server error",
                "details": str(e)
            }
        )


@router.get("/projects/{project_id}", response_model=OdooProjectResponse)
async def get_project_for_odoo(
    project_id: str,
    current_client: dict = Depends(require_projects_read),
    db: Session = Depends(get_db)
):
    """Get a specific project for Odoo"""
    try:
        direct_service = DirectProjectService(db)
        project_data = await direct_service.get_project_with_phases(project_id)
        
        if not project_data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={
                    "code": "PROJECT_NOT_FOUND",
                    "message": f"Project with ID '{project_id}' not found"
                }
            )
        
        project = project_data["project"]
        phases = project_data["phases"]
        
        # Convert phases to Odoo format
        odoo_phases = []
        total_elevations = 0
        
        for phase in phases:
            elevations = db.query(Elevation).filter(Elevation.phase_id == phase.id).all()
            total_elevations += len(elevations)
            
            odoo_elevations = [
                OdooElevationResponse(
                    # Existing fields (maintain backward compatibility)
                    id=elevation.logikal_id,
                    name=elevation.name,
                    description=elevation.description,
                    phase_id=phase.logikal_id,
                    thumbnail_url=f"/api/v1/elevations/{elevation.logikal_id}/thumbnail",
                    width=elevation.width,
                    height=elevation.height,
                    depth=elevation.depth,
                    created_at=elevation.created_at,
                    
                    # NEW: SQLite enrichment data
                    auto_description=elevation.auto_description,
                    auto_description_short=elevation.auto_description_short,
                    width_out=elevation.width_out,
                    width_unit=elevation.width_unit,
                    height_out=elevation.height_out,
                    height_unit=elevation.height_unit,
                    weight_out=elevation.weight_out,
                    weight_unit=elevation.weight_unit,
                    area_output=elevation.area_output,
                    area_unit=elevation.area_unit,
                    
                    # NEW: System information
                    system_code=elevation.system_code,
                    system_name=elevation.system_name,
                    system_long_name=elevation.system_long_name,
                    color_base_long=elevation.color_base_long,
                    
                    # NEW: Parts information
                    parts_count=elevation.parts_count,
                    has_parts_data=elevation.has_parts_data,
                    parts_synced_at=elevation.parts_synced_at,
                    
                    # NEW: Quality metrics
                    parse_status=elevation.parse_status,
                    data_quality_score=elevation.calculate_data_quality_score(),
                    
                    # NEW: Glass specifications
                    glass_specifications=[
                        OdooGlassSpecification(
                            glass_id=glass.glass_id,
                            name=glass.name
                        ) for glass in elevation.glass_specifications
                    ],
                    
                    # NEW: Enhanced timestamps
                    last_sync_date=elevation.last_sync_date,
                    last_update_date=elevation.last_update_date
                )
                for elevation in elevations
            ]
            
            odoo_phases.append(OdooPhaseResponse(
                id=phase.logikal_id,
                name=phase.name,
                description=phase.description,
                project_id=project.logikal_id,
                status=phase.status,
                elevations_count=len(elevations),
                elevations=odoo_elevations,
                created_at=phase.created_at
            ))
        
        return OdooProjectResponse(
            id=project.logikal_id,
            name=project.name,
            description=project.description,
            status=project.status,
            phases_count=len(phases),
            total_elevations=total_elevations,
            phases=odoo_phases,
            created_at=project.created_at
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


@router.get("/projects/{project_id}/complete", response_model=OdooProjectCompleteResponse)
async def get_project_complete_for_odoo(
    project_id: str,
    auto_sync: bool = Query(True, description="Automatically sync if data is stale"),
    current_client: dict = Depends(require_permission("projects:read")),
    db: Session = Depends(get_db)
):
    """Get complete project data for Odoo (project + phases + elevations) with smart sync"""
    try:
        # Check if smart sync is needed
        if auto_sync:
            sync_service = SmartSyncService(db)
            sync_result = sync_service.sync_project_if_needed(project_id)
            if not sync_result["success"]:
                logger.warning(f"Smart sync failed for project {project_id}: {sync_result.get('error')}")
        
        direct_service = DirectProjectService(db)
        complete_data = await direct_service.get_project_complete(project_id)
        
        if not complete_data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={
                    "code": "PROJECT_NOT_FOUND",
                    "message": f"Project with ID '{project_id}' not found"
                }
            )
        
        project = complete_data["project"]
        phases_with_elevations = complete_data["phases_with_elevations"]
        
        # Convert to Odoo format
        odoo_phases = []
        total_elevations = 0
        
        for phase_data in phases_with_elevations:
            phase = phase_data["phase"]
            elevations = phase_data["elevations"]
            total_elevations += len(elevations)
            
            odoo_elevations = [
                OdooElevationResponse(
                    # Existing fields (maintain backward compatibility)
                    id=elevation.logikal_id,
                    name=elevation.name,
                    description=elevation.description,
                    phase_id=phase.logikal_id,
                    thumbnail_url=f"/api/v1/elevations/{elevation.logikal_id}/thumbnail",
                    width=elevation.width,
                    height=elevation.height,
                    depth=elevation.depth,
                    created_at=elevation.created_at,
                    
                    # NEW: SQLite enrichment data
                    auto_description=elevation.auto_description,
                    auto_description_short=elevation.auto_description_short,
                    width_out=elevation.width_out,
                    width_unit=elevation.width_unit,
                    height_out=elevation.height_out,
                    height_unit=elevation.height_unit,
                    weight_out=elevation.weight_out,
                    weight_unit=elevation.weight_unit,
                    area_output=elevation.area_output,
                    area_unit=elevation.area_unit,
                    
                    # NEW: System information
                    system_code=elevation.system_code,
                    system_name=elevation.system_name,
                    system_long_name=elevation.system_long_name,
                    color_base_long=elevation.color_base_long,
                    
                    # NEW: Parts information
                    parts_count=elevation.parts_count,
                    has_parts_data=elevation.has_parts_data,
                    parts_synced_at=elevation.parts_synced_at,
                    
                    # NEW: Quality metrics
                    parse_status=elevation.parse_status,
                    data_quality_score=elevation.calculate_data_quality_score(),
                    
                    # NEW: Glass specifications
                    glass_specifications=[
                        OdooGlassSpecification(
                            glass_id=glass.glass_id,
                            name=glass.name
                        ) for glass in elevation.glass_specifications
                    ],
                    
                    # NEW: Enhanced timestamps
                    last_sync_date=elevation.last_sync_date,
                    last_update_date=elevation.last_update_date
                )
                for elevation in elevations
            ]
            
            odoo_phases.append(OdooPhaseResponse(
                id=phase.logikal_id,
                name=phase.name,
                description=phase.description,
                project_id=project.logikal_id,
                status=phase.status,
                elevations_count=len(elevations),
                elevations=odoo_elevations,
                created_at=phase.created_at
            ))
        
        odoo_project = OdooProjectResponse(
            id=project.logikal_id,
            name=project.name,
            description=project.description,
            status=project.status,
            phases_count=len(phases_with_elevations),
            total_elevations=total_elevations,
            phases=odoo_phases,
            created_at=project.created_at
        )
        
        # Convert phases_with_elevations to serializable format
        serializable_phases = []
        for phase_data in phases_with_elevations:
            phase = phase_data["phase"]
            elevations = phase_data["elevations"]
            
            serializable_phases.append({
                "phase": {
                    "id": phase.logikal_id,
                    "name": phase.name,
                    "description": phase.description,
                    "status": phase.status
                },
                "elevations": [
                    {
                        "id": elev.logikal_id,
                        "name": elev.name,
                        "description": elev.description
                    } for elev in elevations
                ],
                "elevations_count": len(elevations)
            })
        
        return OdooProjectCompleteResponse(
            project=odoo_project,
            phases_with_elevations=serializable_phases,
            summary=complete_data["summary"]
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


@router.get("/projects/{project_id}/phases", response_model=List[OdooPhaseResponse])
async def get_project_phases_for_odoo(
    project_id: str,
    current_client: dict = Depends(require_projects_read),
    db: Session = Depends(get_db)
):
    """Get all phases for a specific project"""
    try:
        direct_service = DirectProjectService(db)
        project_data = await direct_service.get_project_with_phases(project_id)
        
        if not project_data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={
                    "code": "PROJECT_NOT_FOUND",
                    "message": f"Project with ID '{project_id}' not found"
                }
            )
        
        phases = project_data["phases"]
        project = project_data["project"]
        odoo_phases = []
        
        for phase in phases:
            elevations_count = db.query(Elevation).filter(Elevation.phase_id == phase.id).count()
            
            odoo_phases.append(OdooPhaseResponse(
                id=phase.logikal_id,
                name=phase.name,
                description=phase.description,
                project_id=project.logikal_id,
                status=phase.status,
                elevations_count=elevations_count,
                elevations=[],  # Don't include elevations in this endpoint
                created_at=phase.created_at
            ))
        
        return odoo_phases
        
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


@router.get("/projects/{project_id}/phases/{phase_id}/elevations", response_model=List[OdooElevationResponse])
async def get_phase_elevations_for_odoo(
    project_id: str,
    phase_id: str,
    current_client: dict = Depends(require_elevations_read),
    db: Session = Depends(get_db)
):
    """Get all elevations for a specific phase"""
    try:
        direct_service = DirectProjectService(db)
        phase_data = await direct_service.get_phase_with_elevations_by_project(project_id, phase_id)
        
        if not phase_data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={
                    "code": "PHASE_NOT_FOUND",
                    "message": f"Phase with ID '{phase_id}' not found in project '{project_id}'"
                }
            )
        
        elevations = phase_data["elevations"]
        phase = phase_data["phase"]
        odoo_elevations = []
        
        for elevation in elevations:
            odoo_elevations.append(OdooElevationResponse(
                # Existing fields (maintain backward compatibility)
                id=elevation.logikal_id,
                name=elevation.name,
                description=elevation.description,
                phase_id=phase.logikal_id,
                thumbnail_url=f"/api/v1/elevations/{elevation.logikal_id}/thumbnail",
                width=elevation.width,
                height=elevation.height,
                depth=elevation.depth,
                created_at=elevation.created_at,
                
                # NEW: SQLite enrichment data
                auto_description=elevation.auto_description,
                auto_description_short=elevation.auto_description_short,
                width_out=elevation.width_out,
                width_unit=elevation.width_unit,
                height_out=elevation.height_out,
                height_unit=elevation.height_unit,
                weight_out=elevation.weight_out,
                weight_unit=elevation.weight_unit,
                area_output=elevation.area_output,
                area_unit=elevation.area_unit,
                
                # NEW: System information
                system_code=elevation.system_code,
                system_name=elevation.system_name,
                system_long_name=elevation.system_long_name,
                color_base_long=elevation.color_base_long,
                
                # NEW: Parts information
                parts_count=elevation.parts_count,
                has_parts_data=elevation.has_parts_data,
                parts_synced_at=elevation.parts_synced_at,
                
                # NEW: Quality metrics
                parse_status=elevation.parse_status,
                data_quality_score=elevation.calculate_data_quality_score(),
                
                # NEW: Glass specifications
                glass_specifications=[
                    OdooGlassSpecification(
                        glass_id=glass.glass_id,
                        name=glass.name
                    ) for glass in elevation.glass_specifications
                ],
                
                # NEW: Enhanced timestamps
                last_sync_date=elevation.last_sync_date,
                last_update_date=elevation.last_update_date
            ))
        
        return odoo_elevations
        
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


@router.get("/search", response_model=OdooSearchResponse)
async def search_projects_for_odoo(
    q: str = Query(..., description="Search query"),
    current_client: dict = Depends(require_projects_read),
    db: Session = Depends(get_db)
):
    """Search projects by name or description"""
    try:
        direct_service = DirectProjectService(db)
        projects = await direct_service.search_projects(q)
        
        # Convert to Odoo format
        project_summaries = []
        for project in projects:
            phases_count = db.query(Phase).filter(Phase.project_id == project.id).count()
            total_elevations = 0
            for phase in db.query(Phase).filter(Phase.project_id == project.id).all():
                total_elevations += db.query(Elevation).filter(Elevation.phase_id == phase.id).count()
            
            project_summaries.append(OdooProjectSummaryResponse(
                id=project.logikal_id,
                name=project.name,
                description=project.description,
                status=project.status,
                phases_count=phases_count,
                total_elevations=total_elevations,
                created_at=project.created_at
            ))
        
        return OdooSearchResponse(
            results=project_summaries,
            query=q,
            count=len(project_summaries)
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "code": "INTERNAL_ERROR",
                "message": "Internal server error",
                "details": str(e)
            }
        )


@router.get("/stats", response_model=OdooStatsResponse)
async def get_project_stats_for_odoo(
    current_client: dict = Depends(require_projects_read),
    db: Session = Depends(get_db)
):
    """Get project statistics"""
    try:
        direct_service = DirectProjectService(db)
        stats = await direct_service.get_projects_summary()
        
        return OdooStatsResponse(
            total_projects=stats["total_projects"],
            total_phases=stats["total_phases"],
            total_elevations=stats["total_elevations"],
            projects=stats["projects"]
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "code": "INTERNAL_ERROR",
                "message": "Internal server error",
                "details": str(e)
            }
        )
