import pytest

from app.core.auth import get_current_user
from app.main import app
from app.models.user import User


@pytest.fixture(autouse=True)
def override_auth_dependency():
    """
    Globally overrides the get_current_user FastAPI dependency during tests.
    Returns a dummy admin user so that existing integration and REST API tests
    do not fail with 401 Unauthorized or login redirects.
    """
    dummy_user = User(
        id=999,
        username="test_admin",
        hashed_password="mocked_hashed_password",
        role="admin"
    )

    def mock_get_current_user():
        return dummy_user

    # Set dependency override
    app.dependency_overrides[get_current_user] = mock_get_current_user
    
    yield
    
    # Clean up dependency override after test runs
    app.dependency_overrides.pop(get_current_user, None)
