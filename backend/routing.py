import math
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from backend.database import get_db
from backend.models import VehicleRow, TripRow

router = APIRouter(tags=["Routing"])


def calculate_distance(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    R = 3958.8
    dlat = math.radians(lat2 - lat1)
    dlng = math.radians(lng2 - lng1)
    a = (
        math.sin(dlat / 2) ** 2
        + math.cos(math.radians(lat1))
        * math.cos(math.radians(lat2))
        * math.sin(dlng / 2) ** 2
    )
    c = 2 * math.asin(math.sqrt(a))
    return R * c


@router.patch("/vehicles/{vehicle_id}/status")
def update_vehicle_status(
    vehicle_id: str, new_status: str, db: Session = Depends(get_db)
):
    vehicle = db.query(VehicleRow).filter(VehicleRow.id == vehicle_id).first()
    if not vehicle:
        raise HTTPException(status_code=404, detail="Vehicle not found")

    if new_status == "out_of_service" and vehicle.trip_id:
        trip = db.query(TripRow).filter(TripRow.id == vehicle.trip_id).first()
        if trip:
            trip.status = "pending"
        vehicle.trip_id = None

    vehicle.status = new_status
    db.commit()
    db.refresh(vehicle)
    return vehicle