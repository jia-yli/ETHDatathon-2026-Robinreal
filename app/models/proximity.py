"""
Geographic proximity scoring for listings.

Scores each candidate by its distance to landmarks mentioned in the query.
"""
from __future__ import annotations

import math
from typing import Any

# ── Known landmarks with coordinates (lat, lon) ──────────────────────────
LANDMARKS: dict[str, tuple[float, float]] = {
    "epfl":             (46.5197, 6.5657),
    "unil":             (46.5223, 6.5773),
    "eth":              (47.3769, 8.5480),
    "uzh":              (47.3744, 8.5512),
    "hsg":              (47.4239, 9.3748),
    "unibas":           (47.5596, 7.5812),
    "unibe":            (46.9510, 7.4386),
    "unige":            (46.2017, 6.1499),
    "chuv":             (46.5238, 6.6660),
    "hbf zürich":       (47.3779, 8.5403),
    "hbf bern":         (46.9490, 7.4391),
    "hbf basel":        (47.5476, 7.5897),
    "hbf genf":         (46.2100, 6.1424),
    "flughafen zürich": (47.4647, 8.5492),
}

# Score drops linearly from 1.0 at 0 km to 0.0 at this distance.
PROXIMITY_MAX_KM: float = 8.0

# Neutral score for listings with missing coordinates.
PROXIMITY_UNKNOWN: float = 0.4


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    R = 6371.0
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def get_proximity_scores(candidates: list[dict[str, Any]], query: str) -> list[float]:
    """
    Score each candidate by closeness to any landmark mentioned in the query.
    Returns 1.0 for the closest listing, scaling down to 0.0 at PROXIMITY_MAX_KM.
    When no landmark is found in the query, all scores are equal (no ranking effect).
    """
    query_lower = query.lower()
    targets = [coords for name, coords in LANDMARKS.items() if name in query_lower]
    if not targets:
        return [1.0] * len(candidates)

    scores = []
    for c in candidates:
        lat, lon = c.get("latitude"), c.get("longitude")
        if lat is None or lon is None:
            scores.append(PROXIMITY_UNKNOWN)
            continue
        min_dist = min(haversine_km(lat, lon, tlat, tlon) for tlat, tlon in targets)
        scores.append(max(0.0, 1.0 - min_dist / PROXIMITY_MAX_KM))
    return scores
