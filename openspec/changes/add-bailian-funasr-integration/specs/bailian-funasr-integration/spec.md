## ADDED Requirements

### Requirement: Operator can submit FunASR transcription tasks with configurable authentication
The system SHALL accept one or more public audio file URLs and submit them to Bailian FunASR using a configurable bearer credential supplied by config or environment variables.

#### Scenario: Submitting a transcription job
- **WHEN** the operator runs the FunASR client with a valid API key and file URL
- **THEN** the system sends an asynchronous transcription request and records the returned task ID locally

### Requirement: Operator can poll task status and inspect subtask outcomes
The system SHALL query Bailian task status until completion or timeout and preserve task output details, including per-file subtask results.

#### Scenario: Checking a completed task
- **WHEN** the operator polls a submitted task
- **THEN** the system stores the task status payload and exposes whether each file succeeded or failed

### Requirement: Operator can download transcription result artifacts
The system SHALL download available transcription result JSON files from the returned `transcription_url` links and derive plain text output for successful subtasks.

#### Scenario: Saving transcription text locally
- **WHEN** a subtask succeeds and returns a transcription result URL
- **THEN** the system downloads the JSON result and writes a plain-text transcript file for local use

### Requirement: Integration rejects unsupported local-path input for submission
The system SHALL require HTTP, HTTPS, or REST-supported OSS-style file references for submission and explain that local file paths are not accepted by Bailian FunASR.

#### Scenario: Passing a local MP3 path
- **WHEN** the operator provides a filesystem path instead of a supported URL
- **THEN** the system stops before calling Bailian and reports that a public file URL is required
