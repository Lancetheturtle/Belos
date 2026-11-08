from datetime import datetime, timezone, timedelta
from sqlalchemy.orm import Session
from backend.models import VehicleRow, TripRow, VehiclePositionRow


def save_position(db: Session, vehicle: VehicleRow, minute: int):
    unique_timestamp = datetime.now(timezone.utc) + timedelta(
        seconds=minute, microseconds=minute * 150
    )
    db.add(
        VehiclePositionRow(
            vehicle_id=vehicle.id,
            recorded_at=unique_timestamp,
            minute=minute,
            lat=vehicle.lat,
            lng=vehicle.lng,
        )
    )


def advance_shift(db: Session, minutes: int = 1):
    for m in range(1, minutes + 1):
        vehicles = db.query(VehicleRow).all()
        for vehicle in vehicles:
            save_position(db, vehicle, minute=m)
    db.commit()


def create_initial_scenario(db: Session):
    db.query(VehiclePositionRow).delete()
    db.query(TripRow).delete()
    db.query(VehicleRow).delete()
    db.commit()

    initial_vehicle = VehicleRow(
        id="AMB-01", lat=42.727286, lng=-73.695291, status="idle", trip_id=None
    )
    db.add(initial_vehicle)
    db.commit()

    return get_current_snapshot(db)


def get_current_snapshot(db: Session):
    vehicles = db.query(VehicleRow).all()
    trips = db.query(TripRow).all()

    return {
        "minute": 0,
        "vehicles": [
            {
                "id": v.id,
                "lat": v.lat,
                "lng": v.lng,
                "status": v.status,
                "trip_id": v.trip_id,
            }
            for v in vehicles
        ],
        "trips": [
            {
                "id": t.id,
                "origin": {"lat": t.origin_lat, "lng": t.origin_lng},
                "destination": {"lat": t.dest_lat, "lng": t.dest_lng},
                "status": t.status,
            }
            for t in trips
        ],
        "events": [],
    }