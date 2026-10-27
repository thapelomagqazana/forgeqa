# ForgeQA - Product Requirements

> **Project Status: Pre-alpha**
> **Version**: 0.1.0
> **Last Updated**: 2026-10-27
> **Owner**: Solo Developer

---

## 1. Executive Summary

### 1.1 Product Name
**ForgeQA** — Enterprise Test Automation Framework

### 1.2 Product Vision
Build a reusable, extensible, technology-aware test automation framework that enables organisations to create, execute, maintain, analyse, and scale automated tests across multiple applications, teams, and environments without rebuilding their testing infrastructure for every project.

ForgeQA is envisioned as an **engineering platform** rather than a collection of test scripts. It provides a common foundation for UI testing, API testing, database validation, integration testing, and end-to-end testing, with standardised conventions for test design, configuration, reporting, failure handling, test data, and CI/CD integration.

### 1.3 Core Principle
> **Standardise the infrastructure, not every test.**

Teams should share proven engineering capabilities while retaining the freedom to test their applications according to their specific requirements.

---

## 2. The Problem Statement

### 2.1 Current State
Many organisations build automation incrementally. One team uses Selenium, another uses Playwright, and a third maintains API tests using custom HTTP clients. Each project develops its own configuration, authentication helpers, reporting conventions, test-data setup, and CI/CD pipeline.

This creates recurring problems:

| Problem | Description |
| :--- | :--- |
| **Duplicated engineering effort** | Teams repeatedly build the same utilities, authentication flows, API clients, fixtures, and reporting logic. |
| **Fragile and expensive maintenance** | Poor abstractions, brittle selectors, arbitrary waits, and tightly coupled tests cause frequent failures and expensive repairs. |
| **Inconsistent execution** | Different teams produce different reports, use different environment conventions, and apply different quality gates. |
| **Poor failure investigation** | A failed pipeline may reveal only that a test failed, without sufficient context to identify the application defect, environment issue, test-data problem, or automation defect. |
| **Governance and security gaps** | Secrets may be mishandled, sensitive test data may leak into reports, and teams may lack traceability between requirements, tests, and releases. |

### 2.2 The Opportunity
Develop a common automation foundation that reduces repeated engineering work, improves execution reliability, and turns test results into consistent, actionable engineering evidence.

### 2.3 Problem Statement (Draft — To Be Validated in Phase 0.2)
> *"When a QA engineer needs to set up automated testing for a new application, they struggle with rebuilding configuration, fixtures, reporting, and CI integration from scratch, causing delays in test coverage and increased maintenance burden."*

---

## 3. Target Users & Personas

### 3.1 Primary Persona (Hypothesis — To Be Validated)

| Attribute | Description |
| :--- | :--- |
| **Role** | Python QA Engineer, SDET, or Automation Engineer |
| **Team Context** | Small-to-medium software team (3–15 engineers) |
| **Current Workflow** | Pytest-based UI/API automation, often with GitHub Actions CI |
| **Candidate Pain** | Repeated framework setup, inconsistent fixtures, unreliable tests, fragmented failure evidence, and duplicated utilities |
| **Initial Environment** | Python, Pytest, Playwright, HTTPX, GitHub Actions |
| **Desired Outcome** | A reusable foundation that reduces setup and maintenance effort without restricting test design |

### 3.2 Secondary Personas

| Persona | Primary Need |
| :--- | :--- |
| **Developers / Platform Engineers** | Integrate automated checks into pull requests, deployment pipelines, and application environments. |
| **Engineering Managers / QA Leads** | Define quality gates, review automation health, measure maintenance costs, and standardise practices across teams. |

---

## 4. MVP Scope (Phase 1)

### 4.1 MVP Capability List

| ID | Capability | Priority | Acceptance Condition | Rationale |
| :--- | :--- | :--- | :--- | :--- |
| **MVP-01** | Python package and installation | **Must** | A clean environment can install ForgeQA using documented instructions. | Foundation for all other capabilities. |
| **MVP-02** | Pytest integration | **Must** | A new test can use ForgeQA-supported fixtures. | Core execution engine and lifecycle management. |
| **MVP-03** | Validated configuration | **Must** | Invalid configuration fails clearly before test execution where practical. | Prevents silent misconfiguration and early failures. |
| **MVP-04** | Playwright UI support | **Must** | A sample UI test executes and produces actionable failure evidence. | Addresses primary use case (UI testing). |
| **MVP-05** | HTTPX API support | **Must** | A sample API test executes with useful request/response diagnostics. | Addresses secondary use case (API testing). |
| **MVP-06** | Standard result output | **Must** | Test execution produces JUnit XML and a versioned structured JSON result. | Enables CI integration and future analytics. |
| **MVP-07** | Failure diagnostics | **Must** | A deliberate failure creates useful, sanitised diagnostic output. | Core differentiator: evidence-first approach. |
| **MVP-08** | GitHub Actions workflow | **Must** | The reference suite runs in CI and exposes the result artifacts. | Proves CI/CD readiness. |
| **MVP-09** | CLI project scaffolding | **Could** | Include in Phase 1 only if discovery shows it is essential to the first successful workflow. | Improves developer experience but not essential for MVP validation. |

### 4.2 Explicit Exclusions (Deferred to Later Phases)

| Capability | Decision | Rationale | Reconsideration Trigger |
| :--- | :--- | :--- | :--- |
| **Database adapter** | Defer to Phase 6 | Requires validated user workflows. | 3+ users request database validation. |
| **Team dashboard** | Defer to Phase 10 | Requires evidence that CI artifacts alone are insufficient. | 2+ design partners request shared history. |
| **AI failure analysis** | Defer to Phase 9+ | Requires validated problem, measurable benefit, and suitable data controls. | Deterministic analytics prove insufficient. |
| **Multi-language support** | Defer indefinitely | Multiplies maintenance and compatibility complexity. | A concrete user requirement justifies the investment. |
| **Distributed execution** | Defer indefinitely | Not needed for initial adoption. | Measured performance requirements justify it. |

---

## 5. Core User Journeys (Phase 1)

| ID | Journey | Expected Outcome |
| :--- | :--- | :--- |
| **UJ-01** | **Installation** | User runs `pip install forgeqa` in a clean environment and verifies the installation. |
| **UJ-02** | **Configuration** | User creates a `forgeqa.toml` file and runs `forgeqa config validate` to confirm settings are correct. |
| **UJ-03** | **First UI Test** | User writes a Playwright test using ForgeQA fixtures and runs it successfully. |
| **UJ-04** | **First API Test** | User writes an HTTPX test using ForgeQA fixtures and runs it successfully. |
| **UJ-05** | **Failure Diagnosis** | User deliberately fails a test and inspects the generated screenshot, trace, and structured error output. |
| **UJ-06** | **CI Execution** | User pushes code to GitHub and observes the test suite running in GitHub Actions with artifacts published. |

---

## 6. Functional Requirements

| ID | Requirement | Priority | Phase |
| :--- | :--- | :--- | :--- |
| FR-001 | Generate a working project from a maintained template. | P0 | Phase 2 |
| FR-002 | Validate configuration and support named environments. | P0 | Phase 1 |
| FR-003 | Provide standard test fixtures and lifecycle management. | P0 | Phase 1 |
| FR-004 | Support reliable browser automation through Playwright. | P0 | Phase 1 |
| FR-005 | Support reusable API clients and response assertions. | P0 | Phase 1 |
| FR-006 | Produce standard machine-readable test results. | P0 | Phase 1 |
| FR-007 | Capture failure diagnostics automatically. | P0 | Phase 1 |
| FR-008 | Integrate with a reference GitHub Actions pipeline. | P0 | Phase 1 |
| FR-009 | Support test markers, selective execution, and parametrisation. | P1 | Phase 4 |
| FR-010 | Provide test-data factories and isolation conventions. | P1 | Phase 5 |
| FR-011 | Support database validation through an optional adapter. | P1 | Phase 6 |
| FR-012 | Provide configurable parallel execution. | P1 | Phase 4 |
| FR-013 | Support additional reporters and tool adapters. | P1 | Phase 7 |
| FR-014 | Provide a framework upgrade and compatibility policy. | P1 | Phase 12 |
| FR-015 | Publish historical execution metrics and a dashboard. | P2 | Phase 9/10 |
| FR-016 | Integrate with test-management systems and evidence platforms. | P2 | Later |
| FR-017 | Add advanced failure analytics and optional intelligent triage. | P2 | Later |

---

## 7. Non-Functional Requirements

| Area | Requirement | Acceptance Target |
| :--- | :--- | :--- |
| **Reliability** | A framework defect must not silently convert a failed test into a pass. | Retries disabled by default; attempt history preserved. |
| **Determinism** | Fixed inputs and controlled dependencies should produce reproducible outcomes. | Test suite passes consistently in supported environments. |
| **Maintainability** | Modules have defined responsibilities, documented interfaces, and automated tests. | Core modules have >80% test coverage. |
| **Performance** | Measure framework overhead separately from application response time. | Baseline established in Phase 1; no arbitrary targets before measurement. |
| **Scalability** | Support isolated parallel workers and configurable execution limits. | Parallel execution tested in Phase 4. |
| **Portability** | Run locally and in supported CI environments without hard-coded machine-specific paths. | Clean install works on Linux, macOS, Windows. |
| **Security** | Secrets are injected securely and never deliberately printed in logs or reports. | Redaction tests pass in Phase 3/8. |

---

## 8. Success Metrics (Phase 1 Exit Criteria)

| Metric | Target |
| :--- | :--- |
| **Project onboarding** | A new user can generate and run the example project using the documented quick start. |
| **Reusability** | At least two independent example applications use the same framework core. |
| **Framework reliability** | Framework unit and integration tests pass consistently in supported environments. |
| **Diagnostic completeness** | Failed UI tests produce the expected screenshot, trace, and structured failure metadata when capture is enabled. |
| **Result integrity** | Failed tests cannot be silently represented as passed because of retries or reporting errors. |
| **CI compatibility** | The reference pipeline publishes machine-readable results and enforces configured quality gates. |
| **Configuration safety** | Invalid settings and missing mandatory values produce clear, actionable errors. |
| **Security** | Automated checks and manual review find no unresolved critical issues in the release scope. |
| **Maintainability** | Core modules have documented interfaces and meaningful automated test coverage. |
| **Adoption** | Pilot teams can add new application tests without modifying framework internals. |

---

## 9. Out of Scope (ForgeQA v1)

The following are explicitly **not** part of the initial release:

- Hosted dashboards or SaaS platform.
- Distributed execution or remote worker scheduling.
- Multi-language support (only Python in v1).
- AI-based root cause analysis.
- Plugin marketplace or third-party extension discovery.
- Organisation-level access control and audit.
- Mobile automation (Appium) or alternative browser engines (Selenium).

---

## 10. Assumptions & Dependencies

| ID | Assumption / Dependency | Validation Method |
| :--- | :--- | :--- |
| A-01 | Python QA engineers are the primary initial user group. | Phase 0.2 interviews. |
| A-02 | Playwright and Pytest are acceptable foundational tools. | Phase 0.4 ADR review. |
| A-03 | Users will adopt a framework that requires them to write standard Pytest code. | Phase 1 onboarding feedback. |
| A-04 | GitHub Actions is the primary CI platform for initial users. | Phase 0.2 interviews. |
| A-05 | Users will tolerate a slightly longer initial setup if maintenance is reduced. | Phase 1 user testing. |

---

## 11. Open Questions (To Be Resolved in Phase 0)

| ID | Question | Owner | Target Resolution |
| :--- | :--- | :--- | :--- |
| Q-01 | Do users prefer a CLI-based project generator, or is a copy-paste template sufficient? | Solo Dev | Phase 0.2 |
| Q-02 | Is database validation a Phase 1 requirement for the target user? | Solo Dev | Phase 0.2 |
| Q-03 | What is the acceptable framework overhead for a typical UI test? | Solo Dev | Phase 1 baseline |
| Q-04 | Do users require parallel execution in the initial release? | Solo Dev | Phase 0.2 |

---

## 12. Document History

| Version | Date | Author | Changes |
| :--- | :--- | :--- | :--- |
| 0.1.0 | 2026-10-27 | Solo Dev | Initial draft created from Project Brief. |

---

*This document is a living artifact. It will be updated as user discovery (Phase 0.2) and MVP definition (Phase 0.3) are completed.*
