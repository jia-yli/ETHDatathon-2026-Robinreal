"""WorldCover-based green/water share calculation.

Reads ESA WorldCover 2021 v200 10m rasters from ~/datathon_prep/worldcover/.
Returns the fraction of pixels in a radius-m disk that fall into each
land-cover class.

WorldCover class codes:
   10 tree cover         — green
   20 shrubland          — green
   30 grassland          — green
   40 cropland           — green
   50 built-up           — built
   60 bare / sparse veg  — bare
   70 snow & ice         — bare
   80 permanent water    — water
   90 herbaceous wetland — water
   95 mangroves          — water (n/a in CH)
  100 moss & lichen      — bare

Files cover Switzerland in 4 tiles at 3°×3° each.
"""

from __future__ import annotations

import math
from functools import lru_cache
from pathlib import Path
from typing import Any

from .paths import PREP, require

WORLDCOVER_DIR = PREP / "worldcover"

GREEN_CLASSES = {10, 20, 30, 40}     # tree, shrub, grass, crop
WATER_CLASSES = {80, 90, 95}         # water, wetland, mangrove
BUILT_CLASSES = {50}                 # built-up
BARE_CLASSES = {60, 70, 100}         # bare, snow, moss


@lru_cache(maxsize=1)
def _open_tiles() -> list[tuple[Any, Any]]:
    """Return list of (rasterio dataset, bounds) for every WorldCover tile."""
    import rasterio  # type: ignore

    require(WORLDCOVER_DIR)
    tiles = []
    for tif in sorted(WORLDCOVER_DIR.glob("wc_*.tif")):
        ds = rasterio.open(tif)
        tiles.append((ds, ds.bounds))
    if not tiles:
        raise FileNotFoundError(f"No WorldCover *.tif files in {WORLDCOVER_DIR}")
    return tiles


def green_share(lat: float, lon: float, radius_m: int = 500) -> dict[str, float]:
    """Return land-cover fractions inside a radius-m disk centred at (lat, lon).

    Output keys: green, water, built, bare, other. Sum to ~1.0 (rounding aside).
    Returns all-zero dict if the point falls outside the WorldCover tiles loaded.
    """
    import numpy as np
    from rasterio.windows import from_bounds  # type: ignore

    tiles = _open_tiles()

    # Bounding box in degrees (cosine-corrected for longitude)
    dlat = radius_m / 111_320.0
    dlon = radius_m / (111_320.0 * max(math.cos(math.radians(lat)), 1e-6))
    minx, maxx = lon - dlon, lon + dlon
    miny, maxy = lat - dlat, lat + dlat

    tile = next(
        (ds for ds, b in tiles
         if b.left <= lon <= b.right and b.bottom <= lat <= b.top),
        None,
    )
    if tile is None:
        return {"green": 0.0, "water": 0.0, "built": 0.0, "bare": 0.0, "other": 0.0}

    # Read the bbox window
    window = from_bounds(minx, miny, maxx, maxy, tile.transform)
    arr = tile.read(1, window=window, boundless=True, fill_value=0)
    if arr.size == 0:
        return {"green": 0.0, "water": 0.0, "built": 0.0, "bare": 0.0, "other": 0.0}

    # Build a circular mask in pixel space
    rows, cols = arr.shape
    cy, cx = rows / 2.0, cols / 2.0
    # Pixel resolution in metres (WorldCover is ~10 m, but compute from window)
    px_h = (maxy - miny) / max(rows, 1) * 111_320.0
    px_w = (maxx - minx) / max(cols, 1) * 111_320.0 * math.cos(math.radians(lat))
    yy, xx = np.ogrid[:rows, :cols]
    dist_m = np.sqrt(((yy - cy) * px_h) ** 2 + ((xx - cx) * px_w) ** 2)
    mask = dist_m <= radius_m
    sample = arr[mask]
    if sample.size == 0:
        return {"green": 0.0, "water": 0.0, "built": 0.0, "bare": 0.0, "other": 0.0}

    total = float(sample.size)

    def frac(classes: set[int]) -> float:
        return float(np.isin(sample, list(classes)).sum()) / total

    g = frac(GREEN_CLASSES)
    w = frac(WATER_CLASSES)
    b = frac(BUILT_CLASSES)
    ba = frac(BARE_CLASSES)
    return {
        "green": round(g, 3),
        "water": round(w, 3),
        "built": round(b, 3),
        "bare": round(ba, 3),
        "other": round(max(0.0, 1.0 - g - w - b - ba), 3),
    }
