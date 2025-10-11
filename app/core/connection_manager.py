"""
Enhanced Connection Manager for clean connection handling and reduced log noise.
"""
import asyncio
import logging
import time
from contextlib import asynccontextmanager
from typing import Optional, Dict, Any, Callable
from dataclasses import dataclass
from enum import Enum
import aiohttp
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

logger = logging.getLogger(__name__)


class ConnectionState(Enum):
    """Connection state enumeration"""
    IDLE = "idle"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    DISCONNECTING = "disconnecting"
    ERROR = "error"
    CLOSED = "closed"


@dataclass
class ConnectionConfig:
    """Configuration for connection management"""
    timeout: float = 30.0
    max_retries: int = 3
    retry_backoff_factor: float = 0.3
    retry_status_forcelist: tuple = (500, 502, 504)
    pool_connections: int = 10
    pool_maxsize: int = 10
    pool_block: bool = False
    enable_keepalive: bool = True
    keepalive_timeout: float = 5.0
    max_keepalive_connections: int = 5


class ConnectionManager:
    """
    Enhanced connection manager with proper cleanup and reduced log noise.
    """
    
    def __init__(self, config: Optional[ConnectionConfig] = None):
        self.config = config or ConnectionConfig()
        self.state = ConnectionState.IDLE
        self.session: Optional[aiohttp.ClientSession] = None
        self.requests_session: Optional[requests.Session] = None
        self._connection_count = 0
        self._last_activity = time.time()
        
    async def __aenter__(self):
        """Async context manager entry"""
        await self.connect()
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit with proper cleanup"""
        await self.disconnect()
        
    def __enter__(self):
        """Sync context manager entry"""
        self.connect_sync()
        return self
        
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Sync context manager exit with proper cleanup"""
        self.disconnect_sync()
    
    async def connect(self) -> None:
        """Establish async connection with proper error handling"""
        if self.state == ConnectionState.CONNECTED:
            return
            
        self.state = ConnectionState.CONNECTING
        
        try:
            # Configure timeout and connector
            timeout = aiohttp.ClientTimeout(
                total=self.config.timeout,
                connect=self.config.timeout / 2,
                sock_read=self.config.timeout / 2
            )
            
            connector = aiohttp.TCPConnector(
                limit=self.config.pool_connections,
                limit_per_host=self.config.pool_maxsize,
                enable_cleanup_closed=True,
                keepalive_timeout=self.config.keepalive_timeout,
                ttl_dns_cache=300,
                use_dns_cache=True
            )
            
            self.session = aiohttp.ClientSession(
                timeout=timeout,
                connector=connector,
                headers={'Connection': 'keep-alive' if self.config.enable_keepalive else 'close'}
            )
            
            self.state = ConnectionState.CONNECTED
            self._last_activity = time.time()
            
        except Exception as e:
            self.state = ConnectionState.ERROR
            # Use debug level to reduce log noise for common connection issues
            logger.debug(f"Connection establishment failed: {str(e)}")
            raise
    
    def connect_sync(self) -> None:
        """Establish sync connection with proper error handling"""
        if self.state == ConnectionState.CONNECTED:
            return
            
        self.state = ConnectionState.CONNECTING
        
        try:
            # Create session with retry strategy
            self.requests_session = requests.Session()
            
            # Configure retry strategy
            retry_strategy = Retry(
                total=self.config.max_retries,
                backoff_factor=self.config.retry_backoff_factor,
                status_forcelist=self.config.retry_status_forcelist,
                allowed_methods=["HEAD", "GET", "PUT", "DELETE", "OPTIONS", "TRACE", "POST"]
            )
            
            # Mount adapter with retry strategy
            adapter = HTTPAdapter(
                max_retries=retry_strategy,
                pool_connections=self.config.pool_connections,
                pool_maxsize=self.config.pool_maxsize,
                pool_block=self.config.pool_block
            )
            
            self.requests_session.mount("http://", adapter)
            self.requests_session.mount("https://", adapter)
            
            # Set default timeout
            self.requests_session.timeout = self.config.timeout
            
            self.state = ConnectionState.CONNECTED
            self._last_activity = time.time()
            
        except Exception as e:
            self.state = ConnectionState.ERROR
            logger.debug(f"Sync connection establishment failed: {str(e)}")
            raise
    
    async def disconnect(self) -> None:
        """Clean disconnect with proper resource cleanup"""
        if self.state in (ConnectionState.CLOSED, ConnectionState.IDLE):
            return
            
        self.state = ConnectionState.DISCONNECTING
        
        try:
            if self.session and not self.session.closed:
                await self.session.close()
                # Wait a bit for proper cleanup
                await asyncio.sleep(0.1)
                
        except Exception as e:
            logger.debug(f"Error during async disconnect: {str(e)}")
        finally:
            self.session = None
            self.state = ConnectionState.CLOSED
    
    def disconnect_sync(self) -> None:
        """Clean sync disconnect with proper resource cleanup"""
        if self.state in (ConnectionState.CLOSED, ConnectionState.IDLE):
            return
            
        self.state = ConnectionState.DISCONNECTING
        
        try:
            if self.requests_session:
                self.requests_session.close()
                
        except Exception as e:
            logger.debug(f"Error during sync disconnect: {str(e)}")
        finally:
            self.requests_session = None
            self.state = ConnectionState.CLOSED
    
    @asynccontextmanager
    async def get_connection(self):
        """Context manager for getting a connection with automatic cleanup"""
        if not self.session or self.session.closed:
            await self.connect()
            
        try:
            self._connection_count += 1
            self._last_activity = time.time()
            yield self.session
        finally:
            self._connection_count -= 1
    
    def get_sync_connection(self):
        """Get sync connection with automatic setup"""
        if not self.requests_session:
            self.connect_sync()
            
        self._connection_count += 1
        self._last_activity = time.time()
        return self.requests_session
    
    def release_sync_connection(self):
        """Release sync connection"""
        self._connection_count -= 1
    
    async def health_check(self) -> bool:
        """Perform a health check on the connection"""
        if not self.session or self.session.closed:
            return False
            
        try:
            # Simple health check - you can customize this
            async with self.session.get('https://httpbin.org/status/200', timeout=5) as response:
                return response.status == 200
        except Exception:
            return False
    
    def get_stats(self) -> Dict[str, Any]:
        """Get connection statistics"""
        return {
            'state': self.state.value,
            'connection_count': self._connection_count,
            'last_activity': self._last_activity,
            'time_since_activity': time.time() - self._last_activity,
            'config': {
                'timeout': self.config.timeout,
                'max_retries': self.config.max_retries,
                'pool_connections': self.config.pool_connections,
                'pool_maxsize': self.config.pool_maxsize
            }
        }


class ConnectionPool:
    """
    Connection pool manager for multiple connections
    """
    
    def __init__(self, max_connections: int = 10, config: Optional[ConnectionConfig] = None):
        self.max_connections = max_connections
        self.config = config or ConnectionConfig()
        self._pool: Dict[str, ConnectionManager] = {}
        self._lock = asyncio.Lock()
    
    async def get_connection(self, key: str) -> ConnectionManager:
        """Get or create a connection for the given key"""
        async with self._lock:
            if key not in self._pool:
                if len(self._pool) >= self.max_connections:
                    # Remove oldest connection
                    oldest_key = min(self._pool.keys(), 
                                   key=lambda k: self._pool[k]._last_activity)
                    await self._pool[oldest_key].disconnect()
                    del self._pool[oldest_key]
                
                self._pool[key] = ConnectionManager(self.config)
                await self._pool[key].connect()
            
            return self._pool[key]
    
    async def cleanup_idle_connections(self, max_idle_time: float = 300.0):
        """Clean up idle connections"""
        current_time = time.time()
        to_remove = []
        
        async with self._lock:
            for key, conn in self._pool.items():
                if (current_time - conn._last_activity) > max_idle_time:
                    to_remove.append(key)
            
            for key in to_remove:
                await self._pool[key].disconnect()
                del self._pool[key]
    
    async def close_all(self):
        """Close all connections in the pool"""
        async with self._lock:
            for conn in self._pool.values():
                await conn.disconnect()
            self._pool.clear()


# Global connection pool instance
_global_pool: Optional[ConnectionPool] = None

def get_global_connection_pool() -> ConnectionPool:
    """Get the global connection pool instance"""
    global _global_pool
    if _global_pool is None:
        _global_pool = ConnectionPool()
    return _global_pool



