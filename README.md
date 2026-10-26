# Chemistry Teaching Assistant (RAG + talking teacher)

A tutor for Class XI-XII Chemistry. The teacher (Dr. Asha) explains topics, answers
doubts from your course material with page citations, speaks answers aloud through an
animated avatar, and tracks each student's progress.

```
backend/   FastAPI + Postgres/pgvector + Claude  (RAG, lessons, quizzes, progress)
frontend/  Next.js chat UI + avatar + speech in/out + KaTeX/mhchem rendering
```

## 1. Start the database
```bash
docker compose up -d
```

## 2. Backend
```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env        # put your ANTHROPIC_API_KEY in it
uvicorn app.main:app --reload --port 8000
```
On start-up it creates the tables and seeds the syllabus tree (Class XI units 1-14,
Class XII units 1-16) from `app/curriculum.py`.

## 3. Add teaching material (required, the syllabus alone is only an outline)
Use textbooks or notes you have the right to use (e.g. your own notes, or the NCERT
chapters you are licensed to use). Put PDFs/markdown in `backend/data/` and run:
```bash
python -m app.ingest data/xi_ch1.pdf --grade XI --unit 1
python -m app.ingest data/xii_ch3.pdf --grade XII --unit 3
```
Chunks are tagged with grade, unit, page and the closest topic automatically.
Scanned PDFs need OCR first.

## 4. Frontend
```bash
cd frontend
cp .env.local.example .env.local
npm install
npm run dev          # http://localhost:3000
```
Use Chrome or Edge for voice input.

## How it works
- **Lesson mode**: "Teach me this" retrieves chunks for the topic, then streams a short
  lesson (hook, explanation, worked example, check question).
- **Doubt mode**: questions retrieve from the current unit first, then widen to the
  whole class. Chunks that are too far from the question are dropped, so the tutor
  says "the material doesn't cover this" instead of guessing.
- **Numericals**: the model has a calculator tool, so arithmetic is computed, not guessed.
- **Chemistry rendering**: equations with `$\ce{...}$` (mhchem) and LaTeX via KaTeX.
- **Progress**: quiz scores update mastery (0-1) and a spaced-repetition due date;
  doubts per topic are counted. `GET /teacher/overview` lists the topics with the
  most doubts and lowest mastery.

## Upgrading the avatar
`frontend/components/Avatar.tsx` is an SVG placeholder whose mouth moves while the
browser voice speaks. Keep its props (`speaking`, `listening`) and swap the inside for
either a hosted streaming avatar (HeyGen, D-ID, Simli, Tavus) or a three.js VRM model
lip-synced from visemes returned by a cloud TTS (Azure, ElevenLabs, Cartesia).
`frontend/lib/speech.ts` is where to replace browser TTS with that service.

## Run from GitHub (Codespaces)
1. Push this folder to a GitHub repo (keep it private if it will hold your keys' context or notes).
2. On the repo page: **Code → Codespaces → Create codespace on main**.
3. Add your key once: GitHub **Settings → Codespaces → Secrets → New secret**, name
   `ANTHROPIC_API_KEY`, and give it access to this repo (the first launch also prompts for it).
4. Wait for setup to finish (installs dependencies and starts the database).
5. Upload a chapter into `backend/data/` (drag into the Explorer), then in the terminal:
   ```bash
   cd backend && python -m app.ingest data/chapter1.pdf --grade XI --unit 1 && cd ..
   ./start.sh
   ```
6. Open the forwarded port **3000** from the Ports tab.

Textbooks in `backend/data/` are git-ignored on purpose, so copyrighted material is not pushed.
The frontend reaches the backend through its own `/api` proxy, so only port 3000 is needed.
`./start.sh` also works locally on Mac/Linux/WSL.

## Not built yet
- Login / separate teacher accounts and a teacher dashboard UI (the API endpoint exists)
- Practicals and virtual-lab content
- Molecule drawing (RDKit from SMILES)
- Automated tests
