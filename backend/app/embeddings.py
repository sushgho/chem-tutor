from functools import lru_cache

from .config import settings

# bge models work best with this prefix on *queries* (not on documents)
QUERY_PREFIX = "Represent this sentence for searching relevant passages: "


@lru_cache(maxsize=1)
def _model():
    from sentence_transformers import SentenceTransformer

    return SentenceTransformer(settings.embed_model)


def embed_docs(texts):
    return _model().encode(list(texts), normalize_embeddings=True, batch_size=32)


def embed_query(text: str):
    return _model().encode(QUERY_PREFIX + text, normalize_embeddings=True)
