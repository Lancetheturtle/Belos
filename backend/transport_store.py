"""Additive transport storage. The original models and tables are not modified."""
from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import (MetaData, Table, Column, String, Float, Integer, Boolean,
                        DateTime, JSON, select, insert, update, inspect)

source_metadata = MetaData()
ambulances = Table('ambulances', source_metadata,
    Column('ambulance_id', String, primary_key=True), Column('unit_name', String),
    Column('current_location', String), Column('current_lat', Float), Column('current_lng', Float),
    Column('status', String), Column('crew_count', Integer), Column('stretcher_capacity', Integer),
    Column('service_level', String), Column('last_location_update_at', DateTime(timezone=True)),
    Column('shift_end_at', DateTime(timezone=True)))
requests = Table('transport_requests', source_metadata,
    Column('request_id', String, primary_key=True), Column('patient_id', String),
    Column('pickup_location', String), Column('pickup_address', String),
    Column('pickup_lat', Float), Column('pickup_lng', Float), Column('pickup_time', DateTime(timezone=True)),
    Column('status', String), Column('dropoff_location', String), Column('dropoff_address', String),
    Column('dropoff_lat', Float), Column('dropoff_lng', Float), Column('ambulance_id', String),
    Column('transport_type', String), Column('mobility', String), Column('planned_duration_minutes', Integer),
    Column('booking_type', String), Column('service_level', String))

storage_metadata = MetaData()
runtime = Table('belos_transport_runtime', storage_metadata,
    Column('id', String, primary_key=True), Column('reference_at', DateTime(timezone=True), nullable=False),
    Column('minute', Float, nullable=False), Column('wall_at', DateTime(timezone=True), nullable=False),
    Column('running', Boolean, nullable=False), Column('worker_at', DateTime(timezone=True)), Column('speed', Float, nullable=False),
    Column('traffic', Boolean, nullable=False))
plans = Table('belos_transport_plans', storage_metadata,
    Column('trip_id', String, primary_key=True), Column('vehicle_id', String, index=True, nullable=False),
    Column('sequence', Integer, nullable=False), Column('body', JSON, nullable=False))
vehicle_state = Table('belos_transport_vehicle_state', storage_metadata,
    Column('vehicle_id', String, primary_key=True), Column('hold_until', Float, nullable=False),
    Column('hold_reason', String, nullable=False))
events = Table('belos_transport_events', storage_metadata,
    Column('id', String, primary_key=True), Column('recorded_at', DateTime(timezone=True), nullable=False),
    Column('minute', Float, nullable=False), Column('kind', String, nullable=False),
    Column('trip_id', String), Column('from_vehicle_id', String), Column('to_vehicle_id', String),
    Column('reason', String, nullable=False))
positions = Table('belos_transport_positions', storage_metadata,
    Column('id', String, primary_key=True), Column('vehicle_id', String, index=True, nullable=False),
    Column('recorded_at', DateTime(timezone=True), nullable=False), Column('minute', Float, nullable=False),
    Column('lat', Float, nullable=False), Column('lng', Float, nullable=False))


checkpoints = Table('belos_transport_checkpoints', storage_metadata,
    Column('id', String, primary_key=True), Column('kind', String, nullable=False),
    Column('created_at', DateTime(timezone=True), nullable=False),
    Column('body', JSON, nullable=False))


def utc(value):
    if isinstance(value, str):
        value = datetime.fromisoformat(value.replace('Z', '+00:00'))
    if not isinstance(value, datetime):
        raise ValueError('A required database timestamp is missing or invalid.')
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)


class TransportError(Exception):
    def __init__(self, message, status=409):
        super().__init__(message)
        self.status = status


class Store:
    def __init__(self, db):
        self.db = db

    def ready(self):
        inspector = inspect(self.db.connection())
        return all(inspector.has_table(t.name) for t in storage_metadata.sorted_tables)

    def source(self):
        units = [dict(r) for r in self.db.execute(select(ambulances).order_by(ambulances.c.ambulance_id)).mappings()]
        trips = [dict(r) for r in self.db.execute(select(requests).order_by(requests.c.pickup_time, requests.c.request_id)).mappings()]
        for rows, key in [(units, 'ambulance_id'), (trips, 'request_id')]:
            ids = [r[key] for r in rows]
            if any(not isinstance(i, str) or not i.strip() for i in ids) or len(ids) != len(set(ids)):
                raise TransportError('Source records have missing or duplicate identifiers.', 422)
        return units, trips

    def clock(self, lock=False):
        query = select(runtime).where(runtime.c.id == 'default')
        if lock:
            query = query.with_for_update()
        row = self.db.execute(query).mappings().first()
        if row is None:
            raise TransportError('Initialize transport storage with python -m backend.transport_runtime init.', 503)
        return dict(row)

    def save_clock(self, clock):
        self.db.execute(update(runtime).where(runtime.c.id == 'default').values(**clock))

    def all_plans(self):
        return {r['trip_id']: dict(r) for r in self.db.execute(select(plans)).mappings()}

    def save_plan(self, row):
        found = self.db.execute(select(plans.c.trip_id).where(plans.c.trip_id == row['trip_id'])).first()
        if found:
            self.db.execute(update(plans).where(plans.c.trip_id == row['trip_id']).values(**row))
        else:
            self.db.execute(insert(plans).values(**row))

    def update_source(self, table, key, value, **fields):
        result = self.db.execute(update(table).where(table.c[key] == value).values(**fields))
        if result.rowcount != 1:
            raise TransportError('Source record changed or has duplicate identifiers; operation rolled back.')

    def history(self):
        return [dict(r) for r in self.db.execute(select(events).order_by(events.c.recorded_at, events.c.id)).mappings()]

    def event(self, minute, reason, kind='activity', trip=None, old=None, new=None):
        self.db.execute(insert(events).values(id=str(uuid4()), recorded_at=datetime.now(timezone.utc),
            minute=minute, kind=kind, trip_id=trip, from_vehicle_id=old, to_vehicle_id=new, reason=reason))

    def holds(self):
        return {r['vehicle_id']: dict(r) for r in self.db.execute(select(vehicle_state)).mappings()}

    def hold(self, vehicle_id, until, reason):
        values = dict(vehicle_id=vehicle_id, hold_until=until, hold_reason=reason)
        if vehicle_id in self.holds():
            self.db.execute(update(vehicle_state).where(vehicle_state.c.vehicle_id == vehicle_id).values(**values))
        else:
            self.db.execute(insert(vehicle_state).values(**values))

    def position(self, vehicle_id, minute, point):
        self.db.execute(insert(positions).values(id=str(uuid4()), vehicle_id=vehicle_id,
            recorded_at=datetime.now(timezone.utc), minute=minute, lat=point[0], lng=point[1]))
