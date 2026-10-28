"""Health check endpoint."""

from __future__ import annotations

from fastapi import APIRouter

from app.schemas import HealthResponse

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse)
async def health_check() -> HealthResponse:
    """
    Health check endpoint.

    Returns:
        HealthResponse: Status and version of the application.
    """
    return HealthResponse(status="ok", version="0.1.0")
