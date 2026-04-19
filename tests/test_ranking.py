from pathlib import Path
from typing import Any
import os
import json
from concurrent.futures import ThreadPoolExecutor

from app.models.rules import filter_non_residential
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
        title_text = (listing.get("title") or "N/A").replace("|", "\\|")
        original_url = listing.get("original_listing_url") or "#"
        title = f"[{title_text}]({original_url})"
        city = listing.get("city") or "N/A"
        price = listing.get("price_chf") if listing.get("price_chf") is not None else "N/A"
        rooms = listing.get("rooms") if listing.get("rooms") is not None else "N/A"
        area = listing.get("living_area_sqm") if listing.get("living_area_sqm") is not None else "N/A"
        available_from = listing.get("available_from") or "N/A"
        score = item.get("score") if item.get("score") is not None else "N/A"
        reason = item.get("reason") or "N/A"
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

def test_with_query() -> None:
    repo_root = Path(__file__).resolve().parents[1]

    # query = "Ich suche etwas Kleineres in Lausanne, möglichst in der Nähe von EPFL, gern möbliert, unter 2100 CHF, mit guter Anbindung, und am besten in einer Ecke, die sich sicher, entspannt und nicht komplett anonym anfühlt."

    query = "3-room bright apartment in Zurich under 2800 CHF with balcony, close to public transport"

    # query = "Bright family-friendly flat in Winterthur, not too expensive, ideally with parking"

    # query = "Modern apartment in Basel, cheap but central, quiet with nice views"

    # query = "Looking to buy a 5-room house in canton Zurich with garage"

    # query = "Studio apartment for rent in Geneva, max CHF 1500 per month"

    # query = "Looking for a affordable student accomondation, max half an hour door to door to ETH Zurich by public transport, i like modern kitchens."

    # query = "Modern studio in Geneva for June move-in, quiet area, nice views if possible"

    # query = "Around 3-room apartment in Zurich, max CHF 2500"

    hard_facts = extract_hard_facts(query)
    hard_facts.limit = 60000 # limit is applied after filter_hard_facts_via_exec
    hard_facts.offset = 0 # offset is applied after filter_hard_facts_via_exec
    soft_facts = extract_soft_facts(query)

    # Overlap the LLM parse call with the DB query — they are independent.
    parser = QueryParser()
    with ThreadPoolExecutor(max_workers=2) as executor:
        parse_future = executor.submit(parser.parse, query)
        filter_future = executor.submit(filter_hard_facts, repo_root / "data" / "listings.db", hard_facts)
        parsed = parse_future.result()
        candidates = filter_future.result()

    query_constraints = [c.model_dump() for c in parsed.constraints]
    query_hard_constraints, query_soft_constraints = process_constraints(query_constraints, query)

    print(f"\n=== PARSED QUERY ===")
    print(f"Query: {query}")
    print(f"Hard constraints: {len(query_hard_constraints['constraint_list'])}")
    print(f"Soft constraints: {len(query_soft_constraints['constraint_list'])}")

    limit = 25
    offset = 0

    candidates = filter_hard_facts_via_exec(candidates, query_hard_constraints, query)
    candidates = filter_non_residential(candidates, query_hard_constraints, query_soft_constraints, query)
    candidates = candidates[offset: min(offset + limit, len(candidates))]
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


def test_non_residential_query() -> None:
    """
    Verify that explicitly non-residential queries (garage, parking, office, storage)
    are NOT filtered out by filter_non_residential, and that the returned results
    actually contain non-residential listings.

    Three representative queries are tested:
      1. Parking spot in Lausanne
      2. Office / commercial space in Zurich
      3. Storage unit / depot
    """
    repo_root = Path(__file__).resolve().parents[1]
    db_path = repo_root / "data" / "listings.db"

    test_cases = [
        (
            "Je cherche une place de parking ou un garage à louer à Lausanne, "
            "idéalement couvert, disponible de suite.",
            "parking/garage Lausanne",
        ),
        (
            "Looking for a small office or commercial space to rent in central Lausanne, "
            "around 50-100 sqm, good public transport access.",
            "office Lausanne",
        ),
        (
            "I need a storage unit or depot (dépôt) to rent in Lausanne, "
            "at least 10 sqm, affordable price.",
            "storage/depot Lausanne",
        ),
    ]

    parser = QueryParser()
    for query, label in test_cases:
        hard_facts = extract_hard_facts(query)
        hard_facts.limit = 60000
        hard_facts.offset = 0

        with ThreadPoolExecutor(max_workers=2) as executor:
            parse_future = executor.submit(parser.parse, query)
            filter_future = executor.submit(filter_hard_facts, db_path, hard_facts)
            parsed = parse_future.result()
            candidates = filter_future.result()

        query_constraints = [c.model_dump() for c in parsed.constraints]
        query_hard_constraints, query_soft_constraints = process_constraints(query_constraints, query)

        before_filter = len(candidates)
        candidates = filter_hard_facts_via_exec(candidates, query_hard_constraints, query)
        candidates = filter_non_residential(candidates, query_hard_constraints, query_soft_constraints, query)
        after_filter = len(candidates)

        print(f"\n--- [{label}] ---")
        print(f"Query: {query}")
        print(f"Candidates before filter: {before_filter}, after: {after_filter}")

        candidates_slice = candidates[:25]
        soft_facts = extract_soft_facts(query)
        soft_facts_dict = query_soft_constraints
        candidates_slice = filter_soft_facts(candidates_slice, soft_facts_dict)
        ranked = rank_listings(candidates_slice, soft_facts_dict)

        print(f"Top results ({len(ranked)} ranked):")
        for i, r in enumerate(ranked[:5], 1):
            listing = r.listing
            print(
                f"  {i}. [{listing.object_category or 'null category'}] "
                f"{listing.title!r} — CHF {listing.price_chf} — {listing.city}"
            )

        # The filter must not wipe out everything when the query targets non-residential.
        assert after_filter > 0, (
            f"[{label}] filter_non_residential removed ALL candidates for an explicit "
            f"non-residential query — the bypass logic is broken."
        )
