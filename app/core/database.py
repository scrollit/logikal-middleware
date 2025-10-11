from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from core.config import settings

# Fix DATABASE_URL for DigitalOcean compatibility
# DigitalOcean provides postgres:// but SQLAlchemy 1.4+ requires postgresql://
database_url = settings.DATABASE_URL
if database_url.startswith("postgres://"):
    database_url = database_url.replace("postgres://", "postgresql://", 1)

# Create database engine
engine = create_engine(
    database_url,
    pool_pre_ping=True,
    pool_recycle=300,
    echo=False,  # Disable SQL logging for cleaner logs
    future=True,
)

# Create session factory
SessionLocal = sessionmaker(
    bind=engine,
    autocommit=False,
    autoflush=False,
    expire_on_commit=False,   # << important - stops SQLAlchemy from expiring objects on each commit
    future=True,
)

# Create base class for models
Base = declarative_base()


def get_db():
    """Dependency to get database session"""
    db = SessionLocal()
    try:
        yield db
    finally:
        # This does NOT roll back committed work; it only returns the connection to the pool.
        db.close()
