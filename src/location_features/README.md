# location_features

Two functions that turn a listing's `(lat, lon)` into ranking features. All data is local — no API keys, no rate limits, no per-call cost.

```python
from location_features import commute, amenities

travel  = commute((47.3779, 8.5403), (47.3763, 8.5489))   # → distance + 4 mode times
nearby  = amenities((47.3779, 8.5403), radius_m=500)      # → POI counts + nearest + land cover
```

The full signature contract lives in [`agent_docs/location_features_plan.md`](../../agent_docs/location_features_plan.md). **Read that before changing any return shape.**

---

## Quick start (new teammates — do this first)

Goal: route Zürich HB → Zürich Zoo end-to-end on your laptop.

**Step 1 — install Python deps:**
```bash
cd repo && uv sync
```

**Step 2 — confirm prep data exists at `~/datathon_prep/`.** If a file is missing the function will tell you exactly which path to fix.

**Step 3 — try it (proxy mode, instant, no Java):**
```bash
PYTHONPATH=src uv run python -c "
from location_features import commute
print(commute((47.3779, 8.5403), (47.3853, 8.5742)))   # HB -> Zoo
"
# → {'distance_km': 2.6, ..., 'source': 'proxy'}
```

**Step 4 — upgrade to real routing (optional, recommended for the demo):**
```bash
brew install openjdk@21                                  # Linux: apt install openjdk-21-jdk
uv sync --extra routing
uv run python scripts/clean_gtfs.py                      # one-time GTFS fix
export JAVA_HOME=/opt/homebrew/opt/openjdk@21/libexec/openjdk.jdk/Contents/Home
PYTHONPATH=src uv run python -c "
from location_features import commute
print(commute((47.3779, 8.5403), (47.3853, 8.5742)))
"
# → {'distance_km': 2.6, 'transit_min': 12, ..., 'source': 'r5py'}
```
First-ever call: ~5 min (network build, cached afterwards). Subsequent fresh processes: ~30 s. Same-process calls: ~8 s.

If you see `'source': 'proxy'` when you expected `'r5py'`, `JAVA_HOME` is unset or `r5py` isn't installed — see Troubleshooting below.

---

## Setup

### 1. Python deps

From the repo root:

```bash
uv sync                      # required: duckdb, rasterio, numpy, ...
uv sync --extra routing      # optional: r5py for real multimodal routing
uv sync --extra dev          # optional: pytest
```

### 2. Prep data

Both functions read from `~/datathon_prep/`. The full bundle is ~17 GB; for *just these two functions* you need ~600 MB:

| File | Size | Used by |
|---|---|---|
| `processed/ch_pois.parquet` | 11 MB | `amenities` (POI counts + nearest) |
| `processed/ch_green_water.parquet` | 224 MB | `amenities` (water nearest + greenery counts) |
| `worldcover/wc_*.tif` (4 tiles) | 384 MB | `amenities` (land-cover fractions) |
| `gtfs/unzipped/stops.txt` | 10 MB | `commute` proxy (nearest-stop heuristic) |
| `osm/switzerland-latest.osm.pbf` | 505 MB | `commute` r5py (skip if proxy-only) |
| `gtfs/clean/ch_gtfs_2026_no_taxi.zip` | 231 MB | `commute` r5py (skip if proxy-only) |

Source: organizer S3 link. See [`prep_data_pointer.md`](../../prep_data_pointer.md) for inventory.

If a required file is missing, the functions raise `FileNotFoundError` with the exact path — no silent degradation.

### 3. r5py + Java (optional, for real routing)

`commute()` works without this — it falls back to a Haversine + speed proxy and tags the result `"source": "proxy"`. To get real multimodal routing tagged `"source": "r5py"`:

```bash
# macOS — JDK 17+ required
brew install openjdk@21
export JAVA_HOME=/opt/homebrew/opt/openjdk@21/libexec/openjdk.jdk/Contents/Home

# Linux equivalent
sudo apt install openjdk-21-jdk
export JAVA_HOME=/usr/lib/jvm/java-21-openjdk-amd64

uv sync --extra routing

# One-time: strip taxi route_type=1500 (R5 doesn't accept it)
uv run python scripts/clean_gtfs.py
```

After that, **every shell that imports r5py needs `JAVA_HOME` exported.** Without it, `_get_network()` silently catches the JVM startup error and falls back to proxy.

---

## What each function does

### `commute(origin, destination, departure_time=None) -> dict`

Distance + estimated travel time for 4 modes between two `(lat, lon)` points.

```python
>>> commute((47.3779, 8.5403), (47.3763, 8.5489))
{
    "distance_km": 0.67,
    "transit_min": 15,
    "car_min":     8,
    "bike_min":    10,
    "foot_min":    18,
    "source":      "r5py",   # or "proxy"
}
```

- `distance_km` is great-circle (Haversine), always populated.
- Mode times are whole minutes. `None` means unroutable in the time window (e.g. walking from Zürich to Geneva).
- `departure_time` is used only for the transit timetable; defaults to next Tuesday 08:30 local.

**Backends:**

- **r5py** (preferred): builds a network from `osm/switzerland-latest.osm.pbf` + `gtfs/clean/ch_gtfs_2026_no_taxi.zip`. First-ever call costs ~5 min (build + serialise to `~/Library/Caches/r5py/`); after that each fresh process loads the 2.2 GB cache in **~28 s**. Warm calls within the same process are ~8 s.
- **proxy** (fallback): Haversine ÷ speed (foot 5 km/h, bike 15, car 35–80, transit via nearest-stop + 45 km/h). Instant.

### `amenities(location, radius_m=500, categories=None) -> dict`

POI counts, nearest-of-each, and land-cover fractions around one point.

```python
>>> amenities((47.3779, 8.5403), radius_m=500)
{
    "counts": {
        "supermarket":   9,
        "restaurant":    79,
        "tram_stop":     25,
        "train_station": 4,
        # ... all keys in CATEGORY_MAP
    },
    "nearest": {
        "supermarket":   {"name": "Migros", "distance_m": 44},
        "park":          None,
        "train_station": {"name": "Zürich Hauptbahnhof", "distance_m": 74},
        "water":         {"name": "(unnamed)", "distance_m": 220},
        # ...
    },
    "greenery": {"green_features": 98, "water_features": 7},
    "land_cover": {
        "green": 0.12, "water": 0.08, "built": 0.80, "bare": 0.0, "other": 0.0,
    },
}
```

- `counts` / `nearest` keys come from `CATEGORY_MAP` (importable). Pass a `categories=[...]` subset to limit work.
- `greenery` is OSM feature counts (forest edges, streams) within `radius_m`.
- `land_cover` is the *fraction* of a 500 m disk that the WorldCover 10 m raster classifies as each class. Sums to ~1.0. Returns `None` if rasterio isn't installed.

Single query is <50 ms after the parquets warm up; batches of 1k listings finish in seconds.

---

## How it works (and why `commute` is slow the first time)

Both functions use a **lazy singleton** — expensive setup happens inside the first call, and subsequent calls in the same process reuse what's already in memory.

### `amenities` — negligible init

On the first call, `_con()` opens an in-memory DuckDB, loads the spatial extension, and registers two parquet files as views. Cached via `@lru_cache`. One-time cost ~100 ms. Every subsequent call runs SQL directly against the cached connection.

### `commute` — where the waiting happens

On the first call, `_get_network()` has to:

1. **Start the JVM** (r5py wraps a Java engine). ~3 s cold, not negotiable.
2. **Load a 2.2 GB routing network** — a graph of every Swiss road and footpath plus the full national transit timetable (~30k stops, ~17M stop-times), indexed for multi-modal shortest-path search.

That network is built from `switzerland-latest.osm.pbf` + the cleaned GTFS:

- **First-ever build** (no cache yet): ~5 min. r5py serialises the result to `~/Library/Caches/r5py/*.dat`.
- **Subsequent fresh processes**: ~25–30 s to load the cached `.dat` back into the JVM. R5py keys the cache on input-file hash; it only rebuilds if you replace the OSM PBF or rerun `clean_gtfs.py`.

Once the network is in memory, each route query costs ~8 s (the JVM multi-modal path search). That 8 s is not init — it's the routing itself, paid on every call.

### Is init avoidable?

**Mandatory for r5py mode.** You can't route on a graph that isn't loaded.

**Not needed for proxy mode.** If Java/r5py aren't installed, `commute()` silently falls back to Haversine + speed heuristic. Zero init, results are instant, accuracy is coarser. `rank_listings` consumes the same dict either way — only the numbers differ.

### Can I initialise once and reuse it?

**Within one Python process: already happens automatically.** The module-level `_NETWORK` global holds the network for the lifetime of the process. First call costs ~30 s; every subsequent call in the same process is just the ~8 s route time.

**Across separate `uv run python ...` invocations: no.** Each process has its own JVM. Strategies that avoid paying the 30 s repeatedly:

1. **Long-lived process.** Jupyter kernel, FastAPI/uvicorn server, or a Python REPL. Init once, serve thousands of queries. This is how the demo API stays fast.
2. **Batch pre-compute.** Run `commute()` for every listing × fixed reference-POI once, store the minutes as columns on each listing row. At query time, `rank_listings` does an O(1) dict lookup — no r5py, no JVM.

For the live judging demo: strategy 1 (keep uvicorn warm, never restart). For dataset enrichment ahead of time: strategy 2.

---

## Quick examples for teammates

### From the command line

```bash
cd repo
uv run python -c "
from location_features import amenities, commute
loc = (47.3779, 8.5403)
print(amenities(loc, radius_m=400, categories=['restaurant','park','train_station']))
print(commute(loc, (47.3763, 8.5489)))
"
```

### Inside a notebook

```bash
cd repo
uv run jupyter lab
```

```python
from location_features import amenities, commute, CATEGORY_MAP
print(sorted(CATEGORY_MAP))
amenities((47.3779, 8.5403))
```

### Inside the harness ranker

`challenge_harness/app/participant/ranking.py`:

```python
from location_features import amenities, commute

ETH = (47.3763, 8.5489)

def rank_listings(candidates, soft_facts):
    prefs = soft_facts.get("preferences", {})
    for c in candidates:
        loc = (c["latitude"], c["longitude"])
        if "near_eth" in prefs:
            c["_transit_to_eth_min"] = commute(loc, ETH)["transit_min"]
        if "family_friendly" in prefs:
            c["_kindergartens_500m"] = amenities(loc, radius_m=500,
                categories=["kindergarten", "playground"])["counts"]["kindergarten"]
    # ... score using these features ...
```

> **Don't call `commute()` in the live request loop.** With r5py it's ~8 s/call. Pre-compute features per listing during indexing, cache by `listing_id`, look up in the ranker.

---

## Tests

```bash
uv run pytest src/location_features/tests -q
```

Tests skip automatically if the prep bundle isn't mounted.

---

## File layout

```
src/location_features/
├── __init__.py        # exports commute, amenities, CATEGORY_MAP
├── commute.py         # Function 1: r5py + proxy fallback
├── amenities.py       # Function 2: DuckDB POI queries + green_share dispatch
├── green_share.py     # WorldCover raster reader (rasterio)
├── paths.py           # absolute paths to ~/datathon_prep/ files
└── tests/test_smoke.py
```

---

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| `ModuleNotFoundError: location_features` | Running with system Python or wrong cwd | `cd repo && uv run python ...` (uses venv + `pythonpath = ["src"]` from pyproject) |
| `commute()` always returns `"source": "proxy"` | r5py optional extras not installed, or `JAVA_HOME` not set | `uv sync --extra routing` and `export JAVA_HOME=...` |
| `commute()` first-ever call takes 5+ min | r5py building & serialising network from OSM + GTFS | One-time. Subsequent fresh processes load the disk cache in ~28 s; warm calls ~8 s. |
| Cold-start jumped back to 5 min | Cache invalidated because OSM PBF or GTFS changed | Expected — r5py keys the cache on input file hash. Re-runs `clean_gtfs.py` will trigger this. |
| `FileNotFoundError: ~/datathon_prep/...` | Prep bundle missing | Download per [`prep_data_pointer.md`](../../prep_data_pointer.md) |
| `IllegalArgumentException: Taxi route_type code not supported: 1500` | Using raw GTFS instead of cleaned zip | `uv run python scripts/clean_gtfs.py` |
| `green_share unavailable (...)` printed | rasterio not installed or WorldCover tile missing | `uv sync` (rasterio is in base deps); confirm `~/datathon_prep/worldcover/*.tif` exists |
