# ADR-014: Expose ForgeQA config as a session-scoped `settings` fixture backed by `load_config`

> **Status**: Accepted
> **Date**: 2026-10-29
> **Deciders**: @thapelomagqazana
> **Consulted**: None
> **Informed**: None

## Context

WBS 1.2.2 delivered `load_config()`, which reads `forgeqa.toml` and
`FORGEQA_*` environment variables and returns a `ForgeQAConfig`. Until
WBS 1.3.2, a consumer who wanted a `ForgeQAConfig` in a test had to call
`load_config()` themselves. That is fine for one test, but it has three
problems at scale:

1. **Cost.** `load_config` reads a file and parses TOML; on a cold
   process it also imports Pydantic (~30 ms). A suite of 1,000 tests
   that each called `load_config` would pay that cost 1,000 times.
2. **Divergence.** Two tests that each call `load_config` may see
   different configs if a test mutates `forgeqa.toml` or an env var
   mid-session. A config is a snapshot; per-test loading defeats that.
3. **Coupling to future fixtures.** The `browser` (WBS 1.3.3) and
   `api_client` (WBS 1.3.4) fixtures will need a `ForgeQAConfig`. If
   each calls `load_config` itself, the two would see different
   configs when one of them is used with a config-mutating test; more
   importantly, each would be a separate loading point that could
   diverge in *how* it loads (one passing `path=`, one not).

The obvious fix — a session-scoped pytest fixture that calls
`load_config()` once and returns the config — raises a design question
the WBS does not answer: **where does the fixture live?** Pytest's
`pytest11` plugin entry point (`forgeqa.pytest_plugin`) is imported on
**every** pytest invocation in **every** project where `forgeqa` is
installed (ADR-013 §Context). The plugin module's import must stay
cheap (`docs/engineering-standards.md` §3.4, rule 3). But the
`settings` fixture needs `forgeqa.config` (pydantic, `tomllib`, the
schema), which is not cheap. Defining the fixture in the plugin module
would hoist that import to module level and break the cheapness
guarantee — silently degrading pytest startup for every project with
`forgeqa` installed.

Additional forces:

- **Opt-in, not autouse.** A plugin that loads config on every test
  session — even for projects that never use a ForgeQA fixture —
  violates the "do no harm" property established in ADR-013. The
  fixture must be opt-in: a test that names `settings` gets it; a test
  that does not, does not.
- **Error behaviour.** If `forgeqa.toml` is invalid, the error must be
  visible as a fixture-setup error naming the file and field. A fixture
  that swallowed `ForgeQAConfigError` and returned a default config
  would produce a green run against a broken config — the exact failure
  mode WBS 1.2.4's `ForgeQAConfigError` exists to prevent.
- **Override-ability.** A consumer who needs `load_config(path="...")`
  or `load_config(environ=custom)` must be able to override `settings`
  in their own `conftest.py`. The fixture's job is the common case;
  the uncommon case is the consumer's responsibility.
- **Testability.** The fixture body must be testable without a running
  pytest session. That rules out using `request` (which is only
  available inside a session) and points toward a fixture body that
  takes no arguments and calls `load_config()`.

## Decision

1. **The fixture lives in `src/forgeqa/fixtures/settings.py`, not in
   `pytest_plugin.py`.** The plugin module registers it via
   `pytest_plugins = ("forgeqa.fixtures.settings",)`. Pytest imports
   `pytest_plugins` modules when it *activates* the plugin (after
   deciding to run tests, not for `--version` / `--help`), so the
   `forgeqa.config` import happens lazily. The plugin module's own
   import stays cheap — ADR-013 §Decision #3 is preserved.

2. **The fixture is session-scoped and not autouse.**
   `@pytest.fixture(scope="session")`. Session scope because
   `load_config` is too slow to repeat per test and because the
   "resolved once per session and shared" property is what
   `browser`/`api_client` will rely on. Not autouse because a plugin
   that loads config on every session imposes cost on projects that
   do not use ForgeQA fixtures.

3. **The fixture body calls `load_config()` with no arguments.** The
   default search applies: `forgeqa.toml` in CWD, then `FORGEQA_*` env
   vars, then defaults. A consumer who needs a different path or
   environment mapping overrides `settings` in their own
   `conftest.py`.

4. **The fixture body takes no parameters.** No `request`, no
   `config`, no other pytest-provided object. This makes the body
   testable by calling the wrapped function directly (see the "Testing
   a fixture in isolation" note in §Consequences) and prevents the
   hidden-coupling failure mode (reading `request.config.option` to
   decide what to load).

5. **`ForgeQAConfigError` propagates.** The fixture body does not
   catch it. Pytest reports it as a fixture-setup error naming the
   file/field, and the exception's `layer` / `field` / `value` /
   `expected` attributes are visible in the traceback (via the
   exception chain). A fixture that swallowed the error would produce
   a green run against a broken config.

6. **The fixture does not memoise.** Pytest's session-scoped fixture
   cache is the cache. Adding `@functools.lru_cache` to `load_config`
   or to the fixture body would (a) violate the loader's "no caching"
   contract (`docs/engineering-standards.md` §5.2 rule 4) and (b)
   prevent a developer running two `pytest.main()` calls in one
   process from seeing a config change between them.

7. **The fixture is a public surface with a stable import path.**
   `from forgeqa.fixtures.settings import settings` works (for
   type-checking); `forgeqa.fixtures.__all__` lists `"settings"`
   (for the "what does this package export" contract, same
   convention as `forgeqa.__all__` — §4.14).

## Alternatives Considered

| Alternative | Reason Rejected |
| :--- | :--- |
| Define `settings` directly in `forgeqa.pytest_plugin` | Hoists the `forgeqa.config` import (pydantic, `tomllib`, schema) to the plugin module's module-level import. That import runs on every pytest invocation in every project with `forgeqa` installed — the cheapness guarantee ADR-013 §Decision #3 is built around. Breaking it silently degrades pytest startup for unrelated projects. |
| Define `settings` in `forgeqa.pytest_plugin` but import `forgeqa.config` *inside* the fixture body | Works, but puts fixture code in the plugin module — mixing "plugin wiring" (hook implementations, marker manifest) with "fixture bodies" (config loading, eventually Playwright/HTTPX). The split into `forgeqa/fixtures/` is what will keep the plugin module from growing into a 1,000-line module by Phase 5. A one-line `pytest_plugins` declaration today is cheaper than the refactor later. |
| Rely on `conftest.py` auto-discovery for the fixture | Pytest only auto-discovers a project's own `conftest.py`, not a third-party plugin's submodules. A consumer would need to add `from forgeqa.fixtures.settings import settings` to their `conftest.py` — defeating the "install and use" property the plugin is for. |
| Make `settings` function-scoped | Calls `load_config` per test — defeats both the "resolved once per session" WBS criterion and the "shared" criterion. Also slow: ~30 ms per test. |
| Make `settings` autouse | Loads config on every pytest session, including projects that never use ForgeQA fixtures. A plugin must not impose cost on unrelated suites — the "do no harm" property from ADR-013. |
| Catch `ForgeQAConfigError` in the fixture and return a default config | Produces a green run against a broken `forgeqa.toml`. The user's actual bug — a typo in the config — would be invisible. The opposite of what `ForgeQAConfigError` (WBS 1.2.4) exists to do. |
| Cache the fixture result with `functools.lru_cache` (in addition to pytest's session scope) | Pytest's session-scoped fixture cache already provides "once per session". Adding `lru_cache` (a) breaks the loader's "no caching" contract, (b) makes a second `pytest.main()` call in the same process see the first call's config, and (c) has no measurable benefit over pytest's own cache. |
| Take `request` as a fixture parameter and read `request.config.option` to decide what to load | Couples config loading to the consumer's pytest configuration — the hidden-coupling failure mode ADR-013 §Context warns about. Also makes the fixture body untestable without a running pytest session. A consumer who needs a different config overrides the fixture; no `request` needed. |
| Expose `load_config`'s keyword arguments as fixture parameters (e.g. `settings(path=...)`) | Pytest fixtures cannot take arbitrary parameters. A `pytest.fixture(params=...)` parametrizes over a fixed set, not over caller-supplied values. The consumer's override-in-`conftest.py` pattern is the standard solution and is two lines. |
| Return a `dict` instead of a `ForgeQAConfig` | The whole point of `ForgeQAConfig` is typed, validated, frozen config. A `dict` would lose the schema, allow mutation mid-session (breaking "resolved once"), and force every consumer to re-validate. |
| Put the fixture's description in a module-level `_FIXTURE_DOC` constant and keep the function docstring short | Two copies of the same prose drift in practice — a parity test catches the drift but the design itself is the problem. One source of truth (the function's docstring) is simpler, and it is what `pytest --fixtures` shows. See §Consequences, "Single source of truth for the fixture docstring". |
| Test the fixture by reaching through `settings._fixture_function._pytestfixturefunction` (pytest 8) / `settings.__wrapped__` (pytest 7) | Pytest's fixture-wrapper introspection API is private and has changed twice in the last three minor releases (`_pytestfixturefunction` → `FixtureFunctionDefinition._fixture_function` → …). Test the **declaration** at the source level (the decorator, the body) and the **behaviour** via a subprocess ATDD test. See §Consequences, "Testing fixtures without pytest's private introspection API". |

## Consequences

### Positive

- **Session scope, one `load_config` call.** The config is loaded once
  per session and shared across every test that uses `settings` —
  the WBS acceptance criterion, verified by counting `load_config`
  calls in an ATDD test (a `conftest.py` counter written to disk at
  session finish; the count must be 1 across two test files in one
  session).
- **The plugin stays cheap.** `pytest_plugin.py` imports only stdlib +
  `pytest`; `forgeqa.fixtures.settings` is imported lazily via
  `pytest_plugins`. ADR-013 §Decision #3 is preserved.
- **"Do no harm" is preserved.** No `autouse`; a project that does
  not use `settings` pays nothing.
- **Errors are visible.** `ForgeQAConfigError` propagates as a
  fixture-setup error naming the file and field. A broken config is
  never silently replaced by defaults.
- **The fixture body is testable without a pytest session.** It takes
  no `request` parameter; the loader contract (returns a
  `ForgeQAConfig`, has the documented fields) is testable directly,
  and the fixture's *declaration* (session scope, no-argument body,
  no `try`/`except`) is checked at the source level, so a regression
  is caught in a fast hermetic unit test.
- **A future `browser` / `api_client` fixture can depend on
  `settings`** without re-loading the config. The "resolved once and
  shared" property is what makes those fixtures cheap and consistent.
- **The fixture is override-able.** A consumer whose project needs a
  custom `load_config` call writes a two-line override in their
  `conftest.py`. No plugin change required.
- **The sub-plugin pattern scales.** Adding `browser` and `api_client`
  in WBS 1.3.3 / 1.3.4 is a new module plus a new entry in
  `pytest_plugins` — no change to `settings` itself.

### Negative

- **The fixture is session-scoped, which surprises some consumers.**
  A test that mutates `forgeqa.toml` or an env var mid-session will
  not see the change in a `settings` fixture that was already
  created. The fixture docstring and `docs/plugins.md` both document
  this. A consumer who needs per-test isolation can override
  `settings` with a function-scoped version in their `conftest.py` —
  at the cost of per-test `load_config` calls.
- **The fixture does not accept a `path` / `environ`.** A consumer
  whose project lives in a subdirectory, or whose CI sets `FORGEQA_*`
  vars that should not apply to this fixture, must override it. The
  override is two lines; the alternative (fixture parameters) is not
  possible in pytest.
- **A consumer who never uses `settings` but who does use
  `browser`/`api_client` (when those land) will load config via
  `settings` indirectly.** That is correct and desirable — those
  fixtures need the config — but it means the "no ForgeQA config
  loaded" property only holds for projects that use *no* ForgeQA
  fixture. Documented in `docs/plugins.md`.
- **The plugin's `pytest_plugins` tuple is not implicitly versioned.**
  A future pytest version that changes `pytest_plugins` semantics
  (e.g. removes it in favour of an entry-points-only model) would
  break the sub-plugin registration. The AST test in
  `tests/unit/test_plugin_registration.py` does not cover this
  (it checks *imports*, not the tuple), so the test suite would catch
  it only at the integration level. Mitigation: the ATDD test runs a
  real pytest subprocess and would fail if the fixture stopped being
  discovered.

### Neutral

- `pytest_plugins` is a module-level tuple, not a list. Immutable
  value; a test that simulates an addition constructs a new tuple.
  Same convention as `FORGEQA_MARKERS`.
- The fixture returns a `ForgeQAConfig` (a Pydantic model), not a
  dataclass or a plain object. That is the type `load_config`
  produces; the fixture is a one-line wrapper.
- The `settings` fixture is *not* re-exported from
  `forgeqa.config` or from the top-level `forgeqa` package. It is a
  pytest concern, not a configuration concern — the same rationale as
  `FORGEQA_MARKERS` not being in `forgeqa.config.__all__` (ADR-013
  §Decision #4).
- **Single source of truth for the fixture docstring.** An early
  design used a module-level `_FIXTURE_DOC` constant plus a short
  function docstring; the parity test caught the two drifting within
  a day. The current design puts the full prose on the function
  itself, which is what `pytest --fixtures` shows and what a reader
  sees when opening the file. The module docstring keeps the
  *rationale* (why session scope, why no autouse, why no
  `lru_cache`) — a different document for a different audience, not
  a duplication.
- **Testing fixtures without pytest's private introspection API.**
  Pytest 8 wraps `@pytest.fixture`-decorated functions in a
  `FixtureFunctionDefinition`; pytest 7 returned the function with
  `_pytestfixturefunction` attached. Those attribute names are
  private and have changed between minor versions. The unit test
  suite tests the *declaration* at the source level (assert
  `@pytest.fixture(scope="session")` and `return load_config()` are
  present; assert no `try`/`except`) and tests the *loader contract*
  directly. The ATDD suite (`test_settings_fixture_smoke.py`) proves
  the *behaviour* end-to-end with a real pytest subprocess. This is
  the "test the smallest thing, at the right layer" rule — and it
  survives pytest minor-version bumps.

## Reconsideration Trigger

- **Phase 1 ships the `browser` and `api_client` fixtures.** Both
  will depend on `settings`. If either needs a different config than
  `settings` provides (e.g. a browser-specific base_url), the
  fixture's design must be revisited — likely a new sub-fixture
  derived from `settings`, not a change to `settings` itself. See
  ADR-013 §Reconsideration Trigger #1 for the cheap-import constraint
  those fixtures must also honour.
- **A consumer reports that mid-session config changes are not
  picked up.** This is the session-scope consequence. The first
  response is "override `settings` in your `conftest.py` with a
  function-scoped fixture"; if a pattern emerges (many consumers hit
  this), consider adding a parallel `settings_fresh` function-scoped
  fixture. Do not change `settings`' scope — that would break the
  WBS 1.3.2 acceptance criterion.
- **Pytest introduces a fixture-parameter feature** (e.g. "fixtures
  can declare `@pytest.fixture(config=...)` and pytest passes it
  through"). At that point, exposing `load_config`'s keywords as
  fixture parameters becomes possible; whether to do it is a separate
  decision (it would make the fixture's behaviour depend on pytest
  configuration — the hidden-coupling failure mode). Revisit with a
  fresh ADR.
- **A consumer asks for a `settings` fixture that reads a
  non-default path** without overriding in `conftest.py`. The
  override is the answer; if the pattern repeats, consider a
  `pytest_addoption` flag (`--forgeqa-config-path`) and a fixture
  that reads it. That is a Phase 2 concern (CLI options).
- **Pytest changes `pytest_plugins` semantics** (e.g. removes it in
  favour of an entry-points-only model). Migrate the registration
  to the new mechanism; the fixture body and `forgeqa.fixtures`
  package layout stay.
- **A consumer asks for the `settings` fixture to expose the loaded
  config's *source* (the resolved `forgeqa.toml` path, the list of
  `FORGEQA_*` env vars that were applied).** That is a legitimate
  debugging request; the answer is a small addition to the fixture
  (return a tuple `(config, source_info)`) or a parallel
  `settings_source` fixture. Do it as a minor version bump, not
  silently.
- **Pytest introduces a stable public API for fixture introspection**
  (e.g. `pytest.get_fixture_scope(fixture)`). At that point, the
  source-level assertion in the unit tests can be replaced by a
  runtime assertion; the change is a local refactor with no
  user-facing impact. Until then, the source-level check is the
  right tool — it is stable across pytest versions, and the ATDD
  test proves the behaviour.

## Related

- WBS 1.3.2 — Implement the settings Fixture (this decision)
- WBS 1.3.1 — pytest plugin registration (predecessor; established
  the cheap-import constraint this ADR honours)
- WBS 1.2.2 — the `load_config` loader (the function the fixture
  wraps)
- WBS 1.2.4 — `ForgeQAConfigError` (the exception the fixture
  propagates)
- WBS 1.2.5 — safe defaults (the values the fixture returns when no
  `forgeqa.toml` is present)
- ADR-013 — pytest11 plugin registration and the cheap-import
  constraint
- ADR-012 — error handling and logging (the `ForgeQAConfigError`
  whose attributes a consumer sees in a fixture-setup error)
- ADR-011 — safe defaults (the bounds and the reference-app coupling
  the defaults reference)
- `src/forgeqa/fixtures/settings.py` — the fixture module
- `src/forgeqa/pytest_plugin.py` — the `pytest_plugins` declaration
- `tests/unit/test_settings_fixture.py` — the unit test suite
  (source-level declaration checks, loader contract, duplicate-module
  canary)
- `tests/integration/plugin/test_settings_fixture_smoke.py` — the
  ATDD suite (subprocess pytest, session-scope counter, broken-TOML
  fixture error)
- `docs/plugins.md` §"Fixtures the plugin provides" — consumer-facing
  reference (table, example, session-scope caveat, error behaviour,
  override pattern)
- `docs/engineering-standards.md` §3.4 — contributor-facing rules
  for the plugin and its fixtures (rules 9–11 specifically)
- Pytest docs, "Fixtures":
  <https://docs.pytest.org/en/stable/how-to/fixtures.html>
- Pytest docs, "Writing plugins" (`pytest_plugins`):
  <https://docs.pytest.org/en/stable/how-to/writing_plugins.html>
- Python packaging, "Entry points":
  <https://packaging.python.org/en/latest/specifications/entry-points/>
