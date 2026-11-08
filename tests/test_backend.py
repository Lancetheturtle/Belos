import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

# Import production database configuration and models
from backend.database import DATABASE_URL, Base
from backend.models import VehicleRow

# Connect directly to your Tiger Data instance
engine = create_engine(
    DATABASE_URL, pool_pre_ping=True, connect_args={"connect_timeout": 5}
)
SessionTest = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def test_tiger_data_write_and_read_ambulance():
    """Proves that data can be successfully sent (written) and retrieved (read) from Tiger Data using the vehicles table."""
    db = SessionTest()
    test_vehicle_id = "TEST-AMB-99"

    try:
        # 1. Clean up any leftover test record from a previous run
        db.query(VehicleRow).filter(VehicleRow.id == test_vehicle_id).delete()
        db.commit()

        # 2. Create a test vehicle/ambulance row record
        new_ambulance = VehicleRow(
            id=test_vehicle_id,
            lat=42.7272,
            lng=-73.6952,
            status="idle",
            trip_id=None
        )

        # 3. Send (write) the data to the database
        db.add(new_ambulance)
        db.commit()
        print(f"\nSUCCESS: Sent vehicle {test_vehicle_id} to Tiger Data database.")

        # 4. Fetch (read) the data back from the database to verify it arrived
        saved_ambulance = db.query(VehicleRow).filter(VehicleRow.id == test_vehicle_id).first()

        # 5. Assertions to guarantee data made it there safely
        assert saved_ambulance is not None, "Data failed to persist; vehicle record not found in database."
        assert saved_ambulance.id == test_vehicle_id
        assert saved_ambulance.lat == 42.7272
        assert saved_ambulance.status == "idle"
        print(f"SUCCESS: Verified data exists in database for vehicle: {saved_ambulance.id}")

    finally:
        # Clean up the test record so the database stays pristine
        db.query(VehicleRow).filter(VehicleRow.id == test_vehicle_id).delete()
        db.commit()
        db.close()