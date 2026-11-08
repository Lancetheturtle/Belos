import tempfile
import time
import unittest
from pathlib import Path
from fastapi.testclient import TestClient
from .test_dispatch import seed, Roads
from .transport_api import create_app, DispatchService, StateStore


class SpeedTests(unittest.TestCase):
    def test_runtime_speed_changes_clock_without_resetting_shift(self):
        with tempfile.TemporaryDirectory() as directory:
            service = DispatchService(
                Roads(), StateStore(Path(directory) / "state.sqlite3"), seed()
            )
            with TestClient(create_app(service, speed=0)) as client:
                initial = client.get("/transport/state").json()
                response = client.post(
                    "/transport/action", json={"type": "set-speed", "speed": 60}
                )
                self.assertEqual(response.status_code, 200)
                updated = response.json()
                self.assertEqual(updated["simulationSpeed"], 60)
                self.assertEqual(updated["minute"], initial["minute"])
                self.assertEqual(updated["trips"], initial["trips"])
                self.assertEqual(client.get("/health").json()["simulationSpeed"], 60)
                self.assertEqual(
                    client.get("/transport/diagnostics").json()["simulationSpeed"], 60
                )
                deadline = time.monotonic() + 4
                while (
                    client.get("/transport/state").json()["minute"] < 1
                    and time.monotonic() < deadline
                ):
                    time.sleep(0.05)
                self.assertGreaterEqual(
                    client.get("/transport/state").json()["minute"], 1
                )
                self.assertEqual(
                    client.post("/transport/reset", json={}).json()["simulationSpeed"],
                    60,
                )
                for invalid in [0, 61, 1.5, "60", True]:
                    self.assertEqual(
                        client.post(
                            "/transport/action",
                            json={"type": "set-speed", "speed": invalid},
                        ).status_code,
                        422,
                    )
                self.assertEqual(
                    client.post(
                        "/transport/action", json={"type": "set-speed", "speed": 1}
                    ).json()["simulationSpeed"],
                    1,
                )


if __name__ == "__main__":
    unittest.main()
