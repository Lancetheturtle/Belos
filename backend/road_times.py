"""Road travel times and geometry. Never substitute straight-line estimates."""

from copy import deepcopy
from functools import lru_cache
import json
import math
import os
from urllib.error import HTTPError, URLError
from urllib.request import urlopen


class RoutingUnavailable(RuntimeError):
    pass


class NoRoute(RoutingUnavailable):
    pass


class RoadRouter:
    def __init__(self, base=None):
        self.base = (
            base or os.getenv("OSRM_URL", "https://router.project-osrm.org")
        ).rstrip("/")

    def _get(self, path):
        try:
            with urlopen(self.base + path, timeout=5) as response:
                data = json.load(response)
        except HTTPError as exc:
            try:
                if json.load(exc).get("code") in {"NoRoute", "NoTable", "NoSegment"}:
                    raise NoRoute("No drivable road route.") from exc
            except (ValueError, AttributeError):
                pass
            raise RoutingUnavailable("Road routing service failed.") from exc
        except (URLError, TimeoutError, OSError, ValueError) as exc:
            raise RoutingUnavailable(
                "Road routing unavailable; previous plan retained."
            ) from exc
        if data.get("code") != "Ok":
            raise RoutingUnavailable("Road routing returned an invalid response.")
        return data

    def matrix(self, origins, destinations):
        points = origins + destinations
        coordinates = ";".join(f"{p[1]},{p[0]}" for p in points)
        sources = ";".join(str(i) for i in range(len(origins)))
        targets = ";".join(str(i + len(origins)) for i in range(len(destinations)))
        data = self._get(
            f"/table/v1/driving/{coordinates}?sources={sources}&destinations={targets}&annotations=duration"
        )
        rows = data.get("durations")
        if not isinstance(rows, list) or len(rows) != len(origins):
            raise RoutingUnavailable("Invalid road-time matrix.")
        if any(
            not isinstance(row, list) or len(row) != len(destinations) for row in rows
        ):
            raise RoutingUnavailable("Invalid road-time matrix shape.")
        if any(
            value is not None
            and (
                not isinstance(value, (int, float))
                or not math.isfinite(value)
                or value < 0
            )
            for row in rows
            for value in row
        ):
            raise RoutingUnavailable("Invalid road travel time.")
        return [
            [None if value is None else value / 60 for value in row] for row in rows
        ]

    def route(self, origin, destination):
        return deepcopy(self._route(tuple(origin), tuple(destination)))

    @lru_cache(maxsize=512)
    def _route(self, origin, destination):
        coordinates = f"{origin[1]},{origin[0]};{destination[1]},{destination[0]}"
        data = self._get(
            f"/route/v1/driving/{coordinates}?overview=full&geometries=geojson&annotations=duration"
        )
        try:
            route = data["routes"][0]
            points = [[p[1], p[0]] for p in route["geometry"]["coordinates"]]
            seconds = route["legs"][0]["annotation"]["duration"]
            duration = float(route["duration"])
            if len(seconds) != len(points) - 1 or not seconds:
                raise ValueError("Geometry and segment times differ")
            if (
                not math.isfinite(duration)
                or duration < 0
                or any(not math.isfinite(x) or x < 0 for x in seconds)
            ):
                raise ValueError("Invalid duration")
            # Include turn costs, absent from segment annotations, proportionally.
            scale = duration / sum(seconds) if sum(seconds) else 1
            times = [x * scale / 60 for x in seconds]
            if not sum(seconds) and duration:
                times = [duration / 60 / len(seconds)] * len(seconds)
            return {"points": points, "times": times, "minutes": duration / 60}
        except (KeyError, IndexError, TypeError, ValueError) as exc:
            raise RoutingUnavailable(
                "Invalid road geometry or segment timings."
            ) from exc
