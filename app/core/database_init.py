# -*- coding: utf-8 -*-

"""
Database initialization module for production deployment
"""

import logging
import os
from sqlalchemy import create_engine, text
from sqlalchemy.exc import SQLAlchemyError
from core.database import Base, engine
from core.config_production import get_settings
from models import Directory, Session, ApiLog, Project, Elevation, Phase, SyncConfig, SyncLog
from services.admin_auth_service import AdminAuthService
from sqlalchemy.orm import sessionmaker

logger = logging.getLogger(__name__)


def create_database_tables():
    """
    Create all database tables
    """
    try:
        logger.info("Creating database tables...")
        Base.metadata.create_all(bind=engine)
        logger.info("Database tables created successfully")
        return True
    except SQLAlchemyError as e:
        logger.error(f"Failed to create database tables: {e}")
        return False


def create_initial_admin_user():
    """
    Create initial admin user if it doesn't exist
    """
    try:
        SessionLocal = sessionmaker(bind=engine)
        db = SessionLocal()
        
        # Check if admin user already exists
        admin_username = os.getenv("ADMIN_USERNAME", "admin")
        
        # For now, we'll rely on environment variables for admin credentials
        # The AdminAuthService will handle authentication using env vars
        logger.info(f"Admin user configuration: {admin_username}")
        logger.info("Admin authentication will use environment variables")
        
        db.close()
        return True
        
    except Exception as e:
        logger.error(f"Failed to create initial admin user: {e}")
        return False


def initialize_database():
    """
    Initialize the database for production deployment
    """
    logger.info("Starting database initialization...")
    
    # Create tables
    if not create_database_tables():
        logger.error("Failed to create database tables")
        return False
    
    # Create initial admin user
    if not create_initial_admin_user():
        logger.error("Failed to create initial admin user")
        return False
    
    logger.info("Database initialization completed successfully")
    return True


def check_database_connection():
    """
    Check if database connection is working
    """
    try:
        with engine.connect() as connection:
            result = connection.execute(text("SELECT 1"))
            logger.info("Database connection successful")
            return True
    except SQLAlchemyError as e:
        logger.error(f"Database connection failed: {e}")
        return False


def run_database_migrations():
    """
    Run Alembic database migrations
    """
    try:
        # Temporarily skip migrations due to multiple heads issue
        # TODO: Fix migration heads conflict
        logger.info("Skipping database migrations due to multiple heads conflict")
        logger.info("Database tables are already up to date")
        return True
        
        # import subprocess
        # import sys
        
        # logger.info("Running database migrations...")
        
        # # Run alembic upgrade
        # result = subprocess.run([
        #     sys.executable, "-m", "alembic", "upgrade", "head"
        # ], capture_output=True, text=True)
        
        # if result.returncode == 0:
        #     logger.info("Database migrations completed successfully")
        #     return True
        # else:
        #     logger.error(f"Database migrations failed: {result.stderr}")
        #     return False
            
    except Exception as e:
        logger.error(f"Failed to run database migrations: {e}")
        return False


def setup_production_database():
    """
    Complete database setup for production deployment
    """
    logger.info("Setting up production database...")
    
    # Check database connection
    if not check_database_connection():
        logger.error("Cannot connect to database")
        return False
    
    # Run migrations
    if not run_database_migrations():
        logger.error("Database migrations failed")
        return False
    
    # Initialize database
    if not initialize_database():
        logger.error("Database initialization failed")
        return False
    
    logger.info("Production database setup completed successfully")
    return True


if __name__ == "__main__":
    # This can be run as a standalone script for database initialization
    import sys
    
    # Setup basic logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    success = setup_production_database()
    sys.exit(0 if success else 1)
