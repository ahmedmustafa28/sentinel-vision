# Folder Responsibilities

## app/
Application source root for FastAPI services, AI modules, templates, and dashboard logic.

## app/api/
HTTP API layer. Keeps route registration and request-response flow isolated from business logic.

## app/api/routes/
Route modules grouped by domain, such as camera, events, reports, and dashboard endpoints.

## app/core/
Central app configuration, settings loader, constants, and shared middleware wiring.

## app/db/
Database engine/session setup, migration entry points, and repository base utilities.

## app/models/
ORM entities mapped to SQLite tables.

## app/schemas/
Pydantic request/response models used by API and dashboard forms.

## app/services/
Domain services orchestrating YOLO, face recognition, event logging, and report generation.

## app/modules/yolo_detection/
Object detection module boundary. Handles model loading, inference, and detection normalization.

## app/modules/face_recognition/
Face enrollment and matching pipeline with configurable threshold strategy.

## app/modules/ai_report/
Analytics and report generation module (daily/weekly summaries and trend extraction).

## app/dashboard/
Web dashboard composition logic for Jinja2 page rendering and widget aggregation.

## app/templates/
Jinja2 template root for server-rendered UI.

## app/templates/pages/
Page-level templates, such as index, live feed, events, and reports.

## app/templates/components/
Reusable UI fragments such as cards, tables, filter bars, and modal sections.

## app/static/
Frontend static assets.

## app/static/css/
Stylesheets for dashboard UI.

## app/static/js/
Minimal client-side behavior and polling scripts.

## app/static/img/
Icons, logos, and dashboard illustrations.

## data/
Runtime data and generated artifacts.

## data/sqlite/
SQLite database files.

## data/raw/
Input assets and ingestion artifacts, such as known face images and original footage.

## data/processed/
Intermediate AI-processed outputs for debugging and analytics.

## data/models/
Local AI model weights, including YOLO model files.

## data/snapshots/
Captured event frame snapshots associated with event logs.

## data/reports/
Generated PDF/CSV/HTML AI reports.

## data/exports/
Manual export bundles for operations or audit handoff.

## logs/
Application and worker logs.

## logs/events/
Event-focused rolling logs and audit trail text logs.

## scripts/
Operational scripts, such as one-time setup, migration, or cleanup helpers.

## docs/
Architecture and operational documentation.

## tests/
Unit, integration, and API tests.

## deploy/
Deployment artifacts and environment-specific startup configs.
