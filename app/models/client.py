from sqlalchemy import Column, Integer, String, Boolean, DateTime, JSON, Text
from sqlalchemy.sql import func
from datetime import datetime
from core.database import Base


class Client(Base):
    """Client model for Odoo instances and other API consumers"""
    __tablename__ = "clients"
    
    id = Column(Integer, primary_key=True, index=True)
    client_id = Column(String(255), unique=True, nullable=False, index=True)  # Odoo instance identifier
    client_secret_hash = Column(String(255), nullable=False)
    name = Column(String(255), nullable=False)  # Human-readable name
    description = Column(Text, nullable=True)
    permissions = Column(JSON, nullable=False, default=list)  # ["projects:read", "elevations:read", "admin:read"]
    rate_limit_per_hour = Column(Integer, default=1000, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=func.now(), nullable=False)
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now(), nullable=False)
    last_used_at = Column(DateTime, nullable=True)
    
    def __repr__(self):
        return f"<Client(id={self.client_id}, name={self.name}, active={self.is_active})>"
