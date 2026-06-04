import os
import time
import pytest
from datetime import datetime, timezone, timedelta
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.models.base import Base
from app.models.event import Event
from app.jobs.retention_job import run_retention_cleanup
from app.core.config import get_settings
from app.main import app

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
    monkeypatch.setattr("app.db.session.SessionLocal", TestingSessionLocal)
    with TestClient(app) as test_client:
        yield test_client


def test_run_retention_cleanup(db_session, tmp_path, monkeypatch):
    monkeypatch.setattr("app.db.session.SessionLocal", TestingSessionLocal)

    # 1. Create dummy files (snapshots) in tmp_path
    # File 1: Old (outside retention window of 3 days)
    old_file = tmp_path / "old_snapshot.jpg"
    old_file.write_text("old image data")
    old_mtime = time.time() - (4 * 86400)
    os.utime(old_file, (old_mtime, old_mtime))

    # File 2: New (inside retention window of 3 days)
    new_file = tmp_path / "new_snapshot.jpg"
    new_file.write_text("new image data")
    new_mtime = time.time() - (1 * 86400)
    os.utime(new_file, (new_mtime, new_mtime))

    # 2. Add Event records to DB
    # Record 1: Old
    old_time = datetime.now(timezone.utc) - timedelta(days=4)
    old_event = Event(
        id=1,
        camera_id=1,
        event_type="person",
        timestamp=old_time,
        image_path=str(old_file),
    )
    # Record 2: New
    new_time = datetime.now(timezone.utc) - timedelta(days=1)
    new_event = Event(
        id=2,
        camera_id=1,
        event_type="person",
        timestamp=new_time,
        image_path=str(new_file),
    )
    db_session.add(old_event)
    db_session.add(new_event)
    db_session.commit()

    # 3. Run retention cleanup (retention_days = 3)
    result = run_retention_cleanup(retention_days=3, snapshot_dir=tmp_path)

    # 4. Verify results
    assert result["deleted_snapshots"] == 1
    assert result["deleted_event_records"] == 1

    # Verify old file is gone, new file is kept
    assert not old_file.exists()
    assert new_file.exists()

    # Verify old DB record is gone, new DB record is kept
    remaining_events = db_session.query(Event).all()
    assert len(remaining_events) == 1
    assert remaining_events[0].id == 2


def test_api_run_retention_endpoint(client, db_session, monkeypatch):
    monkeypatch.setattr("app.db.session.SessionLocal", TestingSessionLocal)

    class MockSettings:
        secret_key = "test_secret_admin_key"
        event_retention_days = 5
        event_snapshot_dir = "test_snapshots"
        app_name = "AI CCTV Test"
        app_env = "test"

    mock_settings = MockSettings()

    # Register dependency overrides for FastAPI
    app.dependency_overrides[get_settings] = lambda: mock_settings
    monkeypatch.setattr("app.jobs.retention_job.get_settings", lambda: mock_settings)

    try:
        # 1. Access without key -> expects 422 because of missing header
        response = client.post("/admin/run-retention")
        assert response.status_code == 422

        # 2. Access with wrong key -> expects 401
        response = client.post(
            "/admin/run-retention", headers={"X-Admin-Key": "wrong_key"}
        )
        assert response.status_code == 401
        assert response.json()["detail"] == "Invalid Admin Key"

        # 3. Access with correct key -> expects 200
        called = []

        def mock_cleanup(days, path):
            called.append((days, path))
            return {"deleted_snapshots": 3, "deleted_event_records": 4}

        monkeypatch.setattr(
            "app.api.routes.api_admin.run_retention_cleanup", mock_cleanup
        )

        response = client.post(
            "/admin/run-retention", headers={"X-Admin-Key": "test_secret_admin_key"}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        assert data["details"]["deleted_snapshots"] == 3
        assert data["details"]["deleted_event_records"] == 4
        assert len(called) == 1
        assert called[0][0] == 5
    finally:
        app.dependency_overrides.pop(get_settings, None)
