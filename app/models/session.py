from sqlalchemy import Column, Integer, String, DateTime, Boolean
from sqlalchemy.sql import func
from core.database import Base


class Session(Base):
    """Session model for storing authentication sessions"""
    __tablename__ = "sessions"
    
    id = Column(Integer, primary_key=True, index=True)
    token = Column(String(255), unique=True, nullable=False, index=True)
    username = Column(String(255), nullable=False)
    base_url = Column(String(255), nullable=False)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    def __repr__(self):
        return f"<Session(id={self.id}, username='{self.username}', token='{self.token[:10]}...')>"
