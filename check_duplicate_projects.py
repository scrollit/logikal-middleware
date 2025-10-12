#!/usr/bin/env python3
"""
Script to check for duplicate projects and directory context issues
"""
import os
import sys
import asyncio
import logging
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

# Add the app directory to Python path
sys.path.append('/home/jasperhendrickx/clients/logikal-middleware-dev')

# Database connection
DATABASE_URL = "postgresql://logikal_user:logikal_password@localhost:5433/logikal_db"
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def check_duplicate_projects():
    """Check for duplicate projects by name and analyze directory context"""
    
    db = SessionLocal()
    try:
        # Check for duplicate project names
        logger.info("=== Checking for duplicate project names ===")
        duplicate_names_query = text("""
            SELECT name, COUNT(*) as count, 
                   STRING_AGG(logikal_id, ', ') as guids,
                   STRING_AGG(CAST(directory_id AS TEXT), ', ') as directory_ids
            FROM projects 
            WHERE name IS NOT NULL 
            GROUP BY name 
            HAVING COUNT(*) > 1
            ORDER BY count DESC, name
        """)
        
        duplicates = db.execute(duplicate_names_query).fetchall()
        
        if duplicates:
            logger.warning(f"Found {len(duplicates)} duplicate project names:")
            for row in duplicates:
                logger.warning(f"  - {row.name}: {row.count} instances")
                logger.warning(f"    GUIDs: {row.guids}")
                logger.warning(f"    Directory IDs: {row.directory_ids}")
        else:
            logger.info("✅ No duplicate project names found")
        
        # Check specific project DOS22309
        logger.info("\n=== Checking DOS22309 specifically ===")
        dos22309_query = text("""
            SELECT p.name, p.logikal_id, p.directory_id, d.name as directory_name, d.full_path
            FROM projects p
            LEFT JOIN directories d ON p.directory_id = d.id
            WHERE p.name = 'DOS22309'
            ORDER BY p.logikal_id
        """)
        
        dos22309_results = db.execute(dos22309_query).fetchall()
        
        if dos22309_results:
            logger.info(f"Found {len(dos22309_results)} instance(s) of DOS22309:")
            for row in dos22309_results:
                logger.info(f"  - GUID: {row.logikal_id}")
                logger.info(f"    Directory: {row.directory_name} (ID: {row.directory_id})")
                logger.info(f"    Path: {row.full_path}")
        else:
            logger.warning("❌ DOS22309 not found in database")
        
        # Check directory context for projects
        logger.info("\n=== Checking directory distribution ===")
        directory_dist_query = text("""
            SELECT d.name as directory_name, d.full_path, COUNT(p.id) as project_count
            FROM directories d
            LEFT JOIN projects p ON d.id = p.directory_id
            WHERE d.exclude_from_sync = FALSE
            GROUP BY d.id, d.name, d.full_path
            HAVING COUNT(p.id) > 0
            ORDER BY project_count DESC, d.name
        """)
        
        directory_dist = db.execute(directory_dist_query).fetchall()
        
        logger.info("Projects per directory (non-excluded directories only):")
        for row in directory_dist:
            logger.info(f"  - {row.directory_name}: {row.project_count} projects")
            logger.info(f"    Path: {row.full_path}")
        
        # Check for projects without directory context
        logger.info("\n=== Checking projects without directory context ===")
        no_directory_query = text("""
            SELECT name, logikal_id, directory_id
            FROM projects 
            WHERE directory_id IS NULL
            ORDER BY name
        """)
        
        no_directory = db.execute(no_directory_query).fetchall()
        
        if no_directory:
            logger.warning(f"Found {len(no_directory)} projects without directory context:")
            for row in no_directory:
                logger.warning(f"  - {row.name} (GUID: {row.logikal_id})")
        else:
            logger.info("✅ All projects have directory context")
            
    except Exception as e:
        logger.error(f"Database query failed: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    check_duplicate_projects()
