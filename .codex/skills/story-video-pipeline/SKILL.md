---
name: story-video-pipeline
description: Run or maintain the project-scoped Douyin remake pipeline that turns a source video into summary, rewritten narration, Bailian TTS audio, subtitles, A/B video renders, and final muxed outputs. Use when the user wants to generate, rerun, validate, or compare the full remake workflow.
---

# Story Video Pipeline

Use this skill when the task is about the end-to-end remake workflow driven by [story_video_project.py](/D:/codex/scripts/story_video_project.py).

Read [references/workflow.md](references/workflow.md) when you need the exact stage layout, key artifacts, or rerun patterns.

## Preconditions

Before running the pipeline, verify:
- `config.json` exists
- DashScope/Bailian credentials are available in `config.json` or environment variables
- `ffmpeg` and `ffprobe` are available
- the user understands that live runs call paid external APIs

## Primary Command

Use this as the default live run:

```powershell
python scripts/story_video_project.py --config config.json run `
  --profile-url "<douyin-video-url>" `
  --max-scenes 4
```

## Common Rerun Modes

When only upstream artifacts should be reused:

- Reuse download and STT:

```powershell
python scripts/story_video_project.py --config config.json run `
  --profile-url "<douyin-video-url>" `
  --project-root "<existing-project-root>" `
  --skip-ingest `
  --skip-stt `
  --max-scenes 4
```

- Rebuild only final mux outputs:
  Use the helper functions in `scripts/story_video_project.py` rather than rerunning the whole pipeline.

## Acceptance

Do not declare success until these exist under the project root:
- `03_summary/summary.json`
- `04_rewrite/rewrite.json`
- `05_tts/narration.wav`
- `05_tts/subtitles.srt`
- `06_storyboard/scene_plan.json`
- `09_final/route_a_final.mp4`
- `09_final/route_b_final.mp4`
- `10_compare/report.json`

Also verify:
- subtitles are burned into the final videos, not only muxed as a hidden subtitle track
- subtitle density is acceptable, ideally one short line at a time
- the compare report points to the current final outputs

## Notes

- Route A is `Qwen-Image + FFmpeg`.
- Route B is `Wan i2v`.
- The current pipeline uses one shared TTS narration track for both routes, then muxes subtitles and audio into both final videos.
- If the user asks to improve continuity, inspect `04_rewrite/`, `06_storyboard/`, and the subtitle timing logic before changing downstream FFmpeg settings.
