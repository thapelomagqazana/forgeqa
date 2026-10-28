"""
Contract tests for the reference application's UI routes.

These tests validate REF-06, REF-07, REF-08, and REF-09 from the
Reference Scenario Matrix (examples/reference-app/README.md).

Note: These tests use FastAPI's TestClient (no browser). Browser-based
tests using Playwright will be added in Phase 1 (ForgeQA's own test suite).
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
# REF-06: Records page
# =============================================================================


@pytest.mark.integration
def test_ref_06_records_page_loads(client: TestClient) -> None:
    """REF-06: GET /ui/records returns 200 with the record list and form."""
    response = client.get("/ui/records")

    assert response.status_code == 200
    html = response.text

    # Page title
    assert "ForgeQA Reference App" in html

    # Record list container
    assert 'data-testid="record-list"' in html

    # Individual record items
    assert 'data-testid="record-item-1"' in html
    assert 'data-testid="record-item-2"' in html
    assert 'data-testid="record-item-3"' in html

    # Visible text
    assert "Test Record 1" in html
    assert "Test Record 2" in html
    assert "Test Record 3" in html


@pytest.mark.integration
def test_ref_06_form_inputs_have_data_testid(client: TestClient) -> None:
    """REF-06: The form inputs have data-testid attributes."""
    response = client.get("/ui/records")

    assert response.status_code == 200
    html = response.text

    assert 'data-testid="name-input"' in html
    assert 'data-testid="submit-button"' in html


# =============================================================================
# REF-07: Valid form submission
# =============================================================================


@pytest.mark.integration
def test_ref_07_valid_form_submission(client: TestClient) -> None:
    """REF-07: POST /ui/records with a valid name shows a success message."""
    response = client.post("/ui/records", data={"name": "New Test Record"})

    assert response.status_code == 200
    html = response.text

    assert 'data-testid="success-message"' in html
    assert "Record created successfully" in html
    assert "New Test Record" in html


# =============================================================================
# REF-08: Invalid form submission
# =============================================================================


@pytest.mark.integration
def test_ref_08_invalid_form_submission_empty_name(client: TestClient) -> None:
    """REF-08: POST /ui/records with an empty name shows a validation error."""
    response = client.post("/ui/records", data={"name": ""})

    assert response.status_code == 422
    html = response.text

    assert 'data-testid="validation-error"' in html
    assert "Name is required" in html


# =============================================================================
# REF-09: Deliberate failure page
# =============================================================================


@pytest.mark.integration
def test_ref_09_deliberate_failure_page(client: TestClient) -> None:
    """REF-09: GET /ui/fail renders the deliberate failure page."""
    response = client.get("/ui/fail")

    assert response.status_code == 200
    html = response.text

    assert 'data-testid="failure-heading"' in html
    assert "This page intentionally fails" in html
