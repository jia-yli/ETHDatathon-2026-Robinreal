from __future__ import annotations

from pathlib import Path
from typing import Any

from app.core.hard_filters import HardFilterParams, search_listings
from app.models.schemas import HardFilters, ListingsResponse
from app.participant.hard_fact_extraction import extract_hard_facts
from app.participant.ranking import rank_listings
from app.participant.soft_fact_extraction import extract_soft_facts
from app.participant.soft_filtering import filter_soft_facts
from app.participant.process_constraints import process_constraints, filter_hard_facts_via_exec
from app.query_parsing.parser import QueryParser

def filter_hard_facts(db_path: Path, hard_facts: HardFilters) -> list[dict[str, Any]]:
    return search_listings(db_path, to_hard_filter_params(hard_facts))


def query_from_text(
    *,
    db_path: Path,
    query: str,
    limit: int,
    offset: int,
) -> ListingsResponse:
    
    parser = QueryParser()
    parsed = parser.parse(query)
    query_constraints = [c.model_dump() for c in parsed.constraints]
    query_hard_constraints, query_soft_constraints = process_constraints(query_constraints, query)

    hard_facts = extract_hard_facts(query)
    hard_facts.limit = 60000 # limit is applied after filter_hard_facts_via_exec
    hard_facts.offset = 0 # offset is applied after filter_hard_facts_via_exec
    soft_facts = extract_soft_facts(query)
    candidates = filter_hard_facts(db_path, hard_facts)
    candidates = filter_hard_facts_via_exec(candidates, query_hard_constraints)
    candidates = [ candidates[i] for i in range(offset, min(offset + limit, len(candidates))) ]
    candidates = filter_soft_facts(candidates, query_soft_constraints)
    return ListingsResponse(
        listings=rank_listings(candidates, query_soft_constraints),
        meta={},
    )


def query_from_filters(
    *,
    db_path: Path,
    hard_facts: HardFilters | None,
) -> ListingsResponse:
    structured_hard_facts = hard_facts or HardFilters()
    soft_facts = extract_soft_facts("")
    candidates = filter_hard_facts(db_path, structured_hard_facts)
    candidates = filter_soft_facts(candidates, soft_facts)
    return ListingsResponse(
        listings=rank_listings(candidates, soft_facts),
        meta={},
    )


def to_hard_filter_params(hard_facts: HardFilters) -> HardFilterParams:
    return HardFilterParams(
        city=hard_facts.city,
        postal_code=hard_facts.postal_code,
        canton=hard_facts.canton,
        min_price=hard_facts.min_price,
        max_price=hard_facts.max_price,
        min_rooms=hard_facts.min_rooms,
        max_rooms=hard_facts.max_rooms,
        latitude=hard_facts.latitude,
        longitude=hard_facts.longitude,
        radius_km=hard_facts.radius_km,
        features=hard_facts.features,
        offer_type=hard_facts.offer_type,
        object_category=hard_facts.object_category,
        limit=hard_facts.limit,
        offset=hard_facts.offset,
        sort_by=hard_facts.sort_by,
    )
