# ADR-003: Verify optional dependency groups via an isolated-venv script in CI

> **Status**: Accepted
> **Date**: 2026-10-28
> **Deciders**: Solo Developer
> **Consulted**: None
> **Informed**: None

## Context

WBS 1.1.3 requires that ForgeQA's optional dependency groups behave exactly
as documented:

- `pip install forgeqa` must not install Playwright or HTTPX.
- `pip install forgeqa[ui]` must install Playwright and must not install HTTPX.
- `pip install forgeqa[api]` must install HTTPX and must not install Playwright.
- `pip install forgeqa[all]` must install both.

The groups are declared in `pyproject.toml`
(`[project.optional-dependencies]`). A declaration alone is not a
verification. Nothing prevents a future change to `[project].dependencies`
from accidentally pulling in `httpx` — e.g. a helper imports it
transitively, the author adds it to core "to fix the error", and the next
`pip install forgeqa` ships an unrequested HTTP client. Nor does a
declaration prevent a change to `[ui]` from also adding `httpx` "while
we're here". Without an explicit check, the failure mode is silent from the
maintainer's perspective and confusing from the consumer's: `forgeqa` core
now installs an HTTP client the consumer never asked for, and the resulting
bug report is hard to triage because the declaration *looks* correct.

The verification must be **end-to-end**, not just a static read of
`pyproject.toml`:

- A static read cannot detect a **transitive** leak — a runtime dependency
  of `pydantic`, `pytest`, or any future core dep that itself depends on
  `httpx`. Unlikely today, but not impossible tomorrow, and exactly the
  class of bug that WBS 1.1.3 exists to prevent.
- A static read cannot verify that `pip install forgeqa` actually
  **succeeds** against the published wheel — only that the metadata on disk
  *claims* it will.
- A static read cannot detect **environment-level** issues: name-shadowing
  from an editable install on the developer's path, a metadata field typo
  that parses as TOML but breaks `pip` resolution, a broken wheel that
  installs but does not import.

A real-venv verification is the only way to prove the end-to-end contract.
But it is slow (~30 s per scenario × 5 scenarios ≈ 2.5 min), so it must be
**complemented** by a fast config-level test, not replaced by it.

The verification must run **in CI** so regressions are caught before merge,
and **locally** (via `make verify-deps`) so contributors can check their
changes before pushing. It must run on both supported Python versions (3.11
and 3.12) and at least Linux and macOS, because Playwright's wheel
availability differs across platforms and a dependency resolution difference
between 3.11 and 3.12 would go undetected without the matrix.

## Decision

1. **Two layers of verification.**

   - **Config-level (fast, in-process).**
     `tests/unit/test_dependency_groups.py` parses `pyproject.toml` and
     asserts the group shape:
     - `[project].dependencies` contains no optional dependency
       (`playwright` or `httpx`).
     - `ui` declares Playwright and nothing else.
     - `api` declares HTTPX and nothing else.
     - `all` is a superset of `ui ∪ api ∪ dev`.
     - `all` is an explicit list, not a self-reference.
     - `requires-python` matches the Phase 0.5.1 support matrix.

     Runs in <100 ms as part of `make test`.

   - **End-to-end (slow, isolated).**
     `scripts/verify_deps.sh` (or `make verify-deps`) builds a wheel from
     local source, installs it in five fresh virtual environments (one per
     scenario), and asserts that the installed modules match the declared
     groups:
     - `core` — no playwright, no httpx; `forgeqa` imports.
     - `ui` — playwright yes, httpx no; `forgeqa` imports.
     - `api` — httpx yes, playwright no; `forgeqa` imports.
     - `all` — both yes; `forgeqa` imports.
     - `dev` — neither; `ruff` and `mypy` present; `forgeqa` imports.

2. **Build a wheel and install from it, not `pip install -e .`.**
   Editable installs use a different metadata path (a `.pth` file into
   `src/`, plus editable-specific metadata) and do not prove the wheel is
   self-contained. A PyPI consumer installs a wheel; the verifier uses the
   same artifact type.

3. **One fresh venv per scenario, `trap`-cleaned on exit.** Venvs are
   created under `mktemp -d` (unique per invocation, safe under parallel
   CI runs) and removed on `EXIT INT TERM` unless `KEEP_VENVS=1`.
   Scenarios cannot leak into each other. `--no-cache-dir` in `pip install`
   prevents a cached wheel of an older `forgeqa` from masking a change to
   `pyproject.toml`'s extras.

4. **Assertions use `import <module>`, not `pip show`.**
   `pip show` passes for an installed-but-broken module (missing compiled
   dependency, corrupted install, name-shadowing). `import` proves
   usability, which is what the consumer will do. For absence checks,
   `import` failing is the correct signal — it is the same signal the
   consumer's first failed import would produce.

5. **Five scenarios, not three.** In addition to the three the WBS names
   (`core`, `ui`, `api`), the verifier also checks `all` (both optional
   deps present) and `dev` (neither optional dep present). `all` is the
   obvious union test; `dev` guards against a future mistake where someone
   adds `playwright` to `[dev]` "for convenience", silently breaking the
   isolation invariant for every developer.

6. **Run in CI on Ubuntu + macOS, Python 3.11 + 3.12.** Platform-specific
   resolution differences (notably Playwright's Linux vs. macOS wheel
   availability) are caught by the matrix. Windows is deferred to a
   follow-up: Playwright's Windows install is heavier and its resolution is
   already exercised by the reference-app CI.

7. **Add `verify-deps` to `make ci`.** Local CI catches the same
   regressions as remote CI, reducing the "works on my machine" gap.

8. **Pin `ruff` and `mypy` in `[dev]` to the exact versions used by
   `.pre-commit-config.yaml`.** This is a carry-over from WBS 1.1.2's
   tooling-drift incident (venv `ruff 0.17.3` vs. hook `v0.6.9` caused
   every commit to trigger a spurious reformat). A `make tooling-check`
   target fails CI when the two sides disagree. It is bundled into this
   ADR because it is a precondition for `make hooks-run` being idempotent
   on the 1.1.3 branch — without it, contributors cannot trust a green
   commit.

## Alternatives Considered

| Alternative | Reason Rejected |
| :--- | :--- |
| Static-only verification (`pytest` reads `pyproject.toml`) | Fast but cannot detect transitive leaks, broken wheels, or environment-level issues. The WBS acceptance criteria are about `pip install` behaviour, which static verification does not exercise. Kept as a *complement* (Decision #1), not a replacement. |
| `pip install --dry-run` (or `pip install --report`) | Reports what pip *would* install, but does not verify the resulting environment imports cleanly, nor that `pip install` succeeds end-to-end. Halfway between static and end-to-end; strictly worse than either for this contract. |
| `pip install -e .` in a fresh venv | Faster than building a wheel, but uses a different metadata path and does not prove the wheel is self-contained. A consumer installs a wheel from PyPI, not an editable tree. |
| Install everything in one venv and uninstall/reinstall extras | Faster (one venv), but scenarios can leak: an uninstall that fails leaves state behind, and a package that re-appears via a transitive dep masks the failure. Separate venvs are ~30 s slower total and eliminate the failure mode. |
| Use `pip freeze` or `pip list` to compare against an expected set | Fragile: pip's output format varies across versions; the expected set needs constant maintenance; transitive deps of the *expected* deps are hard to separate from leaks. `import <module>` is the minimal, robust check. |
| Only run in CI, not locally | Contributors cannot check their changes before pushing; CI failures turn into round-trips. `make verify-deps` costs 30 s locally and saves the round-trip. |
| Run only on Ubuntu (no macOS in CI matrix) | macOS is the second-most-common developer OS after Linux and has different wheel availability for Playwright. The marginal cost is one extra CI job (~2 min) per matrix entry. Worth it. |
| Run only on Python 3.12 (the "current" supported version) | 3.11 is in the support window (`requires-python = ">=3.11,<3.13"`). A resolution difference between 3.11 and 3.12 would go undetected without the matrix. |
| Subprocess-level test without wheel install (e.g. `python -c "import forgeqa[ui]"` from the dev venv) | The dev venv has extras installed via `make install-all`; it is not a clean environment. Only a fresh venv can prove what a consumer actually receives. |
| Use `pip check` after install | Validates that installed packages' requirements are satisfied, but does not validate the *absence* of a module. `pip check` passes if playwright is installed and required; it does not fail if httpx is installed but unwanted. Wrong tool for the job. |

## Consequences

### Positive

- **Contract is proven, not just declared.** A regression in the extras
  (someone adds `httpx` to `[project].dependencies`, or `playwright` to
  `[dev]`) fails CI on the next push, with a clear diagnostic pointing at
  the scenario that failed.
- **Configuration drift is caught in <100 ms.** The config-level test runs
  as part of `make test`, so a typo in `pyproject.toml` fails fast and
  locally — not 30 s into `verify_deps.sh`.
- **Transitive leaks are caught.** If a future runtime dependency of
  `pydantic` (or any core dep) pulls in `httpx`, the `core` scenario
  fails: `import httpx` succeeds when it should not. Static verification
  cannot catch this.
- **Consumers see the contract in the README.** The extras table in
  `README.md` §"Optional extras" is backed by the verifier; the docs
  cannot drift from the code without CI failing.
- **Contributors can check before pushing.** `make verify-deps` is 30 s
  locally, and the `make ci` target includes it, so pre-push failures
  mirror CI failures.
- **Five scenarios instead of three.** The WBS requires three; the extra
  two (`all`, `dev`) guard against mistakes that would otherwise be silent
  for a maintainer but loud for consumers.
- **Platform coverage.** Ubuntu + macOS × Python 3.11 + 3.12 catches
  Playwright's wheel-availability differences without over-testing
  platform-stable dependencies (HTTPX is pure-Python and stable across
  all supported platforms).

### Negative

- **~30 s per scenario, ~2.5 min total.** Five scenarios × ~30 s each
  (wheel install + optional dep install). Acceptable in CI (adds one job);
  acceptable locally when scoped (`./scripts/verify_deps.sh core` checks
  one scenario in ~30 s).
- **CI matrix is 4 jobs (2 OS × 2 Python).** Adds ~4 × 2 min of wall-clock
  CI time, mostly parallel. Acceptable for the coverage.
- **The verifier builds its own wheel.** If `make build` has already run,
  this is redundant (the wheel is cached in `dist/`). The verifier still
  runs `python -m build --wheel` to ensure the wheel it tests is built from
  the *current* source tree, not a stale `dist/` artifact.
- **`packaging` is added to `[dev]` and `[all]`.** It is already
  transitively present via `pip`/`build`/`twine`; pinning it explicitly
  makes the verify script's optional version comparison honest about its
  dependency. Doesn't affect runtime consumers.
- **The verifier fails fast on the first failing scenario.** A run that
  finds two regressions reports only the first. This is intentional:
  fix one, re-run, find the next. A "report all failures" mode was
  rejected for the diagnostic complexity (per-scenario cleanup handling
  on error) versus the marginal convenience.
- **`ruff` and `mypy` pins in `[dev]` are load-bearing.** A future
  contributor who "just bumps ruff to get the new rule" reintroduces the
  1.1.2 drift. The `make tooling-check` target mitigates this but requires
  discipline to keep the two files aligned when bumping.

### Neutral

- `README.md` grows by ~30 lines for the extras table. It is the
  documentation WBS 1.1.3 explicitly requires.
- `Makefile` gains one target (`verify-deps`) and one addition to `ci`.
- `.github/workflows/quality.yml` gains one job. The workflow's overall
  structure is unchanged.
- `docs/engineering-standards.md` gains a new §4.11 documenting the four
  rules and the two verification layers.
- The extras in `pyproject.toml` are structurally unchanged from 1.1.1;
  the only edit is adding `packaging` to `[dev]` and `[all]`. The WBS's
  "configure" step was largely already done in 1.1.1; this ADR's
  contribution is the "verify" step.

## Reconsideration Trigger

Revisit this decision if any of the following occurs:

- **Scenario runtime becomes excessive.** If `verify_deps.sh` exceeds
  ~5 min total (e.g. because a future extra pulls in a 500 MB toolchain),
  split the CI job into parallel per-scenario jobs. Current runtime is
  ~2.5 min sequentially; parallelising is a config-only change.
- **A new extra is added** (e.g. `[selenium]`, `[appium]`). Extending the
  contract requires extending the verifier. The ADR's five-scenario
  structure is the pattern; the list is data, not logic. Follow the
  four-step procedure documented in
  `docs/engineering-standards.md §4.11`.
- **A transitive dependency leak occurs in production.** If a user
  reports that `pip install forgeqa` installed `httpx`, the verifier
  failed to catch it — add the specific check to `core` and revisit
  whether the verifier's assumptions (e.g. "installing from a locally
  built wheel matches installing from PyPI") hold.
- **Playwright or HTTPX changes packaging.** If either switches to a
  pure-Python wheel or starts pulling in additional transitive deps, the
  verifier's `import <module>` checks remain valid; the alternative
  "run playwright's installer" check is explicitly out of scope (it
  downloads a browser, which is too slow for CI).
- **PyPI's resolver changes behaviour for extras.** E.g. PEP 639-era
  changes to how extras are resolved. Revisit the verifier's pip version
  pin (currently whatever `pip install` resolves to) and consider pinning
  pip itself.
- **Windows is added to the CI matrix.** The ADR defers Windows; if a
  contributor adds it, verify that `scripts/verify_deps.sh` uses
  `python -m pip` (works on Windows) rather than bare `pip`, and that
  the venv paths under `mktemp -d` work on Windows (they do not — use
  `$TMPDIR`/`$TEMP` or an explicit `VENV_BASE`).
- **The tooling-version pins become burdensome.** If maintaining parity
  between `pyproject.toml [dev]` and `.pre-commit-config.yaml` costs more
  than it saves, consider pre-commit's `additional_dependencies` (which
  installs the tool from the hook's pinned version, ignoring `[dev]`).
  This trades one problem (two pins to maintain) for another (no local
  ruff version, so `make fmt` requires pre-commit to be installed).

## Related

- WBS 1.1.3 — Configure & Verify Dependency Groups (this decision)
- WBS 1.1.1 — Finalise Package Metadata & License (declared the four
  extras; provided the installable package this ADR verifies)
- Phase 0.5.3 — Dependency groups specification
- ADR-001 — Adopt MIT license file and PEP 621-compliant package metadata
- ADR-002 — Resolve package version at import time via
  `importlib.metadata` and keep top-level imports dependency-free
  (established the "core imports nothing heavy" invariant that this ADR
  verifies at the install level)
- `scripts/verify_deps.sh` — the end-to-end verifier this ADR documents
- `tests/unit/test_dependency_groups.py` — the fast config-level
  complement
- `docs/engineering-standards.md` §4.11 "Dependency Groups and
  Verification" — contributor-facing rules
- `README.md` §"Optional extras" — consumer-facing documentation of each
  extra
- `docs/public-api.md` §"Optional functionality" — what each extra
  enables at the API level
- PEP 508 — Dependency specification for Python Software Packages:
  https://peps.python.org/pep-0508/
- PEP 621 — Storing project metadata in `pyproject.toml`
  (`optional-dependencies`):
  https://peps.python.org/pep-0621/#dependencies-optional-dependencies
- `pip install --report` (considered and rejected):
  https://pip.pypa.io/en/stable/cli/pip_install/#cmdoption-report
- `packaging.specifiers.SpecifierSet`:
  https://packaging.python.org/en/latest/specifications/version-specifiers/
