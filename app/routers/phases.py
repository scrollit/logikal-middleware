from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime
from core.database import get_db
from schemas.phase import PhaseListResponse, PhaseResponse
from services.phase_service import PhaseService
from models.phase import Phase

router = APIRouter(prefix="/phases", tags=["phases"])


@router.get("/cached", response_model=PhaseListResponse)
async def get_cached_phases(db: Session = Depends(get_db)):
    """Get all cached phases from middleware database (no authentication required)"""
    try:
        cached_phases = db.query(Phase).all()
        from datetime import datetime, timedelta
        
        # Calculate stale phases
        from datetime import timezone
        stale_threshold = datetime.now(timezone.utc) - timedelta(hours=24)
        stale_count = sum(1 for phase in cached_phases if phase.last_sync_date and phase.last_sync_date.replace(tzinfo=timezone.utc) < stale_threshold)
        
        return PhaseListResponse(
            data=[PhaseResponse.from_orm(phase) for phase in cached_phases],
            count=len(cached_phases),
            last_updated=max([phase.last_sync_date for phase in cached_phases if phase.last_sync_date]) if cached_phases else None,
            sync_status="cached",
            stale_count=stale_count
        )
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.get("/", response_model=PhaseListResponse)
async def get_phases(
    token: str = Query(..., description="Authentication token"),
    base_url: str = Query(..., description="Logikal API base URL"),
    use_cache: bool = Query(True, description="Use cached data if available"),
    db: Session = Depends(get_db)
):
    """Get phases from Logikal API or cache"""
    try:
        # If use_cache is True, try to get from database first
        if use_cache:
            cached_phases = db.query(Phase).all()
            if cached_phases:
                return PhaseListResponse(
                    data=[PhaseResponse.from_orm(phase) for phase in cached_phases],
                    count=len(cached_phases)
                )
        
        # Get from API if no cache or cache disabled
        phase_service = PhaseService(db, token, base_url)
        success, phases_data, message = await phase_service.get_phases()
        
        if success:
            # Cache the phases
            await phase_service.cache_phases(phases_data)
            
            # Convert to response format
            phase_responses = []
            for phase_data in phases_data:
                # Extract identifier - Logikal API uses 'id' field (GUID) as identifier
                identifier = phase_data.get('id', '')
                if identifier:  # Only add phases with valid identifiers
                    phase_responses.append(PhaseResponse(
                        id=0,  # Will be set by database
                        logikal_id=identifier,
                        name=phase_data.get('name', ''),
                        description=phase_data.get('description', ''),
                        status=phase_data.get('status', ''),
                        project_id=None,  # Will be set by database
                        created_at=datetime.utcnow(),
                        updated_at=datetime.utcnow()
                    ))
            
            return PhaseListResponse(
                data=phase_responses,
                count=len(phase_responses)
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "code": "PHASE_FETCH_FAILED",
                    "message": "Failed to fetch phases",
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


@router.get("/{phase_id}", response_model=PhaseResponse)
async def get_phase(
    phase_id: str,
    token: str = Query(..., description="Authentication token"),
    base_url: str = Query(..., description="Logikal API base URL"),
    db: Session = Depends(get_db)
):
    """Get a specific phase by ID"""
    try:
        # First try to get from cache
        cached_phase = db.query(Phase).filter(
            Phase.logikal_id == phase_id
        ).first()
        
        if cached_phase:
            return PhaseResponse.from_orm(cached_phase)
        
        # If not in cache, get from API
        phase_service = PhaseService(db, token, base_url)
        success, phases_data, message = await phase_service.get_phases()
        
        if success:
            # Find the specific phase
            target_phase = None
            for phase_data in phases_data:
                identifier = phase_data.get('id', '')
                if identifier == phase_id:
                    target_phase = phase_data
                    break
            
            if target_phase:
                # Extract identifier - Logikal API uses 'id' field (GUID) as identifier
                identifier = target_phase.get('id', '')
                return PhaseResponse(
                    id=0,  # Will be set by database
                    logikal_id=identifier,
                    name=target_phase.get('name', ''),
                    description=target_phase.get('description', ''),
                    status=target_phase.get('status', ''),
                    project_id=None,  # Will be set by database
                    created_at=datetime.utcnow(),
                    updated_at=datetime.utcnow()
                )
            else:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail={
                        "code": "PHASE_NOT_FOUND",
                        "message": f"Phase with ID {phase_id} not found",
                        "details": "The requested phase does not exist"
                    }
                )
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "code": "PHASE_FETCH_FAILED",
                    "message": "Failed to fetch phases",
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


@router.post("/{phase_id}/select")
async def select_phase(
    phase_id: str,
    token: str = Query(..., description="Authentication token"),
    base_url: str = Query(..., description="Logikal API base URL"),
    db: Session = Depends(get_db)
):
    """Select a phase for further operations (required for elevations)"""
    try:
        phase_service = PhaseService(db, token, base_url)
        success, message = await phase_service.select_phase(phase_id)
        
        if success:
            return {"success": True, "message": message}
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "code": "PHASE_SELECT_FAILED",
                    "message": "Failed to select phase",
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
