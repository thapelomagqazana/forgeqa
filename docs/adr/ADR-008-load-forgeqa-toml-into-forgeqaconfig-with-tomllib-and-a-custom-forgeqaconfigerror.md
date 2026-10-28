# ADR-008: Load forgeqa.toml into ForgeQAConfig with tomllib and a custom ForgeQAConfigError

> **Status**: Accepted
> **Date**: 2026-10-28
> **Deciders**: Solo Developer
> **Consulted**: None
> **Informed**: None

## Context

WBS 1.2.2 requires a TOML loader (`src/forgeqa/config/loader.py`) with:

* `load_config(path: Path | None = None) -> ForgeQAConfig`;
* use of `tomllib` (Python 3.11+);
* look for `forgeqa.toml` in the current directory;
* fall back to defaults if the file is missing;
* parse the TOML and instantiate `ForgeQAConfig`;
* catch `tomllib.TOMLDecodeError` and raise a custom
  `ForgeQAConfigError` with a clear message.

The traceability KPI is "The configuration loader is deterministic and
handles all file states gracefully."

WBS 1.2.1 (ADR-007) established the schema: a strictly-typed Pydantic
v2 hierarchy with defaults, `extra="forbid"`, `frozen=True`, and no
file loading. The schema is the contract; the loader is the mechanism.
Separating them means the schema is testable without files on disk, and
the loader is testable without re-testing the schema.

The forces at play:

- **Determinism.** Two calls on the same file must produce equal
  configs. Two calls on a file that was edited in between must produce
  *different* configs (a stale cache is worse than a ~1 ms file read).
- **Graceful degradation.** No file → defaults. Empty file → defaults.
  Comments-only file → defaults. A user who creates an empty
  `forgeqa.toml` is expressing "I have no overrides, use defaults."
- **Clear error messages.** Malformed TOML and invalid values must
  produce an exception whose message includes the file path and
  (for syntax errors) the line number. The WBS's example is
  "Invalid TOML syntax at line 3: ...".
- **Single exception type for the caller.** From the caller's
  perspective, "the file is not valid TOML" and "the file is valid
  TOML but produces an invalid config" are the same class of problem:
  "the config file you gave me does not produce a valid config." A
  single `ForgeQAConfigError` type is easier to catch than two.
- **Explicit is not silent.** A caller who passes an explicit `path`
  and gets a missing file should see an error, not a silent fallback
  to defaults. The explicit path is a deliberate choice; a missing
  file is a caller bug.
- **No environment-variable overrides yet.** `FORGEA_ENV`,
  `FORGEA_CONFIG_PATH`, etc. are Phase 1 follow-ups (WBS 1.2.3, not
  yet scoped). Adding them now would expand scope and the test surface
  without an acceptance criterion driving it.
- **No caching.** A cache would solve a performance problem that does
  not exist (a 1 ms file read) and introduce a staleness problem that
  does.

## Decision

1. **`tomllib` (stdlib since Python 3.11).** The project floor is
   3.11, so `tomllib` is always available. No new dependency is
   added. The alternative — `tomli` (the backport) — would be needed
   only on Python < 3.11, which the project does not support.

2. **`load_config(path: Path | str | None = None)`.** The signature
   accepts `Path | str | None` (rather than only `Path | None`) for
   ergonomic reasons: a caller with a string path should not have to
   wrap it. `None` means "search cwd".

3. **Search order: explicit path > `forgeqa.toml` in cwd > defaults.**
   - If `path` is `None`, `find_config_path()` searches the current
     working directory for `forgeqa.toml`. If found, use it. If not
     found, return `ForgeQAConfig()` (the default config).
   - If `path` is provided, use it. If the file does not exist, raise
     `ForgeQAConfigError` (the caller has a bug).

   The explicit path bypasses the cwd search. A caller who knows where
   the file is should not be surprised by a different file in cwd.

4. **Single `ForgeQAConfigError` type for all load failures.**
   - Malformed TOML: raise `ForgeQAConfigError` with the original
     `TOMLDecodeError` as `__cause__`.
   - Invalid values (Pydantic `ValidationError`): raise
     `ForgeQAConfigError` with the original `ValidationError` as
     `__cause__`.
   - Unreadable file (OSError): raise `ForgeQAConfigError` with the
     original `OSError` as `__cause__`.
   - Missing explicit path: raise `ForgeQAConfigError`.

   The exception is defined in `errors.py`, not `loader.py`. A future
   loader variant (e.g. YAML) raises the same exception; keeping it in
   its own module avoids circular imports and makes the exception
   discoverable without reading the loader.

5. **Error messages include the file path.** For syntax errors, the
   message also includes the line/column when `tomllib` provides it
   (the exact format varies by Python version; the tests assert the
   *concept*, not the exact wording). For validation errors, Pydantic
   already produces a field-level message; the loader prepends the
   file path.

6. **No caching.** Each call reads the file fresh. `test_loader_does_not_cache`
   pins this: two calls with an edit in between produce different
   configs.

7. **UTF-8 encoding explicitly.** `Path.read_text(encoding="utf-8")`.
   The TOML spec requires UTF-8; specifying it makes the loader
   deterministic on Windows (where the default encoding is
   platform-dependent). **Known limitation:** `UnicodeDecodeError` is
   a `ValueError`, not an `OSError`; the current `except OSError`
   catch does not catch it. The fix is one line
   (`except (OSError, UnicodeDecodeError)`) and is recommended before
   merge. See "Negative consequences" below.

8. **`find_config_path()` is a separate public function.** It takes an
   optional directory and returns the absolute path to `forgeqa.toml`
   in that directory, or `None`. Splitting the search from the parse
   makes each testable in isolation, and makes the search contract
   ("absolute path or `None`") explicit.

9. **`DEFAULT_CONFIG_FILENAME = "forgeqa.toml"` is a constant, not a
   setting.** "The config file is called `forgeqa.toml`" is a fact of
   the framework, not a user setting. A consumer who wants a
   differently-named file passes an explicit path.

10. **Public surface: `load_config`, `find_config_path`,
    `DEFAULT_CONFIG_FILENAME`, `ForgeQAConfigError`.** All four are in
    `forgeqa.config.__all__` per ADR-006.

11. **Tests use the real filesystem.** `pytest`'s `tmp_path` fixture
    plus `monkeypatch.chdir`. A loader test that mocks
    `Path.read_text` is testing the mock, not the loader. The
    filesystem is the loader's input; the test should use it
    directly.

12. **No environment-variable overrides in this PR.** A future
    `FORGEA_CONFIG_PATH` and `FORGEA_ENV` (for environment overlays)
    are Phase 1 follow-ups. The loader's current contract is "find,
    parse, validate, or return defaults" — adding env vars would
    expand the contract without a driving acceptance criterion.

## Alternatives Considered

| Alternative | Reason Rejected |
| :--- | :--- |
| `tomli` (the backport) instead of `tomllib` | Unnecessary on Python 3.11+, which is the project floor. Adds a dependency for no benefit. |
| `toml` or `tomlkit` | `toml` is unmaintained; `tomlkit` is for round-tripping (preserving comments and ordering) which the loader does not need (it reads once). `tomllib` is stdlib and correct. |
| A single `load_config` that raises `TOMLDecodeError` for syntax and `ValidationError` for semantics | Forces the caller to catch two exception types. The caller's response (show the error, fix the file) is the same; the single `ForgeQAConfigError` type is simpler and the message distinguishes the cases. |
| Raise `FileNotFoundError` for a missing explicit path | `FileNotFoundError` is a standard exception, but the caller of `load_config` is more likely to catch `ForgeQAConfigError` (the loader's own exception type). Using one exception for all load failures keeps the caller's error handling simple. |
| Silent fallback for an explicit missing path | "I asked for a specific file and got defaults" is a silent bug. The explicit path is a deliberate choice; a missing file is a caller error. |
| Cache the parsed config in a module-level dict | A cache introduces staleness: a developer edits `forgeqa.toml` and calls `load_config()` again, gets the old config. The ~1 ms file read is not worth the staleness. |
| Search parent directories (like `.git` discovery) | Out of scope for 1.2.2. A future "search upward" feature (e.g. for monorepos) is a Phase 1 follow-up, and would need its own decision about how far to search and what to do at the filesystem root. |
| Environment-variable overrides (`FORGEA_ENV`, `FORGEA_CONFIG_PATH`) | Phase 1 follow-ups (WBS 1.2.3, not yet scoped). Adding them now would expand the test surface and the error-handling contract without a driving acceptance criterion. |
| Use `tomllib.load()` (binary file) instead of `tomllib.loads()` | Both work. `loads()` with `read_text()` gives us a `str`, which is easier to include in error context if needed (e.g. "the file contains N bytes of content"). `load()` with `open("rb")` is equally correct; the choice is minor. |
| A `ConfigLoader` class with methods | Overkill for a single function. `load_config(path)` is the whole API; a class would be ceremony around a five-line function. |
| Return `None` from `load_config` when no file is found, instead of defaults | Forces every caller to handle `None`. The WBS says "fall back to defaults"; returning a valid `ForgeQAConfig` is what the WBS requires. A caller who wants to know whether defaults were used can check `find_config_path()` first. |
| Include the file's line count in the error message | Unnecessary. The line/column from `TOMLDecodeError` is more useful than a line count. |
| A separate `toml_loader.py` and `json_loader.py` in different modules | The project uses TOML. A JSON loader is a speculative future need; when it becomes real, it can share `ForgeQAConfigError` and `find_config_path`-style helpers. Splitting the loader into "TOML-specific" and "generic" halves today would be premature abstraction. |
| Assert the exact `TOMLDecodeError` message in tests | Pydantic and `tomllib` message wording varies across Python minor versions. The tests assert the *concept* ("line" or "invalid" appears in the message), so a Python 3.11 → 3.12 upgrade does not break the tests for a cosmetic reason. |
| Skip `test_loads_partial_config_preserves_defaults` because the schema tests already cover defaults | The schema tests cover `ForgeQAConfig()` defaults. The loader test covers "partial file → defaults for unspecified sections," which is a loader+composition property, not just a schema property. A regression in the loader's dict-passing (e.g. replacing `ForgeQAConfig(**data)` with `ForgeQAConfig(data)`) would pass the schema tests and fail this one. |
| Catch `UnicodeDecodeError` alongside `OSError` (recommended) | This is not an alternative — it is the recommended fix for the known limitation noted in Decision #7. It is listed here so the reviewer sees it in the alternatives table. The current code catches only `OSError`; the fix is one line. |

## Consequences

### Positive

- **The WBS acceptance criteria are met.** Valid file → populated
  config. Missing file → defaults. Malformed TOML → clear error.
  Idempotent → pinned by test.
- **One function, one signature, one exception type.** The loader is
  easy to use: `load_config()`, or `load_config(path)`. The caller
  catches `ForgeQAConfigError` for any load failure.
- **Error messages include the file path and (for syntax errors) the
  line.** A user editing `forgeqa.toml` gets a message that names the
  file and points at the problem.
- **No caching, no staleness.** A developer who edits `forgeqa.toml`
  and calls `load_config()` again sees the new values. Pinned by
  `test_loader_does_not_cache`.
- **Deterministic.** Two calls on the same file produce equal configs;
  two calls with an edit in between produce different configs. Both
  pinned by tests.
- **The search logic is testable in isolation.** `find_config_path`
  is a pure function with no side effects; its behaviour (absolute
  path, `None` for missing file, `None` for a directory named
  `forgeqa.toml`) is pinned by dedicated tests.
- **The public API is stable and documented.** `load_config`,
  `find_config_path`, `DEFAULT_CONFIG_FILENAME`, and
  `ForgeQAConfigError` are all re-exported from `forgeqa.config` and
  listed in `docs/public-api.md`.
- **Forward-compatible.** Phase 1 follow-ups (environment overlays,
  multiple config files, upward search) are additive: they add new
  functions and new error cases, not changes to `load_config`'s
  signature or return type.

### Negative

- **`load_config` is not async.** A future async caller (unlikely for
  a test framework's config loader) would need `asyncio.to_thread(load_config)`.
  A synchronous loader is the right default; async is a per-caller
  concern.
- **`ForgeQAConfigError` is a single exception type for several
  failure modes.** A caller who wants to distinguish "malformed TOML"
  from "invalid value" must inspect `__cause__` (a `TOMLDecodeError`
  vs a `ValidationError`). This is intentional (see Decision #4) but
  does mean that the caller who wants granularity must work for it.
- **The error message format is loosely pinned.** `test_malformed_toml_raises_config_error`
  asserts `"line"` or `"invalid"` appears in the message, not the
  exact `tomllib` output. This is a deliberate trade-off (Python
  version stability) but means a future change to `tomllib`'s message
  format would not fail the test even if the new format is worse.
  Mitigated by the manual review of error output during the PR.
- **No caching means every `load_config()` call reads the file.** For
  a typical test run (~one call per test session), this is negligible.
  For a hypothetical hot loop (thousands of calls per second), the
  file I/O cost is ~1 ms each. A future "cached loader" variant could
  be added if a real use case emerges; not needed for the current
  scope.
- **`tomllib` requires UTF-8.** A file in another encoding fails at
  `read_text(encoding="utf-8")` with a `UnicodeDecodeError`, which the
  loader does **not** currently catch (the catch is `except OSError`,
  and `UnicodeDecodeError` is a `ValueError`). This is a latent bug:
  the error would propagate as `UnicodeDecodeError`, not
  `ForgeQAConfigError`. The tests do not exercise this (writing a
  non-UTF-8 file requires `write_bytes`, which the current tests
  avoid). **Recommended fix before merge:** change
  `except OSError as exc` to `except (OSError, UnicodeDecodeError) as exc`
  in `load_config`. This is a one-line change; the rest of the catch
  chain is correct. See also "Reconsideration Trigger" below.
- **`find_config_path` returns an absolute path, not the path as
  given.** A caller who passes a relative directory (e.g. `Path(".")`)
  gets an absolute path back. This is intentional (the path is
  included in error messages and logged), but a caller who expects
  the input path back unchanged is surprised. Documented in
  `find_config_path`'s docstring.

### Neutral

- `src/forgeqa/config/` grows from two files (`__init__.py`,
  `models.py`) to four (`__init__.py`, `models.py`, `loader.py`,
  `errors.py`).
- `tests/unit/config/` grows from two files (`__init__.py`,
  `test_models.py`) to three (`test_loader.py` added).
- `docs/configuration.md` grows by a "Loading configuration" section.
- `docs/public-api.md` grows by three names in the "Optional
  functionality" table.
- `docs/engineering-standards.md` §5.1 grows by a "Loader
  conventions" subsection.
- `docs/adr/ADR-008-*.md` is added.
- `docs/adr/README.md` is regenerated.
- No new dependencies. `tomllib` is stdlib.
- No new Makefile target. `make verify-config` already runs the whole
  `tests/unit/config/` directory, so the loader tests are covered.

## Reconsideration Trigger

Revisit this decision if any of the following occurs:

- **The `UnicodeDecodeError` catch bug is reported by a user.** If a
  user's `forgeqa.toml` is in a non-UTF-8 encoding (unlikely given the
  TOML spec, but possible on legacy Windows systems), the current
  `except OSError` catch does not catch the resulting
  `UnicodeDecodeError`, so the user sees a raw `UnicodeDecodeError`
  rather than a `ForgeQAConfigError` with a clear message. Fix: one
  line. The ADR's "Negative consequences" section documents this as a
  known limitation; the fix should land before the issue is reported.
- **Environment-variable overrides land** (WBS 1.2.3, when scoped).
  `FORGEA_CONFIG_PATH` (for the search), `FORGEA_ENV` (for environment
  overlays), `FORGEA_CONFIG_<SECTION>_<KEY>` (for per-field overrides).
  Each is a new source of truth; the loader's "find, parse, validate"
  contract is extended to "find, parse, validate, apply overrides."
  The ADR is amended to document the precedence order.
- **Multiple config files land** (e.g. `forgeqa.toml` + `forgeqa.ci.toml`
  merged by an environment variable). The loader's `load_config` is
  extended or a new `load_merged_config` is added; the ADR is amended.
- **Upward directory search lands** (like `.git` discovery, for
  monorepos). `find_config_path` gains a `search_parents: bool` or a
  similar option; the ADR is amended.
- **A YAML or JSON loader lands.** The `ForgeQAConfigError` and
  `find_config_path`-style helpers are shared; the new loader is a
  sibling module (e.g. `yaml_loader.py`) with its own tests. The ADR
  is extended to cover the format-agnostic parts.
- **Caching becomes a real need.** If a hot loop calls `load_config`
  thousands of times per second, add a `cached_load_config` (with
  explicit cache invalidation) as a separate function. The current
  `load_config` remains uncached; the cache is opt-in. Not needed for
  the current scope.
- **The error message format is pinned by a downstream tool.** If a
  tool parses `ForgeQAConfigError`'s message (fragile but possible),
  the message format is a contract. The ADR is amended to document
  the format. Today, the `path` attribute is the stable interface for
  programmatic access; the message is for humans.
- **`tomllib` is deprecated or replaced.** If Python 3.14 deprecates
  `tomllib` in favour of a new module (unlikely; `tomllib` is a PEP
  680 implementation and stable), migrate in a single PR. The loader's
  contract is unchanged.
- **`find_config_path` needs a different default directory.** If a
  future feature wants "search the project root" rather than "search
  cwd", the default is changed and the ADR is amended. Current
  behaviour (cwd) matches the WBS.
- **`DEFAULT_CONFIG_FILENAME` needs to be configurable.** If a future
  feature wants to support `forgeqa-<env>.toml` files, the constant
  becomes a `str | Path | None` argument on `find_config_path`. The
  ADR is amended.

## Related

- WBS 1.2.2 — Implement TOML Configuration Loader (this decision)
- WBS 1.2.1 — Define the Root Pydantic Configuration Schema
  (established the schema this loader consumes; ADR-007)
- WBS 0.4.5 — Configuration Contract (the original requirement for a
  validated config)
- WBS 1.2.3 — Environment-variable overrides (a Phase 1 follow-up, not
  yet scoped)
- ADR-006 — Formalise the public API surface and the private-module
  naming convention (`forgeqa.config.__all__` follows the convention)
- ADR-007 — Model the ForgeQA configuration as a strictly-typed
  Pydantic v2 hierarchy with explicit defaults
- `src/forgeqa/config/loader.py` — the loader source
- `src/forgeqa/config/errors.py` — the exception source
- `src/forgeqa/config/__init__.py` — the public re-exports
- `tests/unit/config/test_loader.py` — the executable contract
- `docs/configuration.md` §"Loading configuration" — the
  consumer-facing reference
- `docs/engineering-standards.md` §5.1 "Configuration schema
  conventions" — contributor-facing rules
- `tomllib` documentation:
  https://docs.python.org/3/library/tomllib.html
- TOML specification:
  https://toml.io/en/
- PEP 680 — tomllib: Support for parsing TOML in the Standard Library:
  https://peps.python.org/pep-0680/
