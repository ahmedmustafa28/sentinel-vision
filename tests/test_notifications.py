import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from fastapi.testclient import TestClient

from app.models.base import Base
from app.db.crud_camera import create_camera
from app.db.crud_event import create_event
from app.db.crud_notification import (
    create_notification,
    list_notifications,
    mark_notification_as_read,
    get_unread_notification_count,
)
from app.services.notification_service import NotificationService
from app.main import app

# In-memory SQLite for testing DB CRUDs
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


def test_notification_model_and_crud(db_session):
    # 1. Create dependencies
    camera = create_camera(
        db_session,
        name="Test Camera",
        source_url="0",
        location="Test Location",
        is_restricted=True,
    )
    assert camera.id is not None
    assert camera.is_restricted is True

    event = create_event(
        db_session,
        event_type="unknown_person_detected",
        camera_id=camera.id,
        description="Unknown face seen",
    )
    assert event.id is not None

    # 2. Create Notification
    notification = create_notification(
        db_session,
        event_id=event.id,
        notification_type="unknown_person_detected",
        message="Test alert message",
        email_sent=False,
    )
    assert notification.id is not None
    assert notification.is_read is False

    # 3. Test counts and list
    unread_count = get_unread_notification_count(db_session)
    assert unread_count == 1

    alerts = list_notifications(db_session, is_read=False)
    assert len(alerts) == 1
    assert alerts[0].message == "Test alert message"

    # 4. Mark as read
    updated = mark_notification_as_read(db_session, notification.id, is_read=True)
    assert updated is not None
    assert updated.is_read is True

    unread_count_after = get_unread_notification_count(db_session)
    assert unread_count_after == 0


def test_notification_service_integration(db_session, monkeypatch):
    # Mock settings
    class MockSettings:
        enable_email_alerts = True
        smtp_host = "localhost"
        smtp_port = 587
        smtp_user = "user"
        smtp_pass = "pass"
        alert_to_email = "alert@test.com"

    service = NotificationService(db_session_factory=TestingSessionLocal)
    monkeypatch.setattr(service, "_settings", MockSettings())

    # Mock SMTP send email call
    email_sent_calls = []

    def mock_send_email(subject, body):
        email_sent_calls.append((subject, body))
        return True

    monkeypatch.setattr(service, "_send_email_alert", mock_send_email)

    # Setup database records
    camera = create_camera(
        db_session,
        name="Front Gate",
        source_url="1",
        location="Gate",
        is_restricted=True,
    )
    event = create_event(
        db_session,
        event_type="restricted_area_entered",
        camera_id=camera.id,
        description="Person entered",
    )

    # Run processing
    service.process_event(db_session, event)

    # Wait for the background email dispatch thread to complete
    import time

    time.sleep(0.5)

    # Check notification row created
    unread_count = get_unread_notification_count(db_session)
    assert unread_count == 1

    alerts = list_notifications(db_session, is_read=False)
    assert len(alerts) == 1
    assert "Restricted area entry detected by Front Gate" in alerts[0].message
    assert alerts[0].email_sent is True
    assert alerts[0].email_recipient == "alert@test.com"

    # Assert mock email sent
    assert len(email_sent_calls) == 1
    assert "Restricted Area Intrusion at Gate" in email_sent_calls[0][0]


def test_fastapi_endpoints(db_session):
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

        # Verify unread API endpoint returns successfully
        response = client.get("/api/notifications/unread")
        assert response.status_code == 200
        data = response.json()
        assert "unread_count" in data
        assert "latest_alerts" in data
    finally:
        app.dependency_overrides.clear()
