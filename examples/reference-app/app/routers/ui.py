"""
UI routes for the reference application.

Implements REF-06 (records page), REF-07 (valid form submission),
REF-08 (invalid form submission), and REF-09 (deliberate failure).

Uses Jinja2 templates with data-testid attributes for stable Playwright locators.
Data is managed by app/store.py.
"""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from app import store

router = APIRouter(prefix="/ui", tags=["ui"])

# Template directory (relative to this file)
TEMPLATES_DIR = Path(__file__).parent.parent / "templates"
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))


# =============================================================================
# REF-06: Display records list and create form
# =============================================================================


@router.get("/records", response_class=HTMLResponse)
async def records_page(request: Request) -> HTMLResponse:
    """REF-06: Display the records list and the create form."""
    return templates.TemplateResponse(
        request=request,
        name="records.html",
        context={
            "records": store.get_all_records(),
            "success_message": None,
            "error_message": None,
        },
    )


# =============================================================================
# REF-07 / REF-08: Handle form submission
# =============================================================================


@router.post("/records", response_class=HTMLResponse)
async def create_record_form(
    request: Request,
    name: str = Form(default=""),
) -> HTMLResponse:
    """
    Handle form submission.

    - **Valid input** (`name` is non-empty): add the record and show a success message (REF-07).
    - **Invalid input** (`name` is empty): show a validation error (REF-08).
    """
    # REF-08: Validation error
    if not name.strip():
        return templates.TemplateResponse(
            request=request,
            name="records.html",
            context={
                "records": store.get_all_records(),
                "success_message": None,
                "error_message": "Name is required",
            },
            status_code=422,
        )

    # REF-07: Valid submission
    store.add_record(name=name.strip())

    return templates.TemplateResponse(
        request=request,
        name="records.html",
        context={
            "records": store.get_all_records(),
            "success_message": "Record created successfully",
            "error_message": None,
        },
    )


# =============================================================================
# REF-09: Deliberate failure page
# =============================================================================


@router.get("/fail", response_class=HTMLResponse)
async def fail_page(request: Request) -> HTMLResponse:
    """REF-09: Render a page that intentionally fails assertions."""
    return templates.TemplateResponse(
        request=request,
        name="fail.html",
        context={},
    )
