"""
Pydantic schemas for parsed user query output.

The output is a flat list of Constraint objects — one per house attribute.
Each constraint carries its own hard/soft classification, a standardised value
expression, and a flag indicating whether the key is a predefined feature.

Predefined features are listed in feature.csv / feature.md.  All output is in
English with standardised names regardless of input language.
"""

from __future__ import annotations

from typing import List, Literal

from pydantic import BaseModel, Field


class Constraint(BaseModel):
    """A single extracted constraint corresponding to exactly one house attribute."""

    source_phrase: str
    """The exact words or phrase from the query that express this constraint."""

    key: str
    """
    Feature key.  If the constraint maps to a predefined feature (see feature.csv),
    use that feature's name exactly (snake_case).  Otherwise use an informative
    snake_case key that clearly describes the attribute.
    """

    predefined: bool
    """True when *key* is one of the predefined features in feature.csv / feature.md."""

    constraint_type: Literal["hard", "soft"]
    """
    'hard': the user states the constraint without ambiguity — a firm requirement.
    'soft': the user expresses a preference, wish, or uncertainty — a nice-to-have.
    """

    expression: str
    """
    Standardised mathematical / logical expression using 'this' as the variable.

    Examples by data type:
      boolean present     → "this == true"
      boolean absent      → "this == false"
      exact numeric       → "this == 3.5"
      numeric upper bound → "this <= 2500"
      numeric lower bound → "this >= 80"
      numeric range       → "2000 <= this <= 3000"
      exact string        → "this == 'Zurich'"  |  "this == 'rent'"
      date lower bound    → "this >= '2026-09-01'"
      predefined distance (meters) → "this <= 500"
      non-predefined proximity    → "isclose(this, 5min by foot)"
                                  | "this <= 25min public transport"
    """


class ParsedQuery(BaseModel):
    """Top-level result returned by the QueryParser."""

    original_query: str
    constraints: List[Constraint] = Field(default_factory=list)
