"""Validated call creation and unit availability reports."""

from copy import deepcopy
from datetime import datetime
from uuid import uuid4
from .dispatch_engine import action, safe_replan


def apply_call_action(state, payload, router):
    s = deepcopy(state)
    if payload["type"] == "create-call":
        existing = next(
            (t for t in s["trips"] if t.get("requestKey") == payload["requestKey"]),
            None,
        )
        if existing:
            if existing.get("callInput") != payload:
                raise ValueError(
                    "This submission key was already used for a different call"
                )
            return s
        if payload["pickup"] == payload["destination"]:
            raise ValueError("Pickup and destination must differ")
        s["trips"].append(
            {
                "id": "TR-" + uuid4().hex[:10].upper(),
                "from": payload["pickupName"],
                "to": payload["destinationName"],
                "pickup": payload["pickup"],
                "destination": payload["destination"],
                "scheduled": s["minute"] + payload["pickupInMinutes"],
                "status": "waiting",
                "requestKey": payload["requestKey"],
                "callInput": payload,
                "createdAtMinute": s["minute"],
            }
        )
        safe_replan(s, router, "New transport call added")
        return s
    unit = next((v for v in s["vehicles"] if v["id"] == payload["vehicleId"]), None)
    if unit is None:
        raise ValueError("Vehicle not found")
    timestamp = payload["observedAt"]
    if unit.get("statusReportedAt") and datetime.fromisoformat(
        timestamp
    ) <= datetime.fromisoformat(unit["statusReportedAt"]):
        raise ValueError("Older or duplicate status report rejected")
    trip = next((t for t in s["trips"] if t["id"] == unit.get("tripId")), None)
    status = payload["status"]
    if status == "available" and (trip or unit["holdUntil"] > s["minute"]):
        raise ValueError(
            "Unit still has a trip, service stage, or hold; it cannot be marked available"
        )
    if status == "unavailable" and trip and trip["status"] == "onboard":
        raise ValueError(
            "Patient is onboard. Use Out of service for a breakdown requiring transfer"
        )
    if status in {"unavailable", "out_of_service"}:
        s = action(s, {"type": "outage", "vehicleId": unit["id"]}, router)
    unit = next(v for v in s["vehicles"] if v["id"] == payload["vehicleId"])
    unit["outOfService"] = status == "out_of_service"
    unit["dispatchUnavailable"] = status == "unavailable"
    unit["reportedStatus"], unit["statusReportedAt"] = status, timestamp
    safe_replan(s, router, f"Availability report: {unit['id']} {status}")
    return s
