import math
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from backend.database import get_db
from backend.models import VehicleRow, TripRow
from backend.services.osrm import get_road_route

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


@router.get("/transport/route/{vehicle_id}/{trip_id}")
def get_transport_route(
    vehicle_id: str,
    trip_id: str,
    db: Session = Depends(get_db)
):
    vehicle = db.get(VehicleRow, vehicle_id)
    trip = db.get(TripRow, trip_id)

    if not vehicle:
        raise HTTPException(404, "Vehicle not found")

    if not trip:
        raise HTTPException(404, "Trip not found")

    try:
        route = get_road_route(
            (vehicle.lat, vehicle.lng),
            (trip.origin_lat, trip.origin_lng)
        )
    except Exception:
        raise HTTPException(
            502,
            "Road-routing service unavailable or no route found"
        )

    return {
        "vehicleId": vehicle.id,
        "tripId": trip.id,
        "route": route["path"],
        "durationSeconds": route["durationSeconds"],
        "distanceMeters": route["distanceMeters"]
    }
