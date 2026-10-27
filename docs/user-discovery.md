# ForgeQA - User Discovery

> **Project Status: Pre-alpha**
> **Version**: 0.1.0
> **Last Updated**: 2026-10-27
> **Owner**: Solo Developer

---

## 1. Primary Persona: The Python QA Engineer

> **Note:** This is an initial hypothesis based on the Project Brief. It will be validated during Phase 0.2 user interviews.

### 1.1 Profile

| Attribute | Description |
| :--- | :--- |
| **Role** | QA Engineer, SDET, or Automation Engineer |
| **Experience** | 2–5 years in test automation; comfortable with Python. |
| **Team Size** | Small-to-medium software team (3–15 engineers). |
| **Tech Stack** | Python, Pytest, Playwright, HTTPX, GitHub Actions. |
| **Daily Responsibilities** | Writing and maintaining automated tests, investigating CI failures, collaborating with developers on defect resolution, reporting test coverage to engineering leads. |
| **Current Workflow** | Builds test suites from scratch for each new project. Manages browser fixtures, API clients, test data, and reporting logic manually. Often duplicates utility functions across projects. Uses GitHub Actions for CI. |
| **Desired Outcome** | A reusable foundation that reduces setup and maintenance effort without restricting test design. |

### 1.2 Initial Use Case

> **"Onboarding a new API testing suite for a microservice."**

**Context:** The engineer has just been assigned to a new microservice project. The service has a REST API with a health endpoint, a record retrieval endpoint, and a form submission endpoint.

**Task:** They need to set up a repeatable test suite that validates the API's success and failure paths, runs in CI, and produces clear evidence when tests fail.

**Current Pain:** Without ForgeQA, the engineer must configure HTTPX clients, set up authentication, write custom response assertions, configure JUnit XML reporting, and wire it all into GitHub Actions — a process that takes 1–2 days before the first meaningful test is written.

### 1.3 Secondary Personas

| Persona | Primary Need |
| :--- | :--- |
| **Developers / Platform Engineers** | Integrate automated checks into pull requests, deployment pipelines, and application environments. |
| **Engineering Managers / QA Leads** | Define quality gates, review automation health, measure maintenance costs, and standardise practices across teams. |

---

## 2. Problem Statement (Draft — To Be Validated)

> **Status**: Draft hypothesis. To be validated in Phase 0.2 interviews.

### 2.1 The Statement

> **When** a Python QA engineer needs to set up automated testing for a new application or microservice, **they struggle with** rebuilding configuration, fixtures, API clients, browser lifecycle management, and CI reporting from scratch for every project, **causing** 1–2 days of lost setup time per project and recurring maintenance burden that diverts effort away from writing meaningful test coverage.

### 2.2 Breakdown of the Statement

| Component | Content | Rationale |
| :--- | :--- | :--- |
| **When (User)** | A Python QA engineer | Specific role, not a generic "tester." |
| **Needs to (Job)** | Set up automated testing for a new application or microservice | A concrete, recurring task that happens at the start of every project. |
| **Struggles with (Observed Problem)** | Rebuilding configuration, fixtures, API clients, browser lifecycle, and CI reporting from scratch | Multiple, specific pain points identified from the persona profile. |
| **Causing (Impact)** | 1–2 days of lost setup time per project and recurring maintenance burden | Quantifiable (time) and qualifiable (effort diversion). |

### 2.3 What This Statement Deliberately Avoids

| Avoided Phrase | Reason |
| :--- | :--- |
| "ForgeQA" | Naming the product creates solution bias during interviews. |
| "A new framework" | Interview subjects may answer to please the researcher rather than describe their real workflow. |
| "A better tool" | Vague and leading. |
| "An all-in-one platform" | Assumes the solution before the problem is validated. |

### 2.4 Open Questions for Interviews

> These questions will be asked during Phase 0.2 interviews (WBS 0.2.6) to validate the problem statement.

1. When you started your last automation project, how long did it take before you wrote your first meaningful test?
2. Which parts of the setup process did you have to build from scratch?
3. How often do you encounter setup and maintenance overhead in your current work?
4. What is the impact of that overhead on your team's delivery speed?
5. Have you tried to solve this problem with existing tools or templates? What worked and what did not?

### 2.5 Validation Criteria

| Criterion | Target |
| :--- | :--- |
| **Frequency** | At least 3 of 5 interviewees confirm setup overhead is a recurring pain point. |
| **Impact** | At least 2 interviewees quantify the impact as ≥1 day per project or ≥2 hours per week. |
| **Specificity** | At least 3 interviewees independently identify the same two pain points (e.g., fixtures and diagnostics). |
| **No Solution Bias** | Interviewees describe the problem in their own words without mentioning the framework being proposed. |

---

## 3. Hypotheses to Validate

> These hypotheses are tracked in `docs/risks.md` and will be validated through user interviews in Phase 0.2.

| ID | Hypothesis | Validation Method | Status |
| :--- | :--- | :--- | :--- |
| **H-01** | We believe QA engineers struggle with **fixture setup and lifecycle management** (e.g., browser contexts, API clients) because they must rebuild this infrastructure for every new project. | Conduct 5 user interviews in Phase 0.2. | Open |
| **H-02** | We believe QA engineers spend significant time **investigating CI failures** because current tools provide only a pass/fail status without sufficient diagnostic context (screenshots, traces, request/response metadata). | Conduct 5 user interviews in Phase 0.2. | Open |
| **H-03** | We believe QA engineers would adopt a framework that reduces **initial setup time** from days to hours, even if it requires them to write standard Pytest code. | Conduct 5 user interviews in Phase 0.2. | Open |

---

## 4. Interview Evidence (U-001 to U-010)

> This section will be populated after each interview using the template below.

### 4.1 Interview Template

```markdown
## Interview U-XXX

- **Date**: YYYY-MM-DD
- **Role**:
- **Experience with automation**:
- **Team context**:
- **Current stack**:
- **Existing framework or tools**:

### Recent Real Example

- **What happened**:
- **Frequency**:
- **Time or business impact**:

### Current Workaround

- **What the user does**:
- **What works**:
- **What remains painful**:

### Adoption Constraints

- **Required tools**:
- **Security or policy restrictions**:
- **Switching costs**:

### Evidence

- **Direct observations**:
- **Important quotes**:
- **Problem category**:
- **Confidence**: low / medium / high

### Follow-up

- **Willing to review prototype**: yes / no / unsure
- **Agreed next step**:
```

### 4.2 Completed Interviews

<!--
  Example entry (to be replaced with real data):

  ## Interview U-001

  - **Date**: 2026-10-28
  - **Role**: Senior QA Engineer
  - **Experience with automation**: 4 years
  - **Team context**: 8-person engineering team
  - **Current stack**: Python, Pytest, Playwright, GitHub Actions
  - **Existing framework or tools**: Custom in-house framework

  ### Recent Real Example

  - **What happened**: A login test failed in CI after a dependency upgrade. The team spent 3 hours investigating because the only output was "Element not found."
  - **Frequency**: Weekly
  - **Time or business impact**: 3–5 hours per week across the team.

  ### Current Workaround

  - **What the user does**: Adds manual `print()` statements and re-runs the test locally.
  - **What works**: Eventually finds the issue.
  - **What remains painful**: No automated diagnostics; the feedback loop is slow.

  ### Adoption Constraints

  - **Required tools**: Must integrate with existing Pytest suite.
  - **Security or policy restrictions**: No external SaaS tools allowed.
  - **Switching costs**: Team is comfortable with Pytest; any new tool must be Pytest-native.

  ### Evidence

  - **Direct observations**: Showed a screenshot of a failed CI run with minimal error context.
  - **Important quotes**: "We spend more time investigating why a test failed than writing new tests."
  - **Problem category**: Diagnostics, Failure Investigation.
  - **Confidence**: High

  ### Follow-up

  - **Willing to review prototype**: Yes
  - **Agreed next step**: Schedule a follow-up call in 4 weeks.
-->
```

---

## 5. Interview Analysis Summary

> This section will be populated after all interviews are completed (WBS 0.2.7).

| Theme | Frequency | Supporting Interviews | Impact Description | Priority Score |
| :--- | :--- | :--- | :--- | :--- |
| Setup Friction | TBD | TBD | TBD | TBD |
| Flaky Test Investigation | TBD | TBD | TBD | TBD |
| Diagnostic Gaps | TBD | TBD | TBD | TBD |
| Test Data Management | TBD | TBD | TBD | TBD |

---

## 6. Problem Validation Scoring

> This section will be populated in WBS 0.2.8 using the formula from the Project Brief.

| Problem ID | Description | Frequency (1-5) | Severity (1-5) | Workaround Cost (1-5) | Product Fit (1-5) | Score |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| P-01 | Setup friction | TBD | TBD | TBD | TBD | TBD |
| P-02 | Flaky test investigation | TBD | TBD | TBD | TBD | TBD |
| P-03 | Diagnostic gaps | TBD | TBD | TBD | TBD | TBD |

---

## 7. Design Partner Pipeline

> This section will be populated in WBS 0.2.9.

| Name | Role | Company | Status | Commitment Level |
| :--- | :--- | :--- | :--- | :--- |
| TBD | TBD | TBD | TBD | TBD |

---

## 8. Document History

| Version | Date | Author | Changes |
| :--- | :--- | :--- | :--- |
| 0.1.0 | 2026-10-27 | Solo Dev | Initial draft created from Project Brief and persona hypothesis. |
| 0.1.1 | 2026-10-27 | Solo Dev | Added testable problem statement (WBS 0.2.2) and validation criteria. |

---

*This document is a living artifact. It will be updated after each user interview (Phase 0.2.6) and synthesised in Phase 0.2.7.*
