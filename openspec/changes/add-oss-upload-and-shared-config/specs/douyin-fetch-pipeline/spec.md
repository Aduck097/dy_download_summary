## ADDED Requirements

### Requirement: Downloader pipeline reads from the shared project config
The system SHALL support the shared project config structure for downloader and ffmpeg settings while preserving equivalent runtime behavior.

#### Scenario: Running the downloader with the new config file
- **WHEN** the operator passes the shared `config.json` file to the Douyin pipeline
- **THEN** the pipeline reads downloader, ffmpeg, and path settings from the nested shared config sections
