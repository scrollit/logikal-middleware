"""
Connection health monitor to track and manage connection issues.
"""
import asyncio
import time
import logging
from typing import Dict, List, Optional, Callable
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime, timedelta
import aiohttp
import requests
from collections import defaultdict, deque

logger = logging.getLogger(__name__)


class ConnectionStatus(Enum):
    """Connection status enumeration"""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"


@dataclass
class ConnectionMetrics:
    """Connection metrics for monitoring"""
    total_requests: int = 0
    successful_requests: int = 0
    failed_requests: int = 0
    timeout_requests: int = 0
    connection_errors: int = 0
    average_response_time: float = 0.0
    last_success: Optional[datetime] = None
    last_failure: Optional[datetime] = None
    consecutive_failures: int = 0
    response_times: deque = field(default_factory=lambda: deque(maxlen=100))
    
    @property
    def success_rate(self) -> float:
        """Calculate success rate"""
        if self.total_requests == 0:
            return 0.0
        return (self.successful_requests / self.total_requests) * 100
    
    @property
    def failure_rate(self) -> float:
        """Calculate failure rate"""
        if self.total_requests == 0:
            return 0.0
        return (self.failed_requests / self.total_requests) * 100
    
    def add_response_time(self, response_time: float):
        """Add response time to metrics"""
        self.response_times.append(response_time)
        if self.response_times:
            self.average_response_time = sum(self.response_times) / len(self.response_times)
    
    def record_success(self, response_time: float):
        """Record successful request"""
        self.total_requests += 1
        self.successful_requests += 1
        self.consecutive_failures = 0
        self.last_success = datetime.now()
        self.add_response_time(response_time)
    
    def record_failure(self, error_type: str = "unknown"):
        """Record failed request"""
        self.total_requests += 1
        self.failed_requests += 1
        self.consecutive_failures += 1
        self.last_failure = datetime.now()
        
        if error_type == "timeout":
            self.timeout_requests += 1
        elif error_type == "connection":
            self.connection_errors += 1


@dataclass
class HealthCheckConfig:
    """Configuration for health checks"""
    endpoint: str
    method: str = "GET"
    timeout: float = 5.0
    expected_status: int = 200
    check_interval: float = 30.0
    failure_threshold: int = 3
    recovery_threshold: int = 2


class ConnectionMonitor:
    """
    Monitor connection health and provide insights
    """
    
    def __init__(self):
        self.metrics: Dict[str, ConnectionMetrics] = defaultdict(ConnectionMetrics)
        self.health_checks: Dict[str, HealthCheckConfig] = {}
        self.status_callbacks: List[Callable] = []
        self.monitoring_task: Optional[asyncio.Task] = None
        self.is_monitoring = False
    
    def add_health_check(self, name: str, config: HealthCheckConfig):
        """Add a health check configuration"""
        self.health_checks[name] = config
        logger.info(f"Added health check: {name} -> {config.endpoint}")
    
    def add_status_callback(self, callback: Callable):
        """Add callback for status changes"""
        self.status_callbacks.append(callback)
    
    def record_request(self, 
                      endpoint: str, 
                      success: bool, 
                      response_time: float = 0.0,
                      error_type: str = "unknown"):
        """Record a request for monitoring"""
        metrics = self.metrics[endpoint]
        
        if success:
            metrics.record_success(response_time)
        else:
            metrics.record_failure(error_type)
        
        # Check if status changed
        old_status = self.get_connection_status(endpoint)
        # Status will be recalculated on next call
    
    def get_connection_status(self, endpoint: str) -> ConnectionStatus:
        """Get connection status for an endpoint"""
        metrics = self.metrics[endpoint]
        
        if metrics.total_requests == 0:
            return ConnectionStatus.UNKNOWN
        
        # Check consecutive failures
        if metrics.consecutive_failures >= 5:
            return ConnectionStatus.UNHEALTHY
        
        # Check success rate
        if metrics.success_rate < 50:
            return ConnectionStatus.UNHEALTHY
        elif metrics.success_rate < 80:
            return ConnectionStatus.DEGRADED
        
        # Check response times
        if metrics.average_response_time > 10.0:  # 10 seconds
            return ConnectionStatus.DEGRADED
        
        # Check if recently failed
        if metrics.last_failure and metrics.last_success:
            if metrics.last_failure > metrics.last_success:
                time_since_failure = datetime.now() - metrics.last_failure
                if time_since_failure < timedelta(minutes=5):
                    return ConnectionStatus.DEGRADED
        
        return ConnectionStatus.HEALTHY
    
    def get_health_summary(self) -> Dict[str, Dict]:
        """Get health summary for all endpoints"""
        summary = {}
        
        for endpoint, metrics in self.metrics.items():
            status = self.get_connection_status(endpoint)
            summary[endpoint] = {
                'status': status.value,
                'success_rate': metrics.success_rate,
                'failure_rate': metrics.failure_rate,
                'average_response_time': metrics.average_response_time,
                'total_requests': metrics.total_requests,
                'consecutive_failures': metrics.consecutive_failures,
                'last_success': metrics.last_success.isoformat() if metrics.last_success else None,
                'last_failure': metrics.last_failure.isoformat() if metrics.last_failure else None
            }
        
        return summary
    
    async def perform_health_check(self, name: str, config: HealthCheckConfig) -> bool:
        """Perform a health check"""
        try:
            start_time = time.time()
            
            async with aiohttp.ClientSession() as session:
                async with session.request(
                    config.method,
                    config.endpoint,
                    timeout=aiohttp.ClientTimeout(total=config.timeout)
                ) as response:
                    response_time = time.time() - start_time
                    
                    if response.status == config.expected_status:
                        self.record_request(config.endpoint, True, response_time)
                        return True
                    else:
                        self.record_request(config.endpoint, False, 0, "http_error")
                        return False
        
        except asyncio.TimeoutError:
            self.record_request(config.endpoint, False, 0, "timeout")
            return False
        except Exception as e:
            self.record_request(config.endpoint, False, 0, "connection")
            logger.debug(f"Health check failed for {name}: {type(e).__name__}")
            return False
    
    async def run_health_checks(self):
        """Run all configured health checks"""
        if not self.health_checks:
            return
        
        tasks = []
        for name, config in self.health_checks.items():
            task = asyncio.create_task(self.perform_health_check(name, config))
            tasks.append(task)
        
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
    
    async def monitoring_loop(self):
        """Main monitoring loop"""
        logger.info("Starting connection monitoring")
        
        while self.is_monitoring:
            try:
                await self.run_health_checks()
                
                # Check for status changes and notify callbacks
                for endpoint in self.metrics.keys():
                    status = self.get_connection_status(endpoint)
                    # You could add logic here to detect status changes
                
                # Sleep until next check
                await asyncio.sleep(30)  # Check every 30 seconds
                
            except Exception as e:
                logger.error(f"Error in monitoring loop: {e}")
                await asyncio.sleep(60)  # Wait longer on error
    
    async def start_monitoring(self):
        """Start the monitoring loop"""
        if self.is_monitoring:
            return
        
        self.is_monitoring = True
        self.monitoring_task = asyncio.create_task(self.monitoring_loop())
        logger.info("Connection monitoring started")
    
    async def stop_monitoring(self):
        """Stop the monitoring loop"""
        if not self.is_monitoring:
            return
        
        self.is_monitoring = False
        if self.monitoring_task:
            self.monitoring_task.cancel()
            try:
                await self.monitoring_task
            except asyncio.CancelledError:
                pass
        
        logger.info("Connection monitoring stopped")
    
    def get_recommendations(self) -> List[str]:
        """Get recommendations based on current metrics"""
        recommendations = []
        
        for endpoint, metrics in self.metrics.items():
            status = self.get_connection_status(endpoint)
            
            if status == ConnectionStatus.UNHEALTHY:
                recommendations.append(f"Endpoint {endpoint} is unhealthy - check server status")
            
            if metrics.consecutive_failures >= 3:
                recommendations.append(f"Endpoint {endpoint} has {metrics.consecutive_failures} consecutive failures")
            
            if metrics.average_response_time > 5.0:
                recommendations.append(f"Endpoint {endpoint} has slow response times ({metrics.average_response_time:.2f}s)")
            
            if metrics.failure_rate > 20:
                recommendations.append(f"Endpoint {endpoint} has high failure rate ({metrics.failure_rate:.1f}%)")
        
        return recommendations
    
    def cleanup_old_metrics(self, max_age_hours: int = 24):
        """Clean up old metrics to prevent memory leaks"""
        cutoff_time = datetime.now() - timedelta(hours=max_age_hours)
        
        for endpoint, metrics in self.metrics.items():
            # Remove old response times
            while (metrics.response_times and 
                   len(metrics.response_times) > 50):  # Keep last 50
                metrics.response_times.popleft()
            
            # Reset metrics if no recent activity
            if (metrics.last_success and metrics.last_success < cutoff_time and
                metrics.last_failure and metrics.last_failure < cutoff_time):
                # Reset old metrics
                self.metrics[endpoint] = ConnectionMetrics()


# Global monitor instance
_global_monitor: Optional[ConnectionMonitor] = None

def get_global_monitor() -> ConnectionMonitor:
    """Get the global connection monitor instance"""
    global _global_monitor
    if _global_monitor is None:
        _global_monitor = ConnectionMonitor()
    return _global_monitor


def monitor_request(endpoint: str, success: bool, response_time: float = 0.0, error_type: str = "unknown"):
    """Convenience function to record a request"""
    monitor = get_global_monitor()
    monitor.record_request(endpoint, success, response_time, error_type)


async def start_connection_monitoring():
    """Start global connection monitoring"""
    monitor = get_global_monitor()
    await monitor.start_monitoring()


async def stop_connection_monitoring():
    """Stop global connection monitoring"""
    monitor = get_global_monitor()
    await monitor.stop_monitoring()

