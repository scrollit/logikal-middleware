from fastapi import APIRouter, Depends, HTTPException, status, Query, Body
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime
from core.database import get_db
from schemas.directory import (
    DirectoryListResponse, DirectoryResponse, DirectoryExclusionRequest, 
    DirectoryBulkExclusionRequest
)
from services.directory_service import DirectoryService
from models.directory import Directory

router = APIRouter(prefix="/directories", tags=["directories"])


@router.get("/cached", response_model=DirectoryListResponse)
async def get_cached_directories(db: Session = Depends(get_db)):
    """Get all cached directories from middleware database (no authentication required)"""
    try:
        cached_directories = db.query(Directory).all()
        return DirectoryListResponse(
            data=[DirectoryResponse.from_orm(dir_obj) for dir_obj in cached_directories],
            count=len(cached_directories),
            last_updated=max([dir_obj.synced_at for dir_obj in cached_directories if dir_obj.synced_at]) if cached_directories else None,
            sync_status="cached"
        )
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.get("/", response_model=DirectoryListResponse)
async def get_directories(
    token: str = Query(..., description="Authentication token"),
    base_url: str = Query(..., description="Logikal API base URL"),
    use_cache: bool = Query(True, description="Use cached data if available"),
    db: Session = Depends(get_db)
):
    """Get directories from Logikal API or cache"""
    try:
        # If use_cache is True, try to get from database first
        if use_cache:
            cached_directories = db.query(Directory).all()
            if cached_directories:
                return DirectoryListResponse(
                    data=[DirectoryResponse.from_orm(dir_obj) for dir_obj in cached_directories],
                    count=len(cached_directories)
                )
        
        # Get from API if no cache or cache disabled
        directory_service = DirectoryService(db, token, base_url)
        success, directories_data, message = await directory_service.get_directories()
        
        if success:
            # Cache the directories
            await directory_service.cache_directories(directories_data)
            
            # Convert to response format
            directory_responses = []
            for dir_data in directories_data:
                # Extract identifier - Logikal API uses 'path' field as identifier
                identifier = dir_data.get('path', '')
                directory_responses.append(DirectoryResponse(
                    id=0,  # Will be set by database
                    logikal_id=identifier,
                    name=dir_data.get('name', ''),
                    parent_id=dir_data.get('parent_id'),
                    created_at=datetime.utcnow(),
                    updated_at=datetime.utcnow()
                ))
            
            return DirectoryListResponse(
                data=directory_responses,
                count=len(directory_responses)
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "code": "DIRECTORY_FETCH_FAILED",
                    "message": "Failed to fetch directories",
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


@router.get("/{directory_id}", response_model=DirectoryResponse)
async def get_directory(
    directory_id: str,
    token: str = Query(..., description="Authentication token"),
    base_url: str = Query(..., description="Logikal API base URL"),
    db: Session = Depends(get_db)
):
    """Get a specific directory by ID"""
    try:
        # First try to get from cache
        cached_directory = db.query(Directory).filter(
            Directory.logikal_id == directory_id
        ).first()
        
        if cached_directory:
            return DirectoryResponse.from_orm(cached_directory)
        
        # If not in cache, get from API
        directory_service = DirectoryService(db, token, base_url)
        success, directories_data, message = await directory_service.get_directories()
        
        if success:
            # Find the specific directory
            target_directory = None
            for dir_data in directories_data:
                if dir_data.get('path', '') == directory_id:
                    target_directory = dir_data
                    break
            
            if target_directory:
                # Extract identifier - Logikal API uses 'path' field as identifier
                identifier = target_directory.get('path', '')
                return DirectoryResponse(
                    id=0,  # Will be set by database
                    logikal_id=identifier,
                    name=target_directory.get('name', ''),
                    parent_id=target_directory.get('parent_id'),
                    created_at=datetime.utcnow(),
                    updated_at=datetime.utcnow()
                )
            else:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail={
                        "code": "DIRECTORY_NOT_FOUND",
                        "message": f"Directory with ID {directory_id} not found",
                        "details": "The requested directory does not exist"
                    }
                )
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "code": "DIRECTORY_FETCH_FAILED",
                    "message": "Failed to fetch directories",
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


@router.post("/{directory_id}/select")
async def select_directory(
    directory_id: str,
    token: str = Query(..., description="Authentication token"),
    base_url: str = Query(..., description="Logikal API base URL"),
    db: Session = Depends(get_db)
):
    """Select a directory for further operations"""
    try:
        directory_service = DirectoryService(db, token, base_url)
        success, message = await directory_service.select_directory(directory_id)
        
        if success:
            return {"success": True, "message": message}
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "code": "DIRECTORY_SELECT_FAILED",
                    "message": "Failed to select directory",
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


@router.post("/{directory_id}/exclude")
async def exclude_directory_from_sync(
    directory_id: int,
    request: DirectoryExclusionRequest = Body(...),
    db: Session = Depends(get_db)
):
    """Exclude or include a directory from sync operations"""
    try:
        directory_service = DirectoryService(db, "", "")  # No API calls needed for this operation
        success, message = await directory_service.update_directory_exclusion(directory_id, request.exclude)
        
        if success:
            return {"success": True, "message": message}
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "code": "DIRECTORY_EXCLUSION_FAILED",
                    "message": "Failed to update directory exclusion",
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


@router.post("/bulk-exclude")
async def bulk_exclude_directories_from_sync(
    request: DirectoryBulkExclusionRequest = Body(...),
    db: Session = Depends(get_db)
):
    """Bulk exclude or include directories from sync operations"""
    try:
        directory_service = DirectoryService(db, "", "")  # No API calls needed for this operation
        success, message, updated_count = await directory_service.bulk_update_directory_exclusion(
            request.directory_ids, request.exclude
        )
        
        if success:
            return {
                "success": True, 
                "message": message,
                "updated_count": updated_count
            }
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "code": "BULK_DIRECTORY_EXCLUSION_FAILED",
                    "message": "Failed to bulk update directory exclusion",
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


@router.get("/syncable/", response_model=DirectoryListResponse)
async def get_syncable_directories(
    db: Session = Depends(get_db)
):
    """Get directories that are included in sync operations"""
    try:
        directory_service = DirectoryService(db, "", "")  # No API calls needed for this operation
        syncable_directories = await directory_service.get_syncable_directories()
        
        return DirectoryListResponse(
            data=[DirectoryResponse.from_orm(dir_obj) for dir_obj in syncable_directories],
            count=len(syncable_directories)
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
