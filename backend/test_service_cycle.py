import unittest
from .test_dispatch import seed, Roads
from .dispatch_engine import replan, advance, action
from .service_times import MODEL, BENCHMARK, cycle_metrics


class ServiceCycleTests(unittest.TestCase):
    def setup_cycle(self):
        s = seed()
        s["serviceModel"] = MODEL
        s["vehicles"] = s["vehicles"][:1]
        s["trips"] = s["trips"][:1]
        router = Roads({(1, 11): 8, (11, 21): 15})
        replan(s, router, "benchmark test")
        return s, router

    def test_all_five_stages_total_75_and_no_early_availability(self):
        self.assertEqual(sum(stage["minutes"] for stage in BENCHMARK), 75)
        s, router = self.setup_cycle()
        for moment, stage in [
            (8.1, "Prepare and load patient"),
            (23.1, "Drive to destination"),
            (38.1, "Unload, handoff and paperwork"),
            (70.1, "Reset and become available"),
        ]:
            s = advance(s, moment - s["minute"], router)
            self.assertEqual(s["trips"][0]["serviceStage"], stage)
            self.assertEqual(s["vehicles"][0]["tripId"], "T1")
            self.assertNotIn("availableAt", s["trips"][0])
        replan(s, router, "reset must remain locked")
        self.assertEqual(s["vehicles"][0]["tripId"], "T1")
        self.assertIn("resetUntil", s["vehicles"][0])
        s = advance(s, 5.1, router)
        self.assertNotIn("tripId", s["vehicles"][0])
        trip = s["trips"][0]
        self.assertAlmostEqual(
            trip["availableAt"] - trip["dispatchStartedAt"], 75, delta=0.05
        )
        self.assertAlmostEqual(
            trip["departedPickupAt"] - trip["loadingStartedAt"], 15, delta=0.05
        )
        self.assertAlmostEqual(
            trip["completedAt"] - trip["destinationArrivalAt"], 32, delta=0.05
        )
        self.assertAlmostEqual(trip["availableAt"] - trip["completedAt"], 5, delta=0.05)
        metrics = cycle_metrics(s)
        self.assertEqual(metrics["completedCycles"], 1)
        self.assertAlmostEqual(metrics["averageMinutesBelowBenchmark"], 0, delta=0.05)

    def test_breakdown_during_reset_does_not_requeue_completed_patient(self):
        s, router = self.setup_cycle()
        s = advance(s, 70.1, router)
        s = action(s, {"type": "outage", "vehicleId": "V1"}, router)
        s = advance(s, 10, router)
        self.assertEqual(s["trips"][0]["status"], "complete")
        self.assertNotIn("transferLocation", s["trips"][0])
        self.assertNotIn("availableAt", s["trips"][0])
        s = action(s, {"type": "restore", "vehicleId": "V1"}, router)
        s = advance(s, 0.1, router)
        self.assertGreater(s["trips"][0]["availableAt"], 80)

    def test_scheduled_wait_and_idle_between_jobs_do_not_inflate_active_work(self):
        s, router = self.setup_cycle()
        s["trips"][0]["scheduled"] = 50
        s = advance(s, 119, router)
        metrics = cycle_metrics(s)
        self.assertAlmostEqual(metrics["averageActualCycleMinutes"], 75, delta=0.1)
        row = metrics["cycles"][0]
        self.assertGreater(row["elapsedCycleMinutes"], 116)
        self.assertGreater(row["excludedWaitingMinutes"], 41)
        active = row["actualCycleMinutes"]
        s = advance(s, 50, router)
        self.assertEqual(cycle_metrics(s)["cycles"][0]["actualCycleMinutes"], active)

    def test_total_savings_counts_each_finished_cycle_once_including_losses(self):
        state = {'serviceModel': MODEL, 'trips': [
            {'id': 'A', 'status': 'complete', 'dispatchStartedAt': 0, 'availableAt': 90, 'activeWorkMinutes': 60},
            {'id': 'B', 'status': 'complete', 'dispatchStartedAt': 0, 'availableAt': 100, 'activeWorkMinutes': 80},
            {'id': 'C', 'status': 'onboard', 'dispatchStartedAt': 0, 'activeWorkMinutes': 10},
        ]}
        self.assertEqual(cycle_metrics(state)['totalMinutesSaved'], 10)
        self.assertEqual(cycle_metrics(state)['completedCycles'], 2)
        self.assertEqual(cycle_metrics(state)['totalMinutesSaved'], 10)
        state.pop('serviceModel')
        self.assertIsNone(cycle_metrics(state)['totalMinutesSaved'])

    def test_old_shifts_and_waits_are_excluded_from_active_cycle(self):
        s, router = self.setup_cycle()
        s = action(s, {"type": "delay", "vehicleId": "V1"}, router)
        s = advance(s, 86, router)
        self.assertAlmostEqual(
            cycle_metrics(s)["averageActualCycleMinutes"], 75, delta=0.05
        )
        s.pop("serviceModel")
        self.assertIsNone(cycle_metrics(s)["averageActualCycleMinutes"])
        self.assertFalse(cycle_metrics(s)["compatibleShift"])


if __name__ == "__main__":
    unittest.main()
