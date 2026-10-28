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
- [`ADR-006`](adr/ADR-006-formalise-public-api-surface-and-private-module-convention.md)
  — the decision record for this contract (the `_`-prefix rule and the
  semver promise).
- [`ADR-007`](adr/ADR-007-pydantic-config-hierarchy.md) — the
  configuration schema decision.
- [`ADR-008`](adr/ADR-008-load-forgeqa-toml-into-forgeqaconfig.md) — the
  configuration loader decision.
- [`docs/engineering-standards.md`](engineering-standards.md) — the rules
  contributors follow to keep this contract intact (§4.14 is the
  contributor-facing counterpart to this document; §5.1 and §5.2 cover the
  configuration schema and loader).
- [`docs/configuration.md`](configuration.md) — the consumer-facing
  reference for `forgeqa.toml`: every field, type, default, validation
  rule, and loader behaviour.
- [`tests/unit/test_import.py`](../tests/unit/test_import.py) — the
  executable form of the import-time guarantees below.
- [`tests/unit/test_public_api.py`](../tests/unit/test_public_api.py) —
  the executable form of the top-level public-surface contract below.
- [`tests/unit/config/test_models.py`](../tests/unit/config/test_models.py)
  — the executable form of the `forgeqa.config` schema contract.
- [`tests/unit/config/test_loader.py`](../tests/unit/config/test_loader.py)
  — the executable form of the `forgeqa.config.load_config` contract.

---

## Top-level: `import forgeqa`

```python
import forgeqa

forgeqa.__version__  # str, e.g. "0.1.0"
forgeqa.get_version()  # str, same value as __version__
forgeqa.__all__  # tuple[str, ...], the names below
```

### The public surface of `forgeqa`

**As of 0.1.0 (pre-alpha), the entire public API of the top-level
`forgeqa` package consists of the following names.** Everything else —
fixtures, settings, adapters, reporting — lands in Phase 1 (MVP) and will
be added to this document (and to `forgeqa.__all__`) in the same PR that
ships it. The `forgeqa.config` subpackage has its own public surface; see
[`forgeqa.config`](#forgeqaconfig) below.

| Name | Kind | Since | Description |
| :--- | :--- | :--- | :--- |
| `forgeqa.__version__` | `str` | 0.1.0 | The PEP 440 version string of the installed `forgeqa` distribution, or `"0.0.0+unknown"` when running from an uninstalled source checkout (see "Version resolution" below). |
| `forgeqa.get_version()` | `() -> str` | 0.1.0 | Recommended accessor; returns the same value as `__version__`. Preferred in reports, logs, and artifacts because it insulates callers from a future refactor where `__version__` may become lazily evaluated. |
| `forgeqa.__all__` | `tuple[str, ...]` | 0.1.0 | The names above. Immutable (a `tuple`, not a `list`). Adding a name is semver-minor. |

`forgeqa.__all__ == ("__version__", "get_version")`.

This is verified by
`tests/unit/test_public_api.py::test_all_matches_documented_surface`
(which asserts the tuple against a **test-authoritative**
`EXPECTED_ALL` constant, so a change to `forgeqa.__all__` without a
change to the test and this document fails CI).

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

The public-vs-internal contract is enforced by
`tests/unit/test_public_api.py`:

| Contract | Test |
| :--- | :--- |
| `__all__` matches the documented surface | `test_all_matches_documented_surface` |
| `__all__` is a tuple (immutable) | `test_all_is_immutable_tuple` |
| Every documented name is accessible | `test_documented_names_are_accessible` |
| `get_version() == __version__` | `test_get_version_matches_dunder_version` |
| No `_`-prefixed name in `__all__` (parametrised) | `test_private_name_not_in_all[4 params]` |
| No `_`-prefixed name in `__all__` (structural) | `test_no_underscore_name_in_all` |
| No `_`-prefixed submodule imported by `__init__.py` (source) | `test_no_private_module_in_source_tree_top_level` |
| No `_`-prefixed submodule in `sys.modules` after import (runtime) | `test_no_private_submodule_imported_by_top_level` |
| The doc itself states the `_`-prefix rule | `test_public_api_doc_exists_and_mentions_underscore_rule` |

---

## `forgeqa.config`

The `forgeqa.config` subpackage is the public interface to ForgeQA's
configuration. It is a **top-level public module** — not `_`-prefixed —
so `from forgeqa.config import ForgeQAConfig` is a stable import path.

It is **not** imported by `import forgeqa` (the top-level module is
deliberately minimal). It is imported only when a consumer needs to read
or construct a config.

### The public surface of `forgeqa.config`

`forgeqa.config.__all__ == ( "APIConfig", "BrowserConfig", "BrowserName",
"DEFAULT_CONFIG_FILENAME", "DiagnosticsConfig", "ForgeQAConfig",
"ForgeQAConfigError", "GeneralConfig", "LogLevel", "ReportingConfig",
"find_config_path", "load_config" )`.

| Name | Kind | Since | Description |
| :--- | :--- | :--- | :--- |
| `forgeqa.config.ForgeQAConfig` | `type[BaseModel]` | 0.2.0 | The root configuration model. Composes the five sub-models. Instantiable with no arguments (all defaults). Frozen and forbids unknown keys. |
| `forgeqa.config.GeneralConfig` | `type[BaseModel]` | 0.2.0 | Run identity (environment, artifacts dir, log level). |
| `forgeqa.config.BrowserConfig` | `type[BaseModel]` | 0.2.0 | UI (Playwright) adapter configuration. |
| `forgeqa.config.APIConfig` | `type[BaseModel]` | 0.2.0 | API (HTTPX) adapter configuration. |
| `forgeqa.config.DiagnosticsConfig` | `type[BaseModel]` | 0.2.0 | What evidence to capture (screenshots, traces, console logs). |
| `forgeqa.config.ReportingConfig` | `type[BaseModel]` | 0.2.0 | What reports to emit (JUnit XML, JSON report). |
| `forgeqa.config.BrowserName` | `typing.Literal` alias | 0.2.0 | The set of valid `browser_name` values (`"chromium"`, `"firefox"`, `"webkit"`). Exposed so consumers can type their own helpers against the same set. |
| `forgeqa.config.LogLevel` | `typing.Literal` alias | 0.2.0 | The set of valid `log_level` values (`"DEBUG"`, `"INFO"`, `"WARNING"`, `"ERROR"`). Exposed for the same reason. |
| `forgeqa.config.load_config` | `(path: Path \| str \| None = None) -> ForgeQAConfig` | 0.2.0 | Load a `forgeqa.toml` file into a `ForgeQAConfig`. Falls back to defaults if no file is present. |
| `forgeqa.config.find_config_path` | `(directory: Path \| None = None) -> Path \| None` | 0.2.0 | Find `forgeqa.toml` in a directory. Returns an absolute path or `None`. |
| `forgeqa.config.DEFAULT_CONFIG_FILENAME` | `str` | 0.2.0 | The filename `load_config` searches for (`"forgeqa.toml"`). |
| `forgeqa.config.ForgeQAConfigError` | `type[Exception]` | 0.2.0 | Raised by `load_config` for malformed TOML, invalid values, unreadable files, or a missing explicit path. Carries a `path` attribute. |

### Guarantees

`import forgeqa.config`:

- **Is cheap.** Does not import Playwright, HTTPX, or Pytest. It imports
  `pydantic` (for the models) and `tomllib` (for the loader); both are
  core dependencies. On a warm interpreter it completes in a few
  milliseconds.
- **Is side-effect free.** No file reads, no network calls, no log
  records, no warnings. The import itself does not call `load_config`.
- **`load_config()` is deterministic.** Each call reads the file fresh
  (no caching). Two calls on the same file produce equal configs; two
  calls with an edit in between produce different configs.
- **`load_config()` never returns a partial config.** A partial
  `forgeqa.toml` produces a fully-populated `ForgeQAConfig` with
  defaults for unspecified fields.
- **`load_config()` raises `ForgeQAConfigError`** for any load failure,
  with a message that names the file path (and, for syntax errors,
  the line/column when `tomllib` provides it).

These guarantees are enforced by `tests/unit/config/test_models.py`
(schema) and `tests/unit/config/test_loader.py` (loader). See
[`docs/configuration.md`](configuration.md) for the consumer-facing
reference.

### Stability promise for `forgeqa.config`

The same semver rules apply (see [Stability promise](#stability-promise-summary)
below). In particular:

- Adding a field to a model is **patch** (the default is preserved for
  existing configs).
- Adding a new model, or a new public function, is **minor**.
- Removing or renaming a name in `forgeqa.config.__all__` is **major**.
- Changing a default is **minor** (it changes consumer behaviour); it
  is documented in the release notes.
- Changing `load_config`'s signature (in a non-additive way) is **major**.

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

## Optional functionality (Phase 1)

The following are **not** imported by `import forgeqa`. They are imported
explicitly from their submodules when the caller needs them. They require the
corresponding optional extras, and they **land in Phase 1** — none of them
exist yet.

| Import | Requires extra | Available from | Purpose |
| :--- | :--- | :--- | :--- |
| `from forgeqa.fixtures import browser` | `forgeqa[ui]` | Phase 1 (MVP) | Playwright browser fixture. |
| `from forgeqa.fixtures import api_client` | `forgeqa[api]` | Phase 1 (MVP) | HTTPX API client fixture. |

> **Why these are not imported at the top level:** importing them would
> require Playwright or HTTPX at `import forgeqa` time, which breaks the
> isolation guarantee above. The submodule is loaded only when the caller
> actually asks for the fixture.

When these submodules land, each will:

- Be a top-level module (not `_`-prefixed) — so
  `from forgeqa.fixtures import browser` is a stable import path.
- Have its own `__all__` listing exactly what it exports publicly.
- Be added to `PUBLIC_SUBMODULES` in
  `tests/unit/test_public_api.py`, so its `__all__` is asserted.
- Be documented in a new subsection here, in the same PR.

See ADR-002 §Reconsideration Trigger for the lazy-re-export pattern
(PEP 562 `__getattr__`) if a future API wants
`from forgeqa import Settings` to work without importing Pydantic eagerly.
That decision is not made yet.

---

## What is *not* public

The following are **not** part of the contract and may change at any time,
including in patch releases, without notice:

1. **Any name starting with a single underscore** — e.g.
   `_resolve_version`, `_is_version_fallback`, `_DISTRIBUTION_NAME`,
   `_FALLBACK_VERSION`, `_IS_FALLBACK_VERSION`. The leading underscore
   is the standard Python convention for "internal use only", and
   ForgeQA treats it as a contract: any name or module prefixed with
   `_` is private.

2. **Any module under a `_`-prefixed subpackage** — e.g.
   `forgeqa._internal`, `forgeqa._compat`,
   `forgeqa._adapters.playwright`, `forgeqa._reporting.junit`. The
   entire `_adapters` and `_reporting` trees are private. Import from
   `forgeqa` or from a documented public submodule, never from a
   private path.

3. **Any module-level attribute not listed in `forgeqa.__all__`** —
   e.g. `forgeqa.__author__`, `forgeqa.__license__` (these are kept
   for diagnostics and for `help(forgeqa)` output; they are not API).

4. **The internal layout of `src/forgeqa/`** — the directory structure
   (whether `src/` or flat, whether `_adapters/` or `adapters/`) is an
   implementation detail. Also: the internal layout of
   `src/forgeqa/config/` (`models.py`, `loader.py`, `errors.py` may be
   split or reorganised; import from `forgeqa.config`, not from
   `forgeqa.config.models`).

5. **The exact value of `"0.0.0+unknown"`** (in the fallback case) —
   treat it as "not a real version" and do not pattern-match against
   the literal. The *fact* that a fallback exists is public; its
   literal value is not.

6. **The behaviour of `import forgeqa` under exotic installs**
   (zip-import, namespace packages spanning multiple roots). These are
   not supported for ForgeQA itself; sub-modules may document their
   own behaviour later.

7. **The `ForgeQAConfigError` message format.** The message is for
   humans; the `path` attribute is the stable programmatic interface.
   A tool that parses the message (fragile but possible) is not
   covered by the contract. See ADR-008's reconsideration trigger.

### Why the `_`-prefix rule

Python's PEP 8 style guide has recommended a leading underscore for
"internal use only" names since the language was standardised. ForgeQA
treats that recommendation as a **contract**:

- `_name` (single underscore, module-level) is private per PEP 8.
- `__name` (double underscore, class-level) is name-mangled; not
  relevant to module imports.
- `__name__` (dunder) is used for special methods and
  interpreter-defined attributes. In ForgeQA, `__version__` is a
  **public** dunder because it is documented here and appears in
  `forgeqa.__all__`. All other dunders are implementation detail.

The rule is enforced by `tests/unit/test_public_api.py` on four axes:
membership in `__all__` (`test_private_name_not_in_all`), structure
(`test_no_underscore_name_in_all`), source (`test_no_private_module_in_source_tree_top_level`),
and runtime (`test_no_private_submodule_imported_by_top_level`). If a
future change breaks any of these, CI fails.

**If you have a use case that requires relying on something in this
list, please open an issue** — either the thing should be promoted to
the public API (a documented, versioned change) or there is a supported
alternative that we should document instead.

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
| Add a name to `forgeqa.__all__` or `forgeqa.config.__all__` | minor |
| Remove or rename a name in `forgeqa.__all__` or `forgeqa.config.__all__` | major |
| Change `get_version()` return type | major |
| Change the fallback sentinel `"0.0.0+unknown"` | patch (it is not public), but the *fact* that a fallback exists is public — a "no fallback, raise" policy would be major. |
| Add a new documented submodule (`forgeqa.fixtures`, `forgeqa.config`, …) | minor |
| Add a field to a `forgeqa.config` model (with a default) | patch |
| Change a `forgeqa.config` model field's default | minor |
| Change a `forgeqa.config` model field's type (accepting new values) | minor |
| Change a `forgeqa.config` model field's type (rejecting previously valid values) | major |
| Change `load_config`'s signature (in a non-additive way) | major |
| Change the `ForgeQAConfigError` message format | patch (the message is for humans; the `path` attribute is the stable interface) |
| Change import-time guarantees (e.g. begin importing Playwright at top level) | major (would be a breaking change for consumers without the `ui` extra). |
| Add a top-level warning at import | major (it would break `-W error` consumers). |
| Move a public name into a `_`-prefixed module | major (would break anyone importing the public name). |
| Rename a public submodule to a `_`-prefixed one | major (would break anyone importing the submodule). |

---

## How this contract is enforced

This document is the human-readable contract. Six tools enforce the
machine-readable form on every pull request:

1. **`tests/unit/test_public_api.py`** — asserts `forgeqa.__all__`
   matches `EXPECTED_ALL` (a test-authoritative constant, not imported
   from `forgeqa`, so a change to `forgeqa.__all__` without a change to
   the test fails). Also asserts the `_`-prefix rule on four axes, that
   `get_version() == __version__`, and that this document exists and
   states the rule. Runs in ~50 ms; also invocable as
   `make verify-public-api`.

2. **`tests/unit/test_import.py`** — asserts the import-time
   guarantees: cheap, side-effect free, deterministic, idempotent, no
   warnings, no optional dependency imported at top level. Runs in
   ~1 s as part of `make test`.

3. **`tests/unit/config/test_models.py`** — asserts the schema
   contract: defaults, valid values, invalid values, boundary values,
   composition, immutability, JSON schema. Runs in ~50 ms as part of
   `make verify-config`.

4. **`tests/unit/config/test_loader.py`** — asserts the loader
   contract: valid files, missing files, malformed TOML, invalid
   values, edge cases, idempotency, determinism. Runs in ~50 ms as
   part of `make verify-config`.

5. **`scripts/verify_build.sh`** — asserts the wheel contains the
   package and `LICENSE`, and does not contain `tests/`, `docs/`, or
   any `_`-prefixed top-level module. Runs in ~10 s; `make verify-build`.

6. **`scripts/verify_install.sh`** — asserts the wheel installs in a
   fresh venv and `import forgeqa` resolves outside the source tree.
   Runs in ~20 s; `make verify-install`.

`make ci` runs all six. `make verify-public-api` runs only the
top-level public-API contract test (~50 ms) for quick local iteration
or as a pre-commit hook. `make verify-config` runs only the config
tests (~100 ms) for the same reason.

---

## Reporting issues with the public API

If `import forgeqa` or `forgeqa.config` violates any guarantee in this
document — e.g. `import forgeqa` imports Playwright, it emits a
warning, `forgeqa.__version__` disagrees with `pip show forgeqa`, or
`load_config` returns a partial config — please open an issue at
<https://github.com/thapelomagqazana/forgeqa/issues> with:

1. The output of `python -c "import forgeqa; print(forgeqa.__version__)"`.
2. The output of `pip show forgeqa`.
3. The output of `python -c "import sys; print(sorted(sys.modules))"` after
   `import forgeqa` (redact anything sensitive).
4. If the issue is config-related: the contents of your `forgeqa.toml`
   (redact any secrets; ForgeQA does not put secrets in config, but
   a user might), the output of `python -c "from forgeqa.config import load_config; print(load_config())"`, and any `ForgeQAConfigError` message.
5. The Python version and platform.

Every guarantee in this document is covered by a test. A regression that
violates the contract should be caught by CI; a user-visible failure
therefore usually indicates an environment problem (editable install drift,
a stale `.venv`, an interpreter-level `-W error` flag, or — for config
issues — a `forgeqa.toml` that was edited but not re-read), which the
diagnostics above will identify.

---

## See also

- [`README.md`](../README.md) — project overview and Quick Start.
- [`docs/architecture.md`](architecture.md) — system architecture and
  dependency rules.
- [`docs/engineering-standards.md`](engineering-standards.md) — the
  contributor-facing rules, including §4.14 "Public vs. Internal Module
  Conventions" and §5 "Configuration" (§5.1 schema, §5.2 loader).
- [`docs/configuration.md`](configuration.md) — the consumer-facing
  reference for `forgeqa.toml`: every field, type, default,
  validation rule, and loader behaviour.
- [`docs/adr/ADR-001`](adr/ADR-001-adopt-mit-license-file-and-pep-621-compliant-package-metadata.md)
  — package metadata baseline.
- [`docs/adr/ADR-002`](adr/ADR-002-resolve-package-version-at-import-time-via-importlib-metadata-and-keep-top-level-imports-dependency-free.md)
  — version resolution and import isolation.
- [`docs/adr/ADR-005`](adr/ADR-005-verify-installed-wheel-outside-source-tree.md)
  — clean install (the consumer-facing side of `scripts/verify_install.sh`).
- [`docs/adr/ADR-006`](adr/ADR-006-formalise-public-api-surface-and-private-module-convention.md)
  — this contract.
- [`docs/adr/ADR-007`](adr/ADR-007-pydantic-config-hierarchy.md) — the
  configuration schema decision.
- [`docs/adr/ADR-008`](adr/ADR-008-load-forgeqa-toml-into-forgeqaconfig.md)
  — the configuration loader decision.
- [`tests/unit/test_import.py`](../tests/unit/test_import.py) — the
  executable form of the import-time guarantees.
- [`tests/unit/test_public_api.py`](../tests/unit/test_public_api.py) —
  the executable form of the public-surface contract.
- [`tests/unit/config/test_models.py`](../tests/unit/config/test_models.py)
  — the executable form of the config schema contract.
- [`tests/unit/config/test_loader.py`](../tests/unit/config/test_loader.py)
  — the executable form of the config loader contract.
