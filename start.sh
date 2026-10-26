#!/usr/bin/env bash
# Starts database, backend (port 8000) and frontend (port 3000).
set -e
cd "$(dirname "$0")"

docker compose up -d

(cd backend && uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload) &
BACK=$!
trap 'kill $BACK 2>/dev/null' EXIT

cd frontend
npm run dev -- -H 0.0.0.0
