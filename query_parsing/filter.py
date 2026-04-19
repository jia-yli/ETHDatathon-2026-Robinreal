"""
PropertyFilter — backend that executes LLM-produced expressions against a
property DataFrame row-by-row.

This is the reference implementation for how the pipeline consumes ParsedQuery
output.  It supports all expression tools defined in config/tools.json:

  compare_numeric   this.price <= 2500
  compare_string    this.object_city == 'Zurich'
  boolean_check     this.prop_balcony == true
  set_membership    this.number_of_rooms in [2, 3]
  date_compare      this.available_from >= '2026-09-01'
  distance_column   this.distance_shop <= 500
  distance()        distance(this.geo_lat, this.geo_lng, 47.3769, 8.5476) <= 2

Usage
-----
    from query_parsing.filter import PropertyFilter

    backend = PropertyFilter(df)

    # Filter by all clear constraints (hard + soft)
    matched_df, counts = backend.apply(parsed_query)

    # Filter by hard constraints only
    matched_df, counts = backend.apply(parsed_query, hard_only=True)

    # counts: {expression: n_matching_rows} — useful for diagnostics / scoring
"""

import math

import pandas as pd


# ---------------------------------------------------------------------------
# Haversine distance helper (implements the distance() tool)
# ---------------------------------------------------------------------------

def _haversine_km(lat1, lon1, lat2, lon2):
    """
    Straight-line (Haversine) distance in km between two WGS-84 coordinates.

    Used by the distance() expression tool:
        distance(this.geo_lat, this.geo_lng, target_lat, target_lon) <= km
    """
    R = 6371.0
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlam = math.radians(lon2 - lon1)
    a = (math.sin(dphi / 2) ** 2
         + math.cos(phi1) * math.cos(phi2) * math.sin(dlam / 2) ** 2)
    return 2 * R * math.asin(math.sqrt(a))


# ---------------------------------------------------------------------------
# Expression evaluation globals
# Maps names used in LLM-generated expressions to Python values / callables.
# ---------------------------------------------------------------------------

EXPR_GLOBALS = {
    "__builtins__": {},
    # Boolean literals (LLM uses lowercase JSON-style: true / false)
    "true":  True,
    "false": False,
    # distance tool: distance(this.geo_lat, this.geo_lng, lat, lon) -> km
    "distance": _haversine_km,
}


# ---------------------------------------------------------------------------
# PropertyFilter
# ---------------------------------------------------------------------------

class PropertyFilter:
    """
    Filters a property DataFrame by evaluating ParsedQuery expressions.

    Each clear constraint's expression is evaluated row-by-row against the
    DataFrame.  Results are ANDed together (all constraints must be satisfied).

    Parameters
    ----------
    df : pd.DataFrame
        Property dataset.  Boolean columns must be Python bool (not string).
    """

    def __init__(self, df):
        self._df = df

    # ------------------------------------------------------------------
    # Core evaluation primitives
    # ------------------------------------------------------------------

    def eval_row(self, expr, row):
        """Evaluate *expr* against a single pandas Series row. Returns bool."""
        return bool(eval(expr, EXPR_GLOBALS, {"this": row}))

    def mask(self, expr):
        """Return a boolean pd.Series for *expr* applied to every row."""
        return self._df.apply(lambda row: self.eval_row(expr, row), axis=1)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def apply(self, parsed_query, hard_only=False):
        """
        Apply all clear expressions from *parsed_query* to the DataFrame.

        Parameters
        ----------
        parsed_query : ParsedQuery
        hard_only    : bool
            When True, only hard constraints are applied; soft ones are skipped.

        Returns
        -------
        pd.DataFrame
            Rows satisfying every applied constraint (AND semantics).
        dict
            ``{expression: n_matching_rows}`` counts per expression.
            Useful for ranking or debugging when no rows match.
        """
        combined = pd.Series([True] * len(self._df), index=self._df.index)
        counts = {}
        for c in parsed_query.constraints:
            if c.clarity != "clear" or not c.expression:
                continue
            if hard_only and c.constraint_type != "hard":
                continue
            m = self.mask(c.expression)
            counts[c.expression] = int(m.sum())
            combined = combined & m
        return self._df[combined].copy(), counts
