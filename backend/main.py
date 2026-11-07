from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional

# Use relative imports with dots (.) for files inside the same backend folder
from .database import engine, get_db, Base
from .models import VehicleRow, TripRow, VehiclePositionRow
from .simulation import advance_shift, create_initial_scenario, get_current_snapshot

# Create database tables automatically on startup
Base.metadata.create_all(bind=engine)

app = FastAPI(title="Belos Medical Transport Backend", version="1.0.0")

# Enable CORS for frontend connectivity
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allows all origins for local dev
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class ActionPayload(BaseModel):
    action: Optional[str] = "tick"
    minutes: Optional[int] = 1
    trip_id: Optional[str] = None
    vehicle_id: Optional[str] = None

@app.post("/transport/reset")
def transport_reset(db: Session = Depends(get_db)):
    """Resets the simulation to the initial scenario state."""
    return create_initial_scenario(db)

@app.post("/transport/action")
def transport_action(payload: ActionPayload, db: Session = Depends(get_db)):
    """Advances the simulation shift or handles user dispatcher actions."""
    try:
        # If the action involves advancing time
        if payload.minutes and payload.minutes > 0:
            # Fetch current shift state or create a default session tracker
            advance_shift(db, payload.minutes)
            
        return get_current_snapshot(db)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/health")
def health_check():
    return {"status": "healthy"}