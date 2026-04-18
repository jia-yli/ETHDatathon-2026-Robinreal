"""
Integration tests for the query_parsing layer.

Test cases are loaded from datasets/user_query/test_cases.csv.
Each test makes a real LLM call and validates the structured ParsedQuery output.
All results are dumped to tests/output/query_parser_results.jsonl for human review.

Coverage across 20 cases (see CSV for details)
----------------------------------------------
offer_type       : RENT x2, SALE x3, unspecified x15
object_category  : Wohnung x13, Haus x4, unspecified x3
rooms            : exact x8, min x4, max x2, range x2, none x4
price            : max x11, range x2, none x7
location         : city x16, canton(object_state) x3, zip x0
amenities        : balcony x5, parking x4, elevator x2, garage x2, fireplace x2
other hard       : animal_allowed x3, child_friendly x2, new_building x2,
                   available_from x2, floor x1, area x2
soft constraints : asserted non-empty for cases with vague language
"""

from __future__ import annotations

import csv
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

import pytest

# Make the project root importable regardless of invocation directory
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from query_parsing import QueryParser
from query_parsing.schema import ParsedQuery

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

CSV_PATH = PROJECT_ROOT / "datasets" / "user_query" / "test_cases.csv"
OUTPUT_DIR = Path(__file__).parent / "output"
OUTPUT_FILE = OUTPUT_DIR / "query_parser_results.jsonl"


# ---------------------------------------------------------------------------
# CSV loader
# ---------------------------------------------------------------------------

def _parse_bool(val: str) -> Optional[bool]:
    v = val.strip()
    if v == "True":
        return True
    if v == "False":
        return False
    return None


def _parse_float(val: str) -> Optional[float]:
    v = val.strip()
    return float(v) if v else None


def _parse_int(val: str) -> Optional[int]:
    v = val.strip()
    return int(v) if v else None


def _parse_str(val: str) -> Optional[str]:
    v = val.strip()
    return v if v else None


def load_test_cases() -> List[Dict[str, Any]]:
    """Read test_cases.csv and return a list of structured dicts."""
    cases = []
    with open(CSV_PATH, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            hard: Dict[str, Any] = {}
            for col in ("offer_type", "object_category", "object_city", "object_zip",
                        "object_state", "available_from"):
                v = _parse_str(row[col])
                if v is not None:
                    hard[col] = v
            for col in ("exact_rooms", "min_rooms", "max_rooms",
                        "min_price_chf", "max_price_chf",
                        "min_area_sqm", "max_area_sqm"):
                v = _parse_float(row[col])
                if v is not None:
                    hard[col] = v
            for col in ("prop_balcony", "prop_elevator", "prop_parking",
                        "prop_garage", "prop_fireplace", "prop_child_friendly",
                        "animal_allowed", "is_new_building"):
                v = _parse_bool(row[col])
                if v is not None:
                    hard[col] = v
            for col in ("floor_min", "floor_max"):
                v = _parse_int(row[col])
                if v is not None:
                    hard[col] = v

            soft_empty = _parse_bool(row["soft_empty"])
            raw_soft = row["soft_has"].strip()
            soft_has = [p.strip() for p in raw_soft.split("|") if p.strip()] if raw_soft else []

            cases.append({
                "id": row["id"].strip(),
                "query": row["query"].strip(),
                "hard": hard,
                "soft_empty": soft_empty,
                "soft_has": soft_has,
            })
    return cases


TEST_CASES = load_test_cases()


# ---------------------------------------------------------------------------
# Assertion helpers
# ---------------------------------------------------------------------------

def _city_match(actual: Optional[str], expected: str) -> bool:
    if actual is None:
        return False
    def norm(s: str) -> str:
        return s.lower().replace("ü", "u").replace("ö", "o").replace("ä", "a")
    return norm(expected) in norm(actual) or norm(actual) in norm(expected)


def _assert_hard(result: ParsedQuery, checks: Dict[str, Any]) -> None:
    hc = result.hard_constraints
    for field, expected in checks.items():
        actual = getattr(hc, field)
        if field in ("object_city", "object_state"):
            assert _city_match(actual, expected), (
                f"[{field}] expected ~'{expected}', got '{actual}'"
            )
        elif field == "available_from":
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
    kws_lower = " ".join(result.soft_constraints.keywords).lower()
    raw_lower = (result.soft_constraints.raw_description or "").lower()
    combined = kws_lower + " " + raw_lower
    found = any(p.lower() in combined for p in phrases)
    assert found, (
        f"Expected one of {phrases!r} in soft constraints, "
        f"got keywords={result.soft_constraints.keywords!r}"
    )


# ---------------------------------------------------------------------------
# Shared parser + output file fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def parser() -> QueryParser:
    return QueryParser()


@pytest.fixture(scope="module", autouse=True)
def prepare_output_dir():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    if OUTPUT_FILE.exists():
        OUTPUT_FILE.unlink()
    yield


# ---------------------------------------------------------------------------
# Parametrised test
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("case", TEST_CASES, ids=[c["id"] for c in TEST_CASES])
def test_query_parsing(parser: QueryParser, case: dict, prepare_output_dir) -> None:
    result: ParsedQuery = parser.parse(case["query"])

    # dump result to JSONL for human review
    entry = {
        "id": case["id"],
        "query": case["query"],
        "parsed": result.model_dump(),
    }
    with open(OUTPUT_FILE, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")

    # hard constraints
    _assert_hard(result, case["hard"])

    # soft constraints
    if case["soft_empty"] is True:
        assert not result.soft_constraints.keywords, (
            f"Expected empty soft keywords, got {result.soft_constraints.keywords!r}"
        )
    elif case["soft_empty"] is False:
        _assert_soft_nonempty(result)

    if case["soft_has"]:
        _assert_soft_contains(result, case["soft_has"])
