from fastapi.testclient import TestClient
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.models.base import Base
from app.services.health_service import health_status
from app.main import app

# Setup in-memory SQLite engine for testing database connection ping
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


def test_health_status_independent(db_session, monkeypatch):
    # Mock settings and DB SessionLocal
    monkeypatch.setattr("app.services.health_service.SessionLocal", TestingSessionLocal)

    # Invoke independent health status check
    payload = health_status(processor=None, registry=None)
    
    assert payload is not None
    assert "status" in payload
    assert "service" in payload
    assert "checks" in payload
    assert payload["checks"]["database_connected"] == "healthy"


def test_health_endpoint_rest():
    client = TestClient(app)
    
    # 1. Verify root /health route exists and responds successfully
    response = client.get("/health")
    assert response.status_code == 200
    
    data = response.json()
    assert "status" in data
    assert "checks" in data
    
    # 2. Verify legacy /api/health route responds successfully
    response_legacy = client.get("/api/health")
    assert response_legacy.status_code == 200
    assert response_legacy.json()["status"] == data["status"]
