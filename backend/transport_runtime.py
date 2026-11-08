"""Explicit, additive schema initialization and a separate server simulation worker.

python -m backend.transport_runtime init
python -m backend.transport_runtime run --speed 15
"""
import argparse
from datetime import datetime, timezone
import logging
import time
from backend.database import engine, SessionLocal
from backend.transport_store import Store, storage_metadata, utc
from backend.services.transport_commands import initialize
from backend.services.transport_motion import advance

log=logging.getLogger(__name__)


def tick(db,now=None):
    store=Store(db)
    clock=store.clock(lock=True)
    now=max(utc(now or datetime.now(timezone.utc)),utc(clock['wall_at']))
    elapsed=max(0,(now-utc(clock['wall_at'])).total_seconds())
    if clock['running'] and elapsed:
        advance(store,clock,elapsed*clock['speed']/60)
    clock['wall_at']=now
    clock['worker_at']=now
    store.save_clock(clock)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('operation',choices=['init','run','baseline'])
    parser.add_argument('--speed',type=float,default=1)
    parser.add_argument('--snapshot', help='Saved transport snapshot to import as the immutable reset baseline')
    args=parser.parse_args()
    if not 0<args.speed<=120: parser.error('speed must be between 0 and 120')
    if args.operation=='baseline':
        import json
        from pathlib import Path
        from backend.services.transport_reset import save_baseline
        imported=json.loads(Path(args.snapshot).read_text(encoding='utf-8-sig')) if args.snapshot else None
        with SessionLocal.begin() as db: save_baseline(db,imported)
        print('Reset baseline saved in Tiger Data. Live positions and assignments were not changed.')
        return
    if args.operation=='init':
        # Only the additive belos_transport_* tables are created; existing records
        # and the original backend metadata are never dropped, seeded or copied.
        storage_metadata.create_all(engine)
        with SessionLocal.begin() as db: initialize(db)
        print('Transport extension initialized. Existing Tiger Data records and runtime state preserved; new simulations start paused.')
        return
    with SessionLocal.begin() as db:
        store=Store(db)
        clock=store.clock(lock=True)
        clock.update(running=False,speed=args.speed,wall_at=datetime.now(timezone.utc))
        store.save_clock(clock)
    print('Backend worker ready; simulation paused. Click Start backend simulation in the dashboard to begin. Ctrl+C stops the worker.')
    try:
        while True:
            try:
                with SessionLocal.begin() as db: tick(db)
            except Exception as exc:
                # Do not print connection strings or database response contents.
                log.error('Simulation tick rolled back (%s).',type(exc).__name__)
                # Pause after failure; explicit resume is required to retry.
                with SessionLocal.begin() as db:
                    store=Store(db)
                    clock=store.clock(lock=True)
                    clock.update(running=False,wall_at=datetime.now(timezone.utc))
                    store.save_clock(clock)
                    store.event(clock['minute'],'Simulation paused after a worker error; check routing/database availability before resuming.')
            time.sleep(1)
    except KeyboardInterrupt:
        with SessionLocal.begin() as db:
            store=Store(db)
            clock=store.clock(lock=True)
            clock['running']=False
            store.save_clock(clock)


if __name__=='__main__': main()
