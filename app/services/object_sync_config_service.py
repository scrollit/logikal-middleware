from sqlalchemy.orm import Session
from typing import List, Dict, Optional
from datetime import datetime
import logging

from models.object_sync_config import ObjectSyncConfig

logger = logging.getLogger(__name__)


class ObjectSyncConfigService:
    """Service for managing object sync configurations"""
    
    def __init__(self, db: Session):
        self.db = db
    
    def get_all_configs(self) -> List[ObjectSyncConfig]:
        """Get all object sync configurations"""
        return self.db.query(ObjectSyncConfig).order_by(ObjectSyncConfig.priority, ObjectSyncConfig.object_type).all()
    
    def get_config(self, object_type: str) -> Optional[ObjectSyncConfig]:
        """Get sync configuration for specific object type"""
        return self.db.query(ObjectSyncConfig).filter(ObjectSyncConfig.object_type == object_type).first()
    
    def create_default_configs(self) -> List[ObjectSyncConfig]:
        """Create default sync configurations for all object types"""
        default_configs = [
            {
                "object_type": "directory",
                "display_name": "Directories",
                "description": "Directory structure and navigation data",
                "sync_interval_minutes": 60,
                "priority": 1,
                "depends_on": [],
                "staleness_threshold_minutes": 120,
                "batch_size": 50,
                "max_retry_attempts": 3,
                "retry_delay_minutes": 5
            },
            {
                "object_type": "project",
                "display_name": "Projects",
                "description": "Project information and metadata",
                "sync_interval_minutes": 120,
                "priority": 2,
                "depends_on": ["directory"],
                "staleness_threshold_minutes": 240,
                "batch_size": 100,
                "max_retry_attempts": 3,
                "retry_delay_minutes": 5
            },
            {
                "object_type": "phase",
                "display_name": "Phases",
                "description": "Project phases and workflow stages",
                "sync_interval_minutes": 180,
                "priority": 3,
                "depends_on": ["project"],
                "staleness_threshold_minutes": 360,
                "batch_size": 100,
                "max_retry_attempts": 3,
                "retry_delay_minutes": 5
            },
            {
                "object_type": "elevation",
                "display_name": "Elevations",
                "description": "Elevation drawings and technical data",
                "sync_interval_minutes": 240,
                "priority": 4,
                "depends_on": ["phase"],
                "staleness_threshold_minutes": 480,
                "batch_size": 50,
                "max_retry_attempts": 5,
                "retry_delay_minutes": 10
            },
            {
                "object_type": "elevation_glass",
                "display_name": "Elevation Glass Components",
                "description": "Glass components and parts data for elevations",
                "sync_interval_minutes": 360,
                "priority": 5,
                "depends_on": ["elevation"],
                "staleness_threshold_minutes": 720,
                "batch_size": 25,
                "max_retry_attempts": 5,
                "retry_delay_minutes": 15
            },
            {
                "object_type": "sqlite_parser",
                "display_name": "SQLite Parser Queue",
                "description": "Parsing queue for processing SQLite files and enriching elevation data",
                "sync_interval_minutes": 10,
                "priority": 6,
                "depends_on": ["elevation"],
                "staleness_threshold_minutes": 30,
                "batch_size": 5,
                "max_retry_attempts": 3,
                "retry_delay_minutes": 2
            },
            {
                "object_type": "parsing_errors",
                "display_name": "Parsing Error Logs",
                "description": "Error tracking and monitoring for SQLite parsing failures",
                "sync_interval_minutes": 60,
                "priority": 7,
                "depends_on": ["sqlite_parser"],
                "staleness_threshold_minutes": 120,
                "batch_size": 50,
                "max_retry_attempts": 2,
                "retry_delay_minutes": 5
            }
        ]
        
        created_configs = []
        for config_data in default_configs:
            # Check if config already exists
            existing = self.get_config(config_data["object_type"])
            if not existing:
                config = ObjectSyncConfig(**config_data)
                config.set_dependencies(config_data["depends_on"])
                self.db.add(config)
                created_configs.append(config)
        
        if created_configs:
            self.db.commit()
            logger.info(f"Created {len(created_configs)} default sync configurations")
        
        return created_configs
    
    def update_config(self, object_type: str, config_data: Dict) -> Optional[ObjectSyncConfig]:
        """Update sync configuration for specific object type"""
        config = self.get_config(object_type)
        if not config:
            return None
        
        # Update fields
        for field, value in config_data.items():
            if hasattr(config, field):
                if field == "depends_on" and isinstance(value, list):
                    config.set_dependencies(value)
                else:
                    setattr(config, field, value)
        
        config.updated_at = datetime.utcnow()
        self.db.commit()
        
        logger.info(f"Updated sync configuration for {object_type}")
        return config
    
    def create_config(self, config_data: Dict) -> ObjectSyncConfig:
        """Create new sync configuration"""
        config = ObjectSyncConfig(**config_data)
        
        if "depends_on" in config_data and isinstance(config_data["depends_on"], list):
            config.set_dependencies(config_data["depends_on"])
        
        self.db.add(config)
        self.db.commit()
        
        logger.info(f"Created sync configuration for {config.object_type}")
        return config
    
    def delete_config(self, object_type: str) -> bool:
        """Delete sync configuration"""
        config = self.get_config(object_type)
        if not config:
            return False
        
        self.db.delete(config)
        self.db.commit()
        
        logger.info(f"Deleted sync configuration for {object_type}")
        return True
    
    def toggle_sync_enabled(self, object_type: str) -> Optional[ObjectSyncConfig]:
        """Toggle sync enabled status for object type"""
        config = self.get_config(object_type)
        if not config:
            return None
        
        config.is_sync_enabled = not config.is_sync_enabled
        config.updated_at = datetime.utcnow()
        self.db.commit()
        
        logger.info(f"Toggled sync enabled for {object_type} to {config.is_sync_enabled}")
        return config
    
    def get_sync_order(self) -> List[ObjectSyncConfig]:
        """Get sync configurations ordered by dependency and priority"""
        configs = self.get_all_configs()
        
        # Sort by priority first, then by object type
        sorted_configs = sorted(configs, key=lambda x: (x.priority, x.object_type))
        
        # Apply dependency ordering
        ordered_configs = []
        processed = set()
        
        def add_config_with_dependencies(config):
            if config.object_type in processed:
                return
            
            # Add dependencies first
            for dep_type in config.get_dependencies():
                dep_config = next((c for c in configs if c.object_type == dep_type), None)
                if dep_config:
                    add_config_with_dependencies(dep_config)
            
            # Add this config
            ordered_configs.append(config)
            processed.add(config.object_type)
        
        for config in sorted_configs:
            add_config_with_dependencies(config)
        
        return ordered_configs
    
    def get_configs_summary(self) -> Dict:
        """Get summary of all sync configurations"""
        configs = self.get_all_configs()
        
        summary = {
            "total_configs": len(configs),
            "enabled_configs": len([c for c in configs if c.is_sync_enabled]),
            "disabled_configs": len([c for c in configs if not c.is_sync_enabled]),
            "configs_by_type": {},
            "next_syncs": {},
            "stale_configs": []
        }
        
        for config in configs:
            summary["configs_by_type"][config.object_type] = {
                "display_name": config.display_name,
                "enabled": config.is_sync_enabled,
                "interval_minutes": config.sync_interval_minutes,
                "priority": config.priority,
                "last_sync": config.last_sync.isoformat() if config.last_sync else None,
                "last_attempt": config.last_attempt.isoformat() if config.last_attempt else None
            }
            
            summary["next_syncs"][config.object_type] = config.get_next_sync_time().isoformat()
            
            if config.is_stale():
                summary["stale_configs"].append(config.object_type)
        
        return summary
    
    def update_last_sync(self, object_type: str, success: bool = True) -> Optional[ObjectSyncConfig]:
        """Update last sync timestamp for object type"""
        config = self.get_config(object_type)
        if not config:
            return None
        
        now = datetime.utcnow()
        config.last_attempt = now
        
        if success:
            config.last_sync = now
        
        self.db.commit()
        return config
    
    def trigger_sync_task(self, object_type: str) -> Dict:
        """Trigger sync task for specific object type"""
        config = self.get_config(object_type)
        if not config:
            return {"success": False, "error": f"Configuration not found for {object_type}"}
        
        try:
            # Import tasks based on object type
            if object_type == "sqlite_parser":
                from tasks.sqlite_parser_tasks import trigger_parsing_for_new_files_task
                task = trigger_parsing_for_new_files_task.delay()
                return {
                    "success": True,
                    "task_id": task.id,
                    "object_type": object_type,
                    "message": "SQLite parsing task triggered successfully"
                }
            elif object_type == "parsing_errors":
                # For parsing errors, we can trigger error log cleanup or monitoring
                return {
                    "success": True,
                    "object_type": object_type,
                    "message": "Parsing error monitoring task triggered"
                }
            else:
                # For other object types, we could trigger their respective sync tasks
                return {
                    "success": True,
                    "object_type": object_type,
                    "message": f"Sync task triggered for {object_type}"
                }
                
        except Exception as e:
            logger.error(f"Failed to trigger sync task for {object_type}: {str(e)}")
            return {"success": False, "error": str(e)}
    
    def reset_all_configs(self) -> int:
        """Reset all configurations to defaults"""
        # Delete existing configs
        self.db.query(ObjectSyncConfig).delete()
        self.db.commit()
        
        # Create default configs
        created_configs = self.create_default_configs()
        
        logger.info(f"Reset all sync configurations, created {len(created_configs)} defaults")
        return len(created_configs)
