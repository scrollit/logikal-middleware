from fastapi import APIRouter, Depends, HTTPException, status, Query
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import func
from typing import List, Optional
from datetime import datetime, timedelta, timezone
import os
from core.database import get_db
from schemas.elevation import ElevationListResponse, ElevationResponse
from models.elevation import Elevation
from models.phase import Phase
from models.project import Project
from models.directory import Directory
from models.elevation_glass import ElevationGlass
# Import Celery tasks conditionally to avoid import errors in test environments
try:
    from tasks.sqlite_parser_tasks import parse_elevation_sqlite_task
except ImportError:
    parse_elevation_sqlite_task = None

router = APIRouter(prefix="/elevations", tags=["elevations"])


@router.get("/cached")
async def get_cached_elevations(
    phase_id: Optional[int] = Query(None, description="Filter by phase ID"),
    db: Session = Depends(get_db)
):
    """Get cached elevations from middleware database with hierarchy, optionally filtered by phase (no authentication required)"""
    try:
        # Get elevations with their phase, project and directory relationships
        query = db.query(Elevation).options(
            joinedload(Elevation.phase).joinedload(Phase.project).joinedload(Project.directory)
        )
        
        # Filter by phase if specified
        if phase_id is not None:
            query = query.filter(Elevation.phase_id == phase_id)
        
        cached_elevations = query.all()
        
        # Calculate stale elevations
        stale_threshold = datetime.now(timezone.utc) - timedelta(hours=24)
        stale_count = sum(1 for elevation in cached_elevations if elevation.last_sync_date and elevation.last_sync_date.replace(tzinfo=timezone.utc) < stale_threshold)
        
        # Create elevation data with hierarchy information
        elevation_data = []
        for elevation in cached_elevations:
            elevation_dict = {
                "id": elevation.id,
                "logikal_id": elevation.logikal_id,
                "name": elevation.name,
                "description": elevation.description,
                "phase_id": elevation.phase_id,
                "status": elevation.status,
                "created_at": elevation.created_at,
                "updated_at": elevation.updated_at,
                "last_sync_date": elevation.last_sync_date,
                "last_update_date": elevation.last_update_date,
                "synced_at": elevation.synced_at,
                "sync_status": elevation.sync_status,
                "image_path": elevation.image_path,
                # Parsing status fields
                "parse_status": elevation.parse_status,
                "parse_error": elevation.parse_error,
                "data_parsed_at": elevation.data_parsed_at,
                "has_parts_data": elevation.has_parts_data,
                "phase_name": elevation.phase.name if elevation.phase else "Unknown Phase",
                "project_name": elevation.phase.project.name if elevation.phase and elevation.phase.project else "Unknown Project",
                "directory_name": elevation.phase.project.directory.name if elevation.phase and elevation.phase.project and elevation.phase.project.directory else "Unknown Directory",
                "directory_id": elevation.phase.project.directory.id if elevation.phase and elevation.phase.project and elevation.phase.project.directory else None,
                "is_stale": elevation.last_sync_date and elevation.last_sync_date.replace(tzinfo=timezone.utc) < stale_threshold
            }
            elevation_data.append(elevation_dict)
        
        # Calculate last updated timestamp
        last_updated = None
        if cached_elevations:
            sync_dates = [elevation.last_sync_date for elevation in cached_elevations if elevation.last_sync_date]
            if sync_dates:
                last_updated = max(sync_dates)
        
        return {
            "success": True,
            "data": elevation_data,
            "count": len(cached_elevations),
            "last_updated": last_updated.isoformat() if last_updated else None,
            "sync_status": "cached",
            "stale_count": stale_count
        }
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.get("/{elevation_id}/image")
async def get_elevation_image(elevation_id: int, db: Session = Depends(get_db)):
    """Get elevation image by ID"""
    try:
        elevation = db.query(Elevation).filter(Elevation.id == elevation_id).first()
        
        if not elevation:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Elevation not found")
        
        if not elevation.image_path or not os.path.exists(elevation.image_path):
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Image not found")
        
        return FileResponse(
            path=elevation.image_path,
            media_type='image/jpeg',
            filename=f"elevation_{elevation_id}_{elevation.name}.jpg"
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.get("/{elevation_id}/thumbnail")
async def get_elevation_thumbnail(elevation_id: str, db: Session = Depends(get_db)):
    """Get elevation thumbnail by logikal_id"""
    try:
        # elevation_id here is actually the logikal_id (UUID string)
        elevation = db.query(Elevation).filter(Elevation.logikal_id == elevation_id).first()
        
        if not elevation:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Elevation not found")
        
        if not elevation.image_path or not os.path.exists(elevation.image_path):
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Thumbnail not found")
        
        return FileResponse(
            path=elevation.image_path,
            media_type='image/jpeg',
            filename=f"elevation_{elevation.logikal_id}_{elevation.name}_thumbnail.jpg"
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.get("/{elevation_id}/enrichment")
async def get_elevation_enrichment_status(elevation_id: int, db: Session = Depends(get_db)):
    """Get enrichment status and data for an elevation"""
    
    try:
        elevation = db.query(Elevation).options(
            joinedload(Elevation.glass_specifications)
        ).filter(Elevation.id == elevation_id).first()
        
        if not elevation:
            raise HTTPException(status_code=404, detail="Elevation not found")
        
        response_data = {
            "elevation_id": elevation_id,
            "parse_status": elevation.parse_status,
            "data_parsed_at": elevation.data_parsed_at,
            "parse_error": elevation.parse_error,
            "has_enriched_data": elevation.parse_status == 'success',
        }
        
        # Add enriched data if available
        if elevation.parse_status == 'success':
            response_data.update({
                "enriched_fields": {
                    "auto_description": elevation.auto_description,
                    "auto_description_short": elevation.auto_description_short,
                    "system_code": elevation.system_code,
                    "system_name": elevation.system_name,
                    "system_long_name": elevation.system_long_name,
                    "color_base_long": elevation.color_base_long,
                    "dimensions": {
                        "width_out": elevation.width_out,
                        "width_unit": elevation.width_unit,
                        "height_out": elevation.height_out,
                        "height_unit": elevation.height_unit,
                        "area_output": elevation.area_output,
                        "area_unit": elevation.area_unit,
                        "weight_out": elevation.weight_out,
                        "weight_unit": elevation.weight_unit
                    }
                },
                "glass_specifications": [
                    {
                        "glass_id": glass.glass_id,
                        "name": glass.name
                    }
                    for glass in elevation.glass_specifications
                ]
            })
        
        return response_data
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.post("/{elevation_id}/enrichment/trigger")
async def trigger_elevation_parsing(
    elevation_id: int,
    force: bool = False,
    db: Session = Depends(get_db)
):
    """Manually trigger parsing for an elevation"""
    
    try:
        elevation = db.query(Elevation).filter(Elevation.id == elevation_id).first()
        if not elevation:
            raise HTTPException(status_code=404, detail="Elevation not found")
        
        if not elevation.has_parts_data or not elevation.parts_db_path:
            raise HTTPException(
                status_code=400, 
                detail="Elevation does not have SQLite parts data"
            )
        
        # Check if already parsing
        if elevation.parse_status == 'in_progress' and not force:
            return {
                "success": False,
                "message": "Parsing already in progress",
                "task_id": None
            }
        
        # Trigger parsing task
        if parse_elevation_sqlite_task is None:
            return {
                "success": False,
                "message": "Celery tasks not available",
                "task_id": None
            }
        
        task = parse_elevation_sqlite_task.delay(elevation_id)
        
        return {
            "success": True,
            "message": "Parsing task triggered",
            "task_id": task.id,
            "elevation_id": elevation_id
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.get("/enrichment/status")
async def get_global_enrichment_status(db: Session = Depends(get_db)):
    """Get global enrichment status across all elevations"""
    
    try:
        # Get statistics
        total_elevations = db.query(Elevation).count()
        elevations_with_parts = db.query(Elevation).filter(
            Elevation.has_parts_data == True
        ).count()
        
        # Get parse status counts
        parse_status_counts = db.query(
            Elevation.parse_status,
            func.count(Elevation.id)
        ).filter(
            Elevation.has_parts_data == True
        ).group_by(Elevation.parse_status).all()
        
        status_summary = {status: count for status, count in parse_status_counts}
        
        # Calculate enrichment rate
        enrichment_rate = (
            status_summary.get('success', 0) / elevations_with_parts * 100
            if elevations_with_parts > 0 else 0
        )
        
        return {
            "total_elevations": total_elevations,
            "elevations_with_parts": elevations_with_parts,
            "parse_status_summary": status_summary,
            "enrichment_rate": round(enrichment_rate, 2)
        }
        
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.get("/{elevation_id}")
async def get_elevation_details(elevation_id: int, db: Session = Depends(get_db)):
    """Get detailed elevation information including enriched data"""
    
    try:
        elevation = db.query(Elevation).options(
            joinedload(Elevation.glass_specifications),
            joinedload(Elevation.phase).joinedload(Phase.project).joinedload(Project.directory)
        ).filter(Elevation.id == elevation_id).first()
        
        if not elevation:
            raise HTTPException(status_code=404, detail="Elevation not found")
        
        # Base elevation data
        base_data = {
            "id": elevation.id,
            "name": elevation.name,
            "description": elevation.description,
            "logikal_id": elevation.logikal_id,
            "status": elevation.status,
            "width": elevation.width,
            "height": elevation.height,
            "depth": elevation.depth,
            "created_at": elevation.created_at,
            "updated_at": elevation.updated_at,
            "phase_name": elevation.phase.name if elevation.phase else None,
            "project_name": elevation.phase.project.name if elevation.phase and elevation.phase.project else None,
            "directory_name": elevation.phase.project.directory.name if elevation.phase and elevation.phase.project and elevation.phase.project.directory else None
        }
        
        # Add enrichment data if available
        if elevation.parse_status == 'success':
            base_data.update({
                "enrichment": {
                    "status": elevation.parse_status,
                    "parsed_at": elevation.data_parsed_at,
                    "auto_description": elevation.auto_description,
                    "auto_description_short": elevation.auto_description_short,
                    "dimensions": {
                        "width_out": elevation.width_out,
                        "width_unit": elevation.width_unit,
                        "height_out": elevation.height_out,
                        "height_unit": elevation.height_unit,
                        "weight_out": elevation.weight_out,
                        "weight_unit": elevation.weight_unit,
                        "area_output": elevation.area_output,
                        "area_unit": elevation.area_unit
                    },
                    "system": {
                        "code": elevation.system_code,
                        "name": elevation.system_name,
                        "long_name": elevation.system_long_name,
                        "color_base": elevation.color_base_long
                    },
                    "glass_specifications": [
                        {
                            "glass_id": glass.glass_id,
                            "name": glass.name
                        }
                        for glass in elevation.glass_specifications
                    ]
                }
            })
        else:
            base_data.update({
                "enrichment": {
                    "status": elevation.parse_status,
                    "parsed_at": elevation.data_parsed_at,
                    "error": elevation.parse_error if elevation.parse_status == 'failed' else None
                }
            })
        
        return base_data
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))