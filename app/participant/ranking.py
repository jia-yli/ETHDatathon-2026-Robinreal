from __future__ import annotations

import json
from typing import Any

from app.models.llm_pairwise import get_pairwise_scores
from app.models.schemas import ListingData, RankedListingResult
from app.models.similarity import get_image_similarity_scores, get_similarity_scores
from app.models.soft_filter_score import get_soft_filter_scores
from app.models.apartment_value import get_value_scores

# ── Stage 1 weights (must sum to 1) ───────────────────────────────────────
# sim + soft together capture query relevance; value captures general apartment
# quality / price-efficiency independent of the query.
_W_SIM = 0.45
_W_SOFT = 0.2
_W_VALUE = 0.35

# ── Stage 2 combination weights (must sum to 1) ────────────────────────────
# Pairwise LLM is the most authoritative signal; stage-1 acts as a prior;
# image similarity adds a visual quality bonus.
_W_STAGE1 = 0.3
_W_PAIRWISE = 0.5
_W_IMAGE = 0.2

_TOP_K = 10


def _normalize(values: list[float]) -> list[float]:
    lo, hi = min(values), max(values)
    if hi == lo:
        return [1.0] * len(values)
    return [(v - lo) / (hi - lo) for v in values]


def _stage1_reason(
    sim: float,
    soft: float,
    value: float,
    all_sims: list[float],
    all_softs: list[float],
    all_values: list[float],
) -> str:
    sim_rank   = sorted(all_sims,   reverse=True).index(sim)
    soft_rank  = sorted(all_softs,  reverse=True).index(soft)
    value_rank = sorted(all_values, reverse=True).index(value)
    best_rank  = min(sim_rank, soft_rank, value_rank)
    if best_rank == sim_rank:
        return "Strong semantic match to query"
    elif best_rank == soft_rank:
        return "Strong preference alignment"
    else:
        return "High-quality, good-value apartment"


def rank_listings(
    candidates: list[dict[str, Any]],
    soft_facts: dict[str, Any],
) -> list[RankedListingResult]:
    if not candidates:
        return []

    # ── Stage 1: rough ranking over all candidates ──
    # Each score lives on a different scale:
    #   sim_scores        — cosine similarity ~[0.3, 0.8], narrow range
    #   soft_filter_scores — integer count [0, N], N = #soft constraints (query-dependent)
    #   value_scores      — [0, 1] by construction
    # Normalise each to [0, 1] within the candidate set so the weights are
    # stable and query-independent, then combine.
    sim_scores         = get_similarity_scores(candidates, soft_facts)
    soft_filter_scores = get_soft_filter_scores(candidates, soft_facts)
    value_scores       = get_value_scores(candidates)  # O(1) table-lookup per candidate

    norm_sim   = _normalize(list(sim_scores))
    norm_soft  = _normalize(list(soft_filter_scores))
    norm_value = _normalize(list(value_scores))

    stage1_scores = [
        _W_SIM * norm_sim[i] + _W_SOFT * norm_soft[i] + _W_VALUE * norm_value[i]
        for i in range(len(candidates))
    ]
    stage1_reasons = [
        _stage1_reason(
            norm_sim[i], norm_soft[i], norm_value[i],
            norm_sim, norm_soft, norm_value,
        )
        for i in range(len(candidates))
    ]

    cand_tuples: list[tuple[dict[str, Any], float, str]] = sorted(
        zip(candidates, stage1_scores, stage1_reasons),
        key=lambda x: x[1],
        reverse=True,
    )

    # ── Stage 2: fine-grained re-ranking of top-k ──
    topk = min(_TOP_K, len(cand_tuples))
    topk_candidates, topk_stage1_scores, topk_stage1_reasons = (
        [t[0]        for t in cand_tuples[:topk]],
        [float(t[1]) for t in cand_tuples[:topk]],
        [str(t[2])   for t in cand_tuples[:topk]],
    )

    # soft_facts is identical for every candidate — reuse directly
    topk_soft_facts = soft_facts

    # Image similarity (visual coherence with query)
    image_scores = get_image_similarity_scores(topk_candidates, topk_soft_facts)

    # LLM pairwise tournament
    query = soft_facts.get("original_query", "")
    pairwise_scores, pairwise_reasons = get_pairwise_scores(query, topk_candidates)

    # Normalize each component independently to [0, 1]
    norm_stage1   = _normalize(topk_stage1_scores)
    norm_pairwise = _normalize(pairwise_scores)
    norm_image    = _normalize(image_scores)

    # Combined final score
    final_scores = [
        _W_STAGE1 * norm_stage1[i]
        + _W_PAIRWISE * norm_pairwise[i]
        + _W_IMAGE * norm_image[i]
        for i in range(topk)
    ]

    # Use LLM reason when the candidate won a comparison; fall back to stage-1 reason
    final_reasons = [
        pairwise_reasons[i] if pairwise_reasons[i] else topk_stage1_reasons[i]
        for i in range(topk)
    ]

    # Sort top-k by final score, then append the remaining candidates (stage-1 order).
    # Rest candidates are scaled into [0, floor) so no rest candidate can outscore a
    # top-k candidate regardless of how the two score ranges compare.
    all_ranked: list[tuple[dict[str, Any], float, str]] = sorted(
        [(topk_candidates[i], final_scores[i], final_reasons[i]) for i in range(topk)],
        key=lambda x: x[1],
        reverse=True,
    )
    rest_tuples = cand_tuples[topk:]
    if rest_tuples:
        floor = min(final_scores) if final_scores else 0.0
        rest_s1 = [float(t[1]) for t in rest_tuples]
        lo, hi = min(rest_s1), max(rest_s1)
        _eps = 1e-6
        if hi > lo:
            rest_scaled = [(s - lo) / (hi - lo) * max(0.0, floor - _eps) for s in rest_s1]
        else:
            rest_scaled = [max(0.0, floor - _eps)] * len(rest_tuples)
        for idx, (c, _s, r) in enumerate(rest_tuples):
            all_ranked.append((c, rest_scaled[idx], str(r)))  # type: ignore[arg-type]

    return [
        RankedListingResult(
            listing_id=str(candidate["listing_id"]),
            score=round(float(score), 4),
            reason=str(reason),
            listing=_to_listing_data(candidate),
        )
        for candidate, score, reason in all_ranked
    ]


def _to_listing_data(candidate: dict[str, Any]) -> ListingData:
    return ListingData(
        id=str(candidate["listing_id"]),
        title=candidate["title"],
        description=candidate.get("description"),
        street=candidate.get("street"),
        city=candidate.get("city"),
        postal_code=candidate.get("postal_code"),
        canton=candidate.get("canton"),
        latitude=candidate.get("latitude"),
        longitude=candidate.get("longitude"),
        price_chf=candidate.get("price"),
        rooms=candidate.get("rooms"),
        living_area_sqm=_coerce_int(candidate.get("area")),
        available_from=candidate.get("available_from"),
        image_urls=_coerce_image_urls(candidate.get("image_urls")),
        hero_image_url=candidate.get("hero_image_url"),
        original_listing_url=candidate.get("original_url"),
        features=candidate.get("features") or [],
        offer_type=candidate.get("offer_type"),
        object_category=candidate.get("object_category"),
        object_type=candidate.get("object_type"),
    )


def _coerce_int(value: Any) -> int | None:
    if value is None:
        return None
    try:
        return int(round(float(value)))
    except (TypeError, ValueError):
        return None


def _coerce_image_urls(value: Any) -> list[str] | None:
    if value is None:
        return None
    if isinstance(value, list):
        return [str(item) for item in value]
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError:
            return [value]
        if isinstance(parsed, list):
            return [str(item) for item in parsed]
    return None
