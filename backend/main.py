"""Placeholder module; implementation pending."""
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from typing import List
import time

from models import Vehicle, Incident, DispatchRequest, SimulationStepRequest, Position

# This line MUST be present for Uvicorn to find 'app'
app = FastAPI(title="Belos Dispatch Simulator API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

fake_vehicles = [
    Vehicle(id="AMB-1", position=Position(lat=42.7284, lng=-73.6918), status="available", capabilities=["ALS"]),
    Vehicle(id="AMB-2", position=Position(lat=42.7300, lng=-73.6850), status="available", capabilities=["BLS"]),
    Vehicle(id="AMB-3", position=Position(lat=42.7200, lng=-73.6950), status="available", capabilities=["ALS"]),
]

fake_incidents = [
    Incident(id="INC-1", location=Position(lat=42.7310, lng=-73.6880), priority=1, created_at=time.time(), required_capabilities=["ALS"]),
    Incident(id="INC-2", location=Position(lat=42.7250, lng=-73.6900), priority=2, created_at=time.time(), required_capabilities=["BLS"]),
]

@app.get("/scenario")
def get_scenario():
    return {
        "city": "Troy, NY",
        "vehicles": [v.dict() for v in fake_vehicles],
        "incidents": [i.dict() for i in fake_incidents]
    }

@app.post("/dispatch")
def post_dispatch(payload: DispatchRequest):
    incident = next((i for i in fake_incidents if i.id == payload.incident_id), None)
    if not incident:
        raise HTTPException(status_code=404, detail="Incident not found")
    
    available_vehicles = [v for v in fake_vehicles if v.status == "available"]
    if not available_vehicles:
        raise HTTPException(status_code=400, detail="No available ambulances")

    selected_vehicle = available_vehicles[0]
    selected_vehicle.status = "dispatched"
    selected_vehicle.assigned_incident = incident.id
    incident.status = "assigned"

    return {
        "strategy": payload.strategy,
        "assigned_vehicle_id": selected_vehicle.id,
        "incident_id": incident.id,
        "estimated_travel_time_minutes": 4.5,
        "status": "success"
    }

@app.post("/simulate")
def post_simulate(payload: SimulationStepRequest):
    if payload.action == "disaster_mode":
        return {"message": "Disaster mode triggered: 10 incidents added, road disruption active.", "status": "active"}
    elif payload.action == "tick":
        return {"message": "Simulation ticked forward 1 second.", "status": "running"}
    return {"message": f"Action {payload.action} processed.", "status": "success"}

@app.get("/benchmark")
def get_benchmark():
    return {
        "nearest_available": {
            "mean_response_time_minutes": 6.8,
            "total_distance_km": 142.5,
            "emissions_kg_co2": 31.3
        },
        "fleet_wide_optimizer": {
            "mean_response_time_minutes": 5.2,
            "total_distance_km": 128.1,
            "emissions_kg_co2": 28.1
        }
    }