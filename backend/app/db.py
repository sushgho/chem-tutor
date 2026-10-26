import pathlib

import psycopg
from pgvector.psycopg import register_vector
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

from .config import settings
from .curriculum import flatten

SCHEMA = (pathlib.Path(__file__).resolve().parent.parent / "schema.sql").read_text()


def _configure(conn):
    register_vector(conn)
    conn.commit()  # pool requires the connection to be idle after configure


pool = ConnectionPool(
    settings.database_url,
    min_size=1,
    max_size=8,
    open=False,
    configure=_configure,
    kwargs={"row_factory": dict_row},
)


def init_db():
    """Create tables (idempotent), open the pool and seed the curriculum."""
    with psycopg.connect(settings.database_url, autocommit=True) as c:
        c.execute(SCHEMA.replace("__DIM__", str(settings.embed_dim)))
    pool.open()
    pool.wait()
    with pool.connection() as c:
        for t in flatten():
            c.execute(
                """INSERT INTO topics (id, grade, unit_no, unit_title, title, ord)
                   VALUES (%(id)s, %(grade)s, %(unit_no)s, %(unit_title)s, %(title)s, %(ord)s)
                   ON CONFLICT (id) DO UPDATE SET
                     grade = EXCLUDED.grade, unit_no = EXCLUDED.unit_no,
                     unit_title = EXCLUDED.unit_title, title = EXCLUDED.title,
                     ord = EXCLUDED.ord""",
                t,
            )


def get_topic(topic_id: str):
    with pool.connection() as c:
        return c.execute("SELECT * FROM topics WHERE id = %s", (topic_id,)).fetchone()
