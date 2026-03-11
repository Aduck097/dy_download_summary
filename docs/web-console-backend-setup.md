# Web Console Backend Setup

## What Was Added

The repository now includes a backend scaffold under [web_console_backend](/D:/codex/web_console_backend).

It is designed to sit in front of the existing filesystem-driven pipeline:

- `runs/projects/...` stays the artifact store
- `config.json` stays the local pipeline config
- MySQL is reserved for control-plane metadata

## Current Backend Capabilities

- health endpoint
- config read and save
- project list discovery
- project detail view
- stage normalization
- artifact file listing

## What Is Stubbed

- actual run execution from web
- rerun actions
- log streaming
- MySQL persistence wiring beyond the model layer

## Suggested Next Steps

1. Add Alembic migration setup
2. Add a `run_status.json` writer in the pipeline runner
3. Implement subprocess-based run execution APIs
4. Build the React frontend shell against these APIs
