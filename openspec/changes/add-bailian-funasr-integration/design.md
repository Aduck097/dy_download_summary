## Context

The repository already downloads Douyin media and converts it to local MP3 files, but Bailian FunASR does not accept direct local file uploads. The official REST API requires one or more public file URLs, uses bearer-token authentication, and completes asynchronously through a submit-and-poll workflow.

## Goals / Non-Goals

**Goals:**
- Provide a minimal local CLI that matches the official Bailian FunASR REST API shape.
- Keep API credentials out of source files through config placeholders and environment variable fallback.
- Save raw API payloads and parsed text output for downstream summarization steps.
- Make the public-URL constraint explicit in code and docs so operators do not assume local MP3 paths can be submitted directly.

**Non-Goals:**
- Uploading local MP3 files to OSS or any other storage provider
- Invoking FunASR directly from a frontend
- Abstracting every Bailian model feature into first-class CLI flags

## Decisions

- Use the Python standard library (`urllib`) instead of extra HTTP dependencies to keep the workspace lightweight.
- Support three CLI stages: submit, status, and run, where `run` submits a task and polls until completion.
- Store the full task response and downloaded transcription JSON locally so the integration remains inspectable when results differ from expectations.
- Use config JSON plus environment variables for secrets, defaulting to `BAILIAN_API_KEY` or `DASHSCOPE_API_KEY`.
- Keep `file_urls` operator-provided. The existing downloader pipeline remains separate because converting a local MP3 into a public URL is an infrastructure decision outside this repository.

## Risks / Trade-offs

- [Risk] Operators may expect local MP3 paths to work with Bailian -> Mitigation: validate URLs and document the public-access requirement prominently.
- [Risk] Task success does not guarantee every subtask succeeded -> Mitigation: persist raw task results and inspect `subtask_status` per file.
- [Trade-off] No built-in upload step means one more manual or external step before ASR -> Mitigation: keep the client focused and compatible with any URL source, including OSS.
- [Trade-off] Standard-library HTTP code is less ergonomic than a third-party client -> Mitigation: scope the client to the documented API surface only.
