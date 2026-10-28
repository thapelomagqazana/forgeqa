# ForgeQA Public API

This document is the **contract** between ForgeQA and its consumers.

- Only names listed here are supported.
- Anything else — including module-private names, internal submodules, and
  non-`__all__` module attributes — is implementation detail and may change
  without a deprecation cycle.
- Stability guarantees are scoped to a **major** version: names here are
  stable within a major release. Adding a name is semver-minor; removing or
  renaming a name is semver-major.

The companion documents are:

- [`ADR-002`](adr/ADR-002-resolve-package-version-at-import-time-via-importlib-metadata-and-keep-top-level-imports-dependency-free.md)
  — why the top-level module is kept free of optional dependencies.
- [`docs/engineering-standards.md`](engineering-standards.md) — the rules
  contributors follow to keep this contract intact.
- [`tests/unit/test_import.py`](../tests/unit/test_import.py) — the executable
  form of every guarantee below.

---

## Top-level: `import forgeqa`

```python
import forgeqa

forgeqa.__version__  # str, e.g. "0.1.0"
forgeqa.get_version()  # str, same value as __version__
forgeqa.__all__  # tuple[str, ...], the names below
```

### The public surface of `forgeqa`

| Name | Kind | Description |
| :--- | :--- | :--- |
| `forgeqa.__version__` | `str` | The PEP 440 version string of the installed `forgeqa` distribution, or `"0.0.0+unknown"` when running from an uninstalled source checkout (see "Version resolution" below). |
| `forgeqa.get_version()` | `() -> str` | Recommended accessor; returns the same value as `__version__`. Preferred in reports, logs, and artifacts because it insulates callers from a future refactor where `__version__` may become lazily evaluated. |
| `forgeqa.__all__` | `tuple[str, ...]` | The names above. Immutable. Adding a name is semver-minor. |

`forgeqa.__all__ == ("__version__", "get_version")`.

### Guarantees

`import forgeqa`:

- **Is cheap.** Does not import Playwright, HTTPX, Pydantic, Pytest, or any
  optional dependency. On a warm interpreter it completes in a few
  milliseconds; the budget enforced by the test suite is 200 ms.
- **Is side-effect free.** No file writes, no network calls, no log records,
  no warnings. The module body imports only `importlib.metadata` and
  `typing`.
- **Is deterministic.** Two imports of the same installation yield the same
  version string.
- **Never raises for missing metadata.** If the distribution is not installed
  (e.g. running from a source checkout without `pip install -e .`), the
  version is `"0.0.0+unknown"` and `import forgeqa` still succeeds.
- **Is idempotent.** `import forgeqa` twice in the same interpreter returns
  the same module object.
- **Emits no warnings**, including under `warnings.simplefilter("error")`.

These guarantees are enforced by `tests/unit/test_import.py`:

| Guarantee | Test |
| :--- | :--- |
| Import succeeds | `test_import_forgeqa_succeeds` |
| Version is a `str` | `test_version_attribute_exists_and_is_string` |
| Version matches installed metadata | `test_version_is_resolved_from_installed_metadata` |
| No Playwright import | `test_optional_dependency_not_imported[playwright]` |
| No HTTPX import | `test_optional_dependency_not_imported[httpx]` |
| No optional dep in module graph | `test_no_optional_dependency_in_module_graph` |
| Import is idempotent | `test_import_is_idempotent` |
| Fallback is observable | `test_version_fallback_is_observable` |
| Installed path is not fallback | `test_version_fallback_skips_when_installed` |
| `__all__` is immutable | `test_all_is_immutable` |
| No import-time filesystem/network side effects | `test_no_import_time_filesystem_or_network` |
| Acceptance criteria verbatim | `test_acceptance_criteria_are_met_verbatim` |
| Import is fast | `test_import_is_fast` |
| Deterministic across runs | `test_import_is_deterministic_across_runs` |
| No import-time warnings | `test_import_does_not_emit_warnings` |

---

## Version resolution

`forgeqa.__version__` is resolved from the **installed distribution's
`METADATA`** via `importlib.metadata.version("forgeqa")`. The value in
`pyproject.toml` (`[project].version`) is authoritative; `forgeqa.__version__`
reflects it.

This is the same mechanism `pip show forgeqa` uses, so the value returned by
`pip show` and the value seen by `import forgeqa` are guaranteed to agree.

### The `"0.0.0+unknown"` fallback

When the distribution is not installed — e.g. running from a source checkout
without `pip install -e .` — `importlib.metadata.version` raises
`PackageNotFoundError`. `forgeqa` catches **only** that exception and returns
the literal `"0.0.0+unknown"`. Consequences:

- `import forgeqa` never crashes for missing metadata.
- The value parses under `packaging.version.Version` as a post-release of
  `0.0.0`, so tools that parse versions still succeed.
- The value sorts **below** any real release, so any code that compares
  versions will not accidentally treat the fallback as a real version.
- The value is deliberately not release-shaped: it signals "this is not a
  real release" to anyone inspecting it, including in logs and reports.

Any **other** exception raised while reading metadata (e.g. a corrupt
`METADATA` file) is **not** caught and will propagate. A corrupt install is a
real problem that should be visible, not masked by a fallback.

### Detecting the fallback (advanced)

In rare cases (typically inside a test harness or an external verification
tool) a consumer may need to distinguish an installed release from an
uninstalled source checkout. The private helper:

```python
forgeqa._is_version_fallback()  # -> bool
```

returns `True` when `__version__` came from the fallback path.

**This helper is not part of the public API.** It is not listed in
`forgeqa.__all__`, may change between releases without a deprecation cycle,
and must not be relied on outside test tooling. If you find yourself needing
it in production code, open an issue — the correct fix is likely a promotion
to a public `is_version_fallback()` (a semver-minor change), which is already
on the ADR-002 reconsideration-trigger list.

---

## Optional functionality

The following are **not** imported by `import forgeqa`. They are imported
explicitly from their submodules when the caller needs them. They require the
corresponding optional extras.

| Import | Requires extra | Available from | Purpose |
| :--- | :--- | :--- | :--- |
| `from forgeqa.fixtures import browser` | `forgeqa[ui]` | Phase 1 (MVP) | Playwright browser fixture. |
| `from forgeqa.fixtures import api_client` | `forgeqa[api]` | Phase 1 (MVP) | HTTPX API client fixture. |
| `from forgeqa.settings import load_settings` | core | Phase 1 (MVP) | Read `forgeqa.toml` and return a validated `Settings` object. |
| `from forgeqa.settings import Settings` | core | Phase 1 (MVP) | Validated settings type (Pydantic model). |

> **Why these are not imported at the top level:** importing them would
> require Playwright, HTTPX, or Pydantic at `import forgeqa` time, which
> breaks the isolation guarantee above. The submodule is loaded only when the
> caller actually asks for the fixture or the settings loader.

When these submodules land, each name they expose will be added to the
relevant submodule's `__all__` and documented in a section here, in the same
PR, with a changelog note. See ADR-002 §Reconsideration Trigger for the
lazy-re-export pattern (PEP 562 `__getattr__`) if a future API wants
`from forgeqa import Settings` to work without importing Pydantic eagerly.

---

## What is *not* public

The following are **not** part of the contract and may change at any time,
including in patch releases, without notice:

- Any name starting with `_` — e.g. `_resolve_version`,
  `_is_version_fallback`, `_DISTRIBUTION_NAME`, `_FALLBACK_VERSION`,
  `_IS_FALLBACK_VERSION`.
- Any module-level attribute not listed in `forgeqa.__all__` — e.g.
  `forgeqa.__author__`, `forgeqa.__license__` (these are kept for diagnostics
  and for `help(forgeqa)` output; they are not API).
- The internal layout of `src/forgeqa/` — e.g. private submodules named
  `forgeqa._internal`, `forgeqa._compat`. Import from `forgeqa` or from
  documented submodules, never from `forgeqa._*`.
- The exact value of `"0.0.0+unknown"` (in the fallback case) — treat it as
  "not a real version" and do not pattern-match against the literal.
- The behaviour of `import forgeqa` under exotic installs (zip-import,
  namespace packages spanning multiple roots). These are not supported for
  ForgeQA itself; sub-modules may document their own behaviour later.

If you have a use case that requires relying on something in this list, please
open an issue — either the thing should be promoted to the public API (a
documented, versioned change) or there is a supported alternative that we
should document instead.

---

## Version support policy

- `import forgeqa` works on Python 3.11 and 3.12 (the declared support
  window; see `pyproject.toml` `[project].requires-python`).
- The metadata field `Requires-Python` in the built wheel is the PEP 440
  canonical form of `>=3.11,<3.13`, which is `<3.13,>=3.11`. This is
  semantically identical; see ADR-001 and ADR-002 for why the two forms
  appear different.
- Pre-1.0 versions (`0.x.y`) are **alpha**; the public API above is stable,
  but new names may be added in any minor release without a deprecation
  cycle, and pre-1.0 removals are treated as breaking (semver-major in
  spirit, minor in practice until 1.0).

---

## Stability promise (summary)

| Change | Semver impact |
| :--- | :--- |
| Add a name to `forgeqa.__all__` | minor |
| Remove or rename a name in `forgeqa.__all__` | major |
| Change `get_version()` return type | major |
| Change the fallback sentinel `"0.0.0+unknown"` | patch (it is not public), but the *fact* that a fallback exists is public — a "no fallback, raise" policy would be major. |
| Add a new documented submodule (`forgeqa.fixtures`, `forgeqa.api`, …) | minor |
| Change import-time guarantees (e.g. begin importing Playwright at top level) | major (would be a breaking change for consumers without the `ui` extra). |
| Add a top-level warning at import | major (it would break `-W error` consumers). |

---

## Reporting issues with the public API

If `import forgeqa` violates any guarantee in this document — e.g. it imports
Playwright, it emits a warning, or `forgeqa.__version__` disagrees with
`pip show forgeqa` — please open an issue at
<https://github.com/thapelomagqazana/forgeqa/issues> with:

1. The output of `python -c "import forgeqa; print(forgeqa.__version__)"`.
2. The output of `pip show forgeqa`.
3. The output of `python -c "import sys; print(sorted(sys.modules))"` after
   `import forgeqa` (redact anything sensitive).
4. The Python version and platform.

Every guarantee in this document is covered by a test in
`tests/unit/test_import.py`. A regression that violates the contract should
be caught by CI; a user-visible failure therefore usually indicates an
environment problem (editable install drift, a stale `.venv`, or an
interpreter-level `-W error` flag), which the four diagnostics above will
identify.

---

## See also

- [`README.md`](../README.md) — project overview and Quick Start.
- [`docs/architecture.md`](architecture.md) — system architecture and
  dependency rules.
- [`docs/engineering-standards.md`](engineering-standards.md) — "Public API
  import isolation" rules for contributors.
- [`docs/adr/ADR-001`](adr/ADR-001-adopt-mit-license-file-and-pep-621-compliant-package-metadata.md)
  — package metadata baseline.
- [`docs/adr/ADR-002`](adr/ADR-002-resolve-package-version-at-import-time-via-importlib-metadata-and-keep-top-level-imports-dependency-free.md)
  — version resolution and import isolation.
- [`tests/unit/test_import.py`](../tests/unit/test_import.py) — executable
  contract.
