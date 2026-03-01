# Architecture Overview

## Scope
This document describes the architecture of `MarineGRIB-InReach-Transmitter`, a polling service that:
1. Reads inbound Garmin inReach emails from Gmail.
2. Forwards the request body to Saildocs by email.
3. Waits for a GRIB attachment response.
4. Compresses + base64-encodes the GRIB file.
5. Splits and sends the payload back to the user through Garmin Explore web endpoints.

## High-Level Components

### 1. Orchestrator
- File: `main.py`
- Responsibility: Long-running loop (`while True`) that runs once per minute.
- Flow:
  - Authenticate Gmail API (`gmail_authenticate`).
  - Process new inReach messages (`process_new_inreach_message`).
  - Encode returned GRIB (`encode_saildocs_grib_file`).
  - Send multipart replies to inReach (`send_messages_to_inreach`).

### 2. Email Integration Layer
- File: `src/email_functions.py`
- Responsibilities:
  - Gmail OAuth/token lifecycle.
  - Search inbound messages and de-duplicate previously processed IDs.
  - Parse inReach message body for:
    - Saildocs query payload.
    - Garmin reply URL.
  - Send outbound Gmail messages to Saildocs.
  - Download `.grb` attachment from Saildocs response.
- Key persistent state:
  - `token.pickle` (OAuth token cache).
  - `files/prev_messages.txt` (processed Gmail message IDs).
  - `files/attachments/*.grb` (downloaded GRIB files).

### 3. Saildocs Utilities
- File: `src/saildoc_functions.py`
- Responsibilities:
  - Poll Gmail for Saildocs response mailbox (`query-reply@saildocs.com`) with timeout behavior.
  - Encode GRIB payload:
    - Read binary `.grb`.
    - Compress with `zlib`.
    - Base64 encode to text for transport.

### 4. Garmin inReach Transport
- File: `src/inreach_functions.py`
- Responsibilities:
  - Split encoded payload into fixed-size chunks (`MESSAGE_SPLIT_LENGTH`, default 120 chars).
  - Wrap chunks with protocol markers:
    - `msg {index}/{total}:`
    - payload
    - `end`
  - POST each chunk to Garmin Explore endpoint using URL-derived GUID and configured headers/cookies.

### 5. Configuration
- File: `src/configs.py`
- Responsibility: Central constants for paths, OAuth scopes, service addresses, HTTP headers/cookies, split size, and delay.
- Required user-set values:
  - `GMAIL_ADDRESS`
  - `credentials.json` at expected path

## Runtime Sequence
1. Service starts and authenticates Gmail.
2. Every 60s:
   - Read message IDs from `files/prev_messages.txt`.
   - Query Gmail for inReach sender (`no.reply.inreach@garmin.com`).
   - Compute new IDs = inbox IDs minus processed IDs.
3. For each new inReach request:
   - Parse request text + Garmin reply URL from email body.
   - Send `send <request>` email to `query@saildocs.com`.
   - Poll for response from `query-reply@saildocs.com` (up to ~10 minutes).
   - Download `.grb` attachment.
   - Record processed message ID in `prev_messages.txt`.
4. After processing, `main.py` takes the most recent `(grib_path, reply_url)` returned:
   - Encode/compress file.
   - Split into chunks.
   - Send chunks back to inReach via Garmin endpoint.

## Data and State Model
- External systems:
  - Gmail API (inbound and outbound mail transport).
  - Saildocs email service.
  - Garmin Explore web messaging endpoint.
- Local state:
  - OAuth token (`token.pickle`).
  - Credential file (`credentials.json`).
  - Processed message registry (`files/prev_messages.txt`).
  - Downloaded GRIB artifacts (`files/attachments/`).

## Error Handling Behavior
- `process_new_inreach_message` catches per-message exceptions and still appends message ID to processed list.
- Saildocs timeout or GRIB download failure triggers an error message back to inReach when URL is available.
- Logging is console-print based; no structured logs or alerting pipeline.

## Current Architectural Constraints / Risks
1. Single-process polling worker; no queueing or horizontal concurrency.
2. At-least-once semantics are weak:
   - Message ID can be marked processed even if downstream send fails.
3. Multi-message handling bug risk:
   - `process_new_inreach_message` returns only the last `(grib_path, reply_url)` pair from loop.
   - Earlier new messages in same poll cycle may be requested from Saildocs but not sent back in that same cycle.
4. Tight coupling to Gmail payload shape (`payload.body.data`, header indexing) may break with MIME variations.
5. `send_messages_to_inreach` applies delay after sending all chunks, not between chunk sends.
6. Credentials/secrets are file-based and not abstracted behind environment/secret manager.

## Suggested Evolution Path
1. Replace polling loop with job queue + explicit state machine per request.
2. Persist request lifecycle states (received, requested, grib_ready, sent, failed).
3. Return/send per message inside `process_new_inreach_message` loop (or return a list of jobs).
4. Add structured logging and retry/backoff strategy.
5. Harden Gmail MIME parsing for multipart email bodies.
6. Move sensitive configuration to environment variables or secret storage.

## File Map (Core)
- `main.py`: service loop/orchestrator.
- `src/configs.py`: constants and integration settings.
- `src/email_functions.py`: Gmail auth/search/send/attachment handling.
- `src/saildoc_functions.py`: Saildocs response polling + GRIB encoding.
- `src/inreach_functions.py`: Garmin outbound chunk transport.
- `files/prev_messages.txt`: processed message IDs.
- `files/attachments/`: GRIB attachment storage.
- `InReach_Message_Decoder.ipynb`: client-side decode utility (outside server runtime path).

## Operational Notes
- This service assumes stable API behaviors from Gmail/Saildocs/Garmin endpoints.
- Required Python dependencies are minimal: Gmail client libs, `requests`, and `pandas`.
- Deployment model expected by README: always-on host (example: PythonAnywhere).
