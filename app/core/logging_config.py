"""
Enhanced logging configuration to reduce log noise and improve readability.
"""
import logging
import logging.handlers
import os
from typing import Dict, Any
from datetime import datetime


class ConnectionFilter(logging.Filter):
    """Filter to reduce noise from connection-related logs"""
    
    def __init__(self):
        super().__init__()
        self.suppressed_patterns = [
            'connection reset by peer',
            'connection aborted',
            'connection refused',
            'name or service not known',
            'temporary failure in name resolution',
            'no route to host',
            'connection timed out',
            'broken pipe',
            'connection closed',
            'socket error',
            'network is unreachable'
        ]
    
    def filter(self, record):
        """Filter out common connection error messages"""
        message = record.getMessage().lower()
        
        # Suppress common connection errors that are not actionable
        for pattern in self.suppressed_patterns:
            if pattern in message:
                return False
        
        return True


class RetryFilter(logging.Filter):
    """Filter to reduce noise from retry attempts"""
    
    def __init__(self, max_retry_logs=3):
        super().__init__()
        self.max_retry_logs = max_retry_logs
        self.retry_counts = {}
    
    def filter(self, record):
        """Limit retry attempt logs"""
        if 'retry' in record.getMessage().lower():
            # Count retry attempts per logger
            logger_name = record.name
            count = self.retry_counts.get(logger_name, 0) + 1
            self.retry_counts[logger_name] = count
            
            # Only log first few retry attempts
            if count > self.max_retry_logs:
                return False
        
        return True


class CleanFormatter(logging.Formatter):
    """Clean formatter that reduces log noise"""
    
    def __init__(self, fmt=None, datefmt=None):
        super().__init__(fmt, datefmt)
        self.sensitive_patterns = [
            'password', 'token', 'secret', 'key', 'auth'
        ]
    
    def format(self, record):
        """Format log record with sensitive data filtering"""
        # Get the original message
        message = record.getMessage()
        
        # Filter out sensitive information
        for pattern in self.sensitive_patterns:
            if pattern.lower() in message.lower():
                message = message.replace(pattern, '[REDACTED]')
        
        # Create a copy of the record with the filtered message
        record_copy = logging.makeLogRecord(record.__dict__)
        record_copy.msg = message
        record_copy.args = ()
        
        return super().format(record_copy)


def setup_logging(
    log_level: str = "INFO",
    log_file: str = None,
    max_file_size: int = 10 * 1024 * 1024,  # 10MB
    backup_count: int = 5,
    enable_console: bool = True,
    enable_file: bool = True
) -> None:
    """
    Setup enhanced logging configuration with reduced noise.
    
    Args:
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_file: Path to log file (optional)
        max_file_size: Maximum size of log file before rotation
        backup_count: Number of backup files to keep
        enable_console: Whether to enable console logging
        enable_file: Whether to enable file logging
    """
    
    # Convert string level to logging constant
    level = getattr(logging, log_level.upper(), logging.INFO)
    
    # Create root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(level)
    
    # Clear existing handlers
    root_logger.handlers.clear()
    
    # Create formatters
    detailed_formatter = CleanFormatter(
        fmt='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    simple_formatter = CleanFormatter(
        fmt='%(levelname)s - %(message)s'
    )
    
    # Add filters
    connection_filter = ConnectionFilter()
    retry_filter = RetryFilter()
    
    # Console handler
    if enable_console:
        console_handler = logging.StreamHandler()
        console_handler.setLevel(level)
        console_handler.setFormatter(simple_formatter)
        console_handler.addFilter(connection_filter)
        console_handler.addFilter(retry_filter)
        root_logger.addHandler(console_handler)
    
    # File handler
    if enable_file and log_file:
        # Ensure log directory exists
        log_dir = os.path.dirname(log_file)
        if log_dir and not os.path.exists(log_dir):
            os.makedirs(log_dir, exist_ok=True)
        
        file_handler = logging.handlers.RotatingFileHandler(
            log_file,
            maxBytes=max_file_size,
            backupCount=backup_count
        )
        file_handler.setLevel(level)
        file_handler.setFormatter(detailed_formatter)
        file_handler.addFilter(connection_filter)
        root_logger.addHandler(file_handler)
    
    # Configure specific loggers
    configure_specific_loggers()


def configure_specific_loggers():
    """Configure specific loggers with appropriate levels"""
    
    # Reduce noise from common libraries
    noisy_loggers = [
        'urllib3.connectionpool',
        'requests.packages.urllib3.connectionpool',
        'aiohttp.access',
        'aiohttp.client',
        'asyncio',
        'sqlalchemy.engine',
        'sqlalchemy.pool',
        'celery.worker',
        'celery.worker.strategy',
        'celery.worker.consumer',
        'celery.worker.heartbeat',
        'celery.worker.control',
        'celery.worker.pidbox',
        'celery.worker.consumer.connection',
        'celery.worker.consumer.heart',
        'celery.worker.consumer.mingle',
        'celery.worker.consumer.gossip',
        'celery.worker.consumer.control',
        'celery.worker.consumer.events',
        'celery.worker.consumer.tasks',
        'celery.worker.consumer.agent',
        'celery.worker.consumer.connection',
        'celery.worker.consumer.heart',
        'celery.worker.consumer.mingle',
        'celery.worker.consumer.gossip',
        'celery.worker.consumer.control',
        'celery.worker.consumer.events',
        'celery.worker.consumer.tasks',
        'celery.worker.consumer.agent'
    ]
    
    for logger_name in noisy_loggers:
        logger = logging.getLogger(logger_name)
        logger.setLevel(logging.WARNING)
    
    # Set specific levels for our application loggers
    app_loggers = {
        'app.services': logging.INFO,
        'app.tasks': logging.INFO,
        'app.routers': logging.INFO,
        'app.core': logging.DEBUG,
        'app.models': logging.DEBUG,
        'app.api': logging.INFO
    }
    
    for logger_name, level in app_loggers.items():
        logger = logging.getLogger(logger_name)
        logger.setLevel(level)


def get_logger(name: str) -> logging.Logger:
    """Get a logger with the given name"""
    return logging.getLogger(name)


def log_connection_stats():
    """Log connection statistics for monitoring"""
    logger = get_logger(__name__)
    
    # This would be called periodically to log connection stats
    # Implementation depends on your connection tracking
    pass


class LoggingMiddleware:
    """Middleware to add request/response logging with reduced noise"""
    
    def __init__(self, app, logger_name: str = "app.requests"):
        self.app = app
        self.logger = get_logger(logger_name)
    
    async def __call__(self, scope, receive, send):
        """Process request with logging"""
        if scope["type"] == "http":
            start_time = datetime.now()
            
            # Log request (without sensitive data)
            self.logger.info(f"Request: {scope['method']} {scope['path']}")
            
            # Process request
            await self.app(scope, receive, send)
            
            # Log response time
            duration = (datetime.now() - start_time).total_seconds()
            self.logger.debug(f"Response time: {duration:.3f}s")
        
        else:
            await self.app(scope, receive, send)


# Initialize logging when module is imported
def init_logging():
    """Initialize logging configuration"""
    log_level = os.getenv('LOG_LEVEL', 'INFO')
    log_file = os.getenv('LOG_FILE', 'app/logs/app.log')
    
    setup_logging(
        log_level=log_level,
        log_file=log_file,
        enable_console=True,
        enable_file=True
    )


# Auto-initialize if not in test environment
if not os.getenv('TESTING'):
    init_logging()



