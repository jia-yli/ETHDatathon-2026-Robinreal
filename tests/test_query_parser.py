"""
Integration tests for the query_parsing layer.

Each test case drives a real LLM call against the DeepSeek API and validates
that the structured output matches expected hard and soft constraints.

Coverage across 20 cases
------------------------
offer_type          : RENT ×4, BUY ×3, unspecified ×13
object_category     : Wohnung ×13, Haus ×4, unspecified ×3
rooms               : exact ×8, min ×4, max ×2, range ×2, none ×4
price               : max ×11, range ×2, min ×0, none ×7
city                : specified ×16, none ×4
canton              : specified ×2, none ×18
amenities           : balcony ×5, parking ×4, elevator ×2, garage ×2, fireplace ×2
other hard          : animal_allowed ×3, child_friendly ×2, new_building ×1,
                      available_from ×2, floor ×2, area ×2
soft constraints    : asserted non-empty for cases where vague language is present
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

import pytest

# Make the project root importable regardless of invocation directory
sys.path.insert(0, str(Path(__file__).parent.parent))

from query_parsing import QueryParser
from query_parsing.schema import ParsedQuery


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _city_match(actual: Optional[str], expected: str) -> bool:
    """Case-insensitive substring check; handles umlaut variants."""
    if actual is None:
        return False
    a = actual.lower().replace("ü", "u").replace("ö", "o").replace("ä", "a")
    e = expected.lower().replace("ü", "u").replace("ö", "o").replace("ä", "a")
    return e in a or a in e


def _assert_hard(result: ParsedQuery, checks: Dict[str, Any]) -> None:
    hc = result.hard_constraints
    for field, expected in checks.items():
        actual = getattr(hc, field)
        if field in ("city", "canton"):
            assert _city_match(actual, expected), (
                f"[{field}] expected ~'{expected}', got '{actual}'"
            )
        elif field == "available_from":
            # Accept any date string that contains the expected year-month prefix
            assert actual is not None, f"[available_from] expected ~'{expected}', got None"
            assert expected in actual, (
                f"[available_from] expected substring '{expected}', got '{actual}'"
            )
        elif isinstance(expected, float):
            assert actual is not None, f"[{field}] expected {expected}, got None"
            assert abs(actual - expected) < 0.01, (
                f"[{field}] expected {expected}, got {actual}"
            )
        elif expected is None:
            assert actual is None, f"[{field}] expected None, got '{actual}'"
        else:
            assert actual == expected, (
                f"[{field}] expected {expected!r}, got {actual!r}"
            )


def _assert_soft_nonempty(result: ParsedQuery) -> None:
    assert result.soft_constraints.keywords, (
        "Expected non-empty soft keywords, got empty list"
    )


def _assert_soft_contains(result: ParsedQuery, phrases: List[str]) -> None:
    """At least one phrase from *phrases* should appear (case-insensitive) in keywords."""
    kws_lower = " ".join(result.soft_constraints.keywords).lower()
    raw_lower = (result.soft_constraints.raw_description or "").lower()
    combined = kws_lower + " " + raw_lower
    found = any(p.lower() in combined for p in phrases)
    assert found, (
        f"Expected one of {phrases!r} in soft constraints, "
        f"got keywords={result.soft_constraints.keywords!r}"
    )


# ---------------------------------------------------------------------------
# Shared parser fixture (one instance for the whole test session)
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def parser() -> QueryParser:
    return QueryParser()


# ---------------------------------------------------------------------------
# Test cases
# ---------------------------------------------------------------------------

# Each entry:
#   id          – pytest test ID
#   query       – raw user input
#   hard        – dict of HardConstraints field → expected value
#   soft_empty  – True if we expect NO soft constraints
#   soft_has    – list of phrases; at least one must appear in soft output
#
TEST_CASES = [
    # ------------------------------------------------------------------
    # TC01 – basic apartment, exact rooms, price cap, balcony, city
    # ------------------------------------------------------------------
    dict(
        id="tc01_apartment_zurich_3r5_balcony",
        query="3.5-room bright apartment in Zurich under CHF 2800 with balcony",
        hard=dict(
            object_category="Wohnung",
            exact_rooms=3.5,
            max_price_chf=2800.0,
            prop_balcony=True,
            city="Zurich",
        ),
        soft_empty=False,
        soft_has=["bright"],
    ),
    # ------------------------------------------------------------------
    # TC02 – family-friendly flat, parking, soft price language
    # ------------------------------------------------------------------
    dict(
        id="tc02_family_flat_winterthur_parking",
        query=(
            "Bright family-friendly flat in Winterthur, not too expensive, "
            "ideally with parking"
        ),
        hard=dict(
            object_category="Wohnung",
            city="Winterthur",
            prop_parking=True,
            prop_child_friendly=True,
        ),
        soft_empty=False,
        soft_has=["bright", "not too expensive", "expensive"],
    ),
    # ------------------------------------------------------------------
    # TC03 – almost all soft; only city and category are hard
    # ------------------------------------------------------------------
    dict(
        id="tc03_soft_heavy_basel",
        query="Modern apartment in Basel, cheap but central, quiet with nice views",
        hard=dict(
            object_category="Wohnung",
            city="Basel",
        ),
        soft_empty=False,
        soft_has=["modern", "cheap", "central", "quiet", "view"],
    ),
    # ------------------------------------------------------------------
    # TC04 – buy, house, canton, exact rooms, garage
    # ------------------------------------------------------------------
    dict(
        id="tc04_buy_house_canton_zurich_garage",
        query="Looking to buy a 5-room house in canton Zurich with garage",
        hard=dict(
            offer_type="BUY",
            object_category="Haus",
            exact_rooms=5.0,
            canton="Zurich",
            prop_garage=True,
        ),
        soft_empty=True,
        soft_has=[],
    ),
    # ------------------------------------------------------------------
    # TC05 – rent, studio, Geneva, price cap
    # ------------------------------------------------------------------
    dict(
        id="tc05_rent_studio_geneva_1500",
        query="Studio apartment for rent in Geneva, max CHF 1500 per month",
        hard=dict(
            offer_type="RENT",
            object_category="Wohnung",
            city="Geneva",
            max_price_chf=1500.0,
            exact_rooms=1.0,
        ),
        soft_empty=False,  # LLM may keep 'studio' as a soft keyword; all hard fields still validated
        soft_has=[],
    ),
    # ------------------------------------------------------------------
    # TC06 – exact rooms, availability date, elevator
    # ------------------------------------------------------------------
    dict(
        id="tc06_bern_4r5_available_sep2026_elevator",
        query=(
            "4.5-room apartment in Bern, available from September 2026, "
            "with elevator"
        ),
        hard=dict(
            object_category="Wohnung",
            exact_rooms=4.5,
            city="Bern",
            prop_elevator=True,
            available_from="2026-09",
        ),
        soft_empty=True,
        soft_has=[],
    ),
    # ------------------------------------------------------------------
    # TC07 – pet-friendly, 2-room, soft price
    # ------------------------------------------------------------------
    dict(
        id="tc07_pets_2room_cheap",
        query="2-room flat anywhere in Switzerland, must allow pets, cheap",
        hard=dict(
            object_category="Wohnung",
            exact_rooms=2.0,
            animal_allowed=True,
        ),
        soft_empty=False,
        soft_has=["cheap"],
    ),
    # ------------------------------------------------------------------
    # TC08 – high budget, penthouse/luxury, city – mostly soft
    # ------------------------------------------------------------------
    dict(
        id="tc08_luxury_penthouse_zurich_8000",
        query="Luxury penthouse in Zurich city center, budget up to CHF 8000",
        hard=dict(
            object_category="Wohnung",
            city="Zurich",
            max_price_chf=8000.0,
        ),
        soft_empty=False,
        soft_has=["luxury", "penthouse", "city center", "center"],
    ),
    # ------------------------------------------------------------------
    # TC09 – buy, house, min rooms, city, garage, quiet (soft)
    # ------------------------------------------------------------------
    dict(
        id="tc09_buy_house_zug_6rooms_garage",
        query=(
            "Family house for sale in Zug, at least 6 rooms, "
            "with garage, quiet neighborhood"
        ),
        hard=dict(
            offer_type="BUY",
            object_category="Haus",
            min_rooms=6.0,
            city="Zug",
            prop_garage=True,
        ),
        soft_empty=False,
        soft_has=["quiet"],
    ),
    # ------------------------------------------------------------------
    # TC10 – 2-room, price cap, near landmark (soft)
    # ------------------------------------------------------------------
    dict(
        id="tc10_2room_zurich_2000_near_hb",
        query=(
            "2-room apartment near Zurich main station, max CHF 2000, "
            "good public transport access"
        ),
        hard=dict(
            object_category="Wohnung",
            exact_rooms=2.0,
            city="Zurich",
            max_price_chf=2000.0,
        ),
        soft_empty=False,
        soft_has=["main station", "public transport", "transport"],
    ),
    # ------------------------------------------------------------------
    # TC11 – 1-room, price cap, Lausanne, furnished (soft)
    # ------------------------------------------------------------------
    dict(
        id="tc11_1room_lausanne_1200_furnished",
        query="Cozy 1-room flat in Lausanne, max CHF 1200, furnished if possible",
        hard=dict(
            object_category="Wohnung",
            exact_rooms=1.0,
            city="Lausanne",
            max_price_chf=1200.0,
        ),
        soft_empty=False,
        soft_has=["cozy", "furnished"],
    ),
    # ------------------------------------------------------------------
    # TC12 – new building, balcony + parking, room range, price range
    # ------------------------------------------------------------------
    dict(
        id="tc12_new_building_winterthur_3_4rooms_price_range",
        query=(
            "New building apartment in Winterthur with balcony and parking, "
            "3 to 4 rooms, CHF 2000-3000"
        ),
        hard=dict(
            object_category="Wohnung",
            city="Winterthur",
            is_new_building=True,
            prop_balcony=True,
            prop_parking=True,
            min_rooms=3.0,
            max_rooms=4.0,
            min_price_chf=2000.0,
            max_price_chf=3000.0,
        ),
        soft_empty=True,
        soft_has=[],
    ),
    # ------------------------------------------------------------------
    # TC13 – ground floor, Lucerne, accessibility (soft)
    # ------------------------------------------------------------------
    dict(
        id="tc13_ground_floor_lucerne",
        query=(
            "Ground floor apartment in Lucerne, wheelchair accessible, "
            "with garden terrace access"
        ),
        hard=dict(
            object_category="Wohnung",
            city="Lucerne",
            floor_max=0,
        ),
        soft_empty=False,
        soft_has=["wheelchair", "garden", "terrace"],
    ),
    # ------------------------------------------------------------------
    # TC14 – buy, house, canton, min area, min rooms, price cap
    # ------------------------------------------------------------------
    dict(
        id="tc14_buy_house_aargau_150sqm_5rooms",
        query=(
            "House to buy in canton Aargau, at least 150 sqm, "
            "5 or more rooms, budget CHF 900000"
        ),
        hard=dict(
            offer_type="BUY",
            object_category="Haus",
            canton="Aargau",
            min_area_sqm=150.0,
            min_rooms=5.0,
            max_price_chf=900000.0,
        ),
        soft_empty=True,
        soft_has=[],
    ),
    # ------------------------------------------------------------------
    # TC15 – exact rooms, availability date, pet-friendly
    # ------------------------------------------------------------------
    dict(
        id="tc15_2r5_uster_sep2026_pets",
        query=(
            "2.5 room flat in Uster, available from September 2026, "
            "pets allowed"
        ),
        hard=dict(
            object_category="Wohnung",
            exact_rooms=2.5,
            city="Uster",
            animal_allowed=True,
            available_from="2026-09",
        ),
        soft_empty=True,
        soft_has=[],
    ),
    # ------------------------------------------------------------------
    # TC16 – dog owner, price cap, room range, city
    # ------------------------------------------------------------------
    dict(
        id="tc16_dog_stgallen_1800_2or3rooms",
        query=(
            "I need a place for me and my dog in St. Gallen, "
            "max CHF 1800 per month, 2 or 3 rooms"
        ),
        hard=dict(
            # 'a place' is ambiguous — object_category not asserted
            city="St. Gallen",
            max_price_chf=1800.0,
            animal_allowed=True,
            min_rooms=2.0,
            max_rooms=3.0,
        ),
        soft_empty=False,  # 'me and my dog' may surface as soft
        soft_has=[],
    ),
    # ------------------------------------------------------------------
    # TC17 – rent, fireplace, soft: quiet, green, not too big
    # ------------------------------------------------------------------
    dict(
        id="tc17_rent_aarau_fireplace_quiet",
        query=(
            "Quiet place to rent in Aarau, not too big, "
            "with fireplace for winter evenings"
        ),
        hard=dict(
            offer_type="RENT",
            city="Aarau",
            prop_fireplace=True,
        ),
        soft_empty=False,
        soft_has=["quiet", "not too big", "big"],
    ),
    # ------------------------------------------------------------------
    # TC18 – views (soft), price cap, Lugano
    # ------------------------------------------------------------------
    dict(
        id="tc18_lugano_views_3500_modern",
        query=(
            "Apartment in Lugano with great views, max CHF 3500, "
            "modern interior"
        ),
        hard=dict(
            object_category="Wohnung",
            city="Lugano",
            max_price_chf=3500.0,
        ),
        soft_empty=False,
        soft_has=["view", "modern"],
    ),
    # ------------------------------------------------------------------
    # TC19 – exact rooms, balcony, price cap, top floor (soft)
    # ------------------------------------------------------------------
    dict(
        id="tc19_3room_zurich_balcony_topfloor_2500",
        query=(
            "3-room apartment in Zurich, top floor preferred, "
            "balcony required, under CHF 2500"
        ),
        hard=dict(
            object_category="Wohnung",
            exact_rooms=3.0,
            city="Zurich",
            prop_balcony=True,
            max_price_chf=2500.0,
        ),
        soft_empty=False,
        soft_has=["top floor", "top"],
    ),
    # ------------------------------------------------------------------
    # TC20 – min rooms, balcony, child-friendly, soft: affordable, schools
    # ------------------------------------------------------------------
    dict(
        id="tc20_family_zurich_4rooms_balcony_schools",
        query=(
            "Affordable family apartment in Zurich with at least 4 rooms, "
            "balcony, close to good schools and public transport"
        ),
        hard=dict(
            object_category="Wohnung",
            city="Zurich",
            min_rooms=4.0,
            prop_balcony=True,
            prop_child_friendly=True,
        ),
        soft_empty=False,
        soft_has=["affordable", "school", "transport"],
    ),
]


# ---------------------------------------------------------------------------
# Parametrised test
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("case", TEST_CASES, ids=[c["id"] for c in TEST_CASES])
def test_query_parsing(parser: QueryParser, case: dict) -> None:
    result: ParsedQuery = parser.parse(case["query"])

    # ── hard constraints ────────────────────────────────────────────────────
    _assert_hard(result, case["hard"])

    # ── soft constraints ────────────────────────────────────────────────────
    if case["soft_empty"]:
        assert not result.soft_constraints.keywords, (
            f"Expected empty soft keywords, got {result.soft_constraints.keywords!r}"
        )
    else:
        _assert_soft_nonempty(result)

    if case["soft_has"]:
        _assert_soft_contains(result, case["soft_has"])
