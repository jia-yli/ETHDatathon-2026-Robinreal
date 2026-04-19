"""
QueryParserTool: query parser that uses the tool-based compiler prompt (prompts_tool).

Produces Constraint objects with clarity field and this.column_name expressions.
"""

import json
import os
from pathlib import Path
from typing import Optional

from openai import OpenAI

from .prompts import SYSTEM_PROMPT, build_user_message
from .schema import Constraint, ParsedQuery

_DEFAULT_KEY_FILE = Path(__file__).parent.parent / "tests" / "deepseekapi.txt"
_DEEPSEEK_BASE_URL = "https://api.deepseek.com"
_DEFAULT_MODEL = "deepseek-chat"


def _resolve_api_key(api_key):
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
        "DeepSeek API key not found. Provide via api_key argument, "
        "DEEPSEEK_API_KEY env var, or tests/deepseekapi.txt."
    )


class QueryParser:
    """
    Parses a natural-language real estate query into structured constraints
    using the tool-based compiler prompt.

    Each returned Constraint carries:
      - constraint_type: 'hard' | 'soft'
      - clarity:         'clear' | 'vague'
      - expression:      executable this.column_name expression (clear only)

    Usage
    -----
    >>> parser = QueryParser()
    >>> result = parser.parse("3.5-room apartment in Zurich under CHF 2800")
    >>> result.constraints[0].expression
    "this.number_of_rooms == 3.5"
    """

    def __init__(self, api_key=None, model=_DEFAULT_MODEL):
        self._model = model
        self._client = OpenAI(
            api_key=_resolve_api_key(api_key),
            base_url=_DEEPSEEK_BASE_URL,
        )

    def parse(self, query):
        """
        Send *query* to the LLM and return a ParsedQuery.

        Parameters
        ----------
        query : str
            Raw natural-language user input.

        Returns
        -------
        ParsedQuery
            Validated Pydantic model with constraint list.
        """
        response = self._client.chat.completions.create(
            model=self._model,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user",   "content": build_user_message(query)},
            ],
            response_format={"type": "json_object"},
            temperature=0.0,
        )
        raw_json = response.choices[0].message.content
        data = json.loads(raw_json)
        constraints = [Constraint(**c) for c in data.get("constraints", [])]
        return ParsedQuery(original_query=query, constraints=constraints)
