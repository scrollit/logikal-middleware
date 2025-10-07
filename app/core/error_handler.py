"""
Enhanced error handling with reduced log noise and better connection error management.
"""
import logging
import time
import traceback
from typing import Optional, Dict, Any, Callable, Union
from enum import Enum
from dataclasses import dataclass
from functools import wraps
import asyncio
import aiohttp
import requests
from requests.exceptions import (
    ConnectionError, TimeoutError, RequestException, 
    HTTPError, RetryError, ChunkedEncodingError
)

logger = logging.getLogger(__name__)


class ErrorSeverity(Enum):
    """Error severity levels"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class ErrorCategory(Enum):
    """Error categories for better handling"""
    CONNECTION = "connection"
    TIMEOUT = "timeout"
    AUTHENTICATION = "authentication"
    VALIDATION = "validation"
    BUSINESS_LOGIC = "business_logic"
    SYSTEM = "system"
    UNKNOWN = "unknown"


@dataclass
class ErrorContext:
    """Context information for errors"""
    operation: str
    endpoint: Optional[str] = None
    method: Optional[str] = None
    status_code: Optional[int] = None
    duration: Optional[float] = None
    retry_count: int = 0
    user_id: Optional[str] = None
    request_id: Optional[str] = None


class ErrorHandler:
    """
    Enhanced error handler with reduced log noise and better categorization
    """
    
    def __init__(self, 
                 log_level_threshold: int = logging.WARNING,
                 suppress_common_errors: bool = True,
                 max_error_frequency: int = 10):
        self.log_level_threshold = log_level_threshold
        self.suppress_common_errors = suppress_common_errors
        self.max_error_frequency = max_error_frequency
        self._error_counts: Dict[str, int] = {}
        self._last_error_time: Dict[str, float] = {}
        self._suppressed_errors: Dict[str, int] = {}
    
    def should_log_error(self, error_key: str) -> bool:
        """Determine if an error should be logged based on frequency"""
        if not self.suppress_common_errors:
            return True
            
        current_time = time.time()
        error_count = self._error_counts.get(error_key, 0)
        last_time = self._last_error_time.get(error_key, 0)
        
        # Reset counter if enough time has passed
        if current_time - last_time > 300:  # 5 minutes
            self._error_counts[error_key] = 0
            error_count = 0
        
        # Increment counter
        self._error_counts[error_key] = error_count + 1
        self._last_error_time[error_key] = current_time
        
        # Log first few occurrences, then suppress
        if error_count < 3:
            return True
        elif error_count == 3:
            self._suppressed_errors[error_key] = self._suppressed_errors.get(error_key, 0) + 1
            logger.warning(f"Suppressing frequent error: {error_key} (occurred {error_count + 1} times)")
            return False
        else:
            self._suppressed_errors[error_key] = self._suppressed_errors.get(error_key, 0) + 1
            return False
    
    def categorize_error(self, error: Exception) -> ErrorCategory:
        """Categorize error for better handling"""
        error_type = type(error).__name__
        error_str = str(error).lower()
        
        if isinstance(error, (ConnectionError, aiohttp.ClientConnectorError)):
            return ErrorCategory.CONNECTION
        elif isinstance(error, (TimeoutError, aiohttp.ServerTimeoutError)):
            return ErrorCategory.TIMEOUT
        elif isinstance(error, (aiohttp.ClientResponseError)) and error.status == 401:
            return ErrorCategory.AUTHENTICATION
        elif "validation" in error_str or "invalid" in error_str:
            return ErrorCategory.VALIDATION
        elif "business" in error_str or "workflow" in error_str:
            return ErrorCategory.BUSINESS_LOGIC
        else:
            return ErrorCategory.UNKNOWN
    
    def get_error_severity(self, error: Exception, context: ErrorContext) -> ErrorSeverity:
        """Determine error severity"""
        category = self.categorize_error(error)
        
        if category == ErrorCategory.CONNECTION:
            return ErrorSeverity.MEDIUM
        elif category == ErrorCategory.TIMEOUT:
            return ErrorSeverity.MEDIUM
        elif category == ErrorCategory.AUTHENTICATION:
            return ErrorSeverity.HIGH
        elif category == ErrorCategory.SYSTEM:
            return ErrorSeverity.CRITICAL
        else:
            return ErrorSeverity.LOW
    
    def format_error_message(self, error: Exception, context: ErrorContext) -> str:
        """Format error message with context"""
        category = self.categorize_error(error)
        
        base_msg = f"{context.operation} failed"
        
        if context.endpoint:
            base_msg += f" on {context.method} {context.endpoint}"
        
        if context.status_code:
            base_msg += f" (HTTP {context.status_code})"
        
        if context.duration:
            base_msg += f" after {context.duration:.2f}s"
        
        if context.retry_count > 0:
            base_msg += f" (retry {context.retry_count})"
        
        # Add category-specific information
        if category == ErrorCategory.CONNECTION:
            base_msg += " - Connection issue"
        elif category == ErrorCategory.TIMEOUT:
            base_msg += " - Timeout"
        elif category == ErrorCategory.AUTHENTICATION:
            base_msg += " - Authentication failed"
        
        return base_msg
    
    def handle_error(self, 
                    error: Exception, 
                    context: ErrorContext,
                    log_traceback: bool = False) -> Dict[str, Any]:
        """Handle error with appropriate logging and response"""
        
        category = self.categorize_error(error)
        severity = self.get_error_severity(error, context)
        
        # Create error key for frequency tracking
        error_key = f"{category.value}:{type(error).__name__}:{context.operation}"
        
        # Format error message
        error_message = self.format_error_message(error, context)
        
        # Determine if we should log this error
        should_log = self.should_log_error(error_key)
        
        # Log based on severity and frequency
        if should_log:
            if severity == ErrorSeverity.CRITICAL:
                logger.critical(error_message, exc_info=log_traceback)
            elif severity == ErrorSeverity.HIGH:
                logger.error(error_message, exc_info=log_traceback)
            elif severity == ErrorSeverity.MEDIUM:
                logger.warning(error_message)
            else:
                logger.info(error_message)
        
        # Return structured error information
        return {
            'error': str(error),
            'category': category.value,
            'severity': severity.value,
            'context': {
                'operation': context.operation,
                'endpoint': context.endpoint,
                'method': context.method,
                'status_code': context.status_code,
                'duration': context.duration,
                'retry_count': context.retry_count
            },
            'suppressed': not should_log,
            'suppressed_count': self._suppressed_errors.get(error_key, 0)
        }
    
    def get_error_stats(self) -> Dict[str, Any]:
        """Get error statistics"""
        return {
            'error_counts': dict(self._error_counts),
            'suppressed_errors': dict(self._suppressed_errors),
            'last_error_times': {k: time.time() - v for k, v in self._last_error_time.items()}
        }


# Global error handler instance
_global_error_handler: Optional[ErrorHandler] = None

def get_global_error_handler() -> ErrorHandler:
    """Get the global error handler instance"""
    global _global_error_handler
    if _global_error_handler is None:
        _global_error_handler = ErrorHandler()
    return _global_error_handler


def handle_connection_errors(func: Callable) -> Callable:
    """Decorator for handling connection errors with reduced log noise"""
    @wraps(func)
    async def async_wrapper(*args, **kwargs):
        error_handler = get_global_error_handler()
        context = ErrorContext(operation=func.__name__)
        
        try:
            return await func(*args, **kwargs)
        except Exception as e:
            error_info = error_handler.handle_error(e, context)
            
            # Re-raise with additional context if needed
            if error_info['severity'] == 'critical':
                raise
            else:
                # For non-critical errors, we might want to return a default value
                # or handle them differently based on the function
                raise
    
    @wraps(func)
    def sync_wrapper(*args, **kwargs):
        error_handler = get_global_error_handler()
        context = ErrorContext(operation=func.__name__)
        
        try:
            return func(*args, **kwargs)
        except Exception as e:
            error_info = error_handler.handle_error(e, context)
            raise
    
    # Return appropriate wrapper based on function type
    if asyncio.iscoroutinefunction(func):
        return async_wrapper
    else:
        return sync_wrapper


class ConnectionErrorHandler:
    """Specialized handler for connection-related errors"""
    
    def __init__(self, error_handler: Optional[ErrorHandler] = None):
        self.error_handler = error_handler or get_global_error_handler()
    
    def handle_connection_error(self, 
                              error: Exception, 
                              operation: str,
                              endpoint: Optional[str] = None,
                              method: Optional[str] = None,
                              duration: Optional[float] = None) -> Dict[str, Any]:
        """Handle connection-specific errors"""
        context = ErrorContext(
            operation=operation,
            endpoint=endpoint,
            method=method,
            duration=duration
        )
        
        return self.error_handler.handle_error(error, context)
    
    def is_retryable_error(self, error: Exception) -> bool:
        """Check if error is retryable"""
        category = self.error_handler.categorize_error(error)
        return category in (ErrorCategory.CONNECTION, ErrorCategory.TIMEOUT)
    
    def get_retry_delay(self, retry_count: int, base_delay: float = 1.0) -> float:
        """Calculate retry delay with exponential backoff"""
        return min(base_delay * (2 ** retry_count), 60.0)  # Max 60 seconds

