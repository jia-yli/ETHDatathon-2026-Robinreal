from __future__ import annotations

import json
from typing import Any

from app.models.schemas import ListingData, RankedListingResult
from app.models.similarity import get_image_similarity_scores, get_similarity_scores
from app.models.soft_filter_score import get_soft_filter_scores

def rank_listings(
    candidates: list[dict[str, Any]],
    soft_facts: dict[str, Any],
) -> list[RankedListingResult]:
    
    # get similarity scores
    sim_scores = get_similarity_scores(candidates, soft_facts)
    
    # get soft filter scores
    soft_filter_scores = get_soft_filter_scores(candidates, soft_facts)

    # get image similarity scores
    # image_scores = get_image_similarity_scores(candidates, soft_facts)
    image_scores = [ 0.0 for _ in candidates ]

    # get overall weighted scores
    scores = [] 
    for i in range(len(candidates)):
        overall_score = 0.6 * sim_scores[i] + 0.2 * image_scores[i] + 0.2 * soft_filter_scores[i]
        scores.append(overall_score)

    candidate_score_pairs = [ (candidate, score) for candidate, score in sorted(
        zip(candidates, scores),
        key=lambda x: x[1],
        reverse=True,
    )]
    
    return [
        RankedListingResult(
            listing_id=str(candidate["listing_id"]),
            score=score,
            reason="Matched hard filters; soft ranking stub.",
            listing=_to_listing_data(candidate),
        )
        for candidate, score in candidate_score_pairs
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
