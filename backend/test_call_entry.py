import tempfile
import unittest
from pathlib import Path
from fastapi.testclient import TestClient
from .test_dispatch import seed, Roads
from .transport_api import DispatchService, StateStore, create_app


class CallEntryTests(unittest.TestCase):
    def test_calls_reports_duplicate_protection_and_sql_restart(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "state.sqlite3"
            service = DispatchService(Roads(), StateStore(path), seed())
            with TestClient(create_app(service, speed=0)) as client:
                initial = client.get("/transport/state").json()
                call = {
                    "type": "create-call",
                    "requestKey": "test-call-0001",
                    "pickupName": "Care home",
                    "destinationName": "Hospital",
                    "pickup": [42.73, -73.68],
                    "destination": [42.74, -73.67],
                    "pickupInMinutes": 0,
                }
                response = client.post("/transport/action", json=call)
                self.assertEqual(response.status_code, 200)
                result = response.json()
                self.assertEqual(len(result["trips"]), 3)
                self.assertEqual(
                    len(client.post("/transport/action", json=call).json()["trips"]), 3
                )
                self.assertEqual(
                    client.post(
                        "/transport/action", json={**call, "pickupName": "Changed"}
                    ).status_code,
                    400,
                )
                self.assertEqual(
                    client.post(
                        "/transport/action",
                        json={
                            **call,
                            "requestKey": "invalid-coordinate",
                            "pickup": [91, 0],
                        },
                    ).status_code,
                    422,
                )
                report = {
                    "type": "report-status",
                    "vehicleId": "V1",
                    "status": "unavailable",
                    "observedAt": "2026-11-08T01:00:00Z",
                }
                result = client.post("/transport/action", json=report).json()
                self.assertTrue(result["vehicles"][0]["dispatchUnavailable"])
                self.assertNotIn("tripId", result["vehicles"][0])
                self.assertEqual(
                    client.post("/transport/action", json=report).status_code, 400
                )
                self.assertEqual(
                    client.post(
                        "/transport/action",
                        json={
                            **report,
                            "status": "available",
                            "observedAt": "2026-11-08T01:00:01Z",
                        },
                    ).status_code,
                    200,
                )
                assigned = [
                    v["tripId"]
                    for v in client.get("/transport/state").json()["vehicles"]
                    if v.get("tripId")
                ]
                self.assertEqual(len(assigned), len(set(assigned)))
                self.assertEqual(
                    client.post(
                        "/transport/action",
                        json={
                            **report,
                            "status": "available",
                            "observedAt": "2026-11-08T01:00:02Z",
                        },
                    ).status_code,
                    400,
                )
            restarted = DispatchService(Roads(), StateStore(path), seed()).snapshot()
            self.assertEqual(len(restarted["trips"]), 3)
            self.assertEqual(restarted["vehicles"][0]["reportedStatus"], "available")


if __name__ == "__main__":
    unittest.main()
