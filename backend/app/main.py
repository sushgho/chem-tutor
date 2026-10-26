import json
import urllib.parse
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from . import db, llm, progress, rag
from .config import settings
from .curriculum import tree


@asynccontextmanager
async def lifespan(_app: FastAPI):
    db.init_db()
    yield
    db.pool.close()


app = FastAPI(title="Chemistry Teaching Assistant", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in settings.cors_origins.split(",")],
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-Sources"],
)


def _topic_or_404(topic_id: str):
    t = db.get_topic(topic_id)
    if not t:
        raise HTTPException(404, "unknown topic")
    return t


def _stream(gen, chunks):
    headers = {"X-Sources": urllib.parse.quote(json.dumps(rag.sources_payload(chunks)))}
    return StreamingResponse(gen, media_type="text/plain; charset=utf-8", headers=headers)


# ---------- models ----------
class StudentIn(BaseModel):
    name: str = "Student"


class LessonIn(BaseModel):
    student_id: int
    topic_id: str


class AskIn(BaseModel):
    student_id: int
    topic_id: str
    question: str
    history: list[dict] = []  # [{"role": "user"|"assistant", "content": str}]


class QuizIn(BaseModel):
    topic_id: str
    n: int = 3


class QuizResultIn(BaseModel):
    student_id: int
    topic_id: str
    score: int
    total: int


class StatusIn(BaseModel):
    topic_id: str
    status: str


# ---------- routes ----------
@app.get("/health")
def health():
    return {"ok": True}


@app.get("/curriculum")
def curriculum():
    return tree()


@app.post("/students")
def create_student(body: StudentIn):
    return {"id": progress.ensure_student(body.name)}


@app.get("/students/{student_id}/progress")
def student_progress(student_id: int):
    return progress.get_progress(student_id)


@app.post("/students/{student_id}/status")
def student_status(student_id: int, body: StatusIn):
    _topic_or_404(body.topic_id)
    try:
        progress.set_status(student_id, body.topic_id, body.status)
    except ValueError:
        raise HTTPException(400, "invalid status")
    return {"ok": True}


@app.post("/lesson")
def lesson(body: LessonIn):
    topic = _topic_or_404(body.topic_id)
    progress.touch(body.student_id, body.topic_id)
    chunks = rag.retrieve(
        f"{topic['title']} {topic['unit_title']}", topic["grade"],
        topic["unit_no"], body.topic_id, k=8, min_hits=4, start="topic",
    )
    prompt = llm.lesson_prompt(topic["title"], topic["unit_title"], rag.format_context(chunks))

    def gen():
        out = []
        for piece in llm.stream_answer(
            llm.teacher_system(topic["grade"]), [{"role": "user", "content": prompt}]
        ):
            out.append(piece)
            yield piece
        progress.log_message(body.student_id, body.topic_id, "lesson", "assistant", "".join(out))

    return _stream(gen(), chunks)


@app.post("/ask")
def ask(body: AskIn):
    topic = _topic_or_404(body.topic_id)
    progress.record_doubt(body.student_id, body.topic_id)
    progress.log_message(body.student_id, body.topic_id, "doubt", "user", body.question)
    chunks = rag.retrieve(body.question, topic["grade"], topic["unit_no"], body.topic_id, k=6)
    history = [
        {"role": m["role"], "content": m["content"]}
        for m in body.history[-6:]
        if m.get("role") in ("user", "assistant") and m.get("content")
    ]
    messages = history + [{
        "role": "user",
        "content": llm.doubt_prompt(body.question, rag.format_context(chunks), topic["title"]),
    }]

    def gen():
        out = []
        for piece in llm.stream_answer(llm.teacher_system(topic["grade"]), messages):
            out.append(piece)
            yield piece
        progress.log_message(body.student_id, body.topic_id, "doubt", "assistant", "".join(out))

    return _stream(gen(), chunks)


@app.post("/quiz")
def quiz(body: QuizIn):
    topic = _topic_or_404(body.topic_id)
    chunks = rag.retrieve(
        topic["title"], topic["grade"], topic["unit_no"], body.topic_id, k=6, start="topic"
    )
    if not chunks:
        raise HTTPException(409, "No course material ingested for this topic yet.")
    items = llm.make_quiz(topic["grade"], topic["title"], rag.format_context(chunks), body.n)
    return {"items": items}


@app.post("/quiz/submit")
def quiz_submit(body: QuizResultIn):
    _topic_or_404(body.topic_id)
    return progress.record_quiz(body.student_id, body.topic_id, body.score, body.total)


@app.get("/teacher/overview")
def teacher_overview():
    return progress.teacher_overview()
