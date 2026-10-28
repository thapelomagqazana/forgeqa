"""
ForgeQA Reference Application.

A small FastAPI application used as a test target for ForgeQA.
See examples/reference-app/README.md for the full scenario matrix.
"""

from __future__ import annotations

from fastapi import FastAPI

from app.routers import admin, health, records, ui

app = FastAPI(
    title="ForgeQA Reference App",
    description=(
        "A small, controlled test target for ForgeQA. " "See README.md for the scenario matrix."
    ),
    version="0.1.0",
)

# Register routers
app.include_router(health.router, prefix="/api")
app.include_router(records.router, prefix="/api")
app.include_router(admin.router, prefix="/api")
app.include_router(ui.router)


@app.get("/")
async def root() -> dict[str, str]:
    """Root endpoint for basic connectivity check."""
    return {"message": "ForgeQA Reference App. See /docs for API documentation."}
