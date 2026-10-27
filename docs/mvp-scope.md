# ForgeQA - MVP Scope

> **Project Status: Pre-alpha**
> **Version**: 0.1.0
> **Last Updated**: 2026-10-27
> **Owner**: Solo Developer
> **Based on**: Phase 0.2 User Discovery (`docs/user-discovery-analysis.md`)

---

## 1. Purpose

This document defines the **Minimum Viable Product (MVP)** scope for ForgeQA. Every proposed capability is traced back to a validated user problem from Phase 0.2. If a capability cannot be traced to a validated problem, it is either deferred or excluded.

> **Guiding Principle**: Build only what solves a validated problem. Defer everything else.

---

## 2. Problem-to-Requirement Traceability Matrix

> **Instructions**: This matrix links each validated problem (from `docs/user-discovery-analysis.md`) to the user job it addresses, the observable outcome, and the proposed MVP capability.

| Problem ID | Problem Description (from Phase 0.2) | Problem Score | User Job | Observable Outcome | Proposed Capability | Priority |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **T-01** | Setup Friction: Rebuilding configuration, fixtures, API clients, browser lifecycle, and CI reporting from scratch for every project. | 5.0 | Set up a new automation project for a web application or API. | User writes a passing UI or API test within 10 minutes of installation, without writing custom fixture code. | **MVP-01**: Python package and installation<br>**MVP-02**: Pytest integration (standard fixtures)<br>**MVP-03**: Validated configuration | Must |
| **T-01** | Setup Friction (continued). | 5.0 | Configure the framework for a new environment (local, CI). | User creates a `forgeqa.toml` file, and invalid settings fail with a clear error message before test execution. | **MVP-03**: Validated configuration | Must |
| **T-02** | Diagnostic Gaps: Insufficient context (screenshots, traces, request/response metadata) to investigate test failures. | 4.75 | Investigate why a UI test failed in CI. | User opens the JUnit XML and structured JSON result, finds a screenshot and trace of the failed test, and identifies the root cause without re-running the test locally. | **MVP-06**: Standard result output (JUnit XML + versioned JSON)<br>**MVP-07**: Failure diagnostics (screenshots, traces) | Must |
| **T-02** | Diagnostic Gaps (continued). | 4.75 | Investigate why an API test failed. | User opens the structured result and finds sanitised request/response metadata (method, URL, status, duration) without exposing secrets. | **MVP-07**: Failure diagnostics (API metadata) | Must |
| **T-05** | CI/CD Integration Complexity: Effort required to configure CI pipelines, manage secrets, and publish test results. | 3.25 | Run the test suite in GitHub Actions. | User pushes code to a branch, and the GitHub Actions workflow runs the test suite, publishes JUnit XML, and fails the job if tests fail. | **MVP-08**: Reference GitHub Actions workflow | Must |
| **T-03** | Flaky Test Investigation: Tests that pass and fail intermittently. | 3.75 | Isolate tests to prevent shared-state failures. | Tests run in isolated browser contexts and use unique test data, reducing cross-test contamination. | **MVP-04**: Playwright UI support (browser context isolation)<br>**MVP-05**: HTTPX API support (client isolation) | Must (partial) |
| **T-04** | Test Data Management: Difficulty creating, isolating, and cleaning up test data. | 3.5 | Create and clean up test data without collisions. | User can generate unique test data and clean it up without manual database resets. | **MVP-04**: Playwright UI support (isolation only)<br>**MVP-05**: HTTPX API support (isolation only) | Must (partial) |
| **Essential** | Technical requirement: Framework must be installable and distributable. | N/A | Install the framework in a clean environment. | `pip install forgeqa` succeeds; `import forgeqa` works. | **MVP-01**: Python package and installation | Must |
| **Essential** | Technical requirement: Tests must be runnable via Pytest (the established test runner). | N/A | Run tests using standard Pytest commands. | `pytest` discovers and runs ForgeQA tests without custom configuration. | **MVP-02**: Pytest integration | Must |
| **Essential** | Technical requirement: Results must be machine-readable for CI integration. | N/A | Consume test results in a CI platform. | JUnit XML is generated and parseable by GitHub Actions. | **MVP-06**: Standard result output | Must |

### 2.1 Legend

| Symbol | Meaning |
| :--- | :--- |
| **T-XX** | Theme ID from `docs/user-discovery-analysis.md` |
| **Essential** | Technical requirement not directly tied to a user pain point but essential for the MVP to function. |
| **Must** | Required for the MVP (Phase 1). |
| **Could** | Included only if discovery shows it is essential to the first successful workflow. |
| **Defer** | Not included in Phase 1; tracked for future phases. |

---

## 3. Capability Summary

| Capability ID | Capability | Linked Problems | Priority | Rationale |
| :--- | :--- | :--- | :--- | :--- |
| **MVP-01** | Python package and installation | T-01, Essential | Must | Foundation for all other capabilities. |
| **MVP-02** | Pytest integration (standard fixtures) | T-01, Essential | Must | Reduces setup friction; enables standard test execution. |
| **MVP-03** | Validated configuration | T-01 | Must | Prevents silent misconfiguration; provides clear errors. |
| **MVP-04** | Playwright UI support (isolated contexts) | T-01, T-03, T-04 | Must | Addresses primary use case (UI testing) and isolation. |
| **MVP-05** | HTTPX API support (isolated clients) | T-01, T-03, T-04 | Must | Addresses secondary use case (API testing) and isolation. |
| **MVP-06** | Standard result output (JUnit XML + JSON) | T-02, Essential | Must | Enables CI integration and future analytics. |
| **MVP-07** | Failure diagnostics (screenshots, traces, API metadata) | T-02 | Must | Core differentiator: evidence-first approach. |
| **MVP-08** | Reference GitHub Actions workflow | T-05 | Must | Proves CI/CD readiness; reduces setup friction. |

---

## 4. Deferred Capabilities (Not in MVP)

> These capabilities are **not** included in Phase 1. They are tracked here to prevent scope creep and to document the rationale for deferral.

| Capability | Linked Problem (if any) | Rationale for Deferral | Reconsideration Trigger |
| :--- | :--- | :--- | :--- |
| **CLI project scaffolding** | T-01 | Not essential for the first successful workflow. Users can copy the reference project structure. | 3+ design partners request it; Phase 2. |
| **Database adapter** | T-04 (Test Data) | Requires validated user workflows; not all users need database testing. | 3+ users request database validation; Phase 6. |
| **Parallel execution** | T-03 (Flaky Tests) | Isolation can be achieved with separate browser contexts; parallel execution adds complexity. | Performance requirements justify it; Phase 4. |
| **Advanced flakiness metrics** | T-03 | Requires historical data collection and analysis. | Phase 5. |
| **Test data factories** | T-04 | Can be deferred; users can write their own factories initially. | Phase 6. |
| **Allure reporting** | T-02 | JUnit XML + JSON is sufficient for MVP; Allure is an optional enhancement. | 3+ users request Allure; Phase 3. |
| **Team dashboard** | T-02 | Requires evidence that CI artifacts alone are insufficient. | 2+ design partners request shared history; Phase 10. |
| **AI failure analysis** | T-02 | Requires validated problem, measurable benefit, and suitable data controls. | Phase 9+. |
| **Multi-language support** | N/A | Multiplies maintenance and compatibility complexity. | A concrete user requirement justifies the investment. |
| **Mobile automation (Appium)** | N/A | Requires additional infrastructure and is not core to the initial user. | A concrete user requirement justifies the investment; Phase 7. |
| **Alternative browser automation (Selenium)** | N/A | Playwright covers the initial use case; Selenium adds maintenance burden. | A concrete user requirement justifies the investment; Phase 7. |

---

## 5. Traceability to Phase 0.2 Evidence

> This section links each MVP capability back to the specific interview evidence and thematic analysis.

| Capability ID | Theme ID | Supporting Interviews | Representative Quote |
| :--- | :--- | :--- | :--- |
| **MVP-02** (Pytest fixtures) | T-01 | U-001, U-002, U-004, U-005, U-006, U-008, U-009 | *"I've built the same fixture setup three times in the last two years."* — U-001 |
| **MVP-03** (Validated config) | T-01 | U-002, U-004, U-006 | *"Half the time, a test fails because someone forgot to set the base URL."* — U-004 |
| **MVP-04** (Playwright isolation) | T-01, T-03, T-04 | U-001, U-003, U-006 | *"Browser state leaks between tests because we reuse the same context."* — U-003 |
| **MVP-05** (HTTPX isolation) | T-01, T-03, T-04 | U-002, U-005, U-007 | *"Tests collide because they all use the same test user account."* — U-005 |
| **MVP-06** (JUnit XML + JSON) | T-02 | U-001, U-003, U-004 | *"Getting the JUnit XML report into GitHub Actions was a two-day task."* — U-004 |
| **MVP-07** (Failure diagnostics) | T-02 | U-001, U-003, U-005, U-007 | *"We spend more time investigating why a test failed than writing new tests."* — U-001 |
| **MVP-08** (GitHub Actions) | T-05 | U-001, U-004, U-010 | *"Getting the JUnit XML report into GitHub Actions was a two-day task."* — U-004 |

---

## 6. MVP User Journeys

> These journeys define the end-to-end workflows that the MVP must support. Each journey is linked to the capabilities that enable it.

| Journey ID | Journey | Linked Capabilities | Expected Outcome |
| :--- | :--- | :--- | :--- |
| **UJ-01** | **Installation**: User installs ForgeQA in a clean environment. | MVP-01 | `pip install forgeqa` succeeds; `import forgeqa` works. |
| **UJ-02** | **Configuration**: User creates a `forgeqa.toml` and runs `forgeqa config validate`. | MVP-03 | Valid settings pass; invalid settings fail with clear errors. |
| **UJ-03** | **First UI Test**: User writes a Playwright test using ForgeQA fixtures and runs it. | MVP-02, MVP-04 | Test passes; browser context is isolated. |
| **UJ-04** | **First API Test**: User writes an HTTPX test using ForgeQA fixtures and runs it. | MVP-02, MVP-05 | Test passes; API client is isolated. |
| **UJ-05** | **Failure Diagnosis**: User deliberately fails a test and inspects the generated evidence. | MVP-06, MVP-07 | JUnit XML, structured JSON, screenshot, and trace are generated. |
| **UJ-06** | **CI Execution**: User pushes code to GitHub and observes the test suite running in GitHub Actions. | MVP-08 | Workflow runs, JUnit XML is published, and job fails if tests fail. |

---

## 7. Open Questions

| ID | Question | Target Resolution |
| :--- | :--- | :--- |
| Q-01 | Is the CLI project generator essential for the first successful workflow? | WBS 0.3.3 (MoSCoW Prioritisation) |
| Q-02 | Do design partners require parallel execution in the MVP? | WBS 0.2.9 (Design Partner feedback) |
| Q-03 | What is the acceptable framework overhead for a typical UI test? | Phase 1 baseline measurement |

---

## 8. Document History

| Version | Date | Author | Changes |
| :--- | :--- | :--- | :--- |
| 0.1.0 | 2026-10-27 | Solo Dev | Initial MVP scope created from Phase 0.2 discovery evidence. |
