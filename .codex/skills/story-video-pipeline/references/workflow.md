# Workflow

## Scope

The pipeline is implemented in [story_video_project.py](/D:/codex/scripts/story_video_project.py).

It orchestrates:
- Douyin ingest
- FunASR transcription
- summary generation
- rewritten oral narration
- Bailian TTS
- subtitle generation
- director storyboard
- route A render
- route B render
- final mux
- route comparison

## Project Layout

Each run writes under:

`runs/projects/<project-slug>/<timestamp>/`

Expected directories:
- `01_ingest/`
- `02_stt/`
- `03_summary/`
- `04_rewrite/`
- `05_tts/`
- `06_storyboard/`
- `07_route_a_qwen_ffmpeg/`
- `08_route_b_wan_i2v/`
- `09_final/`
- `10_compare/`

## High-Value Files

- `03_summary/summary.json`
- `04_rewrite/rewrite.json`
- `05_tts/tts_manifest.json`
- `05_tts/subtitles.srt`
- `06_storyboard/scene_plan.json`
- `09_final/final_manifest.json`
- `10_compare/report.json`

## Practical Rerun Strategy

- If Douyin download or STT is already good, rerun with `--skip-ingest --skip-stt`.
- If only subtitles or burn-in changed, avoid redoing model calls; rebuild `subtitles.srt` and final mux outputs only.
- If continuity is weak, prefer changing summary/rewrite/storyboard prompts before touching render settings.
