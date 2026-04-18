"""Smoke tests — run with `pytest src/location_features/tests -q`.

These hit the real prep data at ~/datathon_prep/. They're not fast, but they
catch schema drift and missing files. Skip if the prep bundle isn't mounted.
"""

from __future__ import annotations

import pytest

from location_features import amenities, commute
from location_features.paths import POIS_PARQUET, OSM_PBF

ZURICH_HB = (47.3779, 8.5403)
ETH_ZENTRUM = (47.3763, 8.5489)
GENEVA = (46.2044, 6.1432)
ALPINE = (46.55, 8.00)


pytestmark = pytest.mark.skipif(
    not POIS_PARQUET.exists(),
    reason="prep data not present at ~/datathon_prep/",
)


# ---------- commute ----------


def test_commute_short_hop_all_modes_reasonable() -> None:
    out = commute(ZURICH_HB, ETH_ZENTRUM)
    assert 0 < out["distance_km"] < 2
    assert out["foot_min"] is not None and out["foot_min"] < 30
    assert out["bike_min"] is not None and out["bike_min"] < 20
    assert out["car_min"] is not None and out["car_min"] < 15
    assert out["source"] in {"r5py", "proxy"}


def test_commute_long_distance_foot_unroutable_or_huge() -> None:
    out = commute(ZURICH_HB, GENEVA)
    # Haversine ≈ 225 km — too far to walk / bike in the 10h default window.
    assert out["distance_km"] > 200
    # foot/bike are either None (r5py gave up) or absurdly large (proxy).
    if out["foot_min"] is not None:
        assert out["foot_min"] > 1000


def test_commute_identity_is_zero_ish() -> None:
    out = commute(ZURICH_HB, ZURICH_HB)
    assert out["distance_km"] < 0.01
    # r5py rounds up to its 1-minute resolution; proxy returns 0.
    assert out["foot_min"] is not None and out["foot_min"] <= 1


# ---------- amenities ----------


def test_amenities_hb_is_dense() -> None:
    out = amenities(ZURICH_HB, radius_m=500)
    c = out["counts"]
    assert c["restaurant"] >= 5
    assert c["bus_stop"] >= 1 or c["tram_stop"] >= 1 or c["train_station"] >= 1
    assert "greenery" in out and "land_cover" in out
    if out["land_cover"] is not None:
        assert sum(out["land_cover"].values()) == pytest.approx(1.0, abs=0.01)


def test_amenities_alpine_is_sparse() -> None:
    out = amenities(ALPINE, radius_m=500)
    assert out["counts"]["restaurant"] <= 2
    assert out["counts"]["supermarket"] == 0


def test_amenities_unknown_category_is_ignored(capsys) -> None:
    out = amenities(ZURICH_HB, categories=["restaurant", "not_a_real_category"])
    assert "restaurant" in out["counts"]
    assert "not_a_real_category" not in out["counts"]


def test_amenities_respects_radius() -> None:
    small = amenities(ZURICH_HB, radius_m=100)["counts"]["restaurant"]
    large = amenities(ZURICH_HB, radius_m=800)["counts"]["restaurant"]
    assert small <= large
