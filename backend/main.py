"""
Belos medical transport API.

Local development:
    cd backend
    pip install -r requirements.txt
    uvicorn main:app --reload --port 8000

Set DATABASE_URL in backend/.env to your Tiger Data PostgreSQL URL.
If DATABASE_URL is omitted, the app uses a local SQLite file (belos.db).

This starter implements the frontend Snapshot/Action contract. It is a
simulation backend, not a production emergency-medical dispatch system.
"""

import math
import os
from datetime import datetime, timezone
from typing import Literal, Optional

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    create_engine,
    delete,
    select,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker

load_dotenv()

# ---------------------------------------------------------------------------
# Database configuration
# ---------------------------------------------------------------------------

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./belos.db")

# Use psycopg 3 (installed by psycopg[binary]) for PostgreSQL/Tiger Data.
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql+psycopg://", 1)
elif DATABASE_URL.startswith("postgresql://"):
    DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgresql+psycopg://", 1)

engine_options = {"pool_pre_ping": True}
if DATABASE_URL.startswith("sqlite"):
    engine_options["connect_args"] = {"check_same_thread": False}

engine = create_engine(DATABASE_URL, **engine_options)
SessionLocal = sessionmaker(bind=engine, autoflush=True, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


# ---------------------------------------------------------------------------
# Database tables
# ---------------------------------------------------------------------------

class ShiftStateRow(Base):
    __tablename__ = "shift_state"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
    minute: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    traffic: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)


class VehicleRow(Base):
    __tablename__ = "vehicles"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    crew: Mapped[str] = mapped_column(String(100), nullable=False)
    lat: Mapped[float] = mapped_column(Float, nullable=False)
    lng: Mapped[float] = mapped_column(Float, nullable=False)
    out_of_service: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    hold_until: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    hold_reason: Mapped[str] = mapped_column(String(120), nullable=False, default="")
    trip_id: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)


class TripRow(Base):
    __tablename__ = "trips"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    origin: Mapped[str] = mapped_column(String(200), nullable=False)
    destination: Mapped[str] = mapped_column(String(200), nullable=False)
    pickup_lat: Mapped[float] = mapped_column(Float, nullable=False)
    pickup_lng: Mapped[float] = mapped_column(Float, nullable=False)
    destination_lat: Mapped[float] = mapped_column(Float, nullable=False)
    destination_lng: Mapped[float] = mapped_column(Float, nullable=False)
    scheduled: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="waiting")
    vehicle_id: Mapped[Optional[str]] = mapped_column(
        ForeignKey("vehicles.id"), nullable=True
    )
    actual_pickup: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    completed_at: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    transfer_lat: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    transfer_lng: Mapped[Optional[float]] = mapped_column(Float, nullable=True)


class AssignmentRow(Base):
    """Assignment history, including released/reassigned trips."""

    __tablename__ = "assignments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    trip_id: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    vehicle_id: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    assigned_minute: Mapped[int] = mapped_column(Integer, nullable=False)
    released_minute: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)


class VehiclePositionRow(Base):
    """Timestamped vehicle positions; suitable for conversion to a hypertable."""

    __tablename__ = "vehicle_positions"
    __table_args__ = (
        Index("ix_vehicle_positions_recorded_at", "recorded_at"),
    )

    # Composite key includes the time column, which is required by TimescaleDB
    # for unique indexes on a hypertable.
    vehicle_id: Mapped[str] = mapped_column(
        ForeignKey("vehicles.id"), primary_key=True
    )
    recorded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), primary_key=True
    )
    minute: Mapped[int] = mapped_column(Integer, nullable=False)
    lat: Mapped[float] = mapped_column(Float, nullable=False)
    lng: Mapped[float] = mapped_column(Float, nullable=False)


class TransportEventRow(Base):
    __tablename__ = "transport_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    minute: Mapped[int] = mapped_column(Integer, nullable=False)
    message: Mapped[str] = mapped_column(String(300), nullable=False)
    vehicle_id: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    trip_id: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc)
    )


Base.metadata.create_all(bind=engine)

# Optional: enable this only after confirming the Tiger Data project has the
# TimescaleDB extension available. The ordinary PostgreSQL table works without it.
if (
    engine.dialect.name == "postgresql"
    and os.getenv("ENABLE_HYPERTABLE", "false").lower() == "true"
):
    try:
        with engine.begin() as connection:
            connection.exec_driver_sql("CREATE EXTENSION IF NOT EXISTS timescaledb")
            connection.exec_driver_sql(
                "SELECT create_hypertable("
                "'vehicle_positions', 'recorded_at', if_not_exists => TRUE)"
            )
    except Exception as exc:
        print(f"Could not enable vehicle_positions hypertable: {exc}")


# ---------------------------------------------------------------------------
# API setup and request schema
# ---------------------------------------------------------------------------

app = FastAPI(
    title="Belos Medical Transport API",
    version="1.0.0",
    description="Backend for the Belos medical transport simulation.",
)

allowed_origins = [
    origin.strip()
    for origin in os.getenv(
        "CORS_ORIGINS",
        "http://localhost:5173,http://127.0.0.1:5173,"
        "https://belos.design,https://www.belos.design",
    ).split(",")
    if origin.strip()
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type", "Authorization"],
)


class ActionRequest(BaseModel):
    type: Literal[
        "advance", "traffic", "delay", "emergency", "outage", "restore", "assign"
    ]
    minutes: Optional[int] = Field(default=None, ge=1, le=240)
    enabled: Optional[bool] = None
    vehicleId: Optional[str] = None
    tripId: Optional[str] = None


# ---------------------------------------------------------------------------
# Demo seed data
# ---------------------------------------------------------------------------

def add_event(
    db,
    minute: int,
    message: str,
    vehicle_id: Optional[str] = None,
    trip_id: Optional[str] = None,
):
    db.add(
        TransportEventRow(
            minute=minute,
            message=message,
            vehicle_id=vehicle_id,
            trip_id=trip_id,
        )
    )

from datetime import datetime, timezone, timedelta

def save_position(db, vehicle: VehicleRow, minute: int):
    # Add a unique offset per simulation minute to prevent primary key collisions
    unique_timestamp = datetime.now(timezone.utc) + timedelta(seconds=minute, microseconds=minute * 150)
    db.add(
        VehiclePositionRow(
            vehicle_id=vehicle.id,
            recorded_at=unique_timestamp,
            minute=minute,
            lat=vehicle.lat,
            lng=vehicle.lng,
        )
    )

def reset_demo_data(db):
    """Reset the single shared demo shift to its initial synthetic data."""
    db.execute(delete(VehiclePositionRow))
    db.execute(delete(AssignmentRow))
    db.execute(delete(TransportEventRow))
    db.execute(delete(TripRow))
    db.execute(delete(VehicleRow))
    db.execute(delete(ShiftStateRow))

    shift = ShiftStateRow(id=1, minute=0, traffic=False)
    db.add(shift)

    vehicles = [
        VehicleRow(id="AMB-01", crew="Crew A", lat=42.7284, lng=-73.6918),
        VehicleRow(id="AMB-02", crew="Crew B", lat=42.7300, lng=-73.6850),
        VehicleRow(id="AMB-03", crew="Crew C", lat=42.7200, lng=-73.6950),
        VehicleRow(id="AMB-04", crew="Crew D", lat=42.7350, lng=-73.7000),
    ]
    db.add_all(vehicles)

    # Synthetic facilities and coordinates around Troy, NY. These are demo
    # locations, not verified facility addresses or live patient records.
    trips = [
        TripRow(
            id="TR-101",
            origin="Samaritan Hospital",
            destination="Rehabilitation Center",
            pickup_lat=42.7284,
            pickup_lng=-73.6918,
            destination_lat=42.7350,
            destination_lng=-73.6740,
            scheduled=30,
        ),
        TripRow(
            id="TR-102",
            origin="Troy Care Center",
            destination="Albany Medical Center",
            pickup_lat=42.7350,
            pickup_lng=-73.6890,
            destination_lat=42.6526,
            destination_lng=-73.7562,
            scheduled=45,
        ),
        TripRow(
            id="TR-103",
            origin="Rehabilitation Center",
            destination="Samaritan Hospital",
            pickup_lat=42.7410,
            pickup_lng=-73.6780,
            destination_lat=42.7284,
            destination_lng=-73.6918,
            scheduled=60,
        ),
        TripRow(
            id="TR-104",
            origin="Eddy Memorial",
            destination="Outpatient Clinic",
            pickup_lat=42.7350,
            pickup_lng=-73.6740,
            destination_lat=42.7280,
            destination_lng=-73.6820,
            scheduled=90,
        ),
    ]
    db.add_all(trips)
    db.flush()

    for vehicle in vehicles:
        save_position(db, vehicle, 0)

    add_event(db, 0, "Demo shift initialized with 4 vehicles and 4 transport requests.")


# ---------------------------------------------------------------------------
# Snapshot serialization: must match frontend/src/types/index.ts
# ---------------------------------------------------------------------------

def build_snapshot(db) -> dict:
    shift = db.get(ShiftStateRow, 1)
    if shift is None:
        raise HTTPException(status_code=500, detail="Shift state has not been initialized.")

    vehicles = db.scalars(select(VehicleRow).order_by(VehicleRow.id)).all()
    trips = db.scalars(select(TripRow).order_by(TripRow.scheduled, TripRow.id)).all()
    events = db.scalars(
        select(TransportEventRow)
        .order_by(TransportEventRow.id.desc())
        .limit(30)
    ).all()

    vehicle_data = []
    for vehicle in vehicles:
        item = {
            "id": vehicle.id,
            "crew": vehicle.crew,
            "position": [vehicle.lat, vehicle.lng],
            "outOfService": vehicle.out_of_service,
            "holdUntil": vehicle.hold_until,
            "holdReason": vehicle.hold_reason,
        }
        if vehicle.trip_id:
            item["tripId"] = vehicle.trip_id
        vehicle_data.append(item)

    trip_data = []
    for trip in trips:
        item = {
            "id": trip.id,
            "from": trip.origin,
            "to": trip.destination,
            "pickup": [trip.pickup_lat, trip.pickup_lng],
            "destination": [trip.destination_lat, trip.destination_lng],
            "scheduled": trip.scheduled,
            "status": trip.status,
        }
        if trip.vehicle_id:
            item["vehicleId"] = trip.vehicle_id
        if trip.actual_pickup is not None:
            item["actualPickup"] = trip.actual_pickup
        if trip.completed_at is not None:
            item["completedAt"] = trip.completed_at
        if trip.transfer_lat is not None and trip.transfer_lng is not None:
            item["transferLocation"] = [trip.transfer_lat, trip.transfer_lng]
        trip_data.append(item)

    return {
        "minute": shift.minute,
        "traffic": shift.traffic,
        "vehicles": vehicle_data,
        "trips": trip_data,
        "events": [event.message for event in events],
    }


# ---------------------------------------------------------------------------
# Simulation helpers
# ---------------------------------------------------------------------------

def distance_km(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    radius_km = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dlat = math.radians(lat2 - lat1)
    dlng = math.radians(lng2 - lng1)
    a = (
        math.sin(dlat / 2) ** 2
        + math.cos(p1) * math.cos(p2) * math.sin(dlng / 2) ** 2
    )
    return 2 * radius_km * math.asin(math.sqrt(a))


def move_towards(
    lat: float,
    lng: float,
    target_lat: float,
    target_lng: float,
    max_km: float,
):
    """Move along a straight-line approximation; returns (lat, lng, arrived)."""
    distance = distance_km(lat, lng, target_lat, target_lng)
    if distance <= max_km or distance == 0:
        return target_lat, target_lng, True

    fraction = max_km / distance
    return (
        lat + (target_lat - lat) * fraction,
        lng + (target_lng - lng) * fraction,
        False,
    )


def release_assignment(db, trip_id: str, minute: int):
    assignment = db.scalar(
        select(AssignmentRow)
        .where(
            AssignmentRow.trip_id == trip_id,
            AssignmentRow.released_minute.is_(None),
        )
        .order_by(AssignmentRow.id.desc())
        .limit(1)
    )
    if assignment:
        assignment.released_minute = minute


def vehicle_is_available(vehicle: VehicleRow, minute: int) -> bool:
    return (
        not vehicle.out_of_service
        and vehicle.trip_id is None
        and vehicle.hold_until <= minute
    )


def advance_shift(db, shift: ShiftStateRow, minutes: int):
    vehicles = db.scalars(select(VehicleRow).order_by(VehicleRow.id)).all()

    for _ in range(minutes):
        shift.minute += 1

        for vehicle in vehicles:
            if vehicle.hold_until <= shift.minute and vehicle.hold_reason:
                vehicle.hold_reason = ""

            if vehicle.out_of_service or vehicle.hold_until > shift.minute:
                continue

            if not vehicle.trip_id:
                continue

            trip = db.get(TripRow, vehicle.trip_id)
            if trip is None:
                vehicle.trip_id = None
                continue

            if trip.status == "pickup":
                # If this is a transfer, the replacement vehicle first travels
                # to the patient's handoff location.
                if trip.transfer_lat is not None and trip.transfer_lng is not None:
                    target_lat, target_lng = trip.transfer_lat, trip.transfer_lng
                else:
                    target_lat, target_lng = trip.pickup_lat, trip.pickup_lng
            elif trip.status == "onboard":
                target_lat, target_lng = trip.destination_lat, trip.destination_lng
            else:
                continue

            # 30 km/h on the illustrative direct route; traffic halves speed.
            km_per_minute = 0.25 if shift.traffic else 0.5
            vehicle.lat, vehicle.lng, arrived = move_towards(
                vehicle.lat,
                vehicle.lng,
                target_lat,
                target_lng,
                km_per_minute,
            )

            if arrived and trip.status == "pickup":
                is_transfer = trip.transfer_lat is not None
                trip.status = "onboard"
                if trip.actual_pickup is None:
                    trip.actual_pickup = shift.minute
                trip.transfer_lat = None
                trip.transfer_lng = None
                message = (
                    f"{vehicle.id} reached the transfer point for {trip.id}."
                    if is_transfer
                    else f"{vehicle.id} picked up transport {trip.id}."
                )
                add_event(db, shift.minute, message, vehicle.id, trip.id)

            elif arrived and trip.status == "onboard":
                trip.status = "complete"
                trip.completed_at = shift.minute
                vehicle.trip_id = None
                release_assignment(db, trip.id, shift.minute)
                add_event(
                    db,
                    shift.minute,
                    f"{vehicle.id} completed transport {trip.id}.",
                    vehicle.id,
                    trip.id,
                )

            save_position(db, vehicle, shift.minute)


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.get("/")
def root():
    return {
        "status": "online",
        "service": "Belos Medical Transport API",
        "docs": "/docs",
    }


@app.get("/health")
def health():
    # Verify that the application can reach its database.
    with SessionLocal() as db:
        db.execute(select(ShiftStateRow.id).limit(1))
    return {"status": "ok", "database": "connected"}


@app.on_event("startup")
def initialize_demo_shift():
    # Seed only if this database has never been initialized.
    with SessionLocal.begin() as db:
        if db.get(ShiftStateRow, 1) is None:
            reset_demo_data(db)


@app.get("/transport/state")
def get_transport_state():
    """Read the current shift without resetting it."""
    with SessionLocal() as db:
        return build_snapshot(db)


@app.post("/transport/reset")
def reset_transport():
    """
    Reset the single shared demo shift.

    Note: the current frontend calls this endpoint when it loads. Therefore,
    a browser refresh resets the demo until client.ts is changed to GET
    /transport/state for normal page loads.
    """
    with SessionLocal.begin() as db:
        reset_demo_data(db)
        db.flush()
        return build_snapshot(db)


@app.post("/transport/action")
def transport_action(payload: ActionRequest):
    with SessionLocal.begin() as db:
        shift = db.get(ShiftStateRow, 1)
        if shift is None:
            reset_demo_data(db)
            shift = db.get(ShiftStateRow, 1)

        if payload.type == "advance":
            if payload.minutes is None:
                raise HTTPException(status_code=422, detail="'minutes' is required.")
            advance_shift(db, shift, payload.minutes)

        elif payload.type == "traffic":
            if payload.enabled is None:
                raise HTTPException(status_code=422, detail="'enabled' is required.")
            shift.traffic = payload.enabled
            add_event(
                db,
                shift.minute,
                "Road slowdown enabled." if shift.traffic else "Road slowdown cleared.",
            )

        elif payload.type in ("delay", "emergency", "outage", "restore"):
            if not payload.vehicleId:
                raise HTTPException(status_code=422, detail="'vehicleId' is required.")

            vehicle = db.get(VehicleRow, payload.vehicleId)
            if vehicle is None:
                raise HTTPException(status_code=404, detail="Vehicle not found.")

            if payload.type in ("delay", "emergency"):
                if vehicle.out_of_service:
                    raise HTTPException(
                        status_code=409, detail="Vehicle is out of service."
                    )

                duration = 10 if payload.type == "delay" else 15
                vehicle.hold_until = max(vehicle.hold_until, shift.minute) + duration
                vehicle.hold_reason = (
                    "Crew delay" if payload.type == "delay" else "Priority interruption"
                )
                add_event(
                    db,
                    shift.minute,
                    f"{vehicle.id} held for {duration} minutes ({vehicle.hold_reason.lower()}).",
                    vehicle.id,
                    vehicle.trip_id,
                )

            elif payload.type == "outage":
                if vehicle.out_of_service:
                    raise HTTPException(
                        status_code=409, detail="Vehicle is already out of service."
                    )

                trip = db.get(TripRow, vehicle.trip_id) if vehicle.trip_id else None
                if trip is not None:
                    if trip.status == "onboard":
                        # Patient remains at the stopped vehicle's location
                        # until a replacement vehicle is explicitly assigned.
                        trip.status = "transfer"
                        trip.transfer_lat = vehicle.lat
                        trip.transfer_lng = vehicle.lng
                    elif trip.status == "pickup":
                        # If already heading to a transfer point, keep it as a
                        # transfer request; otherwise return it to waiting.
                        trip.status = (
                            "transfer"
                            if trip.transfer_lat is not None
                            else "waiting"
                        )

                    release_assignment(db, trip.id, shift.minute)
                    trip.vehicle_id = None

                vehicle.trip_id = None
                vehicle.out_of_service = True
                vehicle.hold_until = shift.minute
                vehicle.hold_reason = ""
                add_event(
                    db,
                    shift.minute,
                    f"{vehicle.id} taken out of service; affected transport flagged for reassignment.",
                    vehicle.id,
                    trip.id if trip else None,
                )

            elif payload.type == "restore":
                if not vehicle.out_of_service:
                    raise HTTPException(
                        status_code=409, detail="Vehicle is not out of service."
                    )
                vehicle.out_of_service = False
                vehicle.hold_until = shift.minute
                vehicle.hold_reason = ""
                add_event(
                    db,
                    shift.minute,
                    f"{vehicle.id} returned to service.",
                    vehicle.id,
                )

        elif payload.type == "assign":
            if not payload.tripId or not payload.vehicleId:
                raise HTTPException(
                    status_code=422,
                    detail="'tripId' and 'vehicleId' are required.",
                )

            trip = db.get(TripRow, payload.tripId)
            vehicle = db.get(VehicleRow, payload.vehicleId)

            if trip is None:
                raise HTTPException(status_code=404, detail="Transport request not found.")
            if vehicle is None:
                raise HTTPException(status_code=404, detail="Vehicle not found.")
            if trip.status not in ("waiting", "transfer"):
                raise HTTPException(
                    status_code=409,
                    detail="Only waiting or transfer requests can be assigned.",
                )
            if not vehicle_is_available(vehicle, shift.minute):
                raise HTTPException(
                    status_code=409,
                    detail="Selected vehicle is not available.",
                )

            trip.vehicle_id = vehicle.id
            trip.status = "pickup"
            vehicle.trip_id = trip.id

            db.add(
                AssignmentRow(
                    trip_id=trip.id,
                    vehicle_id=vehicle.id,
                    assigned_minute=shift.minute,
                )
            )
            add_event(
                db,
                shift.minute,
                f"{vehicle.id} assigned to transport {trip.id}.",
                vehicle.id,
                trip.id,
            )

        db.flush()
        return build_snapshot(db)
