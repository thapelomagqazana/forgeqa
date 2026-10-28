"""Smoke test for the reference application's health endpoint."""

import pytest
from app.main import app
from fastapi.testclient import TestClient


@pytest.mark.integration
def test_health_endpoint() -> None:
    """REF-01: GET /api/health returns 200 with {'status': 'ok'}."""
    client = TestClient(app)
    response = client.get("/api/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "version": "0.1.0"}
