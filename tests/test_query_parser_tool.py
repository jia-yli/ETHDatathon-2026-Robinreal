"""
Integration + execution tests for QueryParserTool.

Three test layers:
  1. Static sanity — validate config files structure (no LLM, no CSV)
  2. Eval offline  — evaluate known expressions against sample_properties.csv
  3. LLM + eval   — parse query via DeepSeek, then execute all clear expressions
                    against the CSV and verify boolean results per row

Backend simulation
------------------
PropertyFilter is a minimal example of how a real backend would consume the
parser output.  It supports all expression tools:
  - compare_numeric  : this.price <= 2500
  - compare_string   : this.object_city == 'Zurich'
  - boolean_check    : this.prop_balcony == true
  - set_membership   : this.number_of_rooms in [2, 3]
  - date_compare     : this.available_from >= '2026-09-01'
  - distance_column  : this.distance_shop <= 500
  - distance()       : distance(this.geo_lat, this.geo_lng, 47.3769, 8.5476) <= 2

Run with:
    conda run -n datathon pytest tests/test_query_parser_tool.py -v
    conda run -n datathon pytest tests/test_query_parser_tool.py -v -k eval
    conda run -n datathon pytest tests/test_query_parser_tool.py -v -k llm
"""

import json
import sys
from pathlib import Path

import pandas as pd
import pytest

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from query_parsing.filter import EXPR_GLOBALS, PropertyFilter
from query_parsing.parser import QueryParser
from query_parsing.schema import Constraint, ParsedQuery

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

TEST_CASES_FILE = Path(__file__).parent / "test_cases_tool.json"
SAMPLE_CSV      = Path(__file__).parent / "sample_properties.csv"
OUTPUT_DIR      = Path(__file__).parent / "output"
OUTPUT_FILE     = OUTPUT_DIR / "query_parser_tool_results.jsonl"
CONFIG_DIR      = PROJECT_ROOT / "query_parsing" / "config"

# ---------------------------------------------------------------------------
# Backward-compat helpers used by offline eval tests
# ---------------------------------------------------------------------------

def eval_expression_df(expr, df):
    """Evaluate *expr* against every row; returns a boolean pd.Series."""
    return PropertyFilter(df).mask(expr)


# ---------------------------------------------------------------------------
# Sample CSV fixture
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def sample_df():
    """Load sample_properties.csv with correct dtypes."""
    bool_cols = [
        "is_furnished", "prop_balcony", "prop_garage", "prop_elevator",
        "animal_allowed", "is_new_building", "is_house", "is_penthouse",
    ]
    df = pd.read_csv(SAMPLE_CSV)
    for col in bool_cols:
        if col in df.columns:
            df[col] = df[col].map({"True": True, "False": False, True: True, False: False})
    return df


@pytest.fixture(scope="module")
def parser():
    return QueryParser()


@pytest.fixture(scope="module")
def backend(sample_df):
    """Shared PropertyFilter instance wrapping the sample CSV."""
    return PropertyFilter(sample_df)


@pytest.fixture(scope="module", autouse=True)
def prepare_output():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    if OUTPUT_FILE.exists():
        OUTPUT_FILE.unlink()
    yield


def _load_test_cases():
    return json.loads(TEST_CASES_FILE.read_text(encoding="utf-8"))


# ===========================================================================
# LAYER 1 — Static sanity checks (no LLM, no CSV)
# ===========================================================================

def test_features_json_structure():
    """config/features.json has required fields for every entry."""
    features = json.loads((CONFIG_DIR / "features.json").read_text(encoding="utf-8"))
    assert len(features) > 100, "features.json seems too short"
    for feat in features:
        assert "name" in feat,        f"Missing 'name': {feat}"
        assert "type" in feat,        f"Missing 'type' in {feat.get('name')}"
        assert "description" in feat, f"Missing 'description' in {feat.get('name')}"
        assert feat["type"] in ("values", "keywords", "boolean"), (
            f"Unknown type '{feat['type']}' in {feat['name']}"
        )
    # must NOT have source/important any more
    for feat in features:
        assert "source" not in feat,    f"'source' should not appear in config features: {feat['name']}"
        assert "important" not in feat, f"'important' should not appear in config features: {feat['name']}"


def test_tools_json_has_distance():
    """config/tools.json includes the distance function with landmark examples."""
    data = json.loads((CONFIG_DIR / "tools.json").read_text(encoding="utf-8"))
    names = [t["name"] for t in data["tools"]]
    assert "distance" in names
    dist_tool = next(t for t in data["tools"] if t["name"] == "distance")
    assert "landmark_examples" in dist_tool
    assert any("ETH" in k for k in dist_tool["landmark_examples"])
    assert any("EPFL" in k for k in dist_tool["landmark_examples"])


def test_examples_json_no_key_predefined():
    """config/examples.json constraints must not contain 'key' or 'predefined'."""
    examples = json.loads((CONFIG_DIR / "examples.json").read_text(encoding="utf-8"))
    for ex in examples:
        for c in ex["constraints"]:
            assert "key" not in c,       f"'key' should be removed from example constraint: {c}"
            assert "predefined" not in c, f"'predefined' should be removed from example constraint: {c}"


def test_examples_json_clear_use_this_col():
    """All clear constraints in examples use this.column_name or distance() syntax."""
    examples = json.loads((CONFIG_DIR / "examples.json").read_text(encoding="utf-8"))
    for ex in examples:
        for c in ex["constraints"]:
            if c.get("clarity") == "clear":
                expr = c.get("expression", "")
                assert expr, f"Clear constraint in '{ex['query']}' has no expression"
                assert expr.startswith("this.") or expr.startswith("distance("), (
                    f"Expression '{expr}' in '{ex['query']}' does not use this.col syntax"
                )
            elif c.get("clarity") == "vague":
                assert "expression" not in c, (
                    f"Vague constraint in '{ex['query']}' should not have expression"
                )


# ===========================================================================
# LAYER 2 — Expression eval against sample CSV (no LLM)
# ===========================================================================

_OFFLINE_CASES = [
    # (expression, expected_true_ids)  — id is the 'id' column in the CSV
    ("this.price <= 2500",                  [1, 3, 5, 7]),
    ("this.number_of_rooms >= 3",           [1, 2, 4, 5, 6, 8]),
    ("this.object_city == 'Zurich'",        [1, 7, 8]),
    ("this.prop_balcony == true",           [1, 2, 4, 5, 6]),
    ("this.offer_type == 'sale'",           [6]),
    ("this.object_state == 'ZH'",           [1, 5, 7, 8]),
    ("this.number_of_rooms in [2, 3]",      [7]),           # 2.0 → included
    ("this.object_zip in [8001, 8002]",     [1, 8]),
    ("this.animal_allowed == true",         [1, 2, 3, 6, 7]),
    ("this.is_new_building == true",        [5]),
    ("this.is_furnished == true",           [3, 7]),
    ("this.prop_elevator == true",          [1, 4, 6]),
    ("this.distance_shop <= 200",           [1, 3, 4, 7]),       # row 6 has 250 m
    # distance to ETH Zurich centre — rows 1 and 8 are both within 1 km
    ("distance(this.geo_lat, this.geo_lng, 47.3769, 8.5476) <= 1", [1, 8]),
    # distance to EPFL — row 4 is at exactly EPFL coords (46.5191, 6.5668)
    ("distance(this.geo_lat, this.geo_lng, 46.5191, 6.5668) <= 1", [4]),
]


@pytest.mark.parametrize("expr,expected_ids", _OFFLINE_CASES, ids=[c[0][:40] for c in _OFFLINE_CASES])
def test_eval_expression_offline(sample_df, expr, expected_ids):
    """
    Evaluate a hand-crafted expression against the sample CSV and verify
    which property rows (by id column) match.
    """
    mask = eval_expression_df(expr, sample_df)
    assert isinstance(mask, pd.Series), "eval_expression_df must return a pd.Series"
    assert mask.dtype == bool or mask.dtype == object, "result dtype should be bool"

    actual_ids = sorted(sample_df.loc[mask.values, "id"].tolist())
    assert actual_ids == sorted(expected_ids), (
        f"Expression: {expr!r}\n"
        f"  Expected matching IDs: {sorted(expected_ids)}\n"
        f"  Actual   matching IDs: {actual_ids}"
    )


def test_eval_combined_filter(sample_df):
    """
    Combine multiple expressions to filter properties (like a real search).

    Query: 3+ rooms, Zurich, price <= 3000, has balcony
    Expected: row 1 (3.5 rooms, Zurich, 2200, balcony)
    """
    exprs = [
        "this.number_of_rooms >= 3",
        "this.object_city == 'Zurich'",
        "this.price <= 3000",
        "this.prop_balcony == true",
    ]
    mask = pd.Series([True] * len(sample_df), index=sample_df.index)
    for expr in exprs:
        mask = mask & eval_expression_df(expr, sample_df)

    matching = sorted(sample_df.loc[mask.values, "id"].tolist())
    assert matching == [1], (
        f"Combined filter should match only row 1, got: {matching}"
    )


def test_eval_distance_filter(sample_df):
    """
    Filter by distance to Bern main station (46.9490, 7.4390).
    Only row 2 (Bern) should be within 5 km.
    """
    expr = "distance(this.geo_lat, this.geo_lng, 46.9490, 7.4390) <= 5"
    mask = eval_expression_df(expr, sample_df)
    matching = sorted(sample_df.loc[mask.values, "id"].tolist())
    assert matching == [2], (
        f"Only Bern property (id=2) should be within 5 km of Bern HB, got: {matching}"
    )


# ===========================================================================
# LAYER 3 — LLM parse + execute against sample CSV
# ===========================================================================

_LLM_EXEC_CASES = [
    {
        "id": "llm_exec_01",
        "query": "Apartment in Zurich under CHF 2500, with balcony",
        "expected_matching_ids": [1],
        "notes": "Only row 1 is in Zurich, <= 2500, has balcony",
    },
    {
        "id": "llm_exec_02",
        "query": "New building apartment in Winterthur",
        "expected_matching_ids": [5],
        "notes": "Only row 5 is is_new_building=True in Winterthur",
    },
]


@pytest.mark.parametrize("case", _LLM_EXEC_CASES, ids=[c["id"] for c in _LLM_EXEC_CASES])
def test_llm_parse_and_exec(parser, backend, sample_df, case):
    """
    End-to-end: parse query via LLM, hand off to PropertyFilter, assert matching rows.
    """
    result = parser.parse(case["query"])
    assert result.constraints, f"[{case['query']}] LLM returned no constraints"

    entry = {"id": case["id"], "query": case["query"], "parsed": result.model_dump()}
    with open(OUTPUT_FILE, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")

    # All clear constraints must produce executable expressions
    clear_exprs = [c.expression for c in result.constraints if c.clarity == "clear" and c.expression]
    assert clear_exprs, f"[{case['query']}] No clear expressions produced"

    # Apply via the PropertyFilter backend; catch eval errors with useful messages
    try:
        matched_df, counts = backend.apply(result)
    except Exception as exc:
        pytest.fail(f"[{case['query']}] PropertyFilter.apply() raised: {exc}\n"
                    f"Expressions: {clear_exprs}")

    matching = sorted(matched_df["id"].tolist())

    # Diagnostics printed on failure
    diag = "\n".join(f"  {e!r} → {n} rows" for e, n in counts.items())

    if "expected_matching_ids" in case:
        assert matching == sorted(case["expected_matching_ids"]), (
            f"[{case['query']}]\n{diag}\n"
            f"  Expected IDs: {sorted(case['expected_matching_ids'])}\n"
            f"  Actual   IDs: {matching}"
        )
    elif "expected_matching_ids_contains" in case:
        for eid in case["expected_matching_ids_contains"]:
            assert eid in matching, (
                f"[{case['query']}]\n{diag}\n"
                f"  Expected ID {eid} to appear in {matching}"
            )


@pytest.mark.parametrize("case", _load_test_cases(), ids=[c["id"] for c in _load_test_cases()])
def test_llm_parse_expressions(parser, case):
    """
    Parse query via LLM and check that the output contains expected expressions
    (by substring matching) and correct vague counts.
    """
    query = case["query"]
    result = parser.parse(query)

    # Write output
    entry = {"id": case["id"], "query": query, "parsed": result.model_dump()}
    with open(OUTPUT_FILE, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")

    assert result.constraints, f"[{query}] No constraints returned"

    # All clear constraints must have this.col or distance( expressions
    for c in result.constraints:
        if c.clarity == "clear":
            assert c.expression is not None, (
                f"[{query}] Clear constraint '{c.source_phrase}' has no expression"
            )
            assert c.expression.startswith("this.") or c.expression.startswith("distance("), (
                f"[{query}] Expression '{c.expression}' does not use this.col syntax"
            )
        elif c.clarity == "vague":
            assert c.expression is None, (
                f"[{query}] Vague constraint '{c.source_phrase}' should have no expression"
            )

    # Check expected expression fragments
    all_exprs = " ".join(
        c.expression for c in result.constraints if c.expression
    ).lower()
    for fragments in case.get("expected_expressions_contain", []):
        for frag in fragments:
            assert frag.lower() in all_exprs, (
                f"[{query}] Expected fragment '{frag}' not found in expressions.\n"
                f"  All expressions: {all_exprs!r}"
            )

    # Check vague count
    vague = [c for c in result.constraints if c.clarity == "vague"]
    if "expected_vague_count" in case:
        assert len(vague) == case["expected_vague_count"], (
            f"[{query}] Expected {case['expected_vague_count']} vague constraints, "
            f"got {len(vague)}: {[c.source_phrase for c in vague]}"
        )
    if "expected_vague_count_min" in case:
        assert len(vague) >= case["expected_vague_count_min"], (
            f"[{query}] Expected at least {case['expected_vague_count_min']} vague constraints, "
            f"got {len(vague)}"
        )

    # Check hard phrases
    hard_phrases = {c.source_phrase.lower() for c in result.constraints if c.constraint_type == "hard"}
    for phrase in case.get("expected_hard_phrases", []):
        assert any(phrase.lower() in hp for hp in hard_phrases), (
            f"[{query}] Expected hard phrase '{phrase}' not found.\n"
            f"  Hard phrases: {hard_phrases}"
        )

    # Check soft phrases
    soft_phrases = {c.source_phrase.lower() for c in result.constraints if c.constraint_type == "soft"}
    for phrase in case.get("expected_soft_phrases", []):
        assert any(phrase.lower() in sp for sp in soft_phrases), (
            f"[{query}] Expected soft phrase '{phrase}' not found.\n"
            f"  Soft phrases: {soft_phrases}"
        )
