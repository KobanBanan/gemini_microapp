# Visa Docs Analysis - Backend

FastAPI backend for migrating the Streamlit app to an async, task-driven service.

## Quick start (local, Poetry)

1) Install deps and run:

```
cd visa_docs_analysis/backend
poetry install
poetry run uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

2) Env (local SQLite by default):

```
APP_ENV=dev
DATABASE_URL=sqlite+aiosqlite:///./dev.db
REDIS_URL=redis://localhost:6379/0
GEMINI_API_KEY=
```

3) Health check:

GET http://localhost:8000/api/v1/health → `{ "status": "ok" }`

## Quick start (Docker Compose)

1) Create `.env` for containers:

```
cd visa_docs_analysis
printf 'APP_ENV=dev\nDATABASE_URL=postgresql+asyncpg://dev:dev@postgres:5432/gemini_app\nREDIS_URL=redis://redis:6379/0\nGEMINI_API_KEY=\n' > backend/.env
```

2) Run:

```
docker compose up --build
```

3) API: http://localhost:8000, Docs: http://localhost:8000/api/docs
   - Shared uploads volume mounted at `/app/uploads` for API and worker

## Structure (key files)

```
backend/
  app/
    api/v1/routes_health.py
    api/v1/routes_tasks.py
    api/v1/ws.py
    config.py
    logging.py
    main.py
    db/session.py
    db/migrations/ (alembic)
    models/{base.py,user.py,document.py,task.py,analysis.py}
    schemas/task.py
    services/analysis_service.py
    workers/{celery_app.py,jobs.py}
  Dockerfile
  pyproject.toml
```

## What’s done

- FastAPI app with JSON logging, Pydantic v2 settings
- Async SQLAlchemy session; models: `users`, `documents`, `tasks`, `task_inputs`, `analysis_results`, `oauth_tokens`
- Alembic configured (async URL → sync for migrations); initial migration applied
- REST API:
  - Health: `GET /api/v1/health`
  - Auth (demo JWT + Google OAuth skeleton):
    - `POST /api/v1/auth/token`, `GET /api/v1/auth/me`, `GET /api/v1/auth/login`, `GET /api/v1/auth/callback`, `POST /api/v1/auth/logout`
  - Tasks:
    - `POST /api/v1/tasks/document-inconsistency-check` (JSON: google_drive|upload by path)
    - `POST /api/v1/tasks/document-inconsistency-check-local` (multipart UploadFile)
    - `GET /api/v1/tasks/{id}` (status/result)
  - History:
    - `GET /api/v1/history`, `GET /api/v1/history/analysis/{analysis_id}`
- WebSocket progress: `/api/v1/tasks/{id}/ws` (Redis pubsub)
- Services: document processing (DOCX/PDF/TXT), Google Drive fetch (public + OAuth-ready), Gemini wrapper (tenacity), prompt builder (O1/EB1)
- Celery worker + Redis; analysis pipeline publishes progress and persists results
- Docker Compose: postgres, redis, api, worker (+ healthchecks) + shared `uploads` volume

## Next steps

- Port services from `old_logic`:
  - Document fetching/processing (`services/document_processing.py`, `services/google_docs.py`)
  - Gemini wrapper with tenacity retries and streaming→fallback (`services/gemini.py`)
  - System prompt builder with O1/EB1 knowledge
- Bind tasks to users (`task.created_by`) and auto-select latest `oauth_tokens` for Google Drive private docs; persist refreshed tokens
- Improve WS progress (finer stages, error propagation) and add cancellation API
- Frontend upload + Drive URL form; WS progress viewer; history list/detail
- Tests: unit (services), integration (end-to-end), CI

## Usage snippets

Get token (demo):

```
curl -s -X POST 'http://127.0.0.1:8000/api/v1/auth/token' \
  -H 'Content-Type: application/x-www-form-urlencoded' \
  -d 'username=me@example.com&password=x'
```

Create task from local file (multipart):

```
curl -s -X POST 'http://127.0.0.1:8000/api/v1/tasks/document-inconsistency-check-local' \
  -H "Authorization: Bearer $TOKEN" \
  -F "file=@/absolute/path/file.pdf" -F "use_o1=false" -F "use_eb1=false"
```

Create task by Google Drive URL/ID (public):

```
curl -s -X POST 'http://127.0.0.1:8000/api/v1/tasks/document-inconsistency-check' \
  -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' \
  -d '{"source_type":"google_drive","source_ref":"https://docs.google.com/document/d/FILE_ID/edit"}'
```

Fetch status:

```
curl -s 'http://127.0.0.1:8000/api/v1/tasks/{task_id}'
```

