"""Isolated integration checks. No network, Tiger Data credentials or production writes."""
import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch
from sqlalchemy import create_engine, insert, select, update
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from fastapi import FastAPI
from fastapi.testclient import TestClient
from backend.transport_store import (source_metadata, storage_metadata, ambulances, requests,
    runtime, plans, positions, Store, TransportError, utc)
from backend.services.transport_commands import initialize, command
from backend.services.transport_snapshot import snapshot
from backend.services.transport_motion import advance, location
from backend.transport_runtime import tick
from backend.routes.transport import router
from backend.database import get_db
from backend.services.osrm import RoutingError

NOW=datetime(2026,11,7,14,tzinfo=timezone.utc)


def road(start,end):
    return {'path':[list(start),[(start[0]+end[0])/2,(start[1]+end[1])/2],list(end)],'durationSeconds':60,'distanceMeters':1000}


class IntegrationTests(unittest.TestCase):
    def setUp(self):
        self.timing_patch=patch.multiple('backend.services.transport_timing',LOAD_MINUTES=2.0,HANDOFF_MINUTES=2.0,RESET_MINUTES=0.0)
        self.timing_patch.start()
        self.addCleanup(self.timing_patch.stop)
        self.engine=create_engine('sqlite://',connect_args={'check_same_thread':False},poolclass=StaticPool)
        source_metadata.create_all(self.engine)
        storage_metadata.create_all(self.engine)
        self.sessions=sessionmaker(bind=self.engine)
        with self.sessions.begin() as db:
            for i in (1,2):
                db.execute(insert(ambulances).values(ambulance_id=f'AMB-{i}',unit_name=f'Unit {i}',
                    current_location='Facility',current_lat=42.7+i/1000,current_lng=-73.7,status='available',
                    crew_count=2,stretcher_capacity=1,service_level='BLS',last_location_update_at=NOW,
                    shift_end_at=NOW+timedelta(hours=12)))
            for i in (1,2,3):
                db.execute(insert(requests).values(request_id=f'TR-{i}',patient_id=f'PAT-{i}',
                    pickup_location='Pickup',pickup_address='Pickup address',pickup_lat=42.71,pickup_lng=-73.71,
                    pickup_time=NOW+timedelta(minutes=(i-1)*10),status='scheduled',dropoff_location='Destination',
                    dropoff_address='Destination address',dropoff_lat=42.72,dropoff_lng=-73.72,ambulance_id=None,
                    transport_type='scheduled_transfer',mobility='stretcher',planned_duration_minutes=20,
                    booking_type='preplanned',service_level='BLS'))
            initialize(db)
        self.route_patch=patch('backend.services.transport_planner.get_road_route',side_effect=road)
        self.route_patch.start()
        self.matrix_patch=patch('backend.services.transport_planner.get_time_matrix',side_effect=lambda locations:[[0 if a==b else 60 for b in locations] for a in locations])
        self.matrix_patch.start()

    def tearDown(self):
        self.route_patch.stop();self.matrix_patch.stop();self.engine.dispose()

    def client(self):
        app=FastAPI();app.include_router(router)
        def db_dependency():
            with self.sessions() as db: yield db
        app.dependency_overrides[get_db]=db_dependency
        return TestClient(app)

    def test_snapshot_reads_real_directory_and_does_not_mutate(self):
        with self.sessions() as db:
            before=Store(db).source()
            a=snapshot(db);b=snapshot(db)
            self.assertEqual(a,b)
            self.assertEqual(before,Store(db).source())
            self.assertEqual(len(a['vehicles']),2)
            self.assertEqual(len(a['directory']['transport_requests']),3)
            self.assertEqual(a['trips'][0]['id'],'TR-1')

    def test_get_read_and_alias_never_call_osrm_or_advance(self):
        with patch('backend.services.osrm.requests.get',side_effect=AssertionError('GET must not route')):
            c=self.client()
            a=c.get('/transport/state');b=c.get('/transport/snapshot')
            self.assertEqual(a.status_code,200,a.text)
            self.assertEqual(a.json(),b.json())
            self.assertEqual(c.get('/transport/directory').status_code,200)

    def test_assign_persists_both_projections_and_survives_new_session(self):
        response=self.client().post('/transport/commands',json={'type':'assign','tripId':'TR-1','vehicleId':'AMB-1'})
        self.assertEqual(response.status_code,200,response.text)
        with self.sessions() as db:
            s=snapshot(db)
            self.assertEqual(s['vehicles'][0]['tripId'],'TR-1')
            self.assertEqual(s['trips'][0]['vehicleId'],'AMB-1')
            self.assertEqual(s['assignmentHistory'][0]['toVehicleId'],'AMB-1')
            self.assertEqual(len(s['vehicles'][0]['route']),3)

    def test_assignment_conflict_and_validation(self):
        c=self.client()
        self.assertEqual(c.post('/transport/commands',json={'type':'assign','tripId':'TR-1','vehicleId':'AMB-1'}).status_code,200)
        self.assertEqual(c.post('/transport/commands',json={'type':'assign','tripId':'TR-2','vehicleId':'AMB-1'}).status_code,409)
        self.assertEqual(c.post('/transport/commands',json={'type':'assign','tripId':'missing','vehicleId':'AMB-2'}).status_code,404)
        self.assertEqual(c.post('/transport/commands',json={'type':'assign','tripId':'TR-2'}).status_code,422)
        self.assertEqual(c.post('/transport/commands',json={'type':'delay','vehicleId':'AMB-2','minutes':-1}).status_code,422)
        self.assertEqual(c.post('/transport/commands',json={'type':'optimize','vehicleId':'AMB-2'}).status_code,422)

    def test_road_failure_rolls_back_assignment(self):
        with patch('backend.services.transport_planner.get_road_route',side_effect=RoutingError('offline')):
            response=self.client().post('/transport/commands',json={'type':'assign','tripId':'TR-1','vehicleId':'AMB-1'})
            self.assertEqual(response.status_code,502)
        with self.sessions() as db:
            self.assertIsNone(Store(db).source()[1][0]['ambulance_id'])
            self.assertEqual(Store(db).all_plans(),{})

    def test_worker_moves_vehicle_and_completes_trip_without_polling(self):
        with self.sessions.begin() as db:
            command(db,{'type':'assign','tripId':'TR-1','vehicleId':'AMB-1'})
        with self.sessions.begin() as db:
            store=Store(db);clock=store.clock(lock=True)
            initial=store.source()[0][0]['current_lat']
            advance(store,clock,0.5);store.save_clock(clock)
            self.assertNotEqual(store.source()[0][0]['current_lat'],initial)
        with self.sessions.begin() as db:
            store=Store(db);clock=store.clock(lock=True)
            advance(store,clock,10);store.save_clock(clock)
        with self.sessions() as db:
            result=snapshot(db)
            self.assertEqual(result['trips'][0]['status'],'complete')
            self.assertEqual(result['minute'],10.5)
            self.assertNotIn('tripId',result['vehicles'][0])
            self.assertEqual(db.execute(select(positions)).all().__len__(),2)

    def test_clock_persists_and_paused_worker_does_not_move(self):
        with self.sessions.begin() as db:
            clock=Store(db).clock();wall=clock['wall_at'].replace(tzinfo=timezone.utc)
            tick(db,wall+timedelta(seconds=20))
        with self.sessions() as db:
            self.assertEqual(Store(db).clock()['minute'],0)
        with self.sessions.begin() as db:
            clock=Store(db).clock();clock.update(running=True,speed=15,wall_at=wall);Store(db).save_clock(clock)
            tick(db,wall+timedelta(seconds=4))
        with self.sessions() as db:self.assertEqual(Store(db).clock()['minute'],1)

    def test_delay_holds_actual_position(self):
        with self.sessions.begin() as db:
            command(db,{'type':'assign','tripId':'TR-1','vehicleId':'AMB-1'})
            command(db,{'type':'delay','vehicleId':'AMB-1','minutes':10})
            store=Store(db);clock=store.clock()
            before=store.source()[0][0]['current_lat']
            advance(store,clock,5);store.save_clock(clock)
            self.assertEqual(store.source()[0][0]['current_lat'],before)

    def test_onboard_outage_preserves_patient_and_restore_does_not_reclaim(self):
        with self.sessions.begin() as db:
            command(db,{'type':'assign','tripId':'TR-1','vehicleId':'AMB-1'})
            store=Store(db);clock=store.clock()
            advance(store,clock,3.5);store.save_clock(clock)
            actual=snapshot(db)['trips'][0]['actualPickup']
            position=snapshot(db)['vehicles'][0]['position']
            command(db,{'type':'outage','vehicleId':'AMB-1'})
            s=snapshot(db)
            self.assertEqual(s['trips'][0]['status'],'pickup')
            self.assertEqual(s['trips'][0]['vehicleId'],'AMB-2')
            self.assertEqual(s['trips'][0]['transferLocation'],position)
            self.assertEqual(store.all_plans()['TR-1']['body']['approach']['path'][-1],position)
            self.assertEqual(snapshot(db)['trips'][0]['actualPickup'],actual)
            command(db,{'type':'restore','vehicleId':'AMB-1'})
            self.assertNotIn('tripId',snapshot(db)['vehicles'][0])

    def test_planning_persists_queue_and_worker_activates_it(self):
        with self.sessions.begin() as db:
            command(db,{'type':'optimize'})
            s=snapshot(db)
            self.assertTrue(any(t.get('plannedVehicleId') for t in s['trips']))
            store=Store(db);clock=store.clock()
            advance(store,clock,1);store.save_clock(clock)
            self.assertTrue(any(t['status']=='pickup' for t in snapshot(db)['trips']))

    def test_incompatible_capacity_and_shift_are_rejected(self):
        with self.sessions.begin() as db:
            db.execute(update(ambulances).where(ambulances.c.ambulance_id=='AMB-1').values(stretcher_capacity=0))
        self.assertEqual(self.client().post('/transport/commands',json={'type':'assign','tripId':'TR-1','vehicleId':'AMB-1'}).status_code,409)

    def test_simulated_traffic_does_not_teleport_vehicle(self):
        with self.sessions.begin() as db:
            command(db,{'type':'assign','tripId':'TR-1','vehicleId':'AMB-1'})
            store=Store(db);clock=store.clock()
            advance(store,clock,0.5);store.save_clock(clock)
            point=snapshot(db)['vehicles'][0]['position']
            command(db,{'type':'traffic','enabled':True})
            self.assertEqual(snapshot(db)['vehicles'][0]['position'],point)
            clock=store.clock();advance(store,clock,0.5);store.save_clock(clock)
            self.assertNotEqual(snapshot(db)['vehicles'][0]['position'],point)

    def test_read_snapshot_works_before_extension_initialization(self):
        storage_metadata.drop_all(self.engine)
        response=self.client().get('/transport/state')
        self.assertEqual(response.status_code,200,response.text)
        self.assertFalse(response.json()['integration']['schemaReady'])
        self.assertEqual(response.json()['supportedActions'],[])

    def test_outage_replans_before_pickup_without_reclaim_on_restore(self):
        with self.sessions.begin() as db:
            command(db,{'type':'assign','tripId':'TR-1','vehicleId':'AMB-1'})
            command(db,{'type':'outage','vehicleId':'AMB-1'})
            s=snapshot(db)
            self.assertTrue(s['vehicles'][0]['outOfService'])
            self.assertEqual(s['trips'][0]['plannedVehicleId'],'AMB-2')
            command(db,{'type':'restore','vehicleId':'AMB-1'})
            self.assertNotIn('tripId',snapshot(db)['vehicles'][0])

    def test_outage_is_saved_even_if_replanning_provider_fails(self):
        with self.sessions.begin() as db:
            command(db,{'type':'assign','tripId':'TR-1','vehicleId':'AMB-1'})
            with patch('backend.services.transport_planner.get_time_matrix',side_effect=RoutingError('offline')):
                command(db,{'type':'outage','vehicleId':'AMB-1'})
            s=snapshot(db)
            self.assertTrue(s['vehicles'][0]['outOfService'])
            self.assertNotIn('vehicleId',s['trips'][0])
            self.assertTrue(any('Automatic replanning unavailable' in e for e in s['events']))

    def test_replan_releases_reservations_that_no_longer_fit_shifts(self):
        with self.sessions.begin() as db:
            command(db,{'type':'optimize'})
            db.execute(update(ambulances).values(shift_end_at=NOW-timedelta(minutes=1)))
            command(db,{'type':'optimize'})
            self.assertTrue(all(not t.get('plannedVehicleId') for t in snapshot(db)['trips']))
            self.assertTrue(all(not t['ambulance_id'] for t in Store(db).source()[1]))

    def test_queue_completes_all_trips_and_survives_session_restart(self):
        with self.sessions.begin() as db: command(db,{'type':'optimize'})
        with self.sessions.begin() as db:
            store=Store(db);clock=store.clock()
            advance(store,clock,100);store.save_clock(clock)
        with self.sessions() as db:
            self.assertTrue(all(t['status']=='complete' for t in snapshot(db)['trips']))
            self.assertTrue(all(not v.get('tripId') for v in snapshot(db)['vehicles']))

    def test_onboard_work_is_not_reassigned_by_optimizer(self):
        with self.sessions.begin() as db:
            command(db,{'type':'assign','tripId':'TR-1','vehicleId':'AMB-1'})
            store=Store(db);clock=store.clock()
            advance(store,clock,3.5);store.save_clock(clock)
            command(db,{'type':'optimize'})
            s=snapshot(db)
            self.assertEqual(s['trips'][0]['status'],'onboard')
            self.assertEqual(s['trips'][0]['vehicleId'],'AMB-1')

    def test_duplicate_worker_timestamp_does_not_advance_clock_twice(self):
        with self.sessions.begin() as db:
            store=Store(db);clock=store.clock()
            wall=clock['wall_at'].replace(tzinfo=timezone.utc)
            clock['running']=True;store.save_clock(clock)
            tick(db,wall+timedelta(seconds=60))
            tick(db,wall+timedelta(seconds=60))
            tick(db,wall+timedelta(seconds=120))
            self.assertEqual(store.clock()['minute'],2)

    def test_empty_database_returns_empty_arrays_not_fixtures(self):
        with self.sessions.begin() as db:
            db.execute(requests.delete());db.execute(ambulances.delete())
        response=self.client().get('/transport/state')
        self.assertEqual(response.status_code,200)
        self.assertEqual(response.json()['vehicles'],[])
        self.assertEqual(response.json()['trips'],[])
        self.assertEqual(response.json()['directory'],{'ambulances':[],'transport_requests':[]})

    def test_deployment_entrypoint_forwards_existing_app_and_api_prefix(self):
        from api.index import app,backend_app
        from backend.main import app as original_app
        self.assertIs(backend_app,original_app)
        def dependency():
            with self.sessions() as db: yield db
        original_app.dependency_overrides[get_db]=dependency
        try:
            client=TestClient(app)
            self.assertEqual(client.get('/api/health').status_code,200)
            response=client.get('/api/transport/state')
            self.assertEqual(response.status_code,200,response.text)
            self.assertEqual(len(response.json()['vehicles']),2)
            self.assertEqual(client.get('/api/openapi.json').status_code,200)
            self.assertIn('/api/openapi.json',client.get('/api/docs').text)
        finally:
            original_app.dependency_overrides.pop(get_db,None)

    def test_explicit_transfer_can_release_future_reservations_without_interrupting_active_work(self):
        from backend.services.transport_planner import route_plan
        with self.sessions.begin() as db:
            command(db,{'type':'assign','tripId':'TR-1','vehicleId':'AMB-1'})
            store=Store(db);clock=store.clock()
            advance(store,clock,3.5);store.save_clock(clock)
            store.update_source(ambulances,'ambulance_id','AMB-2',status='out_of_service')
            command(db,{'type':'outage','vehicleId':'AMB-1'})
            store.update_source(ambulances,'ambulance_id','AMB-2',status='available')
            units,trips=store.source()
            v=next(v for v in units if v['ambulance_id']=='AMB-2')
            t=next(t for t in trips if t['request_id']=='TR-2')
            body=route_plan(v,t,clock['minute'],clock['reference_at'],stage='queued')
            store.save_plan({'trip_id':'TR-2','vehicle_id':'AMB-2','sequence':1,'body':body})
            store.update_source(requests,'request_id','TR-2',ambulance_id='AMB-2')
            command(db,{'type':'assign','tripId':'TR-1','vehicleId':'AMB-2'})
            s=snapshot(db)
            self.assertEqual(s['trips'][0]['vehicleId'],'AMB-2')
            self.assertNotIn('plannedVehicleId',s['trips'][1])
            self.assertIsNone(store.source()[1][1]['ambulance_id'])


    def test_reset_restores_persisted_baseline_and_pauses_worker(self):
        from backend.services.transport_reset import save_baseline, baseline
        from backend.transport_store import checkpoints
        with self.sessions.begin() as db:
            save_baseline(db)
            original = Store(db).source()
            command(db, {'type':'assign','tripId':'TR-1','vehicleId':'AMB-1'})
            command(db, {'type':'simulation','running':True,'speed':60})
            command(db, {'type':'delay','vehicleId':'AMB-2','minutes':10})
            command(db, {'type':'traffic','enabled':True})
            clock = Store(db).clock()
            tick(db, utc(clock['wall_at']) + timedelta(seconds=5))
        response = self.client().post('/transport/commands', json={'type':'reset'})
        self.assertEqual(response.status_code, 200, response.text)
        self.assertFalse(response.json()['integration']['running'])
        self.assertEqual(response.json()['integration']['simulationSpeed'], 1)
        self.assertFalse(response.json()['traffic'])
        with self.sessions.begin() as db:
            self.assertEqual(Store(db).source(), original)
            self.assertEqual(Store(db).all_plans(), {})
            self.assertEqual(Store(db).holds(), {})
            self.assertIsNotNone(baseline(db))
            saved = db.execute(select(checkpoints.c.body).where(checkpoints.c.kind=='before_reset')).scalar_one()
            self.assertTrue(saved['clock']['running'])
            clock=Store(db).clock()
            tick(db, utc(clock['wall_at'])+timedelta(seconds=60))
            self.assertEqual(Store(db).source(), original)
            self.assertEqual(Store(db).clock()['minute'], clock['minute'])

    def test_reset_without_baseline_is_rejected_without_writes(self):
        with self.sessions() as db: before=Store(db).source()
        self.assertNotIn('reset', self.client().get('/transport/state').json()['supportedActions'])
        response=self.client().post('/transport/commands', json={'type':'reset'})
        self.assertEqual(response.status_code,409)
        with self.sessions() as db: self.assertEqual(Store(db).source(),before)

    def test_baseline_is_immutable_and_reset_rejects_changed_roster(self):
        from backend.services.transport_reset import save_baseline
        from backend.transport_store import checkpoints
        from sqlalchemy import delete
        with self.sessions.begin() as db: save_baseline(db)
        with self.sessions.begin() as db:
            with self.assertRaises(TransportError): save_baseline(db)
            db.execute(delete(requests).where(requests.c.request_id=='TR-3'))
        response=self.client().post('/transport/commands',json={'type':'reset'})
        self.assertEqual(response.status_code,409)
        with self.sessions() as db:
            self.assertEqual(len(Store(db).source()[1]),2)
            self.assertEqual(len(db.execute(select(checkpoints)).all()),1)

    def test_reset_rolls_back_backup_and_partial_updates_on_failure(self):
        from backend.services.transport_reset import save_baseline
        from backend.transport_store import checkpoints
        with self.sessions.begin() as db:
            save_baseline(db)
            command(db,{'type':'assign','tripId':'TR-1','vehicleId':'AMB-1'})
            before=Store(db).source()
        original_update=Store.update_source
        def fail_on_trip(store,table,*args,**kwargs):
            if table is requests: raise TransportError('Injected failure')
            return original_update(store,table,*args,**kwargs)
        with patch.object(Store,'update_source',fail_on_trip):
            response=self.client().post('/transport/commands',json={'type':'reset'})
        self.assertEqual(response.status_code,409)
        with self.sessions() as db:
            self.assertEqual(Store(db).source(),before)
            self.assertEqual(len(db.execute(select(checkpoints)).all()),1)
            self.assertTrue(Store(db).all_plans())

    def test_reset_imports_original_snapshot_and_preserves_other_fields(self):
        from backend.services.transport_reset import save_baseline
        with self.sessions.begin() as db:
            original=snapshot(db)
            command(db,{'type':'assign','tripId':'TR-1','vehicleId':'AMB-1'})
            command(db,{'type':'simulation','running':True,'speed':15})
            save_baseline(db,original)
            Store(db).update_source(ambulances,'ambulance_id','AMB-1',unit_name='Updated name')
            Store(db).update_source(requests,'request_id','TR-1',pickup_address='Updated address')
        response=self.client().post('/transport/commands',json={'type':'reset'})
        self.assertEqual(response.status_code,200,response.text)
        self.assertEqual(response.json()['directory']['ambulances'][0]['unit_name'],'Updated name')
        self.assertEqual(response.json()['directory']['transport_requests'][0]['pickup_address'],'Updated address')
        self.assertIsNone(response.json()['directory']['transport_requests'][0]['ambulance_id'])


    def test_worker_startup_pauses_previous_run_until_explicit_resume(self):
        from backend.transport_runtime import main
        with self.sessions.begin() as db:
            command(db, {'type':'simulation','running':True,'speed':60})
            before=Store(db).source()
            minute=Store(db).clock()['minute']
        observed=[]
        def check_tick(db):
            clock=Store(db).clock()
            observed.append(clock['running'])
            self.assertEqual(clock['speed'],15)
            tick(db,utc(clock['wall_at'])+timedelta(seconds=60))
            self.assertEqual(Store(db).source(),before)
            self.assertEqual(Store(db).clock()['minute'],minute)
        with patch('backend.transport_runtime.SessionLocal',self.sessions), \
             patch('sys.argv',['transport_runtime','run','--speed','15']), \
             patch('backend.transport_runtime.tick',side_effect=check_tick), \
             patch('backend.transport_runtime.time.sleep',side_effect=KeyboardInterrupt), \
             patch('builtins.print'):
            main()
        self.assertEqual(observed,[False])
        with self.sessions.begin() as db:
            command(db,{'type':'simulation','running':True})
            self.assertTrue(Store(db).clock()['running'])


    def test_snapshot_publishes_only_remaining_route_and_leg(self):
        with self.sessions.begin() as db:
            store=Store(db)
            command(db,{'type':'assign','tripId':'TR-1','vehicleId':'AMB-1'})
            full=store.all_plans()['TR-1']['body']['approach']['path']
            def move(minutes):
                clock=store.clock()
                advance(store,clock,minutes)
                store.save_clock(clock)
                return snapshot(db)['vehicles'][0]
            v=move(.75)
            self.assertEqual(v['routePhase'],'pickup')
            self.assertEqual(v['route'][0],v['position'])
            self.assertEqual(v['route'][-1],full[-1])
            self.assertNotIn(full[0],v['route'])
            self.assertNotIn(full[1],v['route'])
            self.assertEqual(store.all_plans()['TR-1']['body']['approach']['path'],full)
            v=move(.25)
            self.assertEqual(v['routePhase'],'stopped')
            self.assertNotIn('route',v)
            v=move(2.25)
            self.assertEqual(v['routePhase'],'dropoff')
            self.assertEqual(v['route'][0],v['position'])
            v=move(.75)
            self.assertEqual(v['routePhase'],'stopped')
            self.assertNotIn('route',v)
            v=move(2)
            self.assertNotIn('route',v)
            self.assertNotIn('tripId',v)

    def test_one_ambulance_per_request_but_distinct_patients_can_share_facility(self):
        c=self.client()
        self.assertEqual(c.post('/transport/commands',json={'type':'assign','tripId':'TR-1','vehicleId':'AMB-1'}).status_code,200)
        self.assertEqual(c.post('/transport/commands',json={'type':'assign','tripId':'TR-1','vehicleId':'AMB-2'}).status_code,409)
        self.assertEqual(c.post('/transport/commands',json={'type':'assign','tripId':'TR-2','vehicleId':'AMB-2'}).status_code,200)
        with self.sessions() as db:
            s=snapshot(db)
            self.assertEqual(s['trips'][0]['pickup'],s['trips'][1]['pickup'])
            self.assertEqual(s['trips'][0]['vehicleId'],'AMB-1')
            self.assertEqual(s['trips'][1]['vehicleId'],'AMB-2')

    def test_routes_rebuild_after_external_assignment_or_leg_change(self):
        with self.sessions.begin() as db:
            store=Store(db)
            command(db,{'type':'assign','tripId':'TR-1','vehicleId':'AMB-1'})
            store.update_source(requests,'request_id','TR-1',ambulance_id='AMB-2',status='transporting')
            store.update_source(ambulances,'ambulance_id','AMB-1',status='available')
            store.update_source(ambulances,'ambulance_id','AMB-2',status='transporting')
            command(db,{'type':'routes'})
            row=store.all_plans()['TR-1']
            self.assertEqual(row['vehicle_id'],'AMB-2')
            self.assertEqual(row['body']['stage'],'onboard')
            s=snapshot(db)
            self.assertNotIn('route',s['vehicles'][0])
            self.assertEqual(s['vehicles'][1]['routePhase'],'dropoff')


    def test_automatic_transfer_chooses_fastest_road_candidate(self):
        with self.sessions.begin() as db:
            store=Store(db)
            unit=dict(store.source()[0][1])
            unit.update(ambulance_id='AMB-3',current_lat=42.75)
            db.execute(insert(ambulances).values(**unit))
            command(db,{'type':'assign','tripId':'TR-1','vehicleId':'AMB-1'})
            clock=store.clock();advance(store,clock,3.5);store.save_clock(clock)
            def timed_route(start,end):
                result=road(start,end)
                result['durationSeconds']=20 if start[0]==42.75 else 60
                return result
            with patch('backend.services.transport_planner.get_road_route',side_effect=timed_route):
                command(db,{'type':'outage','vehicleId':'AMB-1'})
            self.assertEqual(snapshot(db)['trips'][0]['vehicleId'],'AMB-3')

    def test_failed_transfer_routing_preserves_patient_and_can_retry(self):
        with self.sessions.begin() as db:
            store=Store(db)
            command(db,{'type':'assign','tripId':'TR-1','vehicleId':'AMB-1'})
            clock=store.clock();advance(store,clock,3.5);store.save_clock(clock)
            stopped=snapshot(db)['vehicles'][0]['position']
            with patch('backend.services.transport_planner.get_road_route',side_effect=RoutingError('offline')):
                command(db,{'type':'outage','vehicleId':'AMB-1'})
            trip=snapshot(db)['trips'][0]
            self.assertEqual(trip['status'],'transfer')
            self.assertEqual(trip['transferLocation'],stopped)
            self.assertNotIn('vehicleId',trip)
            command(db,{'type':'optimize'})
            self.assertEqual(snapshot(db)['trips'][0]['vehicleId'],'AMB-2')

    def test_automatic_transfer_does_not_interrupt_active_patient(self):
        with self.sessions.begin() as db:
            store=Store(db)
            command(db,{'type':'assign','tripId':'TR-1','vehicleId':'AMB-1'})
            command(db,{'type':'assign','tripId':'TR-2','vehicleId':'AMB-2'})
            clock=store.clock();advance(store,clock,3.5);store.save_clock(clock)
            command(db,{'type':'outage','vehicleId':'AMB-1'})
            s=snapshot(db)
            self.assertEqual(s['trips'][0]['status'],'transfer')
            self.assertEqual(s['trips'][1]['vehicleId'],'AMB-2')
            self.assertEqual(s['vehicles'][1]['tripId'],'TR-2')


    def test_replacement_outage_keeps_patient_at_original_transfer_location(self):
        with self.sessions.begin() as db:
            store=Store(db)
            command(db,{'type':'assign','tripId':'TR-1','vehicleId':'AMB-1'})
            clock=store.clock();advance(store,clock,3.5);store.save_clock(clock)
            stopped=snapshot(db)['vehicles'][0]['position']
            command(db,{'type':'outage','vehicleId':'AMB-1'})
            self.assertEqual(snapshot(db)['trips'][0]['vehicleId'],'AMB-2')
            command(db,{'type':'outage','vehicleId':'AMB-2'})
            trip=snapshot(db)['trips'][0]
            self.assertEqual(trip['status'],'transfer')
            self.assertEqual(trip['transferLocation'],stopped)


    def test_reset_prepares_active_routes_without_advancing_or_resuming(self):
        from backend.services.transport_reset import save_baseline
        with self.sessions.begin() as db:
            command(db,{'type':'assign','tripId':'TR-1','vehicleId':'AMB-1'})
            save_baseline(db)
            before=snapshot(db)
        response=self.client().post('/transport/commands',json={'type':'reset'})
        self.assertEqual(response.status_code,200,response.text)
        after=response.json()
        self.assertGreater(len(after['vehicles'][0]['route']),1)
        self.assertEqual(after['vehicles'][0]['position'],before['vehicles'][0]['position'])
        self.assertEqual(after['minute'],before['minute'])
        self.assertFalse(after['integration']['running'])

    def test_reset_survives_unavailable_routing_with_visible_retry_message(self):
        from backend.services.transport_reset import save_baseline
        with self.sessions.begin() as db:
            command(db,{'type':'assign','tripId':'TR-1','vehicleId':'AMB-1'})
            save_baseline(db)
        with patch('backend.services.transport_planner.get_road_route',side_effect=RoutingError('offline')):
            response=self.client().post('/transport/commands',json={'type':'reset'})
        self.assertEqual(response.status_code,200,response.text)
        after=response.json()
        self.assertFalse(after['integration']['running'])
        self.assertTrue(any('Road routes could not be prepared' in e for e in after['events']))
        self.assertEqual(after['trips'][0]['vehicleId'],'AMB-1')


    def test_planner_balances_twelve_feasible_calls_and_outage_preserves_them(self):
        from collections import Counter
        with self.sessions.begin() as db:
            store=Store(db)
            template=dict(store.source()[1][0])
            for i in range(4,13):
                trip={**template,'request_id':f'TR-{i}','patient_id':f'PAT-{i}',
                      'pickup_time':NOW+timedelta(minutes=(i-1)*10)}
                db.execute(insert(requests).values(**trip))
            command(db,{'type':'optimize'})
            trips=store.source()[1]
            counts=Counter(t['ambulance_id'] for t in trips)
            self.assertEqual(counts,{'AMB-1':6,'AMB-2':6})
            command(db,{'type':'outage','vehicleId':'AMB-1'})
            trips=store.source()[1]
            self.assertEqual(len(trips),12)
            self.assertTrue(all(t['status']=='scheduled' for t in trips))
            self.assertTrue(all(t['ambulance_id']=='AMB-2' for t in trips))

    def test_balancing_does_not_assign_ineligible_units(self):
        with self.sessions.begin() as db:
            store=Store(db)
            store.update_source(ambulances,'ambulance_id','AMB-2',crew_count=0)
            command(db,{'type':'optimize'})
            self.assertTrue(all(t['ambulance_id']=='AMB-1' for t in store.source()[1]))

    def test_balancing_does_not_sacrifice_pickup_punctuality(self):
        with self.sessions.begin() as db:
            store=Store(db)
            # The idle second unit is too far away for the first two pickups.
            def matrix(locations):
                return [[0 if a==b else (3600 if a[0]>42.7015 and a[0]<42.703 else 60) for b in locations] for a in locations]
            with patch('backend.services.transport_planner.get_time_matrix',side_effect=matrix):
                command(db,{'type':'optimize'})
            trips=store.source()[1]
            self.assertEqual(trips[0]['ambulance_id'],'AMB-1')
            self.assertEqual(trips[1]['ambulance_id'],'AMB-1')


    def test_real_service_cycle_and_job_timer_exclude_idle_time(self):
        with patch.multiple('backend.services.transport_timing',LOAD_MINUTES=15.0,HANDOFF_MINUTES=32.0,RESET_MINUTES=5.0):
            with self.sessions.begin() as db:
                store=Store(db)
                def move(minutes):
                    clock=store.clock();advance(store,clock,minutes);store.save_clock(clock)
                    return snapshot(db)
                idle=move(100)
                self.assertEqual(idle['timeSavings']['activeJobMinutes'],0)
                command(db,{'type':'assign','tripId':'TR-1','vehicleId':'AMB-1'})
                self.assertEqual(store.all_plans()['TR-1']['body']['predictedAvailable'],154)
                self.assertEqual(move(1)['vehicles'][0]['activity'],'Loading patient')
                self.assertEqual(move(15)['trips'][0]['status'],'onboard')
                self.assertEqual(move(1)['vehicles'][0]['activity'],'Handoff and paperwork')
                self.assertEqual(move(32)['vehicles'][0]['activity'],'Resetting for next job')
                s=move(5)
                m=s['timeSavings']
                self.assertEqual(m['completedJobs'],1)
                self.assertEqual(m['completedJobMinutes'],54)
                self.assertEqual(m['netMinutesSaved'],21)
                self.assertEqual(m['activeJobMinutes'],0)
                self.assertEqual(move(100)['timeSavings'],m)

    def test_future_queue_wait_does_not_start_job_timer(self):
        with self.sessions.begin() as db:
            store=Store(db)
            for t in store.source()[1]:
                store.update_source(requests,'request_id',t['request_id'],pickup_time=NOW+timedelta(minutes=120))
            command(db,{'type':'optimize'})
            clock=store.clock();advance(store,clock,20);store.save_clock(clock)
            m=snapshot(db)['timeSavings']
            self.assertEqual(m['activeJobs'],0)
            self.assertEqual(m['activeJobMinutes'],0)

    def test_segment_timing_changes_speed_along_equal_length_roads(self):
        route={'path':[[0,0],[0,1],[0,2]],'segmentDurationsSeconds':[90,10]}
        p,i=location(route,.5)
        self.assertEqual(i,0)
        self.assertAlmostEqual(p[1],50/90)
        p,i=location(route,.95)
        self.assertEqual(i,1)
        self.assertAlmostEqual(p[1],1.5)

    def test_metrics_show_over_baseline_and_exclude_unknown_start(self):
        from backend.services.transport_timing import metrics
        rows={'a':{'body':{'stage':'complete','jobStarted':10,'jobEnded':100}},
              'b':{'body':{'stage':'complete','jobEnded':100}},
              'c':{'body':{'stage':'queued','stageStarted':200}}}
        result=metrics(rows,150)
        self.assertEqual(result['completedJobs'],1)
        self.assertEqual(result['netMinutesSaved'],-15)
        self.assertEqual(result['activeJobMinutes'],0)


if __name__=='__main__': unittest.main()
