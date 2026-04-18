from typing import Any, Dict, List

from app.participant.process_constraints import _evaluate_constraint

def get_soft_filter_scores(candidates: list[dict[str, Any]], soft_facts: dict[str, Any]) -> list[float]:
    scores = []
    for candidate in candidates:
        total_score = 0.0
        for constraint in soft_facts.get("constraint_list", []):
            key = constraint.get("key")
            expression = constraint.get("expression")
            if key is None or expression is None:
                continue
            try:
                satisfied = _evaluate_constraint(candidate, key, expression)
                total_score += 1.0 if satisfied else 0.0
            except Exception as e:
                # print(f"Error evaluating soft constraint for candidate {candidate.get('id', 'N/A')}: {e}")
                pass
        scores.append(total_score)
    return scores
