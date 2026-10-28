# ForgeQA - Engineering Standards

> **Project Status: Pre-alpha**
> **Version**: 0.1.0
> **Last Updated**: 2026-10-28
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

> **Superseded by §4.12 and §4.13.** The three-command workflow above
> verifies that the wheel *installs* and `forgeqa.__version__` is
> queryable. It does **not** verify what the wheel and sdist *contain*
> (WBS 1.1.4, §4.12), and it does **not** verify that the installed
> wheel is *usable outside the source checkout* (WBS 1.1.5, §4.13).
> Both checks are additive; the install check here remains valid and is
> folded into the CI pipeline.

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

> **Current-state note (Phase 0 / WBS 1.1.3):** The shipped `pyproject.toml` currently uses `>=` for **core** dependencies (`pytest>=9.2.0`, `pydantic>=2.14.1`), not `~=`. Reconciling the constraint style is a **Phase 1 follow-up** because (a) it changes install behaviour for every consumer and (b) it should land together with the `uv.lock` lockfile that makes the constraint style meaningful. Until then, the `~=` row above documents the *intended* policy; the actual shipped file is the source of truth for what consumers get today. Do not change one without the other.

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
| **packaging** | Dev | PEP 440 version-specifier comparison (used by `scripts/verify_deps.sh`). | `>=23.0` | 3.8+ |

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

### 4.11 Dependency Groups and Verification

The four optional dependency groups (`ui`, `api`, `dev`, `all`) are a
**contract**, not just a declaration. A consumer installing `forgeqa`
core must not get Playwright or HTTPX; a consumer installing
`forgeqa[ui]` must get Playwright and **not** HTTPX; and so on. This
section documents the rules that keep the contract true and the tools
that verify it.

#### Rules

1. **`[project].dependencies` must not include an optional dependency.**
   Adding `playwright` or `httpx` there installs it for every consumer,
   defeating the purpose of extras. This is the configuration-level
   invariant, enforced by
   `tests/unit/test_dependency_groups.py::test_core_dependencies_do_not_include_optional_deps`.

2. **Each single-purpose extra declares exactly one runtime dependency.**
   - `ui` → Playwright only.
   - `api` → HTTPX only.
   - `dev` → build/verification tooling only (no runtime deps).
   - `all` → the explicit union of the above.

   Enforced by `test_ui_group_contains_playwright_only`,
   `test_api_group_contains_httpx_only`, and
   `test_all_group_is_explicit_union`.

3. **`all` is an explicit list, never a self-reference.**
   `all = ["forgeqa[ui,api,dev]"]` is valid per PEP 508 but warns on older
   resolvers and cannot be statically flattened by tooling. List the
   concrete dependencies. Enforced by
   `test_no_self_reference_in_all`.

4. **Adding a new optional dependency means updating five files in one PR:**
   1. `pyproject.toml` — declare the dependency in the appropriate extra.
   2. `tests/unit/test_dependency_groups.py` — assert the new group's
      shape (or extend an existing assertion).
   3. `scripts/verify_deps.sh` — add a scenario (see "Verification"
      below) and extend the cross-extra "not installed" assertions so
      the new dep is proven absent in the other extras.
   4. `tests/support.py` `FORBIDDEN_IMPORTS_ON_TOP_LEVEL` — add the
      import name (so the 1.1.2 top-level-import isolation test covers
      it automatically).
   5. `README.md` §"Optional extras" — add a row to the table.

   Missing any of these means the contract is documented but not
   enforced (or enforced but not documented).

5. **Tool versions pinned in `[dev]` must match `.pre-commit-config.yaml`.**
   `ruff` and `mypy` are pinned to exact versions in both places
   (`ruff==0.17.3`, `mypy==1.11.2` at the time of writing) because their
   formatters and checkers can disagree across minor versions. Drift
   causes spurious reformats on every commit and hides real issues
   (see WBS 1.1.2's tooling-drift incident). The `make tooling-check`
   target fails CI when the two sides disagree.

#### Verification

Two layers, both required:

1. **Config-level (fast, in-process).**
   `tests/unit/test_dependency_groups.py` parses `pyproject.toml` and
   asserts the group shape. Runs in <100 ms as part of `make test`.
   Catches a typo in `pyproject.toml` before a slow install cycle.

2. **End-to-end (slow, isolated).**
   `scripts/verify_deps.sh` (or `make verify-deps`) builds a wheel from
   local source, installs it in five fresh virtual environments (`core`,
   `ui`, `api`, `all`, `dev`), and asserts that the installed modules
   match the declared groups. Catches transitive leaks (a runtime dep
   that itself pulls in HTTPX) and install-time breakage — failures a
   static read of `pyproject.toml` cannot detect.

Neither layer is sufficient alone:

- Config-only verification cannot see a transitive dependency leak.
- End-to-end-only verification makes `make test` slow (~2.5 min) for
  every contributor on every change.

Both run in CI on Ubuntu and macOS, on Python 3.11 and 3.12.

#### Running the verification

```bash
# Fast, config-only
pytest tests/unit/test_dependency_groups.py -v

# Slow, end-to-end (all five scenarios, ~2.5 min)
make verify-deps

# Slow, end-to-end (single scenario, ~30 s)
./scripts/verify_deps.sh core

# Debug a failing scenario
KEEP_VENVS=1 ./scripts/verify_deps.sh ui
```

`PYTHON_BIN=python3.12 ./scripts/verify_deps.sh` selects a specific
interpreter (used by the CI matrix).

#### See also

- [ADR-003](../adr/ADR-003-verify-optional-dependency-groups-via-isolated-venv.md) — decision record for this verification strategy.
- `README.md` §"Optional extras" — consumer-facing documentation of each extra.
- `docs/public-api.md` §"Optional functionality" — what each extra enables at the API level.

### 4.12 Built Artifact Content Inspection

The wheel and sdist are part of the public contract, not incidental
by-products. The wheel is what `pip install forgeqa` consumes from PyPI;
the sdist is what `pip install forgeqa --no-binary :all:` consumes (and
what some downstream packagers use). Both must contain exactly the
intended files and nothing else.

#### Rules

1. **The wheel contains only the package.** Specifically:
   - `forgeqa/__init__.py` (and all modules under `forgeqa/`)
   - `forgeqa-X.Y.Z.dist-info/METADATA`, `WHEEL`, `RECORD`
   - `forgeqa-X.Y.Z.dist-info/licenses/LICENSE`

   It must **not** contain `tests/`, `docs/`, `examples/`, `scripts/`,
   `*.egg-info/`, `__pycache__/`, or `*.pyc`. Enforced by
   `tests/unit/test_build_config.py` (config-level) and
   `scripts/verify_build.sh` (end-to-end, inspects the built archive).

2. **The sdist contains the source tree.** Specifically:
   - `src/forgeqa/`, `tests/`, `docs/`
   - `README.md`, `LICENSE`, `pyproject.toml`

   It must **not** contain `dist/`, `build/`, `.venv/`, `*.egg-info/`,
   `__pycache__/`, or `*.pyc`. Enforced by
   `tests/unit/test_build_config.py` and `scripts/verify_build.sh`.

3. **`LICENSE` is bundled into the wheel** via
   `[project].license = { file = "LICENSE" }`. Switching to
   `license = { text = "MIT" }` (a small, well-intentioned edit for
   PEP 639 migration) would silently drop the file from the wheel and
   violate WBS 1.1.4. Enforced by
   `tests/unit/test_build_config.py::test_license_file_is_declared_for_bundling`.

4. **Build targets are explicit.** `[tool.hatch.build.targets.wheel]`
   and `[tool.hatch.build.targets.sdist]` each declare
   `packages`/`include` *and* `exclude`. Hatchling's defaults are
   permissive; explicit is auditable. Enforced by
   `tests/unit/test_build_config.py`.

5. **Evolving the build contract means updating four files in one PR:**
   1. `pyproject.toml` — add/change the `include`/`exclude` entry.
   2. `scripts/verify_build.sh` — add the corresponding pattern to
      `WHEEL_REQUIRED`, `WHEEL_FORBIDDEN`, `SDIST_REQUIRED`, or
      `SDIST_FORBIDDEN`.
   3. `tests/unit/test_build_config.py` — assert the config-level
      shape (or extend an existing assertion).
   4. `docs/engineering-standards.md` (this section) — update the
      contract if the intent changes.

   Missing any of these means the contract is documented but not
   enforced (or enforced but not documented). The `pyproject.toml`
   comment block above `[tool.hatch.build.targets.wheel]` mirrors the
   verifier's pattern arrays so a reviewer sees the same contract in
   both places.

6. **Do not use `setup.py` to inspect or modify the archive.**
   `python -m build` is the PEP 517 standard; any post-build step that
   mutates the wheel outside `pyproject.toml` is hidden from the config
   and from downstream packagers. If a file must not be in the wheel,
   exclude it in `[tool.hatch.build.targets.wheel].exclude` — not by
   deleting it after the build.

#### Verification

Two layers, both required:

1. **Config-level (fast, in-process).**
   `tests/unit/test_build_config.py` parses `pyproject.toml` and
   asserts the build-target shape:
   - wheel target declares `packages = ["src/forgeqa"]`
   - wheel exclude list contains `tests`, `docs`, `examples`, `scripts`
   - sdist include list contains `src`, `tests`, `docs`,
     `README.md`, `LICENSE`, `pyproject.toml`
   - sdist exclude list contains `dist`, `build`, `.venv`,
     `*.egg-info`, `__pycache__`
   - `[project].license` references the `LICENSE` file

   Runs in <100 ms as part of `make test`.

2. **End-to-end (slow, isolated).**
   `scripts/verify_build.sh` (or `make verify-build`) runs
   `python -m build` into a fresh temp directory (not `dist/`), then:
   - Lists the wheel with `unzip -l` and asserts required entries are
     present (`forgeqa/__init__.py`,
     `forgeqa-X.Y.Z.dist-info/licenses/LICENSE`, `METADATA`, `WHEEL`).
   - Asserts forbidden entries are absent from the wheel (`tests/`,
     `docs/`, `examples/`, `scripts/`, `*.egg-info/`,
     `__pycache__/`, `*.pyc`).
   - Lists the sdist with `tar -tzf` and asserts the source tree,
     tests, docs, and metadata files are present.
   - Asserts build artifacts are absent from the sdist (`dist/`,
     `build/`, `.venv/`, `*.egg-info/`, `__pycache__/`, `*.pyc`).

Neither layer is sufficient alone:

- Config-only verification cannot prove what hatchling's VCS-aware
  file selection actually includes in the archive. The negative
  assertion ("wheel does not contain tests/") is exactly the kind a
  config read cannot prove.
- End-to-end-only verification makes `make test` slow for every
  contributor on every change.

Both run in CI on Ubuntu and macOS, on Python 3.11 and 3.12.

#### Running the verification

```bash
# Fast, config-only
pytest tests/unit/test_build_config.py -v

# Slow, end-to-end (full: wheel + sdist)
make verify-build

# Slow, end-to-end (wheel or sdist only)
./scripts/verify_build.sh wheel
./scripts/verify_build.sh sdist

# Debug a failing inspection
KEEP_BUILD=1 ./scripts/verify_build.sh
```

`PYTHON_BIN=python3.12 ./scripts/verify_build.sh` selects a specific
interpreter (used by the CI matrix).

#### See also

- [ADR-004](../adr/ADR-004-verify-built-artifacts-contain-intended-files.md) — decision record for this verification strategy.
- `pyproject.toml` `[tool.hatch.build.targets]` — the build config and its content-contract comment block.
- `scripts/verify_build.sh` — the end-to-end verifier.
- `tests/unit/test_build_config.py` — the config-level complement.

### 4.13 Clean-Install Verification

The wheel's content being correct (see §4.12) is necessary but not
sufficient: the wheel must also *install* into a fresh environment and
*work* from outside the source checkout. A developer's `.venv` cannot
prove this — `pip install -e .` puts `src/` on `sys.path`, so the
editable install shadows the wheel and any import succeeds regardless of
whether the wheel is usable. Only a fresh venv, with no editable install
and no `PYTHONPATH`, can prove the wheel works as a consumer will
experience it.

#### Rules

1. **Install from the built wheel, not an editable tree.**
   `pip install dist/forgeqa-*.whl` is what a PyPI consumer runs. `pip
   install -e .` uses a different metadata path and does not prove the
   wheel is self-contained.

2. **Install into a fresh venv, not the developer's `.venv`.**
   The developer's `.venv` almost certainly has `pip install -e .`
   applied. Any test of "does the wheel install?" in that venv is
   meaningless — the editable install shadows the wheel.

3. **Run from a directory outside the source tree.**
   Even inside a fresh venv, running `python -c "import forgeqa"` from
   the repo root would put the current directory on `sys.path[0]`, and
   `src/` is one `cd` away. The verifier runs from
   `/tmp/forgeqa-verify-install-cwd.XXXXXX`.

4. **Assert the import location, not just that import succeeds.**
   `forgeqa.__file__` must resolve under the venv's `site-packages`.
   This is the WBS acceptance criterion "package is importable without
   the repo being on PYTHONPATH", made concrete.

5. **Compare the installed version against the wheel's `METADATA`.**
   A version mismatch means the installed package is not the wheel we
   built. This catches an editable-install leak that the import-path
   check might miss (e.g. a `.pth` file in a *parent* venv that puts
   `src/` on `sys.path`).

6. **Run `pytest` from the temp cwd against a real test file.**
   A bare `pytest` from the temp cwd would collect nothing and pass
   trivially. The verifier creates a `test_installed.py` with three
   real assertions (import, version non-empty, `forgeqa.__file__` under
   `site-packages`) and runs it.

7. **Clean up.** The venv, temp cwd, and wheel dir are all
   `trap`-cleaned on `EXIT INT TERM` unless `KEEP_INSTALL=1`.

8. **`py.typed` is a contract.** The `Typing :: Typed` classifier in
   `pyproject.toml` (present since 1.1.1) promises downstream users that
   inline types are available. PEP 561 requires a `py.typed` marker in
   the package for that promise to be honoured.
   `tests/unit/test_install_contract.py::test_py_typed_marker_present`
   enforces both sides (marker present, file empty).

#### Verification

Two layers, both required:

1. **Config-level (fast, in-process).**
   `tests/unit/test_install_contract.py` parses `src/forgeqa/__init__.py`
   and `pyproject.toml`, and asserts:
   - `__version__` and `get_version` are exposed
   - `__all__` matches the documented public surface
     (`EXPECTED_ALL` in `tests/unit/test_public_api.py`, shared via
     cross-module import so the two tests cannot drift)
   - no `sitecustomize.py` / `usercustomize.py` in the package
   - `py.typed` marker is present and empty
   - `Typing :: Typed` classifier is declared
   - `forgeqa` is a package (directory + `__init__.py`), not a module
   - no name in `__all__` collides with a stdlib module

   Runs in <100 ms as part of `make test`.

2. **End-to-end (slow, isolated).**
   `scripts/verify_install.sh` (or `make verify-install`) builds a wheel
   into a fresh temp dir, creates a fresh venv under `/tmp`, installs
   the wheel with dependencies, asserts import works and
   `forgeqa.__file__` is under `site-packages`, and runs a minimal
   pytest suite from a temp cwd.

Neither alone is sufficient: config-only cannot prove the wheel is
installable and usable in a clean environment; end-to-end-only makes
`make test` slow (a fresh venv + pip install is ~20 s).

Both run in CI on Ubuntu and macOS, on Python 3.11 and 3.12.

#### Running the verification

```bash
# Fast, config-only
pytest tests/unit/test_install_contract.py -v

# Slow, end-to-end (~20 s)
make verify-install

# Debug a failure
KEEP_INSTALL=1 ./scripts/verify_install.sh
# Leaves the venv, temp cwd, and wheel dir in place, prints their paths
```

`PYTHON_BIN=python3.12 ./scripts/verify_install.sh` selects a specific
interpreter (used by the CI matrix).

#### See also

- [ADR-005](../adr/ADR-005-verify-installed-wheel-outside-source-tree.md) — decision record for this verification strategy.
- `scripts/verify_install.sh` — the end-to-end verifier.
- `tests/unit/test_install_contract.py` — the config-level complement.
- §4.12 "Built Artifact Content Inspection" — the wheel-content
  contract that this section's "does it install?" contract complements.
- `docs/public-api.md` §"Guarantees" — the import-time behaviour this
  section verifies from a clean environment.

### 4.14 Public vs. Internal Module Conventions

The public API is defined in `docs/public-api.md`. It is enforced by
`tests/unit/test_public_api.py` and by `scripts/verify_build.sh`. This
section documents the contributor-facing side of the contract — the
rules a contributor must follow when adding, changing, or removing
public names, and when deciding whether a new module is public or
private.

For the *consumer-facing* side (what `forgeqa.__version__` returns, what
the optional dependencies install, what "stable" means), see
`docs/public-api.md`. This section is the counterpart: it tells the
contributor what they must do to keep the contract true.

#### Rules

1. **The public surface is `forgeqa.__all__`.** Every name in
   `__all__` must be documented in `docs/public-api.md`, and vice
   versa. Adding a name is a **semver-minor** event; removing or
   renaming a name is **semver-major**.

   Adding or removing a public name means updating **three places in
   one PR**:
   - `src/forgeqa/__init__.py` — the `__all__` tuple.
   - `docs/public-api.md` — the "public surface" table and, if the
     semver impact changes, the stability promise table.
   - `tests/unit/test_public_api.py` — the `EXPECTED_ALL` constant.

   Missing any of the three fails CI:
   - `test_public_api.py::test_all_matches_documented_surface` catches
     a divergence between `__all__` and `EXPECTED_ALL`.
   - `test_public_api_doc_exists_and_mentions_underscore_rule` catches
     a divergence between the doc and the rule.
   - `test_install_contract.py::test_init_all_matches_documented_surface`
     uses the same `EXPECTED_ALL` (cross-module import), so a fourth
     copy of the expected value is not needed.

   **`EXPECTED_ALL` is test-authoritative.** It is defined in
   `tests/unit/test_public_api.py` and **not** imported from
   `forgeqa.__all__`. Importing it from the code under test would make
   every assertion a tautology — any change to `forgeqa.__all__` would
   pass the test. Defining it in the test file creates the friction
   that makes the contract meaningful: a change to the public surface
   must be a *deliberate* three-place edit, not an accidental drift.

2. **Single-underscore prefix means private.** Any module or name
   starting with `_` is not public, not documented in
   `docs/public-api.md` §"What is public", and not in `__all__`. This
   includes:
   - `forgeqa._internal`, `forgeqa._config`, `forgeqa._compat`
   - `forgeqa._adapters.*`, `forgeqa._reporting.*`
   - Any future private subpackage

   Private modules *may* exist — they are for implementation
   organization. They must not be imported by
   `src/forgeqa/__init__.py` (see Rule 3), and they must not appear in
   `sys.modules` after a bare `import forgeqa`. The rule is enforced
   on four axes (see "Verification" below).

   Dunder names (`__version__`, `__author__`) are public only when
   documented in `docs/public-api.md` and listed in `__all__`.
   `__version__` is public; `__author__` and `__license__` are
   diagnostics. `test_no_underscore_name_in_all` enforces this: only
   dunders in `EXPECTED_ALL` are allowed in `__all__`.

3. **`src/forgeqa/__init__.py` imports only from public modules.**
   The top-level package must not import any `_`-prefixed submodule.
   Doing so would leak it into `sys.modules` after `import forgeqa`
   and make it a de-facto part of the import surface (even if not in
   `__all__`). Enforced by two tests:
   - `test_no_private_submodule_imported_by_top_level` — runtime check
     in a fresh subprocess, asserts no `forgeqa._*` module is in
     `sys.modules`.
   - `test_no_private_module_in_source_tree_top_level` — source check,
     asserts the `__init__.py` source does not contain
     `from ._<name>` or `import forgeqa._<name>` patterns.

   To re-export a name from a private module as public, use an alias
   and re-export the *name*, not the module:

   ```python
   # src/forgeqa/_internal.py defines _helper
   from forgeqa._internal import _helper as public_name  # OK

   __all__ = (..., "public_name")
   ```

   The private module *is* imported in this case (necessarily — the
   name has to come from somewhere), but the exported name is public
   and the private module's contents are not re-exported wholesale.

4. **Public submodules are new top-level modules.** When Phase 1 adds
   `forgeqa.fixtures`, `forgeqa.settings`, etc., they are:
   - top-level modules (not `_`-prefixed)
   - each with their own `__all__`
   - added to `PUBLIC_SUBMODULES` in `test_public_api.py`
     (`test_public_submodules_if_any` then asserts each submodule has
     an `__all__` tuple)
   - documented in `docs/public-api.md` §"Optional functionality"
   - added to `forgeqa.__all__` if the submodule itself (not just its
     names) is meant to be re-exported

   Adding a public submodule is **semver-minor**. The pattern is the
   same three-place edit as Rule 1, plus the submodule's own `__all__`
   and its `PUBLIC_SUBMODULES` entry.

5. **Do not use PEP 562 `__getattr__` without an ADR.** Lazy re-exports
   (`from forgeqa import Settings` without importing pydantic) are
   possible via `__getattr__` but introduce subtle behaviours
   (`hasattr` returns `True` for lazily-computed names, tracebacks
   point at `__getattr__` rather than the real module, and the
   test suite would need to assert the lazy behaviour explicitly). If a
   future API needs it, write an ADR first — ADR-002's reconsideration
   trigger already lists this as a future decision.

6. **`docs/public-api.md` and the code must agree.** The doc is the
   human-readable contract; `forgeqa.__all__` is the machine-readable
   form. A divergence fails:
   - `test_all_matches_documented_surface` (tuple vs `EXPECTED_ALL`)
   - `test_public_api_doc_exists_and_mentions_underscore_rule` (doc
     exists and states the rule)

   The doc's wording is asserted structurally, not verbatim: a change
   from "private" to "internal" does not fail the test, but a wholesale
   removal of the rule does.

#### Verification

Two layers, both required:

1. **Config-level (fast, in-process).**
   `tests/unit/test_public_api.py` parses `src/forgeqa/__init__.py`
   and `docs/public-api.md`, and asserts:
   - `forgeqa.__all__ == EXPECTED_ALL` (matches the doc)
   - `__all__` is a `tuple` (immutable)
   - every documented name is accessible
   - `get_version() == __version__`
   - no `_`-prefixed name is in `__all__` (four axes: membership,
     structure, source, runtime)
   - `docs/public-api.md` exists and states the `_`-prefix rule

   Runs in <100 ms as part of `make test`. `make verify-public-api`
   runs only these tests (~50 ms) for quick local iteration or as a
   pre-commit hook.

2. **End-to-end (wheel content).**
   `scripts/verify_build.sh` inspects the wheel's contents and asserts
   no `_`-prefixed top-level module is shipped. Defense in depth: the
   wheel already excludes `tests/`, `docs/`, etc., but a future change
   to `packages` could add a `_`-prefixed package without the config
   catching it. Runs in ~10 s; `make verify-build`.

Both run in CI on Ubuntu and macOS, on Python 3.11 and 3.12.

#### Running the verification

```bash
# Fast, config-only (~50 ms)
make verify-public-api

# Or directly
pytest tests/unit/test_public_api.py -v

# End-to-end (wheel contents)
make verify-build
```

#### See also

- [ADR-006](../adr/ADR-006-formalise-public-api-surface-and-private-module-convention.md) — decision record.
- `docs/public-api.md` — the consumer-facing contract.
- `tests/unit/test_public_api.py` — the executable contract.
- `tests/unit/test_install_contract.py` — shares `EXPECTED_ALL` via
  cross-module import (single source of truth for the expected public
  surface).
- §4.12 "Built Artifact Content Inspection" — asserts no `_`-prefixed
  top-level module is shipped in the wheel.

---

## 5. Configuration

ForgeQA's configuration is split into three concerns:

1. **The schema** (§5.1) — what a valid config looks like. Enforced by
   Pydantic v2 in `src/forgeqa/config/models.py`. No file I/O.
2. **The loader** (§5.2) — how a `forgeqa.toml` file becomes a
   `ForgeQAConfig`. `src/forgeqa/config/loader.py`.
3. **The consumer doc** (`docs/configuration.md`) — the reference for
   every field, type, default, and validation rule.

The three are separate so each is testable independently: the schema
without files, the loader without re-testing the schema, and the doc
without either. See §5.1 and §5.2 for the contributor-facing rules and
`docs/configuration.md` for the consumer-facing reference.

### 5.1 Configuration schema conventions

The ForgeQA configuration schema (`src/forgeqa/config/models.py`) is a
Pydantic v2 hierarchy. This section documents the conventions
contributors follow when adding or changing a config field.

#### Rules

1. **Every field is strictly typed.** Use the narrowest type that
   accepts the valid values:
   - `Literal[...]` for constrained string sets (e.g. `browser_name`,
     `log_level`).
   - `AnyHttpUrl` for URLs.
   - `PositiveInt` for strictly-positive integers.
   - `bool` for booleans. Pydantic v2 accepts a bounded set of string
     forms for `bool` (`"true"/"false"`, `"yes"/"no"`, `"on"/"off"`,
     `"1"/"0"`, case-insensitive); ambiguous strings like `"maybe"`
     are rejected. Do not add a custom validator for this — it is
     already the behaviour.
   - `str` with `min_length=1` for required non-empty strings.

   Do not use `str` or `int` without constraints when a constraint
   exists. A `str` `browser_name` accepts `"safari"`; a `Literal`
   fails at parse time and lists the valid values in the error.

2. **Every field has a default.** `ForgeQAConfig()` must be valid with
   no arguments. The default is the "when you don't configure
   anything" behaviour, documented in `docs/configuration.md`. A
   field with no sensible default belongs in a future sub-model with
   a construction prerequisite, not in the root config.

3. **`model_config` flags are set on every model.**
   ```python
   model_config = ConfigDict(
       extra="forbid",  # reject unknown keys
       frozen=True,  # immutable
       str_strip_whitespace=True,  # strip whitespace in strings
       validate_assignment=True,  # assignment also validates
       validate_default=True,  # defaults validated at class def
   )
   ```
   Applied to the root model *and* every sub-model, so a sub-model
   constructed in isolation has the same guarantees as one
   constructed through the root.

4. **Sub-models compose; they do not inherit.**
   `ForgeQAConfig` has five sub-model fields. A new concern (e.g.
   `DatabaseConfig` in Phase 6) is a new `BaseModel` plus one new
   field on the root, not a subclass. This keeps each sub-model
   constructible and testable in isolation.

5. **`docs/configuration.md` is updated in the same PR as any field
   change.** A new field, a changed default, a changed type, or a
   removed field requires a corresponding doc update. The doc is the
   consumer-facing reference; the schema is the enforcement. Missing
   the doc update produces a consumer-facing doc that lags the
   schema. Code review catches most cases; the test suite catches
   defaults (via `test_*_config_defaults`) and validation rules (via
   the negative cases).

6. **Cross-field validators require a concrete rule.** Do not add a
   `@model_validator` speculatively. When a concrete rule exists
   ("if A then B must be C"), add the validator and a test in the
   same PR. See ADR-007 Decision #7.

7. **Public names are re-exported from `forgeqa.config`, not
   `forgeqa.config.models`.** Consumers import
   `from forgeqa.config import ForgeQAConfig`. The `models` submodule
   is an implementation detail; it may be split into `browser.py` /
   `api.py` / etc. without a breaking change. `__all__` in
   `forgeqa/config/__init__.py` lists the public names (per ADR-006's
   `__all__` convention).

8. **The schema does not load files.** Loading `forgeqa.toml`
   (environment overlays, secret resolution, path expansion) is a
   separate concern (§5.2, WBS 1.2.2). The schema is the contract;
   the loader is the mechanism. Tests for the schema use pure-Python
   construction; tests for the loader are separate.

#### Verification

One test file, run in two contexts:

- **Local (`make verify-config`, ~50 ms).** Fast enough for
  pre-commit or a quick check before pushing.
- **CI (`make ci`, which includes `verify-config`).** Runs on the
  matrix (Ubuntu + macOS × Python 3.11 + 3.12).

`tests/unit/config/test_models.py` covers:

| Category | Tests |
| :--- | :--- |
| Defaults | `test_*_config_defaults` (one per sub-model) + `test_forgeqa_config_instantiable_with_defaults` |
| Valid values | `test_valid_browser_names_accepted`, `test_valid_log_levels_accepted` (parametrised from `get_args(Literal)`) |
| Invalid values | `test_invalid_browser_name_rejected`, `test_invalid_base_url_rejected`, `test_invalid_browser_timeout_rejected`, `test_invalid_api_timeout_rejected`, `test_invalid_log_level_rejected` |
| Edge/boundary | `test_timeout_boundary_minimum`, `test_timeout_boundary_api_minimum`, `test_bool_from_common_string_forms_accepted`, `test_ambiguous_bool_string_rejected`, `test_extra_field_rejected`, `test_extra_field_rejected_at_root` |
| Corner/composition | `test_nested_sub_model_validation`, `test_partial_override_uses_defaults_for_unspecified`, `test_full_config_round_trip_via_dict` |
| Non-functional | `test_config_is_immutable`, `test_sub_model_is_immutable`, `test_json_schema_is_generated`, `test_str_strip_whitespace_applied`, `test_any_http_url_accepts_https_and_subdomains` |

#### Running the verification

```bash
# Fast, config-only (~50 ms)
make verify-config

# Or directly
pytest tests/unit/config/test_models.py -v
```

#### See also

- [ADR-007](../adr/ADR-007-pydantic-config-hierarchy.md) — decision
  record for the configuration schema.
- `docs/configuration.md` — consumer-facing reference (every field,
  type, default, and validation rule).
- `src/forgeqa/config/models.py` — the schema source.
- `tests/unit/config/test_models.py` — the executable contract.

### 5.2 Configuration loader conventions

The ForgeQA config loader (`src/forgeqa/config/loader.py`) reads a
`forgeqa.toml` file into a `ForgeQAConfig`. This section documents the
conventions contributors follow when extending or changing the loader.

The loader is a separate concern from the schema (§5.1). The schema is
the contract; the loader is the mechanism. The split means the schema is
testable without files, and the loader is testable without re-testing
the schema.

#### Rules

1. **`load_config` is the whole public API.** One function, one
   signature (`path: Path | str | None = None`), one return type
   (`ForgeQAConfig`). A caller does not need to know about `tomllib`,
   `find_config_path`, or the Pydantic model.

2. **Search order is explicit > cwd > defaults.** An explicit path
   that does not exist is an error; a missing cwd file is not. "Explicit
   is not silent": a caller who passes `path=...` and gets a missing
   file should see `ForgeQAConfigError`, not a silent fallback to
   defaults.

3. **One exception type for all load failures.** `ForgeQAConfigError`
   covers malformed TOML, invalid values, unreadable files, and
   missing explicit paths. The original exception is preserved as
   `__cause__` for debugging. The message includes the file path; for
   syntax errors, the line/column when `tomllib` provides it.

4. **No caching.** Each call reads the file fresh. A developer who
   edits `forgeqa.toml` and calls `load_config()` again sees the new
   values. Pinned by `test_loader_does_not_cache`. Caching would
   introduce a staleness failure mode that is worse than the ~1 ms
   file read it would save.

5. **UTF-8 encoding explicitly.** `tomllib` requires UTF-8; the loader
   reads as UTF-8 to be deterministic on Windows (where the default
   encoding is platform-dependent). The `except` clause catches
   `(OSError, UnicodeDecodeError)` — both are "the file could not be
   read as UTF-8 text", which the user needs to fix.

6. **No environment-variable overrides in the current version.**
   `FORGEA_CONFIG_PATH`, `FORGEA_ENV`, and per-field overrides are
   Phase 1 follow-ups. Adding them now would expand the loader's
   contract without a driving acceptance criterion. When they land, the
   ADR-008 reconsideration trigger documents the precedence order to
   define.

7. **The loader does not modify the schema.** A field added to the
   schema (§5.1) is automatically available to the loader via
   `ForgeQAConfig(**data)`. No loader change is needed for a new field.
   This is why the schema/loader split matters: the schema changes
   alone, and the loader inherits the change.

8. **Tests use the real filesystem.** `pytest`'s `tmp_path` fixture
   plus `monkeypatch.chdir`. Mocking `Path.read_text` tests the mock,
   not the loader. The filesystem is the loader's input; the test
   should use it directly.

#### Verification

`tests/unit/config/test_loader.py` is the executable contract. It
covers:

| Category | Tests |
| :--- | :--- |
| Positive | `test_loads_valid_config`, `test_loads_partial_config_preserves_defaults`, `test_loads_explicit_path`, `test_loads_path_as_string` |
| Negative | `test_missing_file_returns_default_config`, `test_explicit_missing_path_raises`, `test_malformed_toml_raises_config_error`, `test_invalid_value_raises_config_error`, `test_unknown_key_raises_config_error` |
| Edge | `test_empty_file_returns_default_config`, `test_comments_only_file_returns_default_config`, `test_whitespace_only_file_returns_default_config` |
| Corner | `test_explicit_path_overrides_cwd`, `test_find_config_path_returns_absolute_path`, `test_find_config_path_returns_none_when_absent`, `test_find_config_path_returns_none_for_missing_directory`, `test_find_config_path_ignores_directories` |
| Boundary | `test_error_includes_file_path`, `test_errors_have_path_attribute` |
| Non-functional | `test_loader_is_idempotent`, `test_loader_does_not_cache`, `test_error_message_is_deterministic` |

`make verify-config` runs the whole `tests/unit/config/` directory,
which includes both `test_models.py` (schema) and `test_loader.py`
(loader). There is no separate `make verify-loader` — the loader is a
part of the configuration contract, and the two test files together
are the contract.

#### Running the verification

```bash
# Fast, config-only (~50 ms + loader tests)
make verify-config

# Or directly
pytest tests/unit/config/ -v
```

#### See also

- [ADR-008](../adr/ADR-008-load-forgeqa-toml-into-forgeqaconfig.md) —
  decision record for the configuration loader.
- `docs/configuration.md` §"Loading configuration" — consumer-facing
  reference (search order, errors, determinism, examples).
- `src/forgeqa/config/loader.py` — the loader source.
- `src/forgeqa/config/errors.py` — the `ForgeQAConfigError` source.
- `tests/unit/config/test_loader.py` — the executable contract.
- §5.1 "Configuration schema conventions" — the schema counterpart.

---

## 6. Security & Secret Handling

| Requirement | Implementation |
| :--- | :--- |
| **Secrets in environment variables** | Never commit `.env` files. Use `os.environ` or Pydantic Settings. |
| **Secret scanning** | Pre-commit hook (`gitleaks` or `detect-secrets`) prevents accidental commits. |
| **Redaction in logs** | Diagnostics must redact passwords, tokens, cookies, and sensitive headers. |
| **Dependency scanning** | `pip-audit` runs in CI (Phase 8). |
| **Artifact security** | Screenshots and traces are stored in a controlled `artifacts/` directory with configurable retention. |

---

## 7. Documentation Standards

| Document | Purpose |
| :--- | :--- |
| `README.md` | Project overview, quick start, links to detailed docs. |
| `docs/product-requirements.md` | What ForgeQA is building and why. |
| `docs/architecture.md` | System context, container diagrams, dependency rules. |
| `docs/engineering-standards.md` | This document—how to build, test, and contribute. |
| `docs/public-api.md` | Consumer-facing contract for the ForgeQA package. |
| `docs/configuration.md` | Consumer-facing reference for `forgeqa.toml` (every field, type, default, validation rule, and loader behaviour). |
| `docs/user-discovery.md` | Persona, problem statement, interview evidence. |
| `docs/mvp-scope.md` | MVP capabilities, user journeys, exclusions. |
| `docs/risks.md` | Technical risks and market hypotheses. |
| `docs/adr/` | Architecture Decision Records. |
| `CONTRIBUTING.md` | How to contribute, PR workflow, code of conduct. |
| `CHANGELOG.md` | Release history and breaking changes. |

---

## 8. Versioning & Release Policy

### 8.1 Semantic Versioning

| Version | Meaning | Example |
| :--- | :--- | :--- |
| **MAJOR** | Breaking changes to the public API. | `1.0.0` → `2.0.0` |
| **MINOR** | New features, backward-compatible. | `1.0.0` → `1.1.0` |
| **PATCH** | Bug fixes, backward-compatible. | `1.0.0` → `1.0.1` |

> **Pre-1.0 Policy**: While the project is in the `0.x.y` phase, breaking changes may occur in minor versions. Document them clearly in the CHANGELOG.

### 8.2 Release Checklist

Before tagging a release:

- [ ] All tests pass locally and in CI.
- [ ] Ruff lint and format checks pass.
- [ ] MyPy passes.
- [ ] `python -m build` succeeds without warnings.
- [ ] `make verify-build` passes (wheel/sdist content inspection; WBS 1.1.4).
- [ ] `make verify-install` passes (clean install from wheel; WBS 1.1.5).
- [ ] `make verify-public-api` passes (public-vs-internal contract; WBS 1.1.6).
- [ ] `make verify-config` passes (configuration schema and loader; WBS 1.2.1, 1.2.2).
- [ ] The built `.whl` installs in a clean environment.
- [ ] `make verify-deps` passes (WBS 1.1.3).
- [ ] `CHANGELOG.md` is updated.
- [ ] Version is bumped in `pyproject.toml` and `src/forgeqa/__init__.py`.
- [ ] Git tag is created (`v0.1.0`).
- [ ] Release notes are published on GitHub.

---

## 9. Document History

| Version | Date | Author | Changes |
| :--- | :--- | :--- | :--- |
| 0.1.0 | 2026-10-27 | Solo Dev | Initial engineering standards created. |
| 0.1.1 | 2026-10-27 | Solo Dev | Added "Supported Python Versions" section (WBS 0.5.1). |
| 0.1.2 | 2026-10-27 | Solo Dev | Added "Build Verification" and "PyPI Classifiers" sections (WBS 0.5.2). |
| 0.1.3 | 2026-10-28 | Solo Dev | Added §4.11 "Dependency Groups and Verification" (WBS 1.1.3); documented the constraint-style reconciliation as a Phase 1 follow-up; added `docs/public-api.md` to the Documentation Standards table; added `make verify-deps` to the Release Checklist. |
| 0.1.4 | 2026-10-28 | Solo Dev | Added §4.12 "Built Artifact Content Inspection" (WBS 1.1.4); marked §1.6 as superseded by §4.12; added `make verify-build` to the Release Checklist; added `packaging` to the Dependency Inventory (from WBS 1.1.3's `[dev]` addition). |
| 0.1.5 | 2026-10-28 | Solo Dev | Added §4.13 "Clean-Install Verification" (WBS 1.1.5); extended §1.6 superseded note to point at §4.13; added `make verify-install` to the Release Checklist; documented the `py.typed` marker requirement (PEP 561) tied to the `Typing :: Typed` classifier. |
| 0.1.6 | 2026-10-28 | Solo Dev | Added §4.14 "Public vs. Internal Module Conventions" (WBS 1.1.6); documented the `EXPECTED_ALL` test-authoritative pattern and the cross-module sharing with `test_install_contract.py`; added `make verify-public-api` to the Release Checklist; cross-referenced `docs/public-api.md` and ADR-006. |
| 0.1.7 | 2026-10-28 | Solo Dev | Added §5 "Configuration" and §5.1 "Configuration schema conventions" (WBS 1.2.1); added `make verify-config` to the Release Checklist; added `docs/configuration.md` to the Documentation Standards table; noted Pydantic's bounded bool coercion in §5.1 rule 1. |
| 0.1.8 | 2026-10-28 | Solo Dev | Added §5.2 "Configuration loader conventions" (WBS 1.2.2); added a §5 preamble pointing at `docs/configuration.md` and the schema/loader split; added the loader to §5.1 rule 8's cross-reference; expanded the §8.2 Release Checklist entry to cover both schema and loader; expanded the §7 Documentation Standards entry for `docs/configuration.md` to mention loader behaviour. |
