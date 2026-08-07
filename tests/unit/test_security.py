import pytest
from fastapi.testclient import TestClient
from fastapi import HTTPException
from backend.app import create_app

app = create_app()

@pytest.fixture
def client():
    return TestClient(app)

def test_cors_headers(client):
    response = client.options("/api/health", headers={
        "Origin": "http://localhost:3000",
        "Access-Control-Request-Method": "GET",
    })
    assert response.status_code == 200
    assert "access-control-allow-origin" in response.headers

def test_command_injection_prevented_on_ports(client):
    response = client.post("/api/control/block/80;rm -rf /")
    # FastAPI path parameter validation should fail (either 422 Unprocessable, 405 Method Not Allowed, or 404 Not Found)
    assert response.status_code in (422, 405, 404)

def test_command_injection_prevented_on_protocol(client):
    response = client.post(
        "/api/control/block/80",
        params={"protocol": "TCP; echo 'hacked'"}
    )
    assert response.status_code == 400
