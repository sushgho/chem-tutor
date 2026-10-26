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
