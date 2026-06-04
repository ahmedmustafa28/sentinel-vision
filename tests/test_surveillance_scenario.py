import time
import pytest
import numpy as np
import logging
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from fastapi.testclient import TestClient

from app.models.base import Base
from app.db.crud_camera import create_camera
from app.db.crud_event import list_events
from app.services.event_engine import EventEngine
from app.main import app

# Setup isolated in-memory SQLite for end-to-end integration scenario
TEST_SQLALCHEMY_DATABASE_URL = "sqlite:///:memory:"
engine = create_engine(
    TEST_SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture(scope="function")
def db_session():
    # Construct schema tables
    Base.metadata.create_all(bind=engine)
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()
        Base.metadata.drop_all(bind=engine)


def test_surveillance_e2e_scenario(db_session, monkeypatch):
    """Simulates a complete CCTV operational scenario:

    1. Person enters a restricted camera zone.
    2. Unknown face is identified.
    3. Object (laptop) disappears.
    4. Verify SQLite event logs and notifications persistence.
    5. Verify dashboard REST API updates unread counters correctly.
    """

    # 1. Setup mocks & settings
    class MockSettings:
        enable_email_alerts = True
        smtp_host = "localhost"
        smtp_port = 587
        smtp_user = "user"
        smtp_pass = "pass"
        alert_to_email = "alert@test.com"
        event_dedupe_seconds = 1
        object_disappearance_seconds = 10
        motion_min_changed_pixels = 10
        motion_min_contour_area = 10
        event_snapshot_dir = "./data/snapshots"

    # Patch settings and session maker in both services
    monkeypatch.setattr("app.services.notification_service.get_settings", MockSettings)
    monkeypatch.setattr("app.services.event_engine.get_settings", MockSettings)

    # Force NotificationService to use our TestingSessionLocal without recursion
    def mock_init(self, db_session_factory=None):
        self._logger = logging.getLogger("NotificationService")
        self._settings = MockSettings()
        self._db_session_factory = db_session_factory or TestingSessionLocal

    monkeypatch.setattr(
        "app.services.notification_service.NotificationService.__init__",
        mock_init,
    )

    # Mock SMTP mail sends
    monkeypatch.setattr(
        "app.services.notification_service.NotificationService._send_email_alert",
        lambda self, subject, body: True,
    )

    # 2. Initialize Camera and EventEngine
    camera = create_camera(
        db_session,
        name="Front Lobby Restricted",
        source_url="rtsp://test_source",
        location="Lobby Entrance",
        is_restricted=True,
    )
    db_session.commit()

    event_engine = EventEngine(
        db_session_factory=TestingSessionLocal,
        dedupe_seconds=1,
        face_event_dedupe_seconds=1,
    )

    dummy_frame = np.zeros((200, 200, 3), dtype=np.uint8)

    # --- SIMULATION 1: Person Entry (Restricted Zone Alert) ---
    # Trigger person detection on restricted camera
    event_engine.process_frame(
        camera_id=camera.id,
        frame=dummy_frame,
        detections=[
            {
                "class_name": "person",
                "confidence": 0.95,
                "bounding_box": {"x1": 20, "y1": 20, "x2": 100, "y2": 150},
            }
        ],
    )

    # Verify event stored in SQLite DB
    events_db = list_events(db_session, camera_id=camera.id)
    assert len(events_db) >= 1
    event_types = {e.event_type for e in events_db}
    assert "person_detected" in event_types
    assert "restricted_area_entered" in event_types

    # Wait briefly for notification thread updates
    time.sleep(0.5)

    # --- SIMULATION 2: Unknown Face Detection ---
    # Trigger unknown face detection on camera
    event_engine.process_frame(
        camera_id=camera.id,
        frame=dummy_frame,
        detections=[],
        unknown_person_detected=True,
        recognized_faces=[
            {
                "name": "Unknown",
                "location": {"top": 10, "right": 40, "bottom": 40, "left": 10},
                "distance": 0.7,
            }
        ],
    )

    events_db_after_face = list_events(db_session, camera_id=camera.id)
    assert "unknown_person_detected" in {e.event_type for e in events_db_after_face}

    time.sleep(0.5)

    # --- SIMULATION 3: Object Disappearance ---
    # Step A: Register the laptop as visible in Lobby
    mock_now = time.time()
    monkeypatch.setattr("time.time", lambda: mock_now)

    event_engine.process_frame(
        camera_id=camera.id,
        frame=dummy_frame,
        detections=[{"class_name": "laptop", "confidence": 0.85}],
    )

    # Step B: Fast-forward time past 10 seconds setting and report missing
    monkeypatch.setattr("time.time", lambda: mock_now + 15.0)

    event_engine.process_frame(
        camera_id=camera.id,
        frame=dummy_frame,
        detections=[],
    )

    events_db_after_removal = list_events(db_session, camera_id=camera.id)
    assert "object_disappeared" in {e.event_type for e in events_db_after_removal}

    time.sleep(0.5)

    # --- SIMULATION 4: Dashboard Notification Updates REST API ---
    # Override FastAPI route dependency
    from app.api.routes.api_notifications import get_db_session

    def override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db_session] = override_get_db
    try:
        client = TestClient(app)

        # Poll the unread alerts dashboard API
        response = client.get("/api/notifications/unread")
        assert response.status_code == 200

        data = response.json()
        assert "unread_count" in data
        assert "latest_alerts" in data

        # Verify that unread notifications are populated and correctly mapped
        assert data["unread_count"] > 0
        latest_msgs = [n["message"] for n in data["latest_alerts"]]
        assert any("Restricted area" in msg for msg in latest_msgs)
        assert any("unknown" in msg.lower() for msg in latest_msgs)
        assert any("laptop" in msg.lower() for msg in latest_msgs)
    finally:
        app.dependency_overrides.clear()
