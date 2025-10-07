import logging
from typing import List, Optional, Dict, Tuple
from sqlalchemy.orm import Session
from models.project import Project
from models.phase import Phase
from models.elevation import Elevation
from services.client_auth_service import ClientAuthService

logger = logging.getLogger(__name__)


class DirectProjectService:
    """Service for direct project access without directory context"""
    
    def __init__(self, db: Session):
        self.db = db
    
    async def get_all_projects(self) -> List[Project]:
        """Get all projects from database (no directory context needed)"""
        try:
            projects = self.db.query(Project).all()
            logger.info(f"Retrieved {len(projects)} projects from database")
            return projects
        except Exception as e:
            logger.error(f"Failed to get projects: {str(e)}")
            return []
    
    async def get_project_by_id(self, project_id: str) -> Optional[Project]:
        """Get a specific project by its Logikal ID"""
        try:
            project = self.db.query(Project).filter(
                Project.logikal_id == project_id
            ).first()
            
            if project:
                logger.info(f"Retrieved project: {project.name} ({project.logikal_id})")
            else:
                logger.warning(f"Project not found: {project_id}")
            
            return project
        except Exception as e:
            logger.error(f"Failed to get project {project_id}: {str(e)}")
            return None
    
    async def get_project_with_phases(self, project_id: str) -> Optional[Dict]:
        """Get project with all its phases"""
        try:
            project = await self.get_project_by_id(project_id)
            if not project:
                return None
            
            # Get phases for this project
            phases = self.db.query(Phase).filter(
                Phase.project_id == project.id
            ).all()
            
            return {
                "project": project,
                "phases": phases,
                "phases_count": len(phases)
            }
        except Exception as e:
            logger.error(f"Failed to get project with phases {project_id}: {str(e)}")
            return None
    
    async def get_project_with_elevations(self, project_id: str) -> Optional[Dict]:
        """Get project with all its elevations (across all phases)"""
        try:
            project = await self.get_project_by_id(project_id)
            if not project:
                return None
            
            # Get all phases for this project
            phases = self.db.query(Phase).filter(
                Phase.project_id == project.id
            ).all()
            
            # Get all elevations for all phases
            all_elevations = []
            for phase in phases:
                elevations = self.db.query(Elevation).filter(
                    Elevation.phase_id == phase.id
                ).all()
                all_elevations.extend(elevations)
            
            return {
                "project": project,
                "phases": phases,
                "elevations": all_elevations,
                "phases_count": len(phases),
                "elevations_count": len(all_elevations)
            }
        except Exception as e:
            logger.error(f"Failed to get project with elevations {project_id}: {str(e)}")
            return None
    
    async def get_project_complete(self, project_id: str) -> Optional[Dict]:
        """Get complete project data: project + phases + elevations with metadata"""
        try:
            project = await self.get_project_by_id(project_id)
            if not project:
                return None
            
            # Get phases for this project
            phases = self.db.query(Phase).filter(
                Phase.project_id == project.id
            ).all()
            
            # Get elevations for each phase
            phases_with_elevations = []
            total_elevations = 0
            
            for phase in phases:
                elevations = self.db.query(Elevation).filter(
                    Elevation.phase_id == phase.id
                ).all()
                
                phases_with_elevations.append({
                    "phase": phase,
                    "elevations": elevations,
                    "elevations_count": len(elevations)
                })
                total_elevations += len(elevations)
            
            return {
                "project": project,
                "phases_with_elevations": phases_with_elevations,
                "summary": {
                    "phases_count": len(phases),
                    "total_elevations": total_elevations,
                    "project_name": project.name,
                    "project_id": project.logikal_id
                }
            }
        except Exception as e:
            logger.error(f"Failed to get complete project data {project_id}: {str(e)}")
            return None
    
    async def get_phase_by_id(self, phase_id: str) -> Optional[Phase]:
        """Get a specific phase by its Logikal ID"""
        try:
            phase = self.db.query(Phase).filter(
                Phase.logikal_id == phase_id
            ).first()
            
            if phase:
                logger.info(f"Retrieved phase: {phase.name} ({phase.logikal_id})")
            else:
                logger.warning(f"Phase not found: {phase_id}")
            
            return phase
        except Exception as e:
            logger.error(f"Failed to get phase {phase_id}: {str(e)}")
            return None
    
    async def get_phase_with_elevations(self, phase_id: str) -> Optional[Dict]:
        """Get phase with all its elevations"""
        try:
            phase = await self.get_phase_by_id(phase_id)
            if not phase:
                return None
            
            # Get elevations for this phase
            elevations = self.db.query(Elevation).filter(
                Elevation.phase_id == phase.id
            ).all()
            
            return {
                "phase": phase,
                "elevations": elevations,
                "elevations_count": len(elevations)
            }
        except Exception as e:
            logger.error(f"Failed to get phase with elevations {phase_id}: {str(e)}")
            return None
    
    async def get_phase_with_elevations_by_project(self, project_id: str, phase_id: str) -> Optional[Dict]:
        """Get phase with all its elevations using project context to avoid duplicate logikal_ids"""
        try:
            # First get the project to ensure it exists
            project = self.db.query(Project).filter(
                Project.logikal_id == project_id
            ).first()
            
            if not project:
                logger.warning(f"Project not found: {project_id}")
                return None
            
            # Get the phase within this specific project
            phase = self.db.query(Phase).filter(
                Phase.logikal_id == phase_id,
                Phase.project_id == project.id
            ).first()
            
            if not phase:
                logger.warning(f"Phase not found: {phase_id} in project {project_id}")
                return None
            
            # Get elevations for this phase
            elevations = self.db.query(Elevation).filter(
                Elevation.phase_id == phase.id
            ).all()
            
            logger.info(f"Retrieved phase: {phase.name} ({phase.logikal_id}) in project: {project.name} with {len(elevations)} elevations")
            
            return {
                "phase": phase,
                "elevations": elevations,
                "elevations_count": len(elevations)
            }
        except Exception as e:
            logger.error(f"Failed to get phase with elevations {phase_id} in project {project_id}: {str(e)}")
            return None
    
    async def get_elevation_by_id(self, elevation_id: str) -> Optional[Elevation]:
        """Get a specific elevation by its Logikal ID"""
        try:
            elevation = self.db.query(Elevation).filter(
                Elevation.logikal_id == elevation_id
            ).first()
            
            if elevation:
                logger.info(f"Retrieved elevation: {elevation.name} ({elevation.logikal_id})")
            else:
                logger.warning(f"Elevation not found: {elevation_id}")
            
            return elevation
        except Exception as e:
            logger.error(f"Failed to get elevation {elevation_id}: {str(e)}")
            return None
    
    async def search_projects(self, query: str) -> List[Project]:
        """Search projects by name or description"""
        try:
            projects = self.db.query(Project).filter(
                Project.name.ilike(f"%{query}%") | 
                Project.description.ilike(f"%{query}%")
            ).all()
            
            logger.info(f"Found {len(projects)} projects matching '{query}'")
            return projects
        except Exception as e:
            logger.error(f"Failed to search projects: {str(e)}")
            return []
    
    async def get_projects_summary(self) -> Dict:
        """Get summary statistics of all projects"""
        try:
            total_projects = self.db.query(Project).count()
            total_phases = self.db.query(Phase).count()
            total_elevations = self.db.query(Elevation).count()
            
            # Get projects with their phase counts
            projects_with_counts = []
            for project in self.db.query(Project).all():
                phase_count = self.db.query(Phase).filter(
                    Phase.project_id == project.id
                ).count()
                projects_with_counts.append({
                    "project_id": project.logikal_id,
                    "project_name": project.name,
                    "phases_count": phase_count
                })
            
            return {
                "total_projects": total_projects,
                "total_phases": total_phases,
                "total_elevations": total_elevations,
                "projects": projects_with_counts
            }
        except Exception as e:
            logger.error(f"Failed to get projects summary: {str(e)}")
            return {
                "total_projects": 0,
                "total_phases": 0,
                "total_elevations": 0,
                "projects": []
            }
