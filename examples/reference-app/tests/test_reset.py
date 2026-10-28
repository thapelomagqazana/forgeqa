"""
Contract tests for the reset endpoint and deterministic test data.

These tests validate that:
- The application starts with 3 seed records.
- POST /api/reset restores the initial state.
- The seed data is synthetic (no real PII).
"""

import pytest
from app import store
from app.main import app
from app.store import INITIAL_RECORDS
from fastapi.testclient import TestClient


@pytest.fixture
def client() -> TestClient:
    """Return a FastAPI test client and reset the store before each test."""
    store.reset()
    return TestClient(app)


# =============================================================================
# Startup seed data
# =============================================================================


@pytest.mark.integration
def test_initial_seed_data_has_three_records(client: TestClient) -> None:
    """The application starts with 3 pre-defined records."""
    response = client.get("/api/records/1")
    assert response.status_code == 200

    response = client.get("/api/records/2")
    assert response.status_code == 200

    response = client.get("/api/records/3")
    assert response.status_code == 200

    # ID 4 should not exist initially
    response = client.get("/api/records/4")
    assert response.status_code == 404


@pytest.mark.integration
def test_seed_data_is_synthetic() -> None:
    """The seed data contains no real PII (only 'Test Record N')."""
    for record in INITIAL_RECORDS:
        assert record.name.startswith("Test Record")
        assert "@" not in record.name  # No email addresses
        assert record.status in {"active", "inactive"}


# =============================================================================
# Reset endpoint
# =============================================================================


@pytest.mark.integration
def test_reset_restores_initial_state(client: TestClient) -> None:
    """POST /api/reset restores the 3 initial records."""
    # Add a new record (so the store is no longer in its initial state)
    response = client.post("/api/records", json={"name": "Extra Record"})
    assert response.status_code == 201
    new_id = response.json()["id"]

    # Verify the new record exists
    response = client.get(f"/api/records/{new_id}")
    assert response.status_code == 200

    # Reset
    response = client.post("/api/admin/reset")
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["message"] == "Store reset to initial state"
    assert payload["records_count"] == 3

    # Verify the new record is gone
    response = client.get(f"/api/records/{new_id}")
    assert response.status_code == 404

    # Verify the 3 seed records exist
    for record_id in (1, 2, 3):
        response = client.get(f"/api/records/{record_id}")
        assert response.status_code == 200


@pytest.mark.integration
def test_reset_is_idempotent(client: TestClient) -> None:
    """Calling reset multiple times produces the same state."""
    response = client.post("/api/admin/reset")
    assert response.status_code == 200

    response = client.post("/api/admin/reset")
    assert response.status_code == 200
    assert response.json()["records_count"] == 3
