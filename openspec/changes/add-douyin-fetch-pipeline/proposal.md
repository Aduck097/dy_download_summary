## Why

We need a repeatable way to pull a Douyin user's short videos and convert them into MP3 files for downstream ASR processing. Doing this manually is slow, inconsistent, and hard to scale across users and repeated runs.

## What Changes

- Add a local CLI workflow for downloading videos from a Douyin user profile with user-provided identifiers and cookies.
- Add a batch audio conversion step that extracts MP3 files from downloaded videos with configurable output settings.
- Persist per-run metadata so downstream systems can map videos, audio files, and source information.
- Document the setup and operating constraints for Douyin fetching, including external tool prerequisites.

## Capabilities

### New Capabilities
- `douyin-fetch-pipeline`: Download videos for a target Douyin user and normalize the output into local artifacts for later processing.

### Modified Capabilities

## Impact

- New local scripts and project documentation
- Runtime dependency on external tools: `f2` and `ffmpeg`
- No server-side APIs or deployed services
