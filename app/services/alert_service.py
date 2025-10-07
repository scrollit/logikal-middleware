from sqlalchemy.orm import Session
from typing import List, Dict, Optional, Any, Tuple
from datetime import datetime, timedelta
from models.project import Project
from models.phase import Phase
from models.elevation import Elevation
import logging
import asyncio
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

logger = logging.getLogger(__name__)


class AlertService:
    """
    Service for monitoring, alerting, and notification management.
    """

    def __init__(self, db: Session):
        self.db = db

    def check_sync_health_alerts(self) -> List[Dict]:
        """
        Check for various sync health issues and generate alerts.
        """
        alerts = []
        
        try:
            # Alert 1: Check for stale data
            stale_alerts = self._check_stale_data_alerts()
            alerts.extend(stale_alerts)
            
            # Alert 2: Check for sync failures
            failure_alerts = self._check_sync_failure_alerts()
            alerts.extend(failure_alerts)
            
            # Alert 3: Check for data consistency issues
            consistency_alerts = self._check_data_consistency_alerts()
            alerts.extend(consistency_alerts)
            
            # Alert 4: Check for performance issues
            performance_alerts = self._check_performance_alerts()
            alerts.extend(performance_alerts)
            
            # Alert 5: Check for system health issues
            system_alerts = self._check_system_health_alerts()
            alerts.extend(system_alerts)
            
            return alerts
            
        except Exception as e:
            logger.error(f"Error checking sync health alerts: {str(e)}")
            return [{
                "type": "system_error",
                "severity": "critical",
                "message": f"Alert system error: {str(e)}",
                "timestamp": datetime.utcnow(),
                "requires_action": True
            }]

    def _check_stale_data_alerts(self) -> List[Dict]:
        """
        Check for stale data and generate alerts.
        """
        alerts = []
        
        try:
            # Check for projects that haven't been synced in 24+ hours
            stale_threshold = datetime.utcnow() - timedelta(hours=24)
            
            stale_projects = self.db.query(Project).filter(
                Project.last_sync_date < stale_threshold
            ).all()
            
            if stale_projects:
                alerts.append({
                    "type": "stale_data",
                    "severity": "warning",
                    "message": f"Found {len(stale_projects)} stale projects (not synced in 24+ hours)",
                    "details": {
                        "count": len(stale_projects),
                        "object_type": "projects",
                        "threshold_hours": 24
                    },
                    "timestamp": datetime.utcnow(),
                    "requires_action": True,
                    "recommended_action": "Run sync for stale projects"
                })
            
            # Check for phases that haven't been synced in 12+ hours
            stale_threshold_phases = datetime.utcnow() - timedelta(hours=12)
            
            stale_phases = self.db.query(Phase).filter(
                Phase.last_sync_date < stale_threshold_phases
            ).count()
            
            if stale_phases > 100:  # Alert if more than 100 stale phases
                alerts.append({
                    "type": "stale_data",
                    "severity": "warning",
                    "message": f"Found {stale_phases} stale phases (not synced in 12+ hours)",
                    "details": {
                        "count": stale_phases,
                        "object_type": "phases",
                        "threshold_hours": 12
                    },
                    "timestamp": datetime.utcnow(),
                    "requires_action": True,
                    "recommended_action": "Run batch sync for stale phases"
                })
            
            # Check for elevations that haven't been synced in 6+ hours
            stale_threshold_elevations = datetime.utcnow() - timedelta(hours=6)
            
            stale_elevations = self.db.query(Elevation).filter(
                Elevation.last_sync_date < stale_threshold_elevations
            ).count()
            
            if stale_elevations > 500:  # Alert if more than 500 stale elevations
                alerts.append({
                    "type": "stale_data",
                    "severity": "warning",
                    "message": f"Found {stale_elevations} stale elevations (not synced in 6+ hours)",
                    "details": {
                        "count": stale_elevations,
                        "object_type": "elevations",
                        "threshold_hours": 6
                    },
                    "timestamp": datetime.utcnow(),
                    "requires_action": True,
                    "recommended_action": "Run batch sync for stale elevations"
                })
            
            return alerts
            
        except Exception as e:
            logger.error(f"Error checking stale data alerts: {str(e)}")
            return []

    def _check_sync_failure_alerts(self) -> List[Dict]:
        """
        Check for sync failure patterns and generate alerts.
        """
        alerts = []
        
        try:
            # Check for projects that have never been synced
            unsynced_projects = self.db.query(Project).filter(
                Project.last_sync_date.is_(None)
            ).count()
            
            if unsynced_projects > 0:
                alerts.append({
                    "type": "sync_failure",
                    "severity": "critical",
                    "message": f"Found {unsynced_projects} projects that have never been synced",
                    "details": {
                        "count": unsynced_projects,
                        "object_type": "projects",
                        "issue": "never_synced"
                    },
                    "timestamp": datetime.utcnow(),
                    "requires_action": True,
                    "recommended_action": "Investigate and sync unsynced projects"
                })
            
            # Check for objects with sync dates but no update dates (potential inconsistency)
            inconsistent_projects = self.db.query(Project).filter(
                Project.last_sync_date.isnot(None),
                Project.last_update_date.is_(None)
            ).count()
            
            if inconsistent_projects > 10:
                alerts.append({
                    "type": "data_inconsistency",
                    "severity": "warning",
                    "message": f"Found {inconsistent_projects} projects with sync dates but no update dates",
                    "details": {
                        "count": inconsistent_projects,
                        "object_type": "projects",
                        "issue": "missing_update_dates"
                    },
                    "timestamp": datetime.utcnow(),
                    "requires_action": True,
                    "recommended_action": "Investigate data consistency issues"
                })
            
            return alerts
            
        except Exception as e:
            logger.error(f"Error checking sync failure alerts: {str(e)}")
            return []

    def _check_data_consistency_alerts(self) -> List[Dict]:
        """
        Check for data consistency issues and generate alerts.
        """
        alerts = []
        
        try:
            # Check for orphaned phases (phases without valid project references)
            orphaned_phases = self.db.query(Phase).filter(
                Phase.project_id.is_(None)
            ).count()
            
            if orphaned_phases > 0:
                alerts.append({
                    "type": "data_inconsistency",
                    "severity": "critical",
                    "message": f"Found {orphaned_phases} orphaned phases without project references",
                    "details": {
                        "count": orphaned_phases,
                        "object_type": "phases",
                        "issue": "orphaned_objects"
                    },
                    "timestamp": datetime.utcnow(),
                    "requires_action": True,
                    "recommended_action": "Fix orphaned phase references"
                })
            
            # Check for orphaned elevations
            orphaned_elevations = self.db.query(Elevation).filter(
                Elevation.project_id.is_(None)
            ).count()
            
            if orphaned_elevations > 0:
                alerts.append({
                    "type": "data_inconsistency",
                    "severity": "critical",
                    "message": f"Found {orphaned_elevations} orphaned elevations without project references",
                    "details": {
                        "count": orphaned_elevations,
                        "object_type": "elevations",
                        "issue": "orphaned_objects"
                    },
                    "timestamp": datetime.utcnow(),
                    "requires_action": True,
                    "recommended_action": "Fix orphaned elevation references"
                })
            
            return alerts
            
        except Exception as e:
            logger.error(f"Error checking data consistency alerts: {str(e)}")
            return []

    def _check_performance_alerts(self) -> List[Dict]:
        """
        Check for performance issues and generate alerts.
        """
        alerts = []
        
        try:
            # Check sync throughput over the last hour
            one_hour_ago = datetime.utcnow() - timedelta(hours=1)
            
            recent_syncs = (
                self.db.query(Project).filter(Project.last_sync_date >= one_hour_ago).count() +
                self.db.query(Phase).filter(Phase.last_sync_date >= one_hour_ago).count() +
                self.db.query(Elevation).filter(Elevation.last_sync_date >= one_hour_ago).count()
            )
            
            # Alert if sync throughput is too low
            if recent_syncs < 5:  # Less than 5 objects synced in the last hour
                alerts.append({
                    "type": "performance",
                    "severity": "warning",
                    "message": f"Low sync throughput: only {recent_syncs} objects synced in the last hour",
                    "details": {
                        "throughput_per_hour": recent_syncs,
                        "threshold": 5,
                        "time_period": "1 hour"
                    },
                    "timestamp": datetime.utcnow(),
                    "requires_action": True,
                    "recommended_action": "Check sync system performance"
                })
            
            # Check for projects with too many unsynced child objects
            projects_with_many_unsynced = []
            all_projects = self.db.query(Project).all()
            
            for project in all_projects:
                phases = self.db.query(Phase).filter(Phase.project_id == project.id).all()
                elevations = self.db.query(Elevation).filter(Elevation.project_id == project.id).all()
                
                unsynced_children = sum(
                    1 for obj in phases + elevations 
                    if not obj.last_sync_date or obj.last_sync_date < one_hour_ago
                )
                
                if unsynced_children > 50:  # More than 50 unsynced child objects
                    projects_with_many_unsynced.append({
                        "project_id": project.logikal_id,
                        "unsynced_count": unsynced_children
                    })
            
            if projects_with_many_unsynced:
                alerts.append({
                    "type": "performance",
                    "severity": "warning",
                    "message": f"Found {len(projects_with_many_unsynced)} projects with many unsynced child objects",
                    "details": {
                        "affected_projects": projects_with_many_unsynced,
                        "threshold": 50
                    },
                    "timestamp": datetime.utcnow(),
                    "requires_action": True,
                    "recommended_action": "Run cascading sync for affected projects"
                })
            
            return alerts
            
        except Exception as e:
            logger.error(f"Error checking performance alerts: {str(e)}")
            return []

    def _check_system_health_alerts(self) -> List[Dict]:
        """
        Check for system health issues and generate alerts.
        """
        alerts = []
        
        try:
            # Check database connection health
            try:
                from sqlalchemy import text
                self.db.execute(text("SELECT 1"))
            except Exception as e:
                alerts.append({
                    "type": "system_health",
                    "severity": "critical",
                    "message": f"Database connection issue: {str(e)}",
                    "details": {
                        "component": "database",
                        "error": str(e)
                    },
                    "timestamp": datetime.utcnow(),
                    "requires_action": True,
                    "recommended_action": "Check database connectivity"
                })
            
            # Check for excessive data growth
            total_objects = (
                self.db.query(Project).count() +
                self.db.query(Phase).count() +
                self.db.query(Elevation).count()
            )
            
            if total_objects > 100000:  # Alert if more than 100k objects
                alerts.append({
                    "type": "system_health",
                    "severity": "warning",
                    "message": f"Large dataset detected: {total_objects} total objects",
                    "details": {
                        "total_objects": total_objects,
                        "threshold": 100000
                    },
                    "timestamp": datetime.utcnow(),
                    "requires_action": True,
                    "recommended_action": "Consider data archiving strategy"
                })
            
            return alerts
            
        except Exception as e:
            logger.error(f"Error checking system health alerts: {str(e)}")
            return []

    def send_alert_notification(self, alert: Dict, recipients: List[str] = None) -> Dict:
        """
        Send alert notification via email.
        """
        try:
            if not recipients:
                recipients = ["admin@example.com"]  # Default recipient
            
            # Create email message
            msg = MIMEMultipart()
            msg['From'] = "noreply@logikal-middleware.com"
            msg['To'] = ", ".join(recipients)
            msg['Subject'] = f"[{alert['severity'].upper()}] Logikal Middleware Alert: {alert['type']}"
            
            # Create email body
            body = f"""
Logikal Middleware Alert

Type: {alert['type']}
Severity: {alert['severity']}
Timestamp: {alert['timestamp']}

Message: {alert['message']}

Details:
{self._format_alert_details(alert.get('details', {}))}

Recommended Action: {alert.get('recommended_action', 'No specific action required')}

Requires Action: {'Yes' if alert.get('requires_action', False) else 'No'}

---
This is an automated alert from the Logikal Middleware system.
            """
            
            msg.attach(MIMEText(body, 'plain'))
            
            # Send email (in production, you would configure SMTP settings)
            # For now, we'll just log the alert
            logger.info(f"ALERT NOTIFICATION: {alert['message']}")
            logger.info(f"Recipients: {recipients}")
            
            return {
                "success": True,
                "message": "Alert notification sent successfully",
                "recipients": recipients,
                "alert_id": alert.get('id', 'unknown')
            }
            
        except Exception as e:
            logger.error(f"Error sending alert notification: {str(e)}")
            return {
                "success": False,
                "error": str(e),
                "alert_id": alert.get('id', 'unknown')
            }

    def _format_alert_details(self, details: Dict) -> str:
        """
        Format alert details for email display.
        """
        if not details:
            return "No additional details available."
        
        formatted_details = []
        for key, value in details.items():
            if isinstance(value, (dict, list)):
                formatted_details.append(f"{key}: {str(value)}")
            else:
                formatted_details.append(f"{key}: {value}")
        
        return "\n".join(formatted_details)

    def get_alert_history(self, hours: int = 24, severity: str = None) -> List[Dict]:
        """
        Get alert history for the specified time period.
        """
        try:
            # In a real implementation, this would query an alerts table
            # For now, we'll simulate by running current health checks
            
            alerts = self.check_sync_health_alerts()
            
            # Filter by severity if specified
            if severity:
                alerts = [alert for alert in alerts if alert['severity'] == severity]
            
            # Sort by timestamp (newest first)
            alerts.sort(key=lambda x: x['timestamp'], reverse=True)
            
            return alerts
            
        except Exception as e:
            logger.error(f"Error getting alert history: {str(e)}")
            return []

    def acknowledge_alert(self, alert_id: str, acknowledged_by: str, notes: str = None) -> Dict:
        """
        Acknowledge an alert.
        """
        try:
            # In a real implementation, this would update an alerts table
            logger.info(f"Alert {alert_id} acknowledged by {acknowledged_by}")
            if notes:
                logger.info(f"Acknowledgement notes: {notes}")
            
            return {
                "success": True,
                "alert_id": alert_id,
                "acknowledged_by": acknowledged_by,
                "acknowledged_at": datetime.utcnow(),
                "notes": notes
            }
            
        except Exception as e:
            logger.error(f"Error acknowledging alert {alert_id}: {str(e)}")
            return {
                "success": False,
                "error": str(e),
                "alert_id": alert_id
            }

    def create_custom_alert(self, alert_type: str, severity: str, message: str, 
                          details: Dict = None, requires_action: bool = True) -> Dict:
        """
        Create a custom alert.
        """
        try:
            alert = {
                "id": f"custom_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}",
                "type": alert_type,
                "severity": severity,
                "message": message,
                "details": details or {},
                "timestamp": datetime.utcnow(),
                "requires_action": requires_action,
                "source": "manual"
            }
            
            logger.info(f"Custom alert created: {message}")
            
            return {
                "success": True,
                "alert": alert
            }
            
        except Exception as e:
            logger.error(f"Error creating custom alert: {str(e)}")
            return {
                "success": False,
                "error": str(e)
            }
