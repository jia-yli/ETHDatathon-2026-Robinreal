"""
Integration tests for the query_parsing layer.

Test cases are loaded from datasets/user_query/test_cases.csv.
Each test makes a real LLM call and validates the structured ParsedQuery output.
All results are dumped to tests/output/query_parser_results.jsonl for human review.

The new output format is a flat list of Constraint objects — one per house attribute.
Each constraint has: source_phrase, key, predefined, constraint_type, expression.
"""

from __future__ import annotations

import csv
import json
import sys
from pathlib import Path
from typing import Any, Dict, List

import pytest

# Make the project root importable regardless of invocation directory
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from query_parsing import QueryParser
from query_parsing.schema import Constraint, ParsedQuery

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

CSV_PATH = PROJECT_ROOT / "datasets" / "user_query" / "test_cases.csv"
OUTPUT_DIR = Path(__file__).parent / "output"
OUTPUT_FILE = OUTPUT_DIR / "query_parser_results.jsonl"


# ---------------------------------------------------------------------------
# CSV loader
# ---------------------------------------------------------------------------

def _split_pipe(val: str) -> List[str]:
    v = val.strip()
    return [p.strip() for p in v.split("|") if p.strip()] if v else []


def _parse_expected_values(val: str) -> Dict[str, List[str]]:
    """
    Parse 'expected_values' column into {key: [fragment, ...]} dict.
    Format: 'key~~fragment|key~~fragment2|key~~fragment3'
    Multiple entries with the same key are ANDed (all fragments must appear in value).
    """
    result: Dict[str, List[str]] = {}
    for entry in _split_pipe(val):
        if "~~" not in entry:
            continue
        k, fragment = entry.split("~~", 1)
        result.setdefault(k.strip(), []).append(fragment.strip())
    return result


def load_test_cases() -> List[Dict[str, Any]]:
    """Read test_cases.csv and return a list of structured dicts."""
    cases = []
    with open(CSV_PATH, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            cases.append({
                "id": row["id"].strip(),
                "query": row["query"].strip(),
                "expected_hard_keys": _split_pipe(row.get("expected_hard_keys", "")),
                "expected_soft_keys": _split_pipe(row.get("expected_soft_keys", "")),
                "expected_values": _parse_expected_values(row.get("expected_values", "")),
            })
    return cases


TEST_CASES = load_test_cases()


# ---------------------------------------------------------------------------
# Assertion helpers
# ---------------------------------------------------------------------------

def _find_constraint(result: ParsedQuery, key: str) -> Constraint | None:
    """Return the first predefined constraint whose key matches exactly."""
    for c in result.constraints:
        if c.key == key and c.predefined:
            return c
    return None


def _assert_has_key(result: ParsedQuery, key: str, expected_type: str) -> None:
    c = _find_constraint(result, key)
    assert c is not None, (
        f"Expected a constraint with key='{key}' ({expected_type}), "
        f"but got keys: {[x.key for x in result.constraints]}"
    )
    assert c.constraint_type == expected_type, (
        f"Constraint '{key}' expected constraint_type='{expected_type}', "
        f"got '{c.constraint_type}'"
    )


def _assert_value_fragments(result: ParsedQuery, expected_values: Dict[str, List[str]]) -> None:
    """For each key, check all fragments appear (case-insensitive) in the constraint's value."""
    for key, fragments in expected_values.items():
        c = _find_constraint(result, key)
        assert c is not None, (
            f"expected_values check: no constraint with key='{key}' found; "
            f"got keys: {[x.key for x in result.constraints]}"
        )
        val_lower = c.expression.lower()
        for fragment in fragments:
            assert fragment.lower() in val_lower, (
                f"Constraint '{key}' value '{c.value}' does not contain "
                f"expected fragment '{fragment}'"
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

    # must produce at least one constraint
    assert result.constraints, "Expected non-empty constraints list"

    # check expected hard constraints (key + type)
    for key in case["expected_hard_keys"]:
        _assert_has_key(result, key, "hard")

    # check expected soft constraints (key + type)
    for key in case["expected_soft_keys"]:
        _assert_has_key(result, key, "soft")

    # check expected value fragments
    _assert_value_fragments(result, case["expected_values"])

