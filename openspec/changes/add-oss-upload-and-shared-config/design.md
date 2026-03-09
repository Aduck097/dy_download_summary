## Context

The repository currently has a working local Douyin download and MP3 conversion pipeline plus a separate FunASR client. Bailian FunASR cannot consume local file paths, so the missing production step is a file hosting stage. Alibaba OSS is the natural fit because it can store the generated MP3 and provide either public URLs or signed URLs.

## Goals / Non-Goals

**Goals:**
- Allow local MP3 files to be uploaded to OSS from the same workflow that invokes FunASR.
- Keep configuration in one file so secrets and endpoints are maintained once.
- Preserve CLI override flags so operators can still adjust specific runs without editing the config file.

**Non-Goals:**
- Managing OSS bucket lifecycle, IAM policies, or infrastructure provisioning
- Replacing the existing downloader with direct SDK-based Douyin acquisition
- Building a queue or background worker around transcription tasks

## Decisions

- Use the already installed official `oss2` SDK for Python rather than shelling out to `ossutil`, because it avoids external process coupling and supports signed URL generation directly in code.
- Add an `upload` command to the FunASR client for isolated OSS testing, while also allowing `run` and `submit` to upload local files automatically.
- Consolidate all stage settings into `config.example.json` under sectioned keys: `paths`, `douyin`, `ffmpeg`, `oss`, and `funasr`.
- Preserve backward compatibility where practical by letting the scripts fall back to legacy flat config shapes if the new sections are absent.

## Risks / Trade-offs

- [Risk] Signed URLs may expire before long-running downstream jobs consume them -> Mitigation: make expiration configurable and allow public base URLs for public buckets.
- [Risk] Operators may accidentally commit live secrets in the shared config -> Mitigation: keep example placeholders and document environment-variable alternatives prominently.
- [Trade-off] One config file increases coupling across stages -> Mitigation: isolate stage-specific keys under named sections and keep CLI overrides intact.
- [Trade-off] Local upload inside the FunASR client expands script scope -> Mitigation: also expose upload-only mode for easier debugging and incremental use.
