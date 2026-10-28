# ForgeQA Reference Application

> **Project Status: Pre-alpha**
> **Version**: 0.1.0
> **Last Updated**: 2026-10-27
> **Owner**: Solo Developer

---

## Getting Started

### Prerequisites

- Python 3.11 or 3.12
- pip
- Make (optional, but recommended)
- Docker (optional, for containerised startup)

### Quick Start (Using Make)

```bash
cd examples/reference-app

# Install dependencies
make install

# Start the server
make run

# In a separate terminal, check the health endpoint
make health
```

### Quick Start (Manual)

```bash
cd examples/reference-app

# Create a virtual environment
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install dependencies
pip install -e ".[dev]"

# Start the server
uvicorn app.main:app --reload
```

### Quick Start (Using Docker)

```bash
cd examples/reference-app

# Build and start the container
make docker-up

# Or manually
docker compose up -d
```

### Available Make Targets

| Target | What It Does |
| :--- | :--- |
| `make install` | Create venv and install dependencies. |
| `make run` | Start the server at `http://127.0.0.1:8000`. |
| `make run-reload` | Start the server with auto-reload (development). |
| `make test` | Run all tests. |
| `make test-cov` | Run tests with coverage. |
| `make reset` | Reset the in-memory store via `POST /api/admin/reset`. |
| `make health` | Check the health endpoint. |
| `make clean` | Remove venv, caches, and build artifacts. |
| `make docker-build` | Build the Docker image. |
| `make docker-up` | Start the docker-compose stack. |
| `make docker-down` | Stop the docker-compose stack. |
| `make docker-logs` | View docker-compose logs. |
| `make help` | Show all available targets. |

### Base URLs

| URL | Description |
| :--- | :--- |
| `http://127.0.0.1:8000/api/health` | Health check endpoint (REF-01) |
| `http://127.0.0.1:8000/api/records/1` | Get a record (REF-02) |
| `http://127.0.0.1:8000/api/records/fail` | Deliberate failure (REF-05) |
| `http://127.0.0.1:8000/api/admin/reset` | Reset the in-memory store |
| `http://127.0.0.1:8000/ui/records` | Records UI (REF-06, REF-07, REF-08) |
| `http://127.0.0.1:8000/ui/fail` | Deliberate UI failure (REF-09) |
| `http://127.0.0.1:8000/docs` | Interactive API documentation (Swagger UI) |
| `http://127.0.0.1:8000/redoc` | Alternative API documentation (ReDoc) |

### Verify the Health Endpoint

```bash
# Using Make
make health

# Or manually
curl http://localhost:8000/api/health
# Expected: {"status":"ok","version":"0.1.0"}
```

### Reset the In-Memory Store

```bash
# Using Make
make reset

# Or manually
curl -X POST http://localhost:8000/api/admin/reset
# Expected: {"status":"ok","message":"Store reset to initial state","records_count":3}
```

### Run the Tests

```bash
# Using Make
make test

# Or manually
pytest tests/ -v
# Expected: 17 passed
```

### Stop the Application

- **Manual/Make**: Press `Ctrl+C` in the terminal.
- **Docker**: Run `make docker-down` or `docker compose down`.

---

## 1. Purpose

The Reference Application is a small, controlled test target used to validate ForgeQA's UI and API workflows. It is **not a second product**. Its job is to provide predictable success and failure scenarios so that:

- ForgeQA's fixtures, adapters, and diagnostics can be tested against a real application.
- Any failure in ForgeQA's tests can be distinguished from a failure in the application under test.
- The MVP acceptance criteria (Phase 0.3.5) can be validated end-to-end.

> **Rule**: Keep this application deliberately simple. Do not add features that are not needed by the scenario matrix below.

---

## 2. Technology Stack

| Layer | Technology | Purpose |
| :--- | :--- | :--- |
| **Framework** | FastAPI | Lightweight, type-safe, auto-documented (OpenAPI). |
| **Server** | Uvicorn | ASGI server for local development. |
| **Data** | In-memory list (`app/store.py`) | No database; resets on server restart or via `POST /api/admin/reset`. |
| **Templates** | Jinja2 | Minimal HTML for UI scenarios. |
| **Validation** | Pydantic | Request/response schema validation. |
| **Forms** | python-multipart | Required by FastAPI for form parsing. |

---

## 3. Reference Scenario Matrix

> **Legend**:
> - **REF-XX**: Scenario ID (from Project Brief Section 7.3).
> - **Type**: API or UI.
> - **Expected**: Exact HTTP status, payload, or UI state.
> - **Locators**: `data-testid` attributes for UI scenarios.
> - **Why It Matters**: The ForgeQA capability this scenario validates.

### 3.1 API Scenarios

#### REF-01: Health Check

| Attribute | Detail |
| :--- | :--- |
| **Type** | API |
| **Method** | `GET` |
| **Path** | `/api/health` |
| **Request Body** | None |
| **Expected Status** | `200 OK` |
| **Expected Payload** | `{"status": "ok", "version": "0.1.0"}` |
| **Expected Headers** | `Content-Type: application/json` |
| **Why It Matters** | Validates basic API execution and response assertions. |

**Test Contract:**
```python
def test_health(api_client):
    response = api_client.get("/api/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "version": "0.1.0"}
```

---

#### REF-02: Retrieve an Existing Record

| Attribute | Detail |
| :--- | :--- |
| **Type** | API |
| **Method** | `GET` |
| **Path** | `/api/records/1` |
| **Request Body** | None |
| **Expected Status** | `200 OK` |
| **Expected Payload** | `{"id": 1, "name": "Test Record 1", "status": "active"}` |
| **Why It Matters** | Validates response assertions and schema validation. |

**Test Contract:**
```python
def test_get_record(api_client):
    response = api_client.get("/api/records/1")
    assert response.status_code == 200
    payload = response.json()
    assert payload["id"] == 1
    assert payload["name"] == "Test Record 1"
    assert payload["status"] == "active"
```

---

#### REF-03: Submit Invalid Data (Validation Error)

| Attribute | Detail |
| :--- | :--- |
| **Type** | API |
| **Method** | `POST` |
| **Path** | `/api/records` |
| **Request Body** | `{"name": ""}` (empty name) |
| **Expected Status** | `422 Unprocessable Entity` |
| **Expected Payload** | `{"detail": [{"loc": ["body", "name"], "msg": "String should have at least 1 character", ...}]}` |
| **Why It Matters** | Validates error handling and Pydantic schema validation. |

**Test Contract:**
```python
def test_submit_invalid_record(api_client):
    response = api_client.post("/api/records", json={"name": ""})
    assert response.status_code == 422
    payload = response.json()
    assert "detail" in payload
    assert payload["detail"][0]["loc"] == ["body", "name"]
```

---

#### REF-04: Request an Unknown Record (404)

| Attribute | Detail |
| :--- | :--- |
| **Type** | API |
| **Method** | `GET` |
| **Path** | `/api/records/9999` |
| **Request Body** | None |
| **Expected Status** | `404 Not Found` |
| **Expected Payload** | `{"detail": "Record not found"}` |
| **Why It Matters** | Validates negative testing and status code assertions. |

**Test Contract:**
```python
def test_get_unknown_record(api_client):
    response = api_client.get("/api/records/9999")
    assert response.status_code == 404
    assert response.json() == {"detail": "Record not found"}
```

---

#### REF-05: Controllable Failure Scenario (500)

| Attribute | Detail |
| :--- | :--- |
| **Type** | API |
| **Method** | `GET` |
| **Path** | `/api/records/fail` |
| **Request Body** | None |
| **Expected Status** | `500 Internal Server Error` |
| **Expected Payload** | `{"detail": "Deliberate failure for diagnostics testing"}` |
| **Why It Matters** | Validates ForgeQA's failure diagnostics (request/response metadata, error classification) without relying on unstable external systems. |

**Test Contract:**
```python
def test_controllable_failure(api_client):
    response = api_client.get("/api/records/fail")
    assert response.status_code == 500
    assert response.json() == {"detail": "Deliberate failure for diagnostics testing"}
```

> **Design note**: This endpoint always returns 500. It is not a bug—it is intentionally designed to exercise ForgeQA's diagnostics path.

---

### 3.2 UI Scenarios

#### REF-06: Open the Record Page

| Attribute | Detail |
| :--- | :--- |
| **Type** | UI |
| **Method** | `GET` |
| **Path** | `/ui/records` |
| **Expected Page Title** | `"ForgeQA Reference App"` |
| **Expected Visible Text** | `"Test Record 1"` |
| **Locators** | `data-testid="record-list"`, `data-testid="record-item-1"` |
| **Why It Matters** | Validates browser lifecycle, page navigation, and locator strategies. |

**Test Contract:**
```python
def test_open_records_page(page):
    page.goto("/ui/records")
    assert page.title() == "ForgeQA Reference App"
    assert page.get_by_test_id("record-list").is_visible()
    assert page.get_by_test_id("record-item-1").text_content() == "Test Record 1"
```

---

#### REF-07: Submit Valid Form Data

| Attribute | Detail |
| :--- | :--- |
| **Type** | UI |
| **Method** | `POST` (via form submission) |
| **Path** | `/ui/records` (form action) |
| **Form Inputs** | `data-testid="name-input"`, `data-testid="submit-button"` |
| **Submitted Value** | `"New Test Record"` |
| **Expected UI State** | Success message visible: `data-testid="success-message"` with text `"Record created successfully"` |
| **Why It Matters** | Validates end-to-end UI workflow (form submission, success state). |

**Test Contract:**
```python
def test_submit_valid_form(page):
    page.goto("/ui/records")
    page.get_by_test_id("name-input").fill("New Test Record")
    page.get_by_test_id("submit-button").click()
    assert page.get_by_test_id("success-message").is_visible()
    assert page.get_by_test_id("success-message").text_content() == "Record created successfully"
```

---

#### REF-08: Submit Invalid Form Data (Validation Message)

| Attribute | Detail |
| :--- | :--- |
| **Type** | UI |
| **Method** | `POST` (via form submission) |
| **Path** | `/ui/records` (form action) |
| **Form Inputs** | `data-testid="name-input"`, `data-testid="submit-button"` |
| **Submitted Value** | `""` (empty) |
| **Expected UI State** | Validation message visible: `data-testid="validation-error"` with text `"Name is required"` |
| **Why It Matters** | Validates failure-state assertions (UI validation errors). |

**Test Contract:**
```python
def test_submit_invalid_form(page):
    page.goto("/ui/records")
    page.get_by_test_id("name-input").fill("")
    page.get_by_test_id("submit-button").click()
    assert page.get_by_test_id("validation-error").is_visible()
    assert page.get_by_test_id("validation-error").text_content() == "Name is required"
```

---

#### REF-09: Deliberate UI Failure (for Diagnostics)

| Attribute | Detail |
| :--- | :--- |
| **Type** | UI |
| **Method** | `GET` |
| **Path** | `/ui/fail` |
| **Expected Page Title** | `"ForgeQA Reference App"` |
| **Expected Visible Text** | `"This page intentionally fails"` |
| **Locators** | `data-testid="failure-heading"` |
| **Why It Matters** | Validates ForgeQA's screenshot and trace capture on failure. The test deliberately asserts the wrong text to trigger a failure. |

**Test Contract:**
```python
def test_deliberate_ui_failure(page):
    page.goto("/ui/fail")
    # This assertion will fail because the heading says "This page intentionally fails"
    assert page.get_by_test_id("failure-heading").text_content() == "This should not match"
```

> **Design note**: This page exists solely to trigger a deterministic failure for diagnostics testing. It should not be linked from the main UI.

---

## 4. Reset Endpoint

To reset the in-memory store to its initial state (3 seed records), call:

```bash
curl -X POST http://localhost:8000/api/admin/reset
```

Expected response:

```json
{
  "status": "ok",
  "message": "Store reset to initial state",
  "records_count": 3
}
```

> **Note**: This endpoint is intended for testing. It restores the 3 synthetic seed records and resets the next ID to 4. It is idempotent (calling it multiple times produces the same state).

---

## 5. Scenario Summary Table

| ID | Type | Method | Path | Expected Status / UI State | Why It Matters |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **REF-01** | API | GET | `/api/health` | 200, `{"status":"ok"}` | Basic API execution |
| **REF-02** | API | GET | `/api/records/1` | 200, `{"id":1,...}` | Response assertions |
| **REF-03** | API | POST | `/api/records` | 422, validation error | Error handling |
| **REF-04** | API | GET | `/api/records/9999` | 404, `{"detail":"..."}` | Negative testing |
| **REF-05** | API | GET | `/api/records/fail` | 500, `{"detail":"..."}` | Diagnostics |
| **REF-06** | UI | GET | `/ui/records` | Page title + visible text | Browser lifecycle |
| **REF-07** | UI | POST | `/ui/records` (form) | Success message visible | End-to-end UI workflow |
| **REF-08** | UI | POST | `/ui/records` (form) | Validation error visible | Failure-state assertions |
| **REF-09** | UI | GET | `/ui/fail` | Deliberate assertion failure | Screenshot/trace diagnostics |
| **RESET** | API | POST | `/api/admin/reset` | 200, `{"status":"ok",...}` | Deterministic test data |

---

## 6. UI Locator Convention

All interactive UI elements **must** use `data-testid` attributes. This provides stable, framework-agnostic locators that are resilient to CSS or text changes.

| Element | `data-testid` | Purpose |
| :--- | :--- | :--- |
| Record list container | `record-list` | Validates the list is visible. |
| Individual record item | `record-item-{id}` | Validates specific record content. |
| Name input field | `name-input` | Form submission. |
| Submit button | `submit-button` | Form submission. |
| Success message | `success-message` | Validates success state. |
| Validation error | `validation-error` | Validates error state. |
| Failure heading | `failure-heading` | Deliberate failure (REF-09). |

**Rule**: Do not use CSS selectors (`#id`, `.class`) or XPath in tests. Use `page.get_by_test_id("...")` exclusively.

---

## 7. Test Data

The application starts with a fixed set of synthetic records (defined in `app/store.py`):

```json
[
  {"id": 1, "name": "Test Record 1", "status": "active"},
  {"id": 2, "name": "Test Record 2", "status": "inactive"},
  {"id": 3, "name": "Test Record 3", "status": "active"}
]
```

**Rules:**
- All data is synthetic. No real personal information.
- The data resets on server restart.
- `POST /api/admin/reset` resets the data to this initial state.
- New records start at ID 4 and increment.

---

## 8. Controllable Failure Scenarios

| Scenario | Endpoint | Behaviour | Purpose |
| :--- | :--- | :--- | :--- |
| **API failure** | `GET /api/records/fail` | Always returns `500` with a specific message. | Test API diagnostics (request/response metadata). |
| **UI failure** | `GET /ui/fail` | Renders a page with a heading that does not match the test assertion. | Test screenshot and trace capture. |
| **Validation error** | `POST /api/records` with empty name | Returns `422` with Pydantic validation details. | Test error handling. |

---

## 9. Traceability Matrix: Scenarios → MVP Capabilities

> **Purpose**: This matrix maps each reference scenario (REF-01 to REF-09) to the specific ForgeQA MVP capability it validates. This ensures that every MVP capability has a concrete, executable test target.

### 9.1 Mapping Table

| Scenario ID | Reference Scenario | MVP Capability ID | MVP Capability Name | How It Validates the Capability |
| :--- | :--- | :--- | :--- | :--- |
| **REF-01** | Health API (`GET /api/health`) | **MVP-05** | HTTPX API Support | Validates that ForgeQA's `api_client` fixture can send a request and assert on a 200 response with a JSON payload. |
| **REF-02** | Get Record API (`GET /api/records/1`) | **MVP-05** | HTTPX API Support | Validates that ForgeQA's `api_client` can retrieve a resource and assert on specific response fields (id, name, status). |
| **REF-03** | Create Record API (`POST /api/records`) | **MVP-05** | HTTPX API Support | Validates that ForgeQA's `api_client` can submit data and assert on both valid (201) and invalid (422) responses. |
| **REF-04** | Unknown Record API (`GET /api/records/9999`) | **MVP-05** | HTTPX API Support | Validates that ForgeQA's `api_client` can handle 404 responses and assert on error payloads. |
| **REF-05** | Controllable API Failure (`GET /api/records/fail`) | **MVP-07** | Failure Diagnostics | Validates that ForgeQA captures sanitised request/response metadata (method, URL, status, duration) when an API call fails with a 500. |
| **REF-06** | Open Record Page (`GET /ui/records`) | **MVP-04** | Playwright UI Support | Validates that ForgeQA's `page` fixture can launch a browser, navigate to a page, and assert on page title and visible text using `data-testid` locators. |
| **REF-07** | Submit Valid Form (`POST /ui/records`) | **MVP-04** | Playwright UI Support | Validates that ForgeQA's `page` fixture can fill a form, click a button, and assert on a success state. |
| **REF-08** | Submit Invalid Form (`POST /ui/records`) | **MVP-04**, **MVP-07** | Playwright UI Support, Failure Diagnostics | Validates that ForgeQA can assert on a validation error state and capture a screenshot when the assertion fails. |
| **REF-09** | Deliberate UI Failure (`GET /ui/fail`) | **MVP-06**, **MVP-07** | Standard Result Output, Failure Diagnostics | Validates that ForgeQA produces JUnit XML, structured JSON, a screenshot, and a Playwright trace when a UI test fails deliberately. |
| **RESET** | Reset Endpoint (`POST /api/admin/reset`) | **MVP-02**, **MVP-06** | Pytest Integration, Standard Result Output | Validates that ForgeQA's fixtures can reset test data deterministically before each test, ensuring isolation and reproducible results. |

### 9.2 Coverage Summary

| MVP Capability ID | MVP Capability Name | Validated By Scenarios |
| :--- | :--- | :--- |
| **MVP-01** | Python Package & Installation | Validated by `make install` and `pip install -e ".[dev]"` (not a reference scenario; infrastructure-level validation). |
| **MVP-02** | Pytest Integration | **RESET** (deterministic fixtures), all scenarios (Pytest discovers and runs tests). |
| **MVP-03** | Validated Configuration | Not directly validated by a reference scenario; validated by ForgeQA's own config tests (Phase 1). |
| **MVP-04** | Playwright UI Support | **REF-06**, **REF-07**, **REF-08** |
| **MVP-05** | HTTPX API Support | **REF-01**, **REF-02**, **REF-03**, **REF-04** |
| **MVP-06** | Standard Result Output | **REF-09**, **RESET** |
| **MVP-07** | Failure Diagnostics | **REF-05**, **REF-08**, **REF-09** |
| **MVP-08** | GitHub Actions Workflow | Not directly validated by a reference scenario; validated by the CI workflow (WBS 0.5.7). |

### 9.3 Coverage Gaps

> The following MVP capabilities are **not** directly validated by a reference scenario. They are validated by infrastructure-level checks instead.

| MVP Capability | Reason for No Scenario | Validation Method |
| :--- | :--- | :--- |
| **MVP-01** (Package & Installation) | It is a prerequisite for running any scenario, not a testable behaviour. | `make install` succeeds in a clean environment. |
| **MVP-03** (Validated Configuration) | It is a framework-level concern, not an application-level behaviour. | ForgeQA's own config unit tests (Phase 1). |
| **MVP-08** (GitHub Actions Workflow) | It is a CI-level concern, not an application-level behaviour. | The `quality.yml` workflow passes on a PR (WBS 0.5.7). |

**Conclusion**: Every MVP capability has a concrete validation method. The reference scenarios cover 5 of 8 MVP capabilities directly; the remaining 3 are covered by infrastructure-level checks.

---

## 10. Project Structure

```
examples/reference-app/
├── app/
│   ├── __init__.py
│   ├── main.py              # FastAPI application
│   ├── schemas.py           # Pydantic request/response schemas
│   ├── store.py             # In-memory data store + reset()
│   ├── routers/
│   │   ├── __init__.py
│   │   ├── admin.py         # POST /api/admin/reset
│   │   ├── health.py        # GET /api/health (REF-01)
│   │   ├── records.py       # GET/POST /api/records (REF-02 to REF-05)
│   │   └── ui.py            # GET/POST /ui/records, GET /ui/fail (REF-06 to REF-09)
│   └── templates/
│       ├── base.html        # Base HTML layout
│       ├── records.html     # Records page (REF-06, REF-07, REF-08)
│       └── fail.html        # Deliberate failure page (REF-09)
├── tests/
│   ├── test_health.py       # REF-01
│   ├── test_records_api.py  # REF-02 to REF-05
│   ├── test_reset.py        # RESET (seed data, reset, idempotency)
│   └── test_ui.py           # REF-06 to REF-09
├── Makefile                 # Development shortcuts
├── Dockerfile               # Container image
├── docker-compose.yml       # Reproducible startup
├── .dockerignore            # Excludes unnecessary files
├── pyproject.toml           # Reference app dependencies
├── README.md                # This file
└── .gitignore               # Excludes .venv/, __pycache__, etc.
```

---

## 11. Document History

| Version | Date | Author | Changes |
| :--- | :--- | :--- | :--- |
| 0.1.0 | 2026-10-27 | Solo Dev | Initial scenario matrix created from Project Brief Section 7.3. |
| 0.1.1 | 2026-10-27 | Solo Dev | Added Getting Started section and project structure (WBS 0.6.2). |
| 0.1.2 | 2026-10-28 | Solo Dev | Added Reset Endpoint section and updated project structure (WBS 0.6.5). |
| 0.1.3 | 2026-10-28 | Solo Dev | Added Makefile, Docker setup, and base URL documentation (WBS 0.6.6). |
| 0.1.4 | 2026-10-28 | Solo Dev | Added Traceability Matrix: Scenarios → MVP Capabilities (WBS 0.6.8). |
