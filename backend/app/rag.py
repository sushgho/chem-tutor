"""Hybrid retrieval (vector + keyword, fused with RRF) with scope widening.

Scope ladder: topic -> unit -> grade. We start narrow so the tutor stays on
the student's current chapter, and widen only if too little relevant text is
found. Chunks farther than settings.max_dist are dropped so the tutor can
honestly say "my material doesn't cover this".
"""
from dataclasses import dataclass

from .config import settings
from .db import pool
from .embeddings import embed_query

SQL = """
WITH v AS (
  SELECT id, ROW_NUMBER() OVER (ORDER BY embedding <=> %(qv)s) AS r
  FROM chunks WHERE {where}
  ORDER BY embedding <=> %(qv)s LIMIT 30
),
f AS (
  SELECT id, ROW_NUMBER() OVER (ORDER BY ts_rank_cd(tsv, q) DESC) AS r
  FROM chunks, websearch_to_tsquery('english', %(q)s) q
  WHERE tsv @@ q AND {where}
  ORDER BY ts_rank_cd(tsv, q) DESC LIMIT 30
)
SELECT c.id, c.content, c.source, c.page, t.title AS topic_title,
       c.embedding <=> %(qv)s AS dist,
       COALESCE(1.0 / (60 + v.r), 0) + COALESCE(1.0 / (60 + f.r), 0) AS score
FROM chunks c
LEFT JOIN topics t ON t.id = c.topic_id
LEFT JOIN v ON v.id = c.id
LEFT JOIN f ON f.id = c.id
WHERE v.id IS NOT NULL OR f.id IS NOT NULL
ORDER BY score DESC
LIMIT %(k)s
"""


@dataclass
class Chunk:
    id: int
    content: str
    source: str
    page: int | None
    topic_title: str | None
    dist: float


def _search(query, qv, where, params, k):
    with pool.connection() as c:
        rows = c.execute(
            SQL.format(where=where),
            {"qv": qv, "q": query, "k": k, **params},
        ).fetchall()
    return [
        Chunk(r["id"], r["content"], r["source"], r["page"], r["topic_title"], float(r["dist"]))
        for r in rows
        if float(r["dist"]) <= settings.max_dist
    ]


def retrieve(query: str, grade: str, unit_no: int | None = None,
             topic_id: str | None = None, k: int = 6, min_hits: int = 3,
             start: str = "unit") -> list[Chunk]:
    qv = embed_query(query)
    ladder = []
    if topic_id and start == "topic":
        ladder.append(("grade = %(grade)s AND topic_id = %(topic)s", {"grade": grade, "topic": topic_id}))
    if unit_no and start in ("topic", "unit"):
        ladder.append(("grade = %(grade)s AND unit_no = %(unit)s", {"grade": grade, "unit": unit_no}))
    ladder.append(("grade = %(grade)s", {"grade": grade}))

    best: list[Chunk] = []
    for where, params in ladder:
        hits = _search(query, qv, where, params, k)
        if len(hits) > len(best):
            best = hits
        if len(hits) >= min_hits:
            return hits
    return best


def format_context(chunks: list[Chunk]) -> str:
    if not chunks:
        return "(no relevant excerpts were found in the course material)"
    parts = []
    for i, c in enumerate(chunks, start=1):
        page = f", p.{c.page}" if c.page else ""
        parts.append(f"[{i}] ({c.source}{page})\n{c.content}")
    return "\n\n".join(parts)


def sources_payload(chunks: list[Chunk]) -> list[dict]:
    return [
        {"n": i, "source": c.source, "page": c.page, "topic": c.topic_title}
        for i, c in enumerate(chunks, start=1)
    ]
