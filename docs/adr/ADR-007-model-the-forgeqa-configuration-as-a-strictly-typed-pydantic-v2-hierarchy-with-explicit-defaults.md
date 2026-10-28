# ADR-007: Model the ForgeQA configuration as a strictly-typed Pydantic v2 hierarchy with explicit defaults

> **Status**: Accepted
> **Date**: 2026-10-28
> **Deciders**: Solo Developer
> **Consulted**: None
> **Informed**: None

## Context

WBS 1.2.1 requires a configuration schema (`src/forgeqa/config/models.py`)
with:

* a root model `ForgeQAConfig` and five sub-models (`GeneralConfig`,
  `BrowserConfig`, `APIConfig`, `DiagnosticsConfig`, `ReportingConfig`);
* strict typing — `Literal["chromium", "firefox", "webkit"]` for
  `browser_name`, `AnyHttpUrl` for `base_url`, `PositiveInt` for
  timeouts, `Literal["DEBUG", "INFO", "WARNING", "ERROR"]` for
  `log_level`;
* sensible defaults on every field;
* composition (the root model contains the sub-models).

The traceability KPI is "The configuration schema is strictly typed and
fully composable."

The WBS is the first concrete deliverable of the Configuration Contract
(WBS 0.4.5). That contract says:

> Configuration is validated at parse time, with a clear error message
> naming the field and (for constrained fields) listing the valid values.
> A typo in a config file must fail at parse time, not silently use a
> default.

That requirement is what makes the "strict typing" part of the WBS
non-negotiable: a schema that coerces `browser_name = "safari"` to
`"chromium"` (or to `None`) is worse than no schema, because it hides
the mistake.

The forces at play:

- **Strict typing.** The WBS explicitly names `Literal`, `AnyHttpUrl`,
  `PositiveInt` for specific fields. The contract explains why: a typo
  must fail at parse time, not silently. This is a design requirement,
  not a style preference.
- **Sensible defaults.** `ForgeQAConfig()` must be valid with no
  arguments. Every field needs a default; the defaults are the
  "when you don't configure anything" behaviour, documented in
  `docs/configuration.md`.
- **Composability.** The root model composes five sub-models. Each
  sub-model is constructible in isolation (a test can construct a
  `BrowserConfig` without the other four). A consumer can pass a
  partial override like `ForgeQAConfig(browser={"browser_name": "firefox"})`
  and get defaults for everything else.
- **Immutability.** A config object passed to a fixture, a test, a
  reporter, and a CI script must not be mutable. If one consumer
  mutates it, the others see the mutation. Frozen models eliminate
  this class of bug.
- **Unknown keys are rejected.** A typo like `timout_ms` in a
  hand-edited `forgeqa.toml` must fail at parse time, not silently use
  the default.
- **The schema is testable without files on disk.** The schema is the
  contract; loading a file into it is a separate concern. Separating
  them means the schema is testable with pure-Python construction, and
  the loader is testable without re-testing the schema.
- **Forward-compatible.** Phase 1 adds a TOML loader. Phase 3 adds
  report-path configuration. Phase 5 adds browser-launch options. The
  schema must grow by adding fields and sub-models, not by
  restructuring.

## Decision

1. **Pydantic v2 (already a core dependency).** `pydantic>=2.14.1` is
   in `[project].dependencies` from WBS 1.1.1. No new dependency is
   added. The Pydantic v2 features relied on are `Literal`,
   `AnyHttpUrl`, `PositiveInt`, `ConfigDict`, and
   `model_json_schema`.

2. **Five sub-models, one concern each.**
   - `GeneralConfig` — run identity and artifacts location.
   - `BrowserConfig` — how to launch a browser (UI adapter).
   - `APIConfig` — how to talk to an HTTP API (API adapter).
   - `DiagnosticsConfig` — what evidence to capture.
   - `ReportingConfig` — what reports to emit.

   Diagnostics and reporting are separate because a consumer might
   want full diagnostics but no JUnit XML (a local debugging run), or
   minimal diagnostics but full JUnit XML (a CI run that only needs
   pass/fail). Combining them would conflate two concerns.

3. **Composition, not inheritance.** The root model is
   `class ForgeQAConfig(BaseModel)` with five sub-model fields. No
   sub-model inherits from another; each is a standalone `BaseModel`.
   This means each is constructible and testable in isolation, and
   adding a new concern (e.g. `DatabaseConfig` in Phase 6) is a new
   class plus one new field on the root, not a class hierarchy change.

4. **Strict typing on every constrained field.**
   - `BrowserName = Literal["chromium", "firefox", "webkit"]` — a
     `str` would accept `"safari"`; a `Literal` fails at parse time
     and (in Pydantic's error message) lists the valid values.
   - `LogLevel = Literal["DEBUG", "INFO", "WARNING", "ERROR"]` —
     `CRITICAL` is excluded (see `docs/configuration.md` §"Why not
     `CRITICAL`?"); `TRACE` is excluded because it is not a stdlib
     `logging` level.
   - `base_url: AnyHttpUrl` — accepts `http`/`https` with a valid
     host; rejects `"not-a-url"`, `"http://"`, `"ftp://..."`, `""`.
   - `timeout_ms: PositiveInt`, `timeout_seconds: PositiveInt` —
     `gt=0`; `0` and negative values fail with "greater than 0".

5. **Sensible defaults on every field.** A new user's
   `ForgeQAConfig()` is a useful configuration, not just a valid one.
   The defaults are chosen for the "typical test framework" use case
   (headless, 10 s timeouts, all diagnostics and reports on) and
   documented field-by-field in `docs/configuration.md`.

6. **`model_config = ConfigDict(extra="forbid", frozen=True, ...)` on
   every model.**
   - `extra="forbid"` — a typo in a TOML key fails at parse time.
   - `frozen=True` — a config object cannot be mutated after
     construction.
   - `str_strip_whitespace=True` — trailing/leading whitespace in
     hand-edited TOML values is stripped.
   - `validate_assignment=True` — even a caller who subclasses and
     unfreezes cannot assign an invalid value.
   - `validate_default=True` — a malformed default (e.g. a future
     contributor writes `timeout_ms: PositiveInt = -1`) fails at
     class-definition time, not at first instantiation.

   The five flags are applied to every model, not just the root. A
   sub-model constructed in isolation has the same guarantees as one
   constructed through the root.

7. **No cross-field validators *yet*.** Every cross-field rule that
   would be added today ("if `headless=False` and `environment='ci'`,
   warn"; "if `screenshots=True` and `browser_name` is unset, error")
   is speculative. When a concrete rule exists, it gets a
   `@model_validator(mode="after")` and a test in the same PR.
   Speculative cross-field rules are the class of bug where a future
   legitimate config fails because of a rule nobody remembers adding.

8. **The schema does not load files.** `forgeqa.toml` loading
   (environment overlays, secret resolution, path expansion) is
   Phase 1 work (WBS 1.2.2). The schema is the contract; the loader
   is the mechanism. Separating them means the schema is testable with
   pure-Python construction and the loader is testable without
   re-testing the schema.

9. **Public re-exports in `forgeqa/config/__init__.py`.** Consumers
   import `ForgeQAConfig`, `BrowserConfig`, etc., from
   `forgeqa.config`, not from `forgeqa.config.models`. The `models`
   submodule is an implementation detail; it may be split into
   `browser.py` / `api.py` / etc. in a future PR without a breaking
   change. The public names are listed in
   `forgeqa/config/__init__.py::__all__`, consistent with ADR-006's
   `__all__` convention.

10. **The schema is tested by `tests/unit/config/test_models.py`.**
    Defaults, valid values, invalid values, boundary values,
    composition, immutability, JSON schema, and round-trip
    serialisation are covered. The test file is part of `make test`
    and runs via `make verify-config` in isolation (~50 ms).

11. **`docs/configuration.md` is the consumer-facing reference.**
    Every field, its type, default, and validation rule. It is the
    document a user reads to decide what to configure; it is updated
    in the same PR as any field change, so the doc and the schema
    cannot drift.

## Alternatives Considered

| Alternative | Reason Rejected |
| :--- | :--- |
| Dataclasses (`@dataclass`) with hand-written validators | Would require hand-writing URL validation, literal validation, positive-int validation, and the associated error messages. Pydantic provides all of them out of the box, with better error messages and a JSON schema. The project already depends on Pydantic (WBS 1.1.1), so there is no dependency cost. |
| `attrs` | Similar to dataclasses: hand-written validators for every constrained type. `attrs` has validators but not built-in URL/literal types; Pydantic is the better fit for a config schema. |
| Pydantic v1 | v1 is deprecated; v2 has better performance, stricter typing, and the `model_config = ConfigDict(...)` form. No reason to use v1 on a new project. |
| `TypedDict` / `NamedTuple` | No validation. A `TypedDict` is a type-checker-only construct; at runtime it is a plain `dict` that accepts anything. The whole point of this schema is runtime validation. |
| `msgspec` | A new dependency; the project already uses Pydantic. `msgspec` is excellent for performance-critical parsing, but ForgeQA's config is parsed once per test run. No reason to add a second serialisation library. |
| All fields as `str` with hand-written validators | Defeats the "strict typing" requirement. A `str` `browser_name` accepts `"safari"` until a hand-written validator rejects it; a `Literal` fails at parse time with the valid values listed. The WBS explicitly names `Literal`, so this alternative is a direct violation of the WBS. |
| `HttpUrl` instead of `AnyHttpUrl` | `HttpUrl` is stricter about some edge cases (e.g. it may reject certain subdomains). The WBS specifies `AnyHttpUrl`, and the common test-target URL `http://localhost:8000` is accepted by both, but `AnyHttpUrl` is more permissive for staging environments with unusual hostnames. |
| `PositiveInt` replaced by `int` with a custom validator | `PositiveInt` is `Annotated[int, Field(gt=0)]` — the constraint is part of the type, so it shows up in the JSON schema, the error message, and type checking. A hand-written validator duplicates what Pydantic does. |
| One big `ForgeQAConfig` with no sub-models | Loses the "sub-models are constructible in isolation" property. A test that wants to check `BrowserConfig` behaviour would have to construct a full `ForgeQAConfig`. Composition is the WBS requirement. |
| Sub-models using inheritance (`class BrowserConfig(GeneralConfig)`) | No relationship exists between the concerns. Inheritance is the wrong tool; composition is correct. |
| Cross-field validators for speculative rules | See Decision #7. The rules are not concrete; adding them speculatively is the class of bug where a future legitimate config fails. |
| Config loader bundled with the schema | See Decision #8. Separating concerns makes both testable independently. The loader is Phase 1 work. |
| `frozen=False` (mutable configs) | A config object passed to multiple consumers must not be mutable. One consumer's mutation must not affect others. |
| `extra="ignore"` (silently ignore unknown keys) | A typo like `timout_ms` would silently use the default, which is exactly the bug the WBS's "clear error" requirement exists to prevent. |
| `str_strip_whitespace=False` (preserve whitespace) | Whitespace around values in hand-edited TOML is common; stripping it silently prevents a class of "why doesn't my URL work" bugs. |
| Public API in `models.py` directly (no `__init__.py` re-export) | Consumers would import from `forgeqa.config.models`, which locks the module path. `__init__.py` re-export lets the implementation be split without a breaking change. |
| No `docs/configuration.md` (schema is self-documenting via JSON schema) | A JSON schema is not a good user-facing doc — it is machine-readable but not user-readable. A markdown reference with examples is what users actually read. |
| Immutable `ForgeQAConfig` but mutable sub-models | A consumer who keeps a reference to `cfg.browser` could mutate it, affecting the parent's "frozen" guarantee indirectly (the parent's reference still points at the mutated sub-model). Both must be frozen. |
| Reject `0` for `timeout_ms` only via documentation | A `PositiveInt` rejects `0` at parse time; documentation would just describe the rule. The WBS's "clear error" requirement is met by the type, not the doc. |

## Consequences

### Positive

- **The schema is strict and fully composable.** Every field is
  precisely typed; every sub-model is constructible in isolation and
  through the root.
- **Invalid values fail at parse time with actionable messages.** A
  typo in `forgeqa.toml` fails immediately, not silently at first use.
- **The schema is testable without files on disk.** `pytest
  tests/unit/config/test_models.py` runs in ~50 ms with no I/O beyond
  importing Pydantic.
- **The schema is the single source of truth for validation.** The
  future TOML loader (Phase 1) delegates to the same models; no
  duplicate validation.
- **The JSON schema is generated automatically.** A future config
  validator, IDE plugin, or docs generator can consume
  `ForgeQAConfig.model_json_schema()`.
- **Immutability eliminates a class of bug.** A config object can be
  passed to multiple consumers without risk of one mutating it.
- **The docs cannot drift from the schema.** `docs/configuration.md`
  lists every field; the test suite asserts the defaults and
  validation rules. Changing a field without changing the doc fails
  review (or, if the review misses it, a future test-driven update
  catches it).
- **Forward-compatible.** Phase 1 adds a loader; Phase 3 adds
  report-path configuration; Phase 5 adds browser-launch options.
  The schema grows by adding fields, not by restructuring.

### Negative

- **Pydantic is the only config-validation dependency.** This was
  already true (WBS 1.1.1), but it is now a load-bearing
  dependency — the schema is expressed entirely in Pydantic
  primitives. A future decision to drop Pydantic would require
  reimplementing `Literal`, `AnyHttpUrl`, `PositiveInt`, `ConfigDict`,
  and the error-message formatting. Documented in the reconsideration
  trigger.
- **`AnyHttpUrl` normalises the trailing slash.** `http://localhost:8000`
  becomes `http://localhost:8000/` in the validated form. Tests
  compare by `host`/`port`/`scheme` rather than raw string, which is
  slightly more verbose but correct. Documented in
  `docs/configuration.md`.
- **`str_strip_whitespace=True` silently strips whitespace.** A
  consumer who wanted a value with leading/trailing spaces (e.g. a
  path with a trailing space, which is bizarre but valid on some
  filesystems) cannot express it. The trade-off is: whitespace in
  config values is overwhelmingly a mistake, not an intent; stripping
  silently is the right default. Documented.
- **`frozen=True` prevents mutation.** A consumer who wants to build
  a config incrementally (construct, mutate, construct) must use
  `model_copy(update=...)` instead of direct assignment. Slightly more
  verbose; documented in `docs/configuration.md`.
- **The five `model_config` flags are repeated on every model.** A
  future refactor could use a shared `_BASE_CONFIG = ConfigDict(...)`
  and `model_config = _BASE_CONFIG` per model, or a common base class
  `class _ForgeQABaseModel(BaseModel)` with the config. The
  repetition is explicit (each model's config is visible) but
  violates DRY. Chosen: explicit repetition, because there are only
  six models and the config is small; refactoring to a base class
  when the count grows is easy and not a breaking change.
- **The `AnyHttpUrl` default is constructed via
  `AnyHttpUrl("http://...")`.** A future Pydantic change to
  `AnyHttpUrl`'s constructor signature would break the
  class-definition. Pydantic's stability promise covers this, but it
  is a dependency on a specific construction pattern. Documented; if
  it breaks, the fix is a one-line change to a `default_factory`.
- **No cross-field validators today.** A future contributor who
  expects "if `headless=False` and `environment='ci'`, warn" will not
  find it. The absence is deliberate (Decision #7); the ADR's
  reconsideration trigger documents that a concrete rule gets a
  validator and a test when the rule becomes real.
- **`docs/configuration.md` must be updated per field change.** A
  future contributor who adds a field without updating the doc
  produces a doc that lags the schema. The test suite does not assert
  doc completeness (that would require parsing the markdown).
  Mitigated by code review; a follow-up could add a
  doc-completeness test.

### Neutral

- `src/forgeqa/config/` is a new package with two files
  (`__init__.py`, `models.py`).
- `tests/unit/config/` is a new package with two files
  (`__init__.py`, `test_models.py`).
- `Makefile` gains one target (`verify-config`).
- `docs/adr/ADR-007-*.md` is added.
- `docs/adr/README.md` is regenerated.
- `docs/configuration.md` is new (~200 lines).
- `docs/engineering-standards.md` gains §5.1.
- `README.md` gains `docs/configuration.md` in the Documentation
  table and `make verify-config` in the Development Commands table.
- No new dependencies. Pydantic is already in
  `[project].dependencies`.

## Reconsideration Trigger

Revisit this decision if any of the following occurs:

- **The project drops Pydantic.** If ForgeQA ever removes Pydantic
  (e.g. to reduce install size for a minimal CLI), the schema must be
  reimplemented in `msgspec` or `attrs` + `cattrs` or hand-written
  validators. The `Literal`, `AnyHttpUrl`, `PositiveInt`, and
  `ConfigDict` features are Pydantic-specific; the replacement must
  provide equivalent strictness. This is not anticipated; Pydantic
  is already a core dependency and its features are a good fit.
- **A concrete cross-field rule emerges.** E.g. "if
  `diagnostics.screenshots=True` but `browser_name` is not set,
  error". The rule gets a `@model_validator(mode="after")` and a test
  in the same PR. The ADR's Decision #7 is amended to document the
  new rule.
- **Phase 1's TOML loader reveals schema gaps.** E.g. if loading a
  real `forgeqa.toml` shows that a field is missing (report file
  names, browser launch options), the schema is extended in the same
  PR as the loader change. The ADR's Decision #2 is amended to add
  the new sub-model or field.
- **The `model_config` repetition becomes a maintenance problem.**
  If the number of models grows past ~10, refactor to a shared base
  class or a `_BASE_CONFIG` constant. The `model_config` flags are
  small and stable; the refactor is not urgent.
- **Pydantic v3 lands.** Pydantic v3 is not on the roadmap at the
  time of writing, but if it lands and changes `ConfigDict`,
  `AnyHttpUrl`, `PositiveInt`, or the `model_config` pattern, the
  schema is migrated in a single PR with the corresponding ADR
  amendment. Pydantic's v1 → v2 migration path is well-documented;
  the v2 → v3 path is expected to be similar.
- **`docs/configuration.md` drifts from the schema.** A
  doc-completeness test (parse the markdown table, assert every
  schema field is documented) could be added. Not implemented today
  because the test would be brittle (the doc has prose, examples,
  and notes, not just the table). If drift becomes a real problem,
  add the test.
- **A field's default changes.** The test suite asserts defaults
  field-by-field; changing a default requires updating the test and
  `docs/configuration.md` in the same PR. This is intentional
  friction.
- **`AnyHttpUrl` becomes too strict or too permissive.** If Pydantic
  changes `AnyHttpUrl`'s accepted set (e.g. starts rejecting
  `http://localhost`), a migration to `HttpUrl` or a custom type is
  needed. Documented in `docs/configuration.md` and tested by
  `test_invalid_base_url_rejected` /
  `test_any_http_url_accepts_https_and_subdomains`.
- **A consumer needs a value with leading/trailing whitespace.**
  Extremely unlikely for a test-framework config, but if it happens,
  set `str_strip_whitespace=False` on the specific model and
  document why.
- **A consumer needs incremental config construction.** If
  `model_copy(update=...)` proves too verbose for a common workflow,
  add a builder or a mutable wrapper in a future PR. Not needed
  today.

## Related

- WBS 1.2.1 — Define the Root Pydantic Configuration Schema (this
  decision)
- WBS 0.4.5 — Configuration Contract (the original requirement for a
  strictly-typed config)
- WBS 1.1.1 — Finalise Package Metadata & License (added
  `pydantic>=2.14.1` to `[project].dependencies`)
- WBS 1.2.2 — TOML config loader (the follow-up that consumes this
  schema; not yet started)
- ADR-006 — Formalise the public API surface and the private-module
  naming convention (`forgeqa.config.__all__` follows the same
  convention)
- `src/forgeqa/config/models.py` — the schema source
- `src/forgeqa/config/__init__.py` — the public re-exports
- `tests/unit/config/test_models.py` — the executable contract
- `docs/configuration.md` — the consumer-facing reference
- `docs/engineering-standards.md` §5.1 "Configuration schema
  conventions" — contributor-facing rules
- Pydantic v2 documentation:
  https://docs.pydantic.dev/latest/
- Pydantic `Literal` types:
  https://docs.pydantic.dev/latest/concepts/types/#literal-types
- Pydantic `AnyHttpUrl`:
  https://docs.pydantic.dev/latest/api/networks/
- Pydantic `PositiveInt`:
  https://docs.pydantic.dev/latest/api/types/#pydantic.types.PositiveInt
- Pydantic `ConfigDict`:
  https://docs.pydantic.dev/latest/api/config/#pydantic.config.ConfigDict
- Pydantic `model_json_schema`:
  https://docs.pydantic.dev/latest/concepts/json_schema/
