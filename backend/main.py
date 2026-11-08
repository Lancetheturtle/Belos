from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional
from sqlalchemy import text

from backend.database import engine, get_db, Base
from backend.simulation import advance_shift, create_initial_scenario, get_current_snapshot
from backend.services.dispatch import assign_best_truck_to_call, reroute_ambulance_to_call
from backend.routing import router as routing_router

# Single authoritative FastAPI app initialization
app = FastAPI(title="Belos Medical Transport Backend", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(routing_router)


class ActionPayload(BaseModel):
    action: Optional[str] = "tick"
    minutes: Optional[int] = 1
    trip_id: Optional[str] = None
    vehicle_id: Optional[str] = None


@app.on_event("startup")
def startup_event():
    print("Attempting to connect to Tiger Data...")
    try:
        Base.metadata.create_all(bind=engine)
        print("Successfully connected and initialized tables!")
    except Exception as e:
        print(f"CRITICAL: Could not connect to database: {e}")


@app.post("/transport/reset")
def transport_reset(db: Session = Depends(get_db)):
    return create_initial_scenario(db)


@app.post("/transport/action")
def transport_action(payload: ActionPayload, db: Session = Depends(get_db)):
    try:
        if payload.minutes and payload.minutes > 0:
            advance_shift(db, payload.minutes)
        return get_current_snapshot(db)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/health")
def health_check():
    return {"status": "healthy"}


@app.get("/health/db")
def test_db_connection(db: Session = Depends(get_db)):
    try:
        result = db.execute(text("SELECT 1")).scalar()
        return {
            "status": "success",
            "message": "Successfully connected to Tiger Data!",
            "test_query_result": result,
        }
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Database connection failed: {str(e)}"
        )


@app.post("/calls/{call_id}/dispatch")
def dispatch_truck_for_call(call_id: int, call_lat: float, call_lon: float, db: Session = Depends(get_db)):
    truck = assign_best_truck_to_call(db, call_id, call_lat, call_lon)
    if not truck:
        raise HTTPException(status_code=404, detail="No available trucks found for dispatch.")
    return {"message": "Truck successfully assigned", "truck_id": truck.id, "call_id": call_id}


@app.post("/trucks/{truck_id}/reroute/{call_id}")
def api_reroute_truck(truck_id: int, call_id: int, db: Session = Depends(get_db)):
    result = reroute_ambulance_to_call(db, truck_id, call_id)
    if "error" in result:
        raise HTTPException(status_code=404, detail=result["error"])
    return result