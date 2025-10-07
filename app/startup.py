#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Production startup script for DigitalOcean App Platform
Handles database initialization and application startup
"""

import os
import sys
import logging
import time
import subprocess
from pathlib import Path

# Add the app directory to Python path
app_dir = Path(__file__).parent
sys.path.insert(0, str(app_dir))

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def wait_for_database(max_retries=30, delay=2):
    """
    Wait for database to be available
    """
    logger.info("Waiting for database to be available...")
    
    for attempt in range(max_retries):
        try:
            from core.database import engine
            from sqlalchemy import text
            with engine.connect() as connection:
                connection.execute(text("SELECT 1"))
            logger.info("Database is available")
            return True
        except Exception as e:
            logger.warning(f"Database not ready (attempt {attempt + 1}/{max_retries}): {e}")
            time.sleep(delay)
    
    logger.error("Database is not available after maximum retries")
    return False


def setup_database():
    """
    Setup database for production
    """
    try:
        from core.database_init import setup_production_database
        
        logger.info("Setting up production database...")
        success = setup_production_database()
        
        if success:
            logger.info("Database setup completed successfully")
            return True
        else:
            logger.error("Database setup failed")
            return False
            
    except Exception as e:
        logger.error(f"Database setup error: {e}")
        return False


def validate_environment():
    """
    Validate required environment variables
    """
    logger.info("Validating environment variables...")
    
    required_vars = [
        "SECRET_KEY",
        "JWT_SECRET_KEY", 
        "DATABASE_URL",
        "LOGIKAL_API_BASE_URL"
    ]
    
    missing_vars = []
    for var in required_vars:
        if not os.getenv(var):
            missing_vars.append(var)
    
    if missing_vars:
        logger.error(f"Missing required environment variables: {missing_vars}")
        return False
    
    logger.info("Environment validation passed")
    return True


def start_application():
    """
    Start the FastAPI application
    """
    logger.info("Starting FastAPI application...")
    
    # Get port from environment or use default
    port = os.getenv("PORT", "8000")
    host = os.getenv("HOST", "0.0.0.0")
    workers = os.getenv("WORKERS", "4")
    
    # Start uvicorn server
    cmd = [
        "uvicorn", 
        "main:app", 
        "--host", host,
        "--port", port,
        "--workers", workers,
        "--access-log",
        "--log-level", "info"
    ]
    
    logger.info(f"Starting server with command: {' '.join(cmd)}")
    
    try:
        # Start the server
        subprocess.run(cmd, check=True)
    except subprocess.CalledProcessError as e:
        logger.error(f"Failed to start application: {e}")
        return False
    except KeyboardInterrupt:
        logger.info("Application stopped by user")
        return True
    
    return True


def main():
    """
    Main startup function
    """
    logger.info("Starting Logikal Middleware for production...")
    
    # Validate environment
    if not validate_environment():
        logger.error("Environment validation failed")
        sys.exit(1)
    
    # Wait for database
    if not wait_for_database():
        logger.error("Database is not available")
        sys.exit(1)
    
    # Setup database
    if not setup_database():
        logger.error("Database setup failed")
        sys.exit(1)
    
    # Start application
    logger.info("Starting application...")
    success = start_application()
    
    if not success:
        logger.error("Application startup failed")
        sys.exit(1)
    
    logger.info("Application started successfully")


if __name__ == "__main__":
    main()
# Force deployment update - Tue Oct  7 21:14:57 CEST 2025
# Force fresh deployment - Tue Oct  7 21:25:36 CEST 2025
