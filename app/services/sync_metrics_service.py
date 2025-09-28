from sqlalchemy.orm import Session
from typing import List, Dict, Optional, Any, Tuple
from datetime import datetime, timedelta
from models.project import Project
from models.phase import Phase
from models.elevation import Elevation
import logging
import statistics

logger = logging.getLogger(__name__)


class SyncMetricsService:
    """
    Service for collecting, analyzing, and reporting sync performance metrics.
    """

    def __init__(self, db: Session):
        self.db = db

    def get_sync_performance_metrics(self, time_period_hours: int = 24) -> Dict:
        """
        Get comprehensive sync performance metrics for the specified time period.
        """
        try:
            cutoff_time = datetime.utcnow() - timedelta(hours=time_period_hours)
            
            metrics = {
                "time_period_hours": time_period_hours,
                "generated_at": datetime.utcnow(),
                "sync_counts": {},
                "performance_metrics": {},
                "data_quality_metrics": {},
                "trends": {}
            }
            
            # Get sync counts
            projects_synced = self.db.query(Project).filter(
                Project.last_sync_date >= cutoff_time
            ).count()
            
            phases_synced = self.db.query(Phase).filter(
                Phase.last_sync_date >= cutoff_time
            ).count()
            
            elevations_synced = self.db.query(Elevation).filter(
                Elevation.last_sync_date >= cutoff_time
            ).count()
            
            metrics["sync_counts"] = {
                "projects": projects_synced,
                "phases": phases_synced,
                "elevations": elevations_synced,
                "total": projects_synced + phases_synced + elevations_synced
            }
            
            # Calculate performance metrics
            metrics["performance_metrics"] = self._calculate_performance_metrics(cutoff_time)
            
            # Calculate data quality metrics
            metrics["data_quality_metrics"] = self._calculate_data_quality_metrics()
            
            # Calculate trends
            metrics["trends"] = self._calculate_trends(time_period_hours)
            
            return metrics
            
        except Exception as e:
            logger.error(f"Error getting sync performance metrics: {str(e)}")
            return {
                "error": str(e),
                "generated_at": datetime.utcnow()
            }

    def _calculate_performance_metrics(self, cutoff_time: datetime) -> Dict:
        """
        Calculate performance metrics for sync operations.
        """
        try:
            # Get all objects synced in the time period
            projects = self.db.query(Project).filter(
                Project.last_sync_date >= cutoff_time
            ).all()
            
            phases = self.db.query(Phase).filter(
                Phase.last_sync_date >= cutoff_time
            ).all()
            
            elevations = self.db.query(Elevation).filter(
                Elevation.last_sync_date >= cutoff_time
            ).all()
            
            all_objects = projects + phases + elevations
            
            if not all_objects:
                return {
                    "avg_sync_frequency": 0,
                    "sync_throughput_per_hour": 0,
                    "data_freshness_score": 0
                }
            
            # Calculate average sync frequency
            sync_dates = [obj.last_sync_date for obj in all_objects if obj.last_sync_date]
            if sync_dates:
                time_diffs = [(datetime.utcnow() - sync_date).total_seconds() / 3600 for sync_date in sync_dates]
                avg_sync_frequency = statistics.mean(time_diffs) if time_diffs else 0
            else:
                avg_sync_frequency = 0
            
            # Calculate sync throughput (objects per hour)
            time_span_hours = (datetime.utcnow() - cutoff_time).total_seconds() / 3600
            sync_throughput_per_hour = len(all_objects) / time_span_hours if time_span_hours > 0 else 0
            
            # Calculate data freshness score (percentage of objects synced recently)
            recent_cutoff = datetime.utcnow() - timedelta(hours=1)
            recent_syncs = sum(1 for obj in all_objects if obj.last_sync_date and obj.last_sync_date >= recent_cutoff)
            data_freshness_score = (recent_syncs / len(all_objects) * 100) if all_objects else 0
            
            return {
                "avg_sync_frequency_hours": round(avg_sync_frequency, 2),
                "sync_throughput_per_hour": round(sync_throughput_per_hour, 2),
                "data_freshness_score": round(data_freshness_score, 2),
                "total_objects_synced": len(all_objects)
            }
            
        except Exception as e:
            logger.error(f"Error calculating performance metrics: {str(e)}")
            return {"error": str(e)}

    def _calculate_data_quality_metrics(self) -> Dict:
        """
        Calculate data quality metrics.
        """
        try:
            total_projects = self.db.query(Project).count()
            total_phases = self.db.query(Phase).count()
            total_elevations = self.db.query(Elevation).count()
            
            # Calculate sync coverage
            synced_projects = self.db.query(Project).filter(
                Project.last_sync_date.isnot(None)
            ).count()
            
            synced_phases = self.db.query(Phase).filter(
                Phase.last_sync_date.isnot(None)
            ).count()
            
            synced_elevations = self.db.query(Elevation).filter(
                Elevation.last_sync_date.isnot(None)
            ).count()
            
            # Calculate stale data percentages
            stale_threshold = datetime.utcnow() - timedelta(hours=24)
            
            stale_projects = self.db.query(Project).filter(
                Project.last_sync_date < stale_threshold
            ).count()
            
            stale_phases = self.db.query(Phase).filter(
                Phase.last_sync_date < stale_threshold
            ).count()
            
            stale_elevations = self.db.query(Elevation).filter(
                Elevation.last_sync_date < stale_threshold
            ).count()
            
            return {
                "total_counts": {
                    "projects": total_projects,
                    "phases": total_phases,
                    "elevations": total_elevations
                },
                "sync_coverage": {
                    "projects": round((synced_projects / total_projects * 100) if total_projects > 0 else 0, 2),
                    "phases": round((synced_phases / total_phases * 100) if total_phases > 0 else 0, 2),
                    "elevations": round((synced_elevations / total_elevations * 100) if total_elevations > 0 else 0, 2)
                },
                "stale_data_percentage": {
                    "projects": round((stale_projects / total_projects * 100) if total_projects > 0 else 0, 2),
                    "phases": round((stale_phases / total_phases * 100) if total_phases > 0 else 0, 2),
                    "elevations": round((stale_elevations / total_elevations * 100) if total_elevations > 0 else 0, 2)
                }
            }
            
        except Exception as e:
            logger.error(f"Error calculating data quality metrics: {str(e)}")
            return {"error": str(e)}

    def _calculate_trends(self, time_period_hours: int) -> Dict:
        """
        Calculate sync trends over time.
        """
        try:
            # Divide time period into hourly buckets
            hourly_buckets = []
            current_time = datetime.utcnow()
            
            for i in range(time_period_hours):
                bucket_start = current_time - timedelta(hours=i+1)
                bucket_end = current_time - timedelta(hours=i)
                
                projects_in_bucket = self.db.query(Project).filter(
                    Project.last_sync_date >= bucket_start,
                    Project.last_sync_date < bucket_end
                ).count()
                
                phases_in_bucket = self.db.query(Phase).filter(
                    Phase.last_sync_date >= bucket_start,
                    Phase.last_sync_date < bucket_end
                ).count()
                
                elevations_in_bucket = self.db.query(Elevation).filter(
                    Elevation.last_sync_date >= bucket_start,
                    Elevation.last_sync_date < bucket_end
                ).count()
                
                hourly_buckets.append({
                    "hour": bucket_start.strftime("%Y-%m-%d %H:00"),
                    "projects": projects_in_bucket,
                    "phases": phases_in_bucket,
                    "elevations": elevations_in_bucket,
                    "total": projects_in_bucket + phases_in_bucket + elevations_in_bucket
                })
            
            # Calculate trend direction
            if len(hourly_buckets) >= 2:
                recent_total = sum(bucket["total"] for bucket in hourly_buckets[:6])  # Last 6 hours
                older_total = sum(bucket["total"] for bucket in hourly_buckets[6:12])  # Previous 6 hours
                
                if recent_total > older_total:
                    trend_direction = "increasing"
                elif recent_total < older_total:
                    trend_direction = "decreasing"
                else:
                    trend_direction = "stable"
            else:
                trend_direction = "insufficient_data"
            
            return {
                "hourly_data": hourly_buckets,
                "trend_direction": trend_direction,
                "peak_hour": max(hourly_buckets, key=lambda x: x["total"])["hour"] if hourly_buckets else None
            }
            
        except Exception as e:
            logger.error(f"Error calculating trends: {str(e)}")
            return {"error": str(e)}

    def get_project_sync_metrics(self, project_id: str, time_period_hours: int = 168) -> Dict:
        """
        Get detailed sync metrics for a specific project.
        """
        try:
            project = self.db.query(Project).filter(Project.logikal_id == project_id).first()
            if not project:
                return {
                    "error": "Project not found",
                    "project_id": project_id
                }
            
            cutoff_time = datetime.utcnow() - timedelta(hours=time_period_hours)
            
            metrics = {
                "project_id": project_id,
                "project_name": project.name,
                "time_period_hours": time_period_hours,
                "generated_at": datetime.utcnow(),
                "sync_history": {},
                "performance_analysis": {},
                "data_quality": {}
            }
            
            # Get phases and elevations for this project
            phases = self.db.query(Phase).filter(Phase.project_id == project.id).all()
            elevations = self.db.query(Elevation).filter(Elevation.project_id == project.id).all()
            
            # Analyze sync history
            project_last_sync = project.last_sync_date
            phases_synced = sum(1 for p in phases if p.last_sync_date and p.last_sync_date >= cutoff_time)
            elevations_synced = sum(1 for e in elevations if e.last_sync_date and e.last_sync_date >= cutoff_time)
            
            metrics["sync_history"] = {
                "project_last_sync": project_last_sync.isoformat() if project_last_sync else None,
                "phases_synced": phases_synced,
                "total_phases": len(phases),
                "elevations_synced": elevations_synced,
                "total_elevations": len(elevations),
                "sync_completion_rate": round(
                    ((1 if project_last_sync else 0) + phases_synced + elevations_synced) / 
                    (1 + len(phases) + len(elevations)) * 100, 2
                )
            }
            
            # Performance analysis
            if project_last_sync:
                time_since_sync = (datetime.utcnow() - project_last_sync).total_seconds() / 3600
                metrics["performance_analysis"] = {
                    "hours_since_last_sync": round(time_since_sync, 2),
                    "sync_frequency_score": max(0, 100 - (time_since_sync / 24 * 100)),  # Score decreases over time
                    "is_stale": time_since_sync > 24
                }
            else:
                metrics["performance_analysis"] = {
                    "hours_since_last_sync": None,
                    "sync_frequency_score": 0,
                    "is_stale": True
                }
            
            # Data quality analysis
            stale_threshold = datetime.utcnow() - timedelta(hours=24)
            stale_phases = sum(1 for p in phases if not p.last_sync_date or p.last_sync_date < stale_threshold)
            stale_elevations = sum(1 for e in elevations if not e.last_sync_date or e.last_sync_date < stale_threshold)
            
            metrics["data_quality"] = {
                "stale_phases": stale_phases,
                "stale_elevations": stale_elevations,
                "data_freshness_score": round(
                    (len(phases) - stale_phases + len(elevations) - stale_elevations) / 
                    (len(phases) + len(elevations)) * 100, 2
                ) if (phases or elevations) else 100
            }
            
            return metrics
            
        except Exception as e:
            logger.error(f"Error getting project sync metrics for {project_id}: {str(e)}")
            return {
                "error": str(e),
                "project_id": project_id,
                "generated_at": datetime.utcnow()
            }

    def get_sync_efficiency_report(self) -> Dict:
        """
        Generate a comprehensive sync efficiency report.
        """
        try:
            report = {
                "generated_at": datetime.utcnow(),
                "summary": {},
                "efficiency_analysis": {},
                "recommendations": []
            }
            
            # Get overall metrics
            metrics_24h = self.get_sync_performance_metrics(24)
            metrics_168h = self.get_sync_performance_metrics(168)  # 1 week
            
            # Calculate summary statistics
            total_objects = metrics_24h.get("sync_counts", {}).get("total", 0)
            throughput = metrics_24h.get("performance_metrics", {}).get("sync_throughput_per_hour", 0)
            freshness_score = metrics_24h.get("performance_metrics", {}).get("data_freshness_score", 0)
            
            report["summary"] = {
                "objects_synced_24h": total_objects,
                "throughput_per_hour": throughput,
                "data_freshness_score": freshness_score,
                "sync_efficiency_grade": self._calculate_efficiency_grade(freshness_score, throughput)
            }
            
            # Efficiency analysis
            report["efficiency_analysis"] = {
                "sync_coverage": metrics_24h.get("data_quality_metrics", {}).get("sync_coverage", {}),
                "stale_data": metrics_24h.get("data_quality_metrics", {}).get("stale_data_percentage", {}),
                "trends": metrics_24h.get("trends", {}),
                "performance_comparison": self._compare_performance_periods(metrics_24h, metrics_168h)
            }
            
            # Generate recommendations
            if freshness_score < 80:
                report["recommendations"].append("Increase sync frequency to improve data freshness")
            
            if throughput < 10:
                report["recommendations"].append("Consider optimizing sync operations for better throughput")
            
            stale_data = metrics_24h.get("data_quality_metrics", {}).get("stale_data_percentage", {})
            if any(percentage > 20 for percentage in stale_data.values()):
                report["recommendations"].append("Address stale data issues in affected object types")
            
            return report
            
        except Exception as e:
            logger.error(f"Error generating sync efficiency report: {str(e)}")
            return {
                "error": str(e),
                "generated_at": datetime.utcnow()
            }

    def _calculate_efficiency_grade(self, freshness_score: float, throughput: float) -> str:
        """
        Calculate an efficiency grade based on freshness and throughput.
        """
        if freshness_score >= 90 and throughput >= 20:
            return "A"
        elif freshness_score >= 80 and throughput >= 15:
            return "B"
        elif freshness_score >= 70 and throughput >= 10:
            return "C"
        elif freshness_score >= 60 and throughput >= 5:
            return "D"
        else:
            return "F"

    def _compare_performance_periods(self, metrics_24h: Dict, metrics_168h: Dict) -> Dict:
        """
        Compare performance between 24h and 168h periods.
        """
        try:
            throughput_24h = metrics_24h.get("performance_metrics", {}).get("sync_throughput_per_hour", 0)
            throughput_168h = metrics_168h.get("performance_metrics", {}).get("sync_throughput_per_hour", 0)
            
            freshness_24h = metrics_24h.get("performance_metrics", {}).get("data_freshness_score", 0)
            freshness_168h = metrics_168h.get("performance_metrics", {}).get("data_freshness_score", 0)
            
            return {
                "throughput_change": round(throughput_24h - throughput_168h, 2),
                "freshness_change": round(freshness_24h - freshness_168h, 2),
                "performance_trend": "improving" if throughput_24h > throughput_168h else "declining"
            }
        except Exception as e:
            logger.error(f"Error comparing performance periods: {str(e)}")
            return {"error": str(e)}
