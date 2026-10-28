# ForgeQA Configuration Reference

ForgeQA reads a single TOML file, `forgeqa.toml`, from the working
directory. This document is the reference for every field, its type,
its default, and its validation rule, plus how the loader finds and
parses the file.

The schema is enforced by `src/forgeqa/config/models.py` (see
[ADR-007](adr/ADR-007-pydantic-config-hierarchy.md) for the design
decision). The loader is `src/forgeqa/config/loader.py` (see
[ADR-008](adr/ADR-008-load-forgeqa-toml-into-forgeqaconfig.md) for its
design decision). The model is a Pydantic v2 hierarchy — invalid values
fail at parse time with a message that names the field and (for
`Literal` fields) lists the valid values.

**Status:** both the schema (WBS 1.2.1) and the loader (WBS 1.2.2) are
implemented. This document describes the actual behaviour, not a
target.

---

## Loading configuration

You do not read `forgeqa.toml` yourself. You call one function:

```python
from forgeqa.config import load_config

cfg = load_config()
```

That is the whole API. `load_config` searches the current working
directory for `forgeqa.toml`, parses it, validates it against the
schema, and returns a fully-defaulted `ForgeQAConfig`. If no file is
present, it returns the default config — a fully-usable configuration
with sensible defaults.

### Search order

1. If you pass an explicit `path`, that path is used. If the file does
   not exist, `ForgeQAConfigError` is raised (an explicit path is a
   caller's choice; a missing file is a caller's bug, not a reason to
   use defaults).
2. Otherwise, `load_config` searches the current working directory for
   `forgeqa.toml`. If found, it is used.
3. Otherwise, the default config is returned.

The search does not walk up the directory tree. If you want a config
file from a specific directory, pass its path explicitly. (A future
Phase 1 feature may add upward search; it is not in this version.)

### Errors

All load failures raise `ForgeQAConfigError`:

```python
from forgeqa.config import ForgeQAConfigError, load_config

try:
    cfg = load_config()
except ForgeQAConfigError as exc:
    print(f"Configuration error: {exc}")
    # exc.path is the file that failed, if a file was involved.
    raise
```

`ForgeQAConfigError` covers:

- **Malformed TOML.** The file exists but is not valid TOML. The
  message includes the file path and (when `tomllib` provides it) the
  line and column.
- **Invalid values.** The file parses as TOML but does not produce a
  valid `ForgeQAConfig` (e.g. `browser_name = "safari"`,
  `timeout_ms = -1`, an unknown key). The message includes the file
  path and the field-level error from Pydantic.
- **Missing explicit path.** You passed `path=...` and the file does
  not exist.
- **Unreadable file.** The file exists but cannot be read (e.g.
  permission denied).

The original exception (`TOMLDecodeError`, `ValidationError`,
`OSError`, or `UnicodeDecodeError`) is preserved as `exc.__cause__`
for debugging.

### Determinism

Each call to `load_config` reads the file fresh. The loader does not
cache. Two calls on the same file produce equal configs; two calls on
a file that was edited in between produce different configs. A
developer who edits `forgeqa.toml` and calls `load_config` again sees
the new values. (Caching was rejected because staleness is a worse
failure mode than a ~1 ms file read.)

### What is not configurable (yet)

- **Config file path via environment variable** (`FORGEA_CONFIG_PATH`).
  Phase 1 follow-up.
- **Environment overlays** (`FORGEA_ENV=ci` picking
  `forgeqa.ci.toml`). Phase 1 follow-up.
- **Per-field environment overrides** (`FORGEA_BROWSER_HEADLESS=false`).
  Phase 1 follow-up.
- **Upward directory search.** Phase 1 follow-up.
- **Multiple config files merged.** Phase 1 follow-up.

Each of these is additive: they will add new functions or extend
`load_config` with new arguments, not change its current signature.

### Examples

Load from the current directory (or defaults if no file is present):

```python
from forgeqa.config import load_config

cfg = load_config()
```

Load from an explicit path:

```python
from pathlib import Path
from forgeqa.config import load_config

cfg = load_config(Path("configs/ci.toml"))
```

Find the config file without loading it:

```python
from forgeqa.config import find_config_path

path = find_config_path()  # absolute Path, or None
if path is not None:
    print(f"Config file found at: {path}")
else:
    print("No config file; defaults will be used")
```

Handle an error:

```python
from forgeqa.config import ForgeQAConfigError, load_config

try:
    cfg = load_config()
except ForgeQAConfigError as exc:
    print(f"Could not load configuration: {exc}")
    raise SystemExit(1)
```

---

## Example

```toml
[general]
environment = "ci"
artifacts_dir = "/tmp/forgeqa-artifacts"
log_level = "DEBUG"

[browser]
browser_name = "chromium"
headless = true
base_url = "http://localhost:8000"
timeout_ms = 10_000

[api]
base_url = "http://localhost:8000/api"
timeout_seconds = 10

[diagnostics]
screenshots = true
traces = true
console_logs = true

[reporting]
junit_xml = true
json_report = true
```

Every field is optional. `ForgeQAConfig()` (no file, no arguments)
produces the same object as the example with all defaults. A
`forgeqa.toml` file that omits a section gets that section's defaults;
a file that specifies one field in a section gets the other fields'
defaults.

---

## Sections

### `[general]`

| Field | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| `environment` | `str` (min length 1) | `"local"` | The environment label: `"local"`, `"ci"`, `"staging"`, `"production"`, or anything else. Used for environment overlays (Phase 1) and artifact tagging (Phase 3). |
| `artifacts_dir` | `str` (min length 1) | `"artifacts"` | Directory where ForgeQA writes diagnostic artifacts. Relative to the working directory unless absolute. Created on first write; never deleted automatically. |
| `log_level` | `Literal["DEBUG", "INFO", "WARNING", "ERROR"]` | `"INFO"` | The framework's log level. Applied to the `forgeqa` logger, not the root logger. `"TRACE"` and `"CRITICAL"` are not accepted — see ["Why not `CRITICAL`?"](#why-not-critical) below. |

### `[browser]`

Only meaningful when `forgeqa[ui]` is installed. The model itself does
not import Playwright; the model is constructible even in a core install.

| Field | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| `browser_name` | `Literal["chromium", "firefox", "webkit"]` | `"chromium"` | The browser engine. Adding a new engine requires a corresponding ForgeQA adapter update; it is not a user-configurable choice. |
| `headless` | `bool` | `true` | Whether to run headless. `false` opens a real browser window for debugging. |
| `base_url` | `AnyHttpUrl` | `http://localhost:8000` | Base URL for relative navigation. Must be an `http` or `https` URL with a valid host. |
| `timeout_ms` | `PositiveInt` | `10_000` | Default navigation and action timeout, in milliseconds. Must be strictly positive. |

### `[api]`

Only meaningful when `forgeqa[api]` is installed.

| Field | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| `base_url` | `AnyHttpUrl` | `http://localhost:8000/api` | Base URL for API requests. Must be an `http` or `https` URL. |
| `timeout_seconds` | `PositiveInt` | `10` | Default request timeout, in seconds. Must be strictly positive. |

### `[diagnostics]`

Controls *capture*. The counterpart is `[reporting]`, which controls
*emission*.

| Field | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| `screenshots` | `bool` | `true` | Capture a screenshot on UI test failure. Requires `forgeqa[ui]`. |
| `traces` | `bool` | `true` | Capture a Playwright trace on UI test failure. Larger than a screenshot (a few MB), but contains the full interaction log. Requires `forgeqa[ui]`. |
| `console_logs` | `bool` | `true` | Capture browser console logs for UI tests. Requires `forgeqa[ui]`. |

Capture is enabled by default because a test framework whose default
is "capture nothing" provides no evidence when a test fails in CI.

### `[reporting]`

Controls *emission*. The counterpart is `[diagnostics]`, which controls
*capture*.

| Field | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| `junit_xml` | `bool` | `true` | Write a JUnit XML report to `<artifacts_dir>/junit.xml`. |
| `json_report` | `bool` | `true` | Write a structured JSON report to `<artifacts_dir>/results.json`. |

---

## Validation

The schema is enforced by Pydantic v2. Invalid values fail at parse
time with a message that names the field. Examples:

```
$ # Invalid browser
$ python -c "from forgeqa.config import BrowserConfig; BrowserConfig(browser_name='safari')"
pydantic_core._pydantic_core.ValidationError: 1 validation error for BrowserConfig
browser_name
  Input should be 'chromium', 'firefox' or 'webkit' [type=literal_error, input_value='safari', input_type=str]
```

```
$ # Invalid timeout
$ python -c "from forgeqa.config import BrowserConfig; BrowserConfig(timeout_ms=-1)"
pydantic_core._pydantic_core.ValidationError: 1 validation error for BrowserConfig
timeout_ms
  Input should be greater than 0 [type=greater_than, input_value=-1, input_type=int]
```

```
$ # Unknown key (typo)
$ python -c "from forgeqa.config import BrowserConfig; BrowserConfig(timout_ms=10000)"
pydantic_core._pydantic_core.ValidationError: 1 validation error for BrowserConfig
timout_ms
  Extra inputs are not permitted [type=extra_forbidden, input_value=10000, input_type=int]
```

When these errors occur during `load_config` (i.e. from a real
`forgeqa.toml` file), they are wrapped in `ForgeQAConfigError` with the
file path prepended — see [Loading configuration](#loading-configuration)
above.

The full set of validation rules is tested by
`tests/unit/config/test_models.py` (see the "Negative cases" section
there).

### What "clear error" means in practice

A clear error:

1. **Names the field.** The `loc` in the error points at the offending
   field, including the parent path if the field is nested
   (`("browser", "browser_name")`, not just `("browser_name",)`).
2. **Names the valid values** (for `Literal` fields). The message lists
   `'chromium', 'firefox' or 'webkit'`; the user does not have to grep
   the source to find them.
3. **Names the constraint** (for constrained fields). `"Input should
   be greater than 0"` is the constraint, not a generic "invalid
   input".
4. **Is actionable.** The user knows what to change after reading the
   error, without opening a doc.

If an error does not meet these criteria, it is a bug — open an issue
at <https://github.com/thapelomagqazana/forgeqa/issues>.

---

## Why these defaults?

The defaults are chosen so that `ForgeQAConfig()` (no config file, no
arguments) is a *useful* configuration, not just a valid one:

- **`environment = "local"`** — the safest default; a user who never
  sets it gets the "I'm on my machine" behaviour.
- **`artifacts_dir = "artifacts"`** — the conventional name; a
  `pytest` run produces `artifacts/` next to the test file, the same
  way `pytest` produces `.pytest_cache/`.
- **`log_level = "INFO"`** — the most useful level for a test
  framework. `DEBUG` is too noisy for a normal run; `WARNING` hides
  the "test started" / "test passed" lines that a user often wants to
  see.
- **`headless = true`** — the default for CI and local automation;
  `false` is opt-in for debugging.
- **`timeout_ms = 10_000`** — Playwright's default is 30 000; ForgeQA
  uses 10 000 to fail faster in CI. A test that takes >10 s to
  navigate is usually a test that will be flaky in CI anyway.
- **`timeout_seconds = 10`** — HTTPX's default is 5 s; 10 s
  accommodates slow test environments without hiding a hung API.
- **All `[diagnostics]` fields `true`** — evidence-first. A test
  framework that captures nothing on failure provides no evidence.
- **All `[reporting]` fields `true`** — JUnit XML is CI-native;
  structured JSON is durable.
- **`browser_name = "chromium"`** — the most common Playwright engine
  in CI, with the widest CI-runner support.

Changing a default is a semver-minor event (it changes install
behaviour for consumers who rely on the default). It is documented in
the release notes and in this section.

---

## Why not `CRITICAL`?

Python's `logging` has a `CRITICAL` level, but ForgeQA excludes it from
`log_level` for two reasons:

1. **A CRITICAL log line in a test-runner context is a framework bug,
   not a test result.** The runner emitting CRITICAL means the runner
   itself is broken — not the test, not the application. Users cannot
   meaningfully "configure" CRITICAL; it either happens (and should be
   fixed) or it doesn't.
2. **CI systems and log aggregators treat CRITICAL as page-worthy.**
   A test framework's config should not have a page-worthy log level
   baked into a config value; the CI system's own thresholds should
   decide what pages.

If a ForgeQA bug ever needs to emit CRITICAL, it does so
unconditionally and ignores `log_level` — which is the correct
behaviour for a bug. A user cannot opt out of a CRITICAL framework
error by setting `log_level = "ERROR"`.

---

## Why not `TRACE`?

`TRACE` is not a Python `logging` level. Some third-party logging
libraries (e.g. `loguru`) provide one; Python's stdlib does not. ForgeQA
uses the stdlib `logging` module (a future decision may change this;
see ADR-007's reconsideration trigger). Until then, `DEBUG` is the
most verbose level available, and it is what `TRACE` would map to in
any case.

A user coming from `loguru` who writes `log_level = "TRACE"` gets a
clear error listing the valid values; the fix is `log_level = "DEBUG"`.

---

## What is not configurable (yet)

The following are intentionally fixed in code for now. Making them
configurable is Phase 2+ work:

- **Artifact file names.** `junit.xml` and `results.json` are fixed.
- **Report directory layout.** The `<artifacts_dir>/tests/<test-id>/`
  layout is fixed.
- **Retention policy.** Artifacts are never deleted automatically.
- **Browser launch options** beyond `headless` (e.g. viewport size,
  user agent, proxy). These will land in Phase 5 alongside flakiness
  controls.
- **API client options** beyond `base_url` and `timeout_seconds`
  (e.g. default headers, retry policy). These will land in Phase 4
  alongside CI/CD execution controls.

If you need one of these today, open an issue — either it should be
added to the schema (a documented, versioned change) or there is a
workaround we should document.

---

## Frozen configuration

`ForgeQAConfig` and its sub-models are immutable. Once constructed, a
field cannot be assigned:

```python
>>> from forgeqa.config import ForgeQAConfig
>>> cfg = ForgeQAConfig()
>>> cfg.general.environment = "production"
Traceback (most recent call last):
  ...
pydantic_core._pydantic_core.ValidationError: 1 validation error for GeneralConfig
environment
  Instance is frozen [type=frozen_instance, input_value='production', input_type=str]
```

To "modify" a config, use `model_copy(update=...)` to construct a new
object:

```python
>>> from forgeqa.config import ForgeQAConfig
>>> cfg = ForgeQAConfig()
>>> new_cfg = cfg.model_copy(
...     update={"general": cfg.general.model_copy(update={"environment": "production"})}
... )
>>> new_cfg.general.environment
'production'
>>> cfg.general.environment  # original is unchanged
'local'
```

The verbosity is deliberate: a config object is a value, not a mutable
bag of settings. Passing it to a fixture, a test, a reporter, and a CI
script means all four see the same value; no consumer can accidentally
mutate it. The `model_copy(update=...)` ceremony is the price.

---

## Whitespace stripping

String values are stripped of leading and trailing whitespace:

```toml
[general]
environment = "  ci  "
```

parses as `environment == "ci"`. This prevents a class of "why doesn't
my URL work" bugs from hand-edited TOML. It also means a value that
*intentionally* starts or ends with whitespace (e.g. a filesystem path
with a trailing space, which is bizarre but valid on some filesystems)
cannot be expressed. The trade-off is: whitespace in config values is
overwhelmingly a mistake, not an intent.

---

## `http` vs. `https`

`base_url` accepts both `http` and `https` URLs. HTTPS is recommended
for anything outside `localhost`, but tests commonly target
`http://localhost:8000` (a local dev server) and
`http://test-service.internal` (a service on a private network).
Forbidding `http` would force every test to either use HTTPS or bypass
validation, which is not a good trade.

An invalid URL (`"not-a-url"`, `"http://"`, `"ftp://example.com"`, `""`)
fails at parse time. The `AnyHttpUrl` type rejects anything without a
valid scheme and host.

---

## The fallback `"0.0.0+unknown"` version

`forgeqa.__version__` is `"0.0.0+unknown"` when the package is not
installed (a source checkout without `pip install -e .`). This is *not*
a configuration value — it is reported by `forgeqa.get_version()` and
is documented in
[`docs/public-api.md`](public-api.md#the-000unknown-fallback). It is
mentioned here because a user reading a report that says
`"0.0.0+unknown"` will reasonably ask "why?". The answer is in the
public-api doc.

---

## Schema and loader are separate concerns

The schema and the loader are two modules with distinct responsibilities:

- **The schema** (`src/forgeqa/config/models.py`, ADR-007) defines what
  a valid config looks like. It is enforced by Pydantic v2 and tested
  by `tests/unit/config/test_models.py`. It runs in ~50 ms and does
  not read any files.
- **The loader** (`src/forgeqa/config/loader.py`, ADR-008) reads
  `forgeqa.toml`, parses it with `tomllib`, and constructs a
  `ForgeQAConfig`. Tested by `tests/unit/config/test_loader.py`.

Splitting them means a schema change is testable without I/O, and a
loader change is testable without re-testing the schema. It also means
a consumer who wants to construct a config in Python (e.g. in a test
fixture) can do so without touching a file:

```python
from forgeqa.config import BrowserConfig, ForgeQAConfig

# No file involved. This is a valid, fully-typed config.
cfg = ForgeQAConfig(browser=BrowserConfig(browser_name="firefox"))
```

A consumer who wants to load from a file uses `load_config`:

```python
from forgeqa.config import load_config

# Reads forgeqa.toml from cwd (or returns defaults if absent).
cfg = load_config()
```

Both paths produce the same `ForgeQAConfig` type. The loader is a
convenience for the common case; constructing from Python is the
power-user path.

---

## See also

- [`docs/engineering-standards.md`](engineering-standards.md) §5.1 —
  contributor-facing Pydantic and loader conventions.
- [`docs/adr/ADR-007`](adr/ADR-007-pydantic-config-hierarchy.md) —
  the schema design decision.
- [`docs/adr/ADR-008`](adr/ADR-008-load-forgeqa-toml-into-forgeqaconfig.md) —
  the loader design decision.
- [`docs/public-api.md`](public-api.md) — the package's public API
  contract.
- `tests/unit/config/test_models.py` — the schema's executable
  contract.
- `tests/unit/config/test_loader.py` — the loader's executable
  contract.
- `src/forgeqa/config/models.py` — the schema source.
- `src/forgeqa/config/loader.py` — the loader source.
