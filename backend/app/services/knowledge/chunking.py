"""Splits document text into overlapping chunks for embedding and retrieval.

Chunks target ~420 words with a 300-word stride (≈120 words overlap).
"""

from typing import List

_CHUNK_WORDS = 420
_CHUNK_STEP = 300


def chunk_text(text: str, chunk_words: int = _CHUNK_WORDS, step: int = _CHUNK_STEP) -> List[str]:
    words = (text or "").split()
    if not words:
        return []
    chunks: List[str] = []
    start = 0
    while start < len(words):
        seg = words[start:start + chunk_words]
        chunks.append(" ".join(seg))
        if start + chunk_words >= len(words):
            break
        start += step
    return chunks
