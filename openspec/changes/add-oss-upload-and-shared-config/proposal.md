## Why

The current workflow stops at local MP3 output, while Bailian FunASR requires network-accessible audio references. We also now have separate config files for different stages, which makes credential management and environment setup harder than it needs to be.

## What Changes

- Add an OSS upload stage so local audio files can be turned into FunASR-compatible URLs.
- Extend the FunASR client to upload local files to OSS before submission and to expose a dedicated upload-only command.
- Consolidate project configuration into a single shared config file used by the downloader, ffmpeg, OSS, and FunASR stages.
- Update documentation to reflect the new end-to-end flow and shared secret management.

## Capabilities

### New Capabilities
- `oss-upload-stage`: Upload local audio files to OSS and generate URLs that downstream ASR tasks can consume.

### Modified Capabilities
- `bailian-funasr-integration`: FunASR submissions now support local file input by uploading to OSS first and using the generated URL.
- `douyin-fetch-pipeline`: The pipeline now reads its configuration from the shared project config instead of a stage-specific flat config.

## Impact

- New shared config structure in `config.example.json`
- Updated Python scripts for Douyin, OSS, and FunASR
- Existing local configs need to be migrated to the new nested structure
