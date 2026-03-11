# Web Console Architecture

## Chosen Direction

Use a split architecture:

- `FastAPI` backend for project discovery, config IO, file metadata, and pipeline execution
- `React + Vite` frontend for the product UI

Reason:

- existing pipeline is Python
- subprocess orchestration belongs in Python
- frontend can stay clean and product-oriented

## System Boundaries

### Backend Responsibilities

- scan `runs/projects/`
- normalize stage status
- expose project and file APIs
- start pipeline subprocesses
- capture stdout and stderr
- read and write `config.json`
- provide signed-safe local file access routes

### Frontend Responsibilities

- dashboard and navigation
- forms and validation UX
- stage timeline
- artifact preview
- run controls
- config editor

## Backend Modules

### `web/api/projects.py`

Endpoints:

- `GET /api/projects`
- `GET /api/projects/{project_id}`
- `GET /api/projects/{project_id}/stages`
- `GET /api/projects/{project_id}/files`
- `GET /api/projects/{project_id}/artifacts/{stage_id}`

### `web/api/runs.py`

Endpoints:

- `POST /api/runs`
- `POST /api/runs/from-stt`
- `POST /api/projects/{project_id}/rerun`
- `GET /api/runs/{run_id}/status`
- `GET /api/runs/{run_id}/logs`

### `web/api/config.py`

Endpoints:

- `GET /api/config`
- `PUT /api/config`
- `POST /api/config/validate`

### `web/services/project_index.py`

Purpose:

- map filesystem runs into API view models

### `web/services/pipeline_runner.py`

Purpose:

- spawn subprocesses
- track running jobs
- write status snapshots

### `web/services/file_preview.py`

Purpose:

- detect preview type by extension
- support json/text/image/audio/video

## Persistent State

The source of truth remains the filesystem.

Add one small control layer:

- `runs/projects/<slug>/<run>/run_status.json`

This file should be owned by the web runner and updated as stages progress.

Suggested shape:

```json
{
  "project_slug": "douyin-7614714151727189617",
  "run_root": "runs/projects/douyin-7614714151727189617/20260310-114436",
  "source_url": "https://www.douyin.com/video/7614714151727189617",
  "status": "running",
  "current_stage": "05_tts",
  "stages": [
    {
      "stage_id": "03_summary",
      "status": "completed",
      "started_at": "2026-03-11T10:00:00",
      "ended_at": "2026-03-11T10:00:16",
      "primary_files": ["03_summary/summary.json"],
      "error_message": ""
    }
  ]
}
```

## Frontend Routes

- `/`
- `/projects`
- `/projects/:projectId`
- `/config`

## Project Detail Screen

### Header

- project slug
- source url
- latest status
- latest updated time

### Stage Rail

- vertical stage list on desktop
- horizontal chips on smaller screens

### Main Panels

- stage overview
- primary artifacts
- logs
- compare result

### Preview Drawer

- opens selected file inline

## Config Screen Structure

### Provider Cards

- FunASR
- Qwen Text
- Qwen Image
- Wan Video
- TTS

### Fields

- endpoint
- model
- api key
- timeouts
- output defaults

### Save Behavior

- optimistic disabled until valid
- diff summary before commit

## Execution Actions

### Full Run

Command target:

- `story_video_project_v2.py run`

### Start From STT

Command target:

- `story_video_project_v2.py run --skip-ingest --skip-stt --project-root <existing>`

### Rerun Final

Preferred future target:

- dedicated command for final-only rebuild

If that command does not exist yet, backend should not fake it.

## Product Risks

### 1. File Locking On Windows

The current workspace already showed locked script behavior.

Mitigation:

- web runner should not overwrite active source files
- logs and status files should be append-friendly

### 2. Long-Running Jobs

Generation jobs can run for many minutes.

Mitigation:

- detach subprocesses from request lifecycle
- poll status from the frontend

### 3. Secret Exposure

Config includes provider keys.

Mitigation:

- mask secrets in read APIs
- accept partial updates
- store raw values only server-side

## Recommended Implementation Order

1. Backend read-only APIs for projects, stages, files, config
2. Frontend shell with dashboard, project list, project detail, config
3. Run start endpoints
4. Live status updates
5. Rerun and log streaming
