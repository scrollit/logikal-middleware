from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime


class SyncRequest(BaseModel):
    """Schema for sync requests"""
    base_url: str = Field(..., description="Base URL of the Logikal API")
    username: str = Field(..., description="Logikal API username")
    password: str = Field(..., description="Logikal API password")


class SyncResponse(BaseModel):
    """Schema for sync responses"""
    success: bool = Field(..., description="Whether the sync operation was successful")
    message: str = Field(..., description="Sync operation message")
    duration_seconds: int = Field(..., description="Duration of the sync operation in seconds")
    directories_processed: int = Field(0, description="Number of directories processed")
    projects_processed: int = Field(0, description="Number of projects processed")
    phases_processed: int = Field(0, description="Number of phases processed")
    elevations_processed: int = Field(0, description="Number of elevations processed")
    total_items: int = Field(0, description="Total number of items processed")


class SyncConfigResponse(BaseModel):
    """Schema for sync configuration response"""
    is_sync_enabled: bool = Field(..., description="Whether sync is enabled")
    sync_interval_minutes: int = Field(..., description="Sync interval in minutes")
    last_full_sync: Optional[str] = Field(None, description="Last full sync timestamp")
    last_incremental_sync: Optional[str] = Field(None, description="Last incremental sync timestamp")


class SyncLogResponse(BaseModel):
    """Schema for sync log response"""
    id: int = Field(..., description="Sync log ID")
    sync_type: str = Field(..., description="Type of sync operation")
    status: str = Field(..., description="Status of the sync operation")
    message: str = Field(..., description="Sync operation message")
    items_processed: int = Field(..., description="Number of items processed")
    duration_seconds: Optional[int] = Field(None, description="Duration in seconds")
    started_at: str = Field(..., description="Start timestamp")
    completed_at: Optional[str] = Field(None, description="Completion timestamp")


class SyncStatusResponse(BaseModel):
    """Schema for sync status response"""
    success: bool = Field(..., description="Whether the status request was successful")
    sync_config: SyncConfigResponse = Field(..., description="Sync configuration")
    recent_logs: List[SyncLogResponse] = Field(..., description="Recent sync logs")
