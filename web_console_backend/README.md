# Web Console Backend

FastAPI backend scaffold for the story video web console.

## Scope

This backend currently provides:

- health check
- config read and save APIs
- project discovery from `runs/projects/`
- stage normalization for one project run
- placeholder run APIs for future pipeline execution
- MySQL-ready SQLAlchemy model layer

## Quick Start

1. Create a virtual environment.
2. Install dependencies from `requirements.txt`.
3. Copy `.env.example` to `.env` and adjust values.
4. Start the server:

```powershell
uvicorn web_console_backend.app.main:app --reload
```

On this machine, prefer a non-conflicting local port such as `8765` and avoid `--reload` if Windows named-pipe permissions are restricted:

```powershell
D:\codex\.venv-web\Scripts\python.exe -m uvicorn web_console_backend.app.main:app --host 127.0.0.1 --port 8765
```

## Current API

- `GET /api/health`
- `GET /api/config`
- `PUT /api/config`
- `POST /api/config/validate`
- `GET /api/projects`
- `GET /api/projects/{project_id}`
- `GET /api/projects/{project_id}/stages`
- `GET /api/projects/{project_id}/files`
- `POST /api/runs`
- `POST /api/runs/from-stt`
- `POST /api/projects/{project_id}/rerun`

## Notes

- File artifacts remain on disk under `runs/projects/`.
- MySQL is intended for control-plane metadata, not large media assets.
- Run execution endpoints are scaffolded and currently return `501`.
