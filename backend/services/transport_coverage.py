"""Explicit demo assumption authorized by the user: relief crews cover later shifts."""
from backend.transport_store import utc

SIMULATED_RELIEF_CREWS = True


def shift_limit(vehicle, reference):
    if SIMULATED_RELIEF_CREWS: return float('inf')
    return (utc(vehicle['shift_end_at'])-utc(reference)).total_seconds()/60
