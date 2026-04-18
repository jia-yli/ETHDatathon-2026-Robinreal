from pathlib import Path
from typing import Any
import os
import json

from fastapi.testclient import TestClient

from app.participant.hard_fact_extraction import extract_hard_facts
from app.participant.ranking import rank_listings
from app.participant.soft_fact_extraction import extract_soft_facts
from app.participant.soft_filtering import filter_soft_facts
from app.harness.bootstrap import bootstrap_database
from app.harness.search_service import filter_hard_facts
from app.participant.process_constraints import process_constraints, filter_hard_facts_via_exec
from app.query_parsing.parser import QueryParser

def build_database(tmp_path: Path) -> Path:
    repo_root = Path(__file__).resolve().parents[1]
    raw_data_dir = repo_root / "raw_data"
    db_path = tmp_path / "listings.db"
    bootstrap_database(db_path=db_path, raw_data_dir=raw_data_dir)
    return db_path

ROOT = Path(__file__).resolve().parents[1]
RESULT_DIR = ROOT / "tests" / "results"
APARTMENT_EXAMPLE_PATH = RESULT_DIR / "apartment_example.json"
RANK_INPUT_PATH = RESULT_DIR / "rank_input.jsonl"
OUTPUT_JSON_PATH = RESULT_DIR / "ranked_apartment_results.json"
OUTPUT_MD_PATH = RESULT_DIR / "ranked_apartments.md"

if not RESULT_DIR.exists():
    RESULT_DIR.mkdir(parents=True, exist_ok=True)

def _model_to_dict(model: Any) -> Any:
    if hasattr(model, "model_dump"):
        return model.model_dump()
    if hasattr(model, "dict"):
        return model.dict()
    return model


def _markdown_image_for(candidate: dict[str, Any]) -> str:
    url = candidate.get("hero_image_url")
    if not url and candidate.get("image_urls"):
        urls = candidate["image_urls"]
        if isinstance(urls, list) and urls:
            url = urls[0]
    return f"![Apartment]({url})" if url else "No image available"


def _render_markdown(results: list[dict[str, Any]]) -> str:
    header = (
        "# Ranked Apartment Listings\n\n"
        "| Image | Title | City | Price (CHF) | Rooms | Area (sqm) | Available From | Score | Reason |\n"
        "|-------|-------|------|-------------|-------|------------|----------------|-------|--------|\n"
    )
    rows: list[str] = []
    for item in results:
        listing = item.get("listing", {})
        image = _markdown_image_for(listing)
        title_text = listing.get("title", "N/A")
        original_url = listing.get("original_listing_url") or "#"
        title = f"[{title_text}]({original_url})"
        city = listing.get("city", "N/A")
        price = listing.get("price_chf", "N/A")
        rooms = listing.get("rooms", "N/A")
        area = listing.get("living_area_sqm", "N/A")
        available_from = listing.get("available_from", "N/A")
        score = item.get("score", "N/A")
        reason = item.get("reason", "N/A")
        rows.append(
            "| "
            + " | ".join(
                [
                    image,
                    title,
                    city,
                    str(price),
                    str(rooms),
                    str(area),
                    str(available_from),
                    str(score),
                    reason.replace("|", "\\|"),
                ]
            )
            + " |"
        )
    return header + "\n".join(rows) + "\n"

def test_with_query_and_soft_constraints() -> None:
    repo_root = Path(__file__).resolve().parents[1]

    query = "Ich suche etwas Kleineres in Lausanne, möglichst in der Nähe von EPFL, gern möbliert, unter 2100 CHF, mit guter Anbindung, und am besten in einer Ecke, die sich sicher, entspannt und nicht komplett anonym anfühlt."

    parser = QueryParser()
    parsed = parser.parse(query)
    query_constraints = [c.model_dump() for c in parsed.constraints]
    query_hard_constraints, query_soft_constraints = process_constraints(query_constraints, query)

    print(f"\n=== PARSED QUERY ===")
    print(f"Query: {query}")
    print(f"Hard constraints: {len(query_hard_constraints['constraint_list'])}")
    print(f"Soft constraints: {len(query_soft_constraints['constraint_list'])}")

    limit = 25
    offset = 0

    hard_facts = extract_hard_facts(query)
    hard_facts.limit = 60000 # limit is applied after filter_hard_facts_via_exec
    hard_facts.offset = 0 # offset is applied after filter_hard_facts_via_exec

    candidates = filter_hard_facts(repo_root / "data" / "listings.db", hard_facts)
    candidates = filter_hard_facts_via_exec(candidates, query_hard_constraints)
    candidates = [ candidates[i] for i in range(offset, min(offset + limit, len(candidates))) ]
    candidates = filter_soft_facts(candidates, query_soft_constraints)

    ranked_results = rank_listings(candidates, query_soft_constraints)
    # assert len(ranked_results) > 0, "Ranked results should not be empty"

    ranked_results_data = [_model_to_dict(result) for result in ranked_results]

    # Print the actual results
    print(f"\n=== RANKED RESULTS ({len(ranked_results)} listings) ===")
    for i, result in enumerate(ranked_results_data[:5], 1):  # Show first 5
        listing = result.get("listing", {})
        print(f"{i}. {listing.get('title', 'N/A')} - Score: {result.get('score', 'N/A')} - {listing.get('city', 'N/A')}")
    if len(ranked_results_data) > 5:
        print(f"... and {len(ranked_results_data) - 5} more listings")

    with OUTPUT_JSON_PATH.open("w", encoding="utf-8") as fh:
        json.dump(ranked_results_data, fh, ensure_ascii=False, indent=2)

    markdown = _render_markdown(ranked_results_data)
    OUTPUT_MD_PATH.write_text(markdown, encoding="utf-8")

    print(f"\nWrote ranked results JSON to: {OUTPUT_JSON_PATH}")
    print(f"Wrote ranked markdown to: {OUTPUT_MD_PATH}")
    print(f"Query: {query}")
    print(f"Hard constraints used: {len(query_hard_constraints['constraint_list'])}")
    print(f"Soft constraints used: {len(query_soft_constraints['constraint_list'])}")
