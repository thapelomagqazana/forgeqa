# ADR-002: Resolve package version at import time via importlib.metadata and keep top-level imports dependency-free

> **Status**: Accepted
> **Date**: 2026-10-28
> **Deciders**: Solo Developer
> **Consulted**: None
> **Informed**: None

## Context

WBS 1.1.2 requires that `import forgeqa` be cheap and side-effect free —
specifically that importing the package does **not** import Playwright or HTTPX
(the two optional UI/API dependencies), and that `forgeqa.__version__` be
queryable. The WBS 1.1.1 baseline shipped a hard-coded
`__version__ = "0.1.0"` literal in `src/forgeqa/__init__.py`.

Two implementation choices dominate this work item:

1. **How to source the version.**
   A hard-coded literal is the simplest option and is what 1.1.1 shipped. But
   it duplicates the value already declared in `pyproject.toml`
   (`[project].version`). Every release then needs **two** edits, and forgetting
   one produces a wheel whose `METADATA` `Version:` field disagrees with
   `forgeqa.__version__`. That is a silent, hard-to-detect bug class: nothing
   in the test suite fails, `pip show` and runtime introspection simply
   disagree. Eliminating the duplicated source of truth removes the bug class
   entirely.

2. **How to keep optional dependencies out of the top-level import.**
   Playwright and HTTPX are optional (`forgeqa[ui]`, `forgeqa[api]`). If
   `src/forgeqa/__init__.py` imports anything that reaches them — directly or
   transitively — then installing `forgeqa` core (without those extras) makes
   `import forgeqa` fail with `ModuleNotFoundError`. That breaks CLI tools, doc
   builders, type-checkers, package managers, and any tool that imports a
   package to introspect it. The WBS 1.1.2 acceptance criteria make this
   explicit: `assert 'playwright' not in sys.modules` and
   `assert 'httpx' not in sys.modules` after a bare `import forgeqa`.

A third concern is **observability** of the version-resolution fallback. When
the package is imported from a source checkout that has not been installed
(no `.dist-info` on `sys.path`), `importlib.metadata.version("forgeqa")` raises
`PackageNotFoundError`. The implementation must not crash in this case (it
would break `python -m pytest` in development and any local `python -c`
experiment), and the fallback must be **testable** without every test needing
to monkeypatch `importlib.metadata`.

Additional forces at play:

- **Contract clarity (WBS 0.4.4).** The public API surface must be explicit and
  stable. Consumers should not depend on module-private names, and the module
  should be able to evolve internals (e.g. from a hard-coded version to
  metadata-resolved) without breaking the contract.
- **No import-time warnings.** Warnings fired during import are reliably
  swallowed by test runners and reliably noisy in CI; they fire once per
  interpreter and are not actionable by end users. The decision must avoid
  them entirely.
- **Forward-compatibility.** Future public names (e.g. a `Settings` type from
  `pydantic`) must not force a top-level `pydantic` import. The mechanism
  chosen now must not preclude lazy re-exports later.

## Decision

1. **`__version__` is resolved from installed metadata.**
   Use `importlib.metadata.version("forgeqa")` at module import time. This is
   the same mechanism `pip show` uses, so the value is guaranteed consistent
   with the installed artifact. `pyproject.toml`'s `[project].version` remains
   the single source of truth; the module reflects it. No duplicated literal in
   source.

2. **The fallback is explicit, obviously-wrong, and observable.**
   When metadata is unavailable (`PackageNotFoundError`), `__version__` becomes
   `"0.0.0+unknown"`. The value parses under
   `packaging.version.Version` (as a post-release of `0.0.0`) so tools that
   parse it still succeed, and it sorts below any real release. A private
   `_is_version_fallback() -> bool` helper exposes the fallback state to tests
   without leaking into the public API.

3. **No import-time warnings.**
   Do **not** call `warnings.warn(...)` when metadata is missing. Instead, the
   fallback is documented in `docs/public-api.md` and observable via the
   private helper. Only `PackageNotFoundError` is caught; any other exception
   (e.g. a corrupt `METADATA`) propagates, because a corrupt install is a real
   problem that should surface.

4. **The top-level module imports nothing heavy.**
   `import forgeqa` imports only the standard library
   (`importlib.metadata`, `typing`). Playwright, HTTPX, and any future optional
   dependency are imported from their submodules (e.g.
   `forgeqa.fixtures`, `forgeqa.api`), never from `forgeqa/__init__.py`.
   Enforcement is via `tests/unit/test_import.py`, which runs in a fresh
   subprocess.

5. **`__all__` is an immutable tuple.**
   `__all__ = ("__version__", "get_version")`. A mutable `list` would let a
   consumer widen the public contract at runtime by accident; a `tuple` makes
   that impossible. Adding a name to `__all__` is a semver-minor event and
   requires a documentation update in `docs/public-api.md`.

6. **`get_version()` is the recommended accessor.**
   It returns the same value as `__version__` but insulates consumers from a
   future refactor in which the version may become lazily evaluated.

7. **`__author__` and `__license__` remain on the module but leave `__all__`.**
   They are diagnostic metadata echoes, not API. Consumers who legitimately
   need attribution read `importlib.metadata.metadata("forgeqa")`.

## Alternatives Considered

| Alternative | Reason Rejected |
| :--- | :--- |
| Hard-code `__version__ = "0.1.0"` (as WBS 1.1.1 shipped) | Duplicates the value in `pyproject.toml`; drift between the two is a real, silent bug class. `pip show` and runtime introspection can disagree with nothing failing in tests. |
| Use `setuptools_scm` / dynamic version from git tags | Adds a build-time dependency and makes version resolution depend on git metadata being present. Fails for sdists (which contain no `.git`), complicates reproducible builds, and is overkill for a pre-alpha package. |
| Use `hatch-vcs` / hatchling's `dynamic = ["version"]` | Same downsides as `setuptools_scm`, plus couples us to hatchling-specific tooling. `importlib.metadata` is build-backend-agnostic. |
| `warnings.warn(...)` on `PackageNotFoundError` | Import-time warnings are reliably ignored by users and reliably noisy in CI. "Warn once per interpreter" semantics mean CI may or may not surface them. Not actionable by end users, who cannot fix missing metadata. |
| Raise `RuntimeError` when metadata is missing | Makes `import forgeqa` fail from a source checkout. Breaks `python -m pytest` in development, local REPL experiments, and doc builders that import packages without installing them. The fallback is strictly safer. |
| Make `__version__` a lazily-evaluated property via module-level `__getattr__` | Over-engineering for a value that costs one `importlib.metadata.version` call (~2–5 ms). Also makes `hasattr(forgeqa, "__version__")` return `True` for a value that hasn't been computed yet, which is a subtle footgun. |
| Import `pydantic` (a core dependency) at the top level "for convenience" | Adds ~30 ms to import time and starts pydantic's schema machinery. Not needed for the minimum API; a future `forgeqa.settings` module can import it when the caller actually needs it. |
| Re-export `Settings` (or any future public name) eagerly | Would pull `pydantic` in at import time, defeating the isolation goal of this ADR. When the first such name lands, use PEP 562 `__getattr__` for lazy re-export. |
| Use a plain `list` for `__all__` | Mutable; consumers can widen the contract at runtime (`forgeqa.__all__.append("bogus")`). A `tuple` makes the contract immutable and communicates that intent via type. |
| Drop `get_version()` and expose only `__version__` | The module attribute is easy to shadow or reassign accidentally (e.g. by a consumer's monkeypatch). `get_version()` gives a stable accessor that survives refactors, such as a future lazily-evaluated version. |
| Test import isolation via `sys.modules` snapshot in the same pytest process | pytest plugins, coverage instrumentation, and prior tests pollute `sys.modules`. Only a fresh subprocess reflects what a consumer will actually see. |
| Pin the version at build time via a generated `_version.py` file | Adds a build step and a generated file to the source tree; the value still has to come from somewhere authoritative, so this just relocates the duplication rather than eliminating it. `importlib.metadata` reads the installed value directly. |

## Consequences

### Positive

- **Single source of truth for the version.** `pyproject.toml` is authoritative;
  `forgeqa.__version__` reflects it. Impossible to ship a wheel whose runtime
  version disagrees with its `METADATA`.
- **`import forgeqa` is cheap.** ~5–10 ms on a warm interpreter, dominated by
  `importlib.metadata.version`. No Playwright, HTTPX, or pydantic imported at
  the top level.
- **Installable without optional dependencies.** `pip install forgeqa`
  (core only) leaves `import forgeqa` fully working. `forgeqa[ui]` and
  `forgeqa[api]` remain strictly additive.
- **Testable fallback.** `_is_version_fallback()` lets tests assert the
  fallback path *and* the installed path without monkeypatching
  `importlib.metadata`.
- **Deterministic.** Two imports of the same installation always yield the
  same version string.
- **No warnings.** `import forgeqa` never emits a warning; under
  `warnings.simplefilter("error")` it still succeeds, and CI can assert this.
- **Contract is explicit and stable.** `__all__` is a tuple and is the single
  source of truth for the public surface, consumed by `docs/public-api.md`
  and by `pydoc`.

### Negative

- **`importlib.metadata` costs ~2–5 ms.** Negligible against typical startup
  costs (pytest alone is 100+ ms), but not literally zero. Documented in
  `docs/public-api.md` so consumers know the cost.
- **`"0.0.0+unknown"` is non-release-shaped.** Any code that assumes a release
  version will treat it as pre-release. This is **intentional**: the fallback
  should be obviously wrong, not silently accepted as a real version.
- **`_is_version_fallback()` is private.** Consumers who legitimately need to
  detect the fallback (e.g. a test harness) must import a private name.
  Acceptable: the number of such consumers is small and the name is documented
  in `docs/public-api.md` for that audience. If a real external consumer
  appears, promote to `is_version_fallback()` and add it to `__all__` — a
  semver-minor change.
- **`__author__` and `__license__` leave `__all__`.** Consumers who imported
  them via `from forgeqa import *` no longer receive them. `from __future__
  import annotations`-style wildcard imports are rare and discouraged; the
  diagnostic value of these attributes remains, only their API status
  changes.

### Neutral

- `__all__` widens from 1.1.1's implicit surface to
  `("__version__", "get_version")`. `__version__` was already public in
  spirit; `get_version` is new.
- `src/forgeqa/__init__.py` grows from ~30 lines to ~140 lines, mostly
  docstrings and comments. Code complexity is unchanged; the docstrings
  carry the contract.
- Module-private names (`_resolve_version`, `_is_version_fallback`,
  `_IS_FALLBACK_VERSION`, `_DISTRIBUTION_NAME`, `_FALLBACK_VERSION`) become
  discoverable to curious consumers via `dir(forgeqa)`. They are documented
  as private and may change without notice; nothing in this ADR prevents
  that.
- A future PEP 562 `__getattr__` becomes the obvious mechanism for re-exporting
  submodule names lazily. Not needed for 1.1.2; documented as a
  reconsideration trigger.

## Reconsideration Trigger

Revisit this decision if any of the following occurs:

- **`importlib.metadata.version` becomes slow or unavailable.** E.g. on a
  future Python that deprecates it, or in a frozen / zip-imported install
  where metadata lookup is expensive. Mitigation would be a
  `functools.cache`-decorated helper; current implementation is fast enough.
  Concrete signal: `test_import_is_fast` (200 ms budget) starts approaching
  or exceeding its threshold in CI.
- **`setuptools_scm` / `hatch-vcs` becomes desirable for other reasons**
  (e.g. nightly builds with commit SHAs in the version string). The source
  of truth then moves to git tags and `_resolve_version` changes to consult a
  generated file. The isolation and accessor decisions in this ADR would
  remain; only the version-source alternative changes.
- **The fallback is exercised in production.** If real users encounter
  `"0.0.0+unknown"` (e.g. via `pipx run`, a devcontainer, or a broken
  install), the fallback is insufficiently visible. Escalate to a
  clearer signal: a one-time message to `stderr` on first import, a
  property on `get_version()`, or a `sys.version_info`-style diagnostic
  registry.
- **A public consumer needs the fallback state.** Promote
  `_is_version_fallback` to `is_version_fallback`, add it to `__all__`,
  document it in `docs/public-api.md`, and note the addition in the
  changelog. Semver-minor.
- **`__all__` grows past ~20 names.** At that size the module becomes hard to
  scan, and a lazy `__getattr__` re-export from submodules becomes warranted.
  This ADR's isolation decision would be extended, not superseded.
- **PEP 562 `__getattr__` is added for the first re-exported name.** The
  isolation rule (no top-level heavy imports) must be preserved via lazy
  loading; revisit this ADR to document the pattern rather than replace it.
- **The `__all__` tuple/list decision becomes burdensome.** E.g. if a
  code-generation step needs to append names at build time. Currently the
  tuple is chosen for immutability at runtime; a build-time codegen would
  generate a tuple at build time and remain consistent with this decision.

## Related

- WBS 1.1.2 — Implement the Minimum Importable Package & Public API (this
  decision)
- WBS 1.1.1 — Finalise Package Metadata & License (ADR-001, predecessor;
  established the hard-coded `__version__` literal that this ADR replaces)
- WBS 0.4.4 — Public API Contract (the surface that `__all__` pins)
- WBS 0.5.2 — Initial `pyproject.toml` (source of truth for the version)
- ADR-001 — Adopt MIT license file and PEP 621-compliant package metadata
- PEP 562 — Module `__getattr__` and `__dir__` (future lazy re-exports):
  https://peps.python.org/pep-0562/
- PEP 440 — Version Identification and Dependency Specification:
  https://peps.python.org/pep-0440/
- PEP 621 — Storing project metadata in `pyproject.toml`
  (`[project].version` as the source of truth):
  https://peps.python.org/pep-0621/
- `importlib.metadata` documentation:
  https://docs.python.org/3/library/importlib.metadata.html
- `packaging.version.Version` documentation (parsing
  `"0.0.0+unknown"`):
  https://packaging.python.org/en/latest/specifications/version-specifiers/
- `docs/public-api.md` — consumer-facing contract
- `docs/engineering-standards.md` — "Public API import isolation" section
- `tests/unit/test_import.py` — executable form of the WBS 1.1.2 acceptance
  criteria
- `src/forgeqa/__init__.py` — the implementation this ADR documents
