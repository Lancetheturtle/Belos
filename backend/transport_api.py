"""Single-process hackathon dispatch API with an independent simulation clock."""

import asyncio
from contextlib import asynccontextmanager, contextmanager
from copy import deepcopy
import json
import logging
import os
from pathlib import Path
import sqlite3
from threading import RLock
from typing import Annotated, Literal, Union

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from .diagnostics import live_diagnostics
from .service_times import MODEL
from pydantic import BaseModel, ConfigDict, Field, AwareDatetime
from typing import Tuple

from .dispatch_engine import action, advance, public_snapshot, safe_replan
from .road_times import RoadRouter, RoutingUnavailable

ROOT = Path(__file__).resolve().parent.parent
logger = logging.getLogger(__name__)


class Payload(BaseModel):
    model_config = ConfigDict(extra="forbid")


Latitude = Annotated[float, Field(ge=-90, le=90, allow_inf_nan=False)]
Longitude = Annotated[float, Field(ge=-180, le=180, allow_inf_nan=False)]


class CreateCall(Payload):
    type: Literal["create-call"]
    requestKey: str = Field(min_length=8, max_length=80)
    pickupName: str = Field(min_length=1, max_length=120)
    destinationName: str = Field(min_length=1, max_length=120)
    pickup: Tuple[Latitude, Longitude]
    destination: Tuple[Latitude, Longitude]
    pickupInMinutes: float = Field(ge=0, le=1440, allow_inf_nan=False)


class ReportStatus(Payload):
    type: Literal["report-status"]
    vehicleId: str
    status: Literal["available", "unavailable", "out_of_service"]
    observedAt: AwareDatetime


class UnitAction(Payload):
    type: Literal["delay", "emergency", "outage", "restore"]
    vehicleId: str


class AssignAction(Payload):
    type: Literal["assign"]
    vehicleId: str
    tripId: str


class TrafficAction(Payload):
    type: Literal["traffic"]
    enabled: bool


class TrafficUpdate(Payload):
    type: Literal["traffic-update"]
    vehicleId: str
    factor: float = Field(ge=1, le=10, allow_inf_nan=False)


class ReplanAction(Payload):
    type: Literal["reoptimize"]


class SpeedAction(Payload):
    type: Literal["set-speed"]
    speed: int = Field(ge=1, le=60, strict=True)


class AdvanceAction(Payload):
    type: Literal["advance"]
    minutes: float = Field(gt=0, le=60, allow_inf_nan=False)


Action = Annotated[
    Union[
        UnitAction,
        AssignAction,
        TrafficAction,
        TrafficUpdate,
        ReplanAction,
        AdvanceAction,
        SpeedAction,
        CreateCall,
        ReportStatus,
    ],
    Field(discriminator="type"),
]


class StateStore:
    """One transactional SQL snapshot, including durable assignment history."""

    def __init__(self, filename):
        self.filename = str(filename)
        Path(filename).parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as db:
            db.execute(
                "CREATE TABLE IF NOT EXISTS dispatch_state (id INTEGER PRIMARY KEY CHECK(id=1), payload TEXT NOT NULL)"
            )

    @contextmanager
    def connect(self):
        db = sqlite3.connect(self.filename, timeout=5)
        try:
            with db:
                yield db
        finally:
            db.close()

    def load(self):
        with self.connect() as db:
            row = db.execute("SELECT payload FROM dispatch_state WHERE id=1").fetchone()
        return json.loads(row[0]) if row else None

    def save(self, state):
        with self.connect() as db:
            db.execute(
                "INSERT INTO dispatch_state(id,payload) VALUES(1,?) ON CONFLICT(id) DO UPDATE SET payload=excluded.payload",
                (json.dumps(state, allow_nan=False),),
            )


class DispatchService:
    def __init__(self, router, store, seed=None):
        self.router, self.store = router, store
        self.seed = seed or json.loads(
            (Path(__file__).with_name("transport_seed.json")).read_text()
        )
        self.state = store.load()
        self.lock = RLock()
        self.retry_ticks = 0

    def commit(self, state):
        # Reject inconsistent assignments before persisting any update.
        assigned = [v["tripId"] for v in state["vehicles"] if v.get("tripId")]
        if len(assigned) != len(set(assigned)):
            raise ValueError("A transport cannot have two ambulances")
        units = {v["id"]: v for v in state["vehicles"]}
        for trip in state["trips"]:
            if trip["status"] in {"pickup", "onboard"}:
                unit = units.get(trip.get("vehicleId"))
                if (
                    not unit
                    or unit.get("tripId") != trip["id"]
                    or unit["outOfService"]
                    or unit.get("dispatchUnavailable")
                ):
                    raise ValueError("Trip and ambulance assignment disagree")
        self.store.save(state)
        self.state = state
        return public_snapshot(state)

    def reset(self):
        with self.lock:
            state = deepcopy(self.seed)
            state["assignmentHistory"] = []
            state["serviceModel"] = MODEL
            state["trafficFactors"] = {}
            # Initial assignments belong to the planner, not frontend presets.
            for unit in state["vehicles"]:
                unit.pop("tripId", None)
            for trip in state["trips"]:
                trip.pop("vehicleId", None)
                trip["status"] = "waiting"
            safe_replan(state, self.router, "Initial road-time dispatch")
            return self.commit(state)

    def snapshot(self):
        with self.lock:
            return (
                public_snapshot(self.state) if self.state is not None else self.reset()
            )

    def act(self, payload):
        with self.lock:
            if self.state is None:
                self.reset()
            if payload["type"] == "advance":
                raise ValueError(
                    "The server owns the clock. Use BELOS_SIM_SPEED to set its speed."
                )
            if payload["type"] in {"create-call", "report-status"}:
                from .call_actions import apply_call_action

                return self.commit(apply_call_action(self.state, payload, self.router))
            return self.commit(action(self.state, payload, self.router))

    def tick(self, minutes):
        with self.lock:
            if self.state is None:
                return
            state = advance(self.state, minutes, self.router)
            if state.get("dispatch", {}).get("status") == "routing-unavailable":
                self.retry_ticks += 1
                if self.retry_ticks >= 15:
                    self.retry_ticks = 0
                    safe_replan(
                        state, self.router, "Retry after road service interruption"
                    )
            else:
                self.retry_ticks = 0
            self.commit(state)


def create_app(service=None, speed=None):
    sim_speed = float(os.getenv("BELOS_SIM_SPEED", "15")) if speed is None else speed
    if not 0 <= sim_speed <= 60:
        raise ValueError("BELOS_SIM_SPEED must be between 0 and 60")

    @asynccontextmanager
    async def lifespan(app):
        app.state.simulation_speed = sim_speed
        app.state.dispatch = service or DispatchService(
            RoadRouter(),
            StateStore(
                os.getenv(
                    "BELOS_STATE_DB", str(ROOT / "data/generated/dispatch.sqlite3")
                )
            ),
        )

        async def clock():
            while True:
                await asyncio.sleep(1)
                current_speed = app.state.simulation_speed
                if current_speed:
                    try:
                        # Fixed tick avoids a large movement jump after routing stalls.
                        await asyncio.to_thread(
                            app.state.dispatch.tick, current_speed / 60
                        )
                    except Exception:
                        logger.exception(
                            "Dispatch tick failed; committed state retained"
                        )

        task = asyncio.create_task(clock())
        yield
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass

    app = FastAPI(title="Belos transport dispatch", lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=os.getenv(
            "BELOS_CORS_ORIGINS", "http://127.0.0.1:5173,http://localhost:5173"
        ).split(","),
        # Vite chooses another port when the default is already occupied.
        # An explicit origin list still overrides this local-development default.
        allow_origin_regex=(
            None
            if os.getenv("BELOS_CORS_ORIGINS")
            else r"^http://(?:localhost|127\.0\.0\.1)(?::[0-9]+)?$"
        ),
        allow_methods=["GET", "POST"],
        allow_headers=["Content-Type"],
    )

    @app.get("/health")
    def health():
        return {
            "status": "ok",
            "mode": "single-process simulation",
            "simulationSpeed": app.state.simulation_speed,
        }

    @app.get("/debug", include_in_schema=False)
    def debug_page():
        return FileResponse(
            Path(__file__).with_name("diagnostics.html"),
            headers={"Cache-Control": "no-store"},
        )

    @app.get("/transport/diagnostics")
    def diagnostics():
        return live_diagnostics(
            app.state.dispatch.snapshot(), app.state.simulation_speed
        )

    def with_speed(snapshot):
        return {**snapshot, "simulationSpeed": app.state.simulation_speed}

    @app.get("/transport/state")
    def state():
        return with_speed(app.state.dispatch.snapshot())

    @app.post("/transport/reset")
    def reset():
        return with_speed(app.state.dispatch.reset())

    @app.post("/transport/action")
    def dispatch(payload: Action):
        try:
            if payload.type == "set-speed":
                snapshot = app.state.dispatch.snapshot()
                app.state.simulation_speed = payload.speed
                return with_speed(snapshot)
            return with_speed(app.state.dispatch.act(payload.model_dump(mode="json")))
        except ValueError as exc:
            raise HTTPException(400, str(exc)) from exc
        except RoutingUnavailable as exc:
            raise HTTPException(503, str(exc)) from exc

    return app


app = create_app()
