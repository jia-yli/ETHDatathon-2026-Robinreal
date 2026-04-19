"""
Integration tests for the query_parsing layer.

Test cases are loaded from datasets/user_query/test_cases.csv.
Each test makes a real LLM call and validates the structured ParsedQuery output.
All results are dumped to tests/output/query_parser_results.jsonl for human review.

The new output format is a flat list of Constraint objects — one per house attribute.
Each constraint has: source_phrase, constraint_type, clarity, expression (clear only).

Matching strategy (key field was removed from schema):
  - Clear constraints are matched by detecting 'this.<key>' in the expression.
  - Vague constraints (no expression) are matched by counting: every expected
    vague key must correspond to at least one vague constraint in the output.
"""

import csv
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

import pytest

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from query_parsing import QueryParser
from query_parsing.schema import Constraint, ParsedQuery

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

CSV_PATH   = PROJECT_ROOT / "datasets" / "user_query" / "test_cases.csv"
OUTPUT_DIR = Path(__file__).parent / "output"
OUTPUT_FILE = OUTPUT_DIR / "query_parser_results.jsonl"


# ---------------------------------------------------------------------------
# CSV loader
# ---------------------------------------------------------------------------

def _split_pipe(val):
    v = val.strip()
    return [p.strip() for p in v.split("|") if p.strip()] if v else []


def _parse_expected_values(val):
    """
    Parse 'expected_values' column into {key: [fragment, ...]} dict.
    Format: 'key~~fragment|key~~fragment2'
    """
    result = {}
    for entry in _split_pipe(val):
        if "~~" not in entry:
            continue
        k, fragment = entry.split("~~", 1)
        result.setdefault(k.strip(), []).append(fragment.strip())
    return result


def load_test_cases():
    cases = []
    with open(CSV_PATH, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            cases.append({
                "id":                  row["id"].strip(),
                "query":               row["query"].strip(),
                "expected_hard_keys":  _split_pipe(row.get("expected_hard_keys", "")),
                "expected_soft_keys":  _split_pipe(row.get("expected_soft_keys", "")),
                "expected_values":     _parse_expected_values(row.get("expected_values", "")),
            })
    return cases


TEST_CASES = load_test_cases()


# ---------------------------------------------------------------------------
# Matching helpers
# ---------------------------------------------------------------------------

def _is_vague_key(key):
    """Keys starting with 'vibe_' never have a column and are always vague."""
    return key.startswith("vibe_")


def _find_clear(result, key):
    """
    Find a clear constraint whose expression references 'this.<key>'.
    Returns the first match or None.
    """
    pattern = f"this.{key}"
    for c in result.constraints:
        if c.clarity == "clear" and c.expression and pattern in c.expression:
            return c
    return None


def _assert_has_key(result, key, expected_type):
    """Assert a constraint for *key* exists with the expected constraint_type."""
    if _is_vague_key(key):
        # Vague keys have no expression; just confirm at least one vague constraint exists.
        vague = [c for c in result.constraints if c.clarity == "vague"]
        assert vague, (
            f"Expected at least one vague constraint (checking key='{key}'), "
            f"but none found in: {[c.source_phrase for c in result.constraints]}"
        )
        return

    c = _find_clear(result, key)
    assert c is not None, (
        f"Expected a clear constraint referencing 'this.{key}' ({expected_type}), "
        f"expressions found: {[x.expression for x in result.constraints if x.expression]}"
    )
    assert c.constraint_type == expected_type, (
        f"Constraint for 'this.{key}' expected constraint_type='{expected_type}', "
        f"got '{c.constraint_type}' (source_phrase='{c.source_phrase}')"
    )


def _assert_value_fragments(result, expected_values):
    """
    For each key, check that a clear constraint referencing 'this.<key>'
    exists and that all fragments appear in its expression.
    """
    for key, fragments in expected_values.items():
        if _is_vague_key(key):
            continue  # vague constraints have no expression to check
        c = _find_clear(result, key)
        assert c is not None, (
            f"expected_values check: no clear constraint with 'this.{key}' found; "
            f"expressions: {[x.expression for x in result.constraints if x.expression]}"
        )
        expr_lower = c.expression.lower()
        for fragment in fragments:
            assert fragment.lower() in expr_lower, (
                f"Constraint for 'this.{key}': expression '{c.expression}' "
                f"does not contain expected fragment '{fragment}'"
            )


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def parser():
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
def test_query_parsing(parser, case, prepare_output_dir):
    result = parser.parse(case["query"])

    entry = {
        "id":     case["id"],
        "query":  case["query"],
        "parsed": result.model_dump(),
    }
    with open(OUTPUT_FILE, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")

    assert result.constraints, "Expected non-empty constraints list"

    for key in case["expected_hard_keys"]:
        _assert_has_key(result, key, "hard")

    for key in case["expected_soft_keys"]:
        _assert_has_key(result, key, "soft")

    _assert_value_fragments(result, case["expected_values"])


