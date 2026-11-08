"""Deterministic rolling dispatch and road-timed simulation, independent of HTTP/SQL."""

from copy import deepcopy
import math
from .road_times import NoRoute, RoutingUnavailable
from .diagnostics import plan_comparison
from .active_work import account_work
from .service_times import LOAD_MINUTES, HANDOFF_MINUTES, RESET_MINUTES

UNREACHABLE = 1e12


def minimum_assignment(costs):
    """Hungarian assignment: rows <= columns, minimum total cost, O(n^2*m)."""
    if not costs:
        return []
    n, m = len(costs), len(costs[0])
    u, v, p, way = [0.0] * (n + 1), [0.0] * (m + 1), [0] * (m + 1), [0] * (m + 1)
    for i in range(1, n + 1):
        p[0], j0 = i, 0
        minimum, used = [math.inf] * (m + 1), [False] * (m + 1)
        while True:
            used[j0] = True
            i0, delta, j1 = p[j0], math.inf, 0
            for j in range(1, m + 1):
                if not used[j]:
                    current = costs[i0 - 1][j - 1] - u[i0] - v[j]
                    if current < minimum[j]:
                        minimum[j], way[j] = current, j0
                    if minimum[j] < delta:
                        delta, j1 = minimum[j], j
            for j in range(m + 1):
                if used[j]:
                    u[p[j]] += delta
                    v[j] -= delta
                else:
                    minimum[j] -= delta
            j0 = j1
            if p[j0] == 0:
                break
        while j0:
            j1 = way[j0]
            p[j0] = p[j1]
            j0 = j1
    result = [-1] * n
    for j in range(1, m + 1):
        if p[j]:
            result[p[j] - 1] = j - 1
    return result


def pickup(trip):
    return trip.get("transferLocation", trip["pickup"])


def multiplier(state, vehicle):
    return (2 if state["traffic"] else 1) * state.get("trafficFactors", {}).get(
        vehicle["id"], 1
    )


def event(state, message):
    state["events"] = [
        f'{state["minute"]:.1f} min Ãƒâ€šÃ‚Â· {message}',
        *state["events"],
    ][:30]


def history(state, trip, old, new, reason):
    if old == new:
        return
    change = {"tripId": trip["id"], "minute": state["minute"], "reason": reason}
    if old:
        change["fromVehicleId"] = old
    if new:
        change["toVehicleId"] = new
    state["assignmentHistory"] = [*state.get("assignmentHistory", []), change][-500:]


def set_route(vehicle, route):
    vehicle["route"] = deepcopy(route["points"])
    vehicle["_times"] = route["times"][:]
    vehicle["routeIndex"] = 0
    vehicle["_segmentElapsed"] = 0
    vehicle["position"] = vehicle["route"][0][:]
    vehicle["movementPath"] = [vehicle["position"][:]]
    vehicle["movementTimes"] = [0.0]


def clear_route(vehicle):
    for key in ("route", "routeIndex", "_times", "_segmentElapsed"):
        vehicle.pop(key, None)


def remaining(vehicle):
    return max(
        0,
        sum(vehicle.get("_times", [])[vehicle.get("routeIndex", 0) :])
        - vehicle.get("_segmentElapsed", 0),
    )


def update_etas(state):
    units = {v["id"]: v for v in state["vehicles"]}
    for trip in state["trips"]:
        vehicle = units.get(trip.get("vehicleId"))
        trip["etaMinute"] = None
        if trip["status"] == "complete":
            trip["etaMinute"] = trip["completedAt"]
        elif vehicle and not vehicle["outOfService"]:
            arrival = max(state["minute"], vehicle["holdUntil"]) + remaining(
                vehicle
            ) * multiplier(state, vehicle)
            trip["etaMinute"] = (
                max(arrival, trip["scheduled"])
                if trip["status"] == "pickup"
                else arrival
            )


def replan(state, router, reason):
    """Commit a whole plan only after all required routing succeeds."""
    next_state = deepcopy(state)
    trips = next_state["trips"]
    locked = {t.get("vehicleId") for t in trips if t["status"] == "onboard"}
    units = sorted(
        (
            v
            for v in next_state["vehicles"]
            if not v["outOfService"]
            and not v.get("dispatchUnavailable")
            and v["id"] not in locked
            and "resetUntil" not in v
        ),
        key=lambda v: v["id"],
    )
    for vehicle in units:
        # Waiting for an old appointment is not a crew availability constraint.
        if vehicle["holdReason"] == "Waiting at pickup":
            vehicle["holdUntil"], vehicle["holdReason"] = next_state["minute"], ""
    pending = sorted(
        (t for t in trips if t["status"] in {"waiting", "pickup", "transfer"}),
        key=lambda t: (0 if "transferLocation" in t else 1, t["scheduled"], t["id"]),
    )
    assignments = {}
    selected, costs = [], []
    if units and pending:
        # Batch all pickup candidates; null pairs are genuinely unreachable.
        times = router.matrix(
            [v["position"] for v in units], [pickup(t) for t in pending]
        )
        reachable = [
            j for j in range(len(pending)) if any(row[j] is not None for row in times)
        ]
        indices = reachable[: len(units)]
        selected = [pending[j] for j in indices]
        costs = [
            [
                (
                    UNREACHABLE
                    if times[i][j] is None
                    else max(next_state["minute"], vehicle["holdUntil"])
                    + times[i][j] * multiplier(next_state, vehicle)
                )
                for i, vehicle in enumerate(units)
            ]
            for j in indices
        ]
        for row, column in enumerate(minimum_assignment(costs)):
            if costs[row][column] >= UNREACHABLE:
                continue
            trip, vehicle = selected[row], units[column]
            try:
                approach = router.route(vehicle["position"], pickup(trip))
                delivery = router.route(pickup(trip), trip["destination"])
            except NoRoute:
                continue
            assignments[trip["id"]] = (vehicle, approach, delivery)
    comparison = plan_comparison(
        next_state, selected, units, costs, assignments, reason
    )
    next_state["planDiagnostics"] = comparison
    next_state["planDiagnosticsHistory"] = [
        *next_state.get("planDiagnosticsHistory", []),
        {
            key: value
            for key, value in comparison.items()
            if key not in {"trips", "basis"}
        },
    ][-50:]
    for vehicle in units:
        vehicle.pop("tripId", None)
        clear_route(vehicle)
    for trip in pending:
        old = trip.pop("vehicleId", None)
        assignment = assignments.get(trip["id"])
        if assignment:
            vehicle, approach, delivery = assignment
            trip["vehicleId"], vehicle["tripId"] = vehicle["id"], trip["id"]
            trip["status"] = "pickup"
            trip.setdefault("dispatchStartedAt", next_state["minute"])
            trip["serviceStage"] = "Drive to pickup"
            trip["transportRoute"], trip["_delivery"] = delivery["points"], delivery
            set_route(vehicle, approach)
        else:
            trip["status"] = "transfer" if "transferLocation" in trip else "waiting"
        history(next_state, trip, old, trip.get("vehicleId"), reason)
    next_state["dispatch"] = {
        "status": "ready",
        "message": reason,
        "algorithm": "Minimum total pickup arrival time for next scheduled wave",
        "routingSource": "OSRM road-profile estimates; no live traffic",
        "lastPlannedMinute": next_state["minute"],
    }
    update_etas(next_state)
    event(next_state, f"Dispatch recalculated: {reason}")
    state.clear()
    state.update(next_state)


def safe_replan(state, router, reason):
    try:
        replan(state, router, reason)
    except RoutingUnavailable as exc:
        state["dispatch"] = {
            "status": "routing-unavailable",
            "message": str(exc),
            "routingSource": "OSRM road-profile estimates; no live traffic",
        }
        event(
            state,
            "Replanning unavailable. Existing valid assignments retained; retry pending.",
        )
        update_etas(state)


def action(state, payload, router):
    """Disruptions are retained even when the road provider is unavailable."""
    s = deepcopy(state)
    kind = payload["type"]
    if kind == "reoptimize":
        safe_replan(s, router, "Dispatcher requested a new plan")
        return s
    if kind == "traffic":
        s["traffic"] = payload["enabled"]
    elif kind == "traffic-update":
        vehicle_id = payload["vehicleId"]
        if not any(v["id"] == vehicle_id for v in s["vehicles"]):
            raise ValueError("Vehicle not found")
        s.setdefault("trafficFactors", {})[vehicle_id] = payload["factor"]
    else:
        vehicle = next(
            (v for v in s["vehicles"] if v["id"] == payload["vehicleId"]), None
        )
        if vehicle is None:
            raise ValueError("Vehicle not found")
        if kind in {"delay", "emergency"}:
            if vehicle["outOfService"]:
                raise ValueError("Return this ambulance to service first")
            vehicle["holdUntil"] = max(s["minute"], vehicle["holdUntil"]) + (
                10 if kind == "delay" else 15
            )
            vehicle["holdReason"] = (
                "Crew delay" if kind == "delay" else "Emergency hold"
            )
        elif kind == "outage":
            vehicle["outOfService"] = True
            trip = next(
                (t for t in s["trips"] if t["id"] == vehicle.get("tripId")), None
            )
            if trip and trip["status"] == "complete":
                # A post-handoff breakdown must never queue the patient again.
                safe_replan(s, router, "Outage during vehicle reset")
                return s
            if trip:
                if trip["status"] == "onboard":
                    trip["transferLocation"] = vehicle["position"][:]
                trip["status"] = "transfer" if "transferLocation" in trip else "waiting"
                trip["serviceStage"] = "Waiting for replacement"
                history(
                    s,
                    trip,
                    trip.pop("vehicleId", None),
                    None,
                    "Ambulance out of service",
                )
            vehicle.pop("tripId", None)
            vehicle.pop("unloadingUntil", None)
            clear_route(vehicle)
            vehicle["movementPath"] = [vehicle["position"][:]]
            vehicle["movementTimes"] = [s["minute"]]
            vehicle["holdUntil"], vehicle["holdReason"] = s["minute"], ""
        elif kind == "restore":
            vehicle["outOfService"] = False
        elif kind == "assign":
            trip = next((t for t in s["trips"] if t["id"] == payload["tripId"]), None)
            if not trip or trip["status"] not in {"waiting", "transfer"}:
                raise ValueError("Trip cannot be manually assigned")
            if (
                vehicle["outOfService"]
                or vehicle.get("tripId")
                or vehicle["holdUntil"] > s["minute"]
            ):
                raise ValueError("Choose an available ambulance")
            approach = router.route(vehicle["position"], pickup(trip))
            delivery = router.route(pickup(trip), trip["destination"])
            history(s, trip, None, vehicle["id"], "Manual assignment")
            trip["vehicleId"], vehicle["tripId"] = vehicle["id"], trip["id"]
            trip["status"] = "pickup"
            trip.setdefault("dispatchStartedAt", s["minute"])
            trip["serviceStage"] = "Drive to pickup"
            trip["transportRoute"], trip["_delivery"] = delivery["points"], delivery
            set_route(vehicle, approach)
            update_etas(s)
            return s
        else:
            raise ValueError("Unsupported action")
    safe_replan(s, router, f"Automatic replan after {kind}")
    return s


def travel(vehicle, minutes, started_at=0.0, factor=1.0):
    elapsed = 0.0
    route, times = vehicle["route"], vehicle["_times"]
    index = vehicle["routeIndex"]
    while index < len(times):
        left = max(0, times[index] - vehicle["_segmentElapsed"])
        if minutes + 1e-10 >= left:
            minutes = max(0.0, minutes - left)
            elapsed += left * factor
            index += 1
            vehicle["_segmentElapsed"] = 0
            vehicle["position"] = route[index][:]
            vehicle["movementPath"].append(vehicle["position"][:])
            vehicle["movementTimes"].append(
                max(vehicle["movementTimes"][-1], started_at + elapsed)
            )
        else:
            elapsed += minutes * factor
            vehicle["_segmentElapsed"] += minutes
            fraction = vehicle["_segmentElapsed"] / times[index]
            vehicle["position"] = [
                a + (b - a) * fraction for a, b in zip(route[index], route[index + 1])
            ]
            vehicle["movementPath"].append(vehicle["position"][:])
            vehicle["movementTimes"].append(
                max(vehicle["movementTimes"][-1], started_at + elapsed)
            )
            break
    vehicle["routeIndex"] = index
    return index == len(times)


def advance(state, minutes, router):
    s = deepcopy(state)
    end = s["minute"] + minutes
    for vehicle in s["vehicles"]:
        vehicle["movementPath"] = [vehicle["position"][:]]
        vehicle["movementTimes"] = [s["minute"]]
    completed = False
    # Small steps keep pickup waiting and loading consistent across polling rates.
    while s["minute"] < end - 1e-9:
        dt = min(1 / 60, end - s["minute"])
        s["minute"] += dt
        for vehicle in s["vehicles"]:
            account_work(s, vehicle, dt)
            if (
                vehicle["outOfService"]
                or not vehicle.get("tripId")
                or vehicle["holdUntil"] > s["minute"] + 1e-9
            ):
                vehicle["movementPath"].append(vehicle["position"][:])
                vehicle["movementTimes"].append(s["minute"])
                continue
            trip = next(t for t in s["trips"] if t["id"] == vehicle["tripId"])
            if "resetUntil" in vehicle:
                if s["minute"] + 1e-9 >= vehicle["resetUntil"]:
                    trip["availableAt"] = s["minute"]
                    trip["serviceStage"] = "Available / cycle finished"
                    vehicle.pop("tripId")
                    vehicle.pop("resetUntil")
                    vehicle["holdUntil"], vehicle["holdReason"] = s["minute"], ""
                    completed = True
                    event(s, f'{vehicle["id"]} finished reset and is available')
                continue
            if "unloadingUntil" in vehicle:
                if s["minute"] + 1e-9 >= vehicle["unloadingUntil"]:
                    trip["status"], trip["completedAt"] = "complete", s["minute"]
                    vehicle.pop("unloadingUntil")
                    clear_route(vehicle)
                    vehicle["resetUntil"] = s["minute"] + RESET_MINUTES
                    vehicle["holdUntil"] = vehicle["resetUntil"]
                    vehicle["holdReason"] = "Reset and become available"
                    trip["serviceStage"] = "Reset and become available"
                    event(
                        s, f'{trip["id"]} handoff complete; {vehicle["id"]} resetting'
                    )
                continue
            if not vehicle.get("route"):
                continue
            if (
                trip["status"] == "onboard"
                and trip.get("serviceStage") == "Prepare and load patient"
            ):
                trip["departedPickupAt"] = s["minute"]
                trip["serviceStage"] = "Drive to destination"
            factor = multiplier(s, vehicle)
            arrived = travel(vehicle, dt / factor, s["minute"] - dt, factor)
            if not arrived:
                continue
            if trip["status"] == "pickup":
                trip.setdefault("pickupArrivalAt", s["minute"])
                if (
                    s["minute"] < trip["scheduled"] - 1e-9
                    and "transferLocation" not in trip
                ):
                    vehicle["holdUntil"], vehicle["holdReason"] = (
                        trip["scheduled"],
                        "Waiting at pickup",
                    )
                    continue
                trip.setdefault("actualPickup", s["minute"])
                trip["loadingStartedAt"] = s["minute"]
                trip["serviceStage"] = "Prepare and load patient"
                trip["status"] = "onboard"
                trip.pop("transferLocation", None)
                path, timestamps = vehicle["movementPath"], vehicle["movementTimes"]
                set_route(vehicle, trip["_delivery"])
                vehicle["movementPath"], vehicle["movementTimes"] = path, timestamps
                vehicle["loadingUntil"] = s["minute"] + LOAD_MINUTES
                vehicle["holdUntil"], vehicle["holdReason"] = (
                    s["minute"] + LOAD_MINUTES,
                    "Prepare and load patient",
                )
                event(s, f'{vehicle["id"]} picked up {trip["id"]}')
            elif trip["status"] == "onboard":
                trip["destinationArrivalAt"] = s["minute"]
                trip["serviceStage"] = "Unload, handoff and paperwork"
                vehicle["unloadingUntil"] = s["minute"] + HANDOFF_MINUTES
                vehicle["holdUntil"], vehicle["holdReason"] = (
                    s["minute"] + HANDOFF_MINUTES,
                    "Unload, handoff and paperwork",
                )
    for vehicle in s["vehicles"]:
        vehicle["movementPath"].append(vehicle["position"][:])
        vehicle["movementTimes"].append(max(end, vehicle["movementTimes"][-1]))
    s["minute"] = end
    if completed:
        safe_replan(s, router, "Ambulance became available")
    update_etas(s)
    return s


def public_snapshot(state):
    """Do not expose internal segment caches or state implementation details."""

    def clean(value):
        if isinstance(value, dict):
            return {k: clean(v) for k, v in value.items() if not k.startswith("_")}
        if isinstance(value, list):
            return [clean(v) for v in value]
        return value

    return clean(state)
