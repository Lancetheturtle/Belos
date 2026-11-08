"""Count work intervals; a stationary service stage is still productive time."""


def account_work(state, vehicle, dt):
    if not vehicle.get("tripId") or vehicle["outOfService"]:
        return
    trip = next(t for t in state["trips"] if t["id"] == vehicle["tripId"])
    start = state["minute"] - dt
    stage = trip.get("serviceStage", "")
    deadline = None
    if "resetUntil" in vehicle:
        stage, deadline = "Reset and become available", vehicle["resetUntil"]
    elif "unloadingUntil" in vehicle:
        stage, deadline = "Unload, handoff and paperwork", vehicle["unloadingUntil"]
    elif stage == "Prepare and load patient":
        deadline = vehicle.get("loadingUntil")
    if deadline is not None:
        work = max(0.0, min(dt, deadline - start))
    elif vehicle["holdUntil"] > state["minute"] + 1e-9 or not vehicle.get("route"):
        work = 0.0
    else:
        times = vehicle.get("_times", [])
        left = max(
            0.0,
            sum(times[vehicle.get("routeIndex", 0) :])
            - vehicle.get("_segmentElapsed", 0),
        )
        factor = (2 if state["traffic"] else 1) * state.get("trafficFactors", {}).get(
            vehicle["id"], 1
        )
        work = min(dt, left * factor)
    trip["activeWorkMinutes"] = trip.get("activeWorkMinutes", 0.0) + work
    stages = trip.setdefault("activeStageMinutes", {})
    stages[stage] = stages.get(stage, 0.0) + work
