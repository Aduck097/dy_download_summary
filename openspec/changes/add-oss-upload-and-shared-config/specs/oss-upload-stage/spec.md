## ADDED Requirements

### Requirement: Operator can upload local audio files to OSS
The system SHALL accept local audio file paths, upload them to a configured OSS bucket, and record the uploaded object metadata locally.

#### Scenario: Uploading a generated MP3
- **WHEN** the operator runs the upload flow with a valid local MP3 path and OSS credentials
- **THEN** the system stores the file in the configured OSS bucket and writes the uploaded object key and URL to a local artifact

### Requirement: Uploaded files yield URLs usable by downstream ASR
The system SHALL generate either public URLs or signed URLs for uploaded OSS objects so they can be passed to Bailian FunASR.

#### Scenario: Using a private bucket with signed URLs
- **WHEN** the OSS bucket is not exposed publicly
- **THEN** the system generates a signed download URL with a configurable expiration time
