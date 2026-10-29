# ADR-011: Make safe defaults explicit and testable against the reference app

> **Status**: Accepted
> **Date**: 2026-10-29
> **Deciders**: @thapelomagqazana
> **Consulted**: None
> **Informed**: None

## Context

WBS 1.2.1 established the config model hierarchy; WBS 1.2.5 requires that
a fresh install — no `forgeqa.toml`, no `FORGEQA_*` env vars — produce a
config that works **against the Phase 0.6 reference app without
modification**. This is the "out-of-the-box" experience: the first thing
a prospective user does is `pip install forgeqa`, drop a test into
`tests/`, run `pytest`, and expect it to either pass or fail loudly with
useful evidence. Spending twenty minutes wiring up `forgeqa.toml`
before the first test runs is the #1 drop-off point for new test
frameworks.

Two forces are in tension:

* **Safety.** Defaults must not surprise the user. They must be local,
  headless, and observably-traceable. A default that points at a
  production URL, or that disables failure evidence, is a footgun.
* **Immediacy.** Defaults should "just work" against *something*. A
  default that points at `http://localhost` with no server running is
  technically safe but practically useless — the first run fails with a
  connection error and no pointer to what to run.

The Phase 0.6 reference app (`examples/reference-app`) is already in
the repo, listens on `127.0.0.1:8000`, and exposes `GET /health`. Using
its address as the `api.base_url` default resolves both forces at once:
the default is local and safe, *and* it points at something a reviewer
can actually start (`make -C examples/reference-app up`).

Additional forces at play:

* **Testability.** Every default must be individually assertable, so a
  regression names the offending field. A single
  `assert config.dict() == {...}` is short but useless when it fails —
  you have to diff to find the field.
* **Documentability.** `docs/configuration.md` must be the single
  source of truth for "what does the default do and why". Code, docs,
  and tests must be kept in sync; CI enforces the code↔test link.
* **Strictness.** Unknown keys in `forgeqa.toml` must fail loudly
  (`extra="forbid"`), because a silent typo that falls back to a
  default is the most expensive class of configuration bug — it is
  invisible, and it only surfaces much later as "why isn't my config
  being applied?".
* **Non-functional cost.** Config construction runs on every test
  session and, through `pytest-xdist`, in every worker. Any I/O or
  expensive validation in the model constructor is multiplied across
  the whole suite. The model must remain pure data.
* **Immutability across workers.** A config that can be mutated
  mid-run is a race across `pytest-xdist` workers and produces
  non-reproducible failures. Frozen models make the config trivially
  safe to share.
* **Two concepts, one concern.** WBS 1.2.5 names
  `screenshot_on_failure` and `trace_on_failure` alongside
  `browser_name`, `headless`, and `timeout_ms`. They are
  browser-specific (Playwright screenshot, Playwright trace). The
  pre-existing `DiagnosticsConfig.screenshots` / `DiagnosticsConfig.traces`
  flags expressed the same idea under a different name, creating two
  sources of truth.

## Decision

1. **Every field in every config model has an explicit default**, chosen
   for the "fresh install, CI-compatible, evidence-first" scenario. The
   WBS 1.2.5 defaults are:
   `general.environment="local"`, `general.log_level="INFO"`,
   `general.artifacts_dir="artifacts"`,
   `browser.browser_name="chromium"`, `browser.headless=True`,
   `browser.timeout_ms=10_000`,
   `browser.screenshot_on_failure=True`,
   `browser.trace_on_failure=True`,
   `api.base_url="http://127.0.0.1:8000"`.
2. **`api.base_url` defaults to `http://127.0.0.1:8000`** — the Phase
   0.6 reference app's origin. This is the only default coupled to a
   specific external service; the coupling is documented and revisited
   when the MVP ships (see Reconsideration Trigger). `127.0.0.1` is
   chosen over `localhost` because on some Linux images `localhost`
   resolves to `::1` (IPv6) first and the reference app binds IPv4 only
   — a fresh install would fail on such images. The default carries
   **no `/api` suffix**: the reference app's health endpoint is
   `/health`, and a "base URL" conventionally is the origin, with the
   API path supplied by the client.
3. **Failure-evidence flags live on `BrowserConfig`.** Add
   `browser.screenshot_on_failure` and `browser.trace_on_failure` (both
   `True` by default). Remove the duplicate
   `diagnostics.screenshots` and `diagnostics.traces` fields — the
   `DiagnosticsConfig` sub-model retains only `console_logs` and is
   re-scoped in its docstring to "diagnostic output that is not
   browser-specific". This is a **clean break** (no deprecation shim):
   the project is pre-alpha with no external consumers, and adding a
   shim now is technical debt that WBS 1.2.5 exists to reduce, not
   create.
4. **Models are `frozen=True`, `extra="forbid"`, `validate_assignment=True`,
   `validate_default=True`, `str_strip_whitespace=True`.** Config is
   read once, shared across workers, and mutations are a bug. Unknown
   keys are rejected loudly. `validate_default=True` means the
   defaults themselves are validated at construction time — a bug in a
   default value cannot reach a user.
5. **`browser.timeout_ms` is bounded `[1, 60_000]`** and
   **`api.timeout_seconds` is bounded `[1, 300]`.** The lower bound
   rejects `0` and negatives (a zero timeout silently breaks
   Playwright's default-timeout resolution); the upper bound catches
   unit-confusion typos (a user who meant seconds and wrote
   milliseconds).
6. **Defaults are tested one-per-field** in
   `tests/unit/config/test_defaults.py`, with the rationale in the
   test docstring and a matching row in `docs/configuration.md`.
   Splitting defaults into one test per field (rather than a single
   dict comparison) means a failing test's *name* is the failure
   message: `test_log_level_defaults_to_info`.
7. **An ATDD integration test** in
   `tests/integration/config/test_defaults_reference_app.py` drives
   the reference app with a config built *purely* from defaults,
   proving the out-of-the-box contract rather than just the field
   values. The test reads `api.base_url` from the default config
   (rather than hard-coding it), so the test cannot pass if the
   default drifts away from the reference app.
8. **The defaults are documented, not hidden.**
   `docs/configuration.md` leads with a table of defaults and the
   reference-app coupling, so users are never surprised by "why is it
   calling `127.0.0.1`?".

## Alternatives Considered

| Alternative | Reason Rejected |
| :--- | :--- |
| No defaults — require `forgeqa.toml` for every field | Fails the "out-of-the-box" acceptance criterion. First-run friction is the #1 drop-off point for new frameworks; a config file that must be written before the first test can run is a hard barrier. |
| Default `base_url` to `http://localhost` (no port) | Works only if the user happens to run on port 80; fails unpredictably across platforms and requires the user to guess the reference app's port. `127.0.0.1:8000` is explicit and matches the reference app. |
| Default `base_url` to `http://localhost:8000` (hostname form) | Fails on Linux images where `localhost` resolves to `::1` first and the reference app binds IPv4 only. `127.0.0.1` is unambiguous. This exact failure mode was observed during the WBS 1.2.5 manual verification; it is the reason the `127.0.0.1` vs `localhost` distinction is documented in this ADR. |
| Default `base_url` to `http://127.0.0.1:8000/api` | Fails the WBS 1.2.5 requirement that the default works against the reference app **without modification** — the reference app's health endpoint is `/health`, not `/api/health`. Additionally, a "base URL" with a path suffix surprises users pointing the client at their own service (which may not have `/api`). |
| Default `base_url` to a placeholder like `https://example.com` | Safe but useless: the first run fails against a third-party site that will never be the user's service. Worse, it silently makes network calls to a domain we do not control. |
| Default `headless=False` | Breaks CI (no display) and is slower. Users who want to *watch* runs will override; users who do not know the field exists will get a broken first experience. |
| Default `screenshot_on_failure=False` / `trace_on_failure=False` | Contradicts ForgeQA's "evidence-first" core principle (see `docs/product-requirements.md`). Evidence is cheap; opting out should be a conscious choice, not the default. |
| Keep failure evidence on `DiagnosticsConfig` (`diagnostics.screenshots`, `diagnostics.traces`) and add aliases on `BrowserConfig` | Creates two sources of truth for the same concept. Every downstream consumer has to decide which field to read; every refactor has to keep two fields in sync; every bug report about "why isn't my screenshot setting taking effect?" becomes a two-place investigation. This is exactly the technical debt WBS 1.2.5 exists to *reduce*. |
| Keep `diagnostics.screenshots` / `diagnostics.traces` as deprecated aliases on the loader (shim) | Pre-alpha project with no external consumers; a shim now would be technical debt with a definite future removal date but no present benefit. Clean break recorded here, taken in this branch. |
| Single `assert config.model_dump() == {...}` test | Short but useless when it fails — you have to diff two dicts to find the field. One test per field makes the test name the failure message. |
| `extra="ignore"` on models | Silent typos in `forgeqa.toml`. Every configuration system we have worked with has been bitten by this; it is the most expensive kind of correctness bug because it is invisible until much later. `extra="forbid"` turns a silent footgun into a fast, actionable error. |
| `frozen=False` (mutable config) | Allows mid-run mutation, which is a race across `pytest-xdist` workers and makes failures non-reproducible. Frozen is free and makes the config trivially shareable. |
| `validate_default=False` | An invalid default would only surface when a user actually used it — i.e. on a fresh install. `validate_default=True` catches a buggy default at construction time, in the framework's own tests, before any user sees it. |
| Document defaults only in `docs/configuration.md`, not in `models.py` docstrings | Documentation is what users read; docstrings are what maintainers read. If they must diverge (they should not, but inevitably will), a maintainer editing `models.py` should see the *reason* for the default next to the code, not have to navigate to the docs. Both are required and the test file enforces the code↔test link. |

## Consequences

### Positive

- A fresh `pip install forgeqa` + a test file is a runnable setup. First-run friction is near zero, and the first run does something observable (hits the reference app's `/health`) rather than failing with a connection error.
- Every default is individually assertable; a regression names the field (`test_log_level_defaults_to_info` fails ⇒ you know exactly what changed).
- The ATDD test **proves** the reference-app contract. It cannot silently drift because it reads `api.base_url` from the default config rather than hard-coding the address.
- `extra="forbid"` turns config typos into immediate, actionable errors rather than silent fallbacks.
- `frozen=True` makes the config trivially safe to share across `pytest-xdist` workers and threads.
- `validate_default=True` means a buggy default fails in CI before it reaches a user.
- `docs/configuration.md` is the single source of truth for the *values*; the test file enforces code↔test parity. A change that skips either one fails loudly.
- The reference-app coupling is **explicit and documented** in one place (this ADR). Reviewers can challenge it by pointing at a paragraph, not by reverse-engineering `models.py`.
- Failure evidence lives in exactly one place (`BrowserConfig`). Downstream code has one field to read, one field to override, one field to document.
- `DiagnosticsConfig` is now clearly scoped to "non-browser diagnostic capture" (today: `console_logs`; future: request/response bodies for API tests), which is a coherent concept rather than an appendix of browser flags.

### Negative

- **The `api.base_url` default is coupled to the reference app.** If the reference app changes ports, the default must change. The ATDD test (`test_defaults_reference_app.py`) will fail loudly on such a change — good, but the fix touches three files (`models.py`, `docs/configuration.md`, this ADR) and one test. The coupling is deliberate for the MVP, not an accident.
- **Removing `diagnostics.screenshots` and `diagnostics.traces` breaks backward compatibility.** Any external code that reads `config.diagnostics.screenshots` will fail with an `AttributeError` after this change. This is accepted because the project is pre-alpha (0.1.0) with no external users; a real product would need a deprecation cycle. The break is recorded here and in the branch commit so it is a documented choice, not a silent one.
- **Every new config field now requires a matching test + docs row.** This is deliberate friction that keeps the contract honest — but it is friction. Adding a field is a three-file change, not one.
- **The ATDD integration test requires the reference app to be running in CI.** That is a real cost (a container spin-up in the `integration` job) but it is the only way to prove "works out of the box". Locally, developers who do not want to run the reference app must skip the integration marker; CI runs it.
- **`frozen=True` blocks legitimate-looking mutations** (e.g. `cfg.general.log_level = "DEBUG"` in a test). Callers must use `model_copy(update=...)` instead — slightly more verbose, but the right default.
- **`validate_default=True` costs a small amount of construction time.** Measured at < 1 ms per config; the non-functional test (`test_construction_is_fast`) caps 1,000 constructions at 100 ms. Not a real cost, but worth recording.

### Neutral

- The unit test file mirrors the defaults list 1:1. More lines than a single dict comparison, but each line names one field, which is what makes the tests useful diagnostics rather than just gates.
- `docs/configuration.md` grows a "Defaults" table with per-field rationale. Intentional: a configuration reference without a defaults table is not a reference.
- `browser.base_url` and `api.base_url` are kept as two independent fields. A UI root and an API root often differ (e.g. UI at `/`, API at `/api`); collapsing them into one field would force every project whose UI and API sit at different paths to override something. They are distinct fields with independent defaults, and neither depends on the other.
- `DiagnosticsConfig` shrinks (from three fields to one). This is not a loss of functionality — it is a correction. The two removed fields reappear on `BrowserConfig` under the names WBS 1.2.5 specifies.
- The `api.timeout_seconds` default (`10`) is not one of the nine defaults named by WBS 1.2.5, but it is asserted in `test_defaults.py` to keep the module's default set fully covered. If a future WBS does not want it, remove both the field and the test together.
- Two of the fields asserted in `test_defaults.py` (`reporting.junit_xml`, `reporting.json_report`) are not named by WBS 1.2.5 either, but are part of the out-of-the-box experience ("produces a CI report and a JSON report on first run") and so are covered for the same reason.

## Reconsideration Trigger

Revisit this decision when **any** of the following occurs:

- **MVP ships (Phase 1 end).** The "first thing users do" becomes "point ForgeQA at *my* service", not "run against the reference app". At that point, `api.base_url` default may shift to a clearly-labelled placeholder (e.g. `http://localhost:8000` documented as "your service"), and the docs will lead with "set this". The ADR will be updated, not superseded, because the decision principle (safe default that points at something runnable) remains — only the specific address changes.
- **The reference app changes its default port or `/health` path.** Update the default in `models.py`, the row in `docs/configuration.md`, and the ATDD test together; add a note to §Related below.
- **First-run telemetry (when introduced) shows > 20% of users spend > 10 minutes editing config before their first green run.** That would mean the defaults are wrong for the median user, not just the demo user — escalate to a new ADR rather than silently shifting defaults.
- **A new config field is proposed without a default.** That is a signal the field may not be safe-default-able (e.g. a required secret, or a field whose correct value depends on the user's environment). Escalate to an ADR rather than adding the field silently; the alternative is to set a "no-op" default and document that the field must be set for real use.
- **Pydantic v3 introduces breaking model-config semantics** (e.g. a different frozen mechanism, or a different default for `validate_default`). Migrate per the new ADR; do not silently change behaviour. The set of config properties this ADR depends on is enumerated in §Decision #4 and §Decision #5, so a Pydantic upgrade is testable against that list.
- **An external consumer requests backward compatibility for `diagnostics.screenshots` / `diagnostics.traces`.** At that point a deprecation shim becomes justified (the pre-alpha rationale no longer holds). Add it to `forgeqa/config/loader.py`, deprecate for one minor version, remove.
- **`pyproject.toml`'s `requires-python` matrix changes** (per ADR-001's reconsideration trigger). The defaults are not version-sensitive today, but any Python-version-dependent `Path` or `os.access` behaviour would need re-verification.

## Related

- WBS 1.2.5 — Define and Validate Safe Defaults (this decision)
- WBS 1.2.1 — Config model hierarchy (predecessor; established the schema)
- WBS 0.6.2 — Phase 0.6 reference app (fixture for the ATDD test; listen address is the source of `api.base_url`'s default)
- ADR-001 — Adopt MIT license file and PEP 621-compliant package metadata (this PR's immediate predecessor; shares the pattern of "default that is testable and documented")
- ADR-002 — Resolve package version at import time via importlib.metadata and keep top-level imports dependency-free (rationale for "no I/O on construction")
- ADR-007 — Model the ForgeQA configuration as a strictly-typed Pydantic v2 hierarchy (the schema this ADR fills in)
- ADR-008 — Load `forgeqa.toml` into `ForgeQAConfig` with `tomllib` and a custom `ForgeQAConfigError` (loader; consumes these defaults)
- ADR-009 — Resolve configuration precedence as CLI > env > TOML > defaults (defaults are layer 4 of this hierarchy)
- ADR-010 — Validate config fields with Pydantic constraints plus a small human-readable error formatter (constraints used by this ADR; the "no side effects in validators" rule interacts with the `artifacts_dir` validator)
- `src/forgeqa/config/models.py` — where the defaults live
- `src/forgeqa/config/__init__.py` — public surface; docstring documents the safe-defaults contract
- `tests/unit/config/test_defaults.py` — one-per-field assertions for every default
- `tests/integration/config/test_defaults_reference_app.py` — ATDD against the reference app
- `docs/configuration.md` §"Defaults" — user-facing defaults table and change workflow
- `docs/product-requirements.md` — the "evidence-first" principle that motivates `screenshot_on_failure=True` / `trace_on_failure=True`
- `examples/reference-app/` — Phase 0.6 fixture; `docker-compose.yml` defines the listen port; `app/routers/health.py` implements `GET /health`
