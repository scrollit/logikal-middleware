"""
Test fixtures and configuration for Phase 1 optimization tests.
"""

import pytest
import asyncio
import tempfile
import shutil
from pathlib import Path
from unittest.mock import Mock, AsyncMock
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import StaticPool

from app.core.database import Base
from app.models.elevation import Elevation
from app.models.elevation_glass import ElevationGlass
from app.services.sqlite_validation_service import SQLiteValidationService, ValidationResult


# Pytest configuration
def pytest_configure(config):
    """Configure pytest with custom markers"""
    config.addinivalue_line("markers", "slow: marks tests as slow (deselect with '-m \"not slow\"')")
    config.addinivalue_line("markers", "integration: marks tests as integration tests")
    config.addinivalue_line("markers", "unit: marks tests as unit tests")


# Async test support
@pytest.fixture(scope="session")
def event_loop():
    """Create event loop for async tests"""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


# Database fixtures
@pytest.fixture(scope="session")
def test_db_engine():
    """
    Create in-memory SQLite database engine for tests.
    Using in-memory DB for speed, or can switch to PostgreSQL test DB.
    """
    # Option 1: In-memory SQLite (fast, but limited)
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    
    # Option 2: PostgreSQL test database (uncomment to use)
    # engine = create_engine(
    #     "postgresql://test:test@localhost/logikal_test",
    #     pool_pre_ping=True
    # )
    
    # Create all tables
    Base.metadata.create_all(engine)
    
    yield engine
    
    # Cleanup
    Base.metadata.drop_all(engine)
    engine.dispose()


@pytest.fixture
def db_session(test_db_engine):
    """Create database session for each test"""
    SessionLocal = sessionmaker(
        bind=test_db_engine,
        autocommit=False,
        autoflush=False,
        expire_on_commit=False
    )
    session = SessionLocal()
    
    yield session
    
    # Rollback any uncommitted changes
    session.rollback()
    session.close()


@pytest.fixture
def mock_db():
    """Create mock database session"""
    mock = Mock(spec=Session)
    mock.query.return_value.filter.return_value.first.return_value = None
    mock.commit = Mock()
    mock.rollback = Mock()
    mock.add = Mock()
    return mock


# SQLite file fixtures
@pytest.fixture(scope="session")
def sample_sqlite_file():
    """
    Find and copy a sample SQLite file from production for testing.
    Returns path to temporary copy.
    """
    # Look for existing SQLite files
    parts_dir = Path("/app/parts_db/elevations")
    
    if parts_dir.exists():
        sqlite_files = list(parts_dir.glob("*.db"))
        if sqlite_files:
            # Copy first file to temp location
            temp_dir = tempfile.mkdtemp()
            src_file = sqlite_files[0]
            dest_file = Path(temp_dir) / "test.db"
            shutil.copy(str(src_file), str(dest_file))
            
            yield str(dest_file)
            
            # Cleanup
            shutil.rmtree(temp_dir)
            return
    
    # If no production files, create minimal test file
    temp_dir = tempfile.mkdtemp()
    test_file = Path(temp_dir) / "test.db"
    _create_minimal_test_sqlite(str(test_file))
    
    yield str(test_file)
    
    shutil.rmtree(temp_dir)


def _create_minimal_test_sqlite(filepath: str):
    """Create a minimal SQLite file with required schema for testing"""
    import sqlite3
    
    conn = sqlite3.connect(filepath)
    cursor = conn.cursor()
    
    # Create Elevations table
    cursor.execute("""
        CREATE TABLE Elevations (
            Name TEXT,
            AutoDescription TEXT,
            AutoDescriptionShort TEXT,
            Width_Output REAL,
            Width_Unit TEXT,
            Height_Output REAL,
            Height_Unit TEXT,
            Weight_Output REAL,
            Weight_Unit TEXT,
            Area_Output REAL,
            Area_Unit TEXT,
            SystemCode TEXT,
            SystemName TEXT,
            SystemLongName TEXT,
            ColorBase_Long TEXT
        )
    """)
    
    # Insert sample data
    cursor.execute("""
        INSERT INTO Elevations VALUES (
            'Test Elevation',
            'Test Auto Description',
            'Test Short',
            1000.0, 'mm',
            2000.0, 'mm',
            50.0, 'kg',
            2.0, 'm2',
            'SYS001',
            'Test System',
            'Test System Long Name',
            'Test Color'
        )
    """)
    
    # Create Glass table
    cursor.execute("""
        CREATE TABLE Glass (
            GlassID TEXT,
            Name TEXT
        )
    """)
    
    # Insert sample glass
    cursor.execute("""
        INSERT INTO Glass VALUES ('GLASS001', 'Test Glass 1')
    """)
    cursor.execute("""
        INSERT INTO Glass VALUES ('GLASS002', 'Test Glass 2')
    """)
    
    conn.commit()
    conn.close()


@pytest.fixture
def test_elevation(db_session, sample_sqlite_file):
    """Create test elevation with SQLite file"""
    elevation = Elevation(
        logikal_id="test-elev-001",
        name="Test Elevation",
        parts_db_path=sample_sqlite_file,
        has_parts_data=True,
        parse_status="pending"
    )
    db_session.add(elevation)
    db_session.commit()
    db_session.refresh(elevation)
    
    yield elevation
    
    # Cleanup
    db_session.query(ElevationGlass).filter_by(elevation_id=elevation.id).delete()
    db_session.delete(elevation)
    db_session.commit()


# Service fixtures
@pytest.fixture
def mock_validation_service():
    """Mock validation service"""
    service = Mock(spec=SQLiteValidationService)
    
    # Mock validate_file to return success by default
    service.validate_file = AsyncMock(return_value=ValidationResult(
        valid=True,
        message="Validation successful"
    ))
    
    # Mock calculate_file_hash
    service.calculate_file_hash = AsyncMock(return_value="abc123def456")
    
    # Mock _open_sqlite_readonly
    mock_conn = Mock()
    mock_conn.cursor.return_value = Mock()
    mock_conn.close = Mock()
    service._open_sqlite_readonly = AsyncMock(return_value=mock_conn)
    
    return service


@pytest.fixture
def mock_sqlite_connection():
    """Mock SQLite connection"""
    mock_conn = Mock()
    mock_cursor = Mock()
    
    # Setup cursor mock
    mock_cursor.fetchone.return_value = ("ok",)
    mock_cursor.fetchall.return_value = []
    mock_conn.cursor.return_value = mock_cursor
    mock_conn.close = Mock()
    
    return mock_conn


# Timing fixtures
@pytest.fixture
def timer():
    """Simple timer fixture for performance testing"""
    import time
    
    class Timer:
        def __init__(self):
            self.start_time = None
            self.elapsed = None
        
        def start(self):
            self.start_time = time.time()
        
        def stop(self):
            self.elapsed = time.time() - self.start_time
            return self.elapsed
        
        def __enter__(self):
            self.start()
            return self
        
        def __exit__(self, *args):
            self.stop()
    
    return Timer()


# Parametrize helpers
def pytest_generate_tests(metafunc):
    """Generate parametrized tests"""
    # Example: parametrize trusted_source tests
    if "trusted_source_flag" in metafunc.fixturenames:
        metafunc.parametrize("trusted_source_flag", [True, False])

