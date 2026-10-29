"""Retrieval for shared subject and class materials."""
from . import rag
from .config import settings
from .db import pool
from .embeddings import embed_query


def retrieve(subject: str, grade: str, query: str, limit: int = 4) -> list[rag.Chunk]:
    query_vector = embed_query(query)
    with pool.connection() as conn:
        rows = conn.execute(
            """WITH scoped AS (
                   SELECT c.id, c.content, c.page, d.source, c.embedding, c.tsv
                   FROM course_document_chunks c
                   JOIN course_documents d ON d.id = c.document_id
                   WHERE d.subject = %(subject)s AND d.grade = %(grade)s
               ),
               v AS (
                   SELECT id, ROW_NUMBER() OVER (ORDER BY embedding <=> %(qv)s) AS r
                   FROM scoped
                   ORDER BY embedding <=> %(qv)s LIMIT 30
               ),
               f AS (
                   SELECT s.id, ROW_NUMBER() OVER (ORDER BY ts_rank_cd(s.tsv, q) DESC) AS r
                   FROM scoped s, websearch_to_tsquery('english', %(query)s) q
                   WHERE s.tsv @@ q
                   ORDER BY ts_rank_cd(s.tsv, q) DESC LIMIT 30
               )
               SELECT s.id, s.content, s.source, s.page, s.embedding <=> %(qv)s AS dist,
                      COALESCE(1.0 / (60 + v.r), 0) + COALESCE(1.0 / (60 + f.r), 0) AS score
               FROM scoped s
               LEFT JOIN v ON v.id = s.id
               LEFT JOIN f ON f.id = s.id
               WHERE v.id IS NOT NULL OR f.id IS NOT NULL
               ORDER BY score DESC
               LIMIT %(limit)s""",
            {
                "subject": subject,
                "grade": grade,
                "qv": query_vector,
                "query": query,
                "limit": limit,
            },
        ).fetchall()
    return [
        rag.Chunk(row["id"], row["content"], row["source"], row["page"], None, float(row["dist"]))
        for row in rows
        if float(row["dist"]) <= settings.max_dist
    ]
