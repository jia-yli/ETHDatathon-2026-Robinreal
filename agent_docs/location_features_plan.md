# Location Features — Implementation Guide

Two standalone functions that turn `(lat, lon)` coordinates into ranking features for the soft-scoring stage.

All data lives at `~/datathon_prep/` (see [prep_data_pointer.md](../prep_data_pointer.md)). No cloud APIs, no API keys, no cost — everything is local.

---

## Function 1 — `commute(origin, destination) -> dict`

### Signature

```python
def commute(
    origin: tuple[float, float],        # (lat, lon)
    destination: tuple[float, float],   # (lat, lon)
    departure_time: str | None = None,  # ISO-8601; default: next Tue 08:30 local
) -> dict:
    """Return distance + estimated travel times for 4 modes."""
```

### Return shape (fixed keys)

```python
{
    "distance_km": 3.42,                # straight-line (Haversine)
    "transit_min": 18,                  # public transport (walk + vehicle + walk)
    "car_min":     9,
    "bike_min":    14,
    "foot_min":    42,
    "transit_legs": [                   # optional, nice for demo/explainability
        {"mode": "walk",  "min": 4, "from": "origin", "to": "Zürich HB"},
        {"mode": "train", "min": 11, "route": "S8",   "to": "Stettbach"},
        {"mode": "walk",  "min": 3,  "to": "destination"},
    ],
}
```

Any mode that cannot be routed (e.g. no transit leg found) → `None` instead of an int. Never raise; log + return the partial dict.

### Data sources

| Purpose | File |
|---|---|
| Walking / cycling / driving network | `~/datathon_prep/osm/switzerland-latest.osm.pbf` |
| Public transit timetable | `~/datathon_prep/gtfs/unzipped/*.txt` (GTFS FP2026) |

### Recommended implementation — `r5py`

`r5py` is a Python wrapper around Conveyal R5. It builds a single transport network from OSM + GTFS, then answers multi-modal routing queries. Battle-tested in urban-planning research, free, MIT-licensed.

```bash
uv pip install r5py
```

Build the network **once at module import**. r5py auto-caches the serialised network (~2.2 GB) to `~/Library/Caches/r5py/` keyed by hash of the OSM PBF + GTFS. First-ever build: ~5 min. Subsequent fresh processes load the cache in ~28 s.

```python
from r5py import TransportNetwork, TravelTimeMatrixComputer
import geopandas as gpd
from shapely.geometry import Point

NETWORK = TransportNetwork(
    osm_pbf="/Users/zhizch/datathon_prep/osm/switzerland-latest.osm.pbf",
    gtfs=["/Users/zhizch/datathon_prep/gtfs/ch_gtfs_2026_latest.zip"],
)
```

Per-query:

```python
import datetime as dt
from r5py import TravelTimeMatrixComputer
from r5py.util import TransportMode

def _tt(origin, destination, modes, departure):
    o = gpd.GeoDataFrame({"id": [0], "geometry": [Point(origin[1], origin[0])]}, crs="EPSG:4326")
    d = gpd.GeoDataFrame({"id": [1], "geometry": [Point(destination[1], destination[0])]}, crs="EPSG:4326")
    m = TravelTimeMatrixComputer(
        NETWORK, origins=o, destinations=d,
        departure=departure, transport_modes=modes,
        max_time=dt.timedelta(hours=3),
    ).compute_travel_times()
    return int(m["travel_time"].iloc[0]) if not m.empty else None
```

Modes:

- `foot_min`: `[TransportMode.WALK]`
- `bike_min`: `[TransportMode.BICYCLE]`
- `car_min`: `[TransportMode.CAR]`
- `transit_min`: `[TransportMode.TRANSIT, TransportMode.WALK]` (walk used for access/egress)

Add Haversine for `distance_km` (no r5py call needed):

```python
import math
def _haversine_km(a, b):
    R = 6371.0
    (lat1, lon1), (lat2, lon2) = a, b
    φ1, φ2 = math.radians(lat1), math.radians(lat2)
    dφ = math.radians(lat2 - lat1); dλ = math.radians(lon2 - lon1)
    h = math.sin(dφ/2)**2 + math.cos(φ1)*math.cos(φ2)*math.sin(dλ/2)**2
    return 2 * R * math.asin(math.sqrt(h))
```

### Fallback — cheaper but coarser

If `r5py` is too heavy for the demo environment, approximate:

- `foot_min  ≈ distance_km / 5 * 60`
- `bike_min  ≈ distance_km / 15 * 60`
- `car_min   ≈ distance_km / 40 * 60` (urban; `/ 80` on motorways)
- `transit_min ≈ walking time to nearest GTFS stop + vehicle time (rough lookup) + egress walk`

Document which branch you used in the return dict:

```python
return {..., "source": "r5py" | "proxy"}
```

### Tests

- `commute((47.3769, 8.5417), (47.3763, 8.5489))` → all 4 modes < 30 min (short Zürich hop).
- `commute((47.3769, 8.5417), (46.2044, 6.1432))` → Zürich → Geneva: transit ≈ 170 min, car ≈ 170 min, bike/foot >> 3h → `None`.
- `commute(x, x)` → all zeros or ~1 min.

---

## Function 2 — `amenities(location, radius_m=500) -> dict`

### Signature

```python
def amenities(
    location: tuple[float, float],  # (lat, lon)
    radius_m: int = 500,
    categories: list[str] | None = None,  # subset; default = all known
) -> dict:
    """Count and describe amenities within `radius_m` of `location`."""
```

### Return shape

```python
{
    "counts": {
        "supermarket": 3,
        "restaurant":  12,
        "bar":          4,
        "school":       2,
        "kindergarten": 1,
        "park":         1,   # leisure=park POI OR green_water polygon intersect
        "playground":   2,
        "pharmacy":     1,
        "train_station": 0,
        "tram_stop":    2,
        "bus_stop":     5,
    },
    "nearest": {
        "supermarket":   {"name": "Migros Bellevue", "distance_m": 142},
        "park":          {"name": "Bürkliplatz",     "distance_m":  88},
        "train_station": {"name": "Zürich HB",       "distance_m": 612},
        "water":         {"name": "Zürichsee",       "distance_m":  74},
        # one per category; null if none in radius
    },
    "greenery": {"green_features": 12, "water_features": 3},  # POI counts in radius
    "land_cover": {"green": 0.12, "water": 0.08, "built": 0.80, "bare": 0.00, "other": 0.00},
                                                # WorldCover 10m raster, fractions sum ≈ 1
}
```

### Data sources

| Category bucket | File | Filter |
|---|---|---|
| amenities (restaurant, bar, school, pharmacy, ...) | `ch_pois.parquet` | `amenity` column |
| shops (supermarket, bakery, ...) | `ch_pois.parquet` | `shop` column |
| leisure (park, playground, sports) | `ch_pois.parquet` | `leisure` column |
| transit stops | `ch_pois.parquet` | `public_transport`, `railway` columns |
| richer named places | `overture/overture_places_ch.parquet` | `category` column |
| water body nearest-distance | `ch_green_water.parquet` | `green_class='water'` |
| green-share in radius | `ch_green_water.parquet` (or WorldCover raster) | polygon intersect |

### Recommended implementation — DuckDB spatial

```python
import duckdb

CON = duckdb.connect(":memory:")
CON.execute("INSTALL spatial; LOAD spatial;")
CON.execute("""
CREATE VIEW pois AS
SELECT *, ST_Point(lon, lat) AS geom
FROM read_parquet('/Users/zhizch/datathon_prep/processed/ch_pois.parquet')
WHERE lat IS NOT NULL;
""")

CATEGORY_MAP = {
    "supermarket":   ("shop",    "supermarket"),
    "restaurant":    ("amenity", "restaurant"),
    "bar":           ("amenity", "bar"),
    "school":        ("amenity", "school"),
    "kindergarten":  ("amenity", "kindergarten"),
    "pharmacy":      ("amenity", "pharmacy"),
    "park":          ("leisure", "park"),
    "playground":    ("leisure", "playground"),
    "train_station": ("railway", "station"),
    "tram_stop":     ("railway", "tram_stop"),
    "bus_stop":      ("public_transport", "stop_position"),
}

def _count_within(lat, lon, radius_m, col, val):
    # 1 degree latitude ≈ 111,320 m; scale lon by cos(lat) for CH it's ~0.68
    sql = f"""
    SELECT count(*) FROM pois
    WHERE "{col}" = ?
      AND 111320 * sqrt(
          power(lat - ?, 2) +
          power((lon - ?) * cos(radians(?)), 2)
      ) <= ?;
    """
    return CON.execute(sql, [val, lat, lon, lat, radius_m]).fetchone()[0]
```

For `green_share_500m` and nearest water-body, use the DuckDB spatial extension with `ST_DWithin` / `ST_Distance` against `ch_green_water.parquet`. Reproject lat/lon → EPSG:2056 (LV95) for accurate metre distances.

### Performance target

- Single location query: < 50 ms after warm-up (parquets cached by OS).
- Batch of 1,000 listings: < 5 s. If slower, pre-build a spatial index (`CREATE INDEX ... USING RTREE(geom)`).

### Tests

- Zürich HB `(47.3779, 8.5403)` → lots of supermarkets/restaurants/transit.
- Random alpine point `(46.55, 8.00)` → mostly zeros, green_share ≈ 1.
- Unknown category in `categories` arg → ignored with a warning, not a crash.

---

## Deliverable

One module, e.g. `repo/src/location_features/`, containing:

```
src/location_features/
    __init__.py        # exports commute, amenities
    commute.py         # Function 1
    amenities.py       # Function 2
    network.py         # lazy-loaded r5py TransportNetwork singleton
    db.py              # lazy-loaded DuckDB connection singleton
    tests/
        test_commute.py
        test_amenities.py
```

**Rules:**

- Both functions must be **pure and re-entrant** — no hidden global state beyond the cached singletons.
- Network + DB objects load on first call, not at import time (keeps CLI startup fast).
- Never hit the internet at runtime.
- If a data file is missing, raise `FileNotFoundError` with the exact path — don't silently degrade.

## Integration point

These feed `app/participant/ranking.py` in the harness:

```python
def rank_listings(candidates, soft_facts):
    if "near_eth" in soft_facts.get("preferences", {}):
        for c in candidates:
            t = commute((c["latitude"], c["longitude"]), ETH_ZENTRUM)["transit_min"]
            c["_features"]["transit_to_eth_min"] = t
    ...
```

Keep feature extraction out of the hot loop of ranking — batch-compute once per request and cache per listing_id.
