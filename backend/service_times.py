"""User-supplied comparison assumptions, in simulated minutes."""

MODEL = "transport-active-cycle-75-v2"
LOAD_MINUTES = 15
HANDOFF_MINUTES = 32
RESET_MINUTES = 5
BENCHMARK = [
    {"stage": "Drive to pickup", "minutes": 8},
    {"stage": "Prepare and load patient", "minutes": LOAD_MINUTES},
    {"stage": "Drive to destination", "minutes": 15},
    {"stage": "Unload, handoff and paperwork", "minutes": HANDOFF_MINUTES},
    {"stage": "Reset and become available", "minutes": RESET_MINUTES},
]


def cycle_metrics(state):
    compatible = state.get("serviceModel") == MODEL
    rows = []
    for trip in state["trips"]:
        start, finish = trip.get("dispatchStartedAt"), trip.get("availableAt")
        actual = (
            trip.get("activeWorkMinutes", 0.0)
            if compatible and start is not None and finish is not None
            else None
        )
        rows.append(
            {
                "tripId": trip["id"],
                "stage": trip.get("serviceStage", trip["status"]),
                "startedAt": start,
                "availableAt": finish,
                "actualCycleMinutes": actual,
                "elapsedCycleMinutes": (
                    finish - start if start is not None and finish is not None else None
                ),
                "excludedWaitingMinutes": (
                    max(0.0, finish - start - actual) if actual is not None else None
                ),
                "activeWorkSoFarMinutes": trip.get("activeWorkMinutes", 0.0),
                "activeStageMinutes": trip.get("activeStageMinutes", {}),
                "minutesBelowBenchmark": 75 - actual if actual is not None else None,
                "pickupArrivalAt": trip.get("pickupArrivalAt"),
                "loadingStartedAt": trip.get("loadingStartedAt"),
                "departedPickupAt": trip.get("departedPickupAt"),
                "destinationArrivalAt": trip.get("destinationArrivalAt"),
                "handoffCompletedAt": trip.get("completedAt"),
            }
        )
    completed = [
        row["actualCycleMinutes"]
        for row in rows
        if row["actualCycleMinutes"] is not None
    ]
    average = sum(completed) / len(completed) if completed else None
    return {
        "stages": BENCHMARK,
        "totalMinutes": 75,
        "serviceMinutes": 52,
        "compatibleShift": compatible,
        "cycles": rows,
        "completedCycles": len(completed),
        "totalMinutesSaved": sum(75 - minutes for minutes in completed) if compatible else None,
        "averageActualCycleMinutes": average,
        "averageMinutesBelowBenchmark": 75 - average if average is not None else None,
        "basis": "User-supplied 75-minute estimate, not a measured control group. Belos retains road-based drive times and uses the same 15+32+5 service minutes. Active cycle counts road travel, preparation/loading, handoff/paperwork and reset only. Idle waiting for a patient, another assignment, or a crew hold is excluded from this KPI. Total elapsed cycle and excluded waiting remain visible separately. Transfers can add active work. Compare this active-work definition consistently with the supplied benchmark. Positive difference means below the benchmark; negative means above. Only finished cycles from a freshly reset shift are included.",
    }
