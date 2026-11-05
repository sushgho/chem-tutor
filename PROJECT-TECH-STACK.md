# DIVA Project: Tools, Libraries, and APIs

This document summarizes the technologies currently used by the DIVA multi-subject
tutoring application. It describes the repository configuration and source code; it
does not imply that every deployment service or production credential is configured.
Never put passwords, API secrets, database URLs, or Supabase service-role keys in this
document.

## Application overview

- **Frontend:** Next.js web application with a desktop tutor at `/` and a mobile/PWA
  tutor at `/mobile`.
- **Backend:** FastAPI service that provides curriculum, study, document, progress,
  quiz, and authentication-session endpoints.
- **Database:** PostgreSQL with the pgvector extension for course material, learner
  progress, chat records, and uploaded study-document indexes.
- **AI:** Groq-hosted chat completions accessed through the OpenAI-compatible API.
- **Authentication:** Supabase Auth for email/phone one-time codes and password sign-in.
  The backend verifies Supabase access tokens before allowing student-specific API
  operations.

## Languages and application frameworks

| Area | Technology | Use |
|---|---|---|
| Frontend | TypeScript, React 19 | Typed interactive user interface |
| Web framework | Next.js 15 | App Router, static generation, frontend hosting and API proxy rewrites |
| Backend | Python 3.11+ | API and retrieval application |
| API framework | FastAPI | JSON, multipart-upload, and streaming HTTP endpoints |
| Request validation | Pydantic 2 and pydantic-settings | API request models and environment configuration |
| ASGI server | Uvicorn | Runs the FastAPI application |

Dependency version ranges are maintained in `frontend/package.json`,
`backend/requirements.txt`, and `backend/requirements-free.txt`.

## Frontend libraries and browser capabilities

| Library / capability | Use |
|---|---|
| `@supabase/supabase-js` | Supabase sessions, email/phone OTP, password sign-in, and password updates |
| `react-markdown` | Render tutor answers written in Markdown |
| `remark-gfm` | GitHub-flavored Markdown, including tables |
| `remark-math` and `rehype-katex` | Parse and display mathematical notation |
| `katex` | Render LaTeX formulas and chemistry notation in the browser |
| `mermaid` | Render generated flowcharts and concept maps |
| Browser `speechSynthesis` | Read tutor answers aloud without a separate TTS service |
| Browser `SpeechRecognition` / `webkitSpeechRecognition` | Optional voice input where supported |
| Web app manifest and service worker | Installable mobile web app (PWA); study APIs still need a network connection |
| Next.js rewrites | Proxy `/api/*` browser requests to the configured backend URL |

No separate avatar, cloud speech, or diagram-generation vendor is currently integrated.
The teacher avatar is implemented in the app, diagrams are rendered with Mermaid, and
speech uses built-in browser APIs.

## Backend libraries

| Library | Use |
|---|---|
| `psycopg` and `psycopg-pool` | PostgreSQL queries and connection pooling |
| `pgvector` | Store and search vector embeddings in PostgreSQL |
| `sentence-transformers` | Optional local semantic embeddings; default model is `BAAI/bge-small-en-v1.5` |
| NumPy | Numerical support for embedding/retrieval operations |
| `openai` | OpenAI-compatible Python client configured with Groq's API endpoint |
| `PyJWT[crypto]` | Verify Supabase-signed access tokens, including asymmetric signing keys |
| `pypdf` | Extract text from PDF textbooks and learner uploads |
| `pypdfium2` and Pillow | Render source PDF pages as images for textbook citations |
| `python-multipart` | Receive PDF/TXT uploads through multipart form requests |

Retrieval is implemented in the project's own modules using PostgreSQL vector search
and full-text search; a separate managed vector database or RAG framework is not used.
The lightweight Render configuration uses keyword embedding mode. The local/full
requirements also include sentence-transformers for semantic embedding mode.

The tutor exposes two bounded model tools in `backend/app/llm.py`: an arithmetic
calculator and an exact integer fraction simplifier that reduces with GCD and checks
equivalence. Math-capable answers are instructed to show their work, validate
probability bounds, and box the final result.

## External APIs and services

### Groq API

- **Purpose:** Generate streamed lessons, explanations, study-chat answers, and quiz
  content.
- **API style:** OpenAI-compatible Chat Completions API.
- **Base URL:** `https://api.groq.com/openai/v1`
- **Configuration:** Backend-only `GROQ_API_KEY` and optional `MODEL` environment
  setting. Do not expose the API key in frontend variables.
- The model ID is configurable. See `backend/app/config.py` and
  `backend/app/llm.py` for the current default and compatibility mapping.

### Supabase Auth API

- **Purpose:** Email/SMS one-time codes and user-ID/password sign-in; persistent auth
  sessions are held by the Supabase client.
- **Frontend library:** `@supabase/supabase-js`.
- **Backend verification:** PyJWT verifies the access-token issuer, audience, expiry,
  and signature. Asymmetric keys are obtained from the Supabase project's JWKS URL;
  legacy HS256 verification can use a backend-only secret.
- **Configuration:** Frontend `NEXT_PUBLIC_SUPABASE_URL` and
  `NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY`; backend `SUPABASE_URL`. For legacy HS256
  projects only, the backend may also use `SUPABASE_JWT_SECRET`.
- Phone OTP requires Supabase phone authentication and an SMS provider to be configured
  in the Supabase project. Email delivery and OTP templates must also be configured.
- The frontend publishable key is intended for browser use. Never use a Supabase
  `service_role` key or JWT signing secret in `NEXT_PUBLIC_*` variables.

### PostgreSQL / pgvector

- **Purpose:** Persist curriculum, authorized course material, vector/text indexes,
  student profiles, progress, messages, quiz attempts, and uploaded document content.
- **Configuration:** Backend-only `DATABASE_URL`; schema is defined in
  `backend/schema.sql`.
- **Local development:** `docker-compose.yml` runs PostgreSQL 16 with pgvector.
- **Deployment options described in the README:** Neon PostgreSQL, Render backend, and
  Vercel frontend. These are configuration/deployment targets, not libraries.

## Backend HTTP API

The FastAPI application is defined in `backend/app/main.py`. OpenAPI documentation is
available at `/docs` when the backend is running. The Next.js browser client calls the
backend through `/api/*` by default.

### General and course catalog

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/health` | Service health check |
| `GET` | `/curriculum` | Chemistry curriculum tree |
| `GET` | `/study/chapters` | Available subject/class chapters |
| `GET` | `/study/topics` | Numbered sections for a selected chapter |
| `GET` | `/study/page-image` | Render an original course-PDF page |

### Authentication-protected learner operations

These routes require `Authorization: Bearer <Supabase access token>`. Student IDs are
resolved to the authenticated account and checked for ownership.

| Method | Path | Purpose |
|---|---|---|
| `POST` | `/auth/session` | Resolve/create the signed-in student's profile and study-library key |
| `GET` | `/students/{student_id}/progress` | Read learning progress |
| `POST` | `/students/{student_id}/status` | Update a topic's learning status |
| `GET` | `/students/{student_id}/documents` | List a student's uploaded materials |
| `POST` | `/students/{student_id}/documents` | Upload and index a PDF/TXT study document |
| `DELETE` | `/students/{student_id}/documents/{document_id}` | Delete an uploaded document |
| `POST` | `/study/chat` | Stream a multi-subject response grounded in course/uploaded material |
| `POST` | `/lesson` | Stream a Chemistry syllabus lesson |
| `POST` | `/ask` | Ask a Chemistry syllabus-topic question |
| `POST` | `/quiz/submit` | Save a student's quiz result |

Document routes also use `X-Study-Library-Key`. Quiz generation is `POST /quiz`. The
current teacher summary route is `GET /teacher/overview`; review its access control
before exposing teacher data on a public deployment.

## Developer and deployment tools

- **npm / npm scripts:** Install frontend packages and run `npm run dev`, `npm run
  build`, or `npm run start` from `frontend/`.
- **pip / Python virtual environment:** Install backend packages and run the FastAPI
  service or backend tests.
- **pytest:** Backend test runner; tests are in `backend/tests/`.
- **Docker Compose:** Starts the local PostgreSQL/pgvector database with
  `docker compose up -d`.
- **Git:** Source control.
- **Optional hosting setup described in `README.md`:** Vercel (Next.js), Render
  (FastAPI), and Neon (PostgreSQL). Production environment variables must be configured
  in the respective service dashboards, not committed to source control.

## Important configuration names

| Variable | Where | Sensitive? |
|---|---|---|
| `NEXT_PUBLIC_SUPABASE_URL` | Frontend | No; public project URL |
| `NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY` | Frontend | Public client key; restrict through Supabase project settings |
| `BACKEND_URL` | Next.js server | No; backend URL |
| `SUPABASE_URL` | Backend | No; project URL |
| `SUPABASE_JWT_SECRET` | Backend only, legacy HS256 projects | **Yes** |
| `DATABASE_URL` | Backend | **Yes** |
| `GROQ_API_KEY` | Backend | **Yes** |
| `MODEL`, `EMBEDDING_MODE`, `EMBED_MODEL`, `EMBED_DIM`, `MAX_DIST`, `CORS_ORIGINS` | Backend | Usually no; operational settings |

The local frontend `.env.local` and backend `.env` files must remain untracked and must
not be copied into documentation, screenshots, logs, or public repositories.
