import pytest
import time
from datetime import datetime, timezone
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models.base import Base
from app.models.camera import Camera
from app.models.event import Event
from app.models.notification import Notification
from app.db.crud_camera import create_camera
from app.db.crud_event import create_event
from app.db.crud_notification import create_notification
from app.services.alert_throttle import AlertThrottle
from app.services.notification_service import NotificationService

from sqlalchemy.pool import StaticPool
TEST_SQLALCHEMY_DATABASE_URL = "sqlite:///:memory:"
engine = create_engine(
    TEST_SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture(scope="function")
def db_session():
    Base.metadata.create_all(bind=engine)
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()
        Base.metadata.drop_all(bind=engine)


@pytest.fixture(autouse=True)
def clean_throttle():
    # Stop background threads and clean the AlertThrottle singleton before and after each test
    throttle = AlertThrottle()
    throttle.stop()
    yield
    throttle = AlertThrottle()
    throttle.stop()


def test_alert_throttle_cooldown(db_session, monkeypatch):
    # Mock settings with 1 second cooldown, digest disabled
    class MockSettings:
        enable_email_alerts = True
        smtp_host = "localhost"
        smtp_port = 587
        smtp_user = "user"
        smtp_pass = "pass"
        alert_to_email = "alert@test.com"
        alert_cooldown_seconds = 1
        alert_digest_minutes = 0

    monkeypatch.setattr("app.services.alert_throttle.get_settings", lambda: MockSettings())
    monkeypatch.setattr("app.services.notification_service.get_settings", lambda: MockSettings())

    camera = create_camera(db_session, name="Test Cam", source_url="0", location="Lobby")
    
    throttle = AlertThrottle()
    
    # First alert should fire immediately
    fired1 = throttle.should_fire(
        camera_id=camera.id,
        camera_name=camera.name,
        event_type="unknown_person_detected",
        notification_id=1,
        event_time=datetime.now(timezone.utc)
    )
    assert fired1 is True

    # Second alert immediately after should be suppressed
    fired2 = throttle.should_fire(
        camera_id=camera.id,
        camera_name=camera.name,
        event_type="unknown_person_detected",
        notification_id=2,
        event_time=datetime.now(timezone.utc)
    )
    assert fired2 is False

    # Sleep to exceed the 1-second cooldown
    time.sleep(1.1)

    # Third alert after cooldown should fire
    fired3 = throttle.should_fire(
        camera_id=camera.id,
        camera_name=camera.name,
        event_type="unknown_person_detected",
        notification_id=3,
        event_time=datetime.now(timezone.utc)
    )
    assert fired3 is True


def test_alert_throttle_independent_keys(db_session, monkeypatch):
    # Mock settings with 10 second cooldown, digest disabled
    class MockSettings:
        enable_email_alerts = True
        smtp_host = "localhost"
        smtp_port = 587
        smtp_user = "user"
        smtp_pass = "pass"
        alert_to_email = "alert@test.com"
        alert_cooldown_seconds = 10
        alert_digest_minutes = 0

    monkeypatch.setattr("app.services.alert_throttle.get_settings", lambda: MockSettings())

    throttle = AlertThrottle()

    # Camera 1, Type A fires
    assert throttle.should_fire(
        camera_id=1, camera_name="Cam1", event_type="type_a", notification_id=1, event_time=datetime.now(timezone.utc)
    ) is True

    # Camera 1, Type A suppressed (cooldown active)
    assert throttle.should_fire(
        camera_id=1, camera_name="Cam1", event_type="type_a", notification_id=2, event_time=datetime.now(timezone.utc)
    ) is False

    # Camera 1, Type B fires (different event type)
    assert throttle.should_fire(
        camera_id=1, camera_name="Cam1", event_type="type_b", notification_id=3, event_time=datetime.now(timezone.utc)
    ) is True

    # Camera 2, Type A fires (different camera)
    assert throttle.should_fire(
        camera_id=2, camera_name="Cam2", event_type="type_a", notification_id=4, event_time=datetime.now(timezone.utc)
    ) is True


def test_alert_throttle_digest(db_session, monkeypatch):
    # Mock settings with 10 second cooldown, 5 minutes digest
    class MockSettings:
        enable_email_alerts = True
        smtp_host = "localhost"
        smtp_port = 587
        smtp_user = "user"
        smtp_pass = "pass"
        alert_to_email = "alert@test.com"
        alert_cooldown_seconds = 10
        alert_digest_minutes = 5

    monkeypatch.setattr("app.services.alert_throttle.get_settings", lambda: MockSettings())
    monkeypatch.setattr("app.services.notification_service.get_settings", lambda: MockSettings())

    # Redirect DB session in AlertThrottle to our TestingSessionLocal
    monkeypatch.setattr("app.db.session.SessionLocal", TestingSessionLocal)

    email_sent_calls = []
    def mock_send_email_alert(self, subject, body):
        email_sent_calls.append((subject, body))
        return True

    monkeypatch.setattr(NotificationService, "_send_email_alert", mock_send_email_alert)

    camera = create_camera(db_session, name="Lobby Gate", source_url="0", location="Lobby")
    event = create_event(db_session, event_type="restricted_area_entered", camera_id=camera.id)
    
    n1 = create_notification(db_session, event_id=event.id, notification_type="restricted_area_entered", message="M1")
    n2 = create_notification(db_session, event_id=event.id, notification_type="restricted_area_entered", message="M2")
    n3 = create_notification(db_session, event_id=event.id, notification_type="restricted_area_entered", message="M3")

    throttle = AlertThrottle()

    # First fires immediately
    assert throttle.should_fire(
        camera_id=camera.id,
        camera_name=camera.name,
        event_type="restricted_area_entered",
        notification_id=n1.id,
        event_time=datetime.now(timezone.utc),
    ) is True

    # Second is suppressed and batched in digest
    assert throttle.should_fire(
        camera_id=camera.id,
        camera_name=camera.name,
        event_type="restricted_area_entered",
        notification_id=n2.id,
        event_time=datetime.now(timezone.utc),
    ) is False

    # Third is suppressed and batched in digest
    assert throttle.should_fire(
        camera_id=camera.id,
        camera_name=camera.name,
        event_type="restricted_area_entered",
        notification_id=n3.id,
        event_time=datetime.now(timezone.utc),
    ) is False

    # Verify batch contains correct aggregation data
    key = (camera.id, "restricted_area_entered")
    assert key in throttle.digest_batches
    assert throttle.digest_batches[key]["count"] == 2
    assert throttle.digest_batches[key]["notification_ids"] == [n2.id, n3.id]

    # Trigger manual digest sending
    throttle.send_digest()

    # Verify digest email formatting
    assert len(email_sent_calls) == 1
    assert "[DIGEST ALERT]" in email_sent_calls[0][0]
    assert "Suppressed Count: 2" in email_sent_calls[0][1]
    assert "Camera: Lobby Gate" in email_sent_calls[0][1]

    # Verify notification records in DB are successfully updated to SENT status
    db_session.refresh(n2)
    db_session.refresh(n3)
    assert n2.email_sent is True
    assert n2.status == "SENT"
    assert n3.email_sent is True
    assert n3.status == "SENT"

    # Verify in-memory batch has been cleared
    assert len(throttle.digest_batches) == 0
