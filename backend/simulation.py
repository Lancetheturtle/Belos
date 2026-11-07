from datetime import datetime, timezone, timedelta
from sqlalchemy.orm import Session
from .models import VehicleRow, TripRow, VehiclePositionRow
from .database import SessionLocal

def save_position(db: Session, vehicle: VehicleRow, minute: int):
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

def advance_shift(db: Session, shift, minutes: int):
    for _ in range(minutes):
        shift.minute += 1
        vehicles = db.query(VehicleRow).all()
        for vehicle in vehicles:
            # Update position logic here
            save_position(db, vehicle, shift.minute)
    db.commit()

def create_initial_scenario(db: Session):
    """Resets and initializes the simulation database with baseline vehicles and trips."""
    # Clear existing rows
    db.query(VehiclePositionRow).delete()
    db.query(TripRow).delete()
    db.query(VehicleRow).delete()
    db.commit()

    # Seed default test vehicle
    initial_vehicle = VehicleRow(
        id="AMB-01",
        lat=42.727286,
        lng=-73.695291,
        status="idle",
        trip_id=None
    )
    db.add(initial_vehicle)
    db.commit()

    return get_current_snapshot(db)

def get_current_snapshot(db: Session):
    """Returns the current state dictionary matching the frontend transport contract."""
    vehicles = db.query(VehicleRow).all()
    trips = db.query(TripRow).all()
    
    return {
        "minute": 0, # Or track current shift minute from database/state
        "vehicles": [
            {"id": v.id, "lat": v.lat, "lng": v.lng, "status": v.status, "trip_id": v.trip_id}
            for v in vehicles
        ],
        "trips": [
            {
                "id": t.id,
                "origin": {"lat": t.origin_lat, "lng": t.origin_lng},
                "destination": {"lat": t.dest_lat, "lng": t.dest_lng},
                "status": t.status
            }
            for t in trips
        ],
        "events": []
    }