CREATE EXTENSION IF NOT EXISTS vector;

-- Curriculum tree: Grade -> Unit -> Topic (seeded from app/curriculum.py)
CREATE TABLE IF NOT EXISTS topics (
    id          TEXT PRIMARY KEY,          -- e.g. XI-01-03
    grade       TEXT NOT NULL,             -- XI | XII
    unit_no     INT  NOT NULL,
    unit_title  TEXT NOT NULL,
    title       TEXT NOT NULL,
    ord         INT  NOT NULL
);

-- Textbook / notes chunks used by RAG
CREATE TABLE IF NOT EXISTS chunks (
    id          BIGSERIAL PRIMARY KEY,
    grade       TEXT NOT NULL,
    unit_no     INT,
    topic_id    TEXT REFERENCES topics(id) ON DELETE SET NULL,
    source      TEXT NOT NULL,             -- file name / book title
    page        INT,
    content     TEXT NOT NULL,
    embedding   vector(__DIM__) NOT NULL,
    tsv         tsvector GENERATED ALWAYS AS (to_tsvector('english', content)) STORED
);
CREATE INDEX IF NOT EXISTS chunks_embedding_idx ON chunks USING hnsw (embedding vector_cosine_ops);
CREATE INDEX IF NOT EXISTS chunks_tsv_idx ON chunks USING gin (tsv);
CREATE INDEX IF NOT EXISTS chunks_scope_idx ON chunks (grade, unit_no, topic_id);

-- Shared, subject-specific course material loaded from authorized local data files.
CREATE TABLE IF NOT EXISTS course_documents (
    id          BIGSERIAL PRIMARY KEY,
    subject     TEXT NOT NULL CHECK (subject IN ('maths', 'physics', 'chemistry', 'biology')),
    grade       TEXT NOT NULL CHECK (grade IN ('XI', 'XII')),
    source      TEXT NOT NULL,
    title       TEXT NOT NULL DEFAULT '',
    chapter_no  INT,
    content_hash TEXT NOT NULL,
    UNIQUE (subject, grade, source),
    UNIQUE (subject, grade, content_hash)
);
ALTER TABLE course_documents ADD COLUMN IF NOT EXISTS title TEXT NOT NULL DEFAULT '';
ALTER TABLE course_documents ADD COLUMN IF NOT EXISTS chapter_no INT;

CREATE TABLE IF NOT EXISTS course_document_chunks (
    id          BIGSERIAL PRIMARY KEY,
    document_id BIGINT NOT NULL REFERENCES course_documents(id) ON DELETE CASCADE,
    page        INT,
    content     TEXT NOT NULL,
    embedding   vector(__DIM__) NOT NULL,
    tsv         tsvector GENERATED ALWAYS AS (to_tsvector('english', content)) STORED
);
CREATE INDEX IF NOT EXISTS course_document_chunks_scope_idx
    ON course_document_chunks (document_id);
CREATE INDEX IF NOT EXISTS course_document_chunks_embedding_idx
    ON course_document_chunks USING hnsw (embedding vector_cosine_ops);
CREATE INDEX IF NOT EXISTS course_document_chunks_tsv_idx
    ON course_document_chunks USING gin (tsv);

CREATE TABLE IF NOT EXISTS students (
    id          BIGSERIAL PRIMARY KEY,
    name        TEXT NOT NULL,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS progress (
    student_id   BIGINT NOT NULL REFERENCES students(id) ON DELETE CASCADE,
    topic_id     TEXT   NOT NULL REFERENCES topics(id) ON DELETE CASCADE,
    status       TEXT   NOT NULL DEFAULT 'in_progress',   -- in_progress | mastered | needs_revision
    mastery      REAL   NOT NULL DEFAULT 0,               -- 0..1 from quiz results
    attempts     INT    NOT NULL DEFAULT 0,
    streak       INT    NOT NULL DEFAULT 0,
    doubts_count INT    NOT NULL DEFAULT 0,
    next_review  TIMESTAMPTZ,
    last_seen    TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (student_id, topic_id)
);

CREATE TABLE IF NOT EXISTS messages (
    id          BIGSERIAL PRIMARY KEY,
    student_id  BIGINT NOT NULL REFERENCES students(id) ON DELETE CASCADE,
    topic_id    TEXT   REFERENCES topics(id) ON DELETE SET NULL,
    kind        TEXT   NOT NULL,                          -- lesson | doubt
    role        TEXT   NOT NULL,                          -- user | assistant
    content     TEXT   NOT NULL,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS quiz_attempts (
    id          BIGSERIAL PRIMARY KEY,
    student_id  BIGINT NOT NULL REFERENCES students(id) ON DELETE CASCADE,
    topic_id    TEXT   NOT NULL REFERENCES topics(id) ON DELETE CASCADE,
    score       INT NOT NULL,
    total       INT NOT NULL,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS student_documents (
    id          BIGSERIAL PRIMARY KEY,
    student_id  BIGINT NOT NULL REFERENCES students(id) ON DELETE CASCADE,
    library_key UUID NOT NULL,
    subject     TEXT NOT NULL CHECK (subject IN ('maths', 'physics', 'chemistry', 'biology')),
    filename    TEXT NOT NULL,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS student_documents_owner_idx
    ON student_documents (student_id, library_key, subject, created_at DESC);

CREATE TABLE IF NOT EXISTS student_document_chunks (
    id          BIGSERIAL PRIMARY KEY,
    document_id BIGINT NOT NULL REFERENCES student_documents(id) ON DELETE CASCADE,
    student_id  BIGINT NOT NULL REFERENCES students(id) ON DELETE CASCADE,
    library_key UUID NOT NULL,
    subject     TEXT NOT NULL CHECK (subject IN ('maths', 'physics', 'chemistry', 'biology')),
    page        INT,
    content     TEXT NOT NULL,
    embedding   vector(__DIM__) NOT NULL,
    tsv         tsvector GENERATED ALWAYS AS (to_tsvector('english', content)) STORED
);
CREATE INDEX IF NOT EXISTS student_document_chunks_owner_idx
    ON student_document_chunks (student_id, library_key, subject);
CREATE INDEX IF NOT EXISTS student_document_chunks_embedding_idx
    ON student_document_chunks USING hnsw (embedding vector_cosine_ops);
CREATE INDEX IF NOT EXISTS student_document_chunks_tsv_idx
    ON student_document_chunks USING gin (tsv);
