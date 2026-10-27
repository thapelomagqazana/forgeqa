# ForgeQA - MVP User Journeys

> **Project Status: Pre-alpha**
> **Version**: 0.1.0
> **Last Updated**: 2026-10-27
> **Owner**: Solo Developer
> **Based on**: `docs/mvp-scope.md` (WBS 0.3.1), Project Brief (Section 4.3)

---

## 1. Purpose

This document defines the **six core user journeys** that a new user must be able to complete for ForgeQA's Phase 1 MVP to be considered successful. Each journey is written in **Context → Action → Expected Outcome** format so it can be directly converted into an end-to-end (E2E) acceptance test.

> **Guiding Principle**: These journeys describe the **user experience**, not the internal code architecture. If a user cannot complete these journeys, the MVP is not ready—regardless of how many features are implemented.

---

## 2. Journey Map Overview

| Journey ID | Journey | Linked Capabilities | Key Acceptance Criterion |
| :--- | :--- | :--- | :--- |
| **UJ-01** | Installation | MVP-01 | #1: Clean environment install |
| **UJ-02** | Configuration | MVP-03 | #8: Invalid config fails clearly |
| **UJ-03** | First UI Test | MVP-02, MVP-04 | #2: Sample UI test executes |
| **UJ-04** | First API Test | MVP-02, MVP-05 | #2: Sample API test executes |
| **UJ-05** | Failure Diagnosis | MVP-06, MVP-07 | #3, #4: Failing test produces evidence |
| **UJ-06** | CI Execution | MVP-08 | #7: CI passes/fails correctly |

---

## 3. Detailed User Journeys

### 3.1 Journey UJ-01: Installation

**Linked Capabilities**: MVP-01 (Python package and installation)
**Linked Acceptance Criterion**: #1 ("A new user can follow the quick start in a clean supported environment.")

| Step | Detail |
| :--- | :--- |
| **Context** | A Python QA engineer has heard about ForgeQA and wants to try it. They have Python 3.11+ installed on their machine and a terminal open. They do not have any prior ForgeQA configuration. |
| **Action** | The user runs `pip install forgeqa` in a clean virtual environment. Then they run `python -c "import forgeqa; print(forgeqa.__version__)"`. |
| **Expected Outcome** | The installation succeeds without errors. The version number (e.g., `0.1.0`) is printed. The user can see that ForgeQA is installed and importable. |
| **Failure Mode** | If the installation fails, the error message is clear and actionable (e.g., "Python 3.11+ required" or "Missing dependency: pytest"). |
| **E2E Test** | `test_installation.py`: Create a fresh venv, install ForgeQA, import it, and assert the version. |

---

### 3.2 Journey UJ-02: Configuration

**Linked Capabilities**: MVP-03 (Validated configuration)
**Linked Acceptance Criterion**: #8 ("Invalid configuration produces a clear, actionable error.")

| Step | Detail |
| :--- | :--- |
| **Context** | The user has installed ForgeQA and wants to configure it for their application. They have a web app running locally at `http://localhost:8000` and an API at `http://localhost:8000/api`. |
| **Action** | The user creates a `forgeqa.toml` file in their project root with the following content:<br><br>```toml<br>[general]<br>environment = "local"<br>artifacts_dir = "artifacts"<br><br>[browser]<br>browser_name = "chromium"<br>headless = true<br>timeout_ms = 10000<br><br>[api]<br>base_url = "http://localhost:8000/api"<br>```<br><br>Then they run `forgeqa config validate`. |
| **Expected Outcome** | The CLI outputs a success message: "Configuration is valid. Environment: local, Browser: chromium, API: http://localhost:8000/api." The user knows their configuration is correct. |
| **Failure Mode** | If the user writes `timeout_ms = "ten thousand"` (a string instead of a number), the CLI outputs: "Invalid configuration: timeout_ms must be an integer (got 'ten thousand'). Fix: set timeout_ms to a positive integer (e.g., 10000)." |
| **E2E Test** | `test_configuration.py`: Write a valid `forgeqa.toml`, run `forgeqa config validate`, assert success. Then write an invalid config, run the command, assert the error message. |

---

### 3.3 Journey UJ-03: First UI Test

**Linked Capabilities**: MVP-02 (Pytest integration), MVP-04 (Playwright UI support)
**Linked Acceptance Criterion**: #2 ("The sample UI and API tests execute successfully.")

| Step | Detail |
| :--- | :--- |
| **Context** | The user has configured ForgeQA and wants to write their first UI test. They have a simple web page with a heading and a button. |
| **Action** | The user creates `tests/test_ui.py` with the following content:<br><br>```python<br>def test_homepage(page):<br>    page.goto("/")<br>    assert page.title() == "My App"<br>    assert page.locator("h1").text_content() == "Welcome"<br>```<br><br>Then they run `pytest tests/test_ui.py`. |
| **Expected Outcome** | Pytest discovers the test, ForgeQA provides the `page` fixture, the browser launches (headless), the test navigates to the app, and the assertions pass. The output shows `1 passed`. |
| **Failure Mode** | If the page title does not match, Pytest reports a clear assertion error with the expected vs. actual value. A screenshot is captured (if diagnostics are enabled). |
| **E2E Test** | `test_first_ui.py`: Use the reference application, write a test using the `page` fixture, assert the page title. Run pytest and assert `1 passed`. |

---

### 3.4 Journey UJ-04: First API Test

**Linked Capabilities**: MVP-02 (Pytest integration), MVP-05 (HTTPX API support)
**Linked Acceptance Criterion**: #2 ("The sample UI and API tests execute successfully.")

| Step | Detail |
| :--- | :--- |
| **Context** | The user has configured ForgeQA and wants to write their first API test. They have an API with a health endpoint at `/api/health`. |
| **Action** | The user creates `tests/test_api.py` with the following content:<br><br>```python<br>def test_health(api_client):<br>    response = api_client.get("/health")<br>    assert response.status_code == 200<br>    assert response.json() == {"status": "ok"}<br>```<br><br>Then they run `pytest tests/test_api.py`. |
| **Expected Outcome** | Pytest discovers the test, ForgeQA provides the `api_client` fixture (configured with the `base_url` from `forgeqa.toml`), the HTTPX client sends the request, and the assertions pass. The output shows `1 passed`. |
| **Failure Mode** | If the API returns a 500, the test fails with a clear error showing the request method, URL, status code, and response body (sanitised). |
| **E2E Test** | `test_first_api.py`: Use the reference application, write a test using the `api_client` fixture, assert the status code and JSON body. Run pytest and assert `1 passed`. |

---

### 3.5 Journey UJ-05: Failure Diagnosis

**Linked Capabilities**: MVP-06 (Standard result output), MVP-07 (Failure diagnostics)
**Linked Acceptance Criterion**: #3 ("An intentionally failing test returns a failing process exit status.") and #4 ("Failure output identifies the failed test and provides available relevant evidence.")

| Step | Detail |
| :--- | :--- |
| **Context** | The user has written a UI test that is failing because the application has a bug (e.g., the heading text changed from "Welcome" to "Welcome!"). |
| **Action** | The user runs `pytest tests/test_ui.py`. The test fails. The user opens the `artifacts/` directory and inspects the generated files. |
| **Expected Outcome** | The test run produces:<br>1. A non-zero exit code.<br>2. A JUnit XML file (`artifacts/junit.xml`) with the failed test.<br>3. A structured JSON file (`artifacts/results.json`) with the failure details.<br>4. A screenshot (`artifacts/tests/<test_id>/failure.png`) showing the page state at the point of failure.<br>5. A Playwright trace (`artifacts/tests/<test_id>/trace.zip`) for deeper investigation.<br>The user can open the screenshot and see that the heading text is "Welcome!" instead of "Welcome", identifying the bug without re-running the test locally. |
| **Failure Mode** | If the screenshot or trace cannot be captured (e.g., browser crash), the original test failure is still reported. The missing evidence is noted in the structured output ("Artifact capture failed: browser context unavailable"). |
| **E2E Test** | `test_failure_diagnostics.py`: Use the reference application with a deliberate bug, write a test that fails, run pytest, and assert that the JUnit XML, structured JSON, screenshot, and trace are generated. |

---

### 3.6 Journey UJ-06: CI Execution

**Linked Capabilities**: MVP-08 (Reference GitHub Actions workflow)
**Linked Acceptance Criterion**: #7 ("The reference suite passes in local execution and CI under the same intended configuration.")

| Step | Detail |
| :--- | :--- |
| **Context** | The user has written UI and API tests locally and wants to run them in GitHub Actions on every push. |
| **Action** | The user copies the reference GitHub Actions workflow (`.github/workflows/forgeqa.yml`) into their repository, customises the environment variables (e.g., `FORGEQA_BASE_URL`), and pushes a commit to a branch. |
| **Expected Outcome** | GitHub Actions triggers the workflow, installs ForgeQA, installs the Playwright browser, starts the reference application, runs the test suite, and publishes the JUnit XML and diagnostic artifacts. If a test fails, the workflow fails with a red status. |
| **Failure Mode** | If the browser installation fails, the workflow logs a clear error (e.g., "Playwright browser installation failed. Check the runner OS and network."). If the reference application fails to start, the workflow logs the startup error and fails before running tests. |
| **E2E Test** | `test_ci_workflow.py`: Push a commit to the repository, wait for the GitHub Actions run, and assert that the workflow passes (or fails for a deliberate test failure). |

---

## 4. Journey-to-Acceptance-Criteria Coverage

> This matrix verifies that every acceptance criterion from the Project Brief (Section 4.3) is covered by at least one user journey.

| Acceptance Criterion (Project Brief 4.3) | Covered By |
| :--- | :--- |
| #1: A new user can follow the quick start in a clean supported environment. | UJ-01 |
| #2: The sample UI and API tests execute successfully. | UJ-03, UJ-04 |
| #3: An intentionally failing test returns a failing process exit status. | UJ-05 |
| #4: Failure output identifies the failed test and provides available relevant evidence. | UJ-05 |
| #5: Secrets and configured sensitive values are not exposed in captured artifacts. | UJ-05 (failure mode), UJ-06 (CI secrets) |
| #6: JUnit XML and the documented JSON format are generated consistently. | UJ-05 |
| #7: The reference suite passes in local execution and CI under the same intended configuration. | UJ-06 |
| #8: Invalid configuration produces a clear, actionable error. | UJ-02 |
| #9: All mandatory automated checks pass before a release candidate is accepted. | CI matrix (all journeys) |
| #10: At least one independent tester can follow the documented workflow without requiring undocumented assistance. | Covered by all journeys (E2E) |

---

## 5. Journey-to-Epic Mapping (Phase 1 Backlog)

> These journeys will be converted into Epics on the GitHub Project board when Phase 1 begins.

| Epic | Linked Journeys | Description |
| :--- | :--- | :--- |
| **Epic 1: Installation & Configuration** | UJ-01, UJ-02 | Package installation, `forgeqa.toml` configuration, validation. |
| **Epic 2: UI and API Fixtures** | UJ-03, UJ-04 | Playwright `page` fixture, HTTPX `api_client` fixture, pytest integration. |
| **Epic 3: Reporting & Diagnostics** | UJ-05 | JUnit XML, structured JSON, screenshots, traces, failure classification. |
| **Epic 4: CI/CD Integration** | UJ-06 | GitHub Actions workflow, artifact publication, exit codes. |

---

## 6. How to Use These Journeys

| Phase | Action |
| :--- | :--- |
| **Phase 1 (MVP Build)** | Convert each journey into an E2E acceptance test. These tests become the definition of done for Phase 1. |
| **Phase 1 Exit Gate** | A new user must be able to complete all six journeys without assistance. |
| **Design Partner Feedback (0.2.9)** | Share these journeys with Design Partners. Ask: "Would this workflow solve your problem?" |
| **Documentation** | Use these journeys as the structure for the README Quick Start guide. |

---

## 7. Document History

| Version | Date | Author | Changes |
| :--- | :--- | :--- | :--- |
| 0.1.0 | 2026-10-27 | Solo Dev | Initial journey definitions created from `docs/mvp-scope.md` (WBS 0.3.1). |
