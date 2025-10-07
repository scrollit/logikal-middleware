import os
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, validator
try:
    from pydantic_settings import BaseSettings
except ImportError:
    from pydantic import BaseSettings
from functools import lru_cache
import logging

logger = logging.getLogger(__name__)


class ProductionSettings(BaseSettings):
    """
    Production configuration settings
    """
    
    # Application Settings
    APP_NAME: str = "Logikal Middleware"
    APP_VERSION: str = "1.0.0"
    ENVIRONMENT: str = "production"
    DEBUG: bool = False
    
    # API Settings
    API_V1_STR: str = "/api/v1"
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    
    # Database Settings
    DATABASE_URL: str
    DATABASE_POOL_SIZE: int = 20
    DATABASE_MAX_OVERFLOW: int = 30
    DATABASE_POOL_TIMEOUT: int = 30
    DATABASE_POOL_RECYCLE: int = 3600
    
    # Redis Settings
    REDIS_HOST: str = "redis"  # Use Docker service name
    REDIS_PORT: int = 6379
    REDIS_DB: int = 0
    REDIS_PASSWORD: Optional[str] = None
    
    # Security Settings
    SECRET_KEY: str
    JWT_SECRET_KEY: str
    ACCESS_TOKEN_EXPIRE_HOURS: int = 24
    ALGORITHM: str = "HS256"
    
    # Rate Limiting
    RATE_LIMIT_PER_MINUTE: int = 60
    RATE_LIMIT_PER_HOUR: int = 1000
    
    # CORS Settings
    CORS_ORIGINS: Optional[List[str]] = None
    CORS_ALLOW_CREDENTIALS: bool = True
    CORS_ALLOW_METHODS: List[str] = ["GET", "POST", "PUT", "DELETE"]
    CORS_ALLOW_HEADERS: List[str] = ["*"]
    
    # Trusted Hosts
    TRUSTED_HOSTS: Optional[List[str]] = None
    
    # Logging Settings
    LOG_LEVEL: str = "INFO"
    LOG_FORMAT: str = "json"  # json or text
    LOG_FILE_PATH: str = "/app/logs/middleware.log"
    LOG_MAX_SIZE: int = 10485760  # 10MB
    LOG_BACKUP_COUNT: int = 5
    
    # Monitoring Settings
    PROMETHEUS_ENABLED: bool = True
    METRICS_ENDPOINT: str = "/metrics"
    
    # Celery Settings
    CELERY_BROKER_URL: str
    CELERY_RESULT_BACKEND: str
    CELERY_TASK_SERIALIZER: str = "json"
    CELERY_ACCEPT_CONTENT: List[str] = ["json"]
    CELERY_RESULT_SERIALIZER: str = "json"
    CELERY_TIMEZONE: str = "UTC"
    CELERY_ENABLE_UTC: bool = True
    
    # Sync Settings
    SYNC_INTERVAL_SECONDS: int = 3600  # 1 hour
    SYNC_BATCH_SIZE: int = 100
    SYNC_MAX_RETRIES: int = 3
    SYNC_RETRY_DELAY: int = 60
    
    # External API Settings
    LOGIKAL_API_BASE_URL: str
    LOGIKAL_AUTH_USERNAME: Optional[str] = None
    LOGIKAL_AUTH_PASSWORD: Optional[str] = None
    LOGIKAL_API_TIMEOUT: int = 30
    LOGIKAL_API_MAX_RETRIES: int = 3
    
    # Performance Settings
    MAX_REQUEST_SIZE: int = 10485760  # 10MB
    REQUEST_TIMEOUT: int = 30
    
    # Health Check Settings
    HEALTH_CHECK_INTERVAL: int = 30
    HEALTH_CHECK_TIMEOUT: int = 5
    
    @validator("CORS_ORIGINS", pre=True)
    def parse_cors_origins(cls, v):
        if v is None:
            return []
        if isinstance(v, str):
            if v == "*":
                return ["*"]
            return [origin.strip() for origin in v.split(",") if origin.strip()]
        return v or []
    
    @validator("TRUSTED_HOSTS", pre=True)
    def parse_trusted_hosts(cls, v):
        if v is None:
            return []
        if isinstance(v, str):
            if v == "*":
                return ["*"]
            return [host.strip() for host in v.split(",") if host.strip()]
        return v or []
    
    @validator("CELERY_ACCEPT_CONTENT", pre=True)
    def parse_celery_accept_content(cls, v):
        if isinstance(v, str):
            return [content.strip() for content in v.split(",") if content.strip()]
        return v
    
    class Config:
        env_file = ".env"
        case_sensitive = True
        extra = "ignore"


class DevelopmentSettings(ProductionSettings):
    """
    Development configuration settings
    """
    ENVIRONMENT: str = "development"
    DEBUG: bool = False
    LOG_LEVEL: str = "DEBUG"
    LOG_FORMAT: str = "text"
    
    # Less restrictive CORS for development
    CORS_ORIGINS: List[str] = ["*"]
    
    # More lenient rate limiting for development
    RATE_LIMIT_PER_MINUTE: int = 1000
    RATE_LIMIT_PER_HOUR: int = 10000


class TestingSettings(ProductionSettings):
    """
    Testing configuration settings
    """
    ENVIRONMENT: str = "testing"
    DEBUG: bool = False
    LOG_LEVEL: str = "WARNING"
    
    # Use in-memory database for testing
    DATABASE_URL: str = "sqlite:///./test.db"
    
    # Disable external API calls in testing
    LOGIKAL_API_BASE_URL: str = "http://mock-logikal-api"
    
    # Fast sync for testing
    SYNC_INTERVAL_SECONDS: int = 10


@lru_cache()
def get_settings() -> ProductionSettings:
    """
    Get application settings based on environment
    """
    environment = os.getenv("ENVIRONMENT", "production").lower()
    
    if environment == "development":
        return DevelopmentSettings()
    elif environment == "testing":
        return TestingSettings()
    else:
        return ProductionSettings()


def get_database_url() -> str:
    """
    Get database URL with proper formatting
    """
    settings = get_settings()
    return settings.DATABASE_URL


def get_redis_url() -> str:
    """
    Get Redis URL with proper formatting
    """
    settings = get_settings()
    
    if settings.REDIS_PASSWORD:
        return f"redis://:{settings.REDIS_PASSWORD}@{settings.REDIS_HOST}:{settings.REDIS_PORT}/{settings.REDIS_DB}"
    else:
        return f"redis://{settings.REDIS_HOST}:{settings.REDIS_PORT}/{settings.REDIS_DB}"


def get_celery_config() -> Dict[str, Any]:
    """
    Get Celery configuration
    """
    settings = get_settings()
    
    return {
        "broker_url": settings.CELERY_BROKER_URL,
        "result_backend": settings.CELERY_RESULT_BACKEND,
        "task_serializer": settings.CELERY_TASK_SERIALIZER,
        "accept_content": settings.CELERY_ACCEPT_CONTENT,
        "result_serializer": settings.CELERY_RESULT_SERIALIZER,
        "timezone": settings.CELERY_TIMEZONE,
        "enable_utc": settings.CELERY_ENABLE_UTC,
        "worker_prefetch_multiplier": 1,
        "task_acks_late": True,
        "worker_max_tasks_per_child": 1000,
        "broker_connection_retry_on_startup": True,
        "broker_connection_retry": True,
        "broker_connection_max_retries": 10,
    }


def get_logging_config() -> Dict[str, Any]:
    """
    Get logging configuration
    """
    settings = get_settings()
    
    return {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            "json": {
                "format": "%(asctime)s %(name)s %(levelname)s %(message)s",
                "datefmt": "%Y-%m-%d %H:%M:%S",
            },
            "text": {
                "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
                "datefmt": "%Y-%m-%d %H:%M:%S",
            }
        },
        "handlers": {
            "console": {
                "class": "logging.StreamHandler",
                "level": settings.LOG_LEVEL,
                "formatter": settings.LOG_FORMAT,
                "stream": "ext://sys.stdout",
            },
            "file": {
                "class": "logging.handlers.RotatingFileHandler",
                "level": settings.LOG_LEVEL,
                "formatter": settings.LOG_FORMAT,
                "filename": settings.LOG_FILE_PATH,
                "maxBytes": settings.LOG_MAX_SIZE,
                "backupCount": settings.LOG_BACKUP_COUNT,
            }
        },
        "loggers": {
            "": {
                "handlers": ["console", "file"],
                "level": settings.LOG_LEVEL,
                "propagate": False,
            }
        }
    }


def validate_required_settings():
    """
    Validate that all required settings are present
    """
    settings = get_settings()
    required_settings = [
        "SECRET_KEY",
        "JWT_SECRET_KEY",
        "DATABASE_URL",
        "CELERY_BROKER_URL",
        "CELERY_RESULT_BACKEND",
        "LOGIKAL_API_BASE_URL",
    ]
    
    missing_settings = []
    for setting in required_settings:
        if not getattr(settings, setting, None):
            missing_settings.append(setting)
    
    if missing_settings:
        raise ValueError(f"Missing required settings: {', '.join(missing_settings)}")
    
    logger.info("All required settings are present")


# Environment-specific configurations
ENVIRONMENT_CONFIGS = {
    "production": {
        "log_level": "INFO",
        "debug": False,
        "cors_origins": [],  # Configure for production
        "trusted_hosts": [],  # Configure for production
        "rate_limit_per_minute": 60,
        "rate_limit_per_hour": 1000,
    },
    "development": {
        "log_level": "DEBUG",
        "debug": True,
        "cors_origins": ["*"],
        "trusted_hosts": ["*"],
        "rate_limit_per_minute": 1000,
        "rate_limit_per_hour": 10000,
    },
    "testing": {
        "log_level": "WARNING",
        "debug": True,
        "cors_origins": ["*"],
        "trusted_hosts": ["*"],
        "rate_limit_per_minute": 10000,
        "rate_limit_per_hour": 100000,
    }
}


def get_environment_config() -> Dict[str, Any]:
    """
    Get configuration for current environment
    """
    environment = os.getenv("ENVIRONMENT", "production").lower()
    return ENVIRONMENT_CONFIGS.get(environment, ENVIRONMENT_CONFIGS["production"])
