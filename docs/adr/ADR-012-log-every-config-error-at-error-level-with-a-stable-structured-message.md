# ADR-012: Log every config error at ERROR level with a stable structured message

> **Status**: Accepted
> **Date**: 2026-10-29
> **Deciders**: @thapelomagqazana
> **Consulted**: None
> **Informed**: None

## Context

WBS 1.2.4 established the error formatter: `ForgeQAConfigError` carries a
single-line, human-readable message (`"browser.timeout_ms must be between
1 and 60000, got 0"`). WBS 1.2.6 requires that every configuration error
also be **logged at ERROR level**, and that the exception be *actionable*
— a caller must be able to identify the offending field without
regex-parsing the message.

Two design questions arise:

1. **Where does the log call live?** Options: (a) at the exception
   constructor, (b) at each raise site in the loader, (c) at the catch
   site in the caller. Each has different implications for testability,
   for coverage of the "log every error" invariant, and for whether a
   test that constructs the exception directly sees the log record.
2. **What does "actionable" mean?** Options: (a) nothing — `str(error)`
   only; (b) structured attributes on the exception, but no log extras;
   (c) both — exception attributes *and* log-record extras. The WBS only
   says "logged at ERROR level", but "actionable" suggests more than a
   string.

Forces at play:

- **Testability.** A test that asserts on the log record should not need
  to invoke the full loader (file I/O, env vars, CLI overrides). It
  should be able to construct the exception directly and assert.
- **Coverage.** The "log every error" invariant must hold for *every*
  producer, including a future adapter (JSON config loader, remote
  config loader) that raises the same exception. If the log call lives
  in `loader.py`, a future adapter that forgets to log would silently
  violate the invariant.
- **Non-intrusiveness.** The library must not hijack the application's
  logging configuration. It must emit records, but it must not add
  handlers, must not set levels, and must not touch the root logger.
- **Failure isolation.** If the application's logging subsystem is
  broken (a handler that raises, a formatter that fails), the
  configuration error must still reach the user. The config error is
  the user's problem; the logging failure is the application's.
- **Diagnosability.** A log reader should see *where in the code* the
  error originated (the loader line), not *where in the exception
  class* the log call lives. `stacklevel=2` is the mechanism; it only
  works if the log call is one frame above the raise site.
- **Pre-alpha, no external consumers.** A breaking change (returning
  a tuple from `format_validation_error`) is acceptable; a
  deprecation shim is not warranted.

## Decision

1. **The log call lives in `ForgeQAConfigError.__init__`.** Every
   construction, everywhere, produces one record. A test that
   constructs the exception directly sees the log. A future adapter
   that raises the same class gets the log for free. **Failure
   isolation** wraps the log call in a `try`/`except Exception` that
   does nothing, so a misbehaving handler cannot mask the config
   error.
2. **The level is `logging.ERROR`.** Not WARNING (config failure is
   fatal for the run), not CRITICAL (config failure is recoverable by
   editing the file and re-running). Exposed as
   `forgeqa.config.logging.CONFIG_ERROR_LEVEL` so the level is a
   named constant, not a literal.
3. **The logger name is `"forgeqa.config.errors"`.** A child of the
   subsystem logger `"forgeqa.config"`, so users can configure either
   the whole subsystem or just this module. Exposed as
   `forgeqa.config.logging.PREFIX` so the literal `"forgeqa.config"`
   appears in exactly one place.
4. **The exception carries structured fields** in addition to the
   message: `layer`, `path`, `field`, `value`, `expected`. The message
   stays the human-readable single-line string (WBS 1.2.4 contract);
   the fields are the *stable interface* for a caller that needs to
   programmatically identify the failure. `str(error)` remains the
   fallback for human consumption and for log readers.
5. **The log record carries structured extras** (`forgeqa_layer`,
   `forgeqa_path`, `forgeqa_field`, `forgeqa_value`,
   `forgeqa_expected`). A structured handler can consume these without
   parsing the message. Prefix namespacing with `forgeqa_` avoids
   collision with the application's own `extra=` keys.
6. **`format_validation_error` returns `(message, fields)`.** The
   loader passes both into the exception constructor. This is a
   breaking change for internal callers; there is only one
   (`loader._validate_layer` / `loader.load_config`), updated in the
   same commit.
7. **The library never configures logging.** No handlers, no levels,
   no root-logger touches. A `NullHandler` on the top-level
   `"forgeqa"` logger is scheduled for a Phase 1 WBS (it belongs in a
   top-level module, not in `config/`).

## Alternatives Considered

| Alternative | Reason Rejected |
| :--- | :--- |
| Log at each raise site in `loader.py` | A future adapter that raises `ForgeQAConfigError` from a different module would need to remember to log. The "log every error" invariant is exactly the kind of thing that gets forgotten. Logging at construction is structurally impossible to forget. |
| Log at the catch site in the caller | The caller may suppress the exception (e.g. a CLI that turns it into an exit code). "The error happened" is a fact worth recording regardless of what the caller does with it. Also, a test that wants to assert "the error was logged" would need to invoke the full loader. |
| Return a `str` from `format_validation_error` (as in 1.2.4) and have the loader call it twice — once for the message, once for the fields | Runs the schema lookup twice per error. More importantly, it allows the message and the fields to describe *different* errors if a future refactor changes the "pick the first error" logic in only one of the two calls. The tuple return guarantees they describe the same error. |
| Do not add structured fields; rely on `str(error)` | A caller who wants "which field failed" would have to regex the message. That is brittle across message-format changes (which the WBS reserves the right to make), and it defeats the "actionable" goal. Structured fields are the right interface. |
| Do not add structured extras to the log record; only log the message | A structured-logging handler (JSON) would need to parse the message to extract fields. The `extra=` dict is the standard logging idiom for structured data; skipping it would force downstream applications to reinvent the extraction we already did. |
| Emit at WARNING level | A bad config is fatal for the run: the run cannot start without a valid `ForgeQAConfig`. WARNING implies "you might want to know"; ERROR implies "this operation failed". ERROR is correct. |
| Emit at CRITICAL level | CRITICAL means "the process cannot continue". A bad config is recoverable: the user edits the file and re-runs. CRITICAL would over-signal. |
| Attach a `NullHandler` to `"forgeqa.config"` inside `errors.py` | That would silently suppress config errors if the rest of the framework still logs at WARNING+. A `NullHandler` belongs at the top-level `"forgeqa"` logger in `forgeqa/__init__.py`, so its scope matches its intent. Scheduled for Phase 1. |
| Configure a handler inside the library (e.g. one that writes to `stderr`) | Hijacks the application's logging configuration. Users who already have a handler would see duplicate lines; users who have a specific formatter would see ours instead. The library emits; the application configures. Non-negotiable. |
| Use `logging.getLogger(__name__)` directly in `errors.py` | Works today (the module is at `forgeqa.config.errors`), but a future module inside `forgeqa.config` that re-exports from `errors` might not be at the same depth. The named factory documents the namespace explicitly and makes the prefix greppable. |
| Wrap the log call in `try`/`except Exception` (this ADR's choice) | The alternative — letting a misbehaving handler raise — would turn the config error into an unrelated traceback. "The user's error is masked by the application's logging bug" is exactly the failure mode a config-error subsystem must not have. Isolation is a one-line cost. |
| Do not wrap the log call in `try`/`except` | Breaks the isolation property above. Only acceptable if we are willing to say "the application's logging is the application's problem, and a broken handler is a bug the application must fix before ForgeQA can work". That is a defensible stance, but it makes ForgeQA fragile in environments with a globally broken logger (which do exist), and the cost of isolation is one line. |
| Use a `dataclass` for the extracted fields | `NamedTuple` is lighter, unpackable, and easier to construct in tests. The fields are a value object, not a service; either works, but `NamedTuple` matches the usage (unpacked into `ForgeQAConfigError(...)` as kwargs). |
| Return a `dataclass` with more fields (e.g. a full Pydantic `ErrorDetails` clone) | Over-engineering. The five fields (`layer`, `path`, `field`, `value`, `expected`) are what a UI needs. A future "show all errors" feature will need a different shape entirely (a list of errors, not one), and that is out of scope for 1.2.6. |

## Consequences

### Positive

- **Every** `ForgeQAConfigError`, everywhere, produces exactly one
  ERROR log record. The invariant is structural, not conventional.
- A test that asserts on the log record can construct the exception
  directly, without invoking the loader. Faster and more focused than
  a loader-level test.
- A caller can programmatically identify the failing field via
  `error.field`, the offending value via `error.value`, and the
  constraint via `error.expected`. No regex parsing.
- The message format is stable (WBS 1.2.4 contract preserved), and the
  structured fields are *additional*, not a replacement.
- Structured handlers (JSON) get first-class access to the error's
  shape via the record's `forgeqa_*` extras.
- Failure isolation: a misbehaving application handler cannot mask the
  config error.
- `stacklevel=2` attributes the log record to the loader's line, not to
  the exception's `__init__`. A log reader sees where in *their* code
  the error originated.
- The library still does not configure logging: no handlers, no
  levels, no root touches. The user remains in control.

### Negative

- **Logging at construction is unusual.** A reader who has never seen
  this pattern may be surprised. The docstring explains why, and the
  ADR records the trade-off. Accepted.
- **`format_validation_error`'s signature is a breaking change.**
  Callers that did `msg = format_validation_error(...)` now need
  `msg, fields = format_validation_error(...)`. Only one such caller
  exists (the loader); updated in the same commit. Pre-alpha, no
  external consumers. Acceptable.
- **The log record's `extra` dict is larger** (five extra fields per
  record). Negligible — logging records are already heap-allocated,
  and the fields are small strings.
- **`try`/`except Exception` around the log call** is a bare except
  with a `noqa`. A reader may flag it as a smell. The `noqa: BLE001`
  and the comment explain the intent; the ADR records the rationale.
  The alternative (letting a bad handler mask the config error) is
  worse.
- **Test files that consume `format_validation_error` must unpack the
  tuple.** This surfaced during 1.2.6's verification:
  `test_validation.py` had ten call sites that treated the return
  value as a string; all were updated to `formatted, _ = ...` in the
  same commit. This is a one-time cost; a future consumer of the
  function will see the signature in the docstring and unpack
  correctly.

### Neutral

- `logging.getLogger("forgeqa.config.errors")` is the correct thing for
  a user to configure; the `PREFIX` constant exists to keep the literal
  in one place.
- The `_extract_fields` function duplicates some of the constraint
  logic in `_format_error`. That is intentional (the two serve
  different audiences: one builds a string, one builds a structured
  value) and the shared helpers keep the duplication small.
- `_ErrorFields` is a `NamedTuple` for unpackability; a `dataclass`
  would work equally well.
- The `NullHandler` question is deferred to Phase 1, where the rest of
  the framework's logging lands. Until then, the "no logging
  configuration by the library" rule is the safest default.
- **Pickling loses `__cause__`.** Stdlib pickle does not preserve
  exception causes by default; the structured fields and the message
  survive a round-trip, but the chain does not. Documented in
  `ForgeQAConfigError`'s docstring; a `__reduce__` could fix it if a
  downstream consumer needs it (see Reconsideration Trigger).

## Reconsideration Trigger

- **Phase 1 logging lands.** The top-level `"forgeqa"` logger gets a
  `NullHandler`, and `config/logging.py` may be promoted to
  `forgeqa/logging.py`. Migrate `CONFIG_ERROR_LEVEL` and `PREFIX` with
  it; a rename is a breaking change for users who configure
  `"forgeqa.config"` explicitly, so record it as a migration note.
- **A structured-logging schema is standardised** (Phase 3). Replace
  the ad-hoc `forgeqa_*` extra keys with whatever the framework
  standardises on. The extra keys were chosen to be namespacing-friendly;
  the migration is a find-and-replace in `errors.py` plus a docs update.
- **A consumer requests the full Pydantic `ErrorDetails`** (e.g. for a
  "show all errors" UI). Return a list of `_ErrorFields` from
  `format_validation_error` (a breaking change for the loader, again),
  or add a separate `format_validation_errors` (plural) helper. Do not
  overload the single-error API.
- **A downstream consumer needs `__cause__` preserved across pickle.**
  Add `ForgeQAConfigError.__reduce__` that explicitly pickles the cause
  chain. Pre-alpha: not yet warranted (the structured fields and the
  message are what a worker needs; the cause is for local debugging).
- **A test asserts on `caplog.records`** and breaks when a future
  refactor adds a second log call. If that happens, audit whether the
  second call is intentional; a "one log record per error" invariant
  is what the tests encode, and it is worth preserving.
- **The library is embedded in an environment where logging is
  globally misconfigured** (e.g. an `atexit` handler that closes the
  stream, an application that sets `logging.disable`). If users report
  "config errors are invisible", audit whether the last-resort
  handler is being reached and consider adding a top-level `NullHandler`
  earlier than Phase 1.

## Related

- WBS 1.2.6 — Implement Custom Configuration Error Handling (this decision)
- WBS 1.2.4 — field-level validators and error formatter (predecessor;
  defined the message shape this WBS preserves)
- WBS 1.2.5 — safe defaults (bounds referenced in the examples; see ADR-011)
- ADR-008 — the loader's existence
- ADR-009 — the precedence hierarchy (the loader applies it)
- ADR-010 — the error formatter design (message shape, `extra_forbidden`,
  `value_error` handling; the formatter this WBS extends)
- ADR-011 — safe defaults (bounds `[1, 60_000]` and `[1, 300]`)
- `src/forgeqa/config/logging.py` — the logger factory and level constant
- `src/forgeqa/config/errors.py` — the exception and formatter
- `src/forgeqa/config/loader.py` — the loader that raises the exception
- `tests/unit/config/test_errors.py` — the tests that pin the log shape
- `tests/unit/config/test_validation.py` — the tests that pin the
  message shape (unpacked for the new tuple return)
- `docs/configuration.md` §"Error logging" — user-facing docs
- Python Logging HOWTO, "Configuring logging for a library":
  https://docs.python.org/3/howto/logging.html#configuring-logging-for-a-library
