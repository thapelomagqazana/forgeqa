# ADR-005: Verify installed wheel works outside the source checkout using an isolated venv and a source-tree-free cwd

> **Status**: Accepted
> **Date**: 2026-10-28
> **Deciders**: Solo Developer
> **Consulted**: None
> **Informed**: None

## Context

WBS 1.1.5 requires that `pip install <wheel>` succeed in a clean
environment, that `import forgeqa` work without the repo being on
`PYTHONPATH`, that `scripts/verify_install.sh` run in CI, and that the
script clean up after itself. The traceability KPI is "The package is
installable and usable outside the source checkout."

WBS 1.1.4 (ADR-004) established that the wheel and sdist **contain** the
right files. Content correctness is necessary but not sufficient: a wheel
with all the right files can still fail to install (metadata error,
missing dependency, broken entry point) or to import (missing transitive
dependency, `importlib.metadata` misconfiguration, `.pth` shadowing).
Only an end-to-end install in a clean environment proves the wheel is
usable.

The tricky part is "clean environment". Two forces work against us:

1. **The developer's `.venv` is not clean.** `make install` runs
   `pip install -e ".[dev]"`, which writes a `.pth` file into the venv's
   `site-packages/` that adds `src/` to `sys.path`. In that venv,
   `import forgeqa` succeeds *regardless of whether the wheel is
   installable*, because the editable install shadows the wheel. Any
   test of the wheel's installability run in the developer's `.venv` is
   meaningless.

2. **The repo root is not clean.** Even inside a fresh venv, running
   `python -c "import forgeqa"` from the repo root puts the current
   directory on `sys.path[0]`, and `src/` is one `cd` away. A forgotten
   `cd` or a stale `cd` in CI would silently shadow the installed
   package. The test would pass for the wrong reason.

A third concern is **observability**. Even if `import forgeqa` succeeds,
that alone does not prove it succeeded from the installed location —
`sys.path` resolution can be shadowed by a `src/` directory, a
`sitecustomize.py`, a parent venv, or a stale `.pth` file. The
verification must assert not just "import succeeds" but "import resolves
to the installed location, not the source tree".

Finally, a **classification gap** surfaced during 1.1.5: the
`Typing :: Typed` classifier has been in `pyproject.toml` since 1.1.1,
but the PEP 561 `py.typed` marker was never added. Without the marker,
downstream type checkers (mypy, pyright) ignore `forgeqa`'s inline
types and fall back to `Any`, silently degrading consumers' type
safety. The classifier without the marker is a broken promise. This
surfaced while writing the "does the package work as installed?"
contract, and belongs with this ADR because (a) the classifier and the
marker must agree, (b) the marker is a one-line change, and (c)
verifying it belongs with verifying the install.

## Decision

1. **Fresh venv under `/tmp` (via `mktemp -d`).** The developer's `.venv`
   is irrelevant — it has an editable install. A fresh venv has no
   editable install, no `.pth` pointing at `src/`, and no inherited
   `PYTHONPATH`. It can only succeed if the wheel is genuinely
   installable and usable.

2. **Fresh working directory under `/tmp` (via `mktemp -d`).** All
   Python invocations run with `cwd` set to the temp dir, so the repo
   root is not on `sys.path[0]`. This eliminates the "forgot to `cd`"
   class of false positives.

3. **Install from a wheel built in this script, not from `dist/`
   verbatim.** A stale `dist/` artifact could pass the verifier while
   the current source produces a broken wheel. The verifier builds into
   a fresh temp dir (`mktemp -d`), then installs from that. Same reason
   as `verify_build.sh` (ADR-004 Decision #2).

4. **Clear `PYTHONPATH` in every subprocess (`env -u PYTHONPATH ...`).**
   Even though a fresh venv should have no `PYTHONPATH` set, a
   developer's shell could be exporting it. Belt-and-braces against a
   whole class of false positives.

5. **Assert the import location, not just that import succeeds.**
   `forgeqa.__file__` must resolve under the venv's `site-packages`.
   This is the WBS acceptance criterion "package is importable without
   the repo being on PYTHONPATH", made concrete.

6. **Compare `forgeqa.__version__` against the wheel's `METADATA`.**
   A version mismatch means the installed package is not the wheel we
   built. This catches an editable-install leak that the import-path
   check might miss (e.g. a `.pth` file in a *parent* venv that puts
   `src/` on `sys.path`). The wheel's `METADATA` is the authoritative
   source; `forgeqa.__version__` (via `importlib.metadata.version`) must
   agree with it.

7. **Run `pytest` from the temp cwd against a real test file.** A bare
   `pytest` from the temp cwd collects nothing and passes trivially. The
   verifier writes a minimal `test_installed.py` with three real
   assertions (import, version non-empty, `forgeqa.__file__` under
   `site-packages` with no `src/` on `sys.path`) and runs it with
   `-p no:cacheprovider` to avoid writing `.pytest_cache` into the temp
   dir.

8. **`trap`-cleaned on `EXIT INT TERM`.** The venv, temp cwd, and wheel
   dir are removed unless `KEEP_INSTALL=1`. This satisfies the WBS
   acceptance criterion "The script cleans up the temporary environment
   after running", while leaving an escape hatch for debugging.

9. **`py.typed` marker added; classifier and marker pinned together.**
   The `Typing :: Typed` classifier (present since 1.1.1) promises
   downstream users that inline types are available. PEP 561 requires an
   empty `py.typed` marker in the package for that promise to be
   honoured. `src/forgeqa/py.typed` is created (empty), and
   `tests/unit/test_install_contract.py::test_py_typed_marker_present`
   + `::test_pyproject_declares_typed_classifier` enforce the two sides
   agree. `scripts/verify_build.sh` additionally asserts the marker is
   bundled into the wheel (so a future `exclude` change cannot drop it
   silently).

10. **Run in CI on Ubuntu + macOS, Python 3.11 + 3.12.** Platform
    differences in `pip`'s resolution and in `pathlib.Path.resolve()`
    (symlink handling differs between Linux and macOS — `/tmp` →
    `/private/tmp` on macOS) are caught by the matrix.

11. **Add `verify-install` to `make ci`.** Local CI catches the same
    regressions as remote CI.

## Alternatives Considered

| Alternative | Reason Rejected |
| :--- | :--- |
| Use the developer's `.venv` | The developer's `.venv` has `pip install -e .` applied; the editable install shadows the wheel. Any test of "does the wheel install?" in that venv is meaningless. |
| Install from `dist/` verbatim | A stale `dist/` artifact could pass the verifier while the current source produces a broken wheel. Build into a fresh temp dir first. |
| Run `python -c "import forgeqa"` from the repo root | The repo root is on `sys.path[0]`, and `src/` is one `cd` away. A forgotten `cd` would shadow the installed package. Use a temp cwd. |
| Assert only that `import forgeqa` succeeds | Import succeeds from a `src/` shadow too. The contract is "usable outside the source checkout", which requires asserting the import location, not just that it happened. |
| Assert `forgeqa.__version__` against a hard-coded string | Couples the test to a specific version. A version bump fails the test for the wrong reason, and an editable install with a slightly different version would pass. Compare against the wheel's `METADATA` instead. |
| Run bare `pytest` from the temp cwd | `pytest` collects nothing and passes trivially. A real test file is required to prove anything. |
| Use `tox` or `nox` | Adds a dependency on a test-runner framework whose own behaviour (env creation, plugin installation) introduces failure modes the verifier would have to distinguish from wheel failures. The verifier is ~200 lines of shell; adding a framework to test whether a wheel installs is over-engineering. |
| Use `pip install --target` instead of a venv | `--target` installs into a directory but does not isolate the interpreter; `sys.path` still points at the developer's environment. A venv is the standard, correct isolation mechanism. |
| Use `pip install --dry-run` | Reports what pip *would* install but does not verify that the resulting environment imports cleanly. WBS 1.1.3 rejected `--dry-run` for the same reason. |
| Run the verifier in the CI's existing `test` job | Adds ~20 s to the most-run job. A dedicated job parallelises and isolates the failure mode (a wheel-install failure is distinct from a unit-test failure). |
| Skip macOS in the CI matrix | Symlink handling in `Path.resolve()` differs between Linux and macOS. `forgeqa.__file__` under macOS may resolve symlinks (e.g. `/tmp` → `/private/tmp`), which could break the `site-packages` substring check if not tested. The matrix catches this. |
| Skip Python 3.11 (test only 3.12) | 3.11 is in the support window. `importlib.metadata` behaviour is stable across the two, but a resolution difference (e.g. dependency metadata) would go undetected without the matrix. |
| No `KEEP_INSTALL` escape hatch | Debugging a failing verifier without the venv intact is painful. The escape hatch costs ~5 lines and pays for itself the first time a failure occurs. |
| Check `forgeqa.__file__` via Python, not shell `case` | Both work; the shell `case` avoids a subprocess, but the Python approach is more readable and handles Windows path separators more naturally. The verifier is shell-first for portability with the other verifiers (`verify_build.sh`, `verify_deps.sh`), so `case` is consistent. A future Windows port should switch to the Python approach. |
| No `py.typed` marker | The `Typing :: Typed` classifier (present since 1.1.1) promises inline types. Without the marker, mypy/pyright fall back to `Any`, silently degrading consumers' type safety. The classifier-marker agreement is a contract; honour it. |
| Empty `py.typed` marker vs. `partial` marker | `partial` is for packages that ship a mix of inline types and stubs. `forgeqa` is inline-typed (mypy strict is on for `src/`); the correct marker is empty per PEP 561. `test_py_typed_marker_present` enforces `size == 0` so a future contributor cannot switch to `partial` without a deliberate decision. |
| Run `pip-audit` against the temp venv here | Phase 8 (Security) adds `pip-audit` in CI. Running it against the temp venv would duplicate what `pip-audit` does against the dependency tree; the two checks belong to different concerns (installability vs. vulnerability). Deferred to Phase 8. |

## Consequences

### Positive

- **The wheel is proven installable and usable in a clean environment.**
  A regression (metadata error, missing dependency, broken `__init__`)
  fails CI on the next push, with a clear diagnostic identifying the
  failed check.
- **The "works outside the source tree" contract is proven.** Import
  location is asserted, not just import success. An editable-install
  shadow in the developer's `.venv` cannot mask a wheel regression.
- **Contributors can check before pushing.** `make verify-install` is
  ~20 s locally, and `make ci` includes it.
- **`py.typed` marker is shipped.** Downstream users' type checkers
  consume inline types, matching the `Typing :: Typed` classifier's
  promise. The classifier-marker agreement is now enforced by two tests
  and one wheel-content assertion.
- **CI matrix catches platform differences.** Symlink resolution
  (macOS `/tmp` → `/private/tmp`) and pip resolution differences are
  caught by running on Ubuntu + macOS × 3.11 + 3.12.
- **Temporary environment is cleaned up.** `trap`-based cleanup runs on
  `EXIT INT TERM`, satisfying the WBS acceptance criterion.

### Negative

- **~20 s per verifier run.** Builds a wheel (~5 s) plus venv creation
  (~5 s) plus pip install (~5 s) plus pytest (~3 s). Acceptable locally
  and in CI.
- **CI matrix is 4 jobs (2 OS × 2 Python).** Adds ~4 × 1 min of
  wall-clock CI time, mostly parallel.
- **The verifier builds its own wheel.** If `make build` has already
  run, this is redundant (the wheel is cached in `dist/`). The verifier
  still builds into a temp dir to ensure it inspects a fresh artifact,
  not a stale one.
- **`py.typed` is an empty file.** It has no behaviour by itself; its
  presence is the contract. A future contributor might be tempted to
  "clean up" an empty file — the `test_py_typed_marker_present` test
  and this ADR are the record of why it is there.
- **The `test_installed.py` sanity check depends on `site-packages`
  being in `forgeqa.__file__`.** A future non-standard install (e.g.
  `pip install --target`) would fail this check for reasons unrelated
  to the wheel. Not a concern for `pip install <wheel>` into a venv,
  but worth noting.
- **macOS symlink resolution.** `Path.resolve()` on macOS resolves
  `/tmp` to `/private/tmp`. The verifier uses string `case` matching on
  the import path and the `sysconfig` site-packages path; both are
  resolved the same way by `sysconfig`, so this should be consistent.
  The CI matrix verifies it; if a future macOS version changes the
  symlink handling, the matrix catches it.

### Neutral

- `Makefile` gains one target (`verify-install`) and one addition to
  `ci`.
- `.github/workflows/quality.yml` gains one job.
- `README.md` gains one row in the Development Commands table and one
  sentence in the Install section.
- `docs/engineering-standards.md` gains §4.13 and one item in §7.2;
  §1.6's superseded note is extended to point at both §4.12 and §4.13.
- `src/forgeqa/py.typed` is added (empty file). This is a
  packaging-metadata change that does not affect runtime behaviour.
- `tests/unit/test_install_contract.py` is a new file in the fast test
  suite; `scripts/verify_install.sh` is a new file in the
  build-tooling directory. Neither changes runtime behaviour.
- `scripts/verify_build.sh`'s `WHEEL_REQUIRED` array gains
  `forgeqa/py\.typed` as a required entry, so the marker's presence in
  the wheel is enforced end-to-end as well as config-level.
- The verifier is shell-based (consistent with `verify_build.sh`,
  `verify_deps.sh`), not Python-based. A future cross-platform port
  might switch to Python for `Path` handling.

## Reconsideration Trigger

Revisit this decision if any of the following occurs:

- **The verifier runtime exceeds ~1 min.** If venv creation or pip
  install becomes slow (e.g. a future dependency tree grows), split the
  wheel build from the install check, or parallelise across the CI
  matrix. Current runtime is ~20 s.
- **The package gains a CLI entry point.** A future `forgeqa` CLI
  (Phase 2) would need its entry point verified:
  `forgeqa --version` from the temp cwd. Add to `verify_install.sh` as
  a new check, and to `test_install_contract.py` as an entry-point
  assertion.
- **A new top-level package is added.** E.g. `forgeqa_cli/` in Phase 2.
  Add its import path to the verifier's checks, and its `py.typed`
  presence to `test_install_contract.py`.
- **`forgeqa.__init__` stops exposing `__version__`.** If ADR-002's
  contract changes (e.g. version becomes a lazy `__getattr__`), update
  the version-comparison check to use `importlib.metadata.version`
  directly.
- **`pip install -e .` becomes unnecessary for development.** E.g. if
  the project switches to a layout where editable installs are not
  used, the developer's `.venv` would no longer have `src/` on
  `sys.path`, and the "fresh venv" requirement would weaken. The
  decision would still hold for CI's fresh-venv environment; it would
  just be a smaller delta locally.
- **Windows is added to the CI matrix.** The verifier uses `mktemp -d`
  and string `case` matching on paths. Windows path separators (`\` vs
  `/`) and `mktemp -d` semantics (`$TEMP` vs `/tmp`) differ. Port to
  Python (using `pathlib.Path.is_relative_to`) before adding Windows.
- **A non-`pip` installer is adopted for consumers.** E.g. `uv pip
  install`, `pipx`, `conda`. The verifier proves `pip install <wheel>`
  works; if consumers use a different installer, add a scenario for it.
  Not applicable today.
- **The `site-packages` location check produces a false positive.**
  E.g. if a future dependency of `forgeqa` installs a `forgeqa` package
  into a *different* `site-packages` (should not happen, but...). The
  version-comparison check would catch it; revisit if it does.
- **The `test_installed.py` sanity check needs extension.** If Phase 1
  adds fixtures (`forgeqa.fixtures`) or settings (`forgeqa.settings`)
  that are importable only with extras, extend `test_installed.py` to
  assert those are importable in the appropriate venv. A future
  `verify_install.sh --extras ui` invocation would install `[ui]` and
  assert `playwright` is importable — overlapping with
  `verify_deps.sh`, and coordinated if added.
- **`py.typed` marker becomes partial.** If the project ever ships
  partial stubs (`py.typed` with `partial` content), update
  `test_py_typed_marker_present` accordingly. Unlikely for an
  inline-typed project, but worth knowing.
- **PEP 561 is superseded or extended.** If the type-information
  packaging spec changes (e.g. a new marker or a new content
  convention), revisit the `py.typed` presence and emptiness checks.

## Related

- WBS 1.1.5 — Verify Clean Installation from Built Artifact (this
  decision)
- WBS 1.1.4 — Build Verification & Wheel Content Inspection (established
  the wheel/sdist content contract that this ADR's install check
  complements)
- WBS 1.1.3 — Configure & Verify Dependency Groups (established the
  fresh-venv pattern for isolation)
- WBS 1.1.2 — Implement the Minimum Importable Package & Public API
  (established the `__version__` / `get_version` contract that this
  ADR's version check relies on)
- WBS 1.1.1 — Finalise Package Metadata & License (established the
  `Typing :: Typed` classifier that the `py.typed` marker makes honest)
- Phase 0.5.2 — Build verification (predecessor; verified the package
  installs but not from a fresh venv and not outside the source tree)
- ADR-001 — Adopt MIT license file and PEP 621-compliant package metadata
- ADR-002 — Resolve package version at import time via `importlib.metadata`
- ADR-003 — Verify optional dependency groups via an isolated-venv script
- ADR-004 — Verify built artifacts contain exactly the intended files
- `scripts/verify_install.sh` — the end-to-end verifier
- `tests/unit/test_install_contract.py` — the config-level complement
- `docs/engineering-standards.md` §4.13 "Clean-Install Verification" —
  contributor-facing rules
- `docs/public-api.md` §"Guarantees" — the import-time behaviour this
  section verifies from a clean environment
- `src/forgeqa/py.typed` — the PEP 561 marker
- `pyproject.toml` `classifiers` — the `Typing :: Typed` classifier
- PEP 517 — A build-system independent format for source trees:
  https://peps.python.org/pep-0517/
- PEP 561 — Distributing and Packaging Type Information (the `py.typed`
  marker): https://peps.python.org/pep-0561/
- PEP 660 — Editable installs for pyproject.toml-based builds (why the
  developer's `.venv` has `src/` on `sys.path`):
  https://peps.python.org/pep-0660/
- `importlib.metadata` documentation:
  https://docs.python.org/3/library/importlib.metadata.html
- Python `venv` documentation:
  https://docs.python.org/3/library/venv.html
- Python `sysconfig` documentation (`purelib` path):
  https://docs.python.org/3/library/sysconfig.html
