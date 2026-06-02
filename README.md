# SentinelCV: Intelligent AI CCTV Surveillance & Event Detection Platform

[![FastAPI](https://img.shields.io/badge/FastAPI-005571?style=flat-square&logo=fastapi)](https://fastapi.tiangolo.com/)
[![Python](https://img.shields.io/badge/Python-3.10%2B-blue?style=flat-square&logo=python)](https://www.python.org/)
[![YOLOv8](https://img.shields.io/badge/YOLOv8-Ultralytics-orange?style=flat-square)](https://github.com/ultralytics/ultralytics)
[![OpenCV](https://img.shields.io/badge/OpenCV-4.x-red?style=flat-square&logo=opencv)](https://opencv.org/)
[![SQLite](https://img.shields.io/badge/SQLite-WAL--Mode-blue?style=flat-square&logo=sqlite)](https://www.sqlite.org/)
[![License](https://img.shields.io/badge/License-MIT-green?style=flat-square)](https://opensource.org/licenses/MIT)

**SentinelCV** is an enterprise-grade, high-performance edge surveillance platform. It leverages advanced Computer Vision (YOLOv8 & `face_recognition`), multi-threaded stream ingestion, and an event-driven rules engine to deliver real-time security monitoring, automated alert dispatches, and deep analytics. 

Structured as a professional, production-ready portfolio project, this application showcases modern software engineering design patterns, thread-safe asynchronous dispatch pipelines, bulletproof SQLite lock prevention, and highly optimized CPU-conscious visual workflows.

---

## 🏗️ System Architecture

The following diagram illustrates SentinelCV's end-to-end data ingestion, processing, and alerting pipelines:

```text
 ┌────────────────────────────────────────────────────────┐
 │                   Camera Stream Ingestion              │
 └───────────────────────────┬────────────────────────────┘
                             │ (rtsp://, webcam, file)
                             ▼
 ┌────────────────────────────────────────────────────────┐
 │           CameraRegistry & Multi-Threaded Managers     │
 │    - Ingest streams continuously in daemon threads     │
 │    - Dynamic FPS rate-limiting & auto-reconnect        │
 └───────────────────────────┬────────────────────────────┘
                             │
                             ▼
 ┌────────────────────────────────────────────────────────┐
 │          SurveillanceProcessor Processing Loop         │
 │  ┌──────────────────────────────────────────────────┐  │
 │  │        1. High-Efficiency Motion Detection       │  │
 │  │           - Compares frame deltas via OpenCV     │  │
 │  │           - Bypasses AI if no motion detected    │  │
 │  └────────────────────────┬─────────────────────────┘  │
 │                           │ (Motion Detected: Yes)
 │                           ▼
 │  ┌──────────────────────────────────────────────────┐  │
 │  │    2. Intensive Neural Inference Pipelines       │  │
 │  │       - YOLOv8 (Person & Asset Tracking)         │  │
 │  │       - Face Recognition (Known vs. Unknown)     │  │
 │  └────────────────────────┬─────────────────────────┘  │
 └───────────────────────────┼────────────────────────────┘
                             │ (Structured Detections)
                             ▼
 ┌────────────────────────────────────────────────────────┐
 │           EventEngine & Alert Dispatch Pipeline        │
 │  - Evaluates rules (intrusion, disappears, unknowns)   │
 │  - Deduplicates events to prevent alert fatigue        │
 │  - Automatically registers events in SQLite DB         │
 └───────────────────────────┬────────────────────────────┘
                             │
                             ▼
 ┌────────────────────────────────────────────────────────┐
 │             Non-Blocking Notification Service          │
 │  - Spawns background worker dispatch threads           │
 │  - Auto-retries SMTP dispatches with backoff (max 3)   │
 │  - Updates histories inside auto-retrying sessions    │
 └───────────────────────────┬────────────────────────────┘
                             │
                             ▼
 ┌────────────────────────────────────────────────────────┐
 │            FastAPI Web Portal & Dashboard UI           │
 │  - Real-time video feeds (MJPEG overlay streaming)     │
 │  - Live AJAX notifications, navbar badge & toasts      │
 │  - Diagnostic root health endpoints (/health)          │
 └────────────────────────────────────────────────────────┘
```

---

## ✨ Key Features

### 🚀 High-Efficiency Visual Workflow (AI Model Bypass)
* **Per-Camera FPS Control**: Throttles processing loops strictly to a target rate (e.g., 10 FPS) per camera stream, preventing high CPU/GPU spikes.
* **OpenCV Motion-Detection Interceptor**: Compares frame deltas before running neural networks. If **no motion** occurs, it completely bypasses YOLO and Face Recognition inferences and skips database event processing. **Saves over 90% in idle CPU overhead.**
* **Isolated Fail-Safes**: All YOLO and Face Recognition blocks are wrapped in safe try/except barriers. A single frame error or invalid camera input will never crash the system.

### 💾 Deadlock-Free SQLite Architecture (`app/db/session.py`)
* **Immediate Locks**: Configures SQLAlchemy connections to execute `BEGIN IMMEDIATE` on every transaction begin. This serializes all SQLite write locks at inception rather than mid-transaction, eliminating multi-threaded deadlocks (`database is locked` / `SQLITE_BUSY`).
* **High-Concurrency WAL Mode**: Activates `PRAGMA journal_mode=WAL` and sets `busy_timeout=30000` (30 seconds) to support concurrent read/write pools.
* **Auto-Retrying Sessions**: Subclasses SQLAlchemy's `Session` as `RetryingSession`. If a lock error does occur, the session automatically catches it, rolls back, and retries the commit up to 3 times using exponential backoff.

### 📧 Non-Blocking Alert Dispatch & Backoff Policies
* **Data-Isolated Workers**: Resolves all lazy-loaded ORM attributes (e.g., `event.timestamp`) in the main thread before launching background alert dispatches. This prevents `DetachedInstanceError` across multi-threaded database states.
* **Asynchronous Threads**: Dispatches SMTP emails inside dedicated background threads, avoiding any lag in the camera frame processing loop.
* **Retry & Backoff**: If SMTP email dispatches fail, the thread automatically retries up to 3 times using exponential backoff (`backoff_base ** attempt`), updates `retry_count` in the database, and marks the notification as `"FAILED"` on exhaustion.

### 📊 Separated Logging & System Diagnostics
* **Structured Logs**: Standardizes console outputs in a strict structured layout: `TIMESTAMP | LOGGER | LEVEL | MESSAGE`.
* **Rotating Log Isolation**: Automatically creates a `/logs` directory and routes outputs into isolated rotating files:
  - `logs/camera.log`: Camera stream capturing and reconnections.
  - `logs/events.log`: Security alerts, database transactions, and SMTP retries.
  - `logs/ai_processing.log`: YOLO inferences, face recognition, and loop sweeps.
  - `logs/api_requests.log`: FastAPI endpoint routers and Uvicorn server logs.
* **Root Health Monitoring (`/health`)**: Audits live system parameters: database availability, camera connection status, YOLO and Face Recognition library loads, and active event engine threads.

---

## 🛠️ Tech Stack

* **Web Framework**: FastAPI (Uvicorn, Starlette)
* **AI & Object Detection**: Ultralytics YOLOv8 (PyTorch)
* **Face Recognition**: dlib-based `face_recognition` library
* **Image Processing**: OpenCV (python-opencv)
* **Database & ORM**: SQLite, SQLAlchemy 2.0
* **Frontend**: HTML5, Vanilla CSS, Tailwind, Bootstrap, Javascript (AJAX Polling)
* **Testing**: Pytest

---

## 📂 Project Directory Structure

```text
.
├── app/
│   ├── api/                  # API and Frontend router endpoints
│   │   └── routes/
│   │       ├── api_notifications.py  # AJAX JSON notifications polling
│   │       ├── health.py             # System /health checks route
│   │       ├── pages.py              # Front-end dashboard and log views
│   │       └── stream.py             # Live MJPEG stream feeds
│   ├── core/
│   │   ├── config.py         # Pydantic Settings configuration loader
│   │   └── logging_config.py # Structured rotating log file routing
│   ├── db/
│   │   ├── init_db.py        # Database creation and startup migrations
│   │   ├── session.py        # SQLite BEGIN IMMEDIATE and RetryingSession
│   │   └── crud_*.py         # CRUD DB operations
│   ├── models/               # SQLAlchemy models (Camera, Event, Notification)
│   ├── modules/
│   │   ├── face_recognition/ # Face recognition inference algorithms
│   │   └── yolo_detection/   # YOLOv8 object detection interfaces
│   ├── services/
│   │   ├── camera_manager.py # Threaded cv2 capture streams
│   │   ├── event_engine.py   # Rule evaluation and deduplication
│   │   └── notification_service.py # Non-blocking email alert dispatches
│   ├── templates/            # Jinja2 HTML templates
│   └── static/               # CSS, JS, and image assets
├── data/                     # Local file databases, snapshots, and weights
│   ├── models/yolo/          # YOLOv8 weights storage (yolov8n.pt)
│   ├── snapshots/            # Event snapshot screenshot storage
│   └── sqlite/               # SQLite CCTV database
├── logs/                     # Isolated structured log files
├── tests/                    # Pytest unit and E2E simulation suites
├── requirements.txt          # Python project dependencies
├── app.py                    # Server startup entry point
└── .gitignore                # Production repository cleanup
```

---

## 🚀 Installation & Setup

### Prerequisites
* **Python 3.10+**
* **CMake** (required for compiling the `dlib` library during `face-recognition` installation)
* A valid webcam (or an RTSP camera stream URL)

### 1. Clone the Repository
```bash
git clone https://github.com/your-username/sentinel-cv-surveillance.git
cd sentinel-cv-surveillance
```

### 2. Configure Environment Settings (`.env`)
Create a `.env` file in the root directory based on `.env.example`:
```env
APP_NAME="SentinelCV AI Surveillance"
APP_ENV=production
APP_HOST=0.0.0.0
APP_PORT=8000
DEBUG=false

# Database Configuration
DB_URL="sqlite:///./data/sqlite/cctv.db"
DB_ECHO=false

# Alert Notification Configurations
ENABLE_EMAIL_ALERTS=true
SMTP_HOST="smtp.gmail.com"
SMTP_PORT=587
SMTP_USER="your-alert-email@gmail.com"
SMTP_PASS="your-app-password"
ALERT_TO_EMAIL="recipient-email@gmail.com"
```

### 3. Build & Install Dependencies
Create a virtual environment and install packages:
```bash
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### 4. Setup Known Faces Directory
Add reference photos of registered personnel to the `known_faces/` directory. Name the images with the person's name (e.g. `jane_doe.jpg`, `ali_sara.png`). On startup, these references are automatically converted into 128-dimensional encodings.

---

## 🖥️ How to Run

### 1. Launch the Application
Run the root startup script:
```bash
python app.py
```
This executes migrations, downloads model weights (if missing), compiles known faces reference models, starts the background `SurveillanceProcessor` thread, and binds the FastAPI server to port `8000`.

### 2. Access the Dashboard
Open your browser and navigate to:
* **Web UI Dashboard**: [http://localhost:8000](http://localhost:8000)
* **Diagnostics Health Check**: [http://localhost:8000/health](http://localhost:8000/health)
* **FastAPI Interactive Docs**: [http://localhost:8000/docs](http://localhost:8000/docs)

---

## 🧪 Automated Testing

We maintain a comprehensive suite of automated tests, covering database CRUD bindings, async alert dispatches, health diagnostics, and end-to-end integration scenario simulations:

```bash
# Run all tests
pytest -v
```

All integration, health, and simulation test cases pass successfully:
```text
tests/test_health.py::test_health_status_independent PASSED
tests/test_health.py::test_health_endpoint_rest PASSED
tests/test_notifications.py::test_notification_model_and_crud PASSED
tests/test_notifications.py::test_notification_service_integration PASSED
tests/test_notifications.py::test_fastapi_endpoints PASSED
tests/test_surveillance_scenario.py::test_surveillance_e2e_scenario PASSED

======================== 6 passed in 20.46s =========================
```

---

## 📡 API Endpoints

| Endpoint | Method | Description |
|---|---|---|
| `/health` | `GET` | Main root system diagnostics monitoring payload |
| `/api/health` | `GET` | Backward-compatible JSON system diagnostics payload |
| `/api/notifications/unread` | `GET` | Polled by AJAX to update navbar badges and toasts |
| `/api/notifications/{id}/read` | `POST` | Marks an alert notification as read |
| `/cameras/add` | `POST` | Registers a new camera stream with restricted area settings |
| `/video_feed/{camera_id}` | `GET` | High-fidelity real-time MJPEG video streaming |

---

## 🔮 Future Enhancements
* **Smarter Intrusion Zones**: Allow drawing polygonal regions of interest (ROI) directly on the web camera view instead of marking the whole camera as restricted.
* **On-Demand LLM Auditing Reports**: Trigger Ollama-based analytical reports summing up historical events.
* **GPU-Accelerated Inference**: Enable PyTorch CUDA optimizations inside the YOLO processing modules.

---

## 📄 License
This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

---

## ✍️ Author
* **Ahmed Mustafa** - *Senior Software Engineer & AI Architect* - [GitHub Profile](https://github.com/ahmedmustafa28)
