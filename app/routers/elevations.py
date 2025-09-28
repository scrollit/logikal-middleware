from fastapi import APIRouter, Depends, HTTPException, status, Query
from fastapi.responses import Response
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime
import base64
from core.database import get_db
from schemas.elevation import ElevationListResponse, ElevationResponse
from services.elevation_service import ElevationService
from models.elevation import Elevation

router = APIRouter(prefix="/elevations", tags=["elevations"])


@router.get("/cached", response_model=ElevationListResponse)
async def get_cached_elevations(db: Session = Depends(get_db)):
    """Get all cached elevations from middleware database (no authentication required)"""
    try:
        cached_elevations = db.query(Elevation).all()
        from datetime import datetime, timedelta
        
        # Calculate stale elevations
        from datetime import timezone
        stale_threshold = datetime.now(timezone.utc) - timedelta(hours=24)
        stale_count = sum(1 for elevation in cached_elevations if elevation.last_sync_date and elevation.last_sync_date.replace(tzinfo=timezone.utc) < stale_threshold)
        
        return ElevationListResponse(
            data=[ElevationResponse.from_orm(elevation) for elevation in cached_elevations],
            count=len(cached_elevations),
            last_updated=max([elevation.last_sync_date for elevation in cached_elevations if elevation.last_sync_date]) if cached_elevations else None,
            sync_status="cached",
            stale_count=stale_count
        )
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.get("/", response_model=ElevationListResponse)
async def get_elevations(
    token: str = Query(..., description="Authentication token"),
    base_url: str = Query(..., description="Logikal API base URL"),
    use_cache: bool = Query(True, description="Use cached data if available"),
    db: Session = Depends(get_db)
):
    """Get elevations from Logikal API or cache"""
    try:
        # If use_cache is True, try to get from database first
        if use_cache:
            cached_elevations = db.query(Elevation).all()
            if cached_elevations:
                return ElevationListResponse(
                    data=[ElevationResponse.from_orm(elevation) for elevation in cached_elevations],
                    count=len(cached_elevations)
                )
        
        # Get from API if no cache or cache disabled
        elevation_service = ElevationService(db, token, base_url)
        success, elevations_data, message = await elevation_service.get_elevations()
        
        if success:
            # Cache the elevations
            await elevation_service.cache_elevations(elevations_data)
            
            # Convert to response format
            elevation_responses = []
            for elevation_data in elevations_data:
                # Extract identifier - Logikal API uses 'id' field (GUID) as identifier
                identifier = elevation_data.get('id', '')
                if identifier:  # Only add elevations with valid identifiers
                    elevation_responses.append(ElevationResponse(
                        id=0,  # Will be set by database
                        logikal_id=identifier,
                        name=elevation_data.get('name', ''),
                        description=elevation_data.get('description', ''),
                        phase_id=elevation_data.get('phase_id', ''),
                        width=elevation_data.get('width'),
                        height=elevation_data.get('height'),
                        depth=elevation_data.get('depth'),
                        project_id=None,  # Will be set by database
                        thumbnail_url=None,  # Will be set by database
                        created_at=datetime.utcnow(),
                        updated_at=datetime.utcnow()
                    ))
            
            return ElevationListResponse(
                data=elevation_responses,
                count=len(elevation_responses)
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "code": "ELEVATION_FETCH_FAILED",
                    "message": "Failed to fetch elevations",
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


@router.get("/{elevation_id}", response_model=ElevationResponse)
async def get_elevation(
    elevation_id: str,
    token: str = Query(..., description="Authentication token"),
    base_url: str = Query(..., description="Logikal API base URL"),
    db: Session = Depends(get_db)
):
    """Get a specific elevation by ID"""
    try:
        # First try to get from cache
        cached_elevation = db.query(Elevation).filter(
            Elevation.logikal_id == elevation_id
        ).first()
        
        if cached_elevation:
            return ElevationResponse.from_orm(cached_elevation)
        
        # If not in cache, get from API
        elevation_service = ElevationService(db, token, base_url)
        success, elevations_data, message = await elevation_service.get_elevations()
        
        if success:
            # Find the specific elevation
            target_elevation = None
            for elevation_data in elevations_data:
                identifier = elevation_data.get('id', '')
                if identifier == elevation_id:
                    target_elevation = elevation_data
                    break
            
            if target_elevation:
                # Extract identifier - Logikal API uses 'id' field (GUID) as identifier
                identifier = target_elevation.get('id', '')
                return ElevationResponse(
                    id=0,  # Will be set by database
                    logikal_id=identifier,
                    name=target_elevation.get('name', ''),
                    description=target_elevation.get('description', ''),
                    phase_id=target_elevation.get('phase_id', ''),
                    width=target_elevation.get('width'),
                    height=target_elevation.get('height'),
                    depth=target_elevation.get('depth'),
                    project_id=None,  # Will be set by database
                    thumbnail_url=None,  # Will be set by database
                    created_at=datetime.utcnow(),
                    updated_at=datetime.utcnow()
                )
            else:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail={
                        "code": "ELEVATION_NOT_FOUND",
                        "message": f"Elevation with ID {elevation_id} not found",
                        "details": "The requested elevation does not exist"
                    }
                )
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "code": "ELEVATION_FETCH_FAILED",
                    "message": "Failed to fetch elevations",
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


@router.get("/{elevation_id}/thumbnail")
async def get_elevation_thumbnail(
    elevation_id: str,
    token: str = Query(..., description="Authentication token"),
    base_url: str = Query(..., description="Logikal API base URL"),
    width: int = Query(300, description="Thumbnail width in pixels"),
    height: int = Query(300, description="Thumbnail height in pixels"),
    format: str = Query("PNG", description="Image format (PNG, JPG, EMF)"),
    view: str = Query("Exterior", description="Viewpoint (Interior, Exterior)"),
    withdimensions: str = Query("true", description="Include dimensions"),
    withdescription: str = Query("false", description="Include description"),
    db: Session = Depends(get_db)
):
    """Get thumbnail for a specific elevation"""
    try:
        elevation_service = ElevationService(db, token, base_url)
        success, thumbnail_data, message = await elevation_service.get_elevation_thumbnail(
            elevation_id, width, height, format, view, withdimensions, withdescription
        )
        
        if success:
            # Decode base64 data and return as image
            image_data = base64.b64decode(thumbnail_data)
            media_type = "image/png" if format.upper() == "PNG" else "image/jpeg"
            return Response(content=image_data, media_type=media_type)
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "code": "THUMBNAIL_FETCH_FAILED",
                    "message": "Failed to fetch thumbnail",
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
