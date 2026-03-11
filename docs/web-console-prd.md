# Web Console PRD

## Goal

Build a product-grade web console for the story video pipeline so operators can:

- configure providers and local paths
- start and rerun projects from the browser
- inspect every pipeline stage
- view generated files without opening the filesystem manually
- understand failures quickly

The console should feel calm, premium, and minimal. The design direction is Apple-like:

- bright surfaces
- restrained depth
- strong spacing
- large typography
- low-noise controls
- motion used sparingly

## Users

### 1. Operator

Runs projects, checks progress, downloads outputs, edits configs.

### 2. Reviewer

Checks continuity files, generated assets, final videos, and compare reports.

### 3. Builder

Maintains provider config, model choices, and system defaults.

## Primary Jobs To Be Done

1. Start a project from a Douyin URL or an existing STT project root.
2. See which stage is running, completed, failed, or skipped.
3. Open files from each stage without leaving the browser.
4. Edit model and pipeline configuration safely.
5. Rerun only the needed stage instead of rerunning the whole flow.

## Product Scope

### V1 Must Have

- Project list
- Project detail page
- Stage status timeline
- File browser for project outputs
- Config editor for `config.json`
- Run actions:
  - full run
  - run from STT
  - rerun final mux
- Live-ish status refresh
- Log viewing

### V1.5 Should Have

- Side-by-side route A / route B preview
- JSON viewers for `summary`, `rewrite`, `scene_plan`, `shot_continuity`
- Inline audio and video preview
- Retry failed stage
- Stage duration and artifact count

### V2 Later

- Multi-user auth
- Queue management
- Cursor subagent delegation from web
- Prompt history diff
- Asset approval workflow

## Information Architecture

### 1. Dashboard

Purpose:

- show system health
- show recent projects
- surface failures

Modules:

- recent runs
- running tasks
- failed stages
- quick actions

### 2. Projects

Purpose:

- browse all remake projects under `runs/projects/`

List columns:

- project slug
- latest run time
- latest status
- last successful final output
- source URL

### 3. Project Detail

Purpose:

- one place to inspect an entire run

Sections:

- hero summary
- stage timeline
- artifacts by stage
- logs
- route comparison
- rerun actions

### 4. Config

Purpose:

- edit `config.json` from structured forms

Sections:

- providers
- models
- ffmpeg and local tools
- output paths
- video defaults
- continuity defaults

### 5. File Explorer

Purpose:

- inspect generated files by stage

Capabilities:

- tree view
- JSON preview
- text preview
- image preview
- audio player
- video player
- download action

## Stage Model

The UI should normalize all pipeline stages into one shared model.

Stages:

1. `01_ingest`
2. `02_stt`
3. `03_summary`
4. `04_rewrite`
5. `05_tts`
6. `06_storyboard`
7. `07_route_a_qwen_ffmpeg`
8. `08_route_b_wan_i2v`
9. `09_final`
10. `10_compare`

Each stage should expose:

- `stage_id`
- `label`
- `status`
- `started_at`
- `ended_at`
- `duration_seconds`
- `artifact_count`
- `primary_files`
- `error_message`
- `log_path`

Allowed status values:

- `pending`
- `running`
- `completed`
- `failed`
- `skipped`

## UX Rules

### Status Clarity

- show one dominant status color per stage
- do not hide failed stages behind tabs
- keep timestamps visible

### File Visibility

- every stage card must show key files first
- JSON files should open in a structured viewer, not raw download only
- final videos should be playable inline

### Safe Configuration

- secrets should be masked by default
- allow explicit reveal
- validate before save
- preserve unknown fields to avoid destructive rewrites

### Rerun Safety

- rerun actions must clearly state scope
- example:
  - rerun from summary
  - rerun route B only
  - rerun final mux only

## Visual Direction

### Layout

- wide centered content
- large whitespace
- floating cards with subtle borders
- sticky top bar

### Typography

- use a refined sans family
- large section headers
- compact monospace for logs and file metadata

### Color

- off-white background
- soft gray panels
- black/near-black text
- one restrained accent color for actions
- semantic stage colors only where needed

### Motion

- soft fade and slide on page load
- no busy dashboards
- status transitions should animate gently

## Success Criteria

- an operator can start a project without using terminal commands
- an operator can identify the failed stage in under 10 seconds
- an operator can open final outputs in 2 clicks or fewer
- an operator can update config without editing JSON manually

## Recommended V1 Tech Direction

- Backend: FastAPI
- Frontend: React + Vite
- UI styling: custom CSS with design tokens, not a heavy admin template
- Data source: direct project directory reads under `runs/projects/`
- Execution model: API starts local subprocesses and stores stage status snapshots

This is the lowest-risk path for the current codebase because the pipeline is already Python-based.
