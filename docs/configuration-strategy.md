# Configuration Strategy

## Goals
- Keep setup simple for rapid development.
- Keep runtime behavior explicit and environment-driven.
- Avoid hardcoded paths and thresholds.

## Approach
- Use a single settings object (Pydantic Settings) in app/core.
- Load precedence:
  1. Environment variables
  2. .env file
  3. Safe defaults in settings class
- Keep all tunable AI thresholds and paths in configuration.

## Environment Profiles
- development: local camera testing, verbose logs, SQLite.
- staging: near-production behavior, stricter logging, fixed model versions.
- production: hardened secrets, controlled logging retention, monitored health checks.

## Config Domains
- App: host, port, debug, app metadata.
- Security: secret key, token expiry, optional auth toggles.
- Database: DB URL, echo mode.
- Video: camera source, frame size, sampling rate.
- YOLO: model path, confidence threshold, IoU threshold.
- Face Recognition: model type, matching tolerance, face image directories.
- Event Logging: retention days, snapshot location, log level.
- Reporting: output path, schedule cron, report options.
- Dashboard: refresh interval, pagination defaults.

## Validation Rules
- Validate numerical bounds (for example confidence between 0 and 1).
- Validate path existence on startup where required.
- Fail fast at startup if critical config is missing.

## Secrets Handling
- Keep secrets out of source control.
- Commit only .env.example.
- For production, inject secrets via environment or secret manager.

## Recommended Minimal Runtime Config Set
- DB_URL
- YOLO_MODEL_PATH
- DEFAULT_CAMERA_SOURCE
- KNOWN_FACES_DIR
- EVENT_SNAPSHOT_DIR
- REPORT_OUTPUT_DIR
