"""
In-memory data store for the reference application.

This module is the single source of truth for records. It provides:
- Initial seed data (deterministic, synthetic).
- A mutable in-memory store.
- A reset() function to restore the initial state.

Data is NOT persisted. It resets on server restart or via POST /api/reset.

All data is explicitly synthetic. No real personal information.
"""

from __future__ import annotations

from app.schemas import RecordResponse

# =============================================================================
# Initial seed data (deterministic)
# =============================================================================
# Rules:
# - IDs are fixed (1, 2, 3).
# - Names are generic ("Test Record N").
# - Statuses are "active" or "inactive".
# - No real PII.

INITIAL_RECORDS: list[RecordResponse] = [
    RecordResponse(id=1, name="Test Record 1", status="active"),
    RecordResponse(id=2, name="Test Record 2", status="inactive"),
    RecordResponse(id=3, name="Test Record 3", status="active"),
]

# =============================================================================
# Mutable store
# =============================================================================
# This list is mutated by the API and UI routers.
# It is reset to INITIAL_RECORDS by reset().

_records: list[RecordResponse] = [r.model_copy() for r in INITIAL_RECORDS]
_next_id: int = 4


# =============================================================================
# Accessors
# =============================================================================


def get_all_records() -> list[RecordResponse]:
    """Return the current list of records (mutable reference)."""
    return _records


def get_record_by_id(record_id: int) -> RecordResponse | None:
    """Return a record by ID, or None if not found."""
    for record in _records:
        if record.id == record_id:
            return record
    return None


def add_record(name: str, status: str = "active") -> RecordResponse:
    """Add a new record and return it. Increments the next ID."""
    global _next_id
    record = RecordResponse(id=_next_id, name=name, status=status)
    _records.append(record)
    _next_id += 1
    return record


def get_next_id() -> int:
    """Return the next available record ID."""
    return _next_id


# =============================================================================
# Reset
# =============================================================================


def reset() -> None:
    """
    Reset the store to its initial state.

    This restores the 3 seed records and resets the next ID to 4.
    It is called by POST /api/reset.
    """
    global _records, _next_id
    _records = [r.model_copy() for r in INITIAL_RECORDS]
    _next_id = 4
