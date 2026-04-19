"""
General apartment value score derived from Gemini-extracted boolean feature CSV.

Feature scores are loaded once per process and stored in a module-level dict,
making per-candidate lookup O(1) at query time (true table lookup).

Score =  w_feature * feature_score
       + w_price   * price_score

  feature_score  in [0, 1] — fraction of positive amenity flags that are True,
                             minus a penalty for negative flags.
  price_score    in [0, 1] — 1 = cheapest in the candidate set, 0 = most expensive.
                             Apartments with missing/zero price get the median (0.5).
"""

from __future__ import annotations

import csv
from pathlib import Path
from typing import Any

_CSV_PATH = (
    Path(__file__).parent.parent
    / "apartment_parsing"
    / "test_results_gemini25_flash_1000_apartments.csv"
)

# Amenity flags that positively signal apartment desirability (each adds 1/N to the score)
_POSITIVE: list[str] = [
    "is_new_building",
    "prop_balcony",
    "prop_elevator",
    "prop_parking",
    "prop_garage",
    "animal_allowed",
    "prop_child_friendly",
    "price_includes_utilities",
    "is_wheelchair_accessible",
    "is_furnished",
    "has_modern_kitchen",
    "has_open_kitchen",
    "has_dishwasher",
    "has_multiple_bathrooms",
    "has_bathtub",
    "has_washing_machine_in_unit",
    "has_cellar_storage",
    "has_terrace",
    "prop_garden_private",
    "view_lake",
    "view_mountains",
    "view_nature",
    "condition_newly_renovated",
    "vibe_bright_light",
    "vibe_sunny",
    "vibe_quiet_peaceful",
    "vibe_family_friendly",
    "location_urban_city_center",
    "commute_excellent",
    "close_to_train_station",
    "close_to_bus_tram",
    "close_to_supermarket",
    "close_to_kindergarten",
    "close_to_schools",
    "suitability_students",
]

# Flags that negatively signal apartment desirability (each subtracts 1/N from the score)
_NEGATIVE: list[str] = [
    "condition_needs_renovation",
]

# Used for apartments absent from the CSV — neutral, slightly-below-median prior
_FALLBACK_FEATURE_SCORE: float = 0.35

_feature_cache: dict[str, float] | None = None


def _load_feature_scores() -> dict[str, float]:
    scores: dict[str, float] = {}
    if not _CSV_PATH.exists():
        return scores

    n_pos = len(_POSITIVE)
    n_neg = len(_NEGATIVE)

    with _CSV_PATH.open(newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            listing_id = row.get("id", "").strip()
            if not listing_id:
                continue
            pos_count = sum(
                1 for col in _POSITIVE if row.get(col, "").strip() == "True"
            )
            neg_count = sum(
                1 for col in _NEGATIVE if row.get(col, "").strip() == "True"
            )
            raw = pos_count / n_pos - neg_count / max(n_neg, 1)
            scores[listing_id] = max(0.0, min(1.0, raw))

    return scores


def _get_feature_score(listing_id: str) -> float:
    global _feature_cache
    if _feature_cache is None:
        _feature_cache = _load_feature_scores()
    return _feature_cache.get(listing_id, _FALLBACK_FEATURE_SCORE)


def get_value_scores(
    candidates: list[dict[str, Any]],
    *,
    w_feature: float = 0.6,
    w_price: float = 0.4,
) -> list[float]:
    """
    Return a general value score in [0, 1] for each candidate.

    The feature component is a pure table lookup (O(1) per candidate).
    The price component is normalised within the current candidate set so that
    the cheapest apartment scores 1.0 and the most expensive scores 0.0.
    """
    feature_scores = [
        _get_feature_score(str(c.get("listing_id", ""))) for c in candidates
    ]

    # Clamp unrealistically low prices: anything below 500 CHF is treated as
    # 500 CHF so that suspiciously cheap (likely data-quality) listings do not
    # get a spurious "cheapest" bonus.
    # 500 CHF/month is chosen as the practical minimum for a habitable Swiss rental.
    _PRICE_FLOOR = 500.0
    prices = [max(float(c.get("price") or 0.0), _PRICE_FLOOR) if float(c.get("price") or 0.0) > 0.0 else 0.0 for c in candidates]
    valid_prices = [p for p in prices if p > 0.0]

    if valid_prices and max(valid_prices) > min(valid_prices):
        lo, hi = min(valid_prices), max(valid_prices)
        price_scores = [
            1.0 - (p - lo) / (hi - lo) if p > 0.0 else 0.5
            for p in prices
        ]
    elif valid_prices:
        # All valid prices are identical → everyone scores 1.0
        price_scores = [1.0 if p > 0.0 else 0.5 for p in prices]
    else:
        price_scores = [0.5] * len(candidates)

    return [
        w_feature * fs + w_price * ps
        for fs, ps in zip(feature_scores, price_scores)
    ]
