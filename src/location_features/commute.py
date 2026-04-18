"""Function 1 — commute: distance + transit/car/bike/foot minutes between 2 points.

Two implementations, selected at runtime:

1. **r5py** (preferred): real multimodal routing over `switzerland-latest.osm.pbf`
   + GTFS. Matches Google Maps quality for Switzerland; free and local.
2. **proxy** (fallback): Haversine distance divided by mode-specific speed,
   transit approximated by nearest-SBB-stop + great-circle vehicle leg.

The r5py network is built once from OSM + GTFS (~5 min, one-time) and
cached to `~/Library/Caches/r5py/` as a 2.2 GB blob. Subsequent fresh
processes load the cache in ~28 s. Warm calls within the same process
take ~8 s. If `r5py` or Java isn't installed, we silently fall back to
the proxy.

Data files (from ~/datathon_prep/):
  - osm/switzerland-latest.osm.pbf       (walk/bike/car network)
  - gtfs/ch_gtfs_2026_latest.zip         (full Swiss timetable, transit)
  - gtfs/unzipped/stops.txt              (fallback: nearest-stop heuristic)
"""

from __future__ import annotations

import datetime as dt
import math
from functools import lru_cache
from typing import Any

from . import paths


# ---------------------------------------------------------------------------
# Geometry helpers
# ---------------------------------------------------------------------------

EARTH_RADIUS_KM = 6371.0


def haversine_km(a: tuple[float, float], b: tuple[float, float]) -> float:
    """Great-circle distance in km between two (lat, lon) points."""
    lat1, lon1 = a
    lat2, lon2 = b
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlam = math.radians(lon2 - lon1)
    h = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlam / 2) ** 2
    return 2 * EARTH_RADIUS_KM * math.asin(math.sqrt(h))


# ---------------------------------------------------------------------------
# r5py network — lazy singleton
# ---------------------------------------------------------------------------

_NETWORK: Any = None
_NETWORK_FAILED = False


def _get_network() -> Any:
    """Build the r5py TransportNetwork once. Returns None if r5py unavailable."""
    global _NETWORK, _NETWORK_FAILED
    if _NETWORK is not None or _NETWORK_FAILED:
        return _NETWORK

    try:
        # Reduce JVM signal usage. Without this, JPype's signal handlers
        # collide with Python's and macOS shows "Python quit unexpectedly"
        # when the process exits.  Must be set before the JVM starts.
        import os as _os

        prev = _os.environ.get("JAVA_TOOL_OPTIONS", "")
        if "-Xrs" not in prev:
            _os.environ["JAVA_TOOL_OPTIONS"] = (prev + " -Xrs").strip()

        from r5py import TransportNetwork  # type: ignore

        paths.require(paths.OSM_PBF)
        paths.require(paths.GTFS_ZIP)
        _NETWORK = TransportNetwork(
            osm_pbf=str(paths.OSM_PBF),
            gtfs=[str(paths.GTFS_ZIP)],
        )
        return _NETWORK
    except Exception as exc:  # ImportError, Java missing, OOM...
        _NETWORK_FAILED = True
        print(f"[commute] r5py unavailable ({type(exc).__name__}: {exc}); using proxy.")
        return None


def _default_departure() -> dt.datetime:
    """Next Tuesday 08:30 local — representative commuter window."""
    now = dt.datetime.now()
    days_ahead = (1 - now.weekday()) % 7 or 7  # 1 = Tuesday
    target = (now + dt.timedelta(days=days_ahead)).replace(
        hour=8, minute=30, second=0, microsecond=0
    )
    return target


# ---------------------------------------------------------------------------
# r5py query wrapper
# ---------------------------------------------------------------------------


def _r5_travel_time(
    network: Any,
    origin: tuple[float, float],
    destination: tuple[float, float],
    modes: list[Any],
    departure: dt.datetime,
    max_minutes: int = 180,
) -> int | None:
    """Return travel time in whole minutes, or None if unroutable."""
    import geopandas as gpd  # type: ignore
    from r5py import TravelTimeMatrix  # type: ignore
    from shapely.geometry import Point  # type: ignore

    o = gpd.GeoDataFrame(
        {"id": [0], "geometry": [Point(origin[1], origin[0])]}, crs="EPSG:4326"
    )
    d = gpd.GeoDataFrame(
        {"id": [1], "geometry": [Point(destination[1], destination[0])]}, crs="EPSG:4326"
    )
    m = TravelTimeMatrix(
        network,
        origins=o,
        destinations=d,
        departure=departure,
        transport_modes=modes,
        max_time=dt.timedelta(minutes=max_minutes),
    )
    if m.empty or m["travel_time"].isna().all():
        return None
    val = m["travel_time"].iloc[0]
    return int(val) if val == val else None  # NaN check


def _commute_r5(
    origin: tuple[float, float],
    destination: tuple[float, float],
    departure: dt.datetime,
) -> dict[str, Any] | None:
    net = _get_network()
    if net is None:
        return None
    try:
        from r5py import TransportMode  # type: ignore
    except Exception:
        return None

    return {
        "distance_km": round(haversine_km(origin, destination), 3),
        "transit_min": _r5_travel_time(
            net, origin, destination,
            [TransportMode.TRANSIT, TransportMode.WALK], departure,
        ),
        "car_min": _r5_travel_time(
            net, origin, destination, [TransportMode.CAR], departure,
        ),
        "bike_min": _r5_travel_time(
            net, origin, destination, [TransportMode.BICYCLE], departure, max_minutes=240,
        ),
        "foot_min": _r5_travel_time(
            net, origin, destination, [TransportMode.WALK], departure, max_minutes=600,
        ),
        "source": "r5py",
    }


# ---------------------------------------------------------------------------
# Proxy fallback
# ---------------------------------------------------------------------------


@lru_cache(maxsize=1)
def _gtfs_stops() -> list[tuple[str, float, float]]:
    """Return (name, lat, lon) for every GTFS stop. Tiny file, ~30k rows."""
    import csv

    paths.require(paths.GTFS_STOPS_TXT)
    stops: list[tuple[str, float, float]] = []
    with open(paths.GTFS_STOPS_TXT, encoding="utf-8") as f:
        for row in csv.DictReader(f):
            try:
                stops.append((row["stop_name"], float(row["stop_lat"]), float(row["stop_lon"])))
            except (KeyError, ValueError):
                continue
    return stops


def _nearest_stop(point: tuple[float, float]) -> tuple[str, float, float, float]:
    """(name, lat, lon, distance_km) of nearest GTFS stop."""
    best = min(_gtfs_stops(), key=lambda s: haversine_km(point, (s[1], s[2])))
    return best[0], best[1], best[2], haversine_km(point, (best[1], best[2]))


def _commute_proxy(
    origin: tuple[float, float],
    destination: tuple[float, float],
) -> dict[str, Any]:
    d_km = haversine_km(origin, destination)

    # Mode-specific speeds tuned to Swiss urban/suburban reality.
    # These are coarse — r5py is strictly better when available.
    foot_min = round(d_km / 5.0 * 60)
    bike_min = round(d_km / 15.0 * 60)
    car_kmh = 35.0 if d_km < 5 else 60.0 if d_km < 30 else 80.0
    car_min = round(d_km / car_kmh * 60)

    # Transit proxy: walk-to-stop + in-vehicle (avg 45 km/h) + walk-from-stop.
    # Falls back gracefully if GTFS file missing.
    try:
        _, o_lat, o_lon, o_walk_km = _nearest_stop(origin)
        _, _, _, d_walk_km = _nearest_stop(destination)
        vehicle_km = max(0.0, d_km - o_walk_km - d_walk_km)
        transit_min = round(
            (o_walk_km + d_walk_km) / 5.0 * 60  # walk legs
            + vehicle_km / 45.0 * 60             # in-vehicle
            + 3                                   # wait buffer
        )
    except FileNotFoundError:
        transit_min = None

    return {
        "distance_km": round(d_km, 3),
        "transit_min": transit_min,
        "car_min": car_min,
        "bike_min": bike_min,
        "foot_min": foot_min,
        "source": "proxy",
    }


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def commute(
    origin: tuple[float, float],
    destination: tuple[float, float],
    departure_time: dt.datetime | None = None,
) -> dict[str, Any]:
    """Return distance (km) + estimated travel times in minutes for 4 modes.

    Parameters
    ----------
    origin, destination : (lat, lon) tuples in WGS84.
    departure_time : used only for transit timetables; defaults to next Tue 08:30.

    Returns
    -------
    dict with keys distance_km, transit_min, car_min, bike_min, foot_min, source.
    Any unroutable mode is `None` (never raises for unroutable queries).
    """
    dep = departure_time or _default_departure()
    r5 = _commute_r5(origin, destination, dep)
    if r5 is not None:
        return r5
    return _commute_proxy(origin, destination)
