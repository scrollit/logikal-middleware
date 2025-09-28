from prometheus_client import Counter, Histogram, Gauge, Info, generate_latest, CONTENT_TYPE_LATEST
from fastapi import Request, Response
from fastapi.responses import PlainTextResponse
import time
import logging

logger = logging.getLogger(__name__)

# Sync Operation Metrics
sync_operations_total = Counter(
    'sync_operations_total',
    'Total number of sync operations',
    ['operation_type', 'status', 'object_type']
)

sync_duration_seconds = Histogram(
    'sync_duration_seconds',
    'Time spent on sync operations',
    ['operation_type', 'object_type'],
    buckets=[0.1, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0, 60.0, 120.0, 300.0]
)

sync_objects_processed = Counter(
    'sync_objects_processed_total',
    'Total number of objects processed during sync',
    ['operation_type', 'object_type', 'status']
)

# Data Quality Metrics
stale_objects_count = Gauge(
    'stale_objects_count',
    'Number of stale objects by type',
    ['object_type']
)

data_consistency_score = Gauge(
    'data_consistency_score',
    'Data consistency score (0-100)',
    ['scope']
)

sync_coverage_percentage = Gauge(
    'sync_coverage_percentage',
    'Sync coverage percentage by object type',
    ['object_type']
)

# System Health Metrics
active_alerts_count = Gauge(
    'active_alerts_count',
    'Number of active alerts',
    ['severity']
)

api_requests_total = Counter(
    'api_requests_total',
    'Total number of API requests',
    ['method', 'endpoint', 'status_code']
)

api_request_duration_seconds = Histogram(
    'api_request_duration_seconds',
    'Time spent processing API requests',
    ['method', 'endpoint'],
    buckets=[0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0]
)

# Database Metrics
database_connections_active = Gauge(
    'database_connections_active',
    'Number of active database connections'
)

database_query_duration_seconds = Histogram(
    'database_query_duration_seconds',
    'Time spent on database queries',
    ['query_type'],
    buckets=[0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5]
)

# Celery Metrics
celery_tasks_total = Counter(
    'celery_tasks_total',
    'Total number of Celery tasks',
    ['task_name', 'status']
)

celery_task_duration_seconds = Histogram(
    'celery_task_duration_seconds',
    'Time spent executing Celery tasks',
    ['task_name'],
    buckets=[0.1, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0, 60.0, 120.0, 300.0]
)

celery_queue_size = Gauge(
    'celery_queue_size',
    'Number of tasks in Celery queue',
    ['queue_name']
)

# Application Info
app_info = Info(
    'app_info',
    'Application information'
)

app_info.info({
    'version': '1.0.0',
    'name': 'logikal-middleware',
    'environment': 'production'
})


class PrometheusMetrics:
    """
    Prometheus metrics collection and management
    """

    @staticmethod
    def record_sync_operation(operation_type: str, object_type: str, status: str, 
                            duration: float, objects_processed: int):
        """Record sync operation metrics"""
        try:
            sync_operations_total.labels(
                operation_type=operation_type,
                status=status,
                object_type=object_type
            ).inc()

            sync_duration_seconds.labels(
                operation_type=operation_type,
                object_type=object_type
            ).observe(duration)

            sync_objects_processed.labels(
                operation_type=operation_type,
                object_type=object_type,
                status=status
            ).inc(objects_processed)

        except Exception as e:
            logger.error(f"Error recording sync operation metrics: {e}")

    @staticmethod
    def update_stale_objects_count(object_type: str, count: int):
        """Update stale objects count"""
        try:
            stale_objects_count.labels(object_type=object_type).set(count)
        except Exception as e:
            logger.error(f"Error updating stale objects count: {e}")

    @staticmethod
    def update_data_consistency_score(scope: str, score: float):
        """Update data consistency score"""
        try:
            data_consistency_score.labels(scope=scope).set(score)
        except Exception as e:
            logger.error(f"Error updating data consistency score: {e}")

    @staticmethod
    def update_sync_coverage(object_type: str, coverage_percentage: float):
        """Update sync coverage percentage"""
        try:
            sync_coverage_percentage.labels(object_type=object_type).set(coverage_percentage)
        except Exception as e:
            logger.error(f"Error updating sync coverage: {e}")

    @staticmethod
    def update_active_alerts_count(severity: str, count: int):
        """Update active alerts count"""
        try:
            active_alerts_count.labels(severity=severity).set(count)
        except Exception as e:
            logger.error(f"Error updating active alerts count: {e}")

    @staticmethod
    def record_api_request(method: str, endpoint: str, status_code: int, duration: float):
        """Record API request metrics"""
        try:
            api_requests_total.labels(
                method=method,
                endpoint=endpoint,
                status_code=str(status_code)
            ).inc()

            api_request_duration_seconds.labels(
                method=method,
                endpoint=endpoint
            ).observe(duration)

        except Exception as e:
            logger.error(f"Error recording API request metrics: {e}")

    @staticmethod
    def update_database_connections(count: int):
        """Update active database connections count"""
        try:
            database_connections_active.set(count)
        except Exception as e:
            logger.error(f"Error updating database connections count: {e}")

    @staticmethod
    def record_database_query(query_type: str, duration: float):
        """Record database query duration"""
        try:
            database_query_duration_seconds.labels(query_type=query_type).observe(duration)
        except Exception as e:
            logger.error(f"Error recording database query metrics: {e}")

    @staticmethod
    def record_celery_task(task_name: str, status: str, duration: float):
        """Record Celery task metrics"""
        try:
            celery_tasks_total.labels(task_name=task_name, status=status).inc()
            
            if duration is not None:
                celery_task_duration_seconds.labels(task_name=task_name).observe(duration)

        except Exception as e:
            logger.error(f"Error recording Celery task metrics: {e}")

    @staticmethod
    def update_celery_queue_size(queue_name: str, size: int):
        """Update Celery queue size"""
        try:
            celery_queue_size.labels(queue_name=queue_name).set(size)
        except Exception as e:
            logger.error(f"Error updating Celery queue size: {e}")


class PrometheusMiddleware:
    """
    FastAPI middleware for collecting Prometheus metrics
    """

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] == "http":
            request = Request(scope, receive)
            start_time = time.time()

            # Process request
            response_sent = False
            status_code = 500

            async def send_wrapper(message):
                nonlocal response_sent, status_code
                if message["type"] == "http.response.start":
                    status_code = message["status"]
                    response_sent = True
                await send(message)

            try:
                await self.app(scope, receive, send_wrapper)
            except Exception as e:
                logger.error(f"Error processing request: {e}")
                if not response_sent:
                    await send({
                        "type": "http.response.start",
                        "status": 500,
                        "headers": [[b"content-type", b"text/plain"]],
                    })
                    await send({
                        "type": "http.response.body",
                        "body": b"Internal Server Error",
                    })

            # Record metrics
            duration = time.time() - start_time
            endpoint = self._get_endpoint_pattern(request.url.path)
            
            PrometheusMetrics.record_api_request(
                method=request.method,
                endpoint=endpoint,
                status_code=status_code,
                duration=duration
            )

        else:
            await self.app(scope, receive, send)

    def _get_endpoint_pattern(self, path: str) -> str:
        """Convert specific paths to endpoint patterns for metrics"""
        # Replace UUIDs and IDs with placeholders
        import re
        
        # Replace UUIDs
        path = re.sub(r'/[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}', '/{id}', path)
        
        # Replace numeric IDs
        path = re.sub(r'/\d+', '/{id}', path)
        
        # Replace specific object IDs with patterns
        path = re.sub(r'/[a-zA-Z0-9_-]{20,}', '/{object_id}', path)
        
        return path


async def metrics_endpoint():
    """
    Prometheus metrics endpoint
    """
    try:
        metrics_data = generate_latest()
        return PlainTextResponse(
            content=metrics_data,
            media_type=CONTENT_TYPE_LATEST
        )
    except Exception as e:
        logger.error(f"Error generating metrics: {e}")
        return PlainTextResponse(
            content="# Error generating metrics\n",
            media_type=CONTENT_TYPE_LATEST,
            status_code=500
        )


def setup_prometheus_metrics(app):
    """
    Setup Prometheus metrics for the FastAPI application
    """
    # Add middleware
    app.add_middleware(PrometheusMiddleware)
    
    # Add metrics endpoint
    app.get("/metrics")(metrics_endpoint)
    
    logger.info("Prometheus metrics setup completed")
