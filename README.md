# ForgeQA

> **A reusable, evidence-first Python test automation foundation.**

[![Quality Gate](https://github.com/thapelomagqazana/forgeqa/actions/workflows/quality.yml/badge.svg)](https://github.com/thapelomagqazana/forgeqa/actions/workflows/quality.yml)
[![Python 3.11+](https://img.shields.io/badge/python-3.11%20%7C%203.12-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Project Status: Pre-alpha](https://img.shields.io/badge/status-pre--alpha-orange.svg)](#project-status)

> **Project Status: Pre-alpha**
> ForgeQA is in active development (Phase 0). The API is not yet stable. See the [Roadmap](#roadmap) for details.

---

## 📖 What is ForgeQA?

ForgeQA is a **reusable, evidence-first test automation framework** built on Python, Pytest, and Playwright. It provides a common foundation for UI, API, and integration testing—so teams can stop rebuilding the same infrastructure for every project and start focusing on what actually matters: **testing their software**.

> **Build automation once. Reuse the engineering. Trust the evidence.**

---

## 😩 The Problem

Many organisations build automation incrementally. One team uses Selenium, another uses Playwright, and a third maintains API tests using custom HTTP clients. Each project develops its own configuration, authentication helpers, reporting conventions, test-data setup, and CI/CD pipeline.

This creates recurring problems:

| Problem | Impact |
| :--- | :--- |
| **Duplicated engineering effort** | Teams repeatedly build the same utilities, authentication flows, API clients, fixtures, and reporting logic. |
| **Fragile and expensive maintenance** | Poor abstractions, brittle selectors, arbitrary waits, and tightly coupled tests cause frequent failures and expensive repairs. |
| **Inconsistent execution** | Different teams produce different reports, use different environment conventions, and apply different quality gates. |
| **Poor failure investigation** | A failed pipeline may reveal only that a test failed, without sufficient context to identify the application defect, environment issue, test-data problem, or automation defect. |
| **Governance and security gaps** | Secrets may be mishandled, sensitive test data may leak into reports, and teams may lack traceability between requirements, tests, and releases. |

---

## 💡 The Solution

ForgeQA provides a **standardised, reusable foundation** that solves these problems:

| Capability | What It Means |
| :--- | :--- |
| **Standardised configuration** | One `forgeqa.toml` file with validated settings. No more scattered environment variables. |
| **Reusable Pytest fixtures** | `browser`, `api_client`, and `settings` fixtures with predictable lifecycles. |
| **Playwright UI automation** | Isolated browser contexts, auto-waiting, screenshots, and traces on failure. |
| **HTTPX API automation** | Reusable HTTP client with sanitised request/response metadata. |
| **Evidence-first diagnostics** | JUnit XML, structured JSON, screenshots, and traces—all linked to the test that produced them. |
| **CI/CD integration** | Reference GitHub Actions workflow that publishes results and fails correctly. |
| **Secure by default** | Secrets redacted from logs and artifacts. No accidental credential leaks. |
| **Extensible** | Optional adapters (database, Selenium, Appium) can be added without changing the core. |

> **The defining principle**: *Standardise the infrastructure, not every test.* Teams share proven engineering capabilities while retaining the freedom to test their applications according to their specific requirements.

---

## 🚀 Quick Start

> **Note**: ForgeQA is in pre-alpha. The Quick Start will be fully functional once Phase 1 (MVP) is complete. The steps below show the intended workflow.

### 1. Install ForgeQA

```bash
# Create a virtual environment
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install ForgeQA (core only)
pip install forgeqa

# Or install with UI (Playwright) and API (HTTPX) support
pip install forgeqa[all]
```

### 2. Configure Your Project

Create a `forgeqa.toml` file in your project root:

```toml
[general]
environment = "local"
artifacts_dir = "artifacts"

[browser]
browser_name = "chromium"
headless = true
timeout_ms = 10000

[api]
base_url = "http://localhost:8000/api"
timeout_seconds = 10
```

### 3. Write Your First Test

Create `tests/test_example.py`:

```python
def test_homepage(page):
    page.goto("/")
    assert page.title() == "My App"

def test_health(api_client):
    response = api_client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
```

### 4. Run Your Tests

```bash
pytest
```

### 5. Investigate Failures

When a test fails, ForgeQA generates:

```
artifacts/
├── junit.xml              # Standard CI report
├── results.json           # Structured result data
└── tests/
    └── test-<id>/
        ├── failure.png    # Screenshot at point of failure
        └── trace.zip      # Playwright trace for deeper investigation
```

Open the screenshot and trace to see exactly what happened—without re-running the test locally.

### 6. Run in CI

Copy the reference GitHub Actions workflow into your repository:

```yaml
# .github/workflows/tests.yml
name: Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
      - run: pip install forgeqa[all]
      - run: playwright install chromium
      - run: pytest --junitxml=artifacts/junit.xml
      - uses: actions/upload-artifact@v4
        if: always()
        with:
          name: test-results
          path: artifacts/
```

---

## 🏗️ Architecture

ForgeQA is built with a **modular, adapter-based architecture**. The core is independent of any specific tool.

```
┌─────────────────────────────────────────────────────────────┐
│                    Consumer Test Suites                     │
│              (Pytest tests written by QA engineers)         │
└─────────────────────────────┬───────────────────────────────┘
                              │
┌─────────────────────────────▼───────────────────────────────┐
│                    ForgeQA Public API                       │
│         (Fixtures, settings, helpers, extension points)     │
└─────────────────────────────┬───────────────────────────────┘
                              │
┌─────────────────────────────▼───────────────────────────────┐
│                       Core Services                         │
│     (Configuration, lifecycle, test identity, contracts)    │
└──────┬──────────────────┬──────────────────┬────────────────┘
       │                  │                  │
┌──────▼──────┐  ┌────────▼────────┐  ┌─────▼──────┐
│  UI Adapter │  │   API Adapter   │  │ Reporting  │
│ (Playwright)│  │     (HTTPX)     │  │  (JUnit XML│
│             │  │                 │  │   + JSON)  │
└─────────────┘  └─────────────────┘  └────────────┘
```

For the full architecture, see [`docs/architecture.md`](docs/architecture.md).

---

## 📚 Documentation

| Document | Purpose |
| :--- | :--- |
| **[Product Requirements](docs/product-requirements.md)** | What ForgeQA is building and why. |
| **[Architecture](docs/architecture.md)** | System context, container diagrams, dependency rules. |
| **[Engineering Standards](docs/engineering-standards.md)** | Supported Python versions, code quality, dependency management. |
| **[User Discovery](docs/user-discovery.md)** | Persona, problem statement, interview evidence. |
| **[MVP Scope](docs/mvp-scope.md)** | MVP capabilities, user journeys, exclusions. |
| **[Risks & Hypotheses](docs/risks.md)** | Technical risks and market hypotheses. |
| **[ADRs](docs/adr/)** | Architecture Decision Records. |
| **[Contributing](CONTRIBUTING.md)** | How to contribute, PR workflow, code of conduct. |
| **[Security](SECURITY.md)** | Security policy, vulnerability reporting, best practices. |

---

## 🗺️ Roadmap

ForgeQA is developed in 12 phases, from foundation to sustainable ecosystem. The current focus is **Phase 0–1: MVP**.

| Phase | Focus | Status |
| :--- | :--- | :--- |
| **Phase 0** | Discovery, architecture, engineering foundation | 🔄 In progress |
| **Phase 1** | MVP: installable package, Pytest fixtures, Playwright + HTTPX, diagnostics, CI | 📋 Planned |
| **Phase 2** | CLI and project scaffolding | 📋 Planned |
| **Phase 3** | Evidence-first reporting and diagnostics | 📋 Planned |
| **Phase 4** | CI/CD integration and execution controls | 📋 Planned |
| **Phase 5** | Reliability, isolation, and flakiness controls | 📋 Planned |
| **Phase 6** | Test data and database validation | 📋 Planned |
| **Phase 7** | Extension architecture and adapter ecosystem | 📋 Planned |
| **Phase 8** | Security and enterprise hardening | 📋 Planned |
| **Phase 9** | Historical quality intelligence | 📋 Planned |
| **Phase 10** | Team dashboard and control plane (conditional) | 📋 Planned |
| **Phase 11** | Commercial validation and packaging | 📋 Planned |
| **Phase 12** | Stable product and sustainable ecosystem | 📋 Planned |

For the full roadmap, see the [Project Brief](docs/product-requirements.md).

---

## 🛠️ Development

### Prerequisites

- **Python**: 3.11 or 3.12 (see [Engineering Standards](docs/engineering-standards.md#1-supported-python-versions))
- **Git**: 2.x+
- **Make**: Any (optional but recommended)

### Setup

```bash
# Clone the repository
git clone https://github.com/thapelomagqazana/forgeqa.git
cd forgeqa

# Install (using Make)
make install
source .venv/bin/activate

# Or manually
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

### Development Commands

| Command | What It Does |
| :--- | :--- |
| `make check` | Run lint, format check, and type check. |
| `make test` | Run all tests. |
| `make test-unit` | Run unit tests only. |
| `make test-cov` | Run tests with coverage. |
| `make build` | Build wheel and sdist. |
| `make ci` | Run the full CI pipeline locally. |
| `make adr-new TITLE="..."` | Create a new ADR. |
| `make hooks-install` | Install pre-commit hooks. |

For the full list, run `make help`.

### Pre-Commit Hooks

ForgeQA uses pre-commit to run automated checks before every commit:

```bash
make hooks-install
```

This installs:
- **gitleaks** (secret scanning)
- **ruff** (lint + format)
- **mypy** (type checking)
- **adr-validate** (ADR validation)
- **conventional-pre-commit** (commit message format)

---

## 🤝 Contributing

We welcome contributions! Please read [CONTRIBUTING.md](CONTRIBUTING.md) before opening a PR.

**Quick summary:**
1. Create a feature branch from `main`.
2. Make changes, add tests, update documentation.
3. Run `make check` and `make test`.
4. Commit using [Conventional Commits](https://www.conventionalcommits.org/).
5. Open a PR. CI must pass. Squash and merge.

---

## 🔒 Security

**Do not open a public issue for security vulnerabilities.**

Please report security issues privately via [GitHub Security Advisories](https://github.com/thapelomagqazana/forgeqa/security/advisories/new) or email `maintainer@forgeqa.dev`.

See [SECURITY.md](SECURITY.md) for the full policy, supported versions, and security controls.

---

## 📄 License

ForgeQA is licensed under the **MIT License**. See [LICENSE](LICENSE) for details.

---

## 🙏 Acknowledgements

ForgeQA builds on the shoulders of giants:

- **[Pytest](https://docs.pytest.org/)** — The test runner that makes everything possible.
- **[Playwright](https://playwright.dev/python/)** — Modern browser automation.
- **[HTTPX](https://www.python-httpx.org/)** — Async-capable HTTP client.
- **[Pydantic](https://docs.pydantic.dev/)** — Data validation and settings management.
- **[Ruff](https://docs.astral.sh/ruff/)** — Blazing-fast Python linting and formatting.
- **[uv](https://docs.astral.sh/uv/)** — Fast Python package management.

---

## 📬 Contact

- **GitHub Discussions**: [Ask questions, share ideas](https://github.com/thapelomagqazana/forgeqa/discussions)
- **GitHub Issues**: [Report bugs, request features](https://github.com/thapelomagqazana/forgeqa/issues)
- **Email**: `maintainer@forgeqa.dev`

---

> **ForgeQA — Build automation once. Reuse the engineering. Trust the evidence.**
