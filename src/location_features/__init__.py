"""Location-derived features for real-estate ranking.

Two functions, both pure-ish (singleton caches) and offline:

- `commute(origin, destination)` -> distance + transit/car/bike/foot minutes.
- `amenities(location, radius_m=500)` -> POI counts + nearest-of-each + green share.

All data is sourced from `~/datathon_prep/` (see prep_data_pointer.md).
See agent_docs/location_features_plan.md for the signature contract.
"""

from __future__ import annotations

from .amenities import CATEGORY_MAP, amenities
from .commute import commute

__all__ = ["amenities", "commute", "CATEGORY_MAP"]
