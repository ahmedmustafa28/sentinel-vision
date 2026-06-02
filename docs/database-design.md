# Database Design (SQLite)

## Design Principles
- Keep schema compact and readable.
- Favor append-only event history for auditability.
- Separate detection events from report snapshots.

## Core Tables

### cameras
Stores configured camera sources.

Fields:
- id (INTEGER, PK)
- name (TEXT, not null)
- source_url (TEXT, not null)
- location (TEXT, nullable)
- is_active (INTEGER, default 1)
- created_at (DATETIME, not null)
- updated_at (DATETIME, not null)

### detection_events
Stores raw detection events from YOLO and face modules.

Fields:
- id (INTEGER, PK)
- camera_id (INTEGER, FK -> cameras.id)
- event_type (TEXT, not null)  -- object_detected, face_matched, unknown_face
- object_label (TEXT, nullable)
- confidence (REAL, nullable)
- face_name (TEXT, nullable)
- face_distance (REAL, nullable)
- snapshot_path (TEXT, nullable)
- metadata_json (TEXT, nullable) -- compact JSON payload
- detected_at (DATETIME, indexed)
- created_at (DATETIME, not null)

### alert_rules
Stores configurable triggers for future alerting.

Fields:
- id (INTEGER, PK)
- name (TEXT, not null)
- event_type (TEXT, not null)
- min_confidence (REAL, nullable)
- is_enabled (INTEGER, default 1)
- created_at (DATETIME, not null)
- updated_at (DATETIME, not null)

### generated_reports
Stores generated AI report artifacts.

Fields:
- id (INTEGER, PK)
- report_type (TEXT, not null) -- daily, weekly, monthly, custom
- period_start (DATETIME, not null)
- period_end (DATETIME, not null)
- summary_json (TEXT, not null)
- file_path (TEXT, nullable)
- created_at (DATETIME, not null)

### known_faces
Stores enrolled identity registry metadata.

Fields:
- id (INTEGER, PK)
- person_name (TEXT, not null)
- reference_image_path (TEXT, not null)
- embedding_vector_path (TEXT, nullable)
- is_active (INTEGER, default 1)
- created_at (DATETIME, not null)
- updated_at (DATETIME, not null)

## Indexing Strategy
- detection_events(detected_at)
- detection_events(camera_id, detected_at)
- detection_events(event_type, detected_at)
- generated_reports(report_type, period_start, period_end)
- known_faces(person_name)

## Retention Strategy
- Keep detection_events for active retention window.
- Periodically archive older rows to CSV in data/exports.
- Keep generated_reports metadata even if files are moved.

## Suggested First Milestone Schema
Implement only cameras, detection_events, known_faces, and generated_reports in phase 1 for fastest delivery.
