import tempfile
from pathlib import Path
import unittest
from fastapi.testclient import TestClient
from .test_dispatch import Roads, seed
from .dispatch_engine import replan, safe_replan
from .diagnostics import live_diagnostics
from .transport_api import DispatchService, StateStore, create_app


class DiagnosticsTests(unittest.TestCase):
    def test_same_matrix_savings_and_no_double_counting(self):
        s = seed()
        roads = Roads({(1, 11): 1, (2, 11): 2, (1, 12): 2, (2, 12): 100})
        replan(s, roads, "test")
        plan = s["planDiagnostics"]
        self.assertEqual(plan["baselineMinutes"], 101)
        self.assertEqual(plan["optimizedMinutes"], 4)
        self.assertEqual(plan["estimatedMinutesSaved"], 97)
        replan(s, roads, "repeat")
        self.assertEqual(s["planDiagnostics"]["estimatedMinutesSaved"], 97)
        self.assertEqual(len(s["planDiagnosticsHistory"]), 2)
        roads.failed = True
        safe_replan(s, roads, "failure")
        self.assertEqual(s["dispatch"]["status"], "routing-unavailable")
        self.assertEqual(s["planDiagnostics"]["reason"], "repeat")

    def test_incomparable_plan_does_not_claim_savings(self):
        s = seed()
        # Greedy consumes V1 for T1 and cannot serve T2; optimized can serve both.
        replan(s, Roads({(1, 11): 1, (2, 11): 2, (1, 12): 3, (2, 12): None}), "test")
        self.assertFalse(s["planDiagnostics"]["comparable"])
        self.assertIsNone(s["planDiagnostics"]["estimatedMinutesSaved"])

    def test_observed_metrics_include_on_time_pickups(self):
        s = seed()
        s["trips"][0]["actualPickup"] = 0
        s["trips"][1]["actualPickup"] = 4
        metrics = live_diagnostics(s, 15)["metrics"]
        self.assertEqual(metrics["averagePickupDelayMinutes"], 2)
        self.assertEqual(metrics["onTimePickups"], 1)
        self.assertEqual(metrics["pickedUp"], 2)

    def test_page_and_read_only_endpoint_and_persistence(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "test.sqlite3"
            service = DispatchService(Roads(), StateStore(path), seed())
            service.reset()
            before = service.snapshot()
            with TestClient(create_app(service, speed=0)) as client:
                page = client.get("/debug")
                self.assertEqual(page.status_code, 200)
                self.assertIn("text/html", page.headers["content-type"])
                self.assertIn("75-minute full transport-cycle benchmark", page.text)
                data = client.get("/transport/diagnostics").json()
                self.assertEqual(len(data["trips"]), 2)
                self.assertTrue(data["latestPlan"]["comparable"])
                self.assertEqual(service.snapshot(), before)
            restarted = DispatchService(Roads(), StateStore(path), seed())
            self.assertEqual(
                restarted.snapshot()["planDiagnostics"], before["planDiagnostics"]
            )


if __name__ == "__main__":
    unittest.main()
