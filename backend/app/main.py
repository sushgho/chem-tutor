import json
import re
import urllib.parse
from contextlib import asynccontextmanager
from typing import Literal

from fastapi import Depends, FastAPI, File, Form, Header, HTTPException, Query, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response, StreamingResponse
from pydantic import BaseModel, Field

from . import auth, course_materials, db, documents, llm, progress, rag
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


def authenticated_student_id(
    authorization: str | None = Header(default=None),
    guest_session: str | None = Header(default=None, alias="X-Guest-Session"),
) -> int:
    if authorization and authorization.startswith("Bearer "):
        token = authorization.removeprefix("Bearer ").strip()
        if not token:
            raise HTTPException(401, "Invalid access token.")
        try:
            auth_user_id = auth.verify_access_token(token)
        except auth.AuthServiceUnavailable as exc:
            raise HTTPException(503, str(exc)) from exc
        except auth.InvalidAccessToken as exc:
            raise HTTPException(401, str(exc), headers={"WWW-Authenticate": "Bearer"}) from exc
        return progress.ensure_authenticated_student(auth_user_id)

    if guest_session:
        guest = progress.get_guest_session(guest_session)
        if guest:
            return guest["id"]
        raise HTTPException(401, "Invalid guest session.")

    if not authorization:
        raise HTTPException(
            401,
            "Create a guest session to access student data.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    raise HTTPException(401, "Invalid access token.", headers={"WWW-Authenticate": "Bearer"})


def _require_student_owner(student_id: int, authenticated_id: int):
    if student_id != authenticated_id:
        raise HTTPException(403, "You cannot access another student's data.")


def _stream(gen, chunks):
    headers = {"X-Sources": urllib.parse.quote(json.dumps(rag.sources_payload(chunks)))}
    return StreamingResponse(gen, media_type="text/plain; charset=utf-8", headers=headers)


def _source_page_search_query(question: str) -> str:
    query = re.sub(r"\b\d+(?:\.\d+)*\b", " ", question)
    query = re.sub(r"[^\w\s-]", " ", query)
    query = re.sub(
        r"\b(?:a|an|and|can|chapter|exact|figure|figures|for|from|help|i|image|images|"
        r"in|include|me|of|original|page|pages|picture|pictures|please|show|showing|"
        r"the|textbook|this|to|view|with|you)\b",
        " ",
        query,
        flags=re.IGNORECASE,
    )
    return " ".join(query.split())


# ---------- models ----------
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


class StudyMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(max_length=8000)


class StudyChatIn(BaseModel):
    student_id: int = Field(gt=0)
    subject: Literal["maths", "physics", "chemistry", "biology"]
    grade: Literal["XI", "XII"] = "XI"
    topic_id: str | None = None
    topic_title: str | None = Field(default=None, max_length=160)
    question: str = Field(min_length=1, max_length=4000)
    mode: Literal["chat", "lesson", "check", "summary", "important_questions", "neet", "jee"] = "chat"
    history: list[StudyMessage] = Field(default_factory=list, max_length=12)


# ---------- routes ----------
@app.get("/health")
def health():
    return {"ok": True}


@app.get("/curriculum")
def curriculum():
    return tree()


@app.get("/study/chapters")
def study_chapters(
    subject: Literal["maths", "physics", "chemistry", "biology"],
    grade: Literal["XI", "XII"],
):
    return {"chapters": course_materials.list_chapters(subject, grade)}


@app.get("/study/topics")
def study_topics(
    subject: Literal["maths", "physics", "chemistry", "biology"],
    grade: Literal["XI", "XII"],
    chapter_no: int = Query(ge=1, le=99),
):
    return {"topics": course_materials.list_topics(subject, grade, chapter_no)}


@app.get("/study/page-image")
def study_page_image(
    subject: Literal["maths", "physics", "chemistry", "biology"],
    grade: Literal["XI", "XII"],
    source: str = Query(min_length=1, max_length=255),
    page: int = Query(ge=1),
):
    try:
        image = course_materials.get_pdf_page(subject, grade, source, page)
    except ValueError as exc:
        raise HTTPException(404, str(exc)) from exc
    if image is None:
        raise HTTPException(404, "The original textbook PDF is not available.")
    return Response(
        image,
        media_type="image/png",
        headers={"Cache-Control": "public, max-age=86400"},
    )


@app.post("/auth/session")
def auth_session(student_id: int = Depends(authenticated_student_id)):
    return {
        "id": student_id,
        "library_key": progress.get_student_library_key(student_id),
    }


@app.post("/guest/session")
def guest_session(guest_token: str | None = Header(default=None, alias="X-Guest-Session")):
    if guest_token:
        session = progress.get_guest_session(guest_token)
        if not session:
            raise HTTPException(401, "Invalid guest session.")
        return {**session, "guest_session": guest_token}
    return progress.create_guest_session()


@app.get("/students/{student_id}/progress")
def student_progress(
    student_id: int,
    authenticated_id: int = Depends(authenticated_student_id),
):
    _require_student_owner(student_id, authenticated_id)
    return progress.get_progress(student_id)


@app.post("/students/{student_id}/status")
def student_status(
    student_id: int,
    body: StatusIn,
    authenticated_id: int = Depends(authenticated_student_id),
):
    _require_student_owner(student_id, authenticated_id)
    _topic_or_404(body.topic_id)
    try:
        progress.set_status(student_id, body.topic_id, body.status)
    except ValueError:
        raise HTTPException(400, "invalid status")
    return {"ok": True}


@app.get("/students/{student_id}/documents")
def student_documents(
    student_id: int,
    subject: str,
    library_key: str = Header(..., alias="X-Study-Library-Key"),
    authenticated_id: int = Depends(authenticated_student_id),
):
    _require_student_owner(student_id, authenticated_id)
    if subject not in documents.SUBJECTS:
        raise HTTPException(400, "unknown subject")
    key = documents.validate_library_key(library_key)
    return {"documents": documents.list_documents(student_id, key, subject)}


@app.post("/students/{student_id}/documents")
def upload_student_document(
    student_id: int,
    subject: str = Form(...),
    file: UploadFile = File(...),
    library_key: str = Header(..., alias="X-Study-Library-Key"),
    authenticated_id: int = Depends(authenticated_student_id),
):
    _require_student_owner(student_id, authenticated_id)
    try:
        key = documents.validate_library_key(library_key)
        return documents.create_document(student_id, key, subject, file.filename or "", file.file)
    except documents.DocumentError as exc:
        raise HTTPException(exc.status_code, str(exc)) from exc


@app.delete("/students/{student_id}/documents/{document_id}")
def remove_student_document(
    student_id: int,
    document_id: int,
    library_key: str = Header(..., alias="X-Study-Library-Key"),
    authenticated_id: int = Depends(authenticated_student_id),
):
    _require_student_owner(student_id, authenticated_id)
    key = documents.validate_library_key(library_key)
    if not documents.delete_document(student_id, key, document_id):
        raise HTTPException(404, "document not found")
    return {"ok": True}


@app.post("/study/chat")
def study_chat(
    body: StudyChatIn,
    library_key: str = Header(..., alias="X-Study-Library-Key"),
    authenticated_id: int = Depends(authenticated_student_id),
):
    _require_student_owner(body.student_id, authenticated_id)
    key = documents.validate_library_key(library_key)
    topic = _topic_or_404(body.topic_id) if body.topic_id else None
    if topic and body.subject != "chemistry":
        raise HTTPException(400, "curriculum topics are currently available for Chemistry.")
    if topic and topic["grade"] != body.grade:
        raise HTTPException(400, "the selected topic does not match the chosen class.")

    query = body.question
    if body.mode == "summary":
        query = f"Summarize the key ideas, definitions, and equations in the study material. {body.question}"
    elif body.mode == "important_questions":
        query = f"High-yield revision questions and answers. {body.question}"
    elif body.mode == "neet":
        query = f"NEET-style practice questions, answers, and explanations. {body.question}"
    elif body.mode == "jee":
        query = f"JEE-style practice questions, worked answers, and explanations. {body.question}"
    if body.topic_title:
        query = f"{body.topic_title} {query}"

    if body.mode in ("summary", "important_questions", "neet", "jee"):
        uploaded_chunks = documents.retrieve_all(body.student_id, key, body.subject, limit=3)
    else:
        uploaded_chunks = documents.retrieve(body.student_id, key, body.subject, query, limit=3)
    chunks = course_materials.retrieve(body.subject, body.grade, query, limit=3)
    if re.search(
        r"\b(?:figure|figures|image|images|diagram|diagrams|illustration|illustrations|picture|pictures)\b",
        body.question,
        re.IGNORECASE,
    ):
        page_query = _source_page_search_query(body.question)
        if page_query:
            page_chunks = course_materials.retrieve(body.subject, body.grade, page_query, limit=3)
            existing_pages = {(chunk.source, chunk.page) for chunk in chunks}
            chunks.extend(
                chunk for chunk in page_chunks
                if (chunk.source, chunk.page) not in existing_pages
            )
    chunks.extend(uploaded_chunks)
    if body.subject == "chemistry":
        if topic:
            if body.topic_title != topic["title"]:
                query = f"{topic['title']} {query}"
        curriculum_chunks = rag.retrieve(
            query,
            body.grade,
            topic["unit_no"] if topic else None,
            topic["id"] if topic else None,
            k=2,
            min_hits=3,
            start="topic" if topic else "unit",
        )
        chunks.extend(curriculum_chunks)
    chunks = chunks[:8]
    history = [
        {"role": message.role, "content": message.content}
        for message in body.history[-8:]
        if message.content.strip()
    ]
    messages = history + [{
        "role": "user",
        "content": llm.study_prompt(
            body.question,
            rag.format_context(chunks),
            body.subject,
            body.mode,
            body.topic_title or (topic["title"] if topic else None),
        ),
    }]
    kind = f"study:{body.subject}"
    progress.log_message(body.student_id, topic["id"] if topic else None, kind, "user", body.question)

    def gen():
        out = []
        for piece in llm.stream_answer(llm.study_teacher_system(body.subject, body.grade), messages):
            out.append(piece)
            yield piece
        progress.log_message(
            body.student_id,
            topic["id"] if topic else None,
            kind,
            "assistant",
            "".join(out),
        )

    return _stream(gen(), chunks)


@app.post("/lesson")
def lesson(
    body: LessonIn,
    authenticated_id: int = Depends(authenticated_student_id),
):
    _require_student_owner(body.student_id, authenticated_id)
    topic = _topic_or_404(body.topic_id)
    progress.touch(body.student_id, body.topic_id)
    chunks = rag.retrieve(
        f"{topic['title']} {topic['unit_title']}", topic["grade"],
        topic["unit_no"], body.topic_id, k=4, min_hits=3, start="topic",
    )
    chunks.extend(
        course_materials.retrieve(
            "chemistry", topic["grade"], f"{topic['title']} {topic['unit_title']}", limit=4
        )
    )
    chunks = chunks[:8]
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
def ask(
    body: AskIn,
    authenticated_id: int = Depends(authenticated_student_id),
):
    _require_student_owner(body.student_id, authenticated_id)
    topic = _topic_or_404(body.topic_id)
    progress.record_doubt(body.student_id, body.topic_id)
    progress.log_message(body.student_id, body.topic_id, "doubt", "user", body.question)
    chunks = rag.retrieve(body.question, topic["grade"], topic["unit_no"], body.topic_id, k=4)
    chunks.extend(course_materials.retrieve("chemistry", topic["grade"], body.question, limit=4))
    chunks = chunks[:8]
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
def quiz_submit(
    body: QuizResultIn,
    authenticated_id: int = Depends(authenticated_student_id),
):
    _require_student_owner(body.student_id, authenticated_id)
    _topic_or_404(body.topic_id)
    return progress.record_quiz(body.student_id, body.topic_id, body.score, body.total)


@app.get("/teacher/overview")
def teacher_overview():
    return progress.teacher_overview()
