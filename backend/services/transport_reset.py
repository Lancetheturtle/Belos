"""Persistent reset checkpoints; never seed or replace the Tiger Data directory."""
import json
import math
from datetime import datetime, timezone
from uuid import uuid4
from sqlalchemy import select, insert, delete
from backend.transport_store import (Store, TransportError, ambulances, requests,
    checkpoints, plans, vehicle_state, utc)

UNIT_FIELDS = ('current_location', 'current_lat', 'current_lng', 'status', 'last_location_update_at')
TRIP_FIELDS = ('status', 'ambulance_id')


def serializable(value):
    return json.loads(json.dumps(value, default=lambda v: utc(v).isoformat()))


def baseline(db):
    return db.execute(select(checkpoints.c.body).where(checkpoints.c.id == 'baseline')).scalar_one_or_none()


def save_baseline(db, imported=None):
    store = Store(db)
    clock = store.clock(lock=True)
    if baseline(db) is not None:
        raise TransportError('A reset baseline already exists; it will not be overwritten.')
    if imported is None:
        if clock['running']:
            raise TransportError('Pause the simulation before capturing its reset baseline.')
        units, trips = store.source()
        body = {'directory': {'ambulances': units, 'transport_requests': trips},
                'minute': clock['minute'], 'referenceAt': utc(clock['reference_at']).isoformat()}
    else:
        body = {'directory': imported['directory'], 'minute': imported['minute'],
                'referenceAt': imported['integration']['referenceAt']}
    validate_baseline(store, body)
    db.execute(insert(checkpoints).values(id='baseline', kind='baseline',
        created_at=datetime.now(timezone.utc), body=serializable(body)))


def validate_baseline(store, body):
    from backend.services.transport_snapshot import point, TRIP_STATUS, ACTIVE
    units, trips = store.source()
    directory = body['directory']
    for current, saved, key in [(units, directory['ambulances'], 'ambulance_id'),
                                 (trips, directory['transport_requests'], 'request_id')]:
        ids = [row[key] for row in saved]
        if len(ids) != len(set(ids)) or set(ids) != {row[key] for row in current}:
            raise TransportError('Reset baseline does not match the current directory IDs; no records were changed.')
    if not math.isfinite(body['minute']):
        raise TransportError('Reset baseline has an invalid clock.', 422)
    utc(body['referenceAt'])
    ids = {v['ambulance_id'] for v in units}
    active = set()
    for v in directory['ambulances']:
        point(v['current_lat'], v['current_lng'])
        utc(v['last_location_update_at'])
        if v['status'] not in ('available','assigned','en_route_to_pickup','at_pickup','transporting','out_of_service'):
            raise TransportError('Invalid baseline ambulance status.', 422)
    for t in directory['transport_requests']:
        vid = t['ambulance_id']
        if t['status'] not in TRIP_STATUS or (vid and vid not in ids):
            raise TransportError('Invalid baseline trip or assignment.', 422)
        if vid and t['status'] in ACTIVE:
            if vid in active: raise TransportError('Baseline has duplicate active assignments.', 422)
            active.add(vid)


def reset(store, clock):
    body = baseline(store.db)
    if body is None:
        raise TransportError('No saved reset baseline. Capture or import one before resetting.')
    validate_baseline(store, body)
    units, trips = store.source()
    # This backup and every restore write share the worker's clock lock and transaction.
    store.db.execute(insert(checkpoints).values(id=str(uuid4()), kind='before_reset',
        created_at=datetime.now(timezone.utc), body=serializable({
            'directory': {'ambulances': units, 'transport_requests': trips},
            'clock': clock, 'plans': store.all_plans(), 'holds': store.holds()})))
    for v in body['directory']['ambulances']:
        values = {k: v[k] for k in UNIT_FIELDS}
        values['last_location_update_at'] = utc(values['last_location_update_at'])
        store.update_source(ambulances, 'ambulance_id', v['ambulance_id'], **values)
    for t in body['directory']['transport_requests']:
        store.update_source(requests, 'request_id', t['request_id'], **{k: t[k] for k in TRIP_FIELDS})
    store.db.execute(delete(plans))
    store.db.execute(delete(vehicle_state))
    clock.update(reference_at=utc(body['referenceAt']), minute=body['minute'],
                 running=False, speed=1, traffic=False, wall_at=datetime.now(timezone.utc))
    # Retain historical events and positions as an audit trail across resets.
    store.event(clock['minute'], 'Simulation reset to the saved Tiger Data baseline; paused at 1x. Previous state backed up.', 'reset')
