"""Project the populated Tiger Data directory into the existing frontend contract."""
from datetime import datetime, time, timezone
from zoneinfo import ZoneInfo
from backend.transport_store import Store, TransportError, utc

TRIP_STATUS = {'scheduled': 'waiting', 'assigned': 'pickup', 'en_route_to_pickup': 'pickup',
    'at_pickup': 'pickup', 'transporting': 'onboard', 'completed': 'complete',
    'cancelled': 'cancelled', 'transfer': 'transfer'}
ACTIVE = {'assigned', 'en_route_to_pickup', 'at_pickup', 'transporting'}


def reference_time(units, trips):
    values = [utc(t['pickup_time']) for t in trips]
    values += [utc(v['last_location_update_at']) for v in units]
    day = min(values).astimezone(ZoneInfo('America/New_York')).date() if values else datetime.now(ZoneInfo('America/New_York')).date()
    return utc(datetime.combine(day, time(9), ZoneInfo('America/New_York')))


def recorded_clock(units, trips):
    reference = reference_time(units, trips)
    latest = max((utc(v['last_location_update_at']) for v in units), default=reference)
    return {'reference_at': reference, 'minute': (latest-reference).total_seconds()/60,
            'running': False, 'speed': 1, 'traffic': False}


def point(lat, lng):
    import math
    if isinstance(lat, bool) or isinstance(lng, bool) or not isinstance(lat, (float,int)) or not isinstance(lng, (float,int)) or not math.isfinite(lat) or not math.isfinite(lng) or abs(lat)>90 or abs(lng)>180:
        raise TransportError('A database record contains invalid coordinates.', 422)
    return [lat, lng]


def snapshot(db):
    store = Store(db)
    units, source_trips = store.source()
    ready = store.ready()
    if ready:
        try:
            clock = store.clock()
        except TransportError:
            ready = False
    if not ready:
        clock = recorded_clock(units, source_trips)
    reference = utc(clock['reference_at'])
    plan_rows = store.all_plans() if ready else {}
    holds = store.holds() if ready else {}
    history = store.history() if ready else []
    ids = {v['ambulance_id'] for v in units}
    active = {}
    for t in source_trips:
        vid = t['ambulance_id'] or None
        if vid and vid not in ids:
            raise TransportError('A transport references a missing ambulance.', 422)
        if t['status'] in ACTIVE and vid:
            if vid in active:
                raise TransportError('An ambulance has multiple active transports.', 422)
            active[vid] = t['request_id']
    vehicles = []
    for v in units:
        vid = v['ambulance_id']
        hold = holds.get(vid, {})
        result = {'id': vid, 'crew': f"{v['crew_count']} crew · {v['service_level']}",
            'position': point(v['current_lat'],v['current_lng']), 'outOfService': v['status']=='out_of_service',
            'holdUntil': hold.get('hold_until',0), 'holdReason': hold.get('hold_reason','')}
        if vid in active:
            result['tripId'] = active[vid]
            plan = plan_rows.get(active[vid],{}).get('body',{})
            route = plan.get('transport') if plan.get('stage') in ('onboard','unloading') else plan.get('approach')
            if plan_rows.get(active[vid],{}).get('vehicle_id') != vid:
                route = None
            stage = plan.get('stage')
            if stage in ('loading','unloading'):
                result['routePhase'] = 'stopped'
            elif route and stage in ('pickup','onboard'):
                # Only publish the untravelled road; progress is owned by the backend.
                index = max(0, min(plan.get('routeIndex',0), len(route['path'])-1))
                remaining = [result['position']]
                for coordinate in route['path'][index+1:]:
                    if coordinate != remaining[-1]: remaining.append(coordinate)
                result['route'] = remaining
                result['routeIndex'] = 0
                result['routePhase'] = ('dropoff' if stage=='onboard' else 'pickup') if len(remaining)>1 else 'stopped'
        vehicles.append(result)
    trips = []
    directory_requests = []
    for t in source_trips:
        status = TRIP_STATUS.get(t['status'])
        if status is None:
            raise TransportError(f"Unsupported database transport status: {t['status']}",422)
        plan = plan_rows.get(t['request_id'],{}).get('body',{})
        result = {'id':t['request_id'], 'from':t['pickup_location'], 'to':t['dropoff_location'],
            'pickup':point(t['pickup_lat'],t['pickup_lng']), 'destination':point(t['dropoff_lat'],t['dropoff_lng']),
            'scheduled':(utc(t['pickup_time'])-reference).total_seconds()/60, 'status':status}
        if t['ambulance_id']:
            result['vehicleId']=t['ambulance_id']
        # Queued assignments remain waiting until the backend activates them.
        if plan.get('stage')=='queued':
            result['status']='waiting'
            result.pop('vehicleId',None)
            result['plannedVehicleId']=plan_rows[t['request_id']]['vehicle_id']
            result['plannedSequence']=plan_rows[t['request_id']]['sequence']
        for field in ['actualPickup','completedAt','transferLocation','eta']:
            if plan.get(field) is not None:
                result[field]=plan[field]
        if plan.get('transport'):
            result['transportRoute']=plan['transport']['path']
        if result['status'] not in ('complete','cancelled') and t['ambulance_id'] and active.get(t['ambulance_id']) != t['request_id'] and plan.get('stage')!='queued':
            raise TransportError('Inconsistent active transport assignment.',422)
        trips.append(result)
        directory = dict(t)
        directory['ambulance_id'] = t['ambulance_id'] or None
        directory['pickup_time']=utc(t['pickup_time']).isoformat()
        directory_requests.append(directory)
    directory_units=[]
    for v in units:
        v=dict(v)
        for field in ['last_location_update_at','shift_end_at']:
            v[field]=utc(v[field]).isoformat()
        directory_units.append(v)
    assignment_history=[]
    for h in history:
        if h['kind']=='assignment':
            item={'tripId':h['trip_id'],'reason':h['reason'],'minute':h['minute']}
            if h['from_vehicle_id']: item['fromVehicleId']=h['from_vehicle_id']
            if h['to_vehicle_id']: item['toVehicleId']=h['to_vehicle_id']
            assignment_history.append(item)
    from backend.services.transport_reset import baseline
    reset_actions = ['reset'] if ready and baseline(db) is not None else []
    return {'minute':clock['minute'],'traffic':clock['traffic'],'vehicles':vehicles,'trips':trips,
        'events':[h['reason'] for h in history[-100:]][::-1], 'assignmentHistory':assignment_history,
        'directory':{'ambulances':directory_units,'transport_requests':directory_requests},
        'supportedActions':['assign','optimize','routes','outage','restore','delay','traffic','simulation'] + reset_actions if ready else [],
        'integration':{'source':'Tiger Data','schemaReady':ready,'running':clock['running'],
            'simulationSpeed':clock['speed'],'referenceAt':reference.isoformat(),
            'workerConnected':bool(clock.get('worker_at') and (datetime.now(timezone.utc)-utc(clock['worker_at'])).total_seconds()<10),
            'routing':'OSRM driving estimates; simulated traffic adjustment'},
    }
