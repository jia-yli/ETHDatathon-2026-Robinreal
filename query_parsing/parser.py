"""
QueryParser: sends a user query to the DeepSeek LLM and returns a ParsedQuery.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Optional

from openai import OpenAI

from .prompts import SYSTEM_PROMPT, build_user_message
from .schema import HardConstraints, ParsedQuery, SoftConstraints

# Default location of the API key file (relative to this package)
_DEFAULT_KEY_FILE = Path(__file__).parent.parent / "tests" / "deepseekapi.txt"

_DEEPSEEK_BASE_URL = "https://api.deepseek.com"
_DEFAULT_MODEL = "deepseek-chat"


def _resolve_api_key(api_key: Optional[str]) -> str:
    """Return the API key from (in order): argument, env var, key file."""
    if api_key:
        return api_key
    env_key = os.environ.get("DEEPSEEK_API_KEY", "").strip()
    if env_key:
        return env_key
    if _DEFAULT_KEY_FILE.exists():
        key = _DEFAULT_KEY_FILE.read_text().strip()
        if key:
            return key
    raise ValueError(
        "DeepSeek API key not found. Provide it via the `api_key` argument, "
        "the DEEPSEEK_API_KEY environment variable, or tests/deepseekapi.txt."
    )


class QueryParser:
    """
    Parses a natural-language real estate query into structured hard and soft constraints.

    Usage
    -----
    >>> parser = QueryParser()
    >>> result = parser.parse("3.5-room apartment in Zurich under CHF 2800 with balcony")
    >>> result.hard_constraints.city
    'Zurich'
    >>> result.hard_constraints.max_price_chf
    2800.0
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = _DEFAULT_MODEL,
    ) -> None:
        self._model = model
        self._client = OpenAI(
            api_key=_resolve_api_key(api_key),
            base_url=_DEEPSEEK_BASE_URL,
        )

    def parse(self, query: str) -> ParsedQuery:
        """
        Send *query* to the LLM and return a :class:`ParsedQuery`.

        Parameters
        ----------
        query:
            Raw natural-language user input.

        Returns
        -------
        ParsedQuery
            Validated Pydantic model with hard and soft constraint fields.
        """
        response = self._client.chat.completions.create(
            model=self._model,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": build_user_message(query)},
            ],
            response_format={"type": "json_object"},
            temperature=0.0,
        )
        raw_json = response.choices[0].message.content
        data = json.loads(raw_json)

        hard = HardConstraints(**data.get("hard_constraints", {}))
        soft = SoftConstraints(**data.get("soft_constraints", {}))
        return ParsedQuery(
            original_query=query,
            hard_constraints=hard,
            soft_constraints=soft,
        )
