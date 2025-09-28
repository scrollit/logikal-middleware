from sqlalchemy.orm import Session
from typing import List, Dict, Optional, Any, Tuple
from datetime import datetime, timedelta
from models.project import Project
from models.phase import Phase
from models.elevation import Elevation
# from services.smart_sync_service import SmartSyncService  # Avoid circular import
import logging
import asyncio
import aiohttp
from core.config import settings

logger = logging.getLogger(__name__)


class AdvancedSyncService:
    """
    Advanced sync service with intelligent staleness detection, cascading sync,
    and sophisticated sync strategies.
    """

    def __init__(self, db: Session):
        self.db = db
        # self.smart_sync_service = SmartSyncService(db)  # Avoid circular import

    async def get_logikal_last_update_date(self, object_type: str, object_id: str, 
                                         base_url: str, auth_token: str) -> Optional[datetime]:
        """
        Fetch the last update date for an object from Logikal API.
        This simulates getting the actual last_update_date from Logikal.
        """
        try:
            # For now, we'll simulate this by making a request to Logikal
            # In a real implementation, this would fetch the actual last_update_date
            
            headers = {
                "Authorization": f"Bearer {auth_token}",
                "Content-Type": "application/json"
            }
            
            # Simulate different endpoints for different object types
            if object_type == "project":
                url = f"{base_url}/api/v1/projects/{object_id}"
            elif object_type == "phase":
                url = f"{base_url}/api/v1/phases/{object_id}"
            elif object_type == "elevation":
                url = f"{base_url}/api/v1/elevations/{object_id}"
            else:
                return None
            
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=headers) as response:
                    if response.status == 200:
                        data = await response.json()
                        # Simulate extracting last_update_date from response
                        # In real implementation, this would come from Logikal's response
                        return datetime.utcnow() - timedelta(hours=1)  # Simulate 1 hour ago
                    else:
                        logger.warning(f"Failed to fetch {object_type} {object_id}: {response.status}")
                        return None
        except Exception as e:
            logger.error(f"Error fetching last update date for {object_type} {object_id}: {str(e)}")
            return None

    def is_object_stale(self, obj: Any, logikal_last_update: Optional[datetime] = None) -> bool:
        """
        Determine if an object is stale based on intelligent comparison.
        """
        if not obj:
            return True
        
        # If we have a Logikal last_update_date, compare it with our last_sync_date
        if logikal_last_update and obj.last_sync_date:
            return logikal_last_update > obj.last_sync_date
        
        # If no last_sync_date, object is stale
        if not obj.last_sync_date:
            return True
        
        # If we don't have Logikal's last_update_date, use a default staleness threshold
        staleness_threshold = timedelta(hours=24)  # Default: 24 hours
        return datetime.utcnow() - obj.last_sync_date > staleness_threshold

    async def get_stale_objects(self, object_type: str, base_url: str, auth_token: str) -> List[Dict]:
        """
        Get all stale objects of a specific type that need syncing.
        """
        try:
            if object_type == "project":
                objects = self.db.query(Project).all()
            elif object_type == "phase":
                objects = self.db.query(Phase).all()
            elif object_type == "elevation":
                objects = self.db.query(Elevation).all()
            else:
                return []
            
            stale_objects = []
            
            # Check each object for staleness
            for obj in objects:
                # Get Logikal's last_update_date for this object
                logikal_last_update = await self.get_logikal_last_update_date(
                    object_type, obj.logikal_id, base_url, auth_token
                )
                
                if self.is_object_stale(obj, logikal_last_update):
                    stale_objects.append({
                        "id": obj.id,
                        "logikal_id": obj.logikal_id,
                        "name": obj.name,
                        "last_sync_date": obj.last_sync_date,
                        "logikal_last_update": logikal_last_update,
                        "staleness_reason": self._get_staleness_reason(obj, logikal_last_update)
                    })
            
            return stale_objects
        except Exception as e:
            logger.error(f"Error getting stale {object_type} objects: {str(e)}")
            return []

    def _get_staleness_reason(self, obj: Any, logikal_last_update: Optional[datetime]) -> str:
        """
        Get a human-readable reason for why an object is stale.
        """
        if not obj.last_sync_date:
            return "Never synced"
        
        if logikal_last_update and logikal_last_update > obj.last_sync_date:
            return f"Logikal updated {logikal_last_update.strftime('%Y-%m-%d %H:%M:%S')}"
        
        staleness_duration = datetime.utcnow() - obj.last_sync_date
        if staleness_duration.days > 0:
            return f"Last synced {staleness_duration.days} days ago"
        elif staleness_duration.seconds > 3600:
            hours = staleness_duration.seconds // 3600
            return f"Last synced {hours} hours ago"
        else:
            minutes = staleness_duration.seconds // 60
            return f"Last synced {minutes} minutes ago"

    async def cascade_sync_project(self, project_id: str, base_url: str, auth_token: str) -> Dict:
        """
        Perform cascading sync for a project: project → phases → elevations.
        """
        try:
            project = self.db.query(Project).filter(Project.logikal_id == project_id).first()
            if not project:
                return {"success": False, "error": "Project not found"}
            
            sync_results = {
                "project_id": project_id,
                "project_synced": False,
                "phases_synced": 0,
                "elevations_synced": 0,
                "errors": [],
                "started_at": datetime.utcnow(),
                "completed_at": None
            }
            
            # Step 1: Sync the project itself
            logger.info(f"Starting cascading sync for project {project_id}")
            
            project_logikal_update = await self.get_logikal_last_update_date(
                "project", project_id, base_url, auth_token
            )
            
            if self.is_object_stale(project, project_logikal_update):
                # Simulate project sync
                project.last_sync_date = datetime.utcnow()
                project.last_update_date = project_logikal_update
                self.db.commit()
                sync_results["project_synced"] = True
                logger.info(f"Project {project_id} synced successfully")
            
            # Step 2: Sync phases for this project
            phases = self.db.query(Phase).filter(Phase.project_id == project.id).all()
            
            for phase in phases:
                try:
                    phase_logikal_update = await self.get_logikal_last_update_date(
                        "phase", phase.logikal_id, base_url, auth_token
                    )
                    
                    if self.is_object_stale(phase, phase_logikal_update):
                        # Simulate phase sync
                        phase.last_sync_date = datetime.utcnow()
                        phase.last_update_date = phase_logikal_update
                        self.db.commit()
                        sync_results["phases_synced"] += 1
                        logger.info(f"Phase {phase.logikal_id} synced successfully")
                except Exception as e:
                    error_msg = f"Failed to sync phase {phase.logikal_id}: {str(e)}"
                    logger.error(error_msg)
                    sync_results["errors"].append(error_msg)
            
            # Step 3: Sync elevations for this project
            elevations = self.db.query(Elevation).filter(Elevation.project_id == project.id).all()
            
            for elevation in elevations:
                try:
                    elevation_logikal_update = await self.get_logikal_last_update_date(
                        "elevation", elevation.logikal_id, base_url, auth_token
                    )
                    
                    if self.is_object_stale(elevation, elevation_logikal_update):
                        # Simulate elevation sync
                        elevation.last_sync_date = datetime.utcnow()
                        elevation.last_update_date = elevation_logikal_update
                        self.db.commit()
                        sync_results["elevations_synced"] += 1
                        logger.info(f"Elevation {elevation.logikal_id} synced successfully")
                except Exception as e:
                    error_msg = f"Failed to sync elevation {elevation.logikal_id}: {str(e)}"
                    logger.error(error_msg)
                    sync_results["errors"].append(error_msg)
            
            sync_results["completed_at"] = datetime.utcnow()
            sync_results["success"] = len(sync_results["errors"]) == 0
            
            logger.info(f"Cascading sync completed for project {project_id}: "
                       f"{sync_results['phases_synced']} phases, "
                       f"{sync_results['elevations_synced']} elevations synced")
            
            return sync_results
            
        except Exception as e:
            logger.error(f"Error in cascading sync for project {project_id}: {str(e)}")
            return {
                "success": False,
                "error": str(e),
                "project_id": project_id,
                "started_at": datetime.utcnow(),
                "completed_at": datetime.utcnow()
            }

    async def selective_sync_objects(self, object_ids: List[str], object_type: str, 
                                   base_url: str, auth_token: str) -> Dict:
        """
        Perform selective sync for specific objects.
        """
        try:
            sync_results = {
                "object_type": object_type,
                "requested_count": len(object_ids),
                "synced_count": 0,
                "skipped_count": 0,
                "failed_count": 0,
                "results": [],
                "started_at": datetime.utcnow(),
                "completed_at": None
            }
            
            for object_id in object_ids:
                try:
                    # Get the object from database
                    if object_type == "project":
                        obj = self.db.query(Project).filter(Project.logikal_id == object_id).first()
                    elif object_type == "phase":
                        obj = self.db.query(Phase).filter(Phase.logikal_id == object_id).first()
                    elif object_type == "elevation":
                        obj = self.db.query(Elevation).filter(Elevation.logikal_id == object_id).first()
                    else:
                        sync_results["results"].append({
                            "object_id": object_id,
                            "status": "failed",
                            "error": "Invalid object type"
                        })
                        sync_results["failed_count"] += 1
                        continue
                    
                    if not obj:
                        sync_results["results"].append({
                            "object_id": object_id,
                            "status": "failed",
                            "error": "Object not found"
                        })
                        sync_results["failed_count"] += 1
                        continue
                    
                    # Check if object needs syncing
                    logikal_last_update = await self.get_logikal_last_update_date(
                        object_type, object_id, base_url, auth_token
                    )
                    
                    if not self.is_object_stale(obj, logikal_last_update):
                        sync_results["results"].append({
                            "object_id": object_id,
                            "status": "skipped",
                            "reason": "Object is up to date"
                        })
                        sync_results["skipped_count"] += 1
                        continue
                    
                    # Perform sync
                    obj.last_sync_date = datetime.utcnow()
                    obj.last_update_date = logikal_last_update
                    self.db.commit()
                    
                    sync_results["results"].append({
                        "object_id": object_id,
                        "status": "synced",
                        "synced_at": datetime.utcnow().isoformat()
                    })
                    sync_results["synced_count"] += 1
                    
                except Exception as e:
                    error_msg = f"Failed to sync {object_type} {object_id}: {str(e)}"
                    logger.error(error_msg)
                    sync_results["results"].append({
                        "object_id": object_id,
                        "status": "failed",
                        "error": error_msg
                    })
                    sync_results["failed_count"] += 1
            
            sync_results["completed_at"] = datetime.utcnow()
            sync_results["success"] = sync_results["failed_count"] == 0
            
            return sync_results
            
        except Exception as e:
            logger.error(f"Error in selective sync for {object_type}: {str(e)}")
            return {
                "success": False,
                "error": str(e),
                "object_type": object_type,
                "started_at": datetime.utcnow(),
                "completed_at": datetime.utcnow()
            }

    def get_sync_dependencies(self, object_type: str, object_id: str) -> List[str]:
        """
        Get the dependency chain for syncing an object.
        Returns the order in which objects should be synced.
        """
        if object_type == "project":
            # For a project, we need to sync: project → phases → elevations
            project = self.db.query(Project).filter(Project.logikal_id == object_id).first()
            if not project:
                return []
            
            dependencies = [f"project:{object_id}"]
            
            # Add phases
            phases = self.db.query(Phase).filter(Phase.project_id == project.id).all()
            for phase in phases:
                dependencies.append(f"phase:{phase.logikal_id}")
            
            # Add elevations
            elevations = self.db.query(Elevation).filter(Elevation.project_id == project.id).all()
            for elevation in elevations:
                dependencies.append(f"elevation:{elevation.logikal_id}")
            
            return dependencies
        
        elif object_type == "phase":
            # For a phase, we need to sync: phase → elevations
            phase = self.db.query(Phase).filter(Phase.logikal_id == object_id).first()
            if not phase:
                return []
            
            dependencies = [f"phase:{object_id}"]
            
            # Add elevations
            elevations = self.db.query(Elevation).filter(Elevation.phase_id == object_id).all()
            for elevation in elevations:
                dependencies.append(f"elevation:{elevation.logikal_id}")
            
            return dependencies
        
        elif object_type == "elevation":
            # Elevations have no dependencies
            return [f"elevation:{object_id}"]
        
        return []

    async def sync_with_dependencies(self, object_type: str, object_id: str, 
                                   base_url: str, auth_token: str) -> Dict:
        """
        Sync an object and all its dependencies in the correct order.
        """
        try:
            dependencies = self.get_sync_dependencies(object_type, object_id)
            
            sync_results = {
                "object_type": object_type,
                "object_id": object_id,
                "dependencies": dependencies,
                "synced_objects": [],
                "errors": [],
                "started_at": datetime.utcnow(),
                "completed_at": None
            }
            
            # Sync objects in dependency order
            for dep in dependencies:
                dep_type, dep_id = dep.split(":", 1)
                
                try:
                    # Get the object
                    if dep_type == "project":
                        obj = self.db.query(Project).filter(Project.logikal_id == dep_id).first()
                    elif dep_type == "phase":
                        obj = self.db.query(Phase).filter(Phase.logikal_id == dep_id).first()
                    elif dep_type == "elevation":
                        obj = self.db.query(Elevation).filter(Elevation.logikal_id == dep_id).first()
                    else:
                        continue
                    
                    if not obj:
                        sync_results["errors"].append(f"Object not found: {dep}")
                        continue
                    
                    # Check if sync is needed
                    logikal_last_update = await self.get_logikal_last_update_date(
                        dep_type, dep_id, base_url, auth_token
                    )
                    
                    if self.is_object_stale(obj, logikal_last_update):
                        # Perform sync
                        obj.last_sync_date = datetime.utcnow()
                        obj.last_update_date = logikal_last_update
                        self.db.commit()
                        
                        sync_results["synced_objects"].append({
                            "type": dep_type,
                            "id": dep_id,
                            "synced_at": datetime.utcnow().isoformat()
                        })
                    else:
                        sync_results["synced_objects"].append({
                            "type": dep_type,
                            "id": dep_id,
                            "status": "skipped",
                            "reason": "Up to date"
                        })
                
                except Exception as e:
                    error_msg = f"Failed to sync {dep}: {str(e)}"
                    logger.error(error_msg)
                    sync_results["errors"].append(error_msg)
            
            sync_results["completed_at"] = datetime.utcnow()
            sync_results["success"] = len(sync_results["errors"]) == 0
            
            return sync_results
            
        except Exception as e:
            logger.error(f"Error in dependency sync for {object_type} {object_id}: {str(e)}")
            return {
                "success": False,
                "error": str(e),
                "object_type": object_type,
                "object_id": object_id,
                "started_at": datetime.utcnow(),
                "completed_at": datetime.utcnow()
            }
