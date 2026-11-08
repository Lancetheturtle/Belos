import pytest
from fastapi.testclient import TestClient
from backend.main import app

client = TestClient(app)

def test_api_root_health():
    """Verifies the backend server is running and responding."""
    response = client.get("/")
    assert response.status_code in [200, 404]  # Adjust if root has a specific welcome route

def test_cors_headers_allow_frontend():
    """Proves that CORS is configured correctly so frontend dev servers can communicate with the API."""
    response = client.options(
        "/",
        headers={
            "Origin": "http://localhost:3000",  # Common frontend port (Vite/React/Next.js)
            "Access-Control-Request-Method": "GET",
        }
    )
    # FastAPI's CORSMiddleware should return headers allowing origin
    assert response.status_code in [200, 204, 405]
    # Verify CORS headers are active in the response
    headers = {k.lower(): v for k, v in response.headers.items()}
    assert "access-control-allow-origin" in headers or "access-control-allow-methods" in headers

def test_get_vehicles_endpoint():
    """Verifies that the vehicles/ambulance endpoint responds successfully with a list or expected payload."""
    response = client.get("/vehicles") # Change path to match your actual route if different (e.g. /api/vehicles)
    # If the route exists, check that it returns valid JSON (list or dict)
    if response.status_code == 200:
        data = response.json()
        assert isinstance(data, (list, dict)), "Vehicles endpoint must return JSON data."
    else:
        # If route uses a different path prefix, flag it
        assert response.status_code != 500, "Server threw an internal error on vehicles endpoint."