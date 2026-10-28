# ADR-004: Verify built artifacts contain exactly the intended files, using isolated inspection in CI

> **Status**: Accepted
> **Date**: 2026-10-28
> **Deciders**: Solo Developer
> **Consulted**: None
> **Informed**: None

## Context

WBS 1.1.4 requires that `python -m build` produce both a wheel and an sdist,
that the wheel contain `forgeqa/__init__.py` and `LICENSE`, and that the
wheel **not** contain `tests/` or `docs/`. The wheel and sdist are part of
the public contract, not incidental by-products: the wheel is what
`pip install forgeqa` consumes from PyPI; the sdist is what
`pip install forgeqa --no-binary :all:` consumes (and what some downstream
packagers use).

The build targets are declared in `pyproject.toml`
(`[tool.hatch.build.targets.wheel]`, `[tool.hatch.build.targets.sdist]`).
A declaration alone is not a verification:

- Hatchling's file selection is **VCS-aware**: it includes files tracked in
  git and excludes files matched by `.gitignore`. A change to `.gitignore`
  (e.g. adding `docs/build/` to ignore generated docs) could accidentally
  pull `docs/` into the wheel if the exclusion is not explicit.
- `[project].license = { file = "LICENSE" }` bundles the file at
  `forgeqa-X.Y.Z.dist-info/licenses/LICENSE`. Switching to
  `license = { text = "MIT" }` — a small, well-intentioned edit for
  PEP 639 migration — would silently drop the file from the wheel. No test
  would fail unless the built artifact is inspected.
- A future change to `[tool.hatch.build.targets.wheel].packages` (e.g.
  adding `src/forgeqa_tools`) could accidentally broaden the selection to
  include `tests/` if the exclusion is not explicit.
- The "wheel does not contain `tests/`" criterion is a **negative**
  assertion. A test suite that reads `pyproject.toml` and asserts `tests`
  is in the `exclude` list can pass while hatchling still ships `tests/`
  for a reason the config does not capture. Only inspecting the archive
  proves absence.

The verification must be **end-to-end** (inspect the built artifacts) and
must be complemented by a fast config-level test that catches most drift
before the slow build runs. It must run in CI so regressions are caught
before merge, and locally via `make verify-build` so contributors can check
their changes before pushing. It must run on both supported Python
versions (3.11 and 3.12) and at least Linux and macOS, because `unzip -l`
and `tar -tzf` output differs subtly between BSD (macOS) and GNU (Linux)
tools — a pattern-parsing bug in the verifier itself would otherwise only
show up in CI on a different OS than the developer used.

Forces at play:

- **Correctness:** the wheel must contain `forgeqa/__init__.py` and
  `LICENSE`; it must not contain `tests/`, `docs/`, `examples/`,
  `scripts/`, or build artifacts.
- **Completeness:** the sdist must contain the source tree, tests, docs,
  and metadata files so downstream consumers can build and test from
  sdist.
- **Auditability:** a reviewer reading `pyproject.toml` should see the
  content contract without needing to know hatchling's narrowing
  semantics.
- **Independence:** the verifier must work even if `forgeqa` itself is
  broken — otherwise a broken install masks content problems.
- **Speed:** the verification must be fast enough to run on every push
  and every local CI invocation (~10 s target).
- **CI cost:** the matrix must be small enough to justify (4 jobs:
  2 OS × 2 Python versions).

## Decision

1. **Two layers of verification.**

   - **Config-level (fast, in-process).**
     `tests/unit/test_build_config.py` parses `pyproject.toml` and asserts
     the build-target shape:
     - wheel target declares `packages = ["src/forgeqa"]`
     - wheel exclude list contains `tests`, `docs`, `examples`, `scripts`
     - sdist include list contains `src`, `tests`, `docs`, `README.md`,
       `LICENSE`, `pyproject.toml`
     - sdist exclude list contains `dist`, `build`, `.venv`,
       `*.egg-info`, `__pycache__`
     - `[project].license` references the `LICENSE` file (for bundling)
     - build-targets section exists and is parseable

     Runs in <100 ms as part of `make test`.

   - **End-to-end (slow, isolated).**
     `scripts/verify_build.sh` (or `make verify-build`) runs
     `python -m build` into a fresh temp directory, then:
     - Lists the wheel with `unzip -l` and asserts required entries are
       present (`forgeqa/__init__.py`,
       `forgeqa-X.Y.Z.dist-info/licenses/LICENSE`, `METADATA`, `WHEEL`).
     - Asserts forbidden entries are absent from the wheel (`tests/`,
       `docs/`, `examples/`, `scripts/`, `*.egg-info/`, `__pycache__/`,
       `*.pyc`).
     - Lists the sdist with `tar -tzf` and asserts the source tree,
       tests, docs, and metadata files are present.
     - Asserts build artifacts are absent from the sdist (`dist/`,
       `build/`, `.venv/`, `*.egg-info/`, `__pycache__/`, `*.pyc`).

2. **Build into a fresh temp directory, not `dist/`.** The verifier must
   inspect the artifact it just built, not a stale one from a prior run.
   `mktemp -d` also makes the verifier safe under parallel CI runs.
   `BUILD_DIR` overrides for reproducibility.

3. **Use `unzip -l` and `tar -tzf`, not Python `zipfile`/`tarfile`.**
   The verifier must work even if `forgeqa` is not installed or is broken
   — otherwise a broken install masks content problems. Shell tools are
   pre-installed on every supported CI runner and dev machine and produce
   stable text output. This is the same lesson as WBS 1.1.3's
   `verify_deps.sh`: verification tooling must not depend on the package
   being verified.

4. **Pattern-based `grep -E` over the listing.** Extending the contract
   (e.g. adding a new top-level package, or a new forbidden directory) is
   a one-line change to the arrays in `verify_build.sh`
   (`WHEEL_REQUIRED`, `WHEEL_FORBIDDEN`, `SDIST_REQUIRED`,
   `SDIST_FORBIDDEN`), not a new function.

5. **Anchored forbidden patterns (`(^|/)`).** `(^|/)tests/` matches
   `tests/` at any depth but not `mytests/` or `contests/`. The
   unanchored `grep -E "tests/"` would produce false positives on
   legitimate files like `foo/tests.txt`. This is a real correctness
   property, not pedantry — it is the difference between a verifier that
   fails only on real regressions and one that fails on
   plausibly-triggered false alarms.

6. **The wheel and sdist have different contracts.** The wheel ships only
   the package; the sdist ships the source tree so downstream can build
   and test offline. `tests/` and `docs/` are **required** in the sdist
   and **forbidden** in the wheel. A single verifier covering both
   scenarios keeps the two contracts in one auditable place — they are
   easy to conflate.

7. **Explicit `exclude` in `pyproject.toml`, in addition to `packages`
   narrowing.** Hatchling's `packages = ["src/forgeqa"]` already excludes
   `tests/` and `docs/`, but the exclusion is implicit: it depends on the
   reader knowing hatchling's semantics. Adding explicit
   `[tool.hatch.build.targets.wheel].exclude` entries makes the invariant
   auditable in the config and robust against a future change to
   `packages`. Same for sdist: `include` already lists the source-tree
   directories, but explicit `exclude` for `dist`, `build`, `.venv`,
   `*.egg-info`, `__pycache__` is belt-and-braces.

8. **Run in CI on Ubuntu + macOS, Python 3.11 + 3.12.** Platform-specific
   output-format differences between BSD and GNU `unzip`/`tar` are
   caught by the matrix. Windows is deferred to a follow-up (the tools
   are present on `windows-latest` via Git for Windows, but path handling
   differs; validate the patterns against Windows output first).

9. **Add `verify-build` to `make ci`.** Local CI catches the same
   regressions as remote CI, reducing the "works on my machine" gap.

10. **Do not use `setup.py` to inspect or modify the archive.**
    `python -m build` is the PEP 517 standard. Any post-build step that
    mutates the wheel outside `pyproject.toml` is hidden from the config
    and from downstream packagers. If a file must not be in the wheel,
    exclude it in `[tool.hatch.build.targets.wheel].exclude` — not by
    deleting it after the build. This is documented in
    `docs/engineering-standards.md` §4.12 rule 6.

## Alternatives Considered

| Alternative | Reason Rejected |
| :--- | :--- |
| Config-only verification (pytest reads `pyproject.toml`) | Fast but cannot prove what hatchling's VCS-aware selection actually includes. The negative assertion ("wheel does not contain tests/") is exactly the kind a config read cannot prove. Kept as a *complement* (Decision #1), not a replacement. |
| Extract the wheel and inspect the filesystem | Slower and requires a temp dir; risks permission issues on some CI runners. `unzip -l` gives the same information (file paths in the archive) without extracting. |
| Use Python's `zipfile` / `tarfile` modules | Adds a runtime dependency on `forgeqa` being importable — exactly the kind of install-state dependency the verifier must avoid. Shell tools are pre-installed on every runner and dev machine. |
| Inspect only the wheel (not the sdist) | The sdist is what downstream packagers and `pip install --no-binary :all:` consume. Its contract (source tree, tests, docs present) is different from the wheel's and is equally part of the public surface. |
| Use `twine check` alone | `twine check` validates `METADATA` renderability and `long_description` content type. It does not inspect the package layout (`forgeqa/__init__.py` presence) or assert absence of `tests/`/`docs/`. The two tools are complementary: `twine check` is a PyPI gate, `verify_build.sh` is a content gate. |
| Build once, inspect both `dist/` and the temp dir | `dist/` may contain stale artifacts from a prior run. Building into a fresh temp dir guarantees the verifier inspects only what it built. |
| Run only on Ubuntu | macOS `unzip` and `tar` have subtly different output formats (notably `tar -tzf` on BSD tar vs. GNU tar). Testing both OSes catches format-dependent parsing bugs in the verifier itself. |
| Assert exact file lists rather than patterns | Hatchling's output varies by Python version (`__pycache__` entries differ), by hatchling version (new metadata fields), and by platform. Exact lists would need constant maintenance. Patterns assert the contract (presence of the package, absence of tests/docs) without coupling to hatchling internals. |
| Add `setup.py`-based verification alongside `python -m build` | `python -m build` is the PEP 517 standard; `setup.py` is deprecated. No value. |
| Post-process the wheel to delete `tests/` (e.g. `zip -d`) | Hides the intent from `pyproject.toml` and from downstream packagers. If `tests/` must not be in the wheel, exclude it at the config level. The post-process approach also invalidates the `RECORD` hashes unless they are regenerated, which is easy to get wrong. |
| Use `pip install --no-binary :all: forgeqa` and inspect the installed files | Slow (~30 s), requires a venv, and inspects the *installed* state rather than the *archive*. The installed state can differ from the archive (e.g. `.pyc` compilation, `.dist-info` relayout). The archive is the contract; the install is a downstream effect. |
| Only check the wheel for `forgeqa/__init__.py` presence | Does not prove the wheel is *usable* (a wheel with `__init__.py` but a broken `METADATA` installs but fails to import). The required-pattern list includes `METADATA`, `WHEEL`, and the LICENSE path, which together prove the wheel is well-formed. |

## Consequences

### Positive

- **Wheel and sdist contents are proven, not declared.** A regression
  (e.g. `license = { text = ... }`, or `tests` removed from the exclude
  list) fails CI on the next push, with a clear diagnostic identifying
  the missing or leaked entry.
- **Configuration drift is caught in <100 ms.** The config-level test
  runs as part of `make test`, so a typo in `pyproject.toml` fails fast
  and locally.
- **Absence of `tests/`/`docs/` in the wheel is proven.** The only way
  to assert absence in a built artifact is to inspect the artifact. The
  verifier does exactly that.
- **The two contracts (wheel vs. sdist) are in one auditable place.**
  A future contributor extending either contract sees both at the top of
  `verify_build.sh`, with the required/forbidden pattern arrays.
- **Contributors can check before pushing.** `make verify-build` is ~10 s
  locally, and `make ci` includes it.
- **The verifier is dependency-free.** It works in a bare shell, without
  a venv, without `forgeqa` being installed. This makes it usable in
  bootstrap scenarios (e.g. verifying a wheel on a fresh machine) and
  makes its correctness independent of the package it is verifying.
- **`make ci` mirrors remote CI.** A contributor can run the same checks
  locally that CI runs, eliminating a large class of "works on my
  machine" surprises.

### Negative

- **~10 s per verifier run.** Builds a wheel + sdist (~5 s) plus two
  archive listings (~1 s each). Acceptable locally and in CI.
- **CI matrix is 4 jobs (2 OS × 2 Python).** Adds ~4 × 1 min of
  wall-clock CI time, mostly parallel.
- **The verifier builds its own artifacts.** If `make build` has already
  run, this is redundant (the artifacts are cached in `dist/`). The
  verifier still builds into a temp dir to ensure it inspects a fresh
  artifact, not a stale one.
- **`unzip -l` output format is not perfectly stable across BSD and GNU
  `unzip`.** The pattern-based `grep -E` is tolerant of format differences
  (it matches on file paths, which appear in every format), but a future
  verifier change to parse columns directly would be fragile. Kept as
  pattern matching precisely to avoid this.
- **The sdist `tar -tzf` output has `forgeqa-X.Y.Z/` as a prefix.**
  Patterns must account for this (the `(^|/)` anchor does). A future
  contributor adding a new pattern should test against the actual output,
  not assume it matches the wheel.
- **The `exclude` lists in `pyproject.toml` are belt-and-braces, not
  strictly necessary.** `packages = ["src/forgeqa"]` already excludes
  `tests/` and `docs/`. The redundancy is intentional (auditability +
  robustness) but a reviewer might question it. The rationale is
  documented inline above the wheel target.
- **The verifier fails fast on the first failing pattern.** A run that
  finds two regressions reports only the first. This is intentional:
  fix one, re-run, find the next. A "report all failures" mode was
  rejected for the diagnostic complexity versus the marginal convenience.

### Neutral

- `Makefile` gains one target (`verify-build`) and one addition to `ci`.
- `.github/workflows/quality.yml` gains one job.
- `README.md` gains one row in the Development Commands table.
- `pyproject.toml` gains explicit `exclude` blocks on both build
  targets. Behaviour is largely unchanged (hatchling's defaults already
  exclude these), but the config is now auditable.
- `docs/engineering-standards.md` gains §4.12 and one item in §7.2;
  §1.6 is marked as superseded by §4.12 (install verification remains
  valid; content inspection is additive).
- `tests/unit/test_build_config.py` is a new file in the fast test
  suite; `scripts/verify_build.sh` is a new file in the build-tooling
  directory. Neither changes runtime behaviour.

## Reconsideration Trigger

Revisit this decision if any of the following occurs:

- **Hatchling's default file selection changes.** If hatchling starts
  including files it previously excluded (e.g. a new metadata field's
  generated file), the forbidden patterns may need adjustment. Concrete
  signal: the `wheel` or `sdist` scenario starts failing with a
  forbidden-entry diagnostic that is actually a hatchling default.
- **A new top-level package is added.** E.g. `forgeqa_cli/` in Phase 2.
  This requires adding a required pattern to `WHEEL_REQUIRED` (so the
  verifier proves the new package is shipped) and a corresponding
  exclude to `[tool.hatch.build.targets.sdist]` if needed.
- **A new forbidden directory is introduced.** E.g. `benchmarks/` in
  Phase 5. Add it to `WHEEL_FORBIDDEN` (and possibly `SDIST_FORBIDDEN`).
- **The build backend changes.** If `forgeqa` moves off hatchling (e.g.
  to `setuptools` or `flit`), the verifier's pattern assumptions (wheel
  path `forgeqa/`, sdist root `forgeqa-X.Y.Z/`) may need adjustment.
  Re-validate against the new backend's output before merging.
- **`twine check` is extended to cover more of the artifact.** If
  `twine check` starts inspecting package layout (currently it does
  not), the verifier's wheel checks may be partially redundant. Keep
  both for defense-in-depth; `twine check` is a PyPI gate, the verifier
  is a content gate.
- **Windows is added to the CI matrix.** `unzip` and `tar` are present
  on `windows-latest` via Git for Windows, but their path handling
  differs. Validate the patterns against Windows output before adding
  Windows to the matrix.
- **The `(^|/)` anchor produces a false positive.** If a future file
  happens to match `(^|/)tests/` without being the `tests/` directory
  (e.g. `forgeqa/internal/tests/`), refine the pattern. Document the
  refinement in a comment in `verify_build.sh`.
- **PEP 639 license migration is adopted.** Switching to
  `license = "MIT"` + `license-files = ["LICENSE"]` would change the
  path in the wheel from `.dist-info/licenses/LICENSE` to the same path
  (the bundled location is PEP 639-compliant). The `WHEEL_REQUIRED`
  pattern would remain valid, but ADR-001's reconsideration trigger
  should be reconciled with ADR-004's before the migration lands.
  Schedule as a 0.5.2 revision.
- **The verifier's runtime exceeds ~1 min.** If a future extra pulls a
  large transitive dependency into the build, the build itself becomes
  slow and the verifier inherits that. Split wheel and sdist verification
  into parallel CI jobs at that point.
- **`python -m build` produces additional artifact types** (e.g. a
  `.zip` for Windows). The verifier currently checks `.whl` and
  `.tar.gz`. Extend `build_artifacts()` and the scenario runners if
  another format is adopted.

## Related

- WBS 1.1.4 — Build Verification & Wheel Content Inspection (this
  decision)
- WBS 1.1.1 — Finalise Package Metadata & License (established the
  `license = { file = "LICENSE" }` form and the build targets that this
  ADR verifies)
- WBS 1.1.3 — Configure & Verify Dependency Groups (established the
  two-layer verification pattern — config-level + end-to-end — that this
  ADR reuses)
- Phase 0.5.2 — Build verification (predecessor; verified the package
  installs but not the archive contents; see §1.6 of engineering
  standards)
- ADR-001 — Adopt MIT license file and PEP 621-compliant package
  metadata
- ADR-002 — Resolve package version at import time via
  `importlib.metadata` and keep top-level imports dependency-free
- ADR-003 — Verify optional dependency groups via an isolated-venv
  script in CI
- `scripts/verify_build.sh` — the end-to-end verifier
- `tests/unit/test_build_config.py` — the config-level complement
- `docs/engineering-standards.md` §4.12 "Built Artifact Content
  Inspection" — contributor-facing rules
- `pyproject.toml` `[tool.hatch.build.targets]` — the build config and
  its content-contract comment block
- PEP 517 — A build-system independent format for source trees:
  https://peps.python.org/pep-0517/
- PEP 621 — Storing project metadata in `pyproject.toml`
  (`license = { file = ... }`):
  https://peps.python.org/pep-0621/
- PEP 639 — Improving License Clarity with Better Package Metadata
  (future migration; relevant to the `WHEEL_REQUIRED` LICENSE path):
  https://peps.python.org/pep-0639/
- Hatchling build configuration:
  https://hatch.pypa.io/latest/config/build/
- Python Packaging User Guide — "Packaging and distributing projects":
  https://packaging.python.org/en/latest/tutorials/packaging-projects/
- `pip install --no-binary :all:` (the consumer of the sdist):
  https://pip.pypa.io/en/stable/cli/pip_install/#cmdoption-no-binary
