import pytest
from backend.database import SessionLocal
from backend.models import VehicleRow, TripRow, VehiclePositionRow

@pytest.fixture
def db_session():
    """Provides an active database session for testing and cleans up after."""
    session = SessionLocal()
    yield session
    session.close()

def test_vehicle_position_history_logging(db_session):
    """Proves that multiple chronological position updates can be logged for a vehicle."""
    vehicle_id = "TEST-POS-AMB"
    
    # Ensure a parent vehicle record exists to satisfy foreign key constraints
    vehicle = VehicleRow(id=vehicle_id, lat=42.7272, lng=-73.6952, crew="Test Crew", out_of_service=False)
    db_session.merge(vehicle)
    db_session.commit()

    # Log first time-series position entry
    pos1 = VehiclePositionRow(vehicle_id=vehicle_id, lat=42.7272, lng=-73.6952, timestamp=1700000000.0)
    db_session.add(pos1)
    db_session.commit()

    # Log subsequent movement position entry
    pos2 = VehiclePositionRow(vehicle_id=vehicle_id, lat=42.7300, lng=-73.7000, timestamp=1700000060.0)
    db_session.add(pos2)
    db_session.commit()

    # Query back all historical positions for this vehicle
    positions = db_session.query(VehiclePositionRow).filter_by(vehicle_id=vehicle_id).all()
    assert len(positions) >= 2, "Should record multiple historical positions for the vehicle."
    
    # Cleanup test entries
    db_session.query(VehiclePositionRow).filter_by(vehicle_id=vehicle_id).delete()
    db_session.delete(vehicle)
    db_session.commit()

def test_trip_assignment_relationship(db_session):
    """Proves that trips can be created and linked to vehicles in Tiger Data."""
    v_id = "TEST-DISPATCH-V1"
    t_id = "TEST-TRIP-99"

    vehicle = VehicleRow(id=v_id, crew="Test Crew", lat=42.0, lng=-73.0, out_of_service=False)
    db_session.merge(vehicle)

    trip = TripRow(
        id=t_id,
        origin="HQ",
        destination="Hospital",
        pickup_lat=42.0,
        pickup_lng=-73.0,
        destination_lat=42.1,
        destination_lng=-73.1,
        scheduled=1700000000,
        status="DISPATCHED",
        vehicle_id=v_id
    )
    db_session.merge(trip)
    db_session.commit()

    saved_trip = db_session.query(TripRow).filter_by(id=t_id).first()
    assert saved_trip is not None
    assert saved_trip.vehicle_id == v_id

    # Cleanup
    db_session.delete(trip)
    db_session.delete(vehicle)
    db_session.commit()