## Why

We need a supported speech-to-text step after local MP3 generation, and Bailian FunASR is the chosen ASR backend. Without an integration layer and secret configuration contract, operators have to handcraft requests and cannot reliably move from downloaded media to transcription output.

## What Changes

- Add a local CLI client for Bailian FunASR recorded-file transcription using the official asynchronous REST API.
- Add a dedicated example configuration file that separates API credentials and request parameters from code.
- Persist submitted task metadata, polled task status, and downloaded transcription results to local output files.
- Document the public-URL requirement and how it fits with the existing local MP3 pipeline.

## Capabilities

### New Capabilities
- `bailian-funasr-integration`: Submit audio URLs to Bailian FunASR, poll task status, and store transcription artifacts locally.

### Modified Capabilities

## Impact

- New local script and config example for FunASR
- Updated project documentation
- Runtime dependency on a valid Bailian API key or temporary auth token
