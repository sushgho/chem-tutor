"""Retrieval for shared subject and class materials."""
from io import BytesIO
import re
from urllib.parse import urlencode

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
SECTION_HEADING = re.compile(r"^\s*(\d+)\.(\d+(?:\.\d+)?)\s+([^\W\d_].*?)\s*$")
INCOMPLETE_HEADING = re.compile(r"\b(?:and|as|at|by|for|from|in|into|of|on|the|to|with|its)$", re.IGNORECASE)
LOWERCASE_CONTINUATION = re.compile(r"^[a-z][a-z -]{0,39}$")
EXERCISE_HEADING = re.compile(r"^\s*(?:MISCELLANEOUS\s+)?EXERCISES?\b(?:\s+(\d+)\.(\d+))?", re.IGNORECASE)


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


def list_topics(subject: str, grade: str, chapter_no: int) -> list[dict]:
    with pool.connection() as conn:
        rows = conn.execute(
            """SELECT d.id AS document_id, c.content
               FROM course_document_chunks c
               JOIN course_documents d ON d.id = c.document_id
               WHERE d.subject = %s AND d.grade = %s AND d.chapter_no = %s
               ORDER BY d.id, c.page, c.id""",
            (subject, grade, chapter_no),
        ).fetchall()

    topics: dict[str, str] = {}
    exercised_sections: set[str] = set()
    document_id = None
    exercises_started = False
    for row in rows:
        if row["document_id"] != document_id:
            document_id = row["document_id"]
            exercised_sections = set()
            exercises_started = False
        lines = [re.sub(r"\s+", " ", line).strip() for line in row["content"].splitlines()]
        for index, line in enumerate(lines):
            exercise = EXERCISE_HEADING.match(line)
            if exercise:
                if exercise.group(1) and int(exercise.group(1)) == chapter_no:
                    exercised_sections.add(f"{exercise.group(1)}.{exercise.group(2)}")
                else:
                    exercises_started = True
                continue

            match = SECTION_HEADING.match(line)
            if (
                not match
                or exercises_started
                or int(match.group(1)) != chapter_no
            ):
                continue

            title = match.group(3).strip(" .:-")
            next_index = index + 1
            while next_index < len(lines) and lines[next_index]:
                next_line = lines[next_index]
                if (
                    SECTION_HEADING.match(next_line)
                    or re.match(r"^\d+[.)]", next_line)
                    or len(next_line) > 80
                    or not (
                        INCOMPLETE_HEADING.search(title)
                        or LOWERCASE_CONTINUATION.fullmatch(next_line)
                    )
                ):
                    break
                title = f"{title} {next_line}".strip()
                next_index += 1

            section_no = f"{match.group(1)}.{match.group(2)}"
            if section_no not in exercised_sections and title and len(title) <= 160:
                if len(title) > len(topics.get(section_no, "")):
                    topics[section_no] = title

    return [
        {"section_no": section_no, "title": title}
        for section_no, title in sorted(topics.items(), key=lambda item: tuple(map(int, item[0].split("."))))
    ]


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
        image_url = None
        if row["page"] is not None:
            image_url = "/study/page-image?" + urlencode({
                "subject": subject,
                "grade": grade,
                "source": row["source"],
                "page": row["page"],
            })
        chunks.append(rag.Chunk(
            row["id"], row["content"], row["source"], row["page"], None,
            float(row["dist"]), image_url,
        ))
    return chunks


def get_pdf_page(subject: str, grade: str, source: str, page_number: int) -> bytes | None:
    with pool.connection() as conn:
        row = conn.execute(
            """SELECT pdf_data FROM course_documents
               WHERE subject = %s AND grade = %s AND source = %s""",
            (subject, grade, source),
        ).fetchone()
    if not row or not row["pdf_data"]:
        return None

    import pypdfium2

    pdf = pypdfium2.PdfDocument(row["pdf_data"])
    try:
        if page_number > len(pdf):
            raise ValueError(f"Page {page_number} is outside this document.")
        page = pdf[page_number - 1]
        try:
            width, height = page.get_size()
            scale = min(2, 2400 / max(width, height))
            bitmap = page.render(scale=scale)
            try:
                with BytesIO() as output:
                    bitmap.to_pil().save(output, format="PNG")
                    return output.getvalue()
            finally:
                bitmap.close()
        finally:
            page.close()
    finally:
        pdf.close()
