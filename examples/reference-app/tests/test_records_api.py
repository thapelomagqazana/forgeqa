"""
Contract tests for the reference application's API endpoints.

These tests validate REF-02, REF-03, REF-04, and REF-05 from the
Reference Scenario Matrix (examples/reference-app/README.md).
"""

import pytest
from app import store
from app.main import app
from fastapi.testclient import TestClient


@pytest.fixture
def client() -> TestClient:
    """Return a FastAPI test client and reset the store before each test."""
    store.reset()
    return TestClient(app)


# =============================================================================
# REF-02: Retrieve an existing record
# =============================================================================


@pytest.mark.integration
def test_ref_02_get_existing_record(client: TestClient) -> None:
    """REF-02: GET /api/records/1 returns 200 with the expected payload."""
    response = client.get("/api/records/1")

    assert response.status_code == 200
    payload = response.json()
    assert payload == {"id": 1, "name": "Test Record 1", "status": "active"}


@pytest.mark.integration
def test_ref_02_get_existing_record_2(client: TestClient) -> None:
    """REF-02: GET /api/records/2 returns the second record."""
    response = client.get("/api/records/2")

    assert response.status_code == 200
    payload = response.json()
    assert payload["id"] == 2
    assert payload["name"] == "Test Record 2"
    assert payload["status"] == "inactive"


# =============================================================================
# REF-03: Create a record (valid)
# =============================================================================


@pytest.mark.integration
def test_ref_03_create_valid_record(client: TestClient) -> None:
    """REF-03: POST /api/records with valid data returns 201."""
    response = client.post("/api/records", json={"name": "New Test Record"})

    assert response.status_code == 201
    payload = response.json()
    assert payload["name"] == "New Test Record"
    assert payload["status"] == "active"
    assert "id" in payload
    assert payload["id"] >= 4  # IDs start at 4 for new records


# =============================================================================
# REF-03: Create a record (invalid — validation error)
# =============================================================================


@pytest.mark.integration
def test_ref_03_create_invalid_record_empty_name(client: TestClient) -> None:
    """REF-03: POST /api/records with empty name returns 422."""
    response = client.post("/api/records", json={"name": ""})

    assert response.status_code == 422
    payload = response.json()
    assert "detail" in payload
    assert payload["detail"][0]["loc"] == ["body", "name"]


@pytest.mark.integration
def test_ref_03_create_invalid_record_missing_name(client: TestClient) -> None:
    """REF-03: POST /api/records without a name returns 422."""
    response = client.post("/api/records", json={})

    assert response.status_code == 422
    payload = response.json()
    assert "detail" in payload
    assert payload["detail"][0]["loc"] == ["body", "name"]


# =============================================================================
# REF-04: Request an unknown record
# =============================================================================


@pytest.mark.integration
def test_ref_04_get_unknown_record(client: TestClient) -> None:
    """REF-04: GET /api/records/9999 returns 404."""
    response = client.get("/api/records/9999")

    assert response.status_code == 404
    assert response.json() == {"detail": "Record not found"}


# =============================================================================
# REF-05: Controllable failure
# =============================================================================


@pytest.mark.integration
def test_ref_05_deliberate_failure(client: TestClient) -> None:
    """REF-05: GET /api/records/fail returns 500 with a specific message."""
    response = client.get("/api/records/fail")

    assert response.status_code == 500
    assert response.json() == {"detail": "Deliberate failure for diagnostics testing"}
