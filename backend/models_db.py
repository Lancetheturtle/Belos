"""Tracks historical data as it comes in"""
from sqlalchemy import Column, String, Float, DateTime, Integer, JSON
from datetime import datetime
from database import Base

class TelemetryLog(Base):
    __tablename__ = "telemetry_logs"

    id = Column(Integer, primary_key=True, index=True)
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)
    vehicle_id = Column(String, index=True)
    lat = Column(Float)
    lng = Column(Float)
    status = Column(String)
    extra_data = Column(JSON, nullable=True)