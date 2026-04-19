import os

import dashscope
import numpy as np
from openai import OpenAI

dashscope.base_http_api_url = 'https://dashscope-intl.aliyuncs.com/api/v1'

_embedding_client: OpenAI | None = None


def _get_embedding_client() -> OpenAI:
    global _embedding_client
    if _embedding_client is None:
        _embedding_client = OpenAI(
            api_key=os.getenv("DASHSCOPE_API_KEY"),
            base_url="https://dashscope-intl.aliyuncs.com/compatible-mode/v1",
        )
    return _embedding_client


def get_cosine_similarity(vec_a: np.ndarray, vec_b: np.ndarray) -> float:
    if len(vec_a) != len(vec_b):
        raise ValueError("Vectors must be of the same length")

    dot_product = np.dot(vec_a, vec_b)
    magnitude_a = np.linalg.norm(vec_a)
    magnitude_b = np.linalg.norm(vec_b)

    if magnitude_a == 0 or magnitude_b == 0:
        return 0.0

    return (dot_product / (magnitude_a * magnitude_b)).item()

def get_text_embedding(text: str | list[str]) -> np.ndarray | list[np.ndarray]:
    client = _get_embedding_client()
    
    # Convert single string to list for uniform processing
    texts = [text] if isinstance(text, str) else text

    # Process in batches of 10 (API limit)
    all_embeddings = []
    batch_size = 10

    for i in range(0, len(texts), batch_size):
        batch = texts[i:i + batch_size]
        completion = client.embeddings.create(
            model="text-embedding-v4",
            input=batch
        )
        batch_embeddings = [ np.array(embedding.embedding) for embedding in completion.data]
        all_embeddings.extend(batch_embeddings)

    # Return single embedding for single input, list for multiple inputs
    return all_embeddings[0] if isinstance(text, str) else all_embeddings

def get_image_embedding(image_url: str) -> np.ndarray:
    input = [{'image': image_url}]
    resp = dashscope.MultiModalEmbedding.call(
        api_key=os.getenv('DASHSCOPE_API_KEY'),
        model="tongyi-embedding-vision-plus",
        input=input,

    )
    return np.array(resp.output["embeddings"][0]['embedding'])
