from pydantic import BaseModel
from typing import List, Optional, Dict, Any
from datetime import datetime


class StaleObjectInfo(BaseModel):
    """Information about a stale object"""
    id: int
    logikal_id: str
    name: str
    last_sync_date: Optional[datetime]
    logikal_last_update: Optional[datetime]
    staleness_reason: str


class StaleObjectsResponse(BaseModel):
    """Response model for stale objects query"""
    object_type: str
    stale_objects: List[StaleObjectInfo]
    total_count: int
    checked_at: datetime


class CascadingSyncResult(BaseModel):
    """Result of a cascading sync operation"""
    project_id: str
    project_synced: bool
    phases_synced: int
    elevations_synced: int
    errors: List[str]
    started_at: datetime
    completed_at: Optional[datetime]
    success: bool


class SelectiveSyncResult(BaseModel):
    """Result of a selective sync operation"""
    object_type: str
    requested_count: int
    synced_count: int
    skipped_count: int
    failed_count: int
    results: List[Dict[str, Any]]
    started_at: datetime
    completed_at: Optional[datetime]
    success: bool


class DependencySyncResult(BaseModel):
    """Result of a dependency-based sync operation"""
    object_type: str
    object_id: str
    dependencies: List[str]
    synced_objects: List[Dict[str, Any]]
    errors: List[str]
    started_at: datetime
    completed_at: Optional[datetime]
    success: bool


class DataValidationResult(BaseModel):
    """Result of data validation"""
    project_id: str
    valid: bool
    errors: List[str]
    warnings: List[str]
    checks: Dict[str, Any]


class PartialFailureAnalysis(BaseModel):
    """Analysis of partial sync failures"""
    project_id: str
    has_partial_failures: bool
    sync_status: Dict[str, Any]
    inconsistencies: List[str]
    recommendations: List[str]


class DataRepairResult(BaseModel):
    """Result of data consistency repair"""
    project_id: str
    success: bool
    repairs_made: List[str]
    errors: List[str]
    started_at: datetime
    completed_at: Optional[datetime]


class DataIntegrityReport(BaseModel):
    """Comprehensive data integrity report"""
    generated_at: datetime
    scope: str
    summary: Dict[str, Any]
    detailed_analysis: List[Dict[str, Any]]
    recommendations: List[str]


class DataHashComparison(BaseModel):
    """Result of data hash comparison"""
    project_id: str
    current_hash: str
    previous_hash: str
    has_changed: bool
    comparison_time: datetime


class SyncPerformanceMetrics(BaseModel):
    """Sync performance metrics"""
    time_period_hours: int
    generated_at: datetime
    sync_counts: Dict[str, int]
    performance_metrics: Dict[str, Any]
    data_quality_metrics: Dict[str, Any]
    trends: Dict[str, Any]


class ProjectSyncMetrics(BaseModel):
    """Detailed sync metrics for a specific project"""
    project_id: str
    project_name: str
    time_period_hours: int
    generated_at: datetime
    sync_history: Dict[str, Any]
    performance_analysis: Dict[str, Any]
    data_quality: Dict[str, Any]


class SyncEfficiencyReport(BaseModel):
    """Sync efficiency report"""
    generated_at: datetime
    summary: Dict[str, Any]
    efficiency_analysis: Dict[str, Any]
    recommendations: List[str]


class AlertInfo(BaseModel):
    """Alert information"""
    id: Optional[str] = None
    type: str
    severity: str
    message: str
    details: Dict[str, Any]
    timestamp: datetime
    requires_action: bool
    recommended_action: Optional[str] = None
    source: str = "system"


class AlertNotificationResult(BaseModel):
    """Result of sending alert notification"""
    success: bool
    message: str
    recipients: List[str]
    alert_id: str


class AlertHistoryResponse(BaseModel):
    """Alert history response"""
    alerts: List[AlertInfo]
    total_count: int
    time_period_hours: int
    generated_at: datetime


class AlertAcknowledgement(BaseModel):
    """Alert acknowledgement"""
    alert_id: str
    acknowledged_by: str
    acknowledged_at: datetime
    notes: Optional[str] = None


class CustomAlertRequest(BaseModel):
    """Request to create a custom alert"""
    alert_type: str
    severity: str
    message: str
    details: Dict[str, Any] = {}
    requires_action: bool = True


class AdvancedSyncStatusResponse(BaseModel):
    """Advanced sync status response"""
    system_status: str
    last_health_check: datetime
    active_alerts: int
    sync_efficiency_grade: str
    data_consistency_score: float
    recommendations: List[str]


class SyncStrategyConfig(BaseModel):
    """Configuration for sync strategies"""
    staleness_threshold_hours: int = 24
    batch_size: int = 100
    max_concurrent_syncs: int = 5
    retry_attempts: int = 3
    enable_cascading_sync: bool = True
    enable_selective_sync: bool = True
    enable_dependency_sync: bool = True


class SyncOperationRequest(BaseModel):
    """Request for sync operations"""
    operation_type: str  # "cascading", "selective", "dependency", "stale_objects"
    object_ids: Optional[List[str]] = None
    object_type: Optional[str] = None
    force_sync: bool = False
    include_dependencies: bool = True


class SyncOperationResponse(BaseModel):
    """Response for sync operations"""
    operation_id: str
    operation_type: str
    status: str  # "started", "in_progress", "completed", "failed"
    message: str
    started_at: datetime
    estimated_completion: Optional[datetime] = None
    progress_percentage: Optional[float] = None


class SyncAnalyticsResponse(BaseModel):
    """Sync analytics response"""
    time_period: str
    total_operations: int
    successful_operations: int
    failed_operations: int
    average_duration_seconds: float
    throughput_per_hour: float
    efficiency_score: float
    top_performing_operations: List[Dict[str, Any]]
    improvement_recommendations: List[str]
