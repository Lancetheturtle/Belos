"""Placeholder module; implementation pending."""
from pydantic import BaseModel
from typing import List, Optional, Dict, Any

class Position(BaseModel):
    lat: float
    lng: float

class Vehicle(BaseModel):
    id: str
    position: Position
    status: str  # "available", "dispatched", "offline"
    capabilities: List[str]  # e.g., ["ALS", "BLS"]
    route: List[Position] = []
    assigned_incident: Optional[str] = None

class Incident(BaseModel):
    id: str
    location: Position
    priority: int  # e.g., 1 (highest) to 3 (lowest)
    created_at: float
    required_capabilities: List[str]
    status: str = "pending"  # "pending", "assigned", "resolved"

class DispatchRequest(BaseModel):
    incident_id: str
    strategy: str = "nearest"  # "nearest" or "fleet_wide"

class SimulationStepRequest(BaseModel):
    action: str  # "tick", "disaster_mode", "reset"
    payload: Optional[Dict[str, Any]] = None