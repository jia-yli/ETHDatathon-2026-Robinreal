"""
Pydantic schemas for parsed user query output.

The output is a flat list of Constraint objects — one per house attribute.
Each constraint carries a hard/soft classification, a clear/vague clarity tag,
and (for clear constraints) a boolean expression in this.column_name syntax
that the pipeline evaluates row-by-row against the property dataset.
"""

from __future__ import annotations

from typing import List, Literal, Optional

from pydantic import BaseModel, Field


class Constraint(BaseModel):
    """A single extracted constraint corresponding to exactly one house attribute."""

    source_phrase: str
    """The exact words or phrase from the query that express this constraint."""

    constraint_type: Literal["hard", "soft"]
    """
    'hard': the user states the constraint without ambiguity — a firm requirement.
    'soft': the user expresses a preference, wish, or uncertainty — a nice-to-have.
    """

    clarity: Literal["clear", "vague"]
    """
    'clear': the constraint can be evaluated against a known column using an available
             tool/expression — expression field must be present.
    'vague': the constraint cannot be resolved to a column+expression with the current
             feature set and tools (e.g. subjective qualities like 'bright', 'cheap',
             proximity to a landmark not in the dataset) — expression field is absent.
    """

    expression: Optional[str] = None
    """
    Executable expression operating on a property row ('this').
    Present only when clarity == 'clear'.  Column values are accessed via
    this.column_name.  Multi-column functions are also supported.

    Examples:
      boolean            → "this.prop_balcony == true"
      numeric bound      → "this.price <= 2500"
      numeric range      → "2000 <= this.price <= 3000"
      exact numeric      → "this.number_of_rooms == 3.5"
      set membership     → "this.number_of_rooms in [2, 3]"
      exact string       → "this.object_city == 'Zurich'"
      string set         → "this.object_zip in [8001, 8002]"
      date bound         → "this.available_from >= '2026-09-01'"
      predefined dist    → "this.distance_shop <= 500"  (metres)
      landmark distance  → "distance(this.geo_lat, this.geo_lng, 47.3769, 8.5476) <= 5"  (km)
    """


class ParsedQuery(BaseModel):
    """Top-level result returned by the QueryParser."""

    original_query: str
    constraints: List[Constraint] = Field(default_factory=list)
