#!/usr/bin/env python3
"""
Standalone test script to reproduce the session isolation issue.
This script demonstrates the problem without FastAPI dependency injection.
"""

import asyncio
import logging
from datetime import datetime
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.ext.declarative import declarative_base

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Database configuration
DATABASE_URL = "postgresql://admin:admin123@localhost:5432/logikal_middleware"

# Create engine and session factory
engine = create_engine(DATABASE_URL, pool_pre_ping=True, pool_recycle=300, echo=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# Simple Project model for testing
class Project(Base):
    __tablename__ = "projects"
    
    id = None  # Will be set by database
    logikal_id = None
    name = None
    directory_id = None
    last_sync_date = None

def get_db():
    """Simulate FastAPI's get_db dependency"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def test_session_isolation():
    """Test that reproduces the session isolation issue"""
    print("=== Testing Session Isolation Issue ===")
    
    # Simulate the problematic pattern from the application
    db_gen = get_db()
    db = next(db_gen)
    
    try:
        print("1. Creating test project...")
        
        # Create a test project
        test_project = Project()
        test_project.logikal_id = "test-session-isolation-123"
        test_project.name = "Test Session Isolation"
        test_project.directory_id = 1
        test_project.last_sync_date = datetime.utcnow()
        
        db.add(test_project)
        print("2. Project added to session")
        
        # Commit the transaction
        db.commit()
        print("3. Transaction committed successfully")
        
        # Verify project exists in this session
        saved_project = db.query(Project).filter(Project.logikal_id == "test-session-isolation-123").first()
        if saved_project:
            print(f"4. Project found in current session: {saved_project.name}")
        else:
            print("4. ERROR: Project not found in current session after commit!")
        
        # Create a new session to check if project persists
        new_db = SessionLocal()
        try:
            persisted_project = new_db.query(Project).filter(Project.logikal_id == "test-session-isolation-123").first()
            if persisted_project:
                print(f"5. Project found in new session: {persisted_project.name}")
                print("✅ Project persistence test PASSED")
            else:
                print("5. ERROR: Project not found in new session!")
                print("❌ Project persistence test FAILED - This is the bug!")
        finally:
            new_db.close()
            
    except Exception as e:
        print(f"ERROR: {e}")
        db.rollback()
    finally:
        # This simulates what happens when FastAPI closes the session
        print("6. Closing session (simulating FastAPI dependency cleanup)...")
        db.close()
        print("7. Session closed")
        
        # Check if project still exists after session closure
        final_db = SessionLocal()
        try:
            final_project = final_db.query(Project).filter(Project.logikal_id == "test-session-isolation-123").first()
            if final_project:
                print(f"8. Project found after session closure: {final_project.name}")
                print("✅ Session closure test PASSED")
            else:
                print("8. ERROR: Project not found after session closure!")
                print("❌ Session closure test FAILED - This is the main bug!")
        finally:
            final_db.close()

def test_alternative_session_management():
    """Test alternative session management patterns"""
    print("\n=== Testing Alternative Session Management ===")
    
    # Test 1: Manual session management
    print("Test 1: Manual session management")
    db = SessionLocal()
    try:
        test_project = Project()
        test_project.logikal_id = "test-manual-session-456"
        test_project.name = "Test Manual Session"
        test_project.directory_id = 1
        test_project.last_sync_date = datetime.utcnow()
        
        db.add(test_project)
        db.commit()
        
        # Check persistence
        new_db = SessionLocal()
        try:
            persisted = new_db.query(Project).filter(Project.logikal_id == "test-manual-session-456").first()
            if persisted:
                print("✅ Manual session management works")
            else:
                print("❌ Manual session management failed")
        finally:
            new_db.close()
    finally:
        db.close()
    
    # Test 2: Context manager pattern
    print("Test 2: Context manager pattern")
    with SessionLocal() as db:
        test_project = Project()
        test_project.logikal_id = "test-context-manager-789"
        test_project.name = "Test Context Manager"
        test_project.directory_id = 1
        test_project.last_sync_date = datetime.utcnow()
        
        db.add(test_project)
        db.commit()
        
        # Check persistence
        with SessionLocal() as check_db:
            persisted = check_db.query(Project).filter(Project.logikal_id == "test-context-manager-789").first()
            if persisted:
                print("✅ Context manager pattern works")
            else:
                print("❌ Context manager pattern failed")

if __name__ == "__main__":
    print("Session Isolation Debug Test")
    print("=" * 50)
    
    try:
        # Test the problematic pattern
        test_session_isolation()
        
        # Test alternative patterns
        test_alternative_session_management()
        
    except Exception as e:
        print(f"Test failed with error: {e}")
        import traceback
        traceback.print_exc()
    
    print("\n" + "=" * 50)
    print("Test completed. Check the output above for results.")
