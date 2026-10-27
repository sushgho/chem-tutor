import hashlib
import math
import re
from functools import lru_cache

from pgvector import Vector

from .config import settings

# bge models work best with this prefix on *queries* (not on documents)
QUERY_PREFIX = "Represent this sentence for searching relevant passages: "
TOKEN_PATTERN = re.compile(r"[a-z0-9]+")


@lru_cache(maxsize=1)
def _model():
    from sentence_transformers import SentenceTransformer

    return SentenceTransformer(settings.embed_model)


def _keyword_vector(text: str) -> Vector:
    tokens = TOKEN_PATTERN.findall(text.lower())
    features = tokens + [f"{left}_{right}" for left, right in zip(tokens, tokens[1:])]
    values = [0.0] * settings.embed_dim
    for feature in features:
        digest = hashlib.blake2b(feature.encode("utf-8"), digest_size=8).digest()
        index = int.from_bytes(digest[:4], "little") % settings.embed_dim
        values[index] += 1.0 if digest[4] & 1 else -1.0
    norm = math.sqrt(sum(value * value for value in values))
    if norm:
        values = [value / norm for value in values]
    return Vector(values)


def embed_docs(texts):
    if settings.embedding_mode == "keyword":
        return [_keyword_vector(text) for text in texts]
    return _model().encode(list(texts), normalize_embeddings=True, batch_size=32)


def embed_query(text: str):
    if settings.embedding_mode == "keyword":
        return _keyword_vector(text)
    return _model().encode(QUERY_PREFIX + text, normalize_embeddings=True)


def similarity(left, right) -> float:
    left_values = left.to_list() if isinstance(left, Vector) else left
    right_values = right.to_list() if isinstance(right, Vector) else right
    return sum(a * b for a, b in zip(left_values, right_values))
