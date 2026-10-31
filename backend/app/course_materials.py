"""Retrieval for shared subject and class materials."""
from . import rag
from .config import settings
from .db import pool
from .embeddings import embed_query


CLASS_XI_CHAPTER_TITLES = {
    "maths": {
        1: "Sets",
        2: "Relations and Functions",
        3: "Trigonometric Functions",
        4: "Complex Numbers and Quadratic Equations",
        5: "Linear Inequalities",
        6: "Permutations and Combinations",
        7: "Binomial Theorem",
        8: "Sequences and Series",
        9: "Straight Lines",
        10: "Conic Sections",
        11: "Introduction to Three Dimensional Geometry",
        12: "Limits and Derivatives",
        13: "Statistics",
        14: "Probability",
    },
    "physics": {
        1: "Units and Measurement",
        2: "Motion in a Straight Line",
        3: "Motion in a Plane",
        4: "Laws of Motion",
        5: "Work, Energy and Power",
        6: "Systems of Particles and Rotational Motion",
        7: "Gravitation",
        8: "Mechanical Properties of Solids",
        9: "Mechanical Properties of Fluids",
        10: "Thermal Properties of Matter",
        11: "Thermodynamics",
        12: "Kinetic Theory",
        13: "Oscillations",
        14: "Waves",
    },
    "chemistry": {
        1: "Some Basic Concepts of Chemistry",
        2: "Structure of Atom",
        3: "Classification of Elements and Periodicity in Properties",
        4: "Chemical Bonding and Molecular Structure",
        5: "States of Matter: Gases and Liquids",
        6: "Thermodynamics",
        7: "Equilibrium",
        8: "Redox Reactions",
        9: "Hydrogen",
        10: "The s-Block Elements",
        11: "Some p-Block Elements",
        12: "Organic Chemistry: Some Basic Principles and Techniques",
        13: "Hydrocarbons",
        14: "Environmental Chemistry",
    },
    "biology": {
        1: "The Living World",
        2: "Biological Classification",
        3: "Plant Kingdom",
        4: "Animal Kingdom",
        5: "Morphology of Flowering Plants",
        6: "Anatomy of Flowering Plants",
        7: "Structural Organisation in Animals",
        8: "Cell: The Unit of Life",
        9: "Biomolecules",
        10: "Cell Cycle and Cell Division",
        11: "Transport in Plants",
        12: "Mineral Nutrition",
        13: "Photosynthesis in Higher Plants",
        14: "Respiration in Plants",
        15: "Plant Growth and Development",
        16: "Digestion and Absorption",
        17: "Breathing and Exchange of Gases",
        18: "Body Fluids and Circulation",
        19: "Excretory Products and their Elimination",
        20: "Locomotion and Movement",
        21: "Neural Control and Coordination",
        22: "Chemical Coordination and Integration",
    },
}


def list_chapters(subject: str, grade: str) -> list[dict]:
    with pool.connection() as conn:
        rows = conn.execute(
            """SELECT chapter_no, title
               FROM course_documents
               WHERE subject = %s AND grade = %s
                 AND chapter_no IS NOT NULL AND title <> ''
               ORDER BY chapter_no, title""",
            (subject, grade),
        ).fetchall()
    chapters = {}
    for row in rows:
        chapter_no = row["chapter_no"]
        title = (
            CLASS_XI_CHAPTER_TITLES.get(subject, {}).get(chapter_no, row["title"])
            if grade == "XI"
            else row["title"]
        )
        chapters.setdefault(chapter_no, {"chapter_no": chapter_no, "title": title})
    return list(chapters.values())


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
                      f.id IS NOT NULL AS keyword_match,
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
    chunks = []
    for row in rows:
        if settings.embedding_mode == "keyword":
            if not row["keyword_match"]:
                continue
        elif float(row["dist"]) > settings.max_dist:
            continue
        chunks.append(
            rag.Chunk(row["id"], row["content"], row["source"], row["page"], None, float(row["dist"]))
        )
    return chunks
