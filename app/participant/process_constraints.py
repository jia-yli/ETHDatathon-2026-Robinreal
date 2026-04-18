import json
import re
from pathlib import Path
from typing import Any, List, Dict, Tuple

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

def process_constraints(query_constraints: List[Dict], original_query: str) -> Tuple[Dict, Dict]:
    """Process constraints for a single query and return hard/soft query dictionaries."""
    predefined = [c for c in query_constraints if c.get("predefined", False)]

    hard_for_query = [c for c in predefined if c.get("constraint_type") == "hard"]
    soft_for_query = [c for c in predefined if c.get("constraint_type") in ["hard", "soft"]]

    hard_constraint_dict = {
        "original_query": original_query,
        "constraint_list": hard_for_query,
    }
    soft_constraint_dict = {
        "original_query": original_query,
        "constraint_list": soft_for_query,
    }

    return hard_constraint_dict, soft_constraint_dict


def process_all_query_constraints(query_constraints: List[List[Dict]], queries: List[str]) -> Tuple[List[Dict], List[Dict]]:
    """Process all queries and return lists of hard/soft query dictionaries."""
    hard_constraints = []
    soft_constraints = []
    for query_constraint_list, original_query in zip(query_constraints, queries):
        hard_dict, soft_dict = process_constraints(query_constraint_list, original_query)
        hard_constraints.append(hard_dict)
        soft_constraints.append(soft_dict)
    return hard_constraints, soft_constraints


KEY_TO_FIELD: dict[str, str] = {
    "number_of_rooms": "rooms",
    "object_city": "city",
    "object_state": "canton",
    "price": "price",
    "offer_type": "offer_type",
    "object_type": "object_type",
    "object_category": "object_category",
    "postal_code": "postal_code",
    "available_from": "available_from",
}


def _normalize_expression(expression: str) -> str:
    """Replace the special 'this' placeholder with a value variable and normalize booleans."""
    expression = expression.replace("this", "value")
    expression = re.sub(r"\btrue\b", "True", expression, flags=re.IGNORECASE)
    expression = re.sub(r"\bfalse\b", "False", expression, flags=re.IGNORECASE)
    return expression


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

    return None


def _evaluate_constraint(candidate: Dict[str, Any], constraint: Dict[str, Any]) -> bool:
    """Return True if the candidate satisfies the constraint expression."""
    key = constraint.get("key")
    expression = constraint.get("expression", "")
    if not key or not expression:
        return False

    value = _resolve_candidate_value(candidate, key)
    normalized = _normalize_expression(expression)

    try:
        return bool(eval(normalized, {"__builtins__": None}, {"value": value}))
    except Exception as e:
        # print(f"Error evaluating constraint '{normalized}' for key '{key}': {e}")
        return False


def filter_hard_facts_via_exec(candidates: List[Dict], hard_constraints: Dict) -> List[Dict]:
    """Filter candidates based on hard constraints using eval and the candidate's own attributes."""
    filtered_candidates = []
    constraints = hard_constraints.get("constraint_list", [])

    for candidate in candidates:
        all_passed = True
        for constraint in constraints:
            if not _evaluate_constraint(candidate, constraint):
                all_passed = False
                break
        if all_passed:
            filtered_candidates.append(candidate)
    return filtered_candidates

if __name__ == "__main__":
    # Load all constraints from the JSONL file, grouped by query
    file_path = Path("tests/output/query_parser_results.jsonl")
    records = load_jsonl(file_path)
    query_constraints = load_all_constraints(file_path)

    # Extract original queries
    queries = [record.get("query", "") for record in records]

    # Process the constraints into hard and soft dictionaries per query
    hard_constraints, soft_constraints = process_all_query_constraints(query_constraints, queries)

    print("=== HARD CONSTRAINTS ===")
    print(f"Number of queries: {len(hard_constraints)}")
    for i, query_dict in enumerate(hard_constraints):
        print(f"Query {i+1}: {len(query_dict['constraint_list'])} hard constraints")
        print(f"  Original query: {query_dict['original_query']}")
        for constraint in query_dict['constraint_list'][:2]:  # Show first 2 examples
            print(f"  - {constraint['source_phrase']}: {constraint['expression']}")

    print(f"\nTotal hard constraint dictionaries: {len(hard_constraints)}")

    print("\n=== SOFT CONSTRAINTS ===")
    print(f"Number of queries: {len(soft_constraints)}")
    for i, query_dict in enumerate(soft_constraints):
        print(f"Query {i+1}: {len(query_dict['constraint_list'])} soft constraints")
        print(f"  Original query: {query_dict['original_query']}")
        for constraint in query_dict['constraint_list'][:2]:  # Show first 2 examples
            print(f"  - {constraint['source_phrase']}: {constraint['expression']}")

    print(f"\nTotal soft constraint dictionaries: {len(soft_constraints)}")

    # Return the dictionaries for use
    print("\nDictionaries created:")
    print(f"hard_constraints: {type(hard_constraints)} with {len(hard_constraints)} query dictionaries")
    print(f"soft_constraints: {type(soft_constraints)} with {len(soft_constraints)} query dictionaries")