import itertools
import json
from pathlib import Path
import tempfile
import unittest

from fastapi.testclient import TestClient
from .dispatch_engine import (
    action,
    advance,
    minimum_assignment,
    public_snapshot,
    replan,
    safe_replan,
)
from .road_times import RoadRouter, RoutingUnavailable
from .transport_api import DispatchService, StateStore, create_app


class Roads:
    def __init__(self, times=None):
        self.times = times or {}
        self.failed = False

    def duration(self, a, b):
        return self.times.get((a[0], b[0]), 2)

    def matrix(self, origins, targets):
        if self.failed:
            raise RoutingUnavailable("Road provider offline")
        return [[self.duration(a, b) for b in targets] for a in origins]

    def route(self, a, b):
        if self.failed:
            raise RoutingUnavailable("Road provider offline")
        duration = self.duration(a, b)
        return {
            "points": [a[:], [(a[0] + b[0]) / 2, b[1]], b[:]],
            "times": [duration / 4, duration * 3 / 4],
            "minutes": duration,
        }


def seed():
    return {
        "minute": 0,
        "traffic": False,
        "events": [],
        "assignmentHistory": [],
        "vehicles": [
            {
                "id": f"V{i}",
                "crew": f"Crew {i}",
                "position": [i, 0],
                "outOfService": False,
                "holdUntil": 0,
                "holdReason": "",
            }
            for i in (1, 2)
        ],
        "trips": [
            {
                "id": f"T{i}",
                "from": "Pickup",
                "to": "Drop-off",
                "pickup": [i + 10, 0],
                "destination": [i + 20, 0],
                "scheduled": 0,
                "status": "waiting",
            }
            for i in (1, 2)
        ],
    }


class DispatchTests(unittest.TestCase):
    def test_assignment_matches_exhaustive_optimum(self):
        for costs in ([[1, 2], [2, 100]], [[4, 1, 8], [3, 6, 2]], [[7, 7], [7, 7]]):
            assignment = minimum_assignment(costs)
            score = sum(row[column] for row, column in zip(costs, assignment))
            best = min(
                sum(costs[i][column] for i, column in enumerate(p))
                for p in itertools.permutations(range(len(costs[0])), len(costs))
            )
            self.assertEqual(score, best)

    def test_faster_road_time_beats_distance_and_greedy(self):
        s = seed()
        router = Roads({(1, 11): 1, (2, 11): 2, (1, 12): 2, (2, 12): 100})
        replan(s, router, "test")
        self.assertEqual([t["vehicleId"] for t in s["trips"]], ["V2", "V1"])
        self.assertEqual([t["etaMinute"] for t in s["trips"]], [2, 2])

    def test_delay_traffic_and_restore_recalculate(self):
        s = seed()
        s["trips"] = s["trips"][:1]
        router = Roads({(1, 11): 2, (2, 11): 4})
        replan(s, router, "test")
        delayed = action(s, {"type": "delay", "vehicleId": "V1"}, router)
        self.assertEqual(delayed["trips"][0]["vehicleId"], "V2")
        traffic = action(
            s, {"type": "traffic-update", "vehicleId": "V1", "factor": 3}, router
        )
        self.assertEqual(traffic["trips"][0]["vehicleId"], "V2")
        restored = action(
            traffic, {"type": "traffic-update", "vehicleId": "V1", "factor": 1}, router
        )
        self.assertEqual(restored["trips"][0]["vehicleId"], "V1")
        outage = action(s, {"type": "outage", "vehicleId": "V1"}, router)
        self.assertEqual(outage["trips"][0]["vehicleId"], "V2")
        self.assertNotIn("tripId", outage["vehicles"][0])

    def test_onboard_locked_then_breakdown_transfers_from_patient_location(self):
        s = seed()
        s["trips"] = s["trips"][:1]
        router = Roads()
        replan(s, router, "test")
        s = advance(s, 2.1, router)
        self.assertEqual(s["trips"][0]["status"], "onboard")
        original = s["trips"][0]["vehicleId"]
        held = action(s, {"type": "delay", "vehicleId": original}, router)
        self.assertEqual(held["trips"][0]["vehicleId"], original)
        broken = action(s, {"type": "outage", "vehicleId": original}, router)
        trip = broken["trips"][0]
        stopped = next(v for v in s["vehicles"] if v["id"] == original)
        self.assertEqual(trip["transferLocation"], stopped["position"])
        self.assertNotEqual(trip["vehicleId"], original)
        self.assertEqual(trip["actualPickup"], s["trips"][0]["actualPickup"])
        self.assertEqual(trip["transportRoute"][0], stopped["position"])
        done = advance(broken, 60, router)
        self.assertEqual(done["trips"][0]["status"], "complete")

    def test_failed_replan_retains_safe_state_and_can_retry(self):
        s = seed()
        router = Roads()
        replan(s, router, "test")
        router.failed = True
        broken = action(s, {"type": "outage", "vehicleId": "V1"}, router)
        self.assertEqual(broken["dispatch"]["status"], "routing-unavailable")
        self.assertNotIn("tripId", broken["vehicles"][0])
        self.assertTrue(broken["vehicles"][0]["outOfService"])
        self.assertTrue(any(t["status"] == "waiting" for t in broken["trips"]))
        router.failed = False
        safe_replan(broken, router, "retry")
        self.assertEqual(broken["dispatch"]["status"], "ready")

    def test_no_duplicate_assignments_and_unreachable_stays_unassigned(self):
        s = seed()
        router = Roads({(1, 11): None, (2, 11): None})
        replan(s, router, "test")
        self.assertEqual(s["trips"][0]["status"], "waiting")
        ids = [t["vehicleId"] for t in s["trips"] if "vehicleId" in t]
        self.assertEqual(len(ids), len(set(ids)))

    def test_segment_speed_and_traffic_affect_motion(self):
        s = seed()
        s["trips"] = s["trips"][:1]
        router = Roads({(1, 11): 4, (2, 11): 9})
        replan(s, router, "test")
        moving = advance(s, 0.5, router)
        self.assertAlmostEqual(moving["vehicles"][0]["position"][0], 3.5)
        s["traffic"] = True
        slow = advance(s, 0.5, router)
        self.assertAlmostEqual(slow["vehicles"][0]["position"][0], 2.25)
        self.assertNotIn("_times", public_snapshot(s)["vehicles"][0])

    def test_movement_timestamps_preserve_segment_speeds_and_holds(self):
        from .dispatch_engine import set_route, travel

        vehicle = seed()["vehicles"][0]
        set_route(vehicle, {"points": [[0, 0], [1, 0], [2, 0]], "times": [0.2, 0.15]})
        travel(vehicle, 0.35, started_at=0, factor=1)
        self.assertAlmostEqual(vehicle["movementTimes"][1], 0.2)
        self.assertAlmostEqual(vehicle["movementTimes"][2], 0.35)
        s = seed()
        router = Roads()
        replan(s, router, "test")
        s["vehicles"][0]["holdUntil"] = 0.1
        s["vehicles"][0]["holdReason"] = "Crew delay"
        s = advance(s, 0.25, router)
        for unit in s["vehicles"]:
            times = unit["movementTimes"]
            self.assertEqual(len(times), len(unit["movementPath"]))
            self.assertTrue(all(a <= b for a, b in zip(times, times[1:])))
            self.assertAlmostEqual(times[-1], 0.25)
        self.assertEqual(
            s["vehicles"][0]["movementPath"][0], s["vehicles"][0]["movementPath"][1]
        )

    def test_completion_dispatches_next_waiting_trip(self):
        s = seed()
        s["vehicles"] = s["vehicles"][:1]
        router = Roads()
        replan(s, router, "test")
        s = advance(s, 56.2, router)
        self.assertEqual(s["trips"][0]["status"], "complete")
        self.assertEqual(s["trips"][1]["vehicleId"], "V1")

    def test_sql_restart_api_actions_and_validation(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "state.sqlite3"
            service = DispatchService(Roads(), StateStore(path), seed())
            with TestClient(create_app(service, speed=0)) as client:
                initial = client.get("/transport/state").json()
                self.assertEqual(len(initial["vehicles"]), 2)
                response = client.post(
                    "/transport/action", json={"type": "outage", "vehicleId": "V1"}
                )
                self.assertEqual(response.status_code, 200)
                self.assertTrue(response.json()["vehicles"][0]["outOfService"])
                self.assertEqual(
                    client.post(
                        "/transport/action",
                        json={
                            "type": "traffic-update",
                            "vehicleId": "V2",
                            "factor": -1,
                        },
                    ).status_code,
                    422,
                )
                self.assertEqual(
                    client.post(
                        "/transport/action", json={"type": "advance", "minutes": 5}
                    ).status_code,
                    400,
                )
                self.assertEqual(
                    client.post(
                        "/transport/action",
                        json={"type": "outage", "vehicleId": "missing"},
                    ).status_code,
                    400,
                )
                restarted = DispatchService(Roads(), StateStore(path), seed())
                self.assertTrue(restarted.snapshot()["vehicles"][0]["outOfService"])
                reset = client.post("/transport/reset", json={}).json()
                self.assertFalse(reset["vehicles"][0]["outOfService"])

    def test_osrm_parser_converts_seconds_and_includes_turn_costs(self):
        router = RoadRouter()
        router._get = lambda path: {
            "routes": [
                {
                    "duration": 90,
                    "geometry": {"coordinates": [[0, 1], [0, 2], [0, 3]]},
                    "legs": [{"annotation": {"duration": [20, 40]}}],
                }
            ]
        }
        route = router.route([1, 0], [3, 0])
        self.assertEqual(route["times"], [0.5, 1.0])
        self.assertEqual(route["points"], [[1, 0], [2, 0], [3, 0]])


if __name__ == "__main__":
    unittest.main()
