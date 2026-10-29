# Multi-Subject Teaching Assistant (RAG + talking teacher)

A tutor for Class XI-XII Maths, Physics, Chemistry, and Biology. DIVA explains topics,
answers questions using uploaded study materials with page citations, prepares revision
summaries and NEET/JEE-style practice, speaks answers aloud, and tracks Chemistry progress.

```
backend/   FastAPI + Postgres/pgvector + Groq    (RAG, lessons, quizzes, progress)
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
cp .env.example .env        # put your GROQ_API_KEY in it
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

### Shared Maths, Physics, Chemistry, and Biology materials
Place authorized NCERT-style PDFs in subject folders under `backend/data/`, then run
from `backend/`:
```bash
python -m app.ingest_shared data
```
The batch importer identifies subject and class from standard filenames such as
`kemh101.pdf` (Maths XI) or `lebo101.pdf` (Biology XII), skips exact duplicate files,
and reports unclassified filenames instead of guessing. It indexes extracted text in
the shared course library, which DIVA searches for every learner's lessons and chats.
Data files remain Git-ignored and must not be committed. To load shared content into
production, configure the production `DATABASE_URL` in the local `backend/.env` file
and set `EMBEDDING_MODE=keyword` to match Render before running the command. Do not
share the database URL in chat or commit it.

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
- **Visual explanations**: lessons and relevant doubts can include inline Mermaid
  flowcharts or concept maps; diagram code is rendered visually and not read aloud.
- **Progress**: quiz scores update mastery (0-1) and a spaced-repetition due date;
  doubts per topic are counted. `GET /teacher/overview` lists the topics with the
  most doubts and lowest mastery.

## Upgrading the avatar
`frontend/components/Avatar.tsx` is an SVG placeholder whose mouth moves while the
browser voice speaks. Keep its props (`speaking`, `listening`) and swap the inside for
either a hosted streaming avatar (HeyGen, D-ID, Simli, Tavus) or a three.js VRM model
lip-synced from visemes returned by a cloud TTS (Azure, ElevenLabs, Cartesia).
`frontend/lib/speech.ts` is where to replace browser TTS with that service.

## Mobile web app and Google Play
The mobile teacher is available at `/mobile`. The frontend includes a web app manifest,
app icons, and a service worker so it can be installed from a supported mobile browser.
The offline cache only saves the mobile page and its Next.js static assets; lessons,
chat, quizzes, and progress still need an internet connection and the backend.

The mobile app provides separate Maths, Physics, Chemistry, and Biology tutors for
Classes XI-XII. Learners can upload text-based PDFs or UTF-8 TXT notes; the backend
extracts and indexes their text for subject-specific chat and summaries. Uploaded
materials stay in the database until deleted from the app. A random key stored in the
browser keeps each study library separate; clearing this browser's site data also clears
the key needed to access that library. Scanned PDFs require OCR before upload. The
upload limit is 12 MB, 100 PDF pages, and 300,000 extracted characters.

Learners can select a Chemistry syllabus topic or enter a chapter/topic for Maths,
Physics, or Biology, then start a short lesson or a one-question understanding check.
DIVA waits for the learner's response and gives feedback in the conversation. The
non-Chemistry subjects use the selected topic and uploaded notes as context; they do not
yet have built-in chapter lists, so learners can type the chapter name or upload their
syllabus/notes.

The tutor uses Groq's Llama 3.3 70B model by default (`MODEL` can override it). NEET/JEE
buttons create clearly labeled practice questions, not claims about exact questions
asked in past exams. For answers to an actual past question, upload the paper first so
the tutor can cite its text. The app does not ship with a verified previous-year
question bank.

### Make it public on Render
The root `render.yaml` defines the FastAPI backend with lightweight keyword retrieval.
Host the Next.js frontend on Vercel's Hobby plan and use Neon Free for PostgreSQL.
This keeps only one service on Render's free compute quota. To create a prototype:
1. Push the project to a GitHub repository that your Render account can access. The
   Render Blueprint must be at the repository root.
2. In Render, choose **New → Blueprint**, connect the repository, and review the
   backend before applying the Blueprint. Create a free PostgreSQL project at
   [Neon](https://neon.tech/) and copy its pooled connection string.
3. During Render Blueprint setup, provide `DATABASE_URL` and `GROQ_API_KEY` as secret
   environment variables. Do not put either value in this file, in `NEXT_PUBLIC_*`, or
   in GitHub.
4. Import the same GitHub repository into [Vercel](https://vercel.com/), set the
   project root to `frontend`, and add `BACKEND_URL` as a server-side environment
   variable with the Render backend's public HTTPS URL. Deploy the site; its Vercel
   URL is the link to share, with `/mobile` at the end.
5. Ingest licensed teaching material into Neon. From `backend/`, install
   `requirements-free.txt`, set `EMBEDDING_MODE=keyword` and `DATABASE_URL` to the same
   Neon connection string, then run `python -m app.ingest <file> --grade XI --unit 1`.
6. Test `<vercel-url>/mobile`, curriculum, lessons, and quizzes.

This is a hobby prototype, not a production hosting guarantee. Render's free backend
sleeps after inactivity and can take about a minute to wake. Render's free plan has
monthly usage limits, and Neon Free has usage limits too. Keyword retrieval is less
semantically capable than the default sentence-transformer mode. The app allows
anonymous students and has no request throttling, so monitor Groq usage and add abuse
protections before widely sharing it. Student progress and conversation history are
stored in the database; publish an appropriate privacy notice.

To publish the same experience on the web and Google Play:
1. Deploy the frontend and backend to production, using a stable HTTPS domain such as
   `https://tutor.example.com`. Set the frontend's `BACKEND_URL` to the public backend
   URL and configure production secrets on the server. Never put `GROQ_API_KEY` in
   frontend variables or source control.
2. Verify `https://tutor.example.com/mobile` and
   `https://tutor.example.com/manifest.webmanifest` work over HTTPS. On Android Chrome,
   open `/mobile` and use **Install app** or **Add to Home screen** to test the PWA.
3. Install Java and the Android SDK, then install Bubblewrap:
   ```bash
   npm install --global @bubblewrap/cli
   bubblewrap init --manifest=https://tutor.example.com/manifest.webmanifest
   ```
   Choose a permanent Android application ID (for example `com.yourcompany.chemtutor`)
   and create/secure the Android signing key. Keep the application ID and signing key
   safe; Play Store updates must use the same ID and signing identity.
4. Build the Android Trusted Web Activity (TWA) bundle with Bubblewrap:
   ```bash
   bubblewrap build
   ```
   Follow Bubblewrap's output for the generated Android project and signed Android App
   Bundle (`.aab`).
5. Publish the Digital Asset Links JSON generated for the final Android package and
   signing certificate at
   `https://tutor.example.com/.well-known/assetlinks.json`. Verify the file is publicly
   reachable before testing the Android app; without this verification, Android may
   show browser controls instead of opening the trusted full-screen app.
6. Create the app in Google Play Console, upload the `.aab` to an internal test track,
   test it on Android, and complete the Play listing, content rating, privacy policy,
   data safety, and current Play Console requirements before requesting release.

The final TWA configuration cannot be generated until the production HTTPS domain and
permanent Android application ID are chosen. Use a domain you control: the Play Store
app is a full-screen window onto that website, and the website must remain available.

## Run from GitHub (Codespaces)
1. Push this folder to a GitHub repo (keep it private if it will hold your keys' context or notes).
2. On the repo page: **Code → Codespaces → Create codespace on main**.
3. Add your key once: GitHub **Settings → Codespaces → Secrets → New secret**, name
   `GROQ_API_KEY`, and give it access to this repo.
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
