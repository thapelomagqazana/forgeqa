# ForgeQA's pytest surface

ForgeQA is a **pytest plugin**. Installing `forgeqa` in the same
environment as `pytest` registers the plugin via the `pytest11` entry
point; pytest auto-discovers it on the next run — no `-p` flag needed.

This document is the reference for:

- what the plugin does at load time,
- which markers it registers (and which it does **not**),
- how to verify the plugin is loaded,
- how to add a marker,
- the constraints the plugin module operates under.

For configuration (`forgeqa.toml`, environment variables, CLI
overrides), see [`docs/configuration.md`](configuration.md). For the
design decision behind this surface, see
[ADR-013](adr/ADR-013-register-forgeqa-as-a-pytest11-plugin-with-a-central-marker-manifest.md).

---

## The entry point

`pyproject.toml` declares:

```toml
[project.entry-points.pytest11]
forgeqa = "forgeqa.pytest_plugin"
```

The entry point group is `pytest11`; the entry point name is `forgeqa`
(what `pytest -p forgeqa` refers to); the value is a dotted module path
(`forgeqa.pytest_plugin`).

The module is loaded on **every** pytest invocation in **every** project
where `forgeqa` is installed — including projects that have no idea what
ForgeQA is. Its import must therefore be cheap (see
[§"Import-cheapness"](#import-cheapness) below).

The `pytest>=9.2.0` dependency is in `[project].dependencies` (not an
optional extra). A `pytest11` plugin that is not importable without
pytest is not a plugin; the dependency is fundamental, not optional.

---

## Markers the plugin registers

At plugin-load time (before test collection), the plugin registers the
following markers on the consumer's pytest session:

| Marker | Meaning |
| :--- | :--- |
| `@pytest.mark.ui` | A test that exercises a browser (Playwright). |
| `@pytest.mark.api` | A test that exercises an HTTP API (HTTPX). |
| `@pytest.mark.unit` | A fast, hermetic test with no I/O. |
| `@pytest.mark.integration` | A test that exercises multiple components together (may use I/O). |

A test file in your project may use these markers without declaring them
in `pyproject.toml`. `pytest --markers` lists them, and pytest does
**not** emit `PytestUnknownMarkWarning` for them.

### Markers that are **not** registered

ForgeQA's own test suite uses two additional markers — `smoke` and
`slow` — declared in `[tool.pytest.ini_options].markers` in
`pyproject.toml`. These are ForgeQA-internal test-suite conventions,
not ForgeQA-consumer concepts:

- `smoke` — "essential delivery-confidence tests" (a ForgeQA-internal
  grouping that happens to be useful to some consumers).
- `slow` — "tests with longer expected runtime" (a ForgeQA-internal
  grouping for its own slow tests).

**The plugin does not register them.** A consumer who wants them
declares them in their own `pyproject.toml`:

```toml
# pyproject.toml, in the consumer's project
[tool.pytest.ini_options]
markers = [
    "smoke: essential delivery-confidence tests",
    "slow: tests with longer expected runtime",
]
```

The rationale: registering them via the plugin would claim marker names
the consumer might want to use for different meanings (e.g. a project
whose `slow` means "> 1 minute" vs. ForgeQA's "> 10 seconds"), and would
pollute `pytest --markers` with names the consumer may not care about.
The consumer's one-line opt-in is the cheaper trade-off. See ADR-013
§Alternatives Considered.

---

## Verifying the plugin is loaded

Two commands:

```bash
pytest --trace-config | grep forgeqa.pytest_plugin
# -> prints a line naming the plugin module:
#    PLUGIN registered: <module 'forgeqa.pytest_plugin' from '...'>

pytest --markers | grep 'pytest.mark.ui'
# -> prints the ui marker line with its description
```

The presence of a `PLUGIN registered: <module 'forgeqa.pytest_plugin' ...>`
line in `--trace-config` output is the signal that the plugin loaded.
`--markers` lists each registered marker.

### Exit codes for these commands

Not all "non-zero exit" is a failure:

| Command | Expected exit code | Why |
| :--- | :--- | :--- |
| `pytest --trace-config` in a directory with tests | `0` (all passed) or `1` (some failed) | It runs the tests after printing the plugin list. |
| `pytest --trace-config --co` in a directory with tests | `0` (collected) | `--co` stops after collection; exit 0 means collection succeeded. |
| `pytest --trace-config` (or with `--co`) in an **empty** directory | `5` | Exit 5 is "no tests collected", **not** a plugin-load failure. |
| `pytest --markers` (any directory) | `0` | Help-style flag; does not run tests. |

If you run `pytest --trace-config --co` in an empty directory and see
exit 5, that is normal — check the output for the `PLUGIN registered:
<module 'forgeqa.pytest_plugin' ...>` line; if it's there, the plugin
loaded and there simply were no tests to collect.

### When the plugin is not being discovered

If neither command names ForgeQA, check the following, in order:

1. **Is `forgeqa` installed in the same environment as `pytest`?**
   `python -m pytest` uses the `python` on `PATH`; `pytest` may use a
   different one. Confirm with:

   ```bash
   python -c "import forgeqa; print(forgeqa.__file__)"
   which pytest
   ```

   If the two are in different environments, `forgeqa` is installed
   for one Python and `pytest` is the other. Fix by installing `forgeqa`
   into the environment whose `pytest` you use, or by using
   `python -m pytest` consistently.

2. **Is the entry point present in the installed distribution's
   metadata?** This is the same view pytest uses:

   ```bash
   python -c "
   from importlib.metadata import entry_points
   eps = entry_points()
   group = eps.select(group='pytest11') if hasattr(eps, 'select') else eps.get('pytest11', [])
   print([(ep.name, ep.value) for ep in group if ep.name == 'forgeqa'])
   "
   # expected: [('forgeqa', 'forgeqa.pytest_plugin')]
   ```

   If the list is empty, the entry point is not in the installed
   metadata. Reinstall to regenerate it (see step 3).

3. **Was the entry point added after the last install?** Adding
   `[project.entry-points.pytest11]` to `pyproject.toml` does **not**
   refresh the installed distribution's metadata — editable install or
   not. Reinstall:

   ```bash
   pip install --force-reinstall --no-deps -e ".[dev]"
   ```

   `--force-reinstall` rebuilds the metadata; `--no-deps` skips
   reinstalling the whole dependency tree (the deps are already
   satisfied). With `uv`:

   ```bash
   uv pip install --reinstall --no-deps -e ".[dev]"
   ```

4. **Is the plugin module importable?** If the entry point is declared
   but the module import fails, pytest will emit a traceback at plugin-
   load time. Check:

   ```bash
   python -c "import forgeqa.pytest_plugin; print(forgeqa.pytest_plugin.__file__)"
   ```

   A failure here is the cause; the fix is whatever the traceback says.

---

## Import-cheapness

The plugin module is loaded on **every** pytest invocation in **every**
project where `forgeqa` is installed. That makes its import cost
load-bearing: a slow import here degrades pytest startup for every
project with `forgeqa` in the environment, not just ForgeQA users.

The constraints, enforced by
`tests/unit/test_plugin_registration.py::test_plugin_module_does_not_import_optional_dependencies`
and `test_plugin_module_import_is_cheap`:

- **No module-level import of `forgeqa.*`.** The plugin module imports
  only the stdlib and `pytest`. The config schema, error formatter, and
  any future fixtures are imported **inside** hook bodies or fixture
  functions. A module-level `import forgeqa.config` would pull in
  pydantic, `tomllib`, the schema, and the JSON-schema lookup — tens of
  milliseconds, on every pytest invocation, everywhere.
- **No module-level import of Playwright, HTTPX, or any other optional
  dependency.** The plugin must be importable in a core install (no
  `[ui]`, no `[api]` extras). Fixtures that need those imports
  (`browser`, `api_client`) import them inside the fixture body.
- **Import budget: < 100 ms.** Measured at ~1 ms on a cold
  interpreter; the budget is ~100× headroom, tight enough to catch a
  regression (an added schema import) without flaking under CI CPU
  contention.

The AST-based test (`test_plugin_module_does_not_import_optional_dependencies`)
catches a regression at commit time. If you add an import and the test
fails, **move it inside the function that needs it** — do not relax the
test.

---

## Adding a marker

Adding a consumer-facing marker to the plugin is a coordinated change
across four files. The tests are designed to make sure a change that
skips any of them fails CI:

1. **`src/forgeqa/pytest_plugin.py`** — add `(name, description)` to
   `FORGEQA_MARKERS`. The description appears in `pytest --markers`;
   it should be one sentence a consumer can act on, ending with a
   period.

2. **`tests/unit/test_plugin_registration.py::test_markers_manifest_has_expected_names`**
   — update the expected set (`{"ui", "api", "unit", "integration"}`)
   to include the new name.

3. **`tests/integration/plugin/test_plugin_smoke.py::test_each_forgeqa_marker_does_not_warn`**
   — update the parametrization to include the new name.

4. **This document** — add a row to the
   [§"Markers the plugin registers"](#markers-the-plugin-registers)
   table and, if the marker is used to select a subset of tests,
   a sentence on what it selects.

The four files move together. A change that updates `FORGEQA_MARKERS`
but not the tests is a CI failure ("registered set does not match
manifest set"); a change that updates the tests but not the docs is a
review comment, not a test failure — but reviewers should treat it as
one.

For a **framework-internal** marker (`smoke`, `slow`, or a new one for
ForgeQA's own test suite), the change is different: add it to
`[tool.pytest.ini_options].markers` in `pyproject.toml`, not to
`FORGEQA_MARKERS`. The distinction is:

- **`FORGEQA_MARKERS`** → consumer-facing; registered by the plugin;
  appears in the consumer's `pytest --markers`.
- **`[tool.pytest.ini_options].markers`** → ForgeQA's own test suite;
  declared for ForgeQA's `pytest` runs; does not affect consumers.

---

## What the plugin does **not** do (yet)

- **Load `forgeqa.toml` at plugin-load time.** Config loading happens
  in the `settings` fixture (Phase 1). A consumer's pytest session is
  not affected by ForgeQA's config.
- **Register fixtures.** The `settings`, `browser`, and `api_client`
  fixtures land in Phase 1 (WBS 1.3.x). They will register via a
  `pytest_plugins` list pointing to a `forgeqa.pytest_fixtures` module,
  keeping the plugin's own module-level imports cheap.
- **Register command-line options.** Any `--forgeqa-*` CLI surface is a
  Phase 2 concern. `pytest --help` currently shows no ForgeQA-specific
  flags.
- **Log at plugin-load time.** A library does not log at import time.
  Diagnostics come from `pytest --trace-config` and `pytest --markers`,
  which the user invokes deliberately.

---

## Design principles (why the plugin looks the way it does)

- **Cheap import, ubiquitous load.** The plugin is loaded everywhere;
  its import cost must not degrade unrelated test suites.
- **Single-source marker manifest.** `FORGEQA_MARKERS` is iterated by
  `pytest_configure` and asserted by tests, so adding a marker is a
  coordinated change, not a scattergun edit.
- **No reads of the consumer's config.** `pytest_configure` calls
  `config.addinivalue_line` and nothing else. Marker registration is
  independent of the consumer's `pyproject.toml` / `pytest.ini` /
  `tox.ini`.
- **Fail loudly, not silently.** If `addinivalue_line` raises (a
  pytest-API incompatibility), the plugin load fails with a traceback
  naming ForgeQA — not silently missing markers that produce confusing
  `PytestUnknownMarkWarning`s downstream.
- **Consumer vs. framework markers are distinct.** The plugin
  registers what the consumer needs (`ui`, `api`, `unit`,
  `integration`); ForgeQA's own test-suite markers (`smoke`, `slow`)
  stay in the framework's ini config.

---

## See also

- [`docs/configuration.md`](configuration.md) — config loading,
  precedence, validation, error logging
- [`docs/engineering-standards.md`](engineering-standards.md)
  §"Pytest markers" — contributor-facing marker conventions
- [`docs/adr/ADR-013`](adr/ADR-013-register-forgeqa-as-a-pytest11-plugin-with-a-central-marker-manifest.md)
  — the design decision (13 alternatives, consequences,
  reconsideration triggers)
- `tests/unit/test_plugin_registration.py` — the plugin's unit test
  suite (import cheapness, manifest, hook behaviour)
- `tests/integration/plugin/test_plugin_smoke.py` — the ATDD test
  suite (subprocess `--trace-config`, `--markers`, and warning-free
  markers)
- [`docs/public-api.md`](public-api.md) — the package's public API
  contract (the plugin module is not part of it; it is pytest-internal)
- Pytest docs, "Writing plugins":
  <https://docs.pytest.org/en/stable/how-to/writing_plugins.html>
- Pytest docs, "Working with custom markers":
  <https://docs.pytest.org/en/stable/how-to/mark.html>
- Python packaging, "Entry points":
  <https://packaging.python.org/en/latest/specifications/entry-points/>
