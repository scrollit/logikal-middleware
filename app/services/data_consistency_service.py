from sqlalchemy.orm import Session
from typing import List, Dict, Optional, Any, Tuple
from datetime import datetime, timedelta
from models.project import Project
from models.phase import Phase
from models.elevation import Elevation
import logging
import hashlib
import json

logger = logging.getLogger(__name__)


class DataConsistencyService:
    """
    Service for ensuring data consistency, validation, and recovery mechanisms.
    """

    def __init__(self, db: Session):
        self.db = db

    def validate_project_consistency(self, project_id: str) -> Dict:
        """
        Validate the consistency of a project and its related data.
        """
        try:
            project = self.db.query(Project).filter(Project.logikal_id == project_id).first()
            if not project:
                return {
                    "valid": False,
                    "errors": ["Project not found"],
                    "project_id": project_id
                }
            
            validation_results = {
                "project_id": project_id,
                "valid": True,
                "errors": [],
                "warnings": [],
                "checks": {}
            }
            
            # Check 1: Project has required fields
            required_fields = ["logikal_id", "name"]
            for field in required_fields:
                if not getattr(project, field, None):
                    validation_results["errors"].append(f"Missing required field: {field}")
                    validation_results["valid"] = False
            
            # Check 2: Project has valid timestamps
            if project.created_at and project.updated_at:
                if project.updated_at < project.created_at:
                    validation_results["errors"].append("Updated date is before created date")
                    validation_results["valid"] = False
            
            # Check 3: Sync timestamps are logical
            if project.last_sync_date and project.last_update_date:
                if project.last_sync_date < project.last_update_date:
                    validation_results["warnings"].append("Sync date is before update date")
            
            # Check 4: Validate phases consistency
            phases = self.db.query(Phase).filter(Phase.project_id == project.id).all()
            validation_results["checks"]["phases_count"] = len(phases)
            
            for phase in phases:
                phase_validation = self._validate_phase_consistency(phase)
                if not phase_validation["valid"]:
                    validation_results["errors"].extend([
                        f"Phase {phase.logikal_id}: {error}" 
                        for error in phase_validation["errors"]
                    ])
                    validation_results["valid"] = False
            
            # Check 5: Validate elevations consistency
            elevations = self.db.query(Elevation).filter(Elevation.project_id == project.id).all()
            validation_results["checks"]["elevations_count"] = len(elevations)
            
            for elevation in elevations:
                elevation_validation = self._validate_elevation_consistency(elevation)
                if not elevation_validation["valid"]:
                    validation_results["errors"].extend([
                        f"Elevation {elevation.logikal_id}: {error}" 
                        for error in elevation_validation["errors"]
                    ])
                    validation_results["valid"] = False
            
            # Check 6: Cross-reference consistency
            cross_ref_issues = self._check_cross_reference_consistency(project, phases, elevations)
            validation_results["errors"].extend(cross_ref_issues)
            if cross_ref_issues:
                validation_results["valid"] = False
            
            return validation_results
            
        except Exception as e:
            logger.error(f"Error validating project consistency for {project_id}: {str(e)}")
            return {
                "valid": False,
                "errors": [f"Validation error: {str(e)}"],
                "project_id": project_id
            }

    def _validate_phase_consistency(self, phase: Phase) -> Dict:
        """
        Validate individual phase consistency.
        """
        validation = {
            "valid": True,
            "errors": []
        }
        
        # Check required fields
        if not phase.logikal_id or not phase.name:
            validation["errors"].append("Missing required fields")
            validation["valid"] = False
        
        # Check project reference
        if phase.project_id:
            project = self.db.query(Project).filter(Project.id == phase.project_id).first()
            if not project:
                validation["errors"].append("Referenced project not found")
                validation["valid"] = False
        
        return validation

    def _validate_elevation_consistency(self, elevation: Elevation) -> Dict:
        """
        Validate individual elevation consistency.
        """
        validation = {
            "valid": True,
            "errors": []
        }
        
        # Check required fields
        if not elevation.logikal_id or not elevation.name:
            validation["errors"].append("Missing required fields")
            validation["valid"] = False
        
        # Check project reference
        if elevation.project_id:
            project = self.db.query(Project).filter(Project.id == elevation.project_id).first()
            if not project:
                validation["errors"].append("Referenced project not found")
                validation["valid"] = False
        
        # Check dimensions are positive
        for dimension in ["width", "height", "depth"]:
            value = getattr(elevation, dimension, None)
            if value is not None and value < 0:
                validation["errors"].append(f"Invalid {dimension}: {value}")
                validation["valid"] = False
        
        return validation

    def _check_cross_reference_consistency(self, project: Project, phases: List[Phase], 
                                         elevations: List[Elevation]) -> List[str]:
        """
        Check cross-reference consistency between projects, phases, and elevations.
        """
        issues = []
        
        # Check that all phases belong to the project
        for phase in phases:
            if phase.project_id != project.id:
                issues.append(f"Phase {phase.logikal_id} has incorrect project reference")
        
        # Check that all elevations belong to the project
        for elevation in elevations:
            if elevation.project_id != project.id:
                issues.append(f"Elevation {elevation.logikal_id} has incorrect project reference")
        
        # Check phase-elevation relationships
        for elevation in elevations:
            if elevation.phase_id:
                # Find the phase
                phase = next((p for p in phases if p.logikal_id == elevation.phase_id), None)
                if not phase:
                    issues.append(f"Elevation {elevation.logikal_id} references non-existent phase {elevation.phase_id}")
        
        return issues

    def detect_partial_sync_failures(self, project_id: str) -> Dict:
        """
        Detect and analyze partial sync failures for a project.
        """
        try:
            project = self.db.query(Project).filter(Project.logikal_id == project_id).first()
            if not project:
                return {
                    "has_partial_failures": False,
                    "errors": ["Project not found"],
                    "project_id": project_id
                }
            
            analysis = {
                "project_id": project_id,
                "has_partial_failures": False,
                "sync_status": {},
                "inconsistencies": [],
                "recommendations": []
            }
            
            # Analyze project sync status
            analysis["sync_status"]["project"] = {
                "last_sync_date": project.last_sync_date,
                "last_update_date": project.last_update_date,
                "is_synced": project.last_sync_date is not None
            }
            
            # Analyze phases sync status
            phases = self.db.query(Phase).filter(Phase.project_id == project.id).all()
            synced_phases = sum(1 for p in phases if p.last_sync_date is not None)
            analysis["sync_status"]["phases"] = {
                "total": len(phases),
                "synced": synced_phases,
                "unsynced": len(phases) - synced_phases
            }
            
            # Analyze elevations sync status
            elevations = self.db.query(Elevation).filter(Elevation.project_id == project.id).all()
            synced_elevations = sum(1 for e in elevations if e.last_sync_date is not None)
            analysis["sync_status"]["elevations"] = {
                "total": len(elevations),
                "synced": synced_elevations,
                "unsynced": len(elevations) - synced_elevations
            }
            
            # Detect inconsistencies
            if project.last_sync_date and synced_phases < len(phases):
                analysis["inconsistencies"].append(
                    f"Project synced but {len(phases) - synced_phases} phases not synced"
                )
                analysis["has_partial_failures"] = True
            
            if synced_phases > 0 and synced_elevations < len(elevations):
                analysis["inconsistencies"].append(
                    f"Some phases synced but {len(elevations) - synced_elevations} elevations not synced"
                )
                analysis["has_partial_failures"] = True
            
            # Check for orphaned objects
            orphaned_phases = [p for p in phases if p.project_id != project.id]
            if orphaned_phases:
                analysis["inconsistencies"].append(
                    f"Found {len(orphaned_phases)} orphaned phases"
                )
                analysis["has_partial_failures"] = True
            
            orphaned_elevations = [e for e in elevations if e.project_id != project.id]
            if orphaned_elevations:
                analysis["inconsistencies"].append(
                    f"Found {len(orphaned_elevations)} orphaned elevations"
                )
                analysis["has_partial_failures"] = True
            
            # Generate recommendations
            if analysis["has_partial_failures"]:
                analysis["recommendations"].append("Run full project sync to resolve inconsistencies")
                
                if synced_phases < len(phases):
                    analysis["recommendations"].append("Sync remaining phases")
                
                if synced_elevations < len(elevations):
                    analysis["recommendations"].append("Sync remaining elevations")
                
                if orphaned_phases or orphaned_elevations:
                    analysis["recommendations"].append("Fix orphaned object references")
            
            return analysis
            
        except Exception as e:
            logger.error(f"Error detecting partial sync failures for {project_id}: {str(e)}")
            return {
                "has_partial_failures": False,
                "errors": [f"Analysis error: {str(e)}"],
                "project_id": project_id
            }

    def repair_data_consistency(self, project_id: str) -> Dict:
        """
        Attempt to repair data consistency issues for a project.
        """
        try:
            project = self.db.query(Project).filter(Project.logikal_id == project_id).first()
            if not project:
                return {
                    "success": False,
                    "error": "Project not found",
                    "project_id": project_id
                }
            
            repair_results = {
                "project_id": project_id,
                "success": True,
                "repairs_made": [],
                "errors": [],
                "started_at": datetime.utcnow(),
                "completed_at": None
            }
            
            # Repair 1: Fix orphaned phases
            orphaned_phases = self.db.query(Phase).filter(
                Phase.project_id != project.id
            ).filter(
                Phase.project_id.in_([p.id for p in self.db.query(Project).filter(Project.logikal_id == project_id).all()])
            ).all()
            
            for phase in orphaned_phases:
                phase.project_id = project.id
                repair_results["repairs_made"].append(f"Fixed orphaned phase {phase.logikal_id}")
            
            # Repair 2: Fix orphaned elevations
            orphaned_elevations = self.db.query(Elevation).filter(
                Elevation.project_id != project.id
            ).filter(
                Elevation.project_id.in_([p.id for p in self.db.query(Project).filter(Project.logikal_id == project_id).all()])
            ).all()
            
            for elevation in orphaned_elevations:
                elevation.project_id = project.id
                repair_results["repairs_made"].append(f"Fixed orphaned elevation {elevation.logikal_id}")
            
            # Repair 3: Fix invalid timestamps
            if project.updated_at and project.created_at and project.updated_at < project.created_at:
                project.updated_at = project.created_at
                repair_results["repairs_made"].append("Fixed invalid updated timestamp")
            
            # Repair 4: Set default sync dates for unsynced objects
            phases = self.db.query(Phase).filter(Phase.project_id == project.id).all()
            for phase in phases:
                if not phase.last_sync_date:
                    phase.last_sync_date = project.created_at
                    repair_results["repairs_made"].append(f"Set default sync date for phase {phase.logikal_id}")
            
            elevations = self.db.query(Elevation).filter(Elevation.project_id == project.id).all()
            for elevation in elevations:
                if not elevation.last_sync_date:
                    elevation.last_sync_date = project.created_at
                    repair_results["repairs_made"].append(f"Set default sync date for elevation {elevation.logikal_id}")
            
            # Commit all repairs
            try:
                self.db.commit()
                repair_results["completed_at"] = datetime.utcnow()
            except Exception as e:
                self.db.rollback()
                repair_results["success"] = False
                repair_results["errors"].append(f"Failed to commit repairs: {str(e)}")
            
            return repair_results
            
        except Exception as e:
            logger.error(f"Error repairing data consistency for {project_id}: {str(e)}")
            return {
                "success": False,
                "error": str(e),
                "project_id": project_id,
                "started_at": datetime.utcnow(),
                "completed_at": datetime.utcnow()
            }

    def generate_data_integrity_report(self, project_id: Optional[str] = None) -> Dict:
        """
        Generate a comprehensive data integrity report.
        """
        try:
            report = {
                "generated_at": datetime.utcnow(),
                "scope": "all_projects" if not project_id else f"project_{project_id}",
                "summary": {},
                "detailed_analysis": [],
                "recommendations": []
            }
            
            if project_id:
                # Analyze specific project
                projects = [self.db.query(Project).filter(Project.logikal_id == project_id).first()]
                projects = [p for p in projects if p]  # Remove None values
            else:
                # Analyze all projects
                projects = self.db.query(Project).all()
            
            total_projects = len(projects)
            consistent_projects = 0
            projects_with_issues = 0
            
            for project in projects:
                validation = self.validate_project_consistency(project.logikal_id)
                partial_failure_analysis = self.detect_partial_sync_failures(project.logikal_id)
                
                project_analysis = {
                    "project_id": project.logikal_id,
                    "project_name": project.name,
                    "validation": validation,
                    "partial_failure_analysis": partial_failure_analysis
                }
                
                report["detailed_analysis"].append(project_analysis)
                
                if validation["valid"] and not partial_failure_analysis["has_partial_failures"]:
                    consistent_projects += 1
                else:
                    projects_with_issues += 1
            
            # Generate summary
            report["summary"] = {
                "total_projects": total_projects,
                "consistent_projects": consistent_projects,
                "projects_with_issues": projects_with_issues,
                "consistency_rate": (consistent_projects / total_projects * 100) if total_projects > 0 else 0
            }
            
            # Generate recommendations
            if projects_with_issues > 0:
                report["recommendations"].append("Run data consistency repairs for projects with issues")
                report["recommendations"].append("Schedule regular data integrity checks")
            
            if report["summary"]["consistency_rate"] < 90:
                report["recommendations"].append("Investigate root causes of data inconsistencies")
            
            return report
            
        except Exception as e:
            logger.error(f"Error generating data integrity report: {str(e)}")
            return {
                "generated_at": datetime.utcnow(),
                "error": str(e),
                "summary": {"error": "Failed to generate report"}
            }

    def calculate_data_hash(self, project_id: str) -> str:
        """
        Calculate a hash of all data for a project to detect changes.
        """
        try:
            project = self.db.query(Project).filter(Project.logikal_id == project_id).first()
            if not project:
                return ""
            
            # Collect all data for hashing
            data_to_hash = {
                "project": {
                    "id": project.logikal_id,
                    "name": project.name,
                    "description": project.description,
                    "status": project.status,
                    "last_sync_date": project.last_sync_date.isoformat() if project.last_sync_date else None,
                    "last_update_date": project.last_update_date.isoformat() if project.last_update_date else None
                },
                "phases": [],
                "elevations": []
            }
            
            # Add phases data
            phases = self.db.query(Phase).filter(Phase.project_id == project.id).all()
            for phase in phases:
                data_to_hash["phases"].append({
                    "id": phase.logikal_id,
                    "name": phase.name,
                    "description": phase.description,
                    "status": phase.status,
                    "last_sync_date": phase.last_sync_date.isoformat() if phase.last_sync_date else None,
                    "last_update_date": phase.last_update_date.isoformat() if phase.last_update_date else None
                })
            
            # Add elevations data
            elevations = self.db.query(Elevation).filter(Elevation.project_id == project.id).all()
            for elevation in elevations:
                data_to_hash["elevations"].append({
                    "id": elevation.logikal_id,
                    "name": elevation.name,
                    "description": elevation.description,
                    "width": elevation.width,
                    "height": elevation.height,
                    "depth": elevation.depth,
                    "phase_id": elevation.phase_id,
                    "last_sync_date": elevation.last_sync_date.isoformat() if elevation.last_sync_date else None,
                    "last_update_date": elevation.last_update_date.isoformat() if elevation.last_update_date else None
                })
            
            # Generate hash
            data_string = json.dumps(data_to_hash, sort_keys=True)
            return hashlib.sha256(data_string.encode()).hexdigest()
            
        except Exception as e:
            logger.error(f"Error calculating data hash for {project_id}: {str(e)}")
            return ""

    def compare_data_hashes(self, project_id: str, previous_hash: str) -> Dict:
        """
        Compare current data hash with a previous hash to detect changes.
        """
        try:
            current_hash = self.calculate_data_hash(project_id)
            
            return {
                "project_id": project_id,
                "current_hash": current_hash,
                "previous_hash": previous_hash,
                "has_changed": current_hash != previous_hash,
                "comparison_time": datetime.utcnow()
            }
            
        except Exception as e:
            logger.error(f"Error comparing data hashes for {project_id}: {str(e)}")
            return {
                "project_id": project_id,
                "error": str(e),
                "has_changed": False
            }
