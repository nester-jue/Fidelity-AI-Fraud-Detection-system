"""Pure-Python hashed embedding vectors for knowledge-base retrieval.

The development environment does not install heavy ML dependencies
(scikit-learn, sentence-transformers, ...), so retrieval uses the
"hashing trick": tokens — unigrams and bigrams — are hashed into a fixed-size
vector with a random sign per bucket. Cosine similarity over these vectors
gives keyword/phrase-aware ranking for retrieval without any new dependencies.
"""

import hashlib
import math
import re
from typing import List

EMBEDDING_DIM = 512


def tokenize(text: str) -> List[str]:
    return re.findall(r"[a-z0-9]+", (text or "").lower())


def _hashed_features(text: str, dim: int = EMBEDDING_DIM) -> List[str]:
    toks = tokenize(text)
    feats: List[str] = []
    for i, tok in enumerate(toks):
        feats.append(tok)
        if i + 1 < len(toks):
            feats.append(f"{toks[i]}_{toks[i + 1]}")
    return feats


def embed(text: str, dim: int = EMBEDDING_DIM) -> List[float]:
    vec = [0.0] * dim
    for feat in _hashed_features(text, dim):
        h = int(hashlib.md5(feat.encode("utf-8")).hexdigest(), 16)
        idx = h % dim
        sign = 1.0 if (h >> 16) & 1 else -1.0
        vec[idx] += sign
    norm = math.sqrt(sum(v * v for v in vec)) or 1.0
    return [v / norm for v in vec]
