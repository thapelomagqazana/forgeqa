"""
Administrative endpoints for the reference application.

Implements POST /api/reset to restore the in-memory store to its initial state.
This ensures deterministic test data for ForgeQA's test suites.
"""

from __future__ import annotations

from fastapi import APIRouter, status
from pydantic import BaseModel, Field

from app import store

router = APIRouter(prefix="/admin", tags=["admin"])


class ResetResponse(BaseModel):
    """Response schema for the reset endpoint."""

    status: str = Field(..., description="Reset status")
    message: str = Field(..., description="Human-readable message")
    records_count: int = Field(..., description="Number of records after reset")


@router.post(
    "/reset",
    response_model=ResetResponse,
    status_code=status.HTTP_200_OK,
    summary="Reset the in-memory store to its initial state",
    description=(
        "Restores the 3 seed records and resets the next ID to 4. "
        "Call this before each test run to ensure deterministic data."
    ),
)
async def reset_store() -> ResetResponse:
    """Reset the in-memory store to its initial state."""
    store.reset()
    return ResetResponse(
        status="ok",
        message="Store reset to initial state",
        records_count=len(store.get_all_records()),
    )
