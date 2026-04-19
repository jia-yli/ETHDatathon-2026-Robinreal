import json
import re
import sqlite3
import unicodedata
from pathlib import Path
from typing import Any, List, Dict, Tuple

from rapidfuzz import process as _fuzz_process, fuzz as _fuzz

from app.models.rules import _is_non_residential_query, is_residential_query

def load_jsonl(file_path: Path) -> List[Dict]:
    """Load JSONL file with concatenated JSON objects."""
    raw = file_path.read_text(encoding="utf-8")
    records = []
    start = None
    depth = 0
    in_string = False
    escape = False

    for index, char in enumerate(raw):
        if escape:
            escape = False
            continue
        if char == "\\":
            escape = True
            continue
        if char == '"':
            in_string = not in_string
            continue
        if in_string:
            continue
        if char == "{":
            if depth == 0:
                start = index
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0 and start is not None:
                block = raw[start : index + 1]
                records.append(json.loads(block))
                start = None

    return records

def load_all_constraints(file_path: Path = None) -> List[List[Dict]]:
    """Load all constraints from the JSONL file, grouped by query."""
    if file_path is None:
        file_path = Path("tests/output/query_parser_results.jsonl")

    records = load_jsonl(file_path)

    # Collect constraints grouped by query
    query_constraints = []
    for record in records:
        parsed = record.get("parsed", {})
        constraints = parsed.get("constraints", [])
        query_constraints.append(constraints)

    return query_constraints

def process_constraints(query_constraints: List[Dict], original_query: str) -> Tuple[Dict, Dict, Dict]:
    """Process constraints for a single query and return hard/soft/vague-soft query dictionaries."""
    clear = [c for c in query_constraints if c.get("clarity") == "clear"]
    vague = [c for c in query_constraints if c.get("clarity") == "vague"]

    hard_for_query = [c for c in clear if c.get("constraint_type") == "hard"]
    soft_for_query = [c for c in clear if c.get("constraint_type") in ["hard", "soft"]]
    vague_soft_for_query = [c for c in vague if c.get("constraint_type") in ["hard", "soft"]]

    hard_constraint_dict = {
        "original_query": original_query,
        "constraint_list": hard_for_query,
    }
    soft_constraint_dict = {
        "original_query": original_query,
        "constraint_list": soft_for_query,
    }
    vague_soft_constraint_dict = {
        "original_query": original_query,
        "constraint_list": vague_soft_for_query,
    }

    return hard_constraint_dict, soft_constraint_dict, vague_soft_constraint_dict


def process_all_query_constraints(query_constraints: List[List[Dict]], queries: List[str]) -> Tuple[List[Dict], List[Dict], List[Dict]]:
    """Process all queries and return lists of hard/soft/vague-soft query dictionaries."""
    hard_constraints = []
    soft_constraints = []
    vague_soft_constraints = []
    for query_constraint_list, original_query in zip(query_constraints, queries):
        hard_dict, soft_dict, vague_soft_dict = process_constraints(query_constraint_list, original_query)
        hard_constraints.append(hard_dict)
        soft_constraints.append(soft_dict)
        vague_soft_constraints.append(vague_soft_dict)
    return hard_constraints, soft_constraints, vague_soft_constraints


KEY_TO_FIELD: dict[str, str] = {
    "number_of_rooms": "rooms",
    "object_city": "city",
    "object_state": "canton",
    "object_zip": "postal_code",
    "price": "price",
    "offer_type": "offer_type",
    "object_type": "object_type",
    "object_category": "object_category",
    "postal_code": "postal_code",
    "available_from": "available_from",
    "geo_lat": "latitude",
    "geo_lng": "longitude",
}

# DB columns (or derived boolean features) that hard-constraint eval can
# actually resolve to a non-None value.  Any constraint key that maps
# outside this set (e.g. "commute_to_eth_minutes", "distance_to_eth")
# has no DB field and would always return None → False, eliminating every
# candidate for residential queries.  Such keys are skipped from hard
# filtering (they may still influence soft scoring via LLM pairwise).
_KNOWN_HARD_FILTERABLE_FIELDS: frozenset[str] = frozenset({
    # via KEY_TO_FIELD
    "rooms", "city", "canton", "price", "offer_type",
    "object_type", "object_category", "postal_code", "available_from",
    # direct DB column names the LLM might use
    "area", "distance_public_transport", "distance_shop",
    "distance_kindergarten", "distance_school_1", "distance_school_2",
    # feature booleans
    "feature_balcony", "feature_elevator", "feature_parking",
    "feature_garage", "feature_fireplace", "feature_child_friendly",
    "feature_pets_allowed", "feature_temporary", "feature_new_build",
    "feature_wheelchair_accessible", "feature_private_laundry",
    "feature_minergie_certified",
    # LLM-generated type assertions resolved via object_type column
    "is_house", "is_apartment",
})


def _extract_column(expression: str) -> str | None:
    """Extract the first 'column_name' from a 'this.column_name' pattern."""
    m = re.search(r'\bthis\.([a-zA-Z_][a-zA-Z0-9_]*)\b', expression)
    return m.group(1) if m else None


def _normalize_expression(expression: str, column: str) -> str:
    """Replace this.column with value and normalize booleans."""
    expression = re.sub(r'\bthis\.' + re.escape(column) + r'\b', 'value', expression)
    expression = re.sub(r"\btrue\b", "True", expression, flags=re.IGNORECASE)
    expression = re.sub(r"\bfalse\b", "False", expression, flags=re.IGNORECASE)
    return expression


def _ascii_fold(s: str) -> str:
    """Lowercase and strip diacritics: Zürich→zurich, Genève→geneve."""
    return unicodedata.normalize("NFKD", s.lower()).encode("ascii", "ignore").decode("ascii")


# Lazily populated map from every folded DB city name → its canonical form.
# Cities sharing a postal code are grouped together; the canonical form is
# the most-frequent variant (ASCII-folded).  This collapses multilingual
# equivalents: "geneva", "geneve", "genf", "geneve" → one shared key.
_CITY_CANONICAL: dict[str, str] = {}


def _load_city_canonical() -> None:
    """Build _CITY_CANONICAL by grouping DB city names via postal code."""
    db_path = Path(__file__).resolve().parents[2] / "data" / "listings.db"
    if not db_path.exists():
        return
    try:
        conn = sqlite3.connect(db_path)
        cur = conn.cursor()
        cur.execute(
            "SELECT city, postal_code, COUNT(*) AS n "
            "FROM listings "
            "WHERE city IS NOT NULL AND postal_code IS NOT NULL "
            "GROUP BY city, postal_code"
        )
        rows = cur.fetchall()
        conn.close()

        # postal_code → {folded_city: total_count}
        postal_counts: dict[str, dict[str, int]] = {}
        for city, postal, n in rows:
            folded = _ascii_fold(city)
            postal_counts.setdefault(postal, {}).setdefault(folded, 0)
            postal_counts[postal][folded] += n

        # For each postal code, pick the most-frequent variant as canonical;
        # all variants in that group map to it.
        for counts in postal_counts.values():
            canonical = max(counts, key=lambda c: counts[c])
            for variant in counts:
                # Only update if not already set (first postal code wins)
                _CITY_CANONICAL.setdefault(variant, canonical)
    except Exception:
        pass


def _normalize_city(s: str) -> str:
    """Return the canonical city name for s.

    Folds diacritics/case, then looks up the postal-code-based canonical map
    so that multilingual variants ("Geneva", "Genève", "Genf") all resolve to
    the same key.  Falls back to plain ASCII fold for unknown names, with a
    rapidfuzz fuzzy match against known canonical forms as a last resort.
    """
    if not _CITY_CANONICAL:
        _load_city_canonical()
    folded = _ascii_fold(s)
    if not _CITY_CANONICAL:
        return folded
    # Exact hit in the canonical map (covers all DB variants)
    if folded in _CITY_CANONICAL:
        return _CITY_CANONICAL[folded]
    # Unknown name (e.g. LLM used a spelling not in DB): fuzzy-match against
    # the set of canonical forms to find the closest known city.
    canonicals = set(_CITY_CANONICAL.values())
    result = _fuzz_process.extractOne(folded, canonicals, scorer=_fuzz.token_sort_ratio)
    if result is not None:
        match, score, _ = result
        if score >= 80:
            return match
    return folded


def _normalize_str_literals(expression: str) -> str:
    """ASCII-fold every quoted string literal inside an expression."""
    return re.sub(r"'([^']*)'|\"([^\"]*)\"", lambda m: repr(_ascii_fold(m.group(1) or m.group(2))), expression)


def _resolve_candidate_value(candidate: Dict[str, Any], key: str) -> Any:
    """Resolve the candidate value corresponding to a constraint key."""
    mapped_key = KEY_TO_FIELD.get(key, key)
    value = candidate.get(mapped_key)
    if value is not None:
        return value

    # Fallback for feature-like keys stored in the features list
    features = candidate.get("features")
    if isinstance(features, list):
        if key.startswith("prop_"):
            return key.replace("prop_", "") in features
        if key.startswith("vibe_"):
            return key.replace("vibe_", "") in features
        if key.startswith("view_"):
            return key.replace("view_", "") in features

    # Map LLM-generated is_* type assertions to DB object_type where possible.
    # When object_type is NULL (96% of listings), fall back to title/description
    # keyword matching so that houses labelled in their title still pass.
    _HOUSE_TYPES = frozenset({
        "Einfamilienhaus", "Doppeleinfamilienhaus", "Reihenhaus", "Villa",
        "Landhaus", "Bauernhaus", "Chalet",
    })
    _APARTMENT_TYPES = frozenset({
        "Wohnung", "Attikawohnung", "Dachwohnung", "Maisonette / Duplex",
        "Terrassenwohnung", "Möbliertes Wohnobjekt", "Einzelzimmer",
    })
    _HOUSE_KEYWORDS = (
        "einfamilienhaus", "reihenhaus", "villa", "chalet", "landhaus",
        "bauernhaus", "doppelhaus", "doppeleinfamilienhaus",
    )
    _APARTMENT_KEYWORDS = (
        "wohnung", "appartement", "apartment", "studio", "zimmer-wohnung",
    )
    otype = candidate.get("object_type")
    if key in ("is_house", "is_apartment"):
        if otype in _HOUSE_TYPES:
            result = True if key == "is_house" else False
        elif otype in _APARTMENT_TYPES:
            result = False if key == "is_house" else True
        else:
            # object_type is NULL — infer from title text only (descriptions are
            # too noisy: apartments often mention house styles in marketing copy).
            title_lower = (candidate.get("title") or "").lower()
            has_house_kw = any(kw in title_lower for kw in _HOUSE_KEYWORDS)
            has_apt_kw = any(kw in title_lower for kw in _APARTMENT_KEYWORDS)
            if key == "is_house":
                result = True if has_house_kw else (False if has_apt_kw else None)
            else:  # is_apartment
                result = True if has_apt_kw else (False if has_house_kw else None)
        return result

    return None


def _evaluate_constraint(
    candidate: Dict[str, Any],
    constraint: Dict[str, Any],
    is_non_residential: bool = False,
) -> bool:
    """Return True if the candidate satisfies the constraint expression.

    When the DB has no value for the constrained field (value is None):
    - Non-residential query: pass through (True) — e.g. availability_immediate
      has no DB column so we can't verify it; don't penalise the listing.
    - Residential query: fail (False) — be strict so spurious constraints
      don't let unrelated listings through.
    """
    expression = constraint.get("expression", "")
    clarity = constraint.get("clarity", "clear")
    if not expression or clarity == "vague":
        return False

    column = _extract_column(expression)
    if not column:
        return False

    value = _resolve_candidate_value(candidate, column)
    if value is None:
        # For is_house/is_apartment: a None value means object_type is NULL.
        # Apply strictly — listing must have a confirmed matching object_type.
        if column.startswith("is_"):
            return False
        return is_non_residential

    # For string values (city names, etc.) normalize diacritics and case so that
    # 'Zürich' matches 'Zurich', 'Genève' matches 'Geneva', etc.
    if isinstance(value, str):
        if column == "object_city" or KEY_TO_FIELD.get(column) == "city":
            value = _normalize_city(value)
            expression = re.sub(
                r"'([^']*)'|\"([^\"]*)\"",
                lambda m: repr(_normalize_city(m.group(1) or m.group(2))),
                expression,
            )
        else:
            value = _ascii_fold(value)
            expression = _normalize_str_literals(expression)

    normalized = _normalize_expression(expression, column)

    try:
        return bool(eval(normalized, {"__builtins__": None}, {"value": value}))
    except Exception:
        return False


# Keys skipped in hard-constraint filtering:
# - object_type / object_category: delegated to filter_non_residential
# - prop_* / vibe_* / view_*: feature flags that live in individual boolean
#   columns not fetched by the SQL query (features_json is [] for most rows).
#   Treating them as hard constraints eliminates all candidates.  They are
#   still used for soft scoring via get_soft_filter_scores.
def _is_feature_key(key: str) -> bool:
    # prop_*/vibe_*/view_* are feature flags with no direct DB column.
    # is_house/is_apartment are resolved via object_type and are hard-filterable.
    return key.startswith(("prop_", "vibe_", "view_"))


def _is_known_filterable(key: str) -> bool:
    """Return True only if this key resolves to a real DB column we can eval against.

    Keys outside this set (e.g. "commute_to_eth_minutes", "distance_to_eth")
    have no DB field and would always evaluate to None → False for residential
    queries, eliminating every candidate.  Such keys are dropped from hard
    filtering; they may still influence soft / LLM pairwise scoring.
    """
    field = KEY_TO_FIELD.get(key, key)
    return field in _KNOWN_HARD_FILTERABLE_FIELDS

_CATEGORY_KEYS: frozenset[str] = frozenset({"object_type", "object_category"})

# Keys excluded from hard filtering: only 1 SALE listing exists in the dataset
# so treating offer_type as a hard filter makes all buy queries return 0 results.
_SOFT_ONLY_KEYS: frozenset[str] = frozenset({"offer_type"})

# Institution keywords (in constraint key names) → canonical city they're located in.
# Used as a fallback when the LLM generates a commute/proximity constraint for a
# named institution but forgets to emit the corresponding object_city constraint.
_INSTITUTION_CITY: dict[str, str] = {
    "eth": "Zurich",
    "epfl": "Lausanne",
    "unige": "Geneva",
    "unibas": "Basel",
    "unibern": "Bern",
    "unil": "Lausanne",
    "hec": "Lausanne",
    "usi": "Lugano",
}


def _infer_city_from_institution_constraints(constraints: list[dict]) -> list[dict]:
    """Return implicit object_city hard constraints inferred from institution references.

    If the LLM emitted a proximity constraint targeting a named Swiss institution
    (e.g. 'near ETH Zurich') but no object_city constraint, synthesize one so that
    geographically irrelevant listings are filtered out.
    """
    has_city = any("this.object_city" in c.get("expression", "") for c in constraints)
    if has_city:
        return []
    for c in constraints:
        search_text = (
            c.get("source_phrase", "") + " " + c.get("expression", "")
        ).lower()
        for institution, city in _INSTITUTION_CITY.items():
            if institution in search_text:
                return [{
                    "expression": f"this.object_city == '{city}'",
                    "clarity": "clear",
                    "constraint_type": "hard",
                    "source_phrase": c.get("source_phrase", ""),
                }]
    return []

def filter_hard_facts_via_exec(candidates: List[Dict], hard_constraints: Dict, query: str = "") -> List[Dict]:
    """Filter candidates based on hard constraints using eval and the candidate's own attributes."""
    is_non_res = _is_non_residential_query(query) and not is_residential_query(query) if query else False
    filtered_candidates = []
    raw_constraints = hard_constraints.get("constraint_list", [])
    # If the LLM missed a city constraint for a named institution commute target,
    # synthesize one to keep geographic filtering intact.
    inferred = _infer_city_from_institution_constraints(raw_constraints)
    constraints = [
        c for c in (inferred + raw_constraints)
        if (col := _extract_column(c.get("expression", ""))) is not None
        and col not in _CATEGORY_KEYS
        and col not in _SOFT_ONLY_KEYS
        and not _is_feature_key(col)
        and _is_known_filterable(col)
    ]

    for candidate in candidates:
        all_passed = True
        for constraint in constraints:
            if not _evaluate_constraint(candidate, constraint, is_non_residential=is_non_res):
                all_passed = False
                break
        if all_passed:
            filtered_candidates.append(candidate)
    return filtered_candidates
