from sqlalchemy import Column, String, Float, Integer, DateTime, ForeignKey, PrimaryKeyConstraint
from .database import Base

class VehicleRow(Base):
    __tablename__ = "vehicles"
    
    id = Column(String, primary_key=True, index=True)
    lat = Column(Float, nullable=False)
    lng = Column(Float, nullable=False)
    trip_id = Column(String, nullable=True)
    status = Column(String, default="idle")


class TripRow(Base):
    __tablename__ = "trips"
    
    id = Column(String, primary_key=True, index=True)
    origin_lat = Column(Float, nullable=False)
    origin_lng = Column(Float, nullable=False)
    dest_lat = Column(Float, nullable=False)
    dest_lng = Column(Float, nullable=False)
    status = Column(String, default="pending")


class VehiclePositionRow(Base):
    __tablename__ = "vehicle_positions"
    
    vehicle_id = Column(String, ForeignKey("vehicles.id"), nullable=False)
    recorded_at = Column(DateTime, nullable=False)
    minute = Column(Integer, nullable=False)
    lat = Column(Float, nullable=False)
    lng = Column(Float, nullable=False)
    
    # Composite primary key matching vehicle_id and recorded_at timestamp
    __table_args__ = (
        PrimaryKeyConstraint('vehicle_id', 'recorded_at', name='pk_vehicle_positions'),
    )

