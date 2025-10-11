from pydantic_settings import BaseSettings
from pydantic import validator
from typing import Optional
import os


class Settings(BaseSettings):
    """Application configuration settings"""
    
    # Logikal API Configuration
    LOGIKAL_BASE_URL: str = "https://logikal.api"
    AUTH_USERNAME: str = "your_logikal_username"
    AUTH_PASSWORD: str = "your_logikal_password"
    
    # Database Configuration
    DATABASE_URL: str = "postgresql://admin:admin@db:5432/logikal_middleware"
    
    # Redis Configuration
    REDIS_URL: str = "redis://redis:6379"
    
    # Application Configuration
    APP_NAME: str = "Logikal Middleware"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = False
    
    # Security Configuration
    SECRET_KEY: str = "your-secret-key-here"
    JWT_SECRET_KEY: str = "your-jwt-secret-key-change-in-production"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    
    # API Configuration
    API_V1_STR: str = "/api/v1"
    
    @validator("DATABASE_URL", pre=True)
    def fix_database_url(cls, v):
        """
        Fix DATABASE_URL format for DigitalOcean compatibility.
        DigitalOcean provides postgres:// but SQLAlchemy 1.4+ requires postgresql://
        """
        if v and isinstance(v, str) and v.startswith("postgres://"):
            return v.replace("postgres://", "postgresql://", 1)
        return v
    
    class Config:
        env_file = ".env.docker"
        case_sensitive = True
        extra = "ignore"


# Global settings instance
settings = Settings()
