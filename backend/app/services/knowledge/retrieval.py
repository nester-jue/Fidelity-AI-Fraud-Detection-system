"""Cosine similarity ranking helpers for knowledge-base retrieval."""

import math
from typing import List, Sequence, Tuple


def cosine_similarity(a: Sequence[float], b: Sequence[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a)) or 1.0
    norm_b = math.sqrt(sum(y * y for y in b)) or 1.0
    return dot / (norm_a * norm_b)


def rank_chunks(
    query: str,
    chunks: Sequence[object],  # items exposing .embedding (list[float]) and .text (str)
    top_k: int,
    threshold: float = 0.0,
) -> List[Tuple[object, float]]:
    """Returns up to ``top_k`` ``(chunk, score)`` tuples, best match first."""
    from .embedding import embed

    q_vec = embed(query)
    scored = [(cosine_similarity(q_vec, c.embedding), c) for c in chunks]
    scored.sort(key=lambda t: t[0], reverse=True)
    return [(c, s) for s, c in scored if s >= threshold][:top_k]
