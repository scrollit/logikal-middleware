from sqlalchemy.orm import Session
from typing import List, Dict, Optional, Tuple
from datetime import datetime, timedelta
from models.project import Project
from models.phase import Phase
from models.elevation import Elevation
from services.advanced_sync_service import AdvancedSyncService
from services.data_consistency_service import DataConsistencyService
from services.sync_metrics_service import SyncMetricsService
from services.alert_service import AlertService
import logging

logger = logging.getLogger(__name__)


class SmartSyncService:
    """
    Service for intelligent synchronization with Logikal API.
    Determines when data needs to be refreshed based on timestamp comparisons.
    """

    def __init__(self, db: Session, logikal_service=None):
        self.db = db
        self.logikal_service = logikal_service  # Will be implemented in later phases
        self.advanced_sync_service = AdvancedSyncService(db)
        self.consistency_service = DataConsistencyService(db)
        self.metrics_service = SyncMetricsService(db)
        self.alert_service = AlertService(db)

    def is_project_stale(self, project: Project) -> bool:
        """
        Check if a project needs to be synced from Logikal.
        Returns True if project data is stale and needs refreshing.
        """
        if not project.last_update_date or not project.last_sync_date:
            logger.info(f"Project {project.logikal_id} has missing timestamps - marking as stale")
            return True
        
        # If Logikal's last_update_date is newer than our last_sync_date, data is stale
        is_stale = project.last_update_date > project.last_sync_date
        if is_stale:
            logger.info(f"Project {project.logikal_id} is stale: update_date={project.last_update_date}, sync_date={project.last_sync_date}")
        
        return is_stale

    def is_phase_stale(self, phase: Phase) -> bool:
        """
        Check if a phase needs to be synced from Logikal.
        Returns True if phase data is stale and needs refreshing.
        """
        if not phase.last_update_date or not phase.last_sync_date:
            logger.info(f"Phase {phase.logikal_id} has missing timestamps - marking as stale")
            return True
        
        is_stale = phase.last_update_date > phase.last_sync_date
        if is_stale:
            logger.info(f"Phase {phase.logikal_id} is stale: update_date={phase.last_update_date}, sync_date={phase.last_sync_date}")
        
        return is_stale

    def is_elevation_stale(self, elevation: Elevation) -> bool:
        """
        Check if an elevation needs to be synced from Logikal.
        Returns True if elevation data is stale and needs refreshing.
        """
        if not elevation.last_update_date or not elevation.last_sync_date:
            logger.info(f"Elevation {elevation.logikal_id} has missing timestamps - marking as stale")
            return True
        
        is_stale = elevation.last_update_date > elevation.last_sync_date
        if is_stale:
            logger.info(f"Elevation {elevation.logikal_id} is stale: update_date={elevation.last_update_date}, sync_date={elevation.last_sync_date}")
        
        return is_stale

    def check_project_sync_needed(self, project_id: str) -> Dict:
        """
        Check if a project and its downstream objects need syncing.
        Returns sync status information.
        """
        project = self.db.query(Project).filter(Project.logikal_id == project_id).first()
        if not project:
            return {
                "project_id": project_id,
                "exists": False,
                "sync_needed": False,
                "reason": "Project not found"
            }

        project_stale = self.is_project_stale(project)
        
        # Check phases
        phases = self.db.query(Phase).filter(Phase.project_id == project.id).all()
        stale_phases = [phase for phase in phases if self.is_phase_stale(phase)]
        
        # Check elevations
        elevations = self.db.query(Elevation).filter(Elevation.project_id == project.id).all()
        stale_elevations = [elevation for elevation in elevations if self.is_elevation_stale(elevation)]

        sync_needed = project_stale or len(stale_phases) > 0 or len(stale_elevations) > 0

        return {
            "project_id": project_id,
            "exists": True,
            "sync_needed": sync_needed,
            "project_stale": project_stale,
            "stale_phases_count": len(stale_phases),
            "stale_elevations_count": len(stale_elevations),
            "total_phases": len(phases),
            "total_elevations": len(elevations),
            "last_sync_date": project.last_sync_date,
            "last_update_date": project.last_update_date
        }

    def sync_project_if_needed(self, project_id: str, force_sync: bool = False) -> Dict:
        """
        Sync a project from Logikal if it's stale or if force_sync is True.
        Implements cascading sync logic.
        """
        try:
            # Check if sync is needed
            sync_status = self.check_project_sync_needed(project_id)
            
            if not sync_status["exists"]:
                return {
                    "success": False,
                    "error": "Project not found",
                    "project_id": project_id
                }

            if not force_sync and not sync_status["sync_needed"]:
                return {
                    "success": True,
                    "synced": False,
                    "reason": "Data is up to date",
                    "project_id": project_id,
                    "sync_status": sync_status
                }

            # Perform the sync
            logger.info(f"Starting smart sync for project {project_id}")
            sync_result = self._perform_project_sync(project_id)
            
            return {
                "success": True,
                "synced": True,
                "project_id": project_id,
                "sync_status": sync_status,
                "sync_result": sync_result
            }

        except Exception as e:
            logger.error(f"Error during smart sync for project {project_id}: {str(e)}")
            return {
                "success": False,
                "error": str(e),
                "project_id": project_id
            }

    def _perform_project_sync(self, project_id: str) -> Dict:
        """
        Internal method to perform the actual sync with Logikal.
        This will be enhanced in later phases to actually sync data.
        For now, it updates timestamps to simulate a successful sync.
        """
        project = self.db.query(Project).filter(Project.logikal_id == project_id).first()
        if not project:
            raise ValueError(f"Project {project_id} not found")

        sync_time = datetime.utcnow()
        
        # Update project sync timestamp
        project.last_sync_date = sync_time
        project.updated_at = sync_time
        
        # Update phases sync timestamps
        phases = self.db.query(Phase).filter(Phase.project_id == project.id).all()
        for phase in phases:
            phase.last_sync_date = sync_time
            phase.updated_at = sync_time
        
        # Update elevations sync timestamps
        elevations = self.db.query(Elevation).filter(Elevation.project_id == project.id).all()
        for elevation in elevations:
            elevation.last_sync_date = sync_time
            elevation.updated_at = sync_time
        
        self.db.commit()
        
        logger.info(f"Smart sync completed for project {project_id}: {len(phases)} phases, {len(elevations)} elevations")
        
        return {
            "synced_at": sync_time,
            "phases_synced": len(phases),
            "elevations_synced": len(elevations)
        }

    def get_sync_status_summary(self) -> Dict:
        """
        Get a summary of sync status for all projects.
        """
        projects = self.db.query(Project).all()
        total_projects = len(projects)
        stale_projects = 0
        projects_never_synced = 0
        
        for project in projects:
            if self.is_project_stale(project):
                stale_projects += 1
            if not project.last_sync_date:
                projects_never_synced += 1

        phases = self.db.query(Phase).all()
        total_phases = len(phases)
        stale_phases = sum(1 for phase in phases if self.is_phase_stale(phase))

        elevations = self.db.query(Elevation).all()
        total_elevations = len(elevations)
        stale_elevations = sum(1 for elevation in elevations if self.is_elevation_stale(elevation))

        return {
            "summary": {
                "total_projects": total_projects,
                "stale_projects": stale_projects,
                "projects_never_synced": projects_never_synced,
                "total_phases": total_phases,
                "stale_phases": stale_phases,
                "total_elevations": total_elevations,
                "stale_elevations": stale_elevations
            },
            "generated_at": datetime.utcnow()
        }

    def mark_project_as_updated(self, project_id: str, update_date: datetime = None) -> bool:
        """
        Mark a project as having been updated in Logikal.
        This would typically be called when we receive data from Logikal.
        """
        if update_date is None:
            update_date = datetime.utcnow()
        
        project = self.db.query(Project).filter(Project.logikal_id == project_id).first()
        if project:
            project.last_update_date = update_date
            project.updated_at = datetime.utcnow()
            self.db.commit()
            logger.info(f"Marked project {project_id} as updated at {update_date}")
            return True
        
        return False

    def mark_phase_as_updated(self, phase_id: str, update_date: datetime = None) -> bool:
        """
        Mark a phase as having been updated in Logikal.
        """
        if update_date is None:
            update_date = datetime.utcnow()
        
        phase = self.db.query(Phase).filter(Phase.logikal_id == phase_id).first()
        if phase:
            phase.last_update_date = update_date
            phase.updated_at = datetime.utcnow()
            self.db.commit()
            logger.info(f"Marked phase {phase_id} as updated at {update_date}")
            return True
        
        return False

    def mark_elevation_as_updated(self, elevation_id: str, update_date: datetime = None) -> bool:
        """
        Mark an elevation as having been updated in Logikal.
        """
        if update_date is None:
            update_date = datetime.utcnow()
        
        elevation = self.db.query(Elevation).filter(Elevation.logikal_id == elevation_id).first()
        if elevation:
            elevation.last_update_date = update_date
            elevation.updated_at = datetime.utcnow()
            self.db.commit()
            logger.info(f"Marked elevation {elevation_id} as updated at {update_date}")
            return True
        
        return False

    async def intelligent_sync_project(self, project_id: str, base_url: str, auth_token: str, 
                                     force_sync: bool = False) -> Dict:
        """
        Perform intelligent sync for a project with advanced features.
        """
        try:
            project = self.db.query(Project).filter(Project.logikal_id == project_id).first()
            if not project:
                return {"success": False, "error": "Project not found"}

            sync_result = {
                "project_id": project_id,
                "sync_type": "intelligent",
                "started_at": datetime.utcnow(),
                "completed_at": None,
                "success": False,
                "steps_completed": [],
                "metrics": {},
                "alerts_generated": []
            }

            # Step 1: Check data consistency before sync
            logger.info(f"Starting intelligent sync for project {project_id}")
            consistency_check = self.consistency_service.validate_project_consistency(project_id)
            
            if not consistency_check["valid"] and not force_sync:
                sync_result["error"] = "Data consistency issues detected. Use force_sync to override."
                sync_result["consistency_issues"] = consistency_check["errors"]
                return sync_result
            
            sync_result["steps_completed"].append("consistency_check")

            # Step 2: Use advanced sync service for intelligent staleness detection
            logikal_last_update = await self.advanced_sync_service.get_logikal_last_update_date(
                "project", project_id, base_url, auth_token
            )
            
            if not force_sync and not self.advanced_sync_service.is_object_stale(project, logikal_last_update):
                sync_result["success"] = True
                sync_result["reason"] = "Project is up-to-date"
                sync_result["completed_at"] = datetime.utcnow()
                return sync_result
            
            sync_result["steps_completed"].append("staleness_check")

            # Step 3: Perform cascading sync
            cascade_result = await self.advanced_sync_service.cascade_sync_project(
                project_id, base_url, auth_token
            )
            
            sync_result["cascade_result"] = cascade_result
            sync_result["steps_completed"].append("cascading_sync")

            # Step 4: Validate data consistency after sync
            post_sync_consistency = self.consistency_service.validate_project_consistency(project_id)
            sync_result["post_sync_consistency"] = post_sync_consistency
            sync_result["steps_completed"].append("post_sync_validation")

            # Step 5: Generate sync metrics
            project_metrics = self.metrics_service.get_project_sync_metrics(project_id, 24)
            sync_result["metrics"] = project_metrics
            sync_result["steps_completed"].append("metrics_generation")

            # Step 6: Check for alerts
            alerts = self.alert_service.check_sync_health_alerts()
            project_alerts = [alert for alert in alerts if project_id in str(alert.get('details', {}))]
            sync_result["alerts_generated"] = project_alerts
            sync_result["steps_completed"].append("alert_check")

            sync_result["success"] = cascade_result["success"]
            sync_result["completed_at"] = datetime.utcnow()

            logger.info(f"Intelligent sync completed for project {project_id}")
            return sync_result

        except Exception as e:
            logger.error(f"Error in intelligent sync for project {project_id}: {str(e)}")
            return {
                "success": False,
                "error": str(e),
                "project_id": project_id,
                "started_at": datetime.utcnow(),
                "completed_at": datetime.utcnow()
            }

    def get_smart_sync_recommendations(self, project_id: str) -> Dict:
        """
        Get smart sync recommendations for a project.
        """
        try:
            project = self.db.query(Project).filter(Project.logikal_id == project_id).first()
            if not project:
                return {"error": "Project not found"}

            recommendations = {
                "project_id": project_id,
                "generated_at": datetime.utcnow(),
                "recommendations": [],
                "priority": "medium"
            }

            # Check project staleness
            if self.is_project_stale(project):
                recommendations["recommendations"].append({
                    "type": "sync_needed",
                    "message": "Project data is stale and needs syncing",
                    "priority": "high"
                })
                recommendations["priority"] = "high"

            # Check data consistency
            consistency_check = self.consistency_service.validate_project_consistency(project_id)
            if not consistency_check["valid"]:
                recommendations["recommendations"].append({
                    "type": "consistency_repair",
                    "message": "Data consistency issues detected",
                    "priority": "critical",
                    "details": consistency_check["errors"]
                })
                recommendations["priority"] = "critical"

            # Check partial sync failures
            partial_failures = self.consistency_service.detect_partial_sync_failures(project_id)
            if partial_failures["has_partial_failures"]:
                recommendations["recommendations"].append({
                    "type": "partial_sync_failure",
                    "message": "Partial sync failures detected",
                    "priority": "high",
                    "details": partial_failures["inconsistencies"]
                })
                if recommendations["priority"] != "critical":
                    recommendations["priority"] = "high"

            # Check sync metrics
            project_metrics = self.metrics_service.get_project_sync_metrics(project_id, 168)
            if project_metrics.get("performance_analysis", {}).get("is_stale", False):
                recommendations["recommendations"].append({
                    "type": "performance_issue",
                    "message": "Project sync performance is below optimal",
                    "priority": "medium"
                })

            return recommendations

        except Exception as e:
            logger.error(f"Error getting smart sync recommendations for {project_id}: {str(e)}")
            return {"error": str(e)}

    def generate_sync_analytics(self, time_period_hours: int = 24) -> Dict:
        """
        Generate comprehensive sync analytics.
        """
        try:
            analytics = {
                "time_period_hours": time_period_hours,
                "generated_at": datetime.utcnow(),
                "overview": {},
                "detailed_metrics": {},
                "recommendations": []
            }

            # Get performance metrics
            performance_metrics = self.metrics_service.get_sync_performance_metrics(time_period_hours)
            analytics["detailed_metrics"]["performance"] = performance_metrics

            # Get efficiency report
            efficiency_report = self.metrics_service.get_sync_efficiency_report()
            analytics["detailed_metrics"]["efficiency"] = efficiency_report

            # Get data integrity report
            integrity_report = self.consistency_service.generate_data_integrity_report()
            analytics["detailed_metrics"]["integrity"] = integrity_report

            # Get current alerts
            alerts = self.alert_service.check_sync_health_alerts()
            analytics["detailed_metrics"]["alerts"] = {
                "total_alerts": len(alerts),
                "critical_alerts": len([a for a in alerts if a.get('severity') == 'critical']),
                "warning_alerts": len([a for a in alerts if a.get('severity') == 'warning'])
            }

            # Generate overview
            analytics["overview"] = {
                "sync_health": "healthy" if len(alerts) == 0 else "needs_attention",
                "efficiency_grade": efficiency_report.get("summary", {}).get("sync_efficiency_grade", "F"),
                "consistency_rate": integrity_report.get("summary", {}).get("consistency_rate", 0),
                "total_objects_synced": performance_metrics.get("sync_counts", {}).get("total", 0)
            }

            # Generate recommendations
            if analytics["overview"]["sync_health"] != "healthy":
                analytics["recommendations"].append("Address active alerts to improve sync health")

            if analytics["overview"]["efficiency_grade"] in ['D', 'F']:
                analytics["recommendations"].append("Optimize sync operations for better efficiency")

            if analytics["overview"]["consistency_rate"] < 90:
                analytics["recommendations"].append("Run data consistency repairs")

            return analytics

        except Exception as e:
            logger.error(f"Error generating sync analytics: {str(e)}")
            return {"error": str(e)}
