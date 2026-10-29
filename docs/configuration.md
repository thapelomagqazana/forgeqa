# ForgeQA Configuration Reference

ForgeQA resolves its configuration from four sources: CLI overrides,
environment variables, `forgeqa.toml`, and defaults. This document is
the reference for every field, its type, its default, and its
validation rule, plus how the loader finds, parses, and layers those
sources.

The schema is enforced by `src/forgeqa/config/models.py` (see
[ADR-007](adr/ADR-007-pydantic-config-hierarchy.md) for the design
decision). The loader is `src/forgeqa/config/loader.py` (see
[ADR-008](adr/ADR-008-load-forgeqa-toml-into-forgeqaconfig.md) and
[ADR-009](adr/ADR-009-resolve-configuration-precedence-as-cli-args-environment-variables-forgeqa-toml-defaults.md)
for its design decisions). The error formatter that turns Pydantic's
raw validation error into a single-line, user-facing message is
`src/forgeqa/config/errors.py` (see
[ADR-010](adr/ADR-010-validate-config-fields-with-pydantic-constraints-and-a-human-readable-error-formatter.md)).
The model is a Pydantic v2 hierarchy — invalid values fail at parse
time with a message that names the field, the constraint, and the
offending value; it does not include a Python traceback.

**Status:** the schema (WBS 1.2.1), the loader (WBS 1.2.2), the
precedence hierarchy (WBS 1.2.3), and field-level validation with
formatted errors (WBS 1.2.4) are all implemented. This document
describes the actual behaviour, not a target.

---

## Precedence

ForgeQA resolves configuration from four sources. When the same setting
is present in more than one, the higher-priority source wins:

| Priority | Source | Example |
| :--- | :--- | :--- |
| **1** (highest) | **CLI / Pytest args** | `cli_overrides={"browser": {"headless": False}}` |
| **2** | **Environment variables** | `FORGEQA_BROWSER_HEADLESS=false` |
| **3** | **`forgeqa.toml`** | `[browser] headless = false` |
| **4** (lowest) | **Defaults** | `headless: bool = True` in `BrowserConfig` |

The order is fixed. There is no configuration to change it.

### Why this order?

- **CLI args are the most specific.** A caller who passes
  `cli_overrides={"browser": {"headless": False}}` is explicitly
  asking for `headless=False` for this invocation, no matter what the
  environment or TOML says. The most specific wins.
- **Environment variables are next.** They represent the machine or
  the CI job. `FORGEQA_BROWSER_HEADLESS=false` is a per-machine or
  per-job setting, more specific than `forgeqa.toml` (which is
  per-repository) but less specific than a per-invocation CLI arg.
- **`forgeqa.toml` is next.** It represents the project's
  configuration, checked into the repository.
- **Defaults are the fallback.** A new user who has not configured
  anything gets sensible behaviour.

This matches the [Twelve-Factor App](https://12factor.net/config)
convention and the pattern used by Kubernetes, Terraform, and most
Python test frameworks.

### Worked examples

**A TOML value overrides a default.**

`forgeqa.toml`:
```toml
[browser]
browser_name = "firefox"
```

```python
from forgeqa.config import load_config

cfg = load_config()
assert cfg.browser.browser_name == "firefox"  # TOML, not default "chromium"
```

**An environment variable overrides a TOML value.**

`forgeqa.toml`:
```toml
[browser]
browser_name = "firefox"
```

Environment:
```bash
export FORGEQA_BROWSER_BROWSER_NAME=webkit
```

```python
cfg = load_config()
assert cfg.browser.browser_name == "webkit"  # env, not TOML's "firefox"
```

**A CLI override overrides an environment variable.**

Environment:
```bash
export FORGEQA_BROWSER_BROWSER_NAME=firefox
```

```python
from forgeqa.config import load_config

cfg = load_config(cli_overrides={"browser": {"browser_name": "webkit"}})
assert cfg.browser.browser_name == "webkit"  # CLI, not env's "firefox"
```

**All four layers, one field.**

```python
# default: "chromium", TOML: "firefox", env: "webkit", CLI: "chromium"
# Winner: "chromium" (CLI wins, even though it equals the default).
```

### Per-field precedence

Precedence is applied **per field**, not per layer. A config where
`browser_name` comes from an environment variable and `headless` comes
from `forgeqa.toml` is valid and common — for example, in CI you might
set `FORGEQA_BROWSER_HEADLESS=false` for a debug run while the rest of
the browser config comes from `forgeqa.toml`.

```toml
# forgeqa.toml
[browser]
browser_name = "firefox"  # overridden by env below
headless = true  # overridden by env below
```

```bash
export FORGEQA_BROWSER_HEADLESS=false
```

```python
cfg = load_config(cli_overrides={"browser": {"timeout_ms": 30_000}})
assert cfg.browser.browser_name == "firefox"  # from TOML
assert cfg.browser.headless is False  # from env
assert cfg.browser.timeout_ms == 30_000  # from CLI
```

### Environment variable naming

Every supported environment variable is listed in
`forgeqa.config.ENV_VAR_OVERRIDES`. The naming convention is:

```
FORGEQA_<SECTION>_<FIELD>
```

where `<SECTION>` is the TOML section (`GENERAL`, `BROWSER`, `API`,
`DIAGNOSTICS`, `REPORTING`) and `<FIELD>` is the field name, both
uppercased.

Examples:

| Environment variable | Configures | TOML equivalent |
| :--- | :--- | :--- |
| `FORGEQA_GENERAL_ENVIRONMENT` | `general.environment` | `[general] environment = ...` |
| `FORGEQA_BROWSER_BROWSER_NAME` | `browser.browser_name` | `[browser] browser_name = ...` |
| `FORGEQA_BROWSER_HEADLESS` | `browser.headless` | `[browser] headless = ...` |
| `FORGEQA_BROWSER_TIMEOUT_MS` | `browser.timeout_ms` | `[browser] timeout_ms = ...` |
| `FORGEQA_API_TIMEOUT_SECONDS` | `api.timeout_seconds` | `[api] timeout_seconds = ...` |

Environment variable values are strings; ForgeQA parses them into the
field's type using Pydantic's coercion rules. For example,
`FORGEQA_BROWSER_HEADLESS=false` parses to `False`;
`FORGEQA_BROWSER_TIMEOUT_MS=30000` parses to `30000`. See
["Boolean coercion"](#boolean-coercion) below for the accepted string
forms for `bool`.

**Unknown `FORGEQA_*` variables are silently ignored.** The environment
is shared with other tools; a stray `FORGEQA_*` var (a leftover from a
shell script, a typo in a CI config) does not break the loader. A
*known* var with an invalid value raises `ForgeQAConfigError` naming
the var.

### CLI overrides

`load_config` accepts a `cli_overrides` argument. The shape is a nested
dict matching `ForgeQAConfig`'s constructor:

```python
from forgeqa.config import load_config

cfg = load_config(
    cli_overrides={
        "browser": {"browser_name": "webkit", "headless": False},
        "api": {"timeout_seconds": 30},
    },
)
```

Only the fields present in `cli_overrides` are overridden. Other fields
follow the usual precedence.

**Unknown CLI-override keys are rejected.** A typo like
`{"browsr": {"headless": True}}` raises `ForgeQAConfigError` with a
message naming the offending key. This is the opposite of the env-var
treatment (unknown env vars are ignored) and is deliberate: a CLI
caller is code, and code typos should fail loudly.

### Errors

Each layer reports errors with the layer's identifying information and
a field-level, human-readable description:

- **CLI override errors** name the offending key and the constraint,
  e.g. `"Invalid CLI override: browser.timeout_ms must be between 100
  and 60000, got 50"`.
- **Environment variable errors** name the offending var and the
  constraint, e.g. `"Invalid value in environment variable(s)
  FORGEQA_BROWSER_TIMEOUT_MS: Invalid environment variable:
  browser.timeout_ms must be between 100 and 60000, got 50"`.
- **TOML errors** name the offending file and the constraint, e.g.
  `"Invalid configuration in /path/to/forgeqa.toml:
  browser.timeout_ms must be between 100 and 60000, got 50"`.

An invalid value at a *lower* layer raises even if a *higher* layer
overrides the field. This is intentional: an invalid env var is a bug
in the environment, and silently letting a CLI override "fix" it would
mask the bug. To silence the error, fix or unset the offending value
at its own layer.

### Determinism

Each call to `load_config` re-reads the file and re-reads the
environment. No caching. A test that calls `load_config` twice with the
same inputs gets equal configs; a developer who changes an env var and
calls `load_config` again sees the new value.

---

## Loading configuration

You do not read `forgeqa.toml` yourself, and you do not scan the
environment yourself. You call one function:

```python
from forgeqa.config import load_config

cfg = load_config()
```

That is the whole API. `load_config` searches the current working
directory for `forgeqa.toml`, reads `FORGEQA_*` environment variables,
merges them in the precedence order described above (with any
`cli_overrides` you pass at highest priority), validates the result
against the schema, and returns a fully-defaulted `ForgeQAConfig`. If
no file is present and no env vars are set, it returns the default
config — a fully-usable configuration with sensible defaults.

### Search order

1. If you pass an explicit `path`, that path is used. If the file does
   not exist, `ForgeQAConfigError` is raised (an explicit path is a
   caller's choice; a missing file is a caller's bug, not a reason to
   use defaults).
2. Otherwise, `load_config` searches the current working directory for
   `forgeqa.toml`. If found, it is used.
3. Otherwise, the TOML layer is empty (defaults plus env plus CLI).

The search does not walk up the directory tree. If you want a config
file from a specific directory, pass its path explicitly. (A future
Phase 1 feature may add upward search; it is not in this version.)

### Signature

```python
def load_config(
    path: Path | str | None = None,
    *,
    cli_overrides: Mapping[str, Mapping[str, Any]] | None = None,
    environ: Mapping[str, str] | None = None,
) -> ForgeQAConfig: ...
```

- `path` — an optional explicit config file path. See "Search order".
- `cli_overrides` — a nested dict for CLI-style overrides; highest
  precedence. See "Precedence" §"CLI overrides".
- `environ` — the environment mapping to read `FORGEQA_*` vars from.
  Defaults to `os.environ`. Passing an explicit mapping is useful in
  tests; production callers should omit it.

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
- **Invalid TOML values.** The file parses as TOML but does not
  produce a valid `ForgeQAConfig` (e.g. `browser_name = "safari"`,
  `timeout_ms = 50`, an unknown key). The message includes the file
  path and a **human-readable** field-level description (see
  ["Validation"](#validation) below).
- **Invalid env var values.** A known `FORGEQA_*` var has a value that
  the target field rejects. The message names the environment
  variable and the field-level description.
- **Invalid CLI overrides.** A CLI override has an unknown section or
  field, or a value the target field rejects. The message names the
  offending key and the field-level description.
- **Missing explicit path.** You passed `path=...` and the file does
  not exist.
- **Unreadable file.** The file exists but cannot be read (e.g.
  permission denied, or a non-UTF-8 encoding).

The original exception (`TOMLDecodeError`, `ValidationError`,
`OSError`, or `UnicodeDecodeError`) is preserved as `exc.__cause__`
for debugging. The user-facing message does **not** include Pydantic's
raw traceback or internal type annotations.

### Determinism

Each call to `load_config` reads the file and the environment fresh.
The loader does not cache. Two calls with the same inputs produce equal
configs; two calls after an edit to `forgeqa.toml` or to an env var
produce different configs. (Caching was rejected because staleness is
a worse failure mode than a ~1 ms file read.)

### What is not configurable (yet)

- **Config file path via environment variable** (`FORGEA_CONFIG_PATH`).
  Phase 1 follow-up.
- **Environment overlays** (`FORGEA_ENV=ci` picking
  `forgeqa.ci.toml`). Phase 1 follow-up.
- **Configurable precedence order.** The four-layer order (CLI > env >
  TOML > defaults) is fixed. A future feature to change it would be
  a breaking change.
- **Strict mode for unknown env vars.** Unknown `FORGEQA_*` vars are
  silently ignored (see "Precedence" §"Environment variable naming").
  A future `load_config(strict_env=True)` could raise on them
  instead.
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

Add CLI overrides (highest precedence):

```python
from forgeqa.config import load_config

cfg = load_config(cli_overrides={"browser": {"headless": False}})
```

Read `FORGEQA_*` env vars from a specific mapping (useful in tests):

```python
from forgeqa.config import load_config

cfg = load_config(environ={"FORGEQA_BROWSER_BROWSER_NAME": "firefox"})
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
| `artifacts_dir` | `str` (min length 1) | `"artifacts"` | Directory where ForgeQA writes diagnostic artifacts. Relative to the working directory unless absolute. Created on first write. The validator checks that the path *can* be created (nearest existing ancestor is writable) but does not create it. See ["Field-level constraints"](#field-level-constraints). |
| `log_level` | `Literal["DEBUG", "INFO", "WARNING", "ERROR"]` | `"INFO"` | The framework's log level. Applied to the `forgeqa` logger, not the root logger. `"TRACE"` and `"CRITICAL"` are not accepted — see ["Why not `CRITICAL`?"](#why-not-critical) below. |

### `[browser]`

Only meaningful when `forgeqa[ui]` is installed. The model itself does
not import Playwright; the model is constructible even in a core install.

| Field | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| `browser_name` | `Literal["chromium", "firefox", "webkit"]` | `"chromium"` | The browser engine. Adding a new engine requires a corresponding ForgeQA adapter update; it is not a user-configurable choice. |
| `headless` | `bool` | `true` | Whether to run headless. `false` opens a real browser window for debugging. |
| `base_url` | `AnyHttpUrl` | `http://localhost:8000` | Base URL for relative navigation. Must be an `http` or `https` URL with a valid host. |
| `timeout_ms` | `int`, must be between 100 and 60000 (inclusive) | `10_000` | Default navigation and action timeout, in milliseconds. See ["Field-level constraints"](#field-level-constraints). |

### `[api]`

Only meaningful when `forgeqa[api]` is installed.

| Field | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| `base_url` | `AnyHttpUrl` | `http://localhost:8000/api` | Base URL for API requests. Must be an `http` or `https` URL. |
| `timeout_seconds` | `int`, must be between 1 and 300 (inclusive) | `10` | Default request timeout, in seconds. See ["Field-level constraints"](#field-level-constraints). |

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

ForgeQA validates configuration values as they are loaded. Invalid
values fail with a **single-line, human-readable error** that names
the field, the constraint, and the offending value — no Pydantic
traceback.

### Error message shape

All validation errors have one of three forms, depending on which
layer produced the value:

```
Invalid configuration in /path/to/forgeqa.toml: <section>.<field> <constraint>, got <value>
Invalid value in environment variable(s) <VAR>: Invalid environment variable: <section>.<field> <constraint>, got <value>
Invalid CLI override: <section>.<field> <constraint>, got <value>
```

The `<constraint>` is one of:

- `must be between <lower> and <upper>` — for fields with two-sided
  bounds (`timeout_ms`, `timeout_seconds`).
- `must be at least <lower>` / `must be at most <upper>` — for
  fields with a one-sided bound (none today; the fallback for a
  future field that declares only one side).
- `must be one of: <option1>, <option2>, ...` — for `Literal`
  fields (`browser_name`, `log_level`).
- `must be a creatable directory: <specific reason>` — for
  `artifacts_dir`.
- `unexpected field: <name>` — for unknown keys.
- (fallback) Pydantic's own message, which is already human-readable.

If more than one field is invalid, the message names the first and
appends `" (and N more)"`. Fix the first error and re-run to see the
next.

### Examples

```
$ # Invalid browser
$ python -c "from forgeqa.config import BrowserConfig; BrowserConfig(browser_name='safari')" 2>&1 | head -2
ForgeQAConfigError: ... browser.browser_name must be one of: 'chromium', 'firefox' or 'webkit'; got 'safari'
```

```
$ # Invalid timeout (below range)
$ python -c "from forgeqa.config import BrowserConfig; BrowserConfig(timeout_ms=50)" 2>&1 | head -2
ForgeQAConfigError: ... browser.timeout_ms must be between 100 and 60000, got 50
```

```
$ # Invalid timeout (above range)
$ python -c "from forgeqa.config import BrowserConfig; BrowserConfig(timeout_ms=60_001)" 2>&1 | head -2
ForgeQAConfigError: ... browser.timeout_ms must be between 100 and 60000, got 60001
```

```
$ # Invalid artifacts_dir (points at a file)
$ python -c "from forgeqa.config import GeneralConfig; GeneralConfig(artifacts_dir='/etc/hosts')" 2>&1 | head -2
ForgeQAConfigError: ... general.artifacts_dir must be a creatable directory: artifacts_dir points at an existing file, not a directory: /etc/hosts
```

```
$ # Unknown key (typo)
$ python -c "from forgeqa.config import BrowserConfig; BrowserConfig(timout_ms=10000)" 2>&1 | head -2
ForgeQAConfigError: ... browser.timout_ms unexpected field: timout_ms
```

When these errors occur during `load_config` (i.e. from a real
`forgeqa.toml` file), they are wrapped in `ForgeQAConfigError` with the
file path prepended — see [Loading configuration](#loading-configuration)
above. An invalid env var or CLI override is likewise wrapped, with the
env var name or CLI key in the message.

The full set of validation rules is tested by
`tests/unit/config/test_models.py` (acceptance: "is this value
valid?") and `tests/unit/config/test_validation.py` (message shape:
"what does the user see when it is not?").

### No tracebacks

The error message is a single line. It does **not** include:

- `pydantic_core._pydantic_core.ValidationError:` — the raw
  Pydantic exception name.
- `[type=..., input_value=..., input_type=...]` — Pydantic's internal
  type annotations.
- A Python traceback.

The underlying `pydantic.ValidationError` is preserved as
`exc.__cause__` for debugging, so a tool that wants the structured
form can still access it. The user-facing message is the actionable
part.

### What "clear error" means in practice

A clear error:

1. **Names the field, with its section.** `browser.timeout_ms`, not
   just `timeout_ms`. This matters when the same field name exists in
   multiple sections.
2. **Names the valid range or options.** `"between 100 and 60000"`,
   `"one of: 'chromium', 'firefox' or 'webkit'"`. The user does not
   have to grep the source to find the bound or the valid values.
3. **Names the offending value.** `"got 50"`, `"got 'safari'"`. The
   user can compare against the range without opening the file.
4. **Is one line.** No multi-line traceback, no internal annotations.
5. **Is actionable.** The user knows what to change after reading the
   error.

If an error does not meet these criteria, it is a bug — open an issue
at <https://github.com/thapelomagqazana/forgeqa/issues>.

### Field-level constraints

The following fields have explicit constraints beyond their type:

| Field | Constraint | Message on violation |
| :--- | :--- | :--- |
| `browser.browser_name` | One of `"chromium"`, `"firefox"`, `"webkit"`. | `must be one of: 'chromium', 'firefox' or 'webkit'` |
| `browser.timeout_ms` | Integer between `100` and `60000` (inclusive). | `must be between 100 and 60000, got <value>` |
| `api.timeout_seconds` | Integer between `1` and `300` (inclusive). | `must be between 1 and 300, got <value>` |
| `general.artifacts_dir` | Creatable: if the path exists, it must be a directory; if not, the nearest existing ancestor must be a writable directory. The validator does **not** create the directory — it is created on first write. | `must be a creatable directory: <specific reason>` (e.g. `parent is not writable: /path`, `points at an existing file, not a directory: /path`) |
| `general.log_level` | One of `"DEBUG"`, `"INFO"`, `"WARNING"`, `"ERROR"`. | `must be one of: 'DEBUG', 'INFO', 'WARNING' or 'ERROR'` |
| `browser.base_url`, `api.base_url` | A valid `http` or `https` URL. | `Input should be a valid URL` (Pydantic's fallback) |
| `general.environment`, `general.artifacts_dir` | Non-empty string (`min_length=1`). | `must be at least 1 characters` (Pydantic's one-sided fallback) |
| `diagnostics.screenshots`, `diagnostics.traces`, `diagnostics.console_logs`, `reporting.junit_xml`, `reporting.json_report` | A boolean. Pydantic accepts the usual string forms (`"true"/"false"`, `"yes"/"no"`, `"on"/"off"`, `"1"/"0"`, case-insensitive); ambiguous strings like `"maybe"` are rejected. | Pydantic's `Input should be a valid boolean` |

The full set of validation rules is tested by
`tests/unit/config/test_models.py` and `tests/unit/config/test_validation.py`.

### Boolean coercion

Pydantic v2 accepts a fixed set of string forms for `bool` fields,
matching Pydantic v1's set: `"true"/"false"`, `"yes"/"no"`,
`"on"/"off"`, and `"1"/"0"` (case-insensitive). All of these parse to
the corresponding boolean:

```toml
[browser]
headless = "yes"   # parses to True
headless = "no"    # parses to False
```

Ambiguous strings like `"maybe"` fail at parse time with a clear
error. The natural unquoted form is also accepted (and is what
`docs/configuration.md`'s example uses):

```toml
[browser]
headless = true
```

If a future release adopts `strict=True` on boolean fields (see
ADR-007's reconsideration trigger), only the quoted string forms
would be rejected; the unquoted form would continue to work. That
change would be a minor breaking change and would be documented in
the release notes.

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

> **Note on `model_copy` and nested models.** When using
> `model_copy(update=...)` on `ForgeQAConfig`, the `update` value for a
> sub-model field must be a **model instance** (e.g.
> `BrowserConfig(...)`), not a **dict**. Passing a dict sets the
> attribute to the dict itself, breaking `cfg.browser.<attr>` access.
> This is a Pydantic v2 behaviour; the loader takes a different
> approach (constructs the merged model) to avoid it. See ADR-009's
> Alternatives table.

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

## Schema, loader, precedence, and validation are separate concerns

The configuration is split across four modules with distinct
responsibilities:

- **The schema** (`src/forgeqa/config/models.py`, ADR-007) defines
  what a valid config looks like. It is enforced by Pydantic v2 and
  tested by `tests/unit/config/test_models.py`. It runs in ~50 ms and
  does not read any files or environment.
- **The loader** (`src/forgeqa/config/loader.py`, ADR-008) reads
  `forgeqa.toml`, parses it with `tomllib`, and constructs a
  `ForgeQAConfig`. Tested by `tests/unit/config/test_loader.py`.
- **The precedence layer** (`src/forgeqa/config/env.py` and the
  precedence logic in `loader.py`, ADR-009) reads `FORGEQA_*` env
  vars, applies CLI overrides, and validates each layer in isolation
  before merging. Tested by `tests/unit/config/test_precedence.py`.
- **The error formatter** (`src/forgeqa/config/errors.py`, ADR-010)
  turns Pydantic's raw `ValidationError` into the single-line,
  human-readable message documented in ["Validation"](#validation).
  Tested by `tests/unit/config/test_validation.py`.

Splitting them means a schema change is testable without I/O, a loader
change is testable without re-testing the schema, the precedence change
is testable without re-testing either, and the message formatter is
testable without going through the loader. It also means a consumer
who wants to construct a config in Python (e.g. in a test fixture) can
do so without touching a file or the environment:

```python
from forgeqa.config import BrowserConfig, ForgeQAConfig

# No file involved. This is a valid, fully-typed config.
cfg = ForgeQAConfig(browser=BrowserConfig(browser_name="firefox"))
```

A consumer who wants to load from a file (and/or env) uses
`load_config`:

```python
from forgeqa.config import load_config

# Reads forgeqa.toml from cwd and FORGEQA_* env vars, or returns
# defaults if neither is present.
cfg = load_config()
```

Both paths produce the same `ForgeQAConfig` type. The loader is a
convenience for the common case; constructing from Python is the
power-user path.

---

## See also

- [`docs/engineering-standards.md`](engineering-standards.md) §5.1 —
  contributor-facing Pydantic conventions (including message
  formatting).
- [`docs/engineering-standards.md`](engineering-standards.md) §5.2 —
  contributor-facing loader and precedence conventions.
- [`docs/adr/ADR-007`](adr/ADR-007-pydantic-config-hierarchy.md) —
  the schema design decision.
- [`docs/adr/ADR-008`](adr/ADR-008-load-forgeqa-toml-into-forgeqaconfig.md) —
  the loader design decision.
- [`docs/adr/ADR-009`](adr/ADR-009-resolve-configuration-precedence-as-cli-args-environment-variables-forgeqa-toml-defaults.md) —
  the precedence design decision.
- [`docs/adr/ADR-010`](adr/ADR-010-validate-config-fields-with-pydantic-constraints-and-a-human-readable-error-formatter.md) —
  the field-validation and error-formatter design decision.
- [`docs/public-api.md`](public-api.md) — the package's public API
  contract.
- `tests/unit/config/test_models.py` — the schema's executable
  contract (acceptance: "is this value valid?").
- `tests/unit/config/test_loader.py` — the loader's executable
  contract.
- `tests/unit/config/test_precedence.py` — the precedence's
  executable contract.
- `tests/unit/config/test_validation.py` — the message shape's
  executable contract ("what does the user see when it is not?").
- `src/forgeqa/config/models.py` — the schema source.
- `src/forgeqa/config/loader.py` — the loader and precedence source.
- `src/forgeqa/config/env.py` — the env-var mapping source.
- `src/forgeqa/config/errors.py` — the error formatter source.
