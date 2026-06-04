import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from fastapi.testclient import TestClient

from app.models.base import Base
from app.db.crud_camera import create_camera
from app.core.validators import validate_camera_source
from app.main import app

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


@pytest.fixture(scope="function")
def client(db_session, monkeypatch):
    # Mock settings DB SessionLocal
    monkeypatch.setattr("app.db.session.SessionLocal", TestingSessionLocal)
    monkeypatch.setattr("app.api.routes.api_cameras.get_db_session", lambda: db_session)
    with TestClient(app) as test_client:
        yield test_client


def test_validate_camera_source_unit(monkeypatch):
    # Mock settings with ALLOW_LOCAL_RTSP = False
    class MockSettingsDefault:
        allow_local_rtsp = False

    monkeypatch.setattr(
        "app.core.validators.get_settings", lambda: MockSettingsDefault()
    )

    # 1. Valid inputs
    assert (
        validate_camera_source("rtsp://example.com/live") == "rtsp://example.com/live"
    )
    assert (
        validate_camera_source("rtsps://example.com/live") == "rtsps://example.com/live"
    )
    assert (
        validate_camera_source("http://mjpeg.example.com/stream.mjpg")
        == "http://mjpeg.example.com/stream.mjpg"
    )
    assert (
        validate_camera_source("https://mjpeg.example.com/stream.mjpg")
        == "https://mjpeg.example.com/stream.mjpg"
    )
    assert validate_camera_source(0) == 0
    assert validate_camera_source("1") == 1

    # 2. Rejected scheme (file://)
    with pytest.raises(ValueError, match="Invalid camera source"):
        validate_camera_source("file:///etc/passwd")

    # 3. Rejected private IPs by default
    with pytest.raises(ValueError, match="Invalid camera source"):
        validate_camera_source("rtsp://192.168.1.1/stream")
    with pytest.raises(ValueError, match="Invalid camera source"):
        validate_camera_source("rtsp://localhost/stream")
    with pytest.raises(ValueError, match="Invalid camera source"):
        validate_camera_source("rtsp://10.0.0.1/stream")
    with pytest.raises(ValueError, match="Invalid camera source"):
        validate_camera_source("rtsp://172.16.0.1/stream")

    # 4. Valid private IPs if ALLOW_LOCAL_RTSP = True
    class MockSettingsAllowLocal:
        allow_local_rtsp = True

    monkeypatch.setattr(
        "app.core.validators.get_settings", lambda: MockSettingsAllowLocal()
    )
    assert (
        validate_camera_source("rtsp://192.168.1.1/stream")
        == "rtsp://192.168.1.1/stream"
    )
    assert (
        validate_camera_source("rtsp://localhost/stream") == "rtsp://localhost/stream"
    )
    assert (
        validate_camera_source("rtsp://127.0.0.1/stream") == "rtsp://127.0.0.1/stream"
    )


def test_api_camera_create_and_validation(client, monkeypatch):
    class MockSettingsDefault:
        allow_local_rtsp = False

    monkeypatch.setattr(
        "app.core.validators.get_settings", lambda: MockSettingsDefault()
    )

    # Create valid camera via REST API
    payload = {
        "name": "Lobby Main",
        "source_url": "rtsp://example.com/stream",
        "location": "Lobby",
        "is_active": True,
        "is_restricted": False,
    }
    response = client.post("/cameras", json=payload)
    assert response.status_code == 201
    data = response.json()
    assert data["id"] is not None
    assert data["name"] == "Lobby Main"
    assert data["source_url"] == "rtsp://example.com/stream"

    # Create invalid camera (rejected scheme file://) -> expects 422
    payload_invalid_scheme = {
        "name": "Invalid Cam",
        "source_url": "file:///tmp/stream",
        "location": "Server Room",
    }
    response = client.post("/cameras", json=payload_invalid_scheme)
    assert response.status_code == 422
    error_msg = response.json()["detail"][0]["msg"]
    assert "Invalid camera source" in error_msg

    # Create invalid camera (rejected private IP) -> expects 422
    payload_invalid_ip = {
        "name": "Local Cam",
        "source_url": "rtsp://192.168.1.100/stream",
    }
    response = client.post("/cameras", json=payload_invalid_ip)
    assert response.status_code == 422


def test_api_camera_update_and_validation(db_session, client, monkeypatch):
    class MockSettingsDefault:
        allow_local_rtsp = False

    monkeypatch.setattr(
        "app.core.validators.get_settings", lambda: MockSettingsDefault()
    )

    # Pre-populate a camera in DB
    camera = create_camera(
        db_session,
        name="Old Name",
        source_url="rtsp://public-stream.com/feed",
        location="Front",
        is_active=True,
        is_restricted=False,
    )

    # Update camera with valid data
    update_payload = {
        "name": "New Name",
        "source_url": "rtsp://updated-public-stream.com/feed",
    }
    response = client.put(f"/cameras/{camera.id}", json=update_payload)
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "New Name"
    assert data["source_url"] == "rtsp://updated-public-stream.com/feed"

    # Update camera with invalid source_url (rejected file:// scheme)
    invalid_update_payload = {"source_url": "file:///var/log"}
    response = client.put(f"/cameras/{camera.id}", json=invalid_update_payload)
    assert response.status_code == 422
    error_msg = response.json()["detail"][0]["msg"]
    assert "Invalid camera source" in error_msg
