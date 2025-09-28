import logging
import logging.config
import json
import sys
import uuid
from datetime import datetime
from typing import Dict, Any, Optional
from contextvars import ContextVar
from fastapi import Request
import structlog

# Context variables for request tracking
request_id_var: ContextVar[Optional[str]] = ContextVar('request_id', default=None)
client_id_var: ContextVar[Optional[str]] = ContextVar('client_id', default=None)

def add_request_context_processor(logger, method_name, event_dict):
    """Add request context to log entries"""
    if request_id_var.get():
        event_dict['request_id'] = request_id_var.get()
    if client_id_var.get():
        event_dict['client_id'] = client_id_var.get()
    return event_dict

# Configure structlog
structlog.configure(
    processors=[
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
        add_request_context_processor,
        structlog.processors.JSONRenderer()
    ],
    context_class=dict,
    logger_factory=structlog.stdlib.LoggerFactory(),
    wrapper_class=structlog.stdlib.BoundLogger,
    cache_logger_on_first_use=True,
)


class CustomFormatter(logging.Formatter):
    """Custom formatter for structured logging"""
    
    def format(self, record):
        log_entry = {
            'timestamp': datetime.utcnow().isoformat(),
            'level': record.levelname,
            'logger': record.name,
            'message': record.getMessage(),
            'module': record.module,
            'function': record.funcName,
            'line': record.lineno,
        }
        
        # Add request context if available
        if hasattr(record, 'request_id'):
            log_entry['request_id'] = record.request_id
        if hasattr(record, 'client_id'):
            log_entry['client_id'] = record.client_id
            
        # Add exception info if present
        if record.exc_info:
            log_entry['exception'] = self.formatException(record.exc_info)
            
        # Add extra fields
        for key, value in record.__dict__.items():
            if key not in ['name', 'msg', 'args', 'levelname', 'levelno', 'pathname', 
                          'filename', 'module', 'exc_info', 'exc_text', 'stack_info',
                          'lineno', 'funcName', 'created', 'msecs', 'relativeCreated',
                          'thread', 'threadName', 'processName', 'process', 'getMessage']:
                log_entry[key] = value
                
        return json.dumps(log_entry)


class RequestContextFilter(logging.Filter):
    """Filter to add request context to log records"""
    
    def filter(self, record):
        record.request_id = request_id_var.get() or 'no-request'
        record.client_id = client_id_var.get() or 'no-client'
        return True


def setup_logging(environment: str = "development", log_level: str = "INFO"):
    """
    Setup structured logging configuration
    """
    
    # Logging configuration
    config = {
        'version': 1,
        'disable_existing_loggers': False,
        'formatters': {
            'json': {
                '()': CustomFormatter,
            },
            'simple': {
                'format': '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            }
        },
        'filters': {
            'request_context': {
                '()': RequestContextFilter,
            }
        },
        'handlers': {
            'console': {
                'class': 'logging.StreamHandler',
                'level': log_level,
                'formatter': 'json' if environment == 'production' else 'simple',
                'filters': ['request_context'],
                'stream': sys.stdout,
            },
            'file': {
                'class': 'logging.handlers.RotatingFileHandler',
                'level': log_level,
                'formatter': 'json',
                'filters': ['request_context'],
                'filename': '/app/logs/middleware.log',
                'maxBytes': 10485760,  # 10MB
                'backupCount': 5,
            },
            'error_file': {
                'class': 'logging.handlers.RotatingFileHandler',
                'level': 'ERROR',
                'formatter': 'json',
                'filters': ['request_context'],
                'filename': '/app/logs/error.log',
                'maxBytes': 10485760,  # 10MB
                'backupCount': 5,
            }
        },
        'loggers': {
            '': {  # Root logger
                'handlers': ['console', 'file', 'error_file'],
                'level': log_level,
                'propagate': False,
            },
            'uvicorn': {
                'handlers': ['console', 'file'],
                'level': 'INFO',
                'propagate': False,
            },
            'uvicorn.access': {
                'handlers': ['console', 'file'],
                'level': 'INFO',
                'propagate': False,
            },
            'sqlalchemy.engine': {
                'handlers': ['console'],
                'level': 'WARNING',
                'propagate': False,
            },
            'celery': {
                'handlers': ['console', 'file'],
                'level': 'INFO',
                'propagate': False,
            },
            'app': {
                'handlers': ['console', 'file', 'error_file'],
                'level': log_level,
                'propagate': False,
            }
        }
    }
    
    logging.config.dictConfig(config)
    
    # Setup structlog
    logger = structlog.get_logger()
    logger.info("Logging setup completed", environment=environment, log_level=log_level)


def get_logger(name: str = None) -> structlog.BoundLogger:
    """Get a structured logger instance"""
    return structlog.get_logger(name)


def set_request_context(request_id: str = None, client_id: str = None):
    """Set request context for logging"""
    if request_id:
        request_id_var.set(request_id)
    if client_id:
        client_id_var.set(client_id)


def clear_request_context():
    """Clear request context"""
    request_id_var.set(None)
    client_id_var.set(None)


def generate_request_id() -> str:
    """Generate a unique request ID"""
    return str(uuid.uuid4())


class LoggingMiddleware:
    """
    FastAPI middleware for request logging
    """
    
    def __init__(self, app):
        self.app = app
        self.logger = get_logger("middleware")
    
    async def __call__(self, scope, receive, send):
        if scope["type"] == "http":
            request = Request(scope, receive)
            request_id = generate_request_id()
            
            # Set request context
            set_request_context(request_id=request_id)
            
            # Extract client info
            client_id = None
            if hasattr(request, 'state') and hasattr(request.state, 'client_id'):
                client_id = request.state.client_id
                set_request_context(client_id=client_id)
            
            # Log request start
            self.logger.info(
                "Request started",
                method=request.method,
                url=str(request.url),
                client_ip=request.client.host if request.client else None,
                user_agent=request.headers.get("user-agent"),
                request_id=request_id,
                client_id=client_id
            )
            
            start_time = datetime.utcnow()
            
            try:
                await self.app(scope, receive, send)
            except Exception as e:
                self.logger.error(
                    "Request failed",
                    method=request.method,
                    url=str(request.url),
                    error=str(e),
                    request_id=request_id,
                    client_id=client_id
                )
                raise
            finally:
                # Log request completion
                duration = (datetime.utcnow() - start_time).total_seconds()
                self.logger.info(
                    "Request completed",
                    method=request.method,
                    url=str(request.url),
                    duration_seconds=duration,
                    request_id=request_id,
                    client_id=client_id
                )
                
                # Clear request context
                clear_request_context()
        else:
            await self.app(scope, receive, send)


# Business logic logging helpers
def log_sync_operation(operation_type: str, object_type: str, status: str, 
                      duration: float, objects_processed: int, **kwargs):
    """Log sync operation details"""
    logger = get_logger("sync")
    logger.info(
        "Sync operation completed",
        operation_type=operation_type,
        object_type=object_type,
        status=status,
        duration_seconds=duration,
        objects_processed=objects_processed,
        **kwargs
    )


def log_data_consistency_check(project_id: str, is_valid: bool, errors: list = None, **kwargs):
    """Log data consistency check results"""
    logger = get_logger("consistency")
    logger.info(
        "Data consistency check completed",
        project_id=project_id,
        is_valid=is_valid,
        errors=errors or [],
        **kwargs
    )


def log_alert_generated(alert_type: str, severity: str, message: str, **kwargs):
    """Log alert generation"""
    logger = get_logger("alerts")
    logger.warning(
        "Alert generated",
        alert_type=alert_type,
        severity=severity,
        message=message,
        **kwargs
    )


def log_api_error(endpoint: str, error: Exception, client_id: str = None, **kwargs):
    """Log API errors"""
    logger = get_logger("api")
    logger.error(
        "API error occurred",
        endpoint=endpoint,
        error_type=type(error).__name__,
        error_message=str(error),
        client_id=client_id,
        **kwargs
    )


def log_performance_metrics(metric_name: str, value: float, unit: str = None, **kwargs):
    """Log performance metrics"""
    logger = get_logger("performance")
    logger.info(
        "Performance metric",
        metric_name=metric_name,
        value=value,
        unit=unit,
        **kwargs
    )
