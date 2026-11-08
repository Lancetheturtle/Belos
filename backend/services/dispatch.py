from sqlalchemy.orm import Session
from backend.models import VehicleRow, TripRow
from math import radians, sin, cos, sqrt, atan2

def calculate_distance(lat1, lon1, lat2, lon2):
    R = 6371.0
    dlat = radians(lat2 - lat1)
    dlon = radians(lon2 - lon1)
    a = sin(dlat / 2)**2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlon / 2)**2
    c = 2 * atan2(sqrt(a), sqrt(1 - a))
    return R * c

def assign_best_truck_to_call(db: Session, call_id: str, call_lat: float, call_lon: float):
    # Query available vehicles from the active VehicleRow table
    available_vehicles = db.query(VehicleRow).filter(
        VehicleRow.status == "idle",
        VehicleRow.trip_id == None
    ).all()

    if not available_vehicles:
        return None

    best_vehicle = None
    min_score = float('inf')

    for vehicle in available_vehicles:
        distance = calculate_distance(call_lat, call_lon, vehicle.lat, vehicle.lng)
        if distance < min_score:
            min_score = distance
            best_vehicle = vehicle

    if best_vehicle:
        best_vehicle.status = "dispatched"
        best_vehicle.trip_id = str(call_id)
        db.commit()
        db.refresh(best_vehicle)
        
    return best_vehicle

def reroute_ambulance_to_call(db: Session, vehicle_id: str, new_trip_id: str):
    vehicle = db.query(VehicleRow).filter(VehicleRow.id == vehicle_id).first()
    trip = db.query(TripRow).filter(TripRow.id == new_trip_id).first()
    
    if not vehicle or not trip:
        return {"error": "Vehicle or Trip not found"}
    
    vehicle.status = "rerouted"
    vehicle.trip_id = str(new_trip_id)
    
    db.commit()
    db.refresh(vehicle)
    
    return {
        "status": "success",
        "message": f"Vehicle {vehicle.id} successfully rerouted to Trip {new_trip_id}",
        "vehicle_id": vehicle.id,
        "new_destination": {"lat": trip.dest_lat, "lng": trip.dest_lng}
    }