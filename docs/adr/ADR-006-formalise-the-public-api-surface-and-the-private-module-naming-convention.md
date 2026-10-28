# ADR-006: Formalise the public API surface and the private-module naming convention

> **Status**: Accepted
> **Date**: 2026-10-28
> **Deciders**: Solo Developer
> **Consulted**: None
> **Informed**: None

## Context

WBS 1.1.6 requires `docs/public-api.md` to list every supported import,
to state explicitly that `_`-prefixed modules are private, and to back
the documentation with a test (`tests/unit/test_public_api.py`) that
fails if a new private module is accidentally exported. The traceability
KPI is "The public API is clearly separated from internal
implementation."

ADR-002 (version resolution) and ADR-005 (clean install) already
established partial contracts: `__version__` and `get_version` are
public; import is cheap and side-effect-free; the wheel is installable
outside the source tree. But four questions were not settled:

1. **What, precisely, is the full public surface?** `forgeqa.__all__`
   is the machine-readable answer, but there was no document stating
   the human-readable contract, no test asserting the two agree, and no
   convention for what to do when the two disagree.
2. **What is the private-module convention, and how is it enforced?**
   PEP 8 says `_`-prefixed module names are internal. ForgeQA has
   `_is_version_fallback`, `_resolve_version`, and will grow more
   private helpers. Nothing stopped a future contributor from adding
   `_internal` to `__all__`, importing a private submodule from
   `__init__.py`, or shipping a `_`-prefixed package in the wheel.
3. **What does the semver promise mean?** "Add a name = minor, remove
   a name = major" is standard, but the project has no document stating
   it, so a future contributor has no reference for whether their change
   is allowed.
4. **How do the doc and the code stay in sync?** If the doc and
   `forgeqa.__all__` can drift, one of them is a lie. Only a test can
   keep them honest.

The forces at play:

- **Consistency.** `docs/engineering-standards.md` has §4.11 (dependency
  groups), §4.12 (artifact content), §4.13 (clean install). The
  public-API contract is the natural §4.14 and belongs in the same
  document set, following the same "rules → two-layer verification →
  see also" pattern.
- **Enforcement over documentation.** A docstring saying "private" is
  ignored the moment someone is in a hurry. A test that fails CI is not.
  The contract must be enforced by a test, not just declared. The WBS
  explicitly requires a test, not just a doc.
- **No premature commitment.** Phase 1 will add `forgeqa.fixtures`,
  `forgeqa.settings`, etc. The contract must be extensible without
  rewriting it when they land. The `PUBLIC_SUBMODULES` set and the
  "add to three places in the same PR" rule provide the extension
  mechanism.
- **Test-authoritative expected values.** If the test imports the
  expected value from `forgeqa.__all__`, it is a tautology — any change
  to `forgeqa.__all__` would pass. The expected value must live in the
  test file so a change to `forgeqa.__all__` without a change to the
  test fails.

## Decision

1. **`docs/public-api.md` is the human-readable contract.** It lists:
   - The entire public surface (currently `__version__` and
     `get_version`), as a table with kind, "since" version, and
     description.
   - The import-time guarantees from ADR-002.
   - What is *not* public, explicitly including "any name starting with
     a single underscore" and "any module under a `_`-prefixed
     subpackage", with a rationale subsection ("Why the `_`-prefix
     rule").
   - The import-time guarantees table and the enforcement table.
   - A stability promise table mapping change types to semver impact.
   - A "How this contract is enforced" section listing the four tools
     that back the claim.
   - A "reporting issues" section for when a guarantee is violated.

2. **`tests/unit/test_public_api.py` is the executable contract.**
   It asserts:
   - `forgeqa.__all__ == EXPECTED_ALL`, where `EXPECTED_ALL` is
     defined **in the test file**, not imported from `forgeqa`. This
     makes the test *not* a tautology: a change to `forgeqa.__all__`
     without a change to `EXPECTED_ALL` (and to `docs/public-api.md`)
     fails CI.
   - `forgeqa.__all__` is a `tuple` (immutable), not a `list`.
   - Every documented name is actually accessible on the module.
   - `get_version() == __version__`.
   - No `_`-prefixed name is in `__all__` (except documented dunders).
     This is enforced on four axes: parametrised membership
     (`test_private_name_not_in_all`), structural
     (`test_no_underscore_name_in_all`), source
     (`test_no_private_module_in_source_tree_top_level`), and runtime
     (`test_no_private_submodule_imported_by_top_level`).
   - `docs/public-api.md` exists and states the `_`-prefix rule
     (`test_public_api_doc_exists_and_mentions_underscore_rule`).

3. **`EXPECTED_ALL` is shared across the test suite.** A small edit to
   `tests/unit/test_install_contract.py` imports it from
   `test_public_api.py`, so the two tests cannot drift. The constant
   is the single source of truth for "what is the expected public
   surface", and a change to it (with `forgeqa.__all__` and
   `docs/public-api.md`) is the deliberate three-place edit the
   contract requires.

4. **`_`-prefixed modules are private, by rule and by test.** They may
   exist as implementation organization; they must not be imported by
   `__init__.py` and must not be in `__all__`. To re-export a name from
   a private module, use a public alias:

   ```python
   from forgeqa._internal import _helper as public_name  # OK

   __all__ = (..., "public_name")
   ```

   The private module *is* imported in this case (necessarily — the
   name has to come from somewhere), but the exported name is public
   and the private module's contents are not re-exported wholesale.

5. **Public submodules are top-level, each with their own `__all__`.**
   When Phase 1 adds `forgeqa.fixtures` and `forgeqa.settings`, they
   are:
   - top-level modules (not `_`-prefixed)
   - each with their own `__all__`
   - added to `PUBLIC_SUBMODULES` in `test_public_api.py`
     (`test_public_submodules_if_any` then asserts each has an
     `__all__` tuple; currently a no-op since the set is empty)
   - documented in `docs/public-api.md` §"Optional functionality"
   - added to `forgeqa.__all__` if the submodule itself (not just its
     names) is meant to be re-exported

   Adding a public submodule is semver-minor.

6. **Dunder names are public only when documented.** `__version__` is
   public because it is in `EXPECTED_ALL` and in `docs/public-api.md`.
   `__author__`, `__license__`, and other dunders are diagnostics.
   `test_no_underscore_name_in_all` allows only dunders in
   `EXPECTED_ALL` and rejects every other `_`-prefixed name.

7. **PEP 562 `__getattr__` requires an ADR before adoption.** Lazy
   re-exports (`from forgeqa import Settings` without importing
   pydantic) introduce subtle behaviours (`hasattr` returns `True` for
   lazily-computed names, tracebacks point at `__getattr__` rather
   than the real module, and the test suite would need to assert the
   lazy behaviour explicitly). If a future API needs it, write an ADR
   first. ADR-002's reconsideration trigger already lists this as a
   future decision.

8. **The source module restates the contract.** `src/forgeqa/__init__.py`
   gains a docstring paragraph that points at `docs/public-api.md`,
   restates the `_`-prefix rule, and names the test that enforces it.
   A contributor reading the source before touching `__all__` sees the
   full contract (three-place edit: code + doc + `EXPECTED_ALL`)
   without opening the ADR. No code change — docstring only.

9. **`make verify-public-api` runs the contract test in isolation.**
   ~50 ms locally; useful for pre-commit and for a quick check before
   pushing. The full `make ci` includes it too.

10. **`scripts/verify_build.sh` excludes `_`-prefixed top-level
    modules from the wheel.** Defense in depth: a future change to
    `[tool.hatch.build.targets.wheel].packages` could add a
    `_`-prefixed package without the config-level test catching it
    (the config test scans the source tree, not the built archive).
    This is the same "config + end-to-end" pattern used by §4.11–§4.13.

## Alternatives Considered

| Alternative | Reason Rejected |
| :--- | :--- |
| Document `__all__` in `docs/public-api.md` only, no test | Documentation drifts. Without a test, `__all__` and the doc will disagree within a month. The WBS explicitly requires a test. |
| Test imports `EXPECTED_ALL` from `forgeqa.__all__` | Tautology. Any change to `forgeqa.__all__` passes the test. The expected value must be defined in the test file so a change must be made deliberately. |
| `EXPECTED_ALL` defined in `pyproject.toml` and read by both the doc and the test | Adds a build-config dependency for a test constant. The test file is the right place; `pyproject.toml` is for packaging metadata. |
| Ship `_`-prefixed modules in the wheel | The private module would be installed and importable, making it a de-facto part of the surface even if not in `__all__`. The build verifier should exclude `_`-prefixed top-level modules. |
| Allow `_`-prefixed names in `__all__` if documented | Defeats the convention. If a name is public, rename it without the underscore. The underscore convention is the only signal a consumer has. |
| Use `__getattr__` to lazily re-export private names | PEP 562 `__getattr__` has subtle behaviours (see Decision #7 and ADR-002's reconsideration trigger). Not needed for 1.1.6; requires an ADR if a future API wants it. |
| Only test at the wheel level, not the source level | The wheel test is slow (~10 s) and cannot see source-tree regressions like "`__init__.py` imports `_internal`". The source-level test is fast (~50 ms) and catches the same class before the build. Both layers are required. |
| Only test at the source level, not the wheel level | A future `packages` change could add a `_`-prefixed package to the wheel without the source test catching it (the source test scans `src/forgeqa/`, not the wheel contents). Both layers are required. |
| Use `pytest.importorskip` for public submodules | The submodules do not exist yet. `PUBLIC_SUBMODULES` is empty and will be populated in Phase 1; the tests for submodule `__all__` will run then. |
| Document public names only in `docs/public-api.md` and remove `forgeqa.__all__` | `__all__` is used by `from forgeqa import *`, by `pydoc`, by IDE completions, and by `scripts/verify_build.sh`. It is the machine-readable form of the contract; the doc is the human-readable form. Both are needed. |
| Make `forgeqa.__all__` a `list` | A list is mutable at runtime (`forgeqa.__all__.append("bogus")`). A tuple is immutable and communicates intent. Enforced by `test_all_is_immutable_tuple`. |
| One giant `test_public_api.py` covering everything | The file is already ~250 lines with 13 test functions. Splitting it further (e.g. `test_public_api_negative.py`) would fragment the contract and make it harder to see the whole picture. The current file is scannable top-to-bottom. |
| Enforce `_`-prefix rule by linting (custom ruff rule) | Custom rules require maintenance and are not portable. A test is portable, visible in CI, and runs on every PR. The test *is* the enforcement. |
| Ship `tests/unit/test_public_api.py` as a `pytest` plugin for consumers | The contract is for ForgeQA's own API, not for consumer packages. A plugin would be over-engineering; consumers have their own contracts. |
| Put `EXPECTED_ALL` in a shared `tests/unit/_api_contract.py` file | Fewer files with the cross-import; the `_api_contract.py` approach is more conventional but adds a file with one constant. Either works; the cross-import (`from tests.unit.test_public_api import EXPECTED_ALL` in `test_install_contract.py`) keeps the constant next to the test that owns it. |
| Make `docs/public-api.md` a generated file (from `__all__` or vice versa) | Generation removes the friction that makes the contract meaningful. A manually-edited doc forces the contributor to think about semver impact when adding a name. Generation could be added later if the surface grows past ~20 names (see Reconsideration Trigger). |

## Consequences

### Positive

- **The public surface is documented, tested, and enforced.** A future
  change to `forgeqa.__all__` without updating `docs/public-api.md` and
  `EXPECTED_ALL` fails CI.
- **The `_`-prefix rule is stated and enforced on four axes:**
  - `docs/public-api.md` states it, with a rationale subsection.
  - `test_public_api.py` asserts it (membership, structure, source,
    runtime).
  - `scripts/verify_build.sh` excludes `_`-prefixed top-level modules
    from the wheel (future-proofing).
- **`EXPECTED_ALL` is test-authoritative.** A deliberate change to the
  public surface requires a coordinated three-place edit; a partial
  change fails CI. This is the friction that makes a contract
  meaningful.
- **`make verify-public-api` gives a fast local check** (~50 ms) that
  can run pre-commit or before pushing.
- **The contract is extensible.** `PUBLIC_SUBMODULES` and the
  "add to three places in the same PR" rule scale to Phase 1's
  `forgeqa.fixtures` and `forgeqa.settings`.
- **Consistency with the other sections.** `docs/engineering-standards.md`
  §4.11–§4.14 all follow the same pattern: rules, two-layer
  verification, running instructions, "See also". A contributor reading
  one section knows how to read the others.
- **The version accessor decision (ADR-002) is now backed by a
  written stability promise.** A future contributor can point at
  `docs/public-api.md` §Stability promise when deciding whether a
  change is semver-minor or semver-major.
- **`test_install_contract.py` shares `EXPECTED_ALL`** with
  `test_public_api.py`, so the two tests cannot drift. A single edit to
  `EXPECTED_ALL` updates both.
- **`src/forgeqa/__init__.py` restates the contract.** A contributor
  who opens the source file before editing `__all__` sees the rule and
  the three-place edit requirement, without needing to open the ADR.

### Negative

- **`tests/unit/test_public_api.py` and `tests/unit/test_install_contract.py`
  share a constant via cross-module import.** Cross-test imports are
  unusual; the alternative is a shared `_api_contract.py` file with one
  constant. Both work; the cross-import is fewer files, the
  `_api_contract.py` is more conventional. Chosen: cross-import, with
  a `# noqa: PLC0415` comment explaining it.
- **`EXPECTED_ALL` must be updated three times per public name.** The
  friction is the point. A future contributor adding a name must:
  - `src/forgeqa/__init__.py` (`__all__`)
  - `docs/public-api.md` (the table and the stability table)
  - `tests/unit/test_public_api.py` (`EXPECTED_ALL`)

  A tool could automate this (e.g. generate `EXPECTED_ALL` from the
  doc), but that adds tooling for a rare event. The manual update is
  ~30 seconds and is the check.
- **The `_`-prefix check on `src/forgeqa/` scans `PKG_DIR.iterdir()`**
  and matches against the source of `__init__.py` with string patterns.
  A future rename of `__init__.py` or of the package directory would
  break the test. Mitigated by the test failing loudly with a clear
  message; the fix is a one-line update to the pattern.
- **The doc mentions the `_`-prefix rule in prose.** A future change
  to the wording of the rule (e.g. "internal" vs "private") could
  make `test_public_api_doc_exists_and_mentions_underscore_rule` fail
  for a cosmetic reason. The test asserts the *concept* is present
  (`"underscore"` or `"_ prefixed"`; `"private"` or `"not public"`),
  not the exact wording. This is loose enough to survive wording
  changes and strict enough to catch a wholesale removal.
- **`PUBLIC_SUBMODULES` is empty today.** The corresponding test
  (`test_public_submodules_if_any`) is a no-op (skipped). This is
  intentional for the pre-alpha surface but means the test suite
  reports "1 skipped", which some readers interpret as "something is
  wrong". The skip reason is explicit ("No public submodules declared
  yet (pre-alpha)"); a future contributor adding a public submodule
  activates the test automatically.

### Neutral

- `docs/public-api.md` grows from ~200 lines (1.1.2 version) to ~400
  lines (1.1.6). The additions are the full public surface table, the
  stability promise table, the "how this is enforced" section, and the
  "why the `_`-prefix rule" rationale subsection.
- `docs/engineering-standards.md` gains §4.14 and one item in §7.2;
  §4.13's verification list is updated to reference `EXPECTED_ALL`.
- `README.md` gains `docs/public-api.md` in the Documentation table.
  (It was added as a file in 1.1.2 but never linked from the README;
  this PR fixes that oversight.)
- `Makefile` gains one target (`verify-public-api`).
- `src/forgeqa/__init__.py` gains a docstring paragraph. No code
  change.
- `tests/unit/test_install_contract.py` gains a cross-module import
  of `EXPECTED_ALL`. The test's behaviour is unchanged.
- `tests/unit/test_public_api.py` is a new file (~250 lines, 13 test
  functions, 17 collected items with parametrisation).
- `scripts/verify_build.sh` adds `_`-prefixed module exclusion. This
  is a defensive check, not a functional change: no `_`-prefixed
  top-level module currently exists, so the check passes trivially
  today. It exists to prevent a future regression.

## Reconsideration Trigger

Revisit this decision if any of the following occurs:

- **A public submodule lands** (Phase 1: `forgeqa.fixtures`,
  `forgeqa.settings`). Populate `PUBLIC_SUBMODULES`, add the submodule
  to `docs/public-api.md` §"Optional functionality", add its
  `__all__` to the test suite. The ADR's pattern extends; the specific
  list is data.
- **`forgeqa.__all__` grows past ~10 names.** The single `EXPECTED_ALL`
  tuple becomes unwieldy; consider splitting into
  `EXPECTED_ALL_TOP_LEVEL` and per-submodule `EXPECTED_ALL_<submodule>`.
  Not needed for the current size (2 names).
- **`_`-prefix rule produces a false positive.** E.g. a future file
  legitimately named `_version.py` for build-time metadata. Refine the
  source-check pattern in `test_public_api.py` to exclude known-safe
  names, documenting the exemption.
- **A consumer needs `_is_version_fallback`.** If a real consumer
  needs the fallback state (currently a private helper in
  `forgeqa/__init__.py`), promote it to `is_version_fallback()` and
  add it to `__all__`, `EXPECTED_ALL`, and `docs/public-api.md`.
  Semver-minor. This is the same reconsideration trigger as ADR-002.
- **PEP 562 `__getattr__` is added.** If a future API wants
  `from forgeqa import Settings` to work without importing pydantic
  eagerly, an ADR is required first (Decision #7). Update
  `test_public_api.py` to assert the lazy name is in `__all__` and
  resolvable via `getattr`.
- **`forgeqa.__all__` becomes a list.** The test
  `test_all_is_immutable_tuple` catches this; if the change is
  intentional (unlikely), update the test and document the rationale.
- **`docs/public-api.md` becomes very long.** If it grows past ~600
  lines, consider splitting into `docs/public-api/index.md` and
  per-submodule docs. Not needed for the current size (~400 lines).
- **A public name is removed.** The stability promise says this is a
  semver-major change. The `test_all_matches_documented_surface` test
  fails until `EXPECTED_ALL` and the doc are updated; that is the
  intended friction. A removal at 1.0+ requires a deprecation cycle
  (see `docs/public-api.md` §Stability promise).
- **`tests/unit/test_install_contract.py` imports from a different
  test module cause pytest collection issues.** Cross-module imports
  in test files can cause duplicate collection if the module is
  collected twice (e.g. via `testpaths` and via direct path). If this
  becomes a problem, move `EXPECTED_ALL` to a shared
  `tests/unit/_api_contract.py` file.
- **The `EXPECTED_ALL` pattern is extended to submodules.** When the
  first public submodule lands, the pattern for its `__all__` should
  be the same: expected value in the test file, not imported from the
  submodule. Extend the pattern; do not weaken it for submodules.
- **A generated `EXPECTED_ALL` becomes attractive.** If the public
  surface grows past ~20 names, hand-maintaining the constant becomes
  error-prone. Consider generating it from the doc (and CI asserting
  the doc matches `forgeqa.__all__`). Not needed for 2 names.

## Related

- WBS 1.1.6 — Document Public vs. Internal Import Rules (this decision)
- WBS 1.1.2 — Implement the Minimum Importable Package & Public API
  (established the initial `__all__` and the import-isolation
  guarantees)
- WBS 0.4.4 — Public API Contract (the original requirement for a
  documented public API)
- ADR-002 — Resolve package version at import time via `importlib.metadata`
  and keep top-level imports dependency-free (established the
  version-resolution contract and the import-isolation invariant)
- ADR-005 — Verify installed wheel works outside the source checkout
  (established the clean-install contract; the
  `test_install_contract.py` tests overlap slightly and share
  `EXPECTED_ALL` with this ADR's tests)
- `docs/public-api.md` — the consumer-facing contract
- `tests/unit/test_public_api.py` — the executable contract
- `tests/unit/test_install_contract.py` — shares `EXPECTED_ALL`
- `docs/engineering-standards.md` §4.14 "Public vs. Internal Module
  Conventions" — contributor-facing rules
- `src/forgeqa/__init__.py` — the module whose docstring points at
  this contract
- `scripts/verify_build.sh` — asserts no `_`-prefixed top-level
  module is shipped in the wheel
- PEP 8 — Style Guide for Python Code (`_name` is internal):
  https://peps.python.org/pep-0008/#descriptive-naming-styles
- PEP 562 — Module `__getattr__` and `__dir__` (future lazy
  re-exports; requires an ADR if adopted):
  https://peps.python.org/pep-0562/
- `docs/public-api.md` §"Stability promise" — the semver table this
  ADR references
