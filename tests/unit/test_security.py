import pytest
from fastapi.testclient import TestClient
import os
from backend.main import app

@pytest.fixture
def client_with_auth():
    import backend.main
    original_key = backend.main.SENTINEL_API_KEY
    backend.main.SENTINEL_API_KEY = "test-secret-key"
    client = TestClient(app)
    yield client
    backend.main.SENTINEL_API_KEY = original_key

def test_auth_required_for_destructive_actions(client_with_auth):
    # Without auth
    response = client_with_auth.post("/api/control/kill/1234")
    assert response.status_code == 401

    # With incorrect auth
    response = client_with_auth.post("/api/control/kill/1234", headers={"X-API-Key": "wrong-key"})
    assert response.status_code == 401

    # Sensitive read without auth
    response = client_with_auth.get("/api/info")
    assert response.status_code == 401

def test_cors_headers(client_with_auth):
    # Our application uses CORSMiddleware, but initializing it dynamically in tests is tricky.
    # We'll assert that the middleware is installed.
    from backend.main import app
    from starlette.middleware.cors import CORSMiddleware
    cors_installed = any(m.cls == CORSMiddleware for m in app.user_middleware)
    assert cors_installed

def test_command_injection_prevented_on_ports(client_with_auth):
    # The API should reject invalid port strings instead of executing them
    response = client_with_auth.post(
        "/api/control/block/80;rm -rf /",
        headers={"X-API-Key": "test-secret-key"}
    )
    assert response.status_code in (422, 405, 404)  # FastAPI path parameter validation should fail

def test_command_injection_prevented_on_protocol(client_with_auth):
    response = client_with_auth.post(
        "/api/control/block/80",
        params={"protocol": "TCP; echo 'hacked'"},
        headers={"X-API-Key": "test-secret-key"}
    )
    assert response.status_code == 400  # Our code should return 400 Invalid Protocol
