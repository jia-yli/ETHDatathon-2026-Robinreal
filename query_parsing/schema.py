"""
Pydantic schemas for parsed user query output.

Hard constraints map directly to filterable database columns.
Soft constraints are vague/subjective and passed downstream for semantic/embedding-based matching.
"""

from __future__ import annotations

from typing import List, Literal, Optional

from pydantic import BaseModel, Field


class HardConstraints(BaseModel):
    """Constraints that can be directly applied as structured filters on listing columns."""

    # Transaction type
    offer_type: Optional[Literal["RENT", "BUY"]] = None

    # Property category (German labels matching the dataset's object_category column)
    object_category: Optional[Literal["Wohnung", "Haus", "Parkplatz", "Gewerbeobjekt"]] = None

    # Room count (Swiss notation: 3.5-room = 3 rooms + kitchen/bath counted as 0.5)
    min_rooms: Optional[float] = None
    max_rooms: Optional[float] = None
    exact_rooms: Optional[float] = None  # set when user names a specific count

    # Price in CHF (monthly for RENT, total for BUY)
    min_price_chf: Optional[float] = None
    max_price_chf: Optional[float] = None

    # Floor area in m²
    min_area_sqm: Optional[float] = None
    max_area_sqm: Optional[float] = None

    # Location
    city: Optional[str] = None
    zip_code: Optional[str] = None
    canton: Optional[str] = None  # e.g. "Zurich", "ZH", "Aargau", "AG"

    # Amenities (True = required, False = explicitly unwanted, None = no preference)
    prop_balcony: Optional[bool] = None
    prop_elevator: Optional[bool] = None
    prop_parking: Optional[bool] = None
    prop_garage: Optional[bool] = None
    prop_fireplace: Optional[bool] = None
    prop_child_friendly: Optional[bool] = None
    animal_allowed: Optional[bool] = None

    # Building flags
    is_new_building: Optional[bool] = None

    # Availability date (ISO 8601, e.g. "2026-09-01")
    available_from: Optional[str] = None

    # Floor number range (0 = ground floor)
    floor_min: Optional[int] = None
    floor_max: Optional[int] = None


class SoftConstraints(BaseModel):
    """
    Vague, subjective, or unmeasurable preferences that cannot be mapped to column filters.
    These are forwarded to downstream layers (e.g. semantic search, image scoring).
    """

    # Short keyword/phrase list extracted from the query
    keywords: List[str] = Field(default_factory=list)

    # Free-text summary of all soft preferences
    raw_description: Optional[str] = None


class ParsedQuery(BaseModel):
    """Top-level result returned by the QueryParser."""

    original_query: str
    hard_constraints: HardConstraints
    soft_constraints: SoftConstraints
