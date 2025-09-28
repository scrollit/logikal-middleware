from fastapi import APIRouter, Depends, HTTPException, status, Body
from sqlalchemy.orm import Session
from typing import Dict
from core.database import get_db
from services.sync_service import SyncService
from schemas.sync import SyncRequest, SyncResponse, SyncStatusResponse

router = APIRouter(prefix="/sync", tags=["sync"])


@router.post("/directories")
async def sync_directories_ui(db: Session = Depends(get_db)):
    """Sync directories for UI (no authentication required)"""
    try:
        # Try to get stored credentials from environment or use defaults
        from core.config_production import get_settings
        settings = get_settings()
        
        sync_service = SyncService(db)
        result = await sync_service.sync_directories(
            settings.LOGIKAL_API_BASE_URL,
            settings.LOGIKAL_AUTH_USERNAME,
            settings.LOGIKAL_AUTH_PASSWORD
        )
        
        if result['success']:
            return {
                "success": True,
                "message": result['message'],
                "directories_processed": result.get('directories_processed', 0)
            }
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=result['message']
            )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.post("/directories/concurrent")
async def sync_directories_concurrent_ui(db: Session = Depends(get_db)):
    """Sync directories concurrently with 2 workers for UI (no authentication required)"""
    try:
        # Try to get stored credentials from environment or use defaults
        from core.config_production import get_settings
        settings = get_settings()
        
        sync_service = SyncService(db)
        result = await sync_service.sync_directories_concurrent(
            settings.LOGIKAL_API_BASE_URL,
            settings.LOGIKAL_AUTH_USERNAME,
            settings.LOGIKAL_AUTH_PASSWORD
        )
        
        if result['success']:
            return {
                "success": True,
                "message": result['message'],
                "directories_processed": result.get('directories_processed', 0),
                "concurrent_workers": result.get('concurrent_workers', 2),
                "duration_seconds": result.get('duration_seconds', 0)
            }
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=result['message']
            )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.post("/test/concurrency-limits")
async def test_concurrency_limits(db: Session = Depends(get_db)):
    """Test optimal concurrent request limits (no authentication required)"""
    try:
        from core.config_production import get_settings
        from services.concurrency_test_service import ConcurrencyTestService
        
        settings = get_settings()
        
        test_service = ConcurrencyTestService(db)
        result = await test_service.test_concurrent_limits(
            settings.LOGIKAL_API_BASE_URL,
            settings.LOGIKAL_AUTH_USERNAME,
            settings.LOGIKAL_AUTH_PASSWORD,
            max_workers=8  # Conservative test limit
        )
        
        return {
            "success": True,
            "message": "Concurrency limit testing completed",
            "test_results": result.get('test_results', []),
            "optimal_analysis": result.get('optimal_analysis', {}),
            "recommendation": result.get('recommendation', {})
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.post("/directories/optimized")
async def sync_directories_optimized_ui(db: Session = Depends(get_db)):
    """Sync directories with optimized batch operations (no authentication required)"""
    try:
        from core.config_production import get_settings
        
        settings = get_settings()
        
        sync_service = SyncService(db)
        result = await sync_service.sync_directories_optimized(
            settings.LOGIKAL_API_BASE_URL,
            settings.LOGIKAL_AUTH_USERNAME,
            settings.LOGIKAL_AUTH_PASSWORD
        )
        
        if result['success']:
            return {
                "success": True,
                "message": result['message'],
                "directories_processed": result.get('directories_processed', 0),
                "duration_seconds": result.get('duration_seconds', 0),
                "optimization": result.get('optimization', 'batch_operations')
            }
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=result['message']
            )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.post("/projects")
async def sync_projects_ui(db: Session = Depends(get_db)):
    """Sync projects for UI (no authentication required)"""
    try:
        from core.config_production import get_settings
        settings = get_settings()
        
        sync_service = SyncService(db)
        result = await sync_service.sync_projects(
            settings.LOGIKAL_API_BASE_URL,
            settings.LOGIKAL_AUTH_USERNAME,
            settings.LOGIKAL_AUTH_PASSWORD
        )
        
        if result['success']:
            return {
                "success": True,
                "message": result['message'],
                "projects_processed": result.get('projects_processed', 0)
            }
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=result['message']
            )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.post("/phases")
async def sync_phases_ui(db: Session = Depends(get_db)):
    """Sync phases for UI (no authentication required)"""
    try:
        from core.config_production import get_settings
        settings = get_settings()
        
        sync_service = SyncService(db)
        result = await sync_service.sync_phases(
            settings.LOGIKAL_API_BASE_URL,
            settings.LOGIKAL_AUTH_USERNAME,
            settings.LOGIKAL_AUTH_PASSWORD
        )
        
        if result['success']:
            return {
                "success": True,
                "message": result['message'],
                "phases_processed": result.get('phases_processed', 0)
            }
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=result['message']
            )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.post("/elevations")
async def sync_elevations_ui(db: Session = Depends(get_db)):
    """Sync elevations for UI (no authentication required)"""
    try:
        from core.config_production import get_settings
        settings = get_settings()
        
        sync_service = SyncService(db)
        result = await sync_service.sync_elevations(
            settings.LOGIKAL_API_BASE_URL,
            settings.LOGIKAL_AUTH_USERNAME,
            settings.LOGIKAL_AUTH_PASSWORD
        )
        
        if result['success']:
            return {
                "success": True,
                "message": result['message'],
                "elevations_processed": result.get('elevations_processed', 0)
            }
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=result['message']
            )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.post("/full", response_model=SyncResponse)
async def trigger_full_sync(
    request: SyncRequest = Body(...),
    db: Session = Depends(get_db)
):
    """Trigger a full sync operation"""
    try:
        sync_service = SyncService(db)
        result = await sync_service.full_sync(
            request.base_url, 
            request.username, 
            request.password
        )
        
        if result['success']:
            return SyncResponse(
                success=True,
                message=result['message'],
                duration_seconds=result['duration_seconds'],
                directories_processed=result.get('directories_processed', 0),
                projects_processed=result.get('projects_processed', 0),
                phases_processed=result.get('phases_processed', 0),
                elevations_processed=result.get('elevations_processed', 0),
                total_items=result.get('total_items', 0)
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "code": "FULL_SYNC_FAILED",
                    "message": "Full sync failed",
                    "details": result['message'],
                    "error": result.get('error')
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


@router.post("/incremental", response_model=SyncResponse)
async def trigger_incremental_sync(
    request: SyncRequest = Body(...),
    db: Session = Depends(get_db)
):
    """Trigger an incremental sync operation"""
    try:
        sync_service = SyncService(db)
        result = await sync_service.incremental_sync(
            request.base_url, 
            request.username, 
            request.password
        )
        
        if result['success']:
            return SyncResponse(
                success=True,
                message=result['message'],
                duration_seconds=result['duration_seconds'],
                directories_processed=result.get('directories_processed', 0),
                projects_processed=result.get('projects_processed', 0),
                phases_processed=result.get('phases_processed', 0),
                elevations_processed=result.get('elevations_processed', 0),
                total_items=result.get('total_items', 0)
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "code": "INCREMENTAL_SYNC_FAILED",
                    "message": "Incremental sync failed",
                    "details": result['message'],
                    "error": result.get('error')
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


@router.get("/status", response_model=SyncStatusResponse)
async def get_sync_status(
    db: Session = Depends(get_db)
):
    """Get current sync status and configuration"""
    try:
        sync_service = SyncService(db)
        result = await sync_service.get_sync_status()
        
        if result['success']:
            return SyncStatusResponse(
                success=True,
                sync_config=result['sync_config'],
                recent_logs=result['recent_logs']
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "code": "SYNC_STATUS_FAILED",
                    "message": "Failed to get sync status",
                    "details": result['message']
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
