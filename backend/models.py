from sqlalchemy import (
    Column,
    String,
    Float,
    Integer,
    DateTime,
    ForeignKey,
    PrimaryKeyConstraint,
    Boolean,
)
from backend.database import Base


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

    __table_args__ = (
        PrimaryKeyConstraint("vehicle_id", "recorded_at", name="pk_vehicle_positions"),
    )


class Truck(Base):
    __tablename__ = "trucks"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, index=True)
    status = Column(String, default="AVAILABLE")
    is_active_trip = Column(Boolean, default=False)
    current_lat = Column(Float, nullable=False)
    current_lon = Column(Float, nullable=False)
    current_assigned_call_id = Column(Integer, nullable=True)


class EmergencyCall(Base):
    __tablename__ = "emergency_calls"

    id = Column(Integer, primary_key=True, index=True)
    description = Column(String, nullable=True)
    latitude = Column(Float, nullable=False)
    longitude = Column(Float, nullable=False)
    status = Column(String, default="PENDING")