"""Additive API for the real Tiger Data directory, separate from legacy routes."""
from typing import Literal
from fastapi import APIRouter, Depends, HTTPException, Query, Response
from pydantic import BaseModel, ConfigDict, Field, model_validator
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session
from backend.database import get_db
from backend.transport_store import Store, TransportError, positions
from backend.services.osrm import get_road_route, RoutingError
from backend.services.transport_snapshot import snapshot
from backend.services.transport_commands import command

def no_cache(response: Response):
    response.headers['Cache-Control']='no-store'


router=APIRouter(tags=['Tiger Data transport'],dependencies=[Depends(no_cache)])


class TransportCommand(BaseModel):
    model_config=ConfigDict(extra='forbid')
    type: Literal['assign','optimize','routes','outage','restore','delay','traffic','simulation','reset']
    tripId: str | None = Field(default=None,min_length=1,max_length=200)
    vehicleId: str | None = Field(default=None,min_length=1,max_length=200)
    minutes: float | None = Field(default=None,gt=0,le=240,allow_inf_nan=False)
    enabled: bool | None = None
    running: bool | None = None
    speed: float | None = Field(default=None,gt=0,le=120,allow_inf_nan=False)

    @model_validator(mode='after')
    def required_fields(self):
        required={'assign':{'tripId','vehicleId'},'outage':{'vehicleId'},'restore':{'vehicleId'},
            'delay':{'vehicleId','minutes'},'traffic':{'enabled'},'simulation':{'running'}}.get(self.type,set())
        allowed=required | ({'speed'} if self.type=='simulation' else set()) | {'type'}
        present={key for key,value in self.model_dump().items() if value is not None}
        if not required<=present: raise ValueError('Missing fields: '+', '.join(sorted(required-present)))
        if present-allowed: raise ValueError('Fields not applicable to this command: '+', '.join(sorted(present-allowed)))
        return self


def _read(db,operation):
    try:
        if db.bind.dialect.name=='postgresql':
            db.connection().exec_driver_sql('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY')
        return operation()
    except TransportError as exc:
        raise HTTPException(exc.status,str(exc)) from exc
    except RoutingError as exc:
        raise HTTPException(502,str(exc)) from exc
    except SQLAlchemyError as exc:
        raise HTTPException(503,'Tiger Data is unavailable or required transport tables are missing.') from exc
    except (TypeError,ValueError) as exc:
        raise HTTPException(422,'Transport records contain missing or invalid data.') from exc


@router.get('/transport/state')
@router.get('/transport/snapshot',include_in_schema=False)
def get_state(db: Session=Depends(get_db)):
    return _read(db,lambda:snapshot(db))


@router.get('/transport/directory')
def get_directory(db: Session=Depends(get_db)):
    return _read(db,lambda:snapshot(db)['directory'])


@router.get('/vehicles')
def get_vehicles(db: Session=Depends(get_db)):
    return _read(db,lambda:snapshot(db)['vehicles'])


@router.get('/transport/routes/{vehicle_id}/{trip_id}')
def preview_route(vehicle_id: str,trip_id: str,db: Session=Depends(get_db)):
    def read():
        units,trips=Store(db).source()
        vehicle=next((v for v in units if v['ambulance_id']==vehicle_id),None)
        trip=next((t for t in trips if t['request_id']==trip_id),None)
        if not vehicle or not trip: raise TransportError('Ambulance or transport not found.',404)
        route=get_road_route([vehicle['current_lat'],vehicle['current_lng']],[trip['pickup_lat'],trip['pickup_lng']])
        return {'vehicleId':vehicle_id,'tripId':trip_id,'route':route['path'],
            'durationSeconds':route['durationSeconds'],'distanceMeters':route['distanceMeters']}
    return _read(db,read)


@router.get('/transport/positions/{vehicle_id}')
def get_positions(vehicle_id: str,limit: int=Query(default=100,ge=1,le=1000),db: Session=Depends(get_db)):
    def read():
        store=Store(db)
        if not store.ready(): return []
        return [dict(r) for r in db.execute(select(positions).where(positions.c.vehicle_id==vehicle_id)
            .order_by(positions.c.recorded_at.desc()).limit(limit)).mappings()]
    return _read(db,read)


@router.post('/transport/commands')
def transport_command(payload: TransportCommand,db: Session=Depends(get_db)):
    try:
        command(db,payload.model_dump(exclude_none=True))
        result=snapshot(db)
        db.commit()
        return result
    except TransportError as exc:
        db.rollback()
        raise HTTPException(exc.status,str(exc)) from exc
    except RoutingError as exc:
        db.rollback()
        raise HTTPException(502,str(exc)) from exc
    except SQLAlchemyError as exc:
        db.rollback()
        raise HTTPException(503,'Tiger Data command failed and was rolled back.') from exc


@router.get('/transport/diagnostics')
def diagnostics(db: Session=Depends(get_db)):
    def read():
        result=snapshot(db)
        return {**result['integration'],'ambulances':len(result['vehicles']),'requests':len(result['trips']),
            'clockMinute':result['minute'],'workerRequired':True,
            'workerCommand':'python -m backend.transport_runtime run --speed 15'}
    return _read(db,read)
