"""
Record management endpoints for the reference application.

Implements REF-02 (get record), REF-03 (create record), REF-04 (not found),
and REF-05 (controllable failure).

Data is managed by app/store.py (in-memory, resettable via POST /api/reset).
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, status

from app import store
from app.schemas import ErrorResponse, RecordCreate, RecordResponse

router = APIRouter(prefix="/records", tags=["records"])


# =============================================================================
# REF-05: Controllable failure (must be defined BEFORE /{record_id})
# =============================================================================


@router.get(
    "/fail",
    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
    response_model=ErrorResponse,
    summary="Deliberate failure for diagnostics testing (REF-05)",
    description=(
        "Always returns 500. This is not a bug — it is intentionally designed "
        "to exercise ForgeQA's failure diagnostics path."
    ),
)
async def deliberate_failure() -> ErrorResponse:
    """REF-05: Controllable failure scenario."""
    raise HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail="Deliberate failure for diagnostics testing",
    )


# =============================================================================
# REF-02: Retrieve an existing record
# =============================================================================


@router.get(
    "/{record_id}",
    response_model=RecordResponse,
    summary="Retrieve a record by ID (REF-02)",
    responses={
        404: {"model": ErrorResponse, "description": "Record not found (REF-04)"},
    },
)
async def get_record(record_id: int) -> RecordResponse:
    """REF-02: Retrieve an existing record."""
    record = store.get_record_by_id(record_id)
    if record is None:
        # REF-04: Unknown record
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Record not found",
        )
    return record


# =============================================================================
# REF-03: Create a record (valid) / validation error (invalid)
# =============================================================================


@router.post(
    "",
    status_code=status.HTTP_201_CREATED,
    response_model=RecordResponse,
    summary="Create a new record (REF-03)",
    responses={
        422: {"description": "Validation error (empty name or missing field)"},
    },
)
async def create_record(payload: RecordCreate) -> RecordResponse:
    """
    REF-03: Create a new record.

    - **Valid** payload (`{"name": "New Record"}`): returns 201 with the created record.
    - **Invalid** payload (`{"name": ""}`): FastAPI automatically returns 422
      with Pydantic validation details.
    """
    return store.add_record(name=payload.name)
