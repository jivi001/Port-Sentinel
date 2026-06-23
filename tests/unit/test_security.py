import pytest
from fastapi.testclient import TestClient
from fastapi import HTTPException
from backend.main import app
from backend.api.dependencies import get_current_user
from backend.core.models import User, RoleEnum

@pytest.fixture
def client():
    return TestClient(app)

def test_auth_required_for_destructive_actions(client):
    # 1. Unauthenticated (get_current_user raises 401)
    def mock_get_current_user_unauth():
        raise HTTPException(status_code=401, detail="Could not validate credentials")
    
    app.dependency_overrides[get_current_user] = mock_get_current_user_unauth
    try:
        response = client.post("/api/control/block/80")
        assert response.status_code == 401
    finally:
        app.dependency_overrides.pop(get_current_user, None)

    # 2. Unauthorized role (get_current_user returns viewer user)
    viewer_user = User(username="viewer", role=RoleEnum.VIEWER.value)
    app.dependency_overrides[get_current_user] = lambda: viewer_user
    try:
        response = client.post("/api/control/block/80")
        assert response.status_code == 403
    finally:
        app.dependency_overrides.pop(get_current_user, None)

def test_cors_headers(client):
    from starlette.middleware.cors import CORSMiddleware
    cors_installed = any(m.cls == CORSMiddleware for m in app.user_middleware)
    assert cors_installed

def test_command_injection_prevented_on_ports(client):
    # Override to return admin user so we pass auth, but check validation of port
    admin_user = User(username="admin", role=RoleEnum.ADMIN.value)
    app.dependency_overrides[get_current_user] = lambda: admin_user
    try:
        response = client.post("/api/control/block/80;rm -rf /")
        # FastAPI path parameter validation should fail (either 422 Unprocessable, 405 Method Not Allowed, or 404 Not Found)
        assert response.status_code in (422, 405, 404)
    finally:
        app.dependency_overrides.pop(get_current_user, None)

def test_command_injection_prevented_on_protocol(client):
    admin_user = User(username="admin", role=RoleEnum.ADMIN.value)
    app.dependency_overrides[get_current_user] = lambda: admin_user
    try:
        response = client.post(
            "/api/control/block/80",
            params={"protocol": "TCP; echo 'hacked'"}
        )
        assert response.status_code == 400
    finally:
        app.dependency_overrides.pop(get_current_user, None)
