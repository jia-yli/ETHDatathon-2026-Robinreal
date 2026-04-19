"""
Listing classification rules: residential vs. non-residential detection.

All constants and helper functions for identifying non-residential listings
and detecting whether a free-text query is looking for a place to live.
"""
from __future__ import annotations

from typing import Any

# Object categories that are definitively non-residential and should never appear
# in apartment search results regardless of query.
NON_RESIDENTIAL_CATEGORIES: frozenset[str] = frozenset({
    "Tiefgarage", "Garage", "Einzelgarage", "Parkplatz", "Einstellplatz",
    "Büro", "Büro/Gewerbe", "Gewerbe", "Gewerbeobjekt", "Lager", "Werkstatt",
    "Laden", "Gastgewerbe",
})

# Keywords in title/description that identify a listing as non-residential
# when object_category is null. Checked case-insensitively.
# NOTE: "bureau" (singular) is intentionally excluded — it means "desk" in everyday
# French apartment listings ("chambre avec bureau") and causes false positives.
NON_RESIDENTIAL_KEYWORDS: tuple[str, ...] = (
    "place de parc", "places de parc", "parkplatz", "tiefgarage",
    "parking souterrain", "borne de recharge",
    "bureaux", "locaux commerciaux", "surface commerciale",
    "surface de bureau", "local commercial",
    "salon de coiffure", "restaurant", "commerce", "enseigne",
    "entrepôt", "lager", "werkstatt",
    # Storage / depot
    "dépôt", "depot", "stockage", "espace de stockage",
    "garage / box", "garage/box",
)

# English terms the LLM may use in object_type/object_category expressions when
# the user is explicitly looking for something non-residential.
NON_RESIDENTIAL_TERMS: frozenset[str] = frozenset({
    "office", "garage", "parking", "storage", "warehouse",
    "commercial", "shop", "restaurant", "industrial", "retail",
})

# Query-text substrings that signal the user wants a place to *live in*.
# Checked case-insensitively against the raw query.
RESIDENTIAL_QUERY_TERMS: tuple[str, ...] = (
    # English — property types and lifestyle intent (NOT "rent" — too generic)
    "apartment", "flat", "studio", "room", "bedroom", "live",
    # French — property types and lifestyle intent (NOT "louer" — too generic)
    "appartement", "chambre", "pièce", "habiter", "logement",
    # German — property types and lifestyle intent (NOT "mieten" — too generic)
    "wohnung", "zimmer", "schlafzimmer", "wohnen",
    # Swiss room-count notation (e.g. "2.5-Zimmer", "3.5 pièces")
    "1.5", "2.5", "3.5", "4.5", "5.5",
)

# Below this price (CHF/month) a listing is almost certainly not a habitable
# residential rental in Switzerland (parking, commercial, data artefact, etc.).
RESIDENTIAL_PRICE_MIN: float = 500.0


def is_residential_query(query: str) -> bool:
    """Return True if the query is clearly looking for a place to live."""
    q = query.lower()
    return any(term in q for term in RESIDENTIAL_QUERY_TERMS)


def _is_non_residential_query(query: str) -> bool:
    """Return True only if the query explicitly targets non-residential listings."""
    q = query.lower()
    return any(term in q for term in NON_RESIDENTIAL_TERMS)


def is_non_residential_by_text(candidate: dict[str, Any]) -> bool:
    """Fallback: detect non-residential listings via title/description keywords."""
    if candidate.get("object_category") is not None:
        # Category is populated — rely on the category check instead.
        return False
    text = " ".join(filter(None, [
        candidate.get("title", ""),
        candidate.get("description", ""),
    ])).lower()
    return any(kw in text for kw in NON_RESIDENTIAL_KEYWORDS)


def filter_non_residential(
    candidates: list[dict[str, Any]],
    hard_constraints: dict,
    soft_constraints: dict,
    query: str = "",
) -> list[dict[str, Any]]:
    """
    Drop non-residential listings unless the query explicitly asks for them.
    Skips filtering when any constraint on object_type or object_category
    references a non-residential category or term.

    For residential queries an additional price floor (RESIDENTIAL_PRICE_MIN)
    is applied to catch non-residential listings that have null categories and
    no detectable keywords (e.g. bare parking spots).
    """
    def _keep_non_residential() -> list[dict[str, Any]]:
        """Return only non-residential listings, falling back to all if none found.

        For null-category listings we only inspect the *title* (not the full
        description) to avoid false positives from apartment descriptions that
        mention nearby amenities such as "proche des commerces/restaurants".
        """
        def _is_non_res(c: dict[str, Any]) -> bool:
            if c.get("object_category") in NON_RESIDENTIAL_CATEGORIES:
                return True
            if c.get("object_category") is not None:
                return False
            # Null-category: title-only keyword scan to stay precise.
            title = (c.get("title") or "").lower()
            return any(kw in title for kw in NON_RESIDENTIAL_KEYWORDS)

        non_res = [c for c in candidates if _is_non_res(c)]
        return non_res if non_res else candidates

    all_constraints = (
        hard_constraints.get("constraint_list", [])
        + soft_constraints.get("constraint_list", [])
    )

    # Collect any requested object_category values from constraints so we can
    # narrow the non-residential pool to exactly what was asked for.
    import re as _re
    _requested_categories: set[str] = set()
    for c in all_constraints:
        expr = c.get("expression", "")
        _col_m = _re.search(r'\bthis\.([a-zA-Z_]+)\b', expr)
        col = _col_m.group(1) if _col_m else c.get("key", "")
        if col in ("object_type", "object_category"):
            _requested_categories.update(_re.findall(r"'([^']+)'", expr))

    for c in all_constraints:
        expr = c.get("expression", "")
        _col_m = _re.search(r'\bthis\.([a-zA-Z_]+)\b', expr)
        col = _col_m.group(1) if _col_m else c.get("key", "")
        if col in ("object_type", "object_category"):
            expr_lower = expr.lower()
            if any(cat.lower() in expr_lower for cat in NON_RESIDENTIAL_CATEGORIES):
                non_res = _keep_non_residential()
                # If the LLM specified particular categories, narrow to those.
                if _requested_categories:
                    narrowed = [l for l in non_res if l.get("object_category") in _requested_categories]
                    return narrowed if narrowed else non_res
                return non_res
            if any(term in expr_lower for term in NON_RESIDENTIAL_TERMS):
                return _keep_non_residential()

    # If the raw query text explicitly asks for non-residential listings
    # (e.g. "parking", "garage", "office"), KEEP only non-residential listings
    # so the ranking pool isn't polluted with apartments.
    # BUT: residential signals take priority — "flat with parking" or
    # "apartment near a restaurant" contains non-residential terms only as
    # amenity/context words, not as the target property type.
    if _is_non_residential_query(query) and not is_residential_query(query):
        return _keep_non_residential()

    result = []
    for c in candidates:
        # Drop by explicit category
        if c.get("object_category") in NON_RESIDENTIAL_CATEGORIES:
            continue
        # Drop by keyword scan (null-category listings)
        if is_non_residential_by_text(c):
            continue
        # Drop listings with suspiciously low prices — almost always parking
        # spots or commercial spaces with null / missing category.
        price = c.get("price") or 0
        if 0 < price < RESIDENTIAL_PRICE_MIN:
            continue
        result.append(c)
    return result
