from typing import Any

import numpy as np

from app.models.utils import get_cosine_similarity, get_text_embedding, get_image_embedding

def get_similarity_scores(
    candidates: list[dict[str, Any]],
    soft_facts: dict[str, Any],
) -> list[float]:

    scores = []
    soft_facts_str = soft_facts.get("raw_description", "")
    soft_facts_embed = get_text_embedding(soft_facts_str)

    candidate_texts = [ candidate.get("description", "") for candidate in candidates ]
    candidate_embeds = get_text_embedding(candidate_texts)

    for i, candidate in enumerate(candidates):
        candidate_embed = candidate_embeds[i]
        score = get_cosine_similarity(np.array(soft_facts_embed), np.array(candidate_embed))
        scores.append(score)
    return scores

def get_image_similarity_scores(
    candidates: list[dict[str, Any]],
    soft_facts: dict[str, Any],
) -> list[float]:

    scores = []
    soft_facts_str = soft_facts.get("raw_description", "")
    soft_facts_embed = get_text_embedding(soft_facts_str)
    for candidate in candidates:
        image_urls = candidate.get("image_urls", [])
        try:
            candidate_embed = get_image_embedding(image_urls[0])
            soft_facts_embed_padded = np.pad(soft_facts_embed, (0, len(candidate_embed) - len(soft_facts_embed)), mode='constant')
            score = get_cosine_similarity(np.array(soft_facts_embed_padded), np.array(candidate_embed))
            scores.append(score)
        except Exception as e:
            scores.append(0.0)
    return scores