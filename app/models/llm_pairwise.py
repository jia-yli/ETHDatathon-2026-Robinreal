"""
LLM-based pairwise comparison for Stage 2 re-ranking.

Each pair (A, B) is sent to DeepSeek and the LLM declares a winner.
  winner A  → score_A += 1.0, score_B += 0.0
  tie       → score_A += 0.5, score_B += 0.5
  winner B  → score_A += 0.0, score_B += 1.0

After all C(n, 2) comparisons each candidate has a win-point total in [0, n-1].
"""

from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any

from openai import OpenAI

_DEEPSEEK_BASE_URL = "https://api.deepseek.com"
_DEFAULT_MODEL = "deepseek-chat"
_KEY_FILE = Path(__file__).parent.parent.parent / "tests" / "deepseekapi.txt"


def _get_client() -> OpenAI:
    api_key = os.environ.get("DEEPSEEK_API_KEY", "").strip()
    if not api_key and _KEY_FILE.exists():
        api_key = _KEY_FILE.read_text().strip()
    if not api_key:
        raise ValueError(
            "DeepSeek API key not found. Set DEEPSEEK_API_KEY or place key in tests/deepseekapi.txt."
        )
    return OpenAI(api_key=api_key, base_url=_DEEPSEEK_BASE_URL)


def _candidate_summary(candidate: dict[str, Any]) -> str:
    parts = [
        f"Title: {candidate.get('title', 'N/A')}",
        f"City: {candidate.get('city', 'N/A')}",
        f"Price: CHF {candidate.get('price', 'N/A')}",
        f"Rooms: {candidate.get('rooms', 'N/A')}",
        f"Area: {candidate.get('area', 'N/A')} sqm",
    ]
    desc = candidate.get("description")
    if desc:
        parts.append(f"Description: {str(desc)[:400]}")
    features = candidate.get("features")
    if isinstance(features, list) and features:
        parts.append(f"Features: {', '.join(str(f) for f in features[:8])}")
    return "\n".join(parts)


def compare_pair(
    query: str,
    candidate_a: dict[str, Any],
    candidate_b: dict[str, Any],
    client: OpenAI,
) -> tuple[float, float, str]:
    """
    Compare two candidates for a query. Returns (score_a, score_b, reason).
    Winner gets 1.0, loser 0.0; tie gives both 0.5.
    reason is a concise sentence explaining the decision from the winner's perspective.
    """
    prompt = (
        "You are a real estate expert. A user is searching for an apartment. "
        "Compare the two listings below and decide which better matches the query.\n\n"
        f"Query: {query}\n\n"
        f"Listing A:\n{_candidate_summary(candidate_a)}\n\n"
        f"Listing B:\n{_candidate_summary(candidate_b)}\n\n"
        "Respond ONLY with JSON:\n"
        '  {"winner": "A" | "B" | "tie", "reason": "<one sentence, max 20 words, '
        'describing the WINNING listing\'s own qualities that make it a great match — '
        'do NOT mention \"A\" or \"B\", do NOT compare to the other listing>"}'
    )
    response = client.chat.completions.create(
        model=_DEFAULT_MODEL,
        messages=[{"role": "user", "content": prompt}],
        response_format={"type": "json_object"},
        temperature=0.0,
        max_tokens=120,
    )
    data = json.loads(response.choices[0].message.content or "{}")
    winner = str(data.get("winner", "tie")).strip().upper()
    reason = str(data.get("reason", "")).strip()
    if winner == "A":
        reason = _rewrite_reason(reason, winner="A", loser="B")
        return 1.0, 0.0, reason
    elif winner == "B":
        reason = _rewrite_reason(reason, winner="B", loser="A")
        return 0.0, 1.0, reason
    else:
        return 0.5, 0.5, reason


def _rewrite_reason(reason: str, *, winner: str, loser: str) -> str:
    """Strip any stray 'A'/'B' / 'Listing A'/'Listing B' labels the LLM may have leaked."""
    # Remove "Listing A" / "Listing B" phrases entirely
    reason = re.sub(rf"\bListing\s+{winner}\b", "This listing", reason, flags=re.IGNORECASE)
    reason = re.sub(rf"\bListing\s+{loser}\b", "", reason, flags=re.IGNORECASE)
    # Remove bare standalone letter labels
    reason = re.sub(rf"\b{winner}\b", "", reason)
    reason = re.sub(rf"\b{loser}\b", "", reason)
    # Clean up any double spaces left behind
    reason = re.sub(r"  +", " ", reason).strip()
    return reason


def get_pairwise_scores(
    query: str,
    candidates: list[dict[str, Any]],
) -> tuple[list[float], list[str]]:
    """
    Run a full round-robin tournament for *candidates*.

    Returns
    -------
    win_scores : list[float]
        Total win points for each candidate (range [0, n-1]).
    reasons : list[str]
        For each candidate: the LLM reason from the comparison where it won
        most recently (empty string if it never won).
    """
    n = len(candidates)
    win_scores = [0.0] * n
    best_reason: list[str] = [""] * n

    if n <= 1:
        return win_scores, best_reason

    client = _get_client()

    for i in range(n):
        for j in range(i + 1, n):
            try:
                sa, sb, reason = compare_pair(query, candidates[i], candidates[j], client)
            except Exception:
                sa, sb, reason = 0.5, 0.5, ""
            win_scores[i] += sa
            win_scores[j] += sb
            # Attach reason to the winner so it explains why they're better
            if sa > sb and reason:
                best_reason[i] = reason
            elif sb > sa and reason:
                best_reason[j] = reason

    return win_scores, best_reason
