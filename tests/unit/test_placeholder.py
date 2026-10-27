"""Placeholder test to verify Pytest configuration and marker discovery."""

import pytest


@pytest.mark.unit
def test_placeholder() -> None:
    """Verify that the unit marker is registered and the test suite runs."""
    assert True
