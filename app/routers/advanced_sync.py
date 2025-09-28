from fastapi import APIRouter, Depends, HTTPException, status, Query, Body
from sqlalchemy.orm import Session
from typing import List, Optional
from core.database import get_db
from core.security import get_current_client, require_permission
from services.advanced_sync_service import AdvancedSyncService
from services.data_consistency_service import DataConsistencyService
from services.sync_metrics_service import SyncMetricsService
from services.alert_service import AlertService
from schemas.advanced_sync import (
    StaleObjectsResponse, CascadingSyncResult, SelectiveSyncResult, DependencySyncResult,
    DataValidationResult, PartialFailureAnalysis, DataRepairResult, DataIntegrityReport,
    DataHashComparison, SyncPerformanceMetrics, ProjectSyncMetrics, SyncEfficiencyReport,
    AlertInfo, AlertNotificationResult, AlertHistoryResponse, AlertAcknowledgement,
    CustomAlertRequest, AdvancedSyncStatusResponse, SyncStrategyConfig,
    SyncOperationRequest, SyncOperationResponse, SyncAnalyticsResponse
)
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/advanced-sync", tags=["Advanced Sync Management"])


@router.get("/status", response_model=AdvancedSyncStatusResponse)
async def get_advanced_sync_status(
    db: Session = Depends(get_db),
    current_client: dict = Depends(require_permission("admin:read"))
):
    """
    Get advanced sync system status and health overview.
    Requires 'admin:read' permission.
    """
    try:
        alert_service = AlertService(db)
        metrics_service = SyncMetricsService(db)
        
        # Get current alerts
        alerts = alert_service.check_sync_health_alerts()
        active_alerts = len([a for a in alerts if a.get('requires_action', False)])
        
        # Get efficiency grade
        efficiency_report = metrics_service.get_sync_efficiency_report()
        efficiency_grade = efficiency_report.get('summary', {}).get('sync_efficiency_grade', 'F')
        
        # Calculate data consistency score
        consistency_service = DataConsistencyService(db)
        integrity_report = consistency_service.generate_data_integrity_report()
        consistency_score = integrity_report.get('summary', {}).get('consistency_rate', 0)
        
        # Generate recommendations
        recommendations = []
        if active_alerts > 0:
            recommendations.append(f"Address {active_alerts} active alerts")
        if efficiency_grade in ['D', 'F']:
            recommendations.append("Improve sync efficiency")
        if consistency_score < 90:
            recommendations.append("Address data consistency issues")
        
        return AdvancedSyncStatusResponse(
            system_status="healthy" if active_alerts == 0 else "needs_attention",
            last_health_check=datetime.utcnow(),
            active_alerts=active_alerts,
            sync_efficiency_grade=efficiency_grade,
            data_consistency_score=consistency_score,
            recommendations=recommendations
        )
        
    except Exception as e:
        logger.error(f"Error getting advanced sync status: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"code": "INTERNAL_ERROR", "message": "Internal server error", "details": str(e)}
        )


@router.get("/stale-objects/{object_type}", response_model=StaleObjectsResponse)
async def get_stale_objects(
    object_type: str,
    base_url: str = Query(..., description="Logikal API base URL"),
    auth_token: str = Query(..., description="Logikal API authentication token"),
    db: Session = Depends(get_db),
    current_client: dict = Depends(require_permission("projects:read"))
):
    """
    Get all stale objects of a specific type that need syncing.
    Requires 'projects:read' permission.
    """
    try:
        if object_type not in ["project", "phase", "elevation"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"code": "INVALID_OBJECT_TYPE", "message": "Object type must be project, phase, or elevation"}
            )
        
        advanced_sync_service = AdvancedSyncService(db)
        stale_objects = await advanced_sync_service.get_stale_objects(object_type, base_url, auth_token)
        
        return StaleObjectsResponse(
            object_type=object_type,
            stale_objects=stale_objects,
            total_count=len(stale_objects),
            checked_at=datetime.utcnow()
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting stale {object_type} objects: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"code": "INTERNAL_ERROR", "message": "Internal server error", "details": str(e)}
        )


@router.post("/cascade-sync/{project_id}", response_model=CascadingSyncResult)
async def trigger_cascade_sync(
    project_id: str,
    base_url: str = Query(..., description="Logikal API base URL"),
    auth_token: str = Query(..., description="Logikal API authentication token"),
    db: Session = Depends(get_db),
    current_client: dict = Depends(require_permission("projects:write"))
):
    """
    Trigger cascading sync for a project (project → phases → elevations).
    Requires 'projects:write' permission.
    """
    try:
        advanced_sync_service = AdvancedSyncService(db)
        result = await advanced_sync_service.cascade_sync_project(project_id, base_url, auth_token)
        
        if not result["success"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"code": "SYNC_FAILED", "message": result["error"]}
            )
        
        return CascadingSyncResult(**result)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error triggering cascade sync for project {project_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"code": "INTERNAL_ERROR", "message": "Internal server error", "details": str(e)}
        )


@router.post("/selective-sync", response_model=SelectiveSyncResult)
async def trigger_selective_sync(
    object_ids: List[str] = Body(..., description="List of object IDs to sync"),
    object_type: str = Query(..., description="Type of objects (project, phase, elevation)"),
    base_url: str = Query(..., description="Logikal API base URL"),
    auth_token: str = Query(..., description="Logikal API authentication token"),
    db: Session = Depends(get_db),
    current_client: dict = Depends(require_permission("projects:write"))
):
    """
    Trigger selective sync for specific objects.
    Requires 'projects:write' permission.
    """
    try:
        if object_type not in ["project", "phase", "elevation"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"code": "INVALID_OBJECT_TYPE", "message": "Object type must be project, phase, or elevation"}
            )
        
        advanced_sync_service = AdvancedSyncService(db)
        result = await advanced_sync_service.selective_sync_objects(object_ids, object_type, base_url, auth_token)
        
        return SelectiveSyncResult(**result)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error triggering selective sync for {object_type}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"code": "INTERNAL_ERROR", "message": "Internal server error", "details": str(e)}
        )


@router.post("/dependency-sync/{object_type}/{object_id}", response_model=DependencySyncResult)
async def trigger_dependency_sync(
    object_type: str,
    object_id: str,
    base_url: str = Query(..., description="Logikal API base URL"),
    auth_token: str = Query(..., description="Logikal API authentication token"),
    db: Session = Depends(get_db),
    current_client: dict = Depends(require_permission("projects:write"))
):
    """
    Trigger dependency-based sync for an object and its dependencies.
    Requires 'projects:write' permission.
    """
    try:
        if object_type not in ["project", "phase", "elevation"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"code": "INVALID_OBJECT_TYPE", "message": "Object type must be project, phase, or elevation"}
            )
        
        advanced_sync_service = AdvancedSyncService(db)
        result = await advanced_sync_service.sync_with_dependencies(object_type, object_id, base_url, auth_token)
        
        return DependencySyncResult(**result)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error triggering dependency sync for {object_type} {object_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"code": "INTERNAL_ERROR", "message": "Internal server error", "details": str(e)}
        )


@router.get("/validate-consistency/{project_id}", response_model=DataValidationResult)
async def validate_data_consistency(
    project_id: str,
    db: Session = Depends(get_db),
    current_client: dict = Depends(require_permission("projects:read"))
):
    """
    Validate data consistency for a specific project.
    Requires 'projects:read' permission.
    """
    try:
        consistency_service = DataConsistencyService(db)
        result = consistency_service.validate_project_consistency(project_id)
        
        return DataValidationResult(**result)
        
    except Exception as e:
        logger.error(f"Error validating data consistency for project {project_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"code": "INTERNAL_ERROR", "message": "Internal server error", "details": str(e)}
        )


@router.get("/partial-failures/{project_id}", response_model=PartialFailureAnalysis)
async def detect_partial_sync_failures(
    project_id: str,
    db: Session = Depends(get_db),
    current_client: dict = Depends(require_permission("projects:read"))
):
    """
    Detect and analyze partial sync failures for a project.
    Requires 'projects:read' permission.
    """
    try:
        consistency_service = DataConsistencyService(db)
        result = consistency_service.detect_partial_sync_failures(project_id)
        
        return PartialFailureAnalysis(**result)
        
    except Exception as e:
        logger.error(f"Error detecting partial sync failures for project {project_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"code": "INTERNAL_ERROR", "message": "Internal server error", "details": str(e)}
        )


@router.post("/repair-consistency/{project_id}", response_model=DataRepairResult)
async def repair_data_consistency(
    project_id: str,
    db: Session = Depends(get_db),
    current_client: dict = Depends(require_permission("admin:write"))
):
    """
    Attempt to repair data consistency issues for a project.
    Requires 'admin:write' permission.
    """
    try:
        consistency_service = DataConsistencyService(db)
        result = consistency_service.repair_data_consistency(project_id)
        
        return DataRepairResult(**result)
        
    except Exception as e:
        logger.error(f"Error repairing data consistency for project {project_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"code": "INTERNAL_ERROR", "message": "Internal server error", "details": str(e)}
        )


@router.get("/integrity-report", response_model=DataIntegrityReport)
async def generate_data_integrity_report(
    project_id: Optional[str] = Query(None, description="Specific project ID (optional)"),
    db: Session = Depends(get_db),
    current_client: dict = Depends(require_permission("admin:read"))
):
    """
    Generate a comprehensive data integrity report.
    Requires 'admin:read' permission.
    """
    try:
        consistency_service = DataConsistencyService(db)
        result = consistency_service.generate_data_integrity_report(project_id)
        
        return DataIntegrityReport(**result)
        
    except Exception as e:
        logger.error(f"Error generating data integrity report: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"code": "INTERNAL_ERROR", "message": "Internal server error", "details": str(e)}
        )


@router.get("/performance-metrics", response_model=SyncPerformanceMetrics)
async def get_sync_performance_metrics(
    time_period_hours: int = Query(24, description="Time period in hours"),
    db: Session = Depends(get_db),
    current_client: dict = Depends(require_permission("admin:read"))
):
    """
    Get comprehensive sync performance metrics.
    Requires 'admin:read' permission.
    """
    try:
        metrics_service = SyncMetricsService(db)
        result = metrics_service.get_sync_performance_metrics(time_period_hours)
        
        return SyncPerformanceMetrics(**result)
        
    except Exception as e:
        logger.error(f"Error getting sync performance metrics: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"code": "INTERNAL_ERROR", "message": "Internal server error", "details": str(e)}
        )


@router.get("/project-metrics/{project_id}", response_model=ProjectSyncMetrics)
async def get_project_sync_metrics(
    project_id: str,
    time_period_hours: int = Query(168, description="Time period in hours (default: 1 week)"),
    db: Session = Depends(get_db),
    current_client: dict = Depends(require_permission("projects:read"))
):
    """
    Get detailed sync metrics for a specific project.
    Requires 'projects:read' permission.
    """
    try:
        metrics_service = SyncMetricsService(db)
        result = metrics_service.get_project_sync_metrics(project_id, time_period_hours)
        
        if "error" in result:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"code": "PROJECT_NOT_FOUND", "message": result["error"]}
            )
        
        return ProjectSyncMetrics(**result)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting project sync metrics for {project_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"code": "INTERNAL_ERROR", "message": "Internal server error", "details": str(e)}
        )


@router.get("/efficiency-report", response_model=SyncEfficiencyReport)
async def get_sync_efficiency_report(
    db: Session = Depends(get_db),
    current_client: dict = Depends(require_permission("admin:read"))
):
    """
    Generate a comprehensive sync efficiency report.
    Requires 'admin:read' permission.
    """
    try:
        metrics_service = SyncMetricsService(db)
        result = metrics_service.get_sync_efficiency_report()
        
        return SyncEfficiencyReport(**result)
        
    except Exception as e:
        logger.error(f"Error getting sync efficiency report: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"code": "INTERNAL_ERROR", "message": "Internal server error", "details": str(e)}
        )


@router.get("/alerts", response_model=List[AlertInfo])
async def get_current_alerts(
    severity: Optional[str] = Query(None, description="Filter by severity (critical, warning, info)"),
    db: Session = Depends(get_db),
    current_client: dict = Depends(require_permission("admin:read"))
):
    """
    Get current system alerts.
    Requires 'admin:read' permission.
    """
    try:
        alert_service = AlertService(db)
        alerts = alert_service.check_sync_health_alerts()
        
        if severity:
            alerts = [alert for alert in alerts if alert['severity'] == severity]
        
        return [AlertInfo(**alert) for alert in alerts]
        
    except Exception as e:
        logger.error(f"Error getting current alerts: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"code": "INTERNAL_ERROR", "message": "Internal server error", "details": str(e)}
        )


@router.post("/alerts/send-notification", response_model=AlertNotificationResult)
async def send_alert_notification(
    alert_id: str = Body(..., description="Alert ID to send notification for"),
    recipients: List[str] = Body(..., description="List of email recipients"),
    db: Session = Depends(get_db),
    current_client: dict = Depends(require_permission("admin:write"))
):
    """
    Send alert notification via email.
    Requires 'admin:write' permission.
    """
    try:
        alert_service = AlertService(db)
        
        # Get the alert (in a real implementation, this would fetch from database)
        alerts = alert_service.check_sync_health_alerts()
        alert = next((a for a in alerts if a.get('id') == alert_id), None)
        
        if not alert:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"code": "ALERT_NOT_FOUND", "message": f"Alert {alert_id} not found"}
            )
        
        result = alert_service.send_alert_notification(alert, recipients)
        
        return AlertNotificationResult(**result)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error sending alert notification: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"code": "INTERNAL_ERROR", "message": "Internal server error", "details": str(e)}
        )


@router.get("/alerts/history", response_model=AlertHistoryResponse)
async def get_alert_history(
    hours: int = Query(24, description="Time period in hours"),
    severity: Optional[str] = Query(None, description="Filter by severity"),
    db: Session = Depends(get_db),
    current_client: dict = Depends(require_permission("admin:read"))
):
    """
    Get alert history for the specified time period.
    Requires 'admin:read' permission.
    """
    try:
        alert_service = AlertService(db)
        alerts = alert_service.get_alert_history(hours, severity)
        
        return AlertHistoryResponse(
            alerts=[AlertInfo(**alert) for alert in alerts],
            total_count=len(alerts),
            time_period_hours=hours,
            generated_at=datetime.utcnow()
        )
        
    except Exception as e:
        logger.error(f"Error getting alert history: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"code": "INTERNAL_ERROR", "message": "Internal server error", "details": str(e)}
        )


@router.post("/alerts/acknowledge", response_model=AlertAcknowledgement)
async def acknowledge_alert(
    alert_id: str = Body(..., description="Alert ID to acknowledge"),
    acknowledged_by: str = Body(..., description="User acknowledging the alert"),
    notes: Optional[str] = Body(None, description="Optional acknowledgement notes"),
    db: Session = Depends(get_db),
    current_client: dict = Depends(require_permission("admin:write"))
):
    """
    Acknowledge an alert.
    Requires 'admin:write' permission.
    """
    try:
        alert_service = AlertService(db)
        result = alert_service.acknowledge_alert(alert_id, acknowledged_by, notes)
        
        if not result["success"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"code": "ACKNOWLEDGEMENT_FAILED", "message": result["error"]}
            )
        
        return AlertAcknowledgement(**result)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error acknowledging alert: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"code": "INTERNAL_ERROR", "message": "Internal server error", "details": str(e)}
        )


@router.post("/alerts/create", response_model=AlertInfo)
async def create_custom_alert(
    request: CustomAlertRequest,
    db: Session = Depends(get_db),
    current_client: dict = Depends(require_permission("admin:write"))
):
    """
    Create a custom alert.
    Requires 'admin:write' permission.
    """
    try:
        alert_service = AlertService(db)
        result = alert_service.create_custom_alert(
            request.alert_type,
            request.severity,
            request.message,
            request.details,
            request.requires_action
        )
        
        if not result["success"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"code": "ALERT_CREATION_FAILED", "message": result["error"]}
            )
        
        return AlertInfo(**result["alert"])
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating custom alert: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"code": "INTERNAL_ERROR", "message": "Internal server error", "details": str(e)}
        )
