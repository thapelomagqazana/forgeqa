# ForgeQA - Risk & Hypothesis Register

> **Project Status: Pre-alpha**
> **Version**: 0.1.0
> **Last Updated**: 2026-10-27
> **Owner**: Solo Developer

---

## 1. Technical Risks

> Technical risks are internal engineering challenges that could delay the project, degrade quality, or create maintenance burden. Each risk is scored using a 1–5 scale for **Likelihood** and **Impact**.

| ID | Risk | Likelihood (1-5) | Impact (1-5) | Mitigation Strategy | Status |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **R-01** | Pytest lifecycle leaks cause flaky tests (e.g., unclosed browser contexts, orphaned API clients). | 3 | 5 | Implement strict fixture teardown tests in Phase 1. Ensure every fixture uses `yield` and `try/finally`. Add automated tests that verify resource cleanup after both passing and failing tests. | Open |
| **R-02** | Over-engineering before proving value. Building dashboards, database adapters, or extension systems before the core framework is validated. | 4 | 5 | Adhere strictly to the MVP exclusion list (Phase 0.3.4). Every new feature must trace to a validated user problem. Enforce the "Reconsideration Trigger" process for deferred features. | Open |
| **R-03** | The framework becomes a thin wrapper around Playwright/Pytest, adding no meaningful value over using them directly. | 3 | 5 | Focus on the differentiators: evidence-first diagnostics, standardised configuration, and optional dependency isolation. Validate with design partners that the framework saves time compared to raw Pytest + Playwright. | Open |
| **R-04** | Excessive abstraction makes tests harder to read and write (the "framework within a framework" problem). | 3 | 4 | Prefer direct, readable tests. Introduce abstractions only for recurring complexity. Public API design principles (Phase 0.4.4) mandate "Explicit over magical." | Open |
| **R-05** | Dependency upgrades break existing user projects. | 3 | 4 | Publish compatibility ranges, maintain release notes, and test upgrade paths in Phase 12. Use a lock file (`uv.lock`) and Dependabot for controlled updates. | Open |
| **R-06** | Sensitive information leaks through reports (e.g., API tokens in request metadata, passwords in screenshots). | 3 | 5 | Implement centralised redaction in Phase 3. Add synthetic-secret tests in Phase 8. Document that screenshots and traces cannot be automatically sanitised and require explicit capture policies. | Open |
| **R-07** | Scope creep into a full testing platform (dashboards, distributed execution, AI analysis) before the core is stable. | 4 | 4 | Keep a hard boundary around Phase 1 MVP. Defer all non-essential features with explicit "Reconsideration Triggers" in `docs/mvp-scope.md`. | Open |
| **R-08** | Solo developer burnout or unavailability stops maintenance and releases. | 3 | 5 | Document release procedures, maintain a `CONTRIBUTING.md`, and establish backup maintainer access in Phase 12. Keep the project scope sustainable. | Open |

---

## 2. Market Hypotheses

> Market hypotheses are assumptions about user needs, adoption, and commercial viability. They are tracked as hypotheses until validated or invalidated through user research (Phase 0.2). Each hypothesis has a clear **Validation Method** and **Status**.

| ID | Hypothesis | Validation Method | Status |
| :--- | :--- | :--- | :--- |
| **H-01** | QA engineers struggle with **fixture setup and lifecycle management** (e.g., browser contexts, API clients) because they must rebuild this infrastructure for every new project. | Conduct 5 user interviews in Phase 0.2. Ask about their last project setup process. | Open |
| **H-02** | QA engineers spend significant time **investigating CI failures** because current tools provide only a pass/fail status without sufficient diagnostic context (screenshots, traces, request/response metadata). | Conduct 5 user interviews in Phase 0.2. Ask about their most recent frustrating test failure and how they investigated it. | Open |
| **H-03** | QA engineers would adopt a framework that reduces **initial setup time** from days to hours, even if it requires them to write standard Pytest code. | Conduct 5 user interviews in Phase 0.2. Ask about their willingness to adopt new tools and switching barriers. | Open |
| **H-04** | Small-to-medium teams (3–15 engineers) are the initial target market, rather than large enterprises with existing custom frameworks. | Analyse interview participant demographics in Phase 0.2. | Open |
| **H-05** | Teams are willing to pay for a "Team" offering (shared history, collaboration, dashboards) after adopting the open-source core. | Conduct pricing conversations in Phase 11. Do not build Team features until validated. | Open |
| **H-06** | GitHub Actions is the primary CI platform for the initial user base. | Ask interview participants about their CI platform in Phase 0.2. | Open |

---

## 3. Risk & Hypothesis Review Cadence

| Frequency | Activity | Owner |
| :--- | :--- | :--- |
| **Weekly** | Review open risks and hypotheses. Update status if new evidence emerges. Add new risks discovered during development. | Solo Dev |
| **End of Phase 0** | Validate all market hypotheses (H-01 to H-06) through user interviews. Mark as **Validated**, **Invalidated**, or **Needs More Data**. | Solo Dev |
| **End of Phase 1** | Review technical risks (R-01 to R-08) based on MVP implementation experience. Update mitigation strategies and likelihood/impact scores. | Solo Dev |
| **End of Phase 8** | Conduct a security-focused risk review. Add any new security risks to the register. | Solo Dev |
| **End of Phase 11** | Review commercial hypotheses (H-05). Update based on pricing conversations and pilot outcomes. | Solo Dev |

---

## 4. Risk Scoring Guide

| Score | Likelihood | Impact |
| :--- | :--- | :--- |
| **1** | Rare — unlikely to occur in the next 12 months. | Negligible — minor inconvenience, no impact on delivery. |
| **2** | Unlikely — could occur but not expected. | Low — small delay or rework, manageable within sprint. |
| **3** | Possible — might occur during the project. | Medium — noticeable delay, requires mitigation effort. |
| **4** | Likely — expected to occur at some point. | High — significant delay or quality degradation, affects Phase exit criteria. |
| **5** | Almost certain — will occur unless actively mitigated. | Critical — blocks release, causes project failure, or creates legal/security exposure. |

---

## 5. Document History

| Version | Date | Author | Changes |
| :--- | :--- | :--- | :--- |
| 0.1.0 | 2026-10-27 | Solo Dev | Initial risk and hypothesis register created from Phase 0.2.1. |

---

*This document is a living artifact. It will be updated after every phase review, user interview, and significant technical decision.*
