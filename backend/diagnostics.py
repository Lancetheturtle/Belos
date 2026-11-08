"""Read-only live metrics and same-input, per-plan comparisons."""


def plan_comparison(state, selected, units, costs, assignments, reason):
    available = set(range(len(units)))
    baseline = {}
    for row, trip in enumerate(selected):
        candidates = [i for i in available if costs[row][i] < 1e12]
        if candidates:
            column = min(candidates, key=lambda i: (costs[row][i], units[i]["id"]))
            baseline[trip["id"]] = column
            available.remove(column)

    rows = []
    for row, trip in enumerate(selected):
        chosen = assignments.get(trip["id"])
        column = next(
            (
                i
                for i, unit in enumerate(units)
                if chosen and unit["id"] == chosen[0]["id"]
            ),
            None,
        )
        greedy = baseline.get(trip["id"])
        rows.append(
            {
                "tripId": trip["id"],
                "scheduled": trip["scheduled"],
                "baselineUnit": units[greedy]["id"] if greedy is not None else None,
                "optimizedUnit": units[column]["id"] if column is not None else None,
                "baselineMinutes": (
                    costs[row][greedy] - state["minute"] if greedy is not None else None
                ),
                "optimizedMinutes": (
                    costs[row][column] - state["minute"] if column is not None else None
                ),
                "candidates": [
                    {
                        "vehicleId": unit["id"],
                        "arrivalMinutes": (
                            cost - state["minute"] if cost < 1e12 else None
                        ),
                    }
                    for unit, cost in zip(units, costs[row])
                ],
            }
        )
    comparable = bool(rows) and all(
        row["baselineMinutes"] is not None and row["optimizedMinutes"] is not None
        for row in rows
    )
    baseline_total = sum(row["baselineMinutes"] for row in rows) if comparable else None
    optimized_total = (
        sum(row["optimizedMinutes"] for row in rows) if comparable else None
    )
    return {
        "minute": state["minute"],
        "reason": reason,
        "trips": rows,
        "comparable": comparable,
        "baselineMinutes": baseline_total,
        "optimizedMinutes": optimized_total,
        "estimatedMinutesSaved": (
            baseline_total - optimized_total if comparable else None
        ),
        "basis": "Same road-time matrix and next-wave trips. Baseline assigns each scheduled trip its fastest remaining unit in order. Optimized minimizes their combined arrival time. Includes crew holds and traffic factors; excludes waiting for scheduled pickup and loading. Estimates, not measured full-shift savings. Do not add savings across replans: trips can repeat.",
    }


def live_diagnostics(state, speed):
    from .service_times import cycle_metrics

    picked_up = [
        trip for trip in state["trips"] if trip.get("actualPickup") is not None
    ]
    lateness = [max(0, trip["actualPickup"] - trip["scheduled"]) for trip in picked_up]
    return {
        "minute": state["minute"],
        "simulationSpeed": speed,
        "cycleBenchmark": cycle_metrics(state),
        "dispatch": state.get("dispatch"),
        "metrics": {
            "trips": len(state["trips"]),
            "completed": sum(trip["status"] == "complete" for trip in state["trips"]),
            "pickedUp": len(picked_up),
            "onTimePickups": sum(delay <= 1e-7 for delay in lateness),
            "averagePickupDelayMinutes": (
                sum(lateness) / len(lateness) if lateness else None
            ),
        },
        "trips": [
            {
                key: trip.get(key)
                for key in (
                    "id",
                    "status",
                    "vehicleId",
                    "scheduled",
                    "etaMinute",
                    "actualPickup",
                    "completedAt",
                )
            }
            for trip in state["trips"]
        ],
        "vehicles": [
            {
                "id": unit["id"],
                "tripId": unit.get("tripId"),
                "outOfService": unit["outOfService"],
                "holdMinutes": max(0, unit["holdUntil"] - state["minute"]),
                "holdReason": unit["holdReason"],
                "trafficFactor": (2 if state["traffic"] else 1)
                * state.get("trafficFactors", {}).get(unit["id"], 1),
            }
            for unit in state["vehicles"]
        ],
        "latestPlan": state.get("planDiagnostics"),
        "planHistory": state.get("planDiagnosticsHistory", []),
        "assignmentHistory": state.get("assignmentHistory", []),
    }
