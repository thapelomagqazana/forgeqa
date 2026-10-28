# examples/reference-app/app/schemas.py
"""
Pydantic schemas for the reference application.

These schemas define the request and response contracts for the API.
They are validated automatically by FastAPI and documented in the OpenAPI schema.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    """Response schema for the health check endpoint (REF-01)."""

    status: str = Field(..., description="Health status")
    version: str = Field(..., description="Application version")


class RecordResponse(BaseModel):
    """Response schema for a single record (REF-02)."""

    id: int = Field(..., description="Unique record ID")
    name: str = Field(..., description="Record name")
    status: str = Field(..., description="Record status (active/inactive)")


class RecordCreate(BaseModel):
    """Request schema for creating a record (REF-03)."""

    name: str = Field(
        ...,
        min_length=1,
        description="Record name (required, must not be empty)",
    )


class ErrorResponse(BaseModel):
    """Response schema for error cases (REF-04, REF-05)."""

    detail: str = Field(..., description="Error message")
