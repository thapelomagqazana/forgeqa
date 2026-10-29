# ADR-013: Register ForgeQA as a pytest11 plugin with a central marker manifest

> **Status**: Accepted
> **Date**: 2026-10-29
> **Deciders**: @thapelomagqazana
> **Consulted**: None
> **Informed**: None

## Context

ForgeQA is a test automation framework built on pytest. Until WBS 1.3.1,
a consumer who wrote `@pytest.mark.ui` in their project saw a
`PytestUnknownMarkWarning` — pytest did not know ForgeQA recognized the
marker, because no plugin registered it. The consumer had to either
declare the markers in their own `pyproject.toml` or silence the
warning; both are friction that a well-behaved pytest plugin eliminates.

WBS 1.3.1 requires:

* A `pytest11` entry point so pytest auto-discovers ForgeQA as a
  plugin.
* A `pytest_configure` hook that registers the consumer-facing markers
  (`ui`, `api`, `unit`, `integration`).
* Proof that the plugin loads and the markers are registered — end to
  end, in a real pytest session.

Forces at play:

* **Ubiquity.** A `pytest11` plugin is loaded on **every** pytest
  invocation in **every** project where the plugin's distribution is
  installed — including projects that have no idea what ForgeQA is.
  A bug here does not just break ForgeQA users; it breaks every pytest
  user who happens to have `forgeqa` in their environment. Import-time
  cost, hook-signature compatibility, and robustness are therefore
  much stricter than for a normal library module.
* **Consumer vs. framework.** ForgeQA has two distinct marker sets.
  Its **own test suite** uses `unit`, `integration`, `ui`, `api`,
  `smoke`, `slow` (declared in `[tool.pytest.ini_options].markers`).
  Its **consumers** need `ui`, `api`, `unit`, `integration` (and may
  want `smoke` / `slow`, but those are not framework-provided). The
  two sets overlap but are not the same. A design that conflates
  them — e.g. registering all six via the plugin — imposes ForgeQA's
  internal taxonomy on the consumer.
* **Discoverability.** A consumer must be able to discover what
  markers are available without reading ForgeQA's source. `pytest
  --markers` is the standard discovery mechanism; the markers must
  carry descriptions, not just names.
* **No hidden config dependency.** The plugin must not read the
  consumer's `pyproject.toml`, `pytest.ini`, or `tox.ini` to decide
  what to register. A project with an unusual pytest config must
  still get ForgeQA's markers. Reading config in the plugin would
  couple ForgeQA's marker registration to the consumer's project
  layout, which is not what WBS 1.3.1 is for.
* **Testability.** "The plugin is loaded" is a claim about a
  **subprocess** invoking pytest, not about a module import. A unit
  test can prove the module is importable and the hook works when
  called; only a subprocess test proves discovery.
* **Pre-alpha, no external consumers.** A breaking change (e.g. a
  marker rename) is acceptable. A backward-compatible shim is not
  warranted for a project that has not yet shipped its MVP.

## Decision

1. **Register the plugin via `[project.entry-points.pytest11]`** in
   `pyproject.toml`:

   ```toml
   [project.entry-points.pytest11]
   forgeqa = "forgeqa.pytest_plugin"
   ```

   The value is a dotted module path. The module is importable
   without side effects; see §Decision #3.

2. **The plugin module is `src/forgeqa/pytest_plugin.py`.** It exposes
   exactly `FORGEQA_MARKERS` (a tuple of `(name, description)` pairs)
   and `pytest_configure`. Nothing else is module-level public.

3. **The module imports cheaply.** It imports only the stdlib and
   `pytest` — **not** `forgeqa.config`, **not** Playwright, **not**
   HTTPX. The expensive parts (config schema, adapters) are imported
   inside hook bodies or fixture functions. A regression that hoists
   them to module level is caught by
   `tests/unit/test_plugin_registration.py::test_plugin_module_does_not_import_optional_dependencies`
   (AST-based) and `test_plugin_module_import_is_cheap`
   (time-bounded, 100 ms).

4. **The marker manifest is a single source of truth.**
   `FORGEQA_MARKERS: tuple[tuple[str, str], ...]` is iterated by
   `pytest_configure` and asserted by the unit test. Adding a marker
   is a two-place change (manifest + test), not a three-place one
   (manifest + hook + test) — the hook is a `for` loop, so it cannot
   drift from the manifest.

5. **Only the consumer markers are registered.** `ui`, `api`,
   `unit`, `integration`. `smoke` and `slow` are **not** registered
   by the plugin; a consumer who wants them declares them in their
   own config. See §Alternatives Considered.

6. **The hook is `pytest_configure(config)`.** It reads only
   `config.addinivalue_line`. It does not read `config.option`,
   `config.inicfg`, or `config.getini`. A unit test with a
   strict stand-in proves the read-only-to-one-method property.

7. **The hook is idempotent.** Calling it twice does not raise and
   does not lose markers. It does produce duplicate lines in the
   in-memory list; pytest deduplicates for display and validation.
   The unit test asserts the count, so a future "skip on second call"
   change is caught.

8. **The end-to-end proof is a subprocess test.** `pytest --trace-config`
   (and `pytest --markers`) is invoked in a temporary project directory
   with no `[tool.pytest.ini_options].markers` — the only way to prove
   the marker registration came from the plugin, not from ini config.

## Alternatives Considered

| Alternative | Reason Rejected |
| :--- | :--- |
| Register markers in `[tool.pytest.ini_options].markers` in ForgeQA's `pyproject.toml` | That section configures **ForgeQA's own test suite**, not the consumer's. A consumer installs ForgeQA from PyPI; they do not inherit our `pyproject.toml`. Marker registration for the consumer must happen via the plugin hook. |
| Register markers in a `conftest.py` at the root of the consumer's project | That is the consumer's responsibility, not ours. It also requires the consumer to know which markers ForgeQA recognizes — exactly what the plugin's registration is meant to save them from. |
| Register all six markers (`ui`, `api`, `unit`, `integration`, `smoke`, `slow`) via the plugin | `smoke` and `slow` are ForgeQA's internal test-suite conventions, not consumer concepts. Registering them imposes ForgeQA's taxonomy on the consumer and pollutes `pytest --markers`. A consumer who wants them declares them in their own config (one line); the cost of that is tiny, and it prevents the plugin from claiming marker names that the consumer may want to use for other meanings. |
| Use a `pytest_plugins` list at the top of the plugin module to import sub-plugins | `pytest_plugins` is for third-party plugins that want to declare their sub-plugins. ForgeQA has exactly one plugin module; a `pytest_plugins` list would be one-line indirection for no benefit. |
| Load config at plugin-load time (`pytest_configure` calls `load_config()`) | Reads the consumer's filesystem in every pytest invocation in every project with `forgeqa` installed — a hidden coupling. Config loading belongs in the `settings` fixture (Phase 1), where it is scoped to a ForgeQA-using test. |
| Register fixtures from `pytest_plugin.py` at module level | The fixtures (`browser`, `api_client`, `settings`) need imports of `forgeqa.config` and optional adapters. Importing those at module level would slow down every pytest invocation. They land as a **sub-plugin** (a separate module listed in `pytest_plugins`) or as fixtures defined in a separate file that `pytest_plugin.py` imports *inside* `pytest_configure` — either way, the module-level import stays cheap. See §Reconsideration Trigger. |
| Declare `pytest` as an optional dependency (an "extra") rather than a runtime dependency | ForgeQA is a pytest plugin. A plugin that is not importable without pytest is not usable; the dependency is fundamental, not optional. `pytest>=9.2.0` stays in `[project].dependencies`. |
| Name the entry point `pytest_forgeqa` instead of `forgeqa` | The entry point name is what `pytest --trace-config` and `pytest -p <name>` reference. `forgeqa` is shorter and matches the project name; `pytest_forgeqa` would be conventional but longer. Either works; the shorter name is what `pytest -p forgeqa` uses, which is what a user might type when debugging. |
| Use a class-based plugin (`class ForgeQAPlugin: def pytest_configure(self, config): …`) | A class-based plugin works, but it must be **instantiated** and assigned to a module-level variable for pytest to discover it — more ceremony for a plugin with one hook. Functions at module level are the simplest correct form, and pytest supports them first-class. A future WBS that adds multiple hooks and shared state might prefer a class; that is a local refactor. |
| Test marker registration by inspecting `config.getini("markers")` after calling `pytest_configure` with a real config | Constructing a real `pytest.Config` outside a pytest session is fragile (needs a plugin manager, rootdir, ini parse). A minimal stand-in with `addinivalue_line` is what the plugin actually uses; testing against a real config tests pytest's behavior, not the plugin's. The **subprocess** test exercises the real config. |
| Test plugin discovery by importing the entry point via `importlib.metadata` | That proves the entry point is **declared**, not that pytest **loads** the plugin. A subprocess test is the only way to prove discovery, because discovery happens in pytest's plugin manager, not at metadata-read time. `test_pyproject_declares_pytest11_entry_point` covers the declared-metadata half; the subprocess tests cover the loaded half. |
| Log plugin-load-time info at INFO/DEBUG | A library should not log at import-time or plugin-load-time. The consumer's pytest log may be noisy already, and a plugin that logs "ForgeQA plugin loaded" at INFO in every pytest invocation is spam. Diagnostics come from `pytest --trace-config` and `pytest --markers`, which the user invokes deliberately. |

## Consequences

### Positive

- A consumer who writes `@pytest.mark.ui` after `pip install forgeqa`
  gets a green run with no `PytestUnknownMarkWarning` — the WBS
  acceptance criterion, verified by a subprocess test that turns the
  warning into an error.
- `pytest --markers` lists ForgeQA's markers with descriptions, so
  the consumer's discovery is one command, not a docs read.
- `pytest --trace-config` names `forgeqa.pytest_plugin`, so a
  debugging user can confirm the plugin is loaded without reading
  ForgeQA's source.
- The plugin's import is cheap (~1 ms), so pytest's startup is
  unaffected in the thousands of projects that have `forgeqa`
  installed but don't use it.
- The marker manifest is the single source of truth, so "add a
  marker" is a manifest change plus a test expectation, not a
  scattergun edit.
- The plugin does not read the consumer's config, so marker
  registration is independent of the consumer's project layout.
- The subprocess test proves end-to-end discovery, so a broken entry
  point (a typo in `pyproject.toml`) fails CI on the same commit,
  not on the next user's machine.

### Negative

- **The plugin is loaded in every pytest invocation in every project
  with `forgeqa` installed.** This is inherent to `pytest11`; the
  mitigation is import-time discipline (tested) and hook-time
  discipline (tested). A future contributor who adds a module-level
  `import forgeqa.config` would slow down every pytest invocation
  everywhere — the AST test catches it, but it is worth
  understanding why the rule exists.
- **A bug in the plugin breaks pytest in unrelated projects.** A
  `pytest_configure` that raises at load time makes pytest's startup
  fail for every project with `forgeqa` installed, not just ForgeQA
  users. The blast radius is larger than for a normal module. The
  mitigation is that `pytest_configure` is trivial (a `for` loop over
  a tuple); a future WBS that adds logic must keep it
  exception-safe — a `try`/`except Exception` around the loop with
  a clear error message, not an unhandled raise.
- **The marker set is a compatibility surface.** Once a consumer
  depends on `@pytest.mark.ui` being registered, removing `ui` from
  the manifest is a breaking change for that consumer. Pre-alpha,
  no external consumers — but the tests encode the four markers, so
  a removal is a deliberate, reviewable change.
- **Subprocess tests are slower and can be flaky in unusual
  environments.** They depend on the `pytest` binary being on `PATH`
  and on the parent process's `forgeqa` being the one the subprocess
  imports. In a venv, that is the same `forgeqa`; in a system
  environment where `forgeqa` was installed with `pip install
  --user` and pytest is system-wide, the subprocess may not see
  `forgeqa` — the test fails with a clear message ("the plugin is
  not being discovered") that names the cause.

### Neutral

- `FORGEQA_MARKERS` is a tuple, not a list. Immutability is the
  default; a test that wants to simulate an addition constructs a
  new tuple. This is a small choice that discourages accidental
  mutation in a test.
- The marker descriptions end with a period. This is a copy-paste
  convention, not a requirement; the test enforces it so that the
  `pytest --markers` output reads consistently.
- `pytest_configure` registers markers unconditionally — no "only if
  the user has a ForgeQA test" check. That is correct: a consumer who
  has `forgeqa` installed and writes `@pytest.mark.ui` in a test
  should not see a warning even if their test does not import from
  `forgeqa`.
- The entry point name is `forgeqa`, matching the project name. A
  user debugging with `pytest -p forgeqa` is a one-word command.

## Reconsideration Trigger

- **Phase 1 lands the `settings` / `browser` / `api_client` fixtures.**
  The plugin module will grow a `pytest_plugins` list (or a sub-plugin
  import inside `pytest_configure`) to register them. The module-level
  import-cheapness rule must be preserved: the sub-plugin imports are
  inside `pytest_configure`, not at module level. Re-run the AST test
  after the change; a failure means the fixtures were imported too
  eagerly.
- **A consumer reports a `PytestUnknownMarkWarning` despite having
  `forgeqa` installed.** The first thing to check is whether the
  installed `forgeqa` version predates 1.3.1 (`python -c "import
  importlib.metadata; print(importlib.metadata.version('forgeqa'))"`).
  The second thing is `pytest --trace-config | grep forgeqa`. If
  neither explains it, the entry-point metadata is stale; ask the
  user to `pip install --force-reinstall forgeqa`. If the pattern
  repeats, consider adding a `pytest --help`-visible diagnostic
  (e.g. a `--forgeqa-version` option in `pytest_addoption`) — but
  only if the pattern repeats.
- **Pytest introduces a plugin-loading-time budget** (e.g. a warning
  if a plugin takes > 10 ms to import). ForgeQA's plugin is ~1 ms
  today; the import-cheapness test's 100 ms budget has ~100x
  headroom. If pytest's budget is much tighter, tighten ours to 10 ms
  and add a startup-time benchmark.
- **A consumer asks for `smoke` / `slow` to be registered by the
  plugin.** This is a legitimate request — the current design says
  "declare them yourself". Adding them is a one-line manifest change
  plus test updates. Do it as a minor version bump (`feat(plugin):
  register smoke and slow markers`) and update the docs and this ADR's
  §Alternatives Considered row. Do not add them silently.
- **The entry point name changes.** Renaming `forgeqa` to e.g.
  `forgeqa-plugin` breaks any user who runs `pytest -p forgeqa`.
  Unlikely, but if it happens, the migration note goes in the release
  notes; the entry point name is part of the user-facing surface.

## Related

- WBS 1.3.1 — Register ForgeQA as a Pytest Plugin & Register Markers
  (this decision)
- WBS 1.2.1 — config schema (the plugin does not load config; the
  schema is used by the Phase 1 fixtures that will register via the
  plugin)
- WBS 1.1.1 — `pyproject.toml` (the entry point is added to this file)
- ADR-007 — Pydantic config hierarchy (the schema the future fixtures
  use)
- ADR-012 — error handling and logging (the plugin does not log at
  load time; diagnostics come from pytest's own
  `--trace-config` / `--markers`)
- `src/forgeqa/pytest_plugin.py` — the plugin module
- `tests/unit/test_plugin_registration.py` — the unit test suite
- `tests/integration/plugin/test_plugin_smoke.py` — the subprocess
  ATDD suite
- `docs/plugins.md` — the consumer-facing pytest surface docs
- `docs/engineering-standards.md` §3.4 "Pytest markers and plugin
  registration" — contributor conventions
- Pytest docs, "Writing plugins":
  https://docs.pytest.org/en/stable/how-to/writing_plugins.html
- Pytest docs, "Working with custom markers":
  https://docs.pytest.org/en/stable/how-to/mark.html
- Python packaging, "Entry points":
  https://packaging.python.org/en/latest/specifications/entry-points/
