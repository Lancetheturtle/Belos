import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.main import app
from backend.database import Base, get_db
from backend.models import Truck, EmergencyCall, VehicleRow

# Use an in-memory SQLite database for fast, isolated testing
SQLALCHEMY_DATABASE_URL = "sqlite:///:memory:"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False}
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base.metadata.create_all(bind=engine)

def override_get_db():
    try:
        db = TestingSessionLocal()
        yield db
    finally:
        db.close()

app.dependency_overrides[get_db] = override_get_db

client = TestClient(app)


def test_health_check():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "healthy"}


def test_transport_reset_and_action():
    # 1. Reset simulation state (seeds AMB-01)
    response = client.post("/transport/reset")
    assert response.status_code == 200
    data = response.json()
    assert len(data["vehicles"]) == 1
    assert data["vehicles"][0]["id"] == "AMB-01"

    # 2. Advance simulation action (should save positions to database)
    action_response = client.post("/transport/action", json={"minutes": 3})
    assert action_response.status_code == 200
    snapshot = action_response.json()
    assert len(snapshot["vehicles"]) == 1


def test_truck_dispatch():
    db = TestingSessionLocal()
    # Seed a test truck and emergency call directly in DB
    truck = Truck(id=1, name="Truck 1", status="AVAILABLE", is_active_trip=False, current_lat=42.7, current_lon=-73.6)
    call = EmergencyCall(id=101, description="Medical Emergency", latitude=42.72, longitude=-73.65)
    db.add(truck)
    db.add(call)
    db.commit()
    db.close()

    # Trigger dispatch endpoint
    response = client.post("/calls/101/dispatch?call_lat=42.72&call_lon=-73.65")
    assert response.status_code == 200
    json_data = response.json()
    assert json_data["truck_id"] == 1
    assert json_data["call_id"] == 101