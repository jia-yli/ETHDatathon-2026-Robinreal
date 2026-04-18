"""
Pydantic schemas for parsed user query output.

Hard constraints map directly to filterable database columns.
Column names and value types match the dataset exactly (see datasets/raw/raw_data/).

Dataset column reference used for filtering:
  number_of_rooms     → float  (e.g. 3.5)
  price               → float  (total price; for RENT this is monthly gross)
  rent_net            → float  (net monthly rent)
  rent_gross          → float  (gross monthly rent)
  area                → float  (m²)
  object_city         → str    (city name as stored)
  object_zip          → str    (postal code string)
  object_state        → str    (canton 2-letter code, upper or lower depending on source)
  prop_balcony        → "true"/"false"
  prop_elevator       → "true"/"false"
  prop_parking        → "true"/"false"
  prop_garage         → "true"/"false"
  prop_fireplace      → "true"/"false"
  prop_child_friendly → "true"/"false"
  animal_allowed      → "true"/"false"
  is_new_building     → "true"/"false"
  available_from      → ISO date string "YYYY-MM-DD"
  floor               → int

Soft constraints are vague/subjective and passed downstream for semantic/embedding-based matching.
"""

from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, Field


class HardConstraints(BaseModel):
    """
    Constraints that map directly to dataset column filters.
    Field names match dataset columns exactly where possible.
    """

    # --- maps to column: number_of_rooms (range filter) ---
    min_rooms: Optional[float] = None
    max_rooms: Optional[float] = None
    exact_rooms: Optional[float] = None  # when user names an exact count

    # --- maps to column: price / rent_gross (monthly CHF for RENT, total for SALE) ---
    min_price_chf: Optional[float] = None
    max_price_chf: Optional[float] = None

    # --- maps to column: area (m²) ---
    min_area_sqm: Optional[float] = None
    max_area_sqm: Optional[float] = None

    # --- maps to columns: object_city, object_zip, object_state ---
    object_city: Optional[str] = None   # preserve original spelling
    object_zip: Optional[str] = None    # postal code string
    object_state: Optional[str] = None  # 2-letter canton code, e.g. "ZH", "BE", "AG"

    # --- maps to boolean columns (dataset stores "true"/"false" strings) ---
    prop_balcony: Optional[bool] = None
    prop_elevator: Optional[bool] = None
    prop_parking: Optional[bool] = None
    prop_garage: Optional[bool] = None
    prop_fireplace: Optional[bool] = None
    prop_child_friendly: Optional[bool] = None
    animal_allowed: Optional[bool] = None

    # --- maps to column: is_new_building ---
    is_new_building: Optional[bool] = None

    # --- maps to column: available_from (ISO 8601) ---
    available_from: Optional[str] = None

    # --- maps to column: floor ---
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
