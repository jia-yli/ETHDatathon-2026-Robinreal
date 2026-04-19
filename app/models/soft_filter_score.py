from __future__ import annotations

from typing import Any

import numpy as np

from app.participant.process_constraints import _evaluate_constraint
from app.models.utils import get_cosine_similarity, get_text_embedding

def get_soft_filter_scores(candidates: list[dict[str, Any]], soft_facts: dict[str, Any]) -> list[float]:
    scores = []
    for candidate in candidates:
        total_score = 0.0
        for constraint in soft_facts.get("constraint_list", []):
            expression = constraint.get("expression")
            clarity = constraint.get("clarity", "clear")
            if not expression or clarity == "vague":
                continue
            try:
                satisfied = _evaluate_constraint(candidate, constraint)
                total_score += 1.0 if satisfied else 0.0
            except Exception:
                pass
        scores.append(total_score)
    return scores


def get_vague_soft_filter_scores(
    candidates: list[dict[str, Any]],
    vague_soft_facts: dict[str, Any],
) -> list[float]:
    """Score candidates against vague (no-expression) soft constraints via embedding similarity.

    For each vague constraint the source_phrase (e.g. "bright", "quiet", "modern kitchen")
    is embedded and compared against each candidate's title + description text.  The
    per-candidate score is the average cosine similarity across all vague phrases.
    Returns a list of zeros when there are no vague constraints.
    """
    phrases = [
        c.get("source_phrase", "")
        for c in vague_soft_facts.get("constraint_list", [])
        if c.get("source_phrase")
    ]
    if not phrases or not candidates:
        return [0.0] * len(candidates)

    # Embed all vague phrases as one batch
    phrase_embeddings = get_text_embedding(phrases)  # list[np.ndarray] or np.ndarray
    if isinstance(phrase_embeddings, np.ndarray) and phrase_embeddings.ndim == 1:
        phrase_embeddings = [phrase_embeddings]

    # Embed candidate texts
    candidate_texts = [
        "title: " + (c.get("title") or "") + "; description: " + (c.get("description") or "")
        for c in candidates
    ]
    candidate_embeddings = get_text_embedding(candidate_texts)
    if isinstance(candidate_embeddings, np.ndarray) and candidate_embeddings.ndim == 1:
        candidate_embeddings = [candidate_embeddings]

    scores: list[float] = []
    for cand_emb in candidate_embeddings:
        sims = [
            get_cosine_similarity(np.array(phrase_emb), np.array(cand_emb))
            for phrase_emb in phrase_embeddings
        ]
        scores.append(float(np.mean(sims)))
    return scores
