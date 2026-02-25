# OSA Hybrid RAG AI Agent

Production-style hybrid AI agent that combines:
- Retrieval-Augmented Generation (RAG) over Vertex AI RAG corpora
- Structured data analysis with Pandas over CSV/Excel files
- FastAPI backend API for sessioned chat orchestration
- React frontend chat UI

This repository contains all three layers.

## 1) System Overview

### Architecture

```text
React UI (adk-agent-ui)  <----HTTP---->  FastAPI Backend (backend.py / backend_local.py)
                                                |
                                                | ADK Runner + Tools
                                                v
                                    Vertex AI Agent + RAG + GCS persistence
```

### Main capabilities

- RAG corpus operations:
  - list corpora
  - create corpus
  - add documents
  - semantic query
  - delete document/corpus
- Structured data operations:
  - load CSV/Excel from URL
  - inspect schema / rows
  - query dataframes
  - run controlled pandas code
  - compare multiple dataframes
- Session-aware dataframe persistence (in cloud mode) via GCS.

## 2) Repository Layout

```text
osa-rag-ai-agent/
|-- rag_agent/
|   |-- agent.py                    # ADK agent + model + instructions + tool wiring
|   |-- config.py                   # env-driven config for RAG behavior
|   `-- tools/                      # RAG + pandas tool implementations
|-- backend.py                      # Cloud-oriented FastAPI backend (v6.1.0)
|-- backend_local.py                # Local dev backend with SQLite session + /api/upload
|-- agent.yaml                      # ADK deploy entrypoint metadata
|-- requirements.txt                # Backend/python dependencies
|-- adk-agent-ui/
|   |-- src/App.tsx                 # React chat app
|   |-- package.json                # Frontend dependencies/scripts
|   `-- Dockerfile                  # Frontend container build
|-- Dockerfile                      # Backend container build
|-- DEPLOYMENT_GUIDE.md             # GCP deployment walkthrough
`-- start.bat / start.sh            # convenience startup scripts
```

## 3) Runtime Modes

Two backend variants exist:

1. `backend.py` (recommended for cloud parity)
- Uses `InMemorySessionService` + explicit `session_id` in state
- DataFrame artifacts persisted in GCS by tools
- Endpoints:
  - `POST /api/chat`
  - `GET /api/status`
  - `GET /api/session/{session_id}/dataframes`
  - `DELETE /api/session/{session_id}/dataframes`

2. `backend_local.py` (local-only convenience)
- Uses `SqliteSessionService` (`rag_agent/.adk/session.db`)
- Adds `POST /api/upload`
- Useful when you want browser upload flow while testing locally

Important: the current frontend calls `/api/upload`; that endpoint is only in `backend_local.py`.

## 4) Prerequisites

- Python 3.11+ recommended
- Node.js 18+ and npm
- Google Cloud project with Vertex AI enabled
- Auth configured for local execution (`gcloud auth application-default login`)

Optional for deployment:
- Docker
- `gcloud` CLI
- `adk` CLI

## 5) Environment Variables

Create `.env` in repo root (do not commit it):

```env
GOOGLE_CLOUD_PROJECT=your-gcp-project-id
GOOGLE_CLOUD_LOCATION=asia-southeast1
GCS_BUCKET=your-gcs-bucket-name
REASONING_ENGINE_ID=your-reasoning-engine-id
```

Notes:
- `GCS_BUCKET` defaults to `osa-rag-ai-agent-bucket` if omitted in `backend.py`.
- Some tools use `GOOGLE_CLOUD_PROJECT` and `GOOGLE_CLOUD_LOCATION` directly.

## 6) Local Setup

### Backend

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate
# macOS/Linux: source .venv/bin/activate

pip install --upgrade pip
pip install -r requirements.txt
```

Run cloud-parity backend:

```bash
python backend.py
# or
uvicorn backend:app --host 0.0.0.0 --port 8000 --reload
```

Run local-upload backend:

```bash
python backend_local.py
# or
uvicorn backend_local:app --host 0.0.0.0 --port 8000 --reload
```

### Frontend

```bash
cd adk-agent-ui
npm install
npm start
```

Frontend default URL: `http://localhost:3000`

Backend default URL: `http://localhost:8000`

## 7) API Contract

### `POST /api/chat`

Request:

```json
{
  "message": "Summarize sales trend for Q1",
  "session_id": "optional-session-id",
  "user_id": "default-user"
}
```

Response:

```json
{
  "status": "success",
  "response": "...agent text...",
  "session_id": "..."
}
```

### `GET /api/status`

Returns readiness + runtime metadata.

### `GET /api/session/{session_id}/dataframes` (`backend.py`)

Lists session dataframe blobs from GCS for debugging persistence.

### `DELETE /api/session/{session_id}/dataframes` (`backend.py`)

Deletes dataframe blobs for a session.

### `POST /api/upload` (`backend_local.py` only)

Uploads a local file to temp storage and returns path metadata.

## 8) Agent and Tools

Agent definition: `rag_agent/agent.py`

- Model: `gemini-2.5-flash`
- Name: `HybridDataAgent`
- Tool groups:
  - RAG: `list_corpora`, `create_corpus`, `add_data`, `rag_query`, etc.
  - Pandas: `load_dataframe`, `query_dataframe`, `execute_pandas_code`, `compare_dataframes`

Behavior highlights:
- Routes analytical requests to pandas tools.
- Routes narrative/semantic document requests to RAG tools.
- Supports multi-file / multi-dataframe analysis.

## 9) Deployment (GCP)

Detailed guide: see `DEPLOYMENT_GUIDE.md`

High-level order:
1. Deploy ADK agent to Vertex AI Agent Engine.
2. Build/push/deploy backend container to Cloud Run.
3. Build/push/deploy frontend container to Cloud Run.

## 10) Security and GitHub Publishing Checklist

Before pushing this repo public/private:

1. Never commit secrets:
- `.env`
- `.env.*`
- `service-account-key.json`
- any private key/cert files (`*.pem`, `*.p12`, `*.pfx`)

2. Ensure `.gitignore` includes secret and local artifacts.

3. If a credential was ever committed, rotate it immediately (service account keys, API keys, tokens).

4. Prefer Google Secret Manager or environment variables injected at deploy time.

5. Review staged files before commit:

```bash
git status
git diff --cached
```

## 11) Known Gaps / Notes

- `adk-agent-ui/src/App.tsx` currently hardcodes a production backend URL and calls `/api/upload`.
- If you run `backend.py` locally, upload calls from UI will fail unless you switch frontend to a backend that exposes `/api/upload` or add that endpoint.
- `start.bat` uses `python backend.py`; `start.sh` uses `uvicorn backend:app --reload`.

## 12) Quick Start (Minimal)

```bash
# terminal 1
python backend.py

# terminal 2
cd adk-agent-ui
npm install
npm start
```

Open `http://localhost:3000` and send a chat message.

---

If you want, I can also generate:
- `README_LOCAL.md` (local dev only)
- `README_DEPLOY.md` (production deployment only)
- `.env.example` and a hardened `.gitignore` in the same pass.
