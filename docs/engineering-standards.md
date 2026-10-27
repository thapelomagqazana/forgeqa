# ForgeQA - Engineering Standards

> **Project Status: Pre-alpha**
> **Version**: 0.1.0
> **Last Updated**: 2026-10-27
> **Owner**: Solo Developer

---

## 1. Supported Python Versions

> **Status**: Locked for Phase 1 (MVP).
> **Decision Date**: 2026-10-27

### 1.1 Version Matrix

| Version | Support Level | Tested in CI | Notes |
| :--- | :--- | :--- | :--- |
| **Python 3.10** | ❌ Unsupported | No | Missing performance improvements; Pydantic V2 works but slower. |
| **Python 3.11** | ✅ **Minimum** | Yes (required) | Baseline for development and CI. |
| **Python 3.12** | ✅ **Maximum (tested)** | Yes (required) | Latest stable version with full dependency compatibility. |
| **Python 3.13** | ⚠️ Experimental | No (yet) | Some dependencies may not be fully compatible. Revisit in Phase 2. |

### 1.2 Rationale

| Factor | Decision | Evidence |
| :--- | :--- | :--- |
| **Pydantic V2 performance** | Minimum 3.11 | Pydantic V2 leverages Python 3.11's performance improvements (e.g., `asyncio` optimisations, faster startup). Using 3.10 would degrade performance. |
| **Playwright compatibility** | Minimum 3.8 | Playwright for Python supports 3.8+, but 3.11+ is recommended for modern async support. |
| **Pytest compatibility** | Minimum 3.10 | Pytest 9.x requires Python 3.10+. We target 3.11+ to align with the Pydantic baseline. |
| **Ecosystem maturity** | 3.11 and 3.12 | Both versions are stable, widely adopted, and fully supported by all dependencies (Pydantic, Playwright, HTTPX, Pytest). |
| **CI cost** | Two versions | Testing two versions (3.11 and 3.12) balances compatibility coverage with CI cost. Testing 3.10 or 3.13 adds little value at this stage. |
| **Future readiness** | 3.13 experimental | Python 3.13 is stable but some dependencies may lag. Will be tested in Phase 2 after dependency updates. |

### 1.3 CI Matrix

The GitHub Actions workflow (`.github/workflows/quality.yml`) will test both versions:

```yaml
strategy:
  matrix:
    python-version: ["3.11", "3.12"]
```

> **Note**: This matrix will be implemented in WBS 0.5.7. The CI workflow will fail if the package cannot be installed or tested on either version.

### 1.4 Enforcement

| Mechanism | Implementation |
| :--- | :--- |
| **Package metadata** | `pyproject.toml` enforces `requires-python = ">=3.11,<3.13"`. `pip install forgeqa` will fail on Python 3.10 or 3.13+. |
| **CI matrix** | GitHub Actions tests both 3.11 and 3.12. |
| **Documentation** | This document is the single source of truth for supported versions. |
| **ADR reference** | See [ADR-001](../adr/ADR-001-python-and-pytest.md) for the full decision record. |

### 1.5 Upgrade Policy

| Event | Action |
| :--- | :--- |
| **New Python release (e.g., 3.13)** | Add to CI matrix as "experimental." Test all dependencies. If compatible, promote to "supported" in the next minor release. |
| **Dependency drops support for a Python version** | Drop the Python version from the matrix. Update `requires-python` and document in release notes. |
| **Security vulnerability in a Python version** | Recommend users upgrade. Update minimum version if necessary. |

### 1.6 Build Verification

The package is built using Hatchling and verified in a clean environment as part of WBS 0.5.2. The build process is:

```bash
python -m build
pip install dist/forgeqa-*.whl
python -c "import forgeqa; print(forgeqa.__version__)"
```

This verification is repeated in CI (WBS 0.5.7) on every pull request to ensure the package remains installable.

### 1.7 PyPI Classifiers

The following classifiers are used in `pyproject.toml`. All classifiers must be selected from the [official PyPI classifier list](https://pypi.org/classifiers/). Inventing new classifiers will cause the build to fail.

```toml
classifiers = [
    "Development Status :: 3 - Alpha",
    "Intended Audience :: Developers",
    "Intended Audience :: Information Technology",
    "License :: OSI Approved :: MIT License",
    "Programming Language :: Python :: 3",
    "Programming Language :: Python :: 3.11",
    "Programming Language :: Python :: 3.12",
    "Topic :: Software Development :: Testing",
    "Topic :: Software Development :: Quality Assurance",
    "Typing :: Typed",
]
```

> **Note**: "Intended Audience :: Quality Engineers" is **not** a valid PyPI classifier. Use "Intended Audience :: Information Technology" instead. QA intent is captured by the "Topic :: Software Development :: Quality Assurance" classifier.

---

## 2. Git & Commit Conventions

### 2.1 Branch Naming

| Prefix | Use Case | Example |
| :--- | :--- | :--- |
| `feat/` | New feature or capability | `feat/add-playwright-fixture` |
| `fix/` | Bug fix | `fix/config-validation-error` |
| `docs/` | Documentation only | `docs/update-architecture` |
| `test/` | Test-only changes | `test/add-fixture-cleanup` |
| `chore/` | Maintenance, tooling, dependencies | `chore/update-ruff-config` |
| `refactor/` | Code restructuring without behaviour change | `refactor/split-config-module` |

### 2.2 Commit Message Format (Conventional Commits)

```
<type>(<scope>): <subject>

[optional body]

[optional footer]
```

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

**Examples:**
```
feat(fixtures): add browser context isolation
fix(config): validate timeout_ms as positive integer
docs(architecture): add C4 context diagram
chore(deps): bump pytest to 9.2.0
```

### 2.3 Pull Request Workflow

1. Create a feature branch from `main`.
2. Make changes, commit using Conventional Commits.
3. Push the branch to GitHub.
4. Open a Pull Request with a clear description.
5. Ensure CI passes (linting, type checking, tests).
6. Squash and merge to `main`.
7. Delete the feature branch (auto-delete enabled).

> **Enforcement**: The `main` branch is protected by a ruleset requiring PRs, blocking force pushes, and requiring conversation resolution (see WBS 0.1.1).

---

## 3. Code Quality Standards

### 3.1 Ruff (Linting & Formatting)

| Setting | Value | Rationale |
| :--- | :--- | :--- |
| `line-length` | 100 | Balances readability with modern screen widths. |
| `target-version` | `py311` | Matches the minimum supported Python version. |
| `select` | `E`, `F`, `I`, `UP`, `B`, `SIM`, `C4` | Core linting rules plus simplification and comprehensions. |
| `ignore` | `E501` | Line length is handled by the formatter. |
| `quote-style` | `double` | Consistent with PEP 8 and the wider Python ecosystem. |

**Commands:**
```bash
ruff check .          # Lint
ruff format --check . # Verify formatting
ruff format .         # Apply formatting
```

### 3.2 MyPy (Type Checking)

| Setting | Value | Rationale |
| :--- | :--- | :--- |
| `python_version` | `3.11` | Matches the minimum supported version. |
| `strict` | `true` | Enforces type safety in the core package. |
| `files` | `["src"]` | Only the package source is strictly typed. |
| `disallow_untyped_defs` | `true` | All functions must have type hints. |

**Commands:**
```bash
mypy src
```

> **Rule**: Any `# type: ignore` must include an explanatory comment (e.g., `# type: ignore[import]  # Playwright lacks type stubs`).

### 3.3 Pytest (Test Execution)

| Setting | Value | Rationale |
| :--- | :--- | :--- |
| `testpaths` | `["tests"]` | Standard test discovery location. |
| `addopts` | `-ra --strict-markers` | Shows extra test summary and prevents marker typos. |
| `markers` | `unit`, `integration`, `ui`, `api`, `smoke`, `slow` | Standardised marker taxonomy. |
| `filterwarnings` | `error` (except `DeprecationWarning`) | Treats warnings as errors to catch issues early. |

**Commands:**
```bash
pytest                        # Run all tests
pytest -m unit                # Run only unit tests
pytest -m "not slow"          # Exclude slow tests
pytest --cov=src/forgeqa      # Run with coverage
```

---

## 4. Dependency Management

### 4.1 Dependency Groups

ForgeQA separates dependencies into groups so that users only install what they need.

| Group | Purpose | Installation |
| :--- | :--- | :--- |
| **Core** | Required for all users (`pytest`, `pydantic`). | `pip install forgeqa` |
| **UI** | Playwright for browser testing. | `pip install forgeqa[ui]` |
| **API** | HTTPX for API testing. | `pip install forgeqa[api]` |
| **Dev** | Build tools, linters, type checkers, test coverage. | `pip install forgeqa[dev]` |
| **All** | All optional dependencies (UI + API + Dev). | `pip install forgeqa[all]` |

> **Rule**: Core installation must **not** install Playwright or HTTPX. These are optional and installed only when the user requests the `ui` or `api` extra.

### 4.2 Tooling

| Tool | Purpose | Usage |
| :--- | :--- | :--- |
| **uv** | Dependency resolution, lockfile generation, environment management. | `uv lock`, `uv sync`, `uv add` |
| **Dependabot** | Automated weekly dependency update PRs. | Configured in `.github/dependabot.yml` |

> **Why uv?** `uv` is significantly faster than `pip` and generates a cross-platform lockfile (`uv.lock`) that guarantees reproducible installations across machines. It also handles dependency resolution for all extras (`ui`, `api`, `dev`) in a single lockfile.

### 4.3 Version Constraint Policy

| Dependency Type | Constraint | Example | Rationale |
| :--- | :--- | :--- | :--- |
| **Core** | `~=` (compatible release) | `pytest~=9.2.0` | Allows patch and minor updates within the same major version, but not breaking changes. For example, `~=9.2.0` allows `9.2.x` and `9.3.x` but not `10.0.0`. |
| **Optional** | `>=` (minimum version) | `playwright>=1.64.1` | Allows users to upgrade independently. The minimum is the tested version. |
| **Dev** | `>=` (minimum version) | `ruff>=0.6.9` | Keeps tooling up to date without blocking. |

> **Rule**: Do not pin dependencies to exact versions (`==`) in `pyproject.toml`. Use the lockfile (`uv.lock`) for reproducible local development and CI. Exact pins in `pyproject.toml` prevent users from receiving security patches.

**Example `pyproject.toml`:**

```toml
[project]
dependencies = [
    "pytest~=9.2.0",      # Core: compatible release
    "pydantic~=2.14.1",   # Core: compatible release
]

[project.optional-dependencies]
ui = ["playwright>=1.64.1"]   # Optional: minimum version
api = ["httpx>=0.27"]         # Optional: minimum version
dev = ["ruff>=0.6.9", "mypy>=1.11.2", "build", "pytest-cov", "coverage[toml]", "pre-commit"]
```

### 4.4 Lockfile

| File | Purpose | Committed? |
| :--- | :--- | :--- |
| `uv.lock` | Exact resolved versions for all dependencies (including transitive). | ✅ **Yes** (required for reproducible installs) |
| `pyproject.toml` | Broad version constraints and project metadata. | ✅ Yes |

> **Rule**: Never edit `uv.lock` manually. Use `uv lock` or `uv add` to update it. The lockfile is automatically updated by Dependabot PRs.

**Commands:**

```bash
# Generate or update the lockfile
uv lock

# Install the exact versions from the lockfile
uv sync

# Add a new dependency (updates pyproject.toml and uv.lock)
uv add some-package
```

### 4.5 Automated Updates (Dependabot)

Dependabot is configured to check for dependency updates **weekly** (Monday 09:00 UTC). It creates PRs for:

- **Python dependencies** (`pip` ecosystem).
- **GitHub Actions** (workflow versions).

Configuration file: `.github/dependabot.yml`.

**Grouping strategy:**
- **Minor and patch updates** are grouped into a single PR to reduce noise.
- **Major updates** are kept separate for careful review.

### 4.6 Review Process for Updates

| Step | Action |
| :--- | :--- |
| **1. Check CI** | All quality checks (lint, format, type check, ADR validation, test, build) must pass on the Dependabot PR. |
| **2. Review changelog** | Open the dependency's release notes. Identify breaking changes, deprecations, and new features. |
| **3. Check compatibility** | Ensure the update supports Python 3.11 and 3.12. |
| **4. Local test (if major)** | For major version bumps, run `uv sync` and `make test` locally. |
| **5. Merge** | Squash and merge. The lockfile is automatically updated by Dependabot. |
| **6. Verify** | Confirm the `main` branch CI passes after merge. |

> **Rule**: Never merge a Dependabot PR if CI fails. Investigate the failure before proceeding.

### 4.7 Breaking Change Protocol

| Scenario | Action |
| :--- | :--- |
| **Major version bump** | Manually review the changelog. Update code if needed. Add a note to `CHANGELOG.md`. |
| **Security vulnerability** | Merge the security update immediately (after CI passes). Document in release notes. |
| **Dependency drops Python version** | Remove that Python version from the CI matrix. Update `requires-python` and document in `docs/engineering-standards.md`. |
| **Dependency adds a new Python version** | Add it to the CI matrix as "experimental." Test for 2 weeks. If stable, promote to "supported." |

### 4.8 Dependency Inventory

> This inventory is updated when a dependency is added or removed. It is reviewed in Phase 8 (Security) and Phase 12 (Stable Release).

| Dependency | Type | Purpose | Version Constraint | Python Support |
| :--- | :--- | :--- | :--- | :--- |
| **pytest** | Core | Test discovery and execution. | `~=9.2.0` | 3.10+ |
| **pydantic** | Core | Configuration and result validation. | `~=2.14.1` | 3.8+ |
| **playwright** | Optional (UI) | Browser automation. | `>=1.64.1` | 3.8+ |
| **httpx** | Optional (API) | HTTP client for API testing. | `>=0.27` | 3.8+ |
| **ruff** | Dev | Linting and formatting. | `>=0.6.9` | 3.7+ |
| **mypy** | Dev | Static type checking. | `>=1.11.2` | 3.8+ |
| **build** | Dev | PEP 517 package build. | `>=1.2.1` | 3.8+ |
| **pytest-cov** | Dev | Test coverage. | `>=5.0.0` | 3.8+ |
| **coverage[toml]** | Dev | Coverage data (TOML support). | `>=7.6.0` | 3.8+ |
| **pre-commit** | Dev | Git hook management. | `>=3.8.0` | 3.9+ |

> **Note**: Python support columns are based on the dependency's own `requires-python` metadata. They are verified during the review process (Step 3 in 4.6).

### 4.9 Security & Vulnerability Scanning

| Tool | Purpose | Frequency | Status |
| :--- | :--- | :--- | :--- |
| **gitleaks** | Detect hardcoded secrets. | Every commit (pre-commit hook). | ✅ Implemented |
| **Dependabot alerts** | Detect known vulnerabilities in dependencies. | Continuous (GitHub). | ✅ Implemented |
| **pip-audit** | Detect known vulnerabilities in Python dependencies. | Every CI run. | 🔄 Phase 8 |
| **SBOM (CycloneDX)** | Inventory of all components in the release. | Every release. | 🔄 Phase 8 |

> **Rule**: Critical vulnerabilities must be addressed within 7 days. High vulnerabilities within 30 days. See `SECURITY.md` for the full remediation policy.

### 4.10 Dependency Update Checklist

Before merging any dependency update PR:

- [ ] CI passes (lint, format, type check, ADR validation, test, build).
- [ ] Changelog reviewed for breaking changes.
- [ ] Python 3.11 and 3.12 compatibility confirmed.
- [ ] Lockfile (`uv.lock`) updated (Dependabot does this automatically).
- [ ] For major version bumps: local test run with `uv sync && make test`.
- [ ] For security updates: documented in `CHANGELOG.md`.
- [ ] For dependency inventory changes: `docs/engineering-standards.md` updated.


---

## 5. Security & Secret Handling

| Requirement | Implementation |
| :--- | :--- |
| **Secrets in environment variables** | Never commit `.env` files. Use `os.environ` or Pydantic Settings. |
| **Secret scanning** | Pre-commit hook (`gitleaks` or `detect-secrets`) prevents accidental commits. |
| **Redaction in logs** | Diagnostics must redact passwords, tokens, cookies, and sensitive headers. |
| **Dependency scanning** | `pip-audit` runs in CI (Phase 8). |
| **Artifact security** | Screenshots and traces are stored in a controlled `artifacts/` directory with configurable retention. |

---

## 6. Documentation Standards

| Document | Purpose |
| :--- | :--- |
| `README.md` | Project overview, quick start, links to detailed docs. |
| `docs/product-requirements.md` | What ForgeQA is building and why. |
| `docs/architecture.md` | System context, container diagrams, dependency rules. |
| `docs/engineering-standards.md` | This document—how to build, test, and contribute. |
| `docs/user-discovery.md` | Persona, problem statement, interview evidence. |
| `docs/mvp-scope.md` | MVP capabilities, user journeys, exclusions. |
| `docs/risks.md` | Technical risks and market hypotheses. |
| `docs/adr/` | Architecture Decision Records. |
| `CONTRIBUTING.md` | How to contribute, PR workflow, code of conduct. |
| `CHANGELOG.md` | Release history and breaking changes. |

---

## 7. Versioning & Release Policy

### 7.1 Semantic Versioning

| Version | Meaning | Example |
| :--- | :--- | :--- |
| **MAJOR** | Breaking changes to the public API. | `1.0.0` → `2.0.0` |
| **MINOR** | New features, backward-compatible. | `1.0.0` → `1.1.0` |
| **PATCH** | Bug fixes, backward-compatible. | `1.0.0` → `1.0.1` |

> **Pre-1.0 Policy**: While the project is in the `0.x.y` phase, breaking changes may occur in minor versions. Document them clearly in the CHANGELOG.

### 7.2 Release Checklist

Before tagging a release:

- [ ] All tests pass locally and in CI.
- [ ] Ruff lint and format checks pass.
- [ ] MyPy passes.
- [ ] `python -m build` succeeds without warnings.
- [ ] The built `.whl` installs in a clean environment.
- [ ] `CHANGELOG.md` is updated.
- [ ] Version is bumped in `pyproject.toml` and `src/forgeqa/__init__.py`.
- [ ] Git tag is created (`v0.1.0`).
- [ ] Release notes are published on GitHub.

---

## 8. Document History

| Version | Date | Author | Changes |
| :--- | :--- | :--- | :--- |
| 0.1.0 | 2026-10-27 | Solo Dev | Initial engineering standards created. |
| 0.1.1 | 2026-10-27 | Solo Dev | Added "Supported Python Versions" section (WBS 0.5.1). |
| 0.1.2 | 2026-10-27 | Solo Dev | Added "Build Verification" and "PyPI Classifiers" sections (WBS 0.5.2). |
