from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime


class DirectoryBase(BaseModel):
    """Base directory schema"""
    logikal_id: str = Field(..., description="Unique identifier from Logikal API")
    name: str = Field(..., description="Directory name")
    full_path: Optional[str] = Field(None, description="Full navigation path")
    level: Optional[int] = Field(0, description="Directory depth level")
    parent_id: Optional[int] = Field(None, description="Parent directory ID")
    exclude_from_sync: bool = Field(False, description="Whether to exclude from sync operations")


class DirectoryCreate(DirectoryBase):
    """Schema for creating a directory"""
    pass


class DirectoryUpdate(BaseModel):
    """Schema for updating a directory"""
    exclude_from_sync: Optional[bool] = Field(None, description="Whether to exclude from sync operations")
    sync_status: Optional[str] = Field(None, description="Sync status")


class DirectoryResponse(DirectoryBase):
    """Schema for directory response"""
    id: int
    synced_at: Optional[datetime] = Field(None, description="Last sync timestamp")
    last_api_sync: Optional[datetime] = Field(None, description="Last API sync timestamp")
    api_created_date: Optional[datetime] = Field(None, description="API creation date")
    api_changed_date: Optional[datetime] = Field(None, description="API change date")
    sync_status: Optional[str] = Field(None, description="Sync status")
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


class DirectoryListResponse(BaseModel):
    """Response schema for directory list"""
    success: bool = True
    data: List[DirectoryResponse]
    count: int


class DirectoryExclusionRequest(BaseModel):
    """Schema for directory exclusion requests"""
    exclude: bool = Field(..., description="Whether to exclude from sync")


class DirectoryBulkExclusionRequest(BaseModel):
    """Schema for bulk directory exclusion requests"""
    directory_ids: List[int] = Field(..., description="List of directory IDs to update")
    exclude: bool = Field(..., description="Whether to exclude from sync")
