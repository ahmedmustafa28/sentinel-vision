import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.models.base import Base
from app.db.crud_event import create_event
from app.db.crud_camera import create_camera
from app.main import app

# Isolated in-memory SQLite for testing report routes
TEST_SQLALCHEMY_DATABASE_URL = "sqlite:///:memory:"
engine = create_engine(
    TEST_SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture(scope="function")
def db_session(monkeypatch):
    Base.metadata.create_all(bind=engine)
    db = TestingSessionLocal()
    # Force pages.py route to use TestingSessionLocal
    monkeypatch.setattr("app.api.routes.pages.SessionLocal", TestingSessionLocal)
    try:
        yield db
    finally:
        db.close()
        Base.metadata.drop_all(bind=engine)


def test_reports_page_and_generation(db_session):
    # Use TestClient with lifespan context manager so that templates and state are initialized
    with TestClient(app) as client:
        # 1. Test GET /reports page when empty
        response = client.get("/reports")
        assert response.status_code == 200
        assert "AI Reports" in response.text

        # Create dummy camera and event to have events for report generation
        camera = create_camera(
            db_session,
            name="Test Camera",
            source_url="rtsp://test",
            location="Test Area",
            is_restricted=False,
        )
        db_session.commit()

        create_event(
            db_session,
            event_type="person_detected",
            camera_id=camera.id,
            description="A person was detected in test zone",
        )
        db_session.commit()

        # 2. Test POST /reports/generate returns a FileResponse download
        response_post = client.post("/reports/generate")
        assert response_post.status_code == 200
        assert response_post.headers["content-type"] == "application/octet-stream"
        assert "attachment; filename=" in response_post.headers["content-disposition"]
        assert "ai_reports_" in response_post.headers["content-disposition"]

        # 3. Test GET /reports page again to ensure files list loads and download link works
        response_after = client.get("/reports")
        assert response_after.status_code == 200
        assert "AI Reports" in response_after.text

        # Find the generated file in the page content or via files listing and test GET download
        import glob
        import os
        from app.core.config import BASE_DIR

        reports_dir = (BASE_DIR / "data" / "reports").resolve()
        list_of_files = glob.glob(str(reports_dir / "*.txt"))
        assert len(list_of_files) > 0
        latest_filename = os.path.basename(list_of_files[0])

        response_download = client.get(f"/reports/download/{latest_filename}")
        assert response_download.status_code == 200
        assert response_download.headers["content-type"] == "application/octet-stream"
        assert (
            response_download.headers["content-disposition"]
            == f'attachment; filename="{latest_filename}"'
        )
