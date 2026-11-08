from sqlalchemy.orm import Session
from backend.models import Truck, EmergencyCall
from math import radians, sin, cos, sqrt, atan2

def calculate_distance(lat1, lon1, lat2, lon2):
    R = 6371.0
    dlat = radians(lat2 - lat1)
    dlon = radians(lon2 - lon1)
    a = sin(dlat / 2)**2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlon / 2)**2
    c = 2 * atan2(sqrt(a), sqrt(1 - a))
    return R * c

def assign_best_truck_to_call(db: Session, call_id: int, call_lat: float, call_lon: float):
    available_trucks = db.query(Truck).filter(
        Truck.status == "AVAILABLE",
        Truck.is_active_trip == False
    ).all()

    if not available_trucks:
        return None

    best_truck = None
    min_score = float('inf')

    for truck in available_trucks:
        distance = calculate_distance(call_lat, call_lon, truck.current_lat, truck.current_lon)
        if distance < min_score:
            min_score = distance
            best_truck = truck

    if best_truck:
        best_truck.status = "DISPATCHED"
        best_truck.is_active_trip = True
        best_truck.current_assigned_call_id = call_id
        db.commit()
        db.refresh(best_truck)
        
    return best_truck

def reroute_ambulance_to_call(db: Session, truck_id: int, new_call_id: int):
    truck = db.query(Truck).filter(Truck.id == truck_id).first()
    call = db.query(EmergencyCall).filter(EmergencyCall.id == new_call_id).first()
    
    if not truck or not call:
        return {"error": "Truck or Emergency Call not found"}
    
    truck.status = "DISPATCHED_REROUTED"
    truck.is_active_trip = True
    truck.current_assigned_call_id = new_call_id
    
    db.commit()
    db.refresh(truck)
    
    return {
        "status": "success",
        "message": f"Truck {truck.id} successfully rerouted to Call {new_call_id}",
        "truck_id": truck.id,
        "new_destination": {"lat": call.latitude, "lon": call.longitude}
    }