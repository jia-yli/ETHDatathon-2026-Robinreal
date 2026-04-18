"""Function 2 — amenities: POI counts + nearest-of-each + green share near a point.

Queries two local parquet files via DuckDB (spatial extension). No network I/O.

Data files (from ~/datathon_prep/):
  - processed/ch_pois.parquet         (821K Swiss POIs: amenity/shop/leisure/railway/...)
  - processed/ch_green_water.parquet  (700K green/water polygons + centroids)
"""

from __future__ import annotations

from functools import lru_cache
from typing import Any

import duckdb

from . import paths


# ---------------------------------------------------------------------------
# Category mapping
# ---------------------------------------------------------------------------
# Each key is the public feature name. Value is (column, value-in-column).
# Columns are OSM tag columns from ch_pois.parquet.
CATEGORY_MAP: dict[str, tuple[str, str]] = {
    # Shops & daily essentials
    "supermarket":   ("shop", "supermarket"),
    "convenience":   ("shop", "convenience"),
    "bakery":        ("shop", "bakery"),
    # Food & drink
    "restaurant":    ("amenity", "restaurant"),
    "cafe":          ("amenity", "cafe"),
    "bar":           ("amenity", "bar"),
    # Services
    "pharmacy":      ("amenity", "pharmacy"),
    "bank":          ("amenity", "bank"),
    "hospital":      ("amenity", "hospital"),
    # Education / family
    "school":        ("amenity", "school"),
    "kindergarten":  ("amenity", "kindergarten"),
    "university":    ("amenity", "university"),
    # Leisure / outdoors
    "park":          ("leisure", "park"),
    "playground":    ("leisure", "playground"),
    "sports_centre": ("leisure", "sports_centre"),
    # Transit
    "train_station": ("railway", "station"),
    "tram_stop":     ("railway", "tram_stop"),
    "bus_stop":      ("public_transport", "stop_position"),
}


# ---------------------------------------------------------------------------
# DuckDB connection — lazy singleton
# ---------------------------------------------------------------------------


@lru_cache(maxsize=1)
def _con() -> duckdb.DuckDBPyConnection:
    paths.require(paths.POIS_PARQUET)
    paths.require(paths.GREEN_WATER_PARQUET)

    c = duckdb.connect(":memory:")
    c.execute("INSTALL spatial; LOAD spatial;")

    # POI view — flat table of (col, val, name, lat, lon)
    c.execute(
        f"""
        CREATE VIEW pois AS
        SELECT amenity, shop, leisure, tourism, public_transport, railway,
               sport, healthcare, office, name, lat, lon
        FROM read_parquet('{paths.POIS_PARQUET}')
        WHERE lat IS NOT NULL AND lon IS NOT NULL;
        """
    )

    # Green/water view — precompute a WGS84 geometry so we can do ST_Distance
    # against our query point. The parquet stores WKT strings for polygons
    # and NULL-geometry point rows; we accept both.
    c.execute(
        f"""
        CREATE VIEW gw AS
        SELECT
            green_class,
            name,
            lat,
            lon,
            area_deg2,
            ST_GeomFromText(geom_wkt) AS geom
        FROM read_parquet('{paths.GREEN_WATER_PARQUET}')
        WHERE green_class IS NOT NULL AND geom_wkt IS NOT NULL;
        """
    )

    return c


# ---------------------------------------------------------------------------
# Distance helpers (match DuckDB's distance formula for consistency)
# ---------------------------------------------------------------------------
# CH sits around 46–48° latitude → cos(47°) ≈ 0.682. We scale longitude by
# cos(query lat) to approximate metres without reprojecting every row.
# Error is <1% for radii up to ~2 km — fine for amenity buckets.

_DIST_SQL = (
    "111320 * sqrt("
    "  power(lat - {lat}, 2) + "
    "  power((lon - {lon}) * cos(radians({lat})), 2)"
    ")"
)


def _count(c: duckdb.DuckDBPyConnection, lat: float, lon: float, radius_m: int,
           col: str, val: str) -> int:
    sql = f"""
        SELECT count(*) FROM pois
        WHERE "{col}" = ? AND {_DIST_SQL.format(lat=lat, lon=lon)} <= ?;
    """
    return c.execute(sql, [val, radius_m]).fetchone()[0]


def _nearest(c: duckdb.DuckDBPyConnection, lat: float, lon: float, radius_m: int,
             col: str, val: str) -> dict[str, Any] | None:
    sql = f"""
        SELECT name, {_DIST_SQL.format(lat=lat, lon=lon)} AS d
        FROM pois
        WHERE "{col}" = ? AND {_DIST_SQL.format(lat=lat, lon=lon)} <= ?
        ORDER BY d ASC
        LIMIT 1;
    """
    row = c.execute(sql, [val, radius_m]).fetchone()
    if row is None:
        return None
    return {"name": row[0], "distance_m": round(row[1])}


def _nearest_water(c: duckdb.DuckDBPyConnection, lat: float, lon: float,
                   radius_m: int) -> dict[str, Any] | None:
    """Nearest water body centroid within radius (for 'near lake' signal)."""
    sql = f"""
        SELECT name, {_DIST_SQL.format(lat=lat, lon=lon)} AS d
        FROM gw
        WHERE green_class = 'water'
          AND {_DIST_SQL.format(lat=lat, lon=lon)} <= ?
        ORDER BY d ASC
        LIMIT 1;
    """
    row = c.execute(sql, [radius_m]).fetchone()
    if row is None:
        return None
    return {"name": row[0] or "(unnamed)", "distance_m": round(row[1])}


def _green_score(c: duckdb.DuckDBPyConnection, lat: float, lon: float,
                 radius_m: int) -> dict[str, int]:
    """Count green/water features whose centroid falls within the radius.

    `ch_green_water.parquet` stores most geometries as LINESTRING (forest
    edges, streams), so polygon-intersection is not meaningful. A proper
    green-share fraction requires the WorldCover 10m raster — deferred.

    Returns counts per high-level bucket.
    """
    buckets = {
        "green_features": "green_class IN ('forest','wood','meadow','grass','park','scrub','farmland','garden')",
        "water_features": "green_class IN ('water','stream','river','lake','pond')",
    }
    out: dict[str, int] = {}
    for key, pred in buckets.items():
        sql = f"""
            SELECT count(*) FROM gw
            WHERE {pred}
              AND {_DIST_SQL.format(lat=lat, lon=lon)} <= ?;
        """
        out[key] = c.execute(sql, [radius_m]).fetchone()[0]
    return out


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def amenities(
    location: tuple[float, float],
    radius_m: int = 500,
    categories: list[str] | None = None,
) -> dict[str, Any]:
    """Return nearby amenity counts, nearest-of-each, and green-share.

    Parameters
    ----------
    location : (lat, lon) in WGS84.
    radius_m : search radius in metres. 500 is a reasonable walking buffer.
    categories : subset of `CATEGORY_MAP` keys. Unknown keys are ignored with
                 a warning. None → all categories.

    Returns
    -------
    dict with keys: counts, nearest, green_share_500m.
    """
    lat, lon = location
    cats = categories or list(CATEGORY_MAP.keys())
    unknown = set(cats) - set(CATEGORY_MAP.keys())
    if unknown:
        print(f"[amenities] ignoring unknown categories: {sorted(unknown)}")
    cats = [k for k in cats if k in CATEGORY_MAP]

    c = _con()

    counts: dict[str, int] = {}
    nearest: dict[str, dict[str, Any] | None] = {}
    for key in cats:
        col, val = CATEGORY_MAP[key]
        counts[key] = _count(c, lat, lon, radius_m, col, val)
        nearest[key] = _nearest(c, lat, lon, radius_m, col, val)

    # Always include water via the green/water file — it's richer than POI
    # tagging for lakes/rivers.
    nearest["water"] = _nearest_water(c, lat, lon, radius_m)

    greenery = _green_score(c, lat, lon, radius_m)

    # Land-cover share from WorldCover raster — optional (degrades gracefully
    # if rasterio isn't installed or the tile is missing).
    land_cover: dict[str, float] | None
    try:
        from .green_share import green_share as _land_cover

        land_cover = _land_cover(lat, lon, radius_m=radius_m)
    except Exception as exc:
        print(f"[amenities] green_share unavailable ({type(exc).__name__}: {exc})")
        land_cover = None

    return {
        "counts": counts,
        "nearest": nearest,
        "greenery": greenery,        # POI-feature counts (forest edges, streams, ...)
        "land_cover": land_cover,    # WorldCover fractions: green/water/built/bare/other
    }
