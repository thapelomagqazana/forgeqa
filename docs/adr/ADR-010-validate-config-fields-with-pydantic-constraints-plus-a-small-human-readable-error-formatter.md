# ADR-010: Validate config fields with Pydantic constraints plus a small human-readable error formatter

> **Status**: Accepted
> **Date**: 2026-10-29
> **Deciders**: @thapelomagqazana
> **Consulted**: None
> **Informed**: None

## Context

WBS 1.2.4 requires field-level validation with clear errors:

* `artifacts_dir` must be a valid path that can be created.
* `timeout_ms` must be between 100 and 60000.
* `trace_on_failure` must be a boolean (this is satisfied by
  `DiagnosticsConfig.traces: bool`; Pydantic's bounded bool coercion
  already handles the string forms — see `docs/configuration.md`
  §"Boolean coercion").
* The loader must catch `pydantic.ValidationError` and raise a
  `ForgeQAConfigError` with a **formatted** message, not a raw
  Pydantic traceback.

The traceability KPI is "Users receive actionable configuration
errors, not tracebacks."

ADR-007 (schema), ADR-008 (loader), and ADR-009 (precedence)
established the config subsystem. This ADR extends it with three
concerns:

1. **Field-level constraints** that are not expressible as a type
   alone (`timeout_ms` range, `timeout_seconds` range,
   `artifacts_dir` creatability).
2. **Error formatting** that turns Pydantic's structured error into a
   single-line, human-readable message.
3. **The "no traceback" property**: a user should never see
   `pydantic_core._pydantic_core.ValidationError` in their terminal.

The forces at play:

- **Constraints belong on the type when possible.**
  `Annotated[int, Field(ge=100, le=60_000)]` is clearer and shorter
  than a hand-written `@field_validator`. Pydantic enforces it and
  produces a structured error; the formatter renders it. A
  hand-written validator would reproduce the bound-checking and
  message-construction, which is a source of bugs (off-by-one,
  inconsistent messages).
- **One field needs I/O.** `artifacts_dir` is a path that must be
  creatable. That is a filesystem check, not a type constraint; it
  needs a `@field_validator`.
- **Validation has no side effects.** The `artifacts_dir` validator
  checks that the path *can* be created; it does not create it. A
  config that is loaded but never used should not touch the
  filesystem.
- **Error formatting is a pure function.** It takes a
  `ValidationError` and returns a string. It does not read files, does
  not depend on state, and is testable in isolation.
- **No Pydantic internals in user-facing messages.** Pydantic's raw
  error includes `[type=..., input_value=..., input_type=...]` and
  sometimes a multi-line traceback for nested models. A user editing
  a config file cannot act on that.
- **Two-sided bounds require a schema lookup.** Pydantic v2 emits
  **one error per violated bound**, and each error's `ctx` carries
  only *that* bound. A single error from
  `Annotated[int, Field(ge=100, le=60_000)]` is either
  `{"type": "greater_than_equal", "ctx": {"ge": 100}}` or
  `{"type": "less_than_equal", "ctx": {"le": 60_000}}` — never both.
  The "must be between X and Y" form the ADR and docs promise
  requires looking up the *other* bound from the model schema.
- **Two `loc` shapes.** A caller who constructs
  `ForgeQAConfig(browser={"timeout_ms": 50})` gets
  `loc = ("browser", "timeout_ms")` (length 2). A caller who
  constructs `BrowserConfig(timeout_ms=50)` directly gets
  `loc = ("timeout_ms",)` (length 1, no section prefix). Both must
  render the two-sided message.

## Decision

1. **`timeout_ms` and `timeout_seconds` use `Annotated` constraints,
   not `@field_validator`.** `timeout_ms` is
   `Annotated[int, Field(ge=100, le=60_000)]`; `timeout_seconds` is
   `Annotated[int, Field(ge=1, le=300)]`. Pydantic's
   `greater_than_equal` / `less_than_equal` errors carry the bound
   values in `ctx`; `format_validation_error` renders them as
   `"must be between 100 and 60000, got 50"`.

2. **`artifacts_dir` uses a `@field_validator(mode="after")`.** The
   validator checks:
   - If the path is an existing directory: accept.
   - If the path is an existing file: reject with
     `"artifacts_dir points at an existing file, not a directory: <path>"`.
   - If the path does not exist: walk up to the nearest existing
     ancestor; check that it is a directory and is writable. If yes,
     accept (because `mkdir(parents=True)` would succeed); if no,
     reject with a specific message naming the ancestor.
   - The validator does **not** create the directory.

3. **Validation has no side effects.** The `artifacts_dir` validator
   does not call `mkdir`. The directory is created on first write, as
   documented in `docs/configuration.md` §"`[general]`". The validator
   checks a *property* of the value (the parent is writable), not an
   *outcome* (the directory exists). A config that is loaded but never
   used does not touch the filesystem.

4. **`format_validation_error(exc, *, layer, path=None)` is a pure
   function in `src/forgeqa/config/errors.py`.** It:
   - Takes a `ValidationError`, a `layer` name, and an optional path.
   - Formats the **first** error. If more than one, appends
     `" (and N more)"`.
   - Uses Pydantic's `error["ctx"]` to extract literal options and
     single-sided bounds; consults the model schema
     (`_declared_bounds_for`) for the *other* side of a two-sided bound.
   - Falls back to `error["msg"]` for unrecognised types.
   - Returns a single-line string, no newlines, no
     `[type=..., input_value=...]` annotations, no `pydantic_core`
     references.

5. **`_declared_bounds_for(loc)` handles two `loc` shapes.**
   - **Length 2** (`("browser", "timeout_ms")`): look up the section
     in `ForgeQAConfig`'s top-level properties, then the field in that
     section's sub-schema. Unambiguous.
   - **Length 1** (`("timeout_ms",)`): scan every sub-model for a
     property named `field_name`; the first match wins. The current
     schema has unique field names across sub-models, so the lookup
     is unambiguous today. A future schema with a shared field name
     in two sub-models is a documented limitation (see
     Reconsideration Trigger); callers who need the unambiguous form
     construct `ForgeQAConfig` rather than the sub-model directly.
   - Returns `(lower, upper)` where each side is `None` if not
     declared, or `None` if the field has no `Annotated` bounds.

6. **The field-path prefix is only prepended when `loc` has a
   section.** `_format_error` already names the field (its
   `field_name` is `loc[-1]`). `format_validation_error` prepends
   `_format_loc(loc)` only when `len(loc) >= 2`, so the message reads
   `"browser.timeout_ms must be ..."` for nested locs and
   `"timeout_ms must be ..."` for direct sub-model locs — **no
   duplicate field name in either case**. This was a real bug in an
   early formatter version: an unconditional prefix produced
   `"timeout_ms timeout_ms must be at least 100"`.

7. **The loader calls `format_validation_error` in all four
   `except ValidationError` sites** (three `_validate_layer` branches —
   TOML, env, CLI — plus the final construction in `load_config`).
   The formatted string becomes the first argument to
   `ForgeQAConfigError`. The env branch prepends the env var name(s)
   (via `_env_vars_for_validation_errors`); the TOML branch prepends
   the file path; the CLI branch has no prefix (the formatted message
   already names the field).

8. **A shared `assert_clean_message` helper in `tests/unit/config/__init__.py`**
   asserts no Pydantic internals, no `Traceback`, and no newlines.
   Used by `test_models.py`, `test_loader.py`, `test_precedence.py`,
   and `test_validation.py`.

9. **`test_validation.py` is a separate file** from `test_models.py`.
   The two cover different contracts: `test_models.py` covers "is this
   value valid?" (acceptance); `test_validation.py` covers "what does
   the user see when it is not?" (message shape). The split mirrors
   the schema/loader split in the source.

10. **Error message shape is a contract.** The format is:

    ```
    Invalid configuration in <path>: <section>.<field> <constraint>, got <value>[ (and N more)]
    Invalid environment variable: <section>.<field> <constraint>, got <value>[ (and N more)]
    Invalid CLI override: <section>.<field> <constraint>, got <value>[ (and N more)]
    ```

    The `<constraint>` is one of:
    - `must be between <lower> and <upper>` — two-sided bounds.
    - `must be at least <lower>` / `must be at most <upper>` —
      one-sided bounds (used when the other side is not declared).
    - `must be one of: <option1>, <option2>, ...` — `Literal` fields.
    - `must be a creatable directory: <specific reason>` —
      `artifacts_dir`.
    - `unexpected field: <name>` — unknown keys.
    - (fallback) Pydantic's `error["msg"]`.

## Alternatives Considered

| Alternative | Reason Rejected |
| :--- | :--- |
| Hand-written `@field_validator` for `timeout_ms` and `timeout_seconds` | Reproduces the bound-checking and message-construction that `Annotated[int, Field(ge=..., le=...)]` already does. More code, more surface for bugs (off-by-one, inconsistent messages). `Annotated` is the Pydantic-native way. |
| `mkdir` at validation time | Violates "validation has no side effects". A config that is loaded but never used should not create directories. Also complicates cleanup (a config loaded during a test run leaves a directory behind). |
| Validate only the *type* of `artifacts_dir` (str) | Misses the point of a field-level validator for this field. A typo like `artifacts_dir = "/nope/does/not/exist"` would fail at the first test failure instead of at config-load time. |
| Require the path to exist (`is_dir()` only) | Forces users to `mkdir` the directory manually. The framework should create it on first write. |
| Custom exception class per field (`TimeoutError`, `BrowserNameError`, …) | A user who has two invalid fields would catch two exception types. Single `ForgeQAConfigError` with a clear message is simpler for the caller; the field name is in the message. |
| Raise `ValidationError` directly (let Pydantic's traceback show) | The WBS explicitly says "The error message does not expose internal Pydantic tracebacks". Pydantic's raw error includes `[type=..., input_value=..., input_type=...]` and a `pydantic_core._pydantic_core.ValidationError:` line that a user cannot act on. |
| Format *all* errors as a multi-line list | A config with two invalid fields is rare; a single-line message with `" (and N more)"` is enough for the common case. Multi-line is a follow-up (Reconsideration Trigger). |
| Return a `list[str]` of all errors from `load_config` | Would force every caller to handle multiple errors. The current `ForgeQAConfigError` is a single exception; a future `ConfigErrorReport` could hold multiple, but not today. |
| `parse_validation_error` in the loader (instead of `errors.py`) | The formatter is a pure function; putting it in `errors.py` next to `ForgeQAConfigError` makes it discoverable and keeps `loader.py` focused on the layering logic. |
| Use `pydantic.errors` (a package of Pydantic's error formatters) | Pydantic's formatters are for its own error rendering; they do not produce the "section.field must be X, got Y" shape that a config file user needs. |
| Put the `assert_clean_message` helper in `tests/support.py` | `tests/support.py` is for *all* tests; the config helper is only used by config tests. Putting it in `tests/unit/config/__init__.py` keeps it with its consumers and avoids polluting the global test helpers. |
| Trust `error["ctx"]` to carry both bounds | **It does not.** Pydantic v2 emits one error per violated bound. The first implementation expected both in `ctx`; the 10 `test_validation.py` failures proved it wrong. The formatter now consults the schema for the *other* bound. This alternative is recorded because it is the obvious-looking approach and will be re-attempted by a future contributor unless the ADR names it. |
| Render the one-sided form and accept it | Technically accurate, but the WBS acceptance criterion says "mentioning the field and valid **range**" — a range has two ends. A user who sets `timeout_ms = 100_000` and sees only "must be at least 100" might think 100_000 is acceptable. The two-sided form names both ends. |
| Unconditionally prepend `_format_loc(loc)` in `format_validation_error` | Produced `"timeout_ms timeout_ms must be ..."` for length-1 locs (a real bug caught by the tests). `_format_error` already names the field. The prefix is only useful when `loc` carries a section. |
| Fix the tests to accept the one-sided form | The tests, the ADR, and `docs/configuration.md` §"Validation" all promise the two-sided form. The implementation was wrong; the tests were right. Fixing the implementation was the correct response. |
| Cache `ForgeQAConfig.model_json_schema()` at import time | Would run the schema walk when `forgeqa.config.errors` is imported, i.e. for every consumer who imports the module (to catch `ForgeQAConfigError`) even if they never trigger a validation error. Pydantic caches the schema per class, so the first call at error time is ~2 ms and subsequent calls are ~10 µs; the cost is only paid by the failure path. Lazy is better. |

## Consequences

### Positive

- **Errors are actionable.** `"browser.timeout_ms must be between 100 and 60000, got 50"` tells the user exactly which field, which range, and which value.
- **No Pydantic internals leak.** The `[type=..., input_value=...]` annotations and the `pydantic_core._pydantic_core.ValidationError:` traceback line are stripped. The message is one line.
- **Constraints live on the type.** `Annotated[int, Field(ge=..., le=...)]` is shorter and clearer than a hand-written validator, and Pydantic's error has the bound values in `ctx` (so the formatter can render them).
- **`artifacts_dir` is validated early.** A typo in the path fails at config-load time, not at the first test failure.
- **Validation has no side effects.** A config that is loaded but never used does not touch the filesystem.
- **The formatter is testable in isolation.** `format_validation_error(exc, layer="TOML", path=...)` is a pure function; its output can be asserted without going through the loader.
- **The three-layer error attribution is preserved.** TOML errors name the file path; env errors name the env var; CLI errors name the field. A user knows which of their three inputs to fix.
- **Both loc shapes render the same two-sided message.** `BrowserConfig(timeout_ms=50)` and `ForgeQAConfig(browser={"timeout_ms": 50})` both produce `"must be between 100 and 60000, got 50"`. The length-1 form omits the section prefix (there is no section), the length-2 form includes it. Neither duplicates the field name.

### Negative

- **`artifacts_dir` validation is platform-dependent.** `os.access(parent, os.W_OK)` on Windows uses a slightly different heuristic than on POSIX, and running as root makes every path writable. The `test_artifacts_dir_rejects_unwritable_parent` test skips when the filesystem does not enforce read-only (e.g. as root). This is a documented limitation; a future PR could add a Windows-specific test.
- **Multiple errors are collapsed.** A config with two invalid fields shows the first and " (and 1 more)". A user who fixes the first and re-runs will see the second, so no information is lost, but it is a two-round-trip experience. Multi-line is a follow-up.
- **`_declared_bounds_for` is per-error.** The function walks the JSON schema once per formatted error. For a typical config with one invalid field, this is one walk (~10 µs after Pydantic's per-class cache warms). For a hypothetical config with hundreds of invalid fields, this would be hundreds of walks; not a real concern (the caller would fix the first error and re-run).
- **The length-1 lookup is ambiguous if two sub-models share a field name with different bounds.** Not the case today; documented in Reconsideration Trigger. The fix is a future ADR if the schema ever shares field names.
- **The `value_error` branch strips `"Value error, "`.** Pydantic v2 prefixes a `ValueError` message with that string; the formatter strips it. If Pydantic v3 changes the prefix, the strip becomes a no-op and the user sees `"Value error, artifacts_dir must be a creatable directory: ..."`. Cosmetic; a future fix is one line.
- **The formatter's two-sided branch is only as good as the schema lookup.** If a future Pydantic version changes the JSON schema shape (e.g. moves `minimum` / `maximum` under a different key), the lookup returns `None`, and the formatter falls back to the one-sided form. The tests would catch this (they assert the two-sided form); the fix is to update `_declared_bounds_for` for the new shape.
- **Tests for `artifacts_dir` use real directories** (`tmp_path`), which is slower than a mock. The `test_artifacts_dir_rejects_unwritable_parent` test in particular does `chmod` and skips on filesystems that ignore it. The cost is worth it: mocking `Path.is_dir` and `os.access` would test the mock, not the validator.

### Neutral

- `src/forgeqa/config/errors.py` grows by ~180 lines (the formatter plus `_declared_bounds_for`).
- `src/forgeqa/config/models.py` grows by ~50 lines (the validator and the `Annotated` field types).
- `src/forgeqa/config/loader.py` shrinks slightly (four `except` blocks now call the formatter instead of `str(exc)`).
- `tests/unit/config/test_validation.py` is a new file (~330 lines, ~20 tests).
- `tests/unit/config/__init__.py` gains a shared helper (`assert_clean_message`).
- `tests/unit/config/test_models.py` is updated for the new bounds (parametrisations extended; the two single-value boundary tests are replaced by parametrised boundary tests).
- `docs/configuration.md` "Validation" section is rewritten.
- `docs/engineering-standards.md` §5.1 gains a rule on message formatting; Document History gets a `0.2.0` row (new minor: the error shape is a contract).
- `docs/adr/ADR-010-*.md` is added; `docs/adr/README.md` is regenerated.
- `docs/public-api.md` §`forgeqa.config` gains `format_validation_error`.
- No new dependencies.

## Reconsideration Trigger

Revisit this decision if any of the following occurs:

- **A user reports multiple invalid fields in one config.** If the "first + (and N more)" experience causes a two-round-trip, add a `format_validation_errors(exc)` that returns a multi-line list. The current `format_validation_error` becomes `format_validation_errors(exc)[0]` in that case. Semver-minor.
- **Pydantic v3 changes error shape.** The formatter reads `error["type"]`, `error["loc"]`, `error["ctx"]`, `error["input"]`, `error["msg"]`. `_declared_bounds_for` reads `ForgeQAConfig.model_json_schema()` and expects `$defs`, `properties`, `$ref`, `minimum`, `maximum`. If v3 changes any of these, both the formatter and the schema walk need updating. `test_validation.py` pins the current shapes; a v3 upgrade will fail the tests with a clear diff.
- **A new field type introduces a new Pydantic error type.** The formatter falls back to `error["msg"]`, which is already human-readable. If the fallback turns out to be ugly (e.g. `"Input should be a valid dictionary or instance of X"`), add a case to `_format_error`.
- **A future schema shares a field name across two sub-models with different bounds.** The length-1 `_declared_bounds_for` lookup picks the first match; the two-sided form could be wrong for one of the sub-models. Fix options: (a) require `ForgeQAConfig` construction (length-2 locs), (b) add a test enforcing unique field names, or (c) pass the section explicitly through `format_validation_error`. Requires a new ADR if it happens.
- **The schema lookup becomes a performance concern.** E.g. if `format_validation_error` is called in a loop with hundreds of errors. Add `functools.cache` to a `_schema_for()` helper; the cache is per-process and survives across calls. Not needed today.
- **`artifacts_dir` validator semantics change.** E.g. if a future feature wants to create the directory eagerly (violating "no side effects"), the validator moves to a loader step. That would need an ADR amendment.
- **Windows test coverage.** The `test_artifacts_dir_rejects_unwritable_parent` test skips on filesystems that ignore `chmod`. A Windows-specific test (using `attrib +R` or a different mechanism) is a follow-up. Not critical; the POSIX test covers the code path.
- **The `assert_clean_message` regex needs extension.** If Pydantic adds a new internal annotation format, extend `PYDANTIC_INTERNAL_RE`. The regex is one line in `tests/unit/config/__init__.py`.
- **Error messages become a problem for i18n / localization.** The current messages are English strings. A future localization feature would need a message-catalog layer. Not currently planned.
- **A field needs a one-sided bound by design** (e.g. a future `max_retries: Annotated[int, Field(ge=0)]` with no upper bound). The formatter's one-sided fallback ("must be at least 0") is correct for that field; no change needed. If the schema wants "between 0 and infinity", it should declare `le=...` explicitly.

## Related

- WBS 1.2.4 — Implement Field-Level Validation with Clear Errors (this decision)
- WBS 1.2.1 — Define the Root Pydantic Configuration Schema (ADR-007; the schema this ADR constrains)
- WBS 1.2.2 — Implement TOML Configuration Loader (ADR-008; the loader this ADR teaches to format errors)
- WBS 1.2.3 — Enforce Configuration Precedence Hierarchy (ADR-009; the layering this ADR's error formatter is applied to)
- WBS 0.4.5 — Configuration Contract (the original requirement)
- ADR-006 — Formalise the public API surface and the private-module naming convention (`forgeqa.config.__all__` follows the convention)
- ADR-007 — Model the ForgeQA configuration as a strictly-typed Pydantic v2 hierarchy with explicit defaults
- ADR-008 — Load forgeqa.toml into ForgeQAConfig with tomllib and a custom ForgeQAConfigError
- ADR-009 — Resolve configuration precedence as CLI args > environment variables > forgeqa.toml > defaults
- `src/forgeqa/config/errors.py` — the error formatter
- `src/forgeqa/config/models.py` — the constraints and the `artifacts_dir` validator
- `src/forgeqa/config/loader.py` — the call sites
- `tests/unit/config/test_validation.py` — the executable contract for message shape
- `tests/unit/config/test_models.py` — the executable contract for acceptance
- `docs/configuration.md` §"Validation" — consumer-facing reference
- `docs/engineering-standards.md` §5.1 — contributor-facing rules
- Pydantic `Annotated` and `Field` constraints:
  https://docs.pydantic.dev/latest/concepts/fields/
- Pydantic `ValidationError.errors()` (the structured error shape):
  https://docs.pydantic.dev/latest/errors/errors/
- Pydantic custom validators:
  https://docs.pydantic.dev/latest/concepts/validators/#field-validators
- Pydantic `model_json_schema` (used by `_declared_bounds_for`):
  https://docs.pydantic.dev/latest/concepts/json_schema/
