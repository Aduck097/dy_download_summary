## ADDED Requirements

### Requirement: FunASR client accepts local file input through OSS staging
The system SHALL allow operators to pass local file paths to the FunASR client, upload those files to OSS, and submit the resulting URLs to Bailian FunASR.

#### Scenario: Running transcription from a local MP3
- **WHEN** the operator provides `--local-file` to the FunASR client
- **THEN** the system uploads the local file to OSS and uses the resulting URL in the submitted transcription task

### Requirement: FunASR client stores upload metadata alongside task artifacts
The system SHALL persist local-to-OSS upload mappings in the same output directory as task artifacts for traceability.

#### Scenario: Inspecting a completed transcription run
- **WHEN** the operator opens the output directory from a FunASR run that uploaded local files
- **THEN** they can identify which local file became which OSS object and URL
