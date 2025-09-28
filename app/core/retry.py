import asyncio
import random
import logging
from typing import Callable, Any, Optional, Union
from functools import wraps
import time

logger = logging.getLogger(__name__)


class RetryConfig:
    """Configuration for retry behavior"""
    def __init__(
        self,
        max_retries: int = 3,
        base_delay: float = 1.0,
        max_delay: float = 60.0,
        exponential_base: float = 2.0,
        jitter: bool = True,
        retryable_status_codes: set = None
    ):
        self.max_retries = max_retries
        self.base_delay = base_delay
        self.max_delay = max_delay
        self.exponential_base = exponential_base
        self.jitter = jitter
        self.retryable_status_codes = retryable_status_codes or {503, 502, 504, 429}


class RateLimiter:
    """Simple rate limiter using asyncio"""
    
    def __init__(self, requests_per_second: float = 2.0):
        self.requests_per_second = requests_per_second
        self.min_interval = 1.0 / requests_per_second
        self.last_request_time = 0.0
        self._lock = asyncio.Lock()
    
    async def acquire(self):
        """Acquire permission to make a request"""
        async with self._lock:
            current_time = time.time()
            time_since_last = current_time - self.last_request_time
            
            if time_since_last < self.min_interval:
                sleep_time = self.min_interval - time_since_last
                logger.debug(f"Rate limiting: sleeping for {sleep_time:.2f} seconds")
                await asyncio.sleep(sleep_time)
            
            self.last_request_time = time.time()


def retry_async(
    config: Optional[RetryConfig] = None,
    rate_limiter: Optional[RateLimiter] = None
):
    """
    Decorator for async functions with retry logic and rate limiting
    
    Args:
        config: Retry configuration
        rate_limiter: Rate limiter instance
    """
    if config is None:
        config = RetryConfig()
    
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs) -> Any:
            last_exception = None
            
            for attempt in range(config.max_retries + 1):
                try:
                    # Apply rate limiting if configured
                    if rate_limiter:
                        await rate_limiter.acquire()
                    
                    # Execute the function
                    result = await func(*args, **kwargs)
                    
                    # If successful, return the result
                    if attempt > 0:
                        logger.info(f"Function {func.__name__} succeeded on attempt {attempt + 1}")
                    return result
                    
                except Exception as e:
                    last_exception = e
                    
                    # Check if this is a retryable error
                    if not _is_retryable_error(e, config.retryable_status_codes):
                        logger.error(f"Non-retryable error in {func.__name__}: {str(e)}")
                        raise e
                    
                    # If this was the last attempt, raise the exception
                    if attempt == config.max_retries:
                        logger.error(f"Function {func.__name__} failed after {config.max_retries + 1} attempts: {str(e)}")
                        raise e
                    
                    # Calculate delay for next attempt
                    delay = _calculate_delay(attempt, config)
                    logger.warning(f"Function {func.__name__} failed on attempt {attempt + 1}: {str(e)}. Retrying in {delay:.2f} seconds...")
                    
                    await asyncio.sleep(delay)
            
            # This should never be reached, but just in case
            raise last_exception
        
        return wrapper
    return decorator


def _is_retryable_error(error: Exception, retryable_status_codes: set) -> bool:
    """Check if an error is retryable based on status codes"""
    error_str = str(error)
    
    # Check for HTTP status codes in the error message
    for status_code in retryable_status_codes:
        if f"{status_code}" in error_str:
            return True
    
    # Check for specific error types
    if "ConnectionError" in str(type(error)):
        return True
    
    if "TimeoutError" in str(type(error)):
        return True
    
    return False


def _calculate_delay(attempt: int, config: RetryConfig) -> float:
    """Calculate delay for exponential backoff with jitter"""
    # Exponential backoff
    delay = config.base_delay * (config.exponential_base ** attempt)
    
    # Cap at maximum delay
    delay = min(delay, config.max_delay)
    
    # Add jitter to prevent thundering herd
    if config.jitter:
        jitter = random.uniform(0, delay * 0.1)  # 10% jitter
        delay += jitter
    
    return delay


# Global rate limiters for different API endpoints
auth_rate_limiter = RateLimiter(requests_per_second=1.0)  # Slower for auth
api_rate_limiter = RateLimiter(requests_per_second=2.0)   # Faster for regular API calls

# Default retry configurations
default_retry_config = RetryConfig(
    max_retries=3,
    base_delay=1.0,
    max_delay=30.0,
    exponential_base=2.0,
    jitter=True
)

auth_retry_config = RetryConfig(
    max_retries=2,
    base_delay=2.0,
    max_delay=60.0,
    exponential_base=2.0,
    jitter=True
)
