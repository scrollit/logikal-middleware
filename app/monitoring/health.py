from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import text
from typing import Dict, Any, List
from datetime import datetime, timedelta
import asyncio
import aiohttp
import redis
from core.database import get_db
from core.config_production import get_settings
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/health", tags=["Health Checks"])


class HealthChecker:
    """
    Comprehensive health check system
    """
    
    def __init__(self, db: Session):
        self.db = db
        self.settings = get_settings()
    
    async def check_database_health(self) -> Dict[str, Any]:
        """Check database connectivity and performance"""
        try:
            start_time = datetime.utcnow()
            
            # Test basic connectivity
            result = self.db.execute(text("SELECT 1")).scalar()
            if result != 1:
                raise Exception("Database query returned unexpected result")
            
            # Test query performance
            query_start = datetime.utcnow()
            self.db.execute(text("SELECT COUNT(*) FROM projects"))
            query_duration = (datetime.utcnow() - query_start).total_seconds()
            
            # Check connection pool status
            pool = self.db.bind.pool
            pool_status = {
                "size": pool.size(),
                "checked_in": pool.checkedin(),
                "checked_out": pool.checkedout(),
                "overflow": pool.overflow(),
                "invalid": getattr(pool, 'invalid', lambda: 0)()  # Handle missing attribute gracefully
            }
            
            total_duration = (datetime.utcnow() - start_time).total_seconds()
            
            return {
                "status": "healthy",
                "response_time_ms": round(total_duration * 1000, 2),
                "query_performance_ms": round(query_duration * 1000, 2),
                "connection_pool": pool_status,
                "checked_at": datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Database health check failed: {str(e)}")
            return {
                "status": "unhealthy",
                "error": str(e),
                "checked_at": datetime.utcnow().isoformat()
            }
    
    async def check_redis_health(self) -> Dict[str, Any]:
        """Check Redis connectivity and performance"""
        try:
            start_time = datetime.utcnow()
            
            # Connect to Redis
            redis_client = redis.Redis(
                host=getattr(self.settings, 'REDIS_HOST', 'redis'),  # Default to 'redis' for Docker
                port=getattr(self.settings, 'REDIS_PORT', 6379),
                db=getattr(self.settings, 'REDIS_DB', 0),
                password=getattr(self.settings, 'REDIS_PASSWORD', None),
                socket_timeout=5,
                socket_connect_timeout=5
            )
            
            # Test basic operations
            test_key = f"health_check_{datetime.utcnow().timestamp()}"
            redis_client.set(test_key, "test_value", ex=60)
            value = redis_client.get(test_key)
            redis_client.delete(test_key)
            
            if value != b"test_value":
                raise Exception("Redis read/write test failed")
            
            # Get Redis info
            info = redis_client.info()
            
            total_duration = (datetime.utcnow() - start_time).total_seconds()
            
            return {
                "status": "healthy",
                "response_time_ms": round(total_duration * 1000, 2),
                "redis_version": info.get("redis_version"),
                "used_memory_human": info.get("used_memory_human"),
                "connected_clients": info.get("connected_clients"),
                "uptime_in_seconds": info.get("uptime_in_seconds"),
                "checked_at": datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Redis health check failed: {str(e)}")
            return {
                "status": "unhealthy",
                "error": str(e),
                "checked_at": datetime.utcnow().isoformat()
            }
    
    async def check_celery_health(self) -> Dict[str, Any]:
        """Check Celery worker and queue health"""
        try:
            from celery_app import celery_app
            
            start_time = datetime.utcnow()
            
            # Check Celery worker status
            inspect = celery_app.control.inspect()
            active_workers = inspect.active()
            registered_tasks = inspect.registered()
            
            if not active_workers:
                raise Exception("No active Celery workers found")
            
            # Check queue sizes
            queue_info = {}
            for worker_name, tasks in active_workers.items():
                queue_info[worker_name] = {
                    "active_tasks": len(tasks),
                    "registered_tasks": len(registered_tasks.get(worker_name, []))
                }
            
            total_duration = (datetime.utcnow() - start_time).total_seconds()
            
            return {
                "status": "healthy",
                "response_time_ms": round(total_duration * 1000, 2),
                "active_workers": len(active_workers),
                "workers": queue_info,
                "checked_at": datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Celery health check failed: {str(e)}")
            return {
                "status": "unhealthy",
                "error": str(e),
                "checked_at": datetime.utcnow().isoformat()
            }
    
    async def check_external_api_health(self) -> Dict[str, Any]:
        """Check external API connectivity"""
        try:
            start_time = datetime.utcnow()
            
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=10)) as session:
                # Test external API connectivity (replace with actual endpoint)
                test_url = f"{self.settings.LOGIKAL_API_BASE_URL}/health"
                
                async with session.get(test_url) as response:
                    if response.status >= 400:
                        raise Exception(f"External API returned status {response.status}")
                    
                    response_data = await response.json()
                    
                    total_duration = (datetime.utcnow() - start_time).total_seconds()
                    
                    return {
                        "status": "healthy",
                        "response_time_ms": round(total_duration * 1000, 2),
                        "external_api_status": response.status,
                        "external_api_response": response_data,
                        "checked_at": datetime.utcnow().isoformat()
                    }
                    
        except Exception as e:
            logger.error(f"External API health check failed: {str(e)}")
            return {
                "status": "unhealthy",
                "error": str(e),
                "checked_at": datetime.utcnow().isoformat()
            }
    
    async def check_system_resources(self) -> Dict[str, Any]:
        """Check system resource usage"""
        try:
            import psutil
            
            # CPU usage
            cpu_percent = psutil.cpu_percent(interval=1)
            
            # Memory usage
            memory = psutil.virtual_memory()
            memory_percent = memory.percent
            
            # Disk usage
            disk = psutil.disk_usage('/')
            disk_percent = disk.percent
            
            # Load average
            load_avg = psutil.getloadavg()
            
            return {
                "status": "healthy" if cpu_percent < 80 and memory_percent < 80 and disk_percent < 90 else "warning",
                "cpu_usage_percent": cpu_percent,
                "memory_usage_percent": memory_percent,
                "memory_available_gb": round(memory.available / (1024**3), 2),
                "disk_usage_percent": disk_percent,
                "disk_free_gb": round(disk.free / (1024**3), 2),
                "load_average": {
                    "1min": load_avg[0],
                    "5min": load_avg[1],
                    "15min": load_avg[2]
                },
                "checked_at": datetime.utcnow().isoformat()
            }
            
        except ImportError:
            return {
                "status": "unavailable",
                "error": "psutil not available",
                "checked_at": datetime.utcnow().isoformat()
            }
        except Exception as e:
            logger.error(f"System resources health check failed: {str(e)}")
            return {
                "status": "unhealthy",
                "error": str(e),
                "checked_at": datetime.utcnow().isoformat()
            }
    
    async def check_application_health(self) -> Dict[str, Any]:
        """Check application-specific health metrics"""
        try:
            # Check sync status
            try:
                from services.sync_metrics_service import SyncMetricsService
                metrics_service = SyncMetricsService(self.db)
            except ImportError:
                # Service not available, skip metrics
                metrics_service = None
            
            # Get recent sync metrics
            if metrics_service:
                sync_metrics = metrics_service.get_sync_performance_metrics(1)  # Last hour
            else:
                sync_metrics = {"sync_counts": {"total": 0}, "performance_metrics": {"data_freshness_score": 0}}
            
            # Check for stale data
            try:
                from services.advanced_sync_service import AdvancedSyncService
                advanced_sync_service = AdvancedSyncService(self.db)
            except ImportError:
                advanced_sync_service = None
            
            # Count stale objects (simplified check)
            from models.project import Project
            from datetime import datetime, timedelta
            
            stale_threshold = datetime.utcnow() - timedelta(hours=24)
            stale_projects = self.db.query(Project).filter(
                Project.last_sync_date < stale_threshold
            ).count()
            
            total_projects = self.db.query(Project).count()
            
            # Check alerts
            try:
                from services.alert_service import AlertService
                alert_service = AlertService(self.db)
                alerts = alert_service.check_sync_health_alerts()
                critical_alerts = len([a for a in alerts if a.get('severity') == 'critical'])
            except ImportError:
                alerts = []
                critical_alerts = 0
            
            return {
                "status": "healthy" if critical_alerts == 0 and stale_projects < total_projects * 0.5 else "warning",
                "sync_metrics": {
                    "total_objects_synced": sync_metrics.get("sync_counts", {}).get("total", 0),
                    "data_freshness_score": sync_metrics.get("performance_metrics", {}).get("data_freshness_score", 0)
                },
                "data_health": {
                    "total_projects": total_projects,
                    "stale_projects": stale_projects,
                    "stale_percentage": round((stale_projects / total_projects * 100) if total_projects > 0 else 0, 2)
                },
                "alerts": {
                    "total_alerts": len(alerts),
                    "critical_alerts": critical_alerts
                },
                "checked_at": datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Application health check failed: {str(e)}")
            return {
                "status": "unhealthy",
                "error": str(e),
                "checked_at": datetime.utcnow().isoformat()
            }


@router.get("/")
async def basic_health_check():
    """
    Basic health check endpoint
    """
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "version": get_settings().APP_VERSION,
        "environment": get_settings().ENVIRONMENT
    }


@router.get("/detailed")
async def detailed_health_check(db: Session = Depends(get_db)):
    """
    Detailed health check with all components
    """
    health_checker = HealthChecker(db)
    
    # Run all health checks concurrently
    checks = await asyncio.gather(
        health_checker.check_database_health(),
        health_checker.check_redis_health(),
        health_checker.check_celery_health(),
        health_checker.check_system_resources(),
        health_checker.check_application_health(),
        return_exceptions=True
    )
    
    database_health, redis_health, celery_health, system_health, app_health = checks
    
    # Determine overall status
    overall_status = "healthy"
    unhealthy_components = []
    
    for check_name, check_result in [
        ("database", database_health),
        ("redis", redis_health),
        ("celery", celery_health),
        ("system", system_health),
        ("application", app_health)
    ]:
        if isinstance(check_result, Exception):
            overall_status = "unhealthy"
            unhealthy_components.append(check_name)
        elif isinstance(check_result, dict) and check_result.get("status") in ["unhealthy", "warning"]:
            if check_result.get("status") == "unhealthy":
                overall_status = "unhealthy"
                unhealthy_components.append(check_name)
            elif overall_status == "healthy":
                overall_status = "warning"
    
    response = {
        "status": overall_status,
        "timestamp": datetime.utcnow().isoformat(),
        "version": get_settings().APP_VERSION,
        "environment": get_settings().ENVIRONMENT,
        "components": {
            "database": database_health,
            "redis": redis_health,
            "celery": celery_health,
            "system": system_health,
            "application": app_health
        }
    }
    
    if unhealthy_components:
        response["unhealthy_components"] = unhealthy_components
    
    # Return appropriate HTTP status code
    if overall_status == "unhealthy":
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=response)
    elif overall_status == "warning":
        raise HTTPException(status_code=status.HTTP_200_OK, detail=response)
    
    return response


@router.get("/ready")
async def readiness_check(db: Session = Depends(get_db)):
    """
    Kubernetes readiness probe endpoint
    """
    health_checker = HealthChecker(db)
    
    # Check critical components only
    database_health = await health_checker.check_database_health()
    redis_health = await health_checker.check_redis_health()
    
    if (database_health.get("status") == "unhealthy" or 
        redis_health.get("status") == "unhealthy"):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"status": "not_ready", "components": {"database": database_health, "redis": redis_health}}
        )
    
    return {"status": "ready"}


@router.get("/live")
async def liveness_check():
    """
    Kubernetes liveness probe endpoint
    """
    return {"status": "alive", "timestamp": datetime.utcnow().isoformat()}
