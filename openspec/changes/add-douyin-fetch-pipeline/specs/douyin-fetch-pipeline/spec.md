## ADDED Requirements

### Requirement: Operator can fetch a Douyin user's videos
The system SHALL accept a Douyin user identifier input and invoke an external downloader to fetch that user's videos into a run-specific workspace directory.

#### Scenario: Fetching from a user profile URL
- **WHEN** the operator provides a Douyin profile URL and required downloader options
- **THEN** the system creates a local run directory and stores downloaded video files for that user in a predictable location

### Requirement: Operator can convert downloaded videos to normalized MP3 files
The system SHALL batch-convert downloaded video files into MP3 outputs using configurable sample rate, channel count, and bitrate settings.

#### Scenario: Converting fetched media for ASR
- **WHEN** the operator runs the pipeline with conversion enabled
- **THEN** the system emits one MP3 file per successfully processed video file using the requested audio settings

### Requirement: Pipeline records structured run metadata
The system SHALL write a machine-readable manifest that records the input user reference, run timestamp, discovered video files, conversion results, and failures.

#### Scenario: Inspecting a completed run
- **WHEN** the operator opens the manifest for a finished run
- **THEN** they can identify which files were downloaded, which MP3 files were produced, and which items failed

### Requirement: Pipeline surfaces dependency and execution failures
The system SHALL fail with actionable errors when required external tools are unavailable or subprocess steps fail.

#### Scenario: Missing downloader binary
- **WHEN** the configured downloader command is not installed or not executable
- **THEN** the system stops before processing media and reports which dependency is missing
