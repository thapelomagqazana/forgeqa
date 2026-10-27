# Contributing to ForgeQA

> **Thank you for your interest in contributing to ForgeQA!**
>
> ForgeQA is a reusable, evidence-first Python test automation foundation. This guide explains how to set up the development environment, follow the project conventions, and submit high-quality contributions.

---

## Table of Contents

1. [Code of Conduct](#1-code-of-conduct)
2. [Getting Started](#2-getting-started)
3. [Development Workflow](#3-development-workflow)
4. [Commit Conventions](#4-commit-conventions)
5. [Pre-Commit Hooks](#5-pre-commit-hooks)
6. [Testing](#6-testing)
7. [Code Quality](#7-code-quality)
8. [Architecture Decision Records](#8-architecture-decision-records)
9. [Pull Request Process](#9-pull-request-process)
10. [Reporting Bugs](#10-reporting-bugs)
11. [Suggesting Features](#11-suggesting-features)
12. [Security Reports](#12-security-reports)

---

## 1. Code of Conduct

Be respectful, constructive, and professional. ForgeQA is a solo-maintained project, so patience and clear communication are appreciated.

- **Be kind**: Disagreements are fine; personal attacks are not.
- **Be specific**: "It doesn't work" is not a bug report. Include reproduction steps.
- **Be patient**: Responses may take a few days. This is a side project.

---

## 2. Getting Started

### 2.1 Prerequisites

| Tool | Version | Purpose |
| :--- | :--- | :--- |
| **Python** | 3.11 or 3.12 | Core runtime (see `docs/engineering-standards.md`) |
| **Git** | 2.x+ | Version control |
| **Make** | Any | Development shortcuts (optional but recommended) |

### 2.2 Clone the Repository

```bash
git clone https://github.com/thapelomagqazana/forgeqa.git
cd forgeqa
```

### 2.3 Set Up the Development Environment

**Option A: Using Make (recommended)**

```bash
make install
source .venv/bin/activate
```

**Option B: Manual**

```bash
python -m venv .venv
source .venv/bin/activate   # On Windows: .venv\Scripts\activate
pip install --upgrade pip
pip install -e ".[dev]"
```

This installs:
- The `forgeqa` package in editable mode.
- Core dependencies (`pytest`, `pydantic`).
- Development tools (`ruff`, `mypy`, `build`, `pytest-cov`, `pre-commit`).

### 2.4 Verify the Setup

```bash
make check      # Lint, format, type check
make test       # Run all tests
```

Or manually:

```bash
ruff check .
ruff format --check .
mypy src
pytest
```

All four commands should pass. If they do, your environment is ready.

---

## 3. Development Workflow

### 3.1 Branch Naming

Create a feature branch from `main`. The `main` branch is protected and requires a Pull Request (PR) to merge.

| Prefix | Use Case | Example |
| :--- | :--- | :--- |
| `feat/` | New feature | `feat/add-playwright-fixture` |
| `fix/` | Bug fix | `fix/config-validation-error` |
| `docs/` | Documentation only | `docs/update-architecture` |
| `test/` | Test-only changes | `test/add-fixture-cleanup` |
| `chore/` | Maintenance, tooling | `chore/update-ruff-config` |
| `refactor/` | Code restructuring | `refactor/split-config-module` |

```bash
git checkout main
git pull origin main
git checkout -b feat/your-feature-name
```

### 3.2 Making Changes

1. Write the code.
2. Add or update tests in `tests/`.
3. Update documentation if needed.
4. Run `make check` and `make test` to verify.
5. Commit using [Conventional Commits](#4-commit-conventions).
6. Push the branch and open a PR.

---

## 4. Commit Conventions

ForgeQA uses **Conventional Commits**. This is enforced by the `conventional-pre-commit` hook.

### 4.1 Format

```
<type>(<scope>): <subject>

[optional body]

[optional footer]
```

### 4.2 Types

| Type | Description |
| :--- | :--- |
| `feat` | A new feature |
| `fix` | A bug fix |
| `docs` | Documentation only |
| `test` | Adding or updating tests |
| `chore` | Maintenance, tooling, dependencies |
| `refactor` | Code change that neither fixes a bug nor adds a feature |
| `perf` | Performance improvement |
| `ci` | CI configuration changes |

### 4.3 Examples

```
feat(fixtures): add browser context isolation
fix(config): validate timeout_ms as positive integer
docs(architecture): add C4 context diagram
chore(deps): bump pytest to 9.2.0
test(api): add negative-path tests for HTTPX adapter
```

### 4.4 Scope (Optional but Recommended)

Use the module name as the scope: `config`, `fixtures`, `adapters`, `reporting`, `diagnostics`, `cli`, `docs`.

---

## 5. Pre-Commit Hooks

ForgeQA uses [pre-commit](https://pre-commit.com/) to run automated checks before every commit. This catches issues locally and saves CI time.

### 5.1 Installation

After setting up the environment:

```bash
make hooks-install
```

Or manually:

```bash
pre-commit install
pre-commit install --hook-type commit-msg
```

### 5.2 What Runs on Every Commit

| Hook | Purpose |
| :--- | :--- |
| **gitleaks** | Detects hardcoded secrets (API keys, tokens, passwords). |
| **trailing-whitespace** | Removes trailing whitespace. |
| **end-of-file-fixer** | Ensures files end with a newline. |
| **check-yaml** | Validates YAML syntax. |
| **check-toml** | Validates TOML syntax. |
| **check-added-large-files** | Blocks files larger than 500 KB. |
| **check-merge-conflict** | Prevents committing merge conflict markers. |
| **ruff** | Lints and auto-fixes Python code. |
| **ruff-format** | Formats Python code. |
| **mypy** | Type-checks `src/`. |
| **adr-validate** | Validates ADRs against the template. |
| **adr-index** | Regenerates the ADR index. |
| **conventional-pre-commit** | Enforces Conventional Commits message format. |

### 5.3 Running Hooks Manually

```bash
# Run all hooks against all files
make hooks-run

# Or manually
pre-commit run --all-files

# Run a specific hook
pre-commit run ruff --all-files
```

### 5.4 Skipping Hooks (Use Sparingly)

```bash
git commit --no-verify -m "chore: emergency fix"
```

> **Warning**: CI will still run the full quality gate, so skipping hooks only delays the failure.

### 5.5 Updating Hooks

```bash
make hooks-update
```

Then commit the updated `.pre-commit-config.yaml` and verify with `make hooks-run`.

---

## 6. Testing

### 6.1 Test Structure

```
tests/
├── unit/              # Fast, isolated tests
├── integration/       # Tests involving multiple components
├── acceptance/        # End-to-end tests (Phase 1+)
└── conftest.py        # Shared fixtures
```

### 6.2 Running Tests

```bash
# All tests
make test

# Unit tests only
make test-unit

# Integration tests only
make test-integration

# UI tests only (requires Playwright)
make test-ui

# API tests only
make test-api

# Exclude slow tests
make test-fast

# With coverage
make test-cov
```

Or manually:

```bash
pytest
pytest -m unit
pytest -m "not slow"
pytest --cov=src/forgeqa --cov-report=term-missing
```

### 6.3 Writing Tests

- Every new feature must have tests.
- Every bug fix must have a regression test.
- Use the marker taxonomy: `@pytest.mark.unit`, `@pytest.mark.integration`, `@pytest.mark.ui`, `@pytest.mark.api`, `@pytest.mark.smoke`, `@pytest.mark.slow`.
- Use descriptive test names: `test_config_validation_rejects_negative_timeout`, not `test_config_1`.
- Use fixtures for shared setup (e.g., `api_client`, `browser`).
- Avoid arbitrary `sleep()` calls; use explicit waits.

### 6.4 Coverage Target

The core package (`src/forgeqa/`) should maintain **≥ 80% coverage**. Run `make test-cov` and open `htmlcov/index.html` to inspect.

---

## 7. Code Quality

### 7.1 Ruff (Lint & Format)

```bash
make lint           # Lint
make format         # Apply formatting
make format-check   # Verify formatting
```

Rules:
- Line length: 100 characters.
- Target Python: 3.11.
- Rule sets: `E`, `F`, `I`, `UP`, `B`, `SIM`, `C4`.
- `E501` is ignored (line length handled by formatter).

### 7.2 MyPy (Type Checking)

```bash
make typecheck
```

Rules:
- Strict mode for `src/forgeqa/`.
- All public functions must have type hints.
- Any `# type: ignore` must include an explanatory comment.

### 7.3 Full Quality Gate

```bash
make check
```

This runs lint + format-check + typecheck. It must pass before opening a PR.

---

## 8. Architecture Decision Records

ForgeQA uses ADRs to document significant architectural decisions. ADRs live in `docs/adr/`.

### 8.1 Creating a New ADR

```bash
make adr-new TITLE="Your Decision Title"
```

Or manually:

```bash
python scripts/adr.py new "Your Decision Title"
```

This creates `docs/adr/ADR-XXX-your-decision-title.md` from the template. Fill in:
- **Context**: What problem are you solving?
- **Decision**: What did you decide?
- **Alternatives Considered**: What else was considered, and why rejected?
- **Consequences**: Positive, negative, and neutral impacts.
- **Reconsideration Trigger**: What would cause you to revisit this decision?

### 8.2 Regenerating the Index

```bash
make adr-index
```

This updates `docs/adr/README.md` with a table of all ADRs.

### 8.3 Validating ADRs

```bash
make adr-validate
```

This checks that every ADR contains the required sections and has no unreplaced placeholders.

### 8.4 ADR Status Values

| Status | Meaning |
| :--- | :--- |
| **Proposed** | Under discussion; not yet accepted. |
| **Accepted** | Agreed upon and in effect. |
| **Deprecated** | No longer relevant, but kept for history. |
| **Superseded by ADR-XXX** | Replaced by a newer decision. |

---

## 9. Pull Request Process

### 9.1 Before Opening a PR

- [ ] `make check` passes (lint, format, typecheck).
- [ ] `make test` passes.
- [ ] `make adr-validate` passes (if you added/changed an ADR).
- [ ] Documentation is updated (if needed).
- [ ] Commit messages follow Conventional Commits.

### 9.2 Opening the PR

1. Push your branch to GitHub.
2. Click **Compare & pull request**.
3. Fill in the PR description:
   - **What**: What does this PR change?
   - **Why**: Why is this change needed? Link to the WBS task or issue.
   - **How**: Brief technical summary.
   - **Testing**: How did you test it?
4. Ensure CI passes (all checks green).
5. Request review (if you are not the only maintainer).

### 9.3 Merging

- The `main` branch is protected. PRs require:
  - All CI checks to pass.
  - Conversation resolution (resolve all comments).
  - Squash and merge (no merge commits).
- After merging, the feature branch is auto-deleted.

### 9.4 PR Review Checklist (for Reviewers)

- [ ] Does the PR solve the stated problem?
- [ ] Are there tests for the new behaviour?
- [ ] Do the tests cover edge cases?
- [ ] Is the code readable and maintainable?
- [ ] Are public APIs documented?
- [ ] Are secrets redacted in logs and artifacts?
- [ ] Is the CHANGELOG updated (if user-facing)?

---

## 10. Reporting Bugs

Open a GitHub Issue with:

1. **Title**: Clear and descriptive (e.g., "Config validation fails with empty base_url").
2. **Environment**: OS, Python version, ForgeQA version.
3. **Steps to reproduce**: Minimal code snippet.
4. **Expected behaviour**: What should happen.
5. **Actual behaviour**: What actually happens (include error messages).
6. **Logs**: Paste relevant output (redact secrets!).

---

## 11. Suggesting Features

Open a GitHub Discussion (not an Issue) with:

1. **Problem**: What problem are you trying to solve?
2. **Current workaround**: How do you solve it today?
3. **Proposed solution**: What would you like ForgeQA to do?
4. **Alternatives considered**: What else have you tried?
5. **Impact**: Who else would benefit?

> **Note**: Features are prioritised based on validated user problems (see `docs/mvp-scope.md`). Not every suggestion will be implemented.

---

## 12. Security Reports

**Do not open a public issue for security vulnerabilities.**

Report security issues privately via:
- GitHub Security Advisories: https://github.com/thapelomagqazana/forgeqa/security/advisories/new
- Or email: maintainer@forgeqa.dev

Include:
- Description of the vulnerability.
- Steps to reproduce.
- Potential impact.
- Suggested fix (if known).

You will receive a response within 5 business days.

---

## 13. Document History

| Version | Date | Author | Changes |
| :--- | :--- | :--- | :--- |
| 0.1.0 | 2026-10-27 | Solo Dev | Initial CONTRIBUTING.md created. |
| 0.1.1 | 2026-10-27 | Solo Dev | Added pre-commit hooks, ADR workflow, and security reporting sections. |

---

*Thank you for contributing to ForgeQA. Every contribution—code, documentation, bug reports, or feedback—helps make the project better.*
