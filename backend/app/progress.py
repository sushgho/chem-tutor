from .db import pool


def ensure_student(name: str) -> int:
    with pool.connection() as c:
        return c.execute(
            "INSERT INTO students (name) VALUES (%s) RETURNING id", (name,)
        ).fetchone()["id"]


def touch(student_id: int, topic_id: str):
    """Mark a topic as started / seen (never downgrades 'mastered')."""
    with pool.connection() as c:
        c.execute(
            """INSERT INTO progress (student_id, topic_id) VALUES (%s, %s)
               ON CONFLICT (student_id, topic_id) DO UPDATE SET last_seen = now()""",
            (student_id, topic_id),
        )


def record_doubt(student_id: int, topic_id: str):
    with pool.connection() as c:
        c.execute(
            """INSERT INTO progress (student_id, topic_id, doubts_count) VALUES (%s, %s, 1)
               ON CONFLICT (student_id, topic_id) DO UPDATE
               SET doubts_count = progress.doubts_count + 1, last_seen = now()""",
            (student_id, topic_id),
        )


def set_status(student_id: int, topic_id: str, status: str):
    if status not in ("in_progress", "mastered", "needs_revision"):
        raise ValueError("bad status")
    with pool.connection() as c:
        c.execute(
            """INSERT INTO progress (student_id, topic_id, status) VALUES (%s, %s, %s)
               ON CONFLICT (student_id, topic_id) DO UPDATE
               SET status = EXCLUDED.status, last_seen = now()""",
            (student_id, topic_id, status),
        )


def record_quiz(student_id: int, topic_id: str, score: int, total: int) -> dict:
    """Update mastery + spaced-repetition schedule from a quiz result."""
    ratio = score / total if total else 0.0
    with pool.connection() as c:
        c.execute(
            "INSERT INTO quiz_attempts (student_id, topic_id, score, total) VALUES (%s,%s,%s,%s)",
            (student_id, topic_id, score, total),
        )
        row = c.execute(
            "SELECT mastery, attempts, streak FROM progress WHERE student_id=%s AND topic_id=%s",
            (student_id, topic_id),
        ).fetchone()
        old_m = row["mastery"] if row else 0.0
        attempts = row["attempts"] if row else 0
        streak = row["streak"] if row else 0

        mastery = ratio if attempts == 0 else 0.6 * ratio + 0.4 * old_m
        streak = streak + 1 if ratio >= 0.8 else 0
        if ratio < 0.5:
            days = 1
        elif ratio < 0.8:
            days = 3
        else:
            days = min(2 ** streak, 30)
        status = "mastered" if mastery >= 0.8 else (
            "needs_revision" if ratio < 0.5 else "in_progress")

        c.execute(
            """INSERT INTO progress (student_id, topic_id, status, mastery, attempts, streak, next_review)
               VALUES (%(s)s, %(t)s, %(st)s, %(m)s, 1, %(sk)s, now() + make_interval(days => %(d)s))
               ON CONFLICT (student_id, topic_id) DO UPDATE SET
                 status = EXCLUDED.status, mastery = EXCLUDED.mastery,
                 attempts = progress.attempts + 1, streak = EXCLUDED.streak,
                 next_review = EXCLUDED.next_review, last_seen = now()""",
            {"s": student_id, "t": topic_id, "st": status, "m": mastery, "sk": streak, "d": days},
        )
    return {"mastery": mastery, "status": status, "next_review_in_days": days}


def get_progress(student_id: int) -> dict:
    with pool.connection() as c:
        rows = c.execute(
            """SELECT topic_id, status, mastery, doubts_count, next_review,
                      (next_review IS NOT NULL AND next_review <= now()) AS due
               FROM progress WHERE student_id = %s""",
            (student_id,),
        ).fetchall()
        totals = c.execute("SELECT grade, COUNT(*) AS n FROM topics GROUP BY grade").fetchall()
        mastered = c.execute(
            """SELECT t.grade, COUNT(*) AS n FROM progress p JOIN topics t ON t.id = p.topic_id
               WHERE p.student_id = %s AND p.status = 'mastered' GROUP BY t.grade""",
            (student_id,),
        ).fetchall()
    done = {r["grade"]: r["n"] for r in mastered}
    summary = {
        r["grade"]: {"total": r["n"], "mastered": done.get(r["grade"], 0)} for r in totals
    }
    return {
        "topics": {r["topic_id"]: {**r, "next_review": str(r["next_review"]) if r["next_review"] else None}
                   for r in rows},
        "summary": summary,
        "due_for_revision": [r["topic_id"] for r in rows if r["due"]],
    }


def log_message(student_id: int, topic_id: str | None, kind: str, role: str, content: str):
    with pool.connection() as c:
        c.execute(
            "INSERT INTO messages (student_id, topic_id, kind, role, content) VALUES (%s,%s,%s,%s,%s)",
            (student_id, topic_id, kind, role, content),
        )


def teacher_overview() -> dict:
    with pool.connection() as c:
        students = c.execute("SELECT COUNT(*) AS n FROM students").fetchone()["n"]
        topics = c.execute(
            """SELECT t.id, t.grade, t.unit_no, t.title,
                      COALESCE(SUM(p.doubts_count), 0) AS doubts,
                      AVG(p.mastery) FILTER (WHERE p.attempts > 0) AS avg_mastery,
                      COUNT(DISTINCT p.student_id) AS students
               FROM topics t LEFT JOIN progress p ON p.topic_id = t.id
               GROUP BY t.id ORDER BY doubts DESC, t.ord LIMIT 20"""
        ).fetchall()
    return {"students": students, "hardest_topics": topics}
