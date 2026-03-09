## Context

The workspace currently contains only OpenSpec metadata. The requested MVP is a local, operator-driven workflow that accepts Douyin user information, downloads that user's videos through an existing downloader, and converts the resulting media files to MP3 for ASR. The unstable part is the Douyin acquisition layer, so the implementation should avoid embedding brittle reverse-engineered requests directly in repository code.

## Goals / Non-Goals

**Goals:**
- Provide a single local command that orchestrates download and conversion steps.
- Keep the implementation lightweight and auditable by using standard-library Python plus external CLI tools.
- Produce deterministic output folders and metadata that downstream ASR jobs can consume.
- Allow operators to pass cookies, output locations, and MP3 settings without editing code.

**Non-Goals:**
- Reimplementing a Douyin crawler in this repository
- Automatic bypass of platform anti-bot controls
- Uploading results to cloud storage or directly invoking ASR services

## Decisions

- Use a Python CLI as the main entry point because the workspace is empty and Python can coordinate subprocesses, files, and JSON metadata with minimal dependency overhead.
- Treat `f2` as the Douyin acquisition dependency rather than building custom HTTP scraping, because downloader maintenance belongs in a dedicated upstream project.
- Treat `ffmpeg` as a required external dependency for audio extraction, and expose MP3 settings through CLI flags.
- Persist a `manifest.json` file for every run so later automation can correlate source URLs, downloaded media, and converted MP3 files.
- Keep download and conversion separate internally, even when exposed as one command, so partial retries remain possible.

## Risks / Trade-offs

- [Risk] `f2` output conventions may vary by version -> Mitigation: allow explicit raw video input directory and detect common media extensions instead of assuming one fixed filename.
- [Risk] Douyin may require valid cookies or change anti-bot behavior -> Mitigation: surface cookie configuration explicitly in docs and fail fast with tool stderr.
- [Trade-off] External CLI dependencies increase setup work -> Mitigation: document prerequisites and keep repository code dependency-light.
- [Trade-off] MP3 conversion without content inspection may extract silent or music-only clips -> Mitigation: preserve original video files and manifest for later filtering.
