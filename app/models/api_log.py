from sqlalchemy import Column, Integer, String, DateTime, Boolean, Text
from sqlalchemy.sql import func
from core.database import Base


class ApiLog(Base):
    """API log model for storing API call information"""
    __tablename__ = "api_logs"
    
    id = Column(Integer, primary_key=True, index=True)
    endpoint = Column(String(255), nullable=False)
    method = Column(String(10), nullable=False)
    status_code = Column(Integer, nullable=True)
    response_time_ms = Column(Integer, nullable=True)
    success = Column(Boolean, nullable=False)
    error_message = Column(Text, nullable=True)
    request_url = Column(String(500), nullable=True)
    request_method = Column(String(10), nullable=True)
    request_payload = Column(Text, nullable=True)
    response_body = Column(Text, nullable=True)
    response_summary = Column(String(500), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    def __repr__(self):
        return f"<ApiLog(id={self.id}, endpoint='{self.endpoint}', method='{self.method}', success={self.success})>"
