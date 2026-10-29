"""Unit tests for ForgeQA config safe defaults (WBS 1.2.5).

These tests are the contract for ADR-011: a fresh ``ForgeQAConfig()``
with no ``forgeqa.toml`` and no environment variables must yield exactly
the documented defaults, and each field must be individually asserted so
a regression names the offending field.

Test taxonomy
-------------
* **Positive** -- happy path, defaults present and of the right type.
* **Negative** -- bad input (extra keys, wrong types) is rejected by the
  model rather than silently falling back to a default. This is the
  safety net for typos in ``forgeqa.toml``.
* **Boundary** -- numeric ranges on ``timeout_ms`` and ``timeout_seconds``.
* **Edge** -- legal-but-unusual values (e.g. the minimum legal timeout).
* **Corner** -- combinations unlikely but legal (e.g. overriding one
  field must not disturb any other field's default).
* **Non-functional** -- no I/O at construction, bounded construction
  time, immutability, deterministic equality. These protect the
  *properties* of the config object, not just its values.

**URL comparison note.** ``AnyHttpUrl`` fields are compared against
``AnyHttpUrl`` values, not against their rendered strings. Pydantic v2
normalises the bare-origin form to include a trailing slash
(``"http://127.0.0.1:8000/"``); the rendered string is a formatting
detail, not the contract. This is the same rule ADR-011 applies to
``Requires-Python`` in the packaging context: compare semantically, not
textually.

Every test carries its rationale in the docstring -- reviewers should be
able to read the test file as a spec of 1.2.5. The tests deliberately do
**not** read from disk, do **not** start the reference app, and do
**not** require any optional dependency (Playwright, HTTPX). The ATDD
counterpart that exercises the reference app lives at
``tests/integration/config/test_defaults_reference_app.py``.

Running
-------
``pytest tests/unit/config/test_defaults.py -v`` yields one test per
documented default, plus the boundary, negative, corner, and
non-functional groups. ``make test-unit`` runs the whole unit suite.
"""

from __future__ import annotations

import time

import pytest
from pydantic import AnyHttpUrl, ValidationError

from forgeqa.config.models import (
    APIConfig,
    BrowserConfig,
    DiagnosticsConfig,
    ForgeQAConfig,
    GeneralConfig,
    ReportingConfig,
)

# All tests in this module are fast, hermetic, and unit-scoped. The
# `unit` marker is used by `pytest -m unit` (see the Makefile's
# `test-unit` target) and by the CI job that runs unit tests without
# starting the reference app.
pytestmark = pytest.mark.unit


# ===========================================================================
# Positive: every documented default is exactly as specified
# ===========================================================================


class TestDocumentedDefaults:
    """One test per default from WBS 1.2.5.

    If one of these fails, the WBS ID in the docstring points at the
    requirement it violates. Splitting defaults into one test per field
    (rather than a single dict comparison) is deliberate: a failing test
    name is the failure message. See ADR-011 §Decision #6.
    """

    # --- GeneralConfig -----------------------------------------------------

    def test_environment_defaults_to_local(self) -> None:
        """WBS 1.2.5: ``environment="local"``.

        Rationale: ``local`` is the least surprising tag for a fresh
        install. ``ci`` / ``staging`` are opt-in, because defaulting to
        them would make fresh local runs claim to be something they are
        not.
        """
        assert ForgeQAConfig().general.environment == "local"

    def test_log_level_defaults_to_info(self) -> None:
        """WBS 1.2.5: ``log_level="INFO"``.

        Rationale: ``INFO`` shows lifecycle events without drowning CI
        logs in per-action noise. ``DEBUG`` is opt-in for diagnosis.
        """
        assert ForgeQAConfig().general.log_level == "INFO"

    def test_artifacts_dir_defaults_to_artifacts(self) -> None:
        """WBS 1.2.5: ``artifacts_dir="artifacts"``.

        Rationale: relative to CWD, already in ``.gitignore``, writable
        on every supported OS without elevation.
        """
        assert ForgeQAConfig().general.artifacts_dir == "artifacts"

    # --- BrowserConfig -----------------------------------------------------

    def test_browser_name_defaults_to_chromium(self) -> None:
        """WBS 1.2.5: ``browser_name="chromium"``.

        Rationale: widest CI image coverage, fastest to launch. Users
        who need cross-engine coverage opt in explicitly.
        """
        assert ForgeQAConfig().browser.browser_name == "chromium"

    def test_headless_defaults_to_true(self) -> None:
        """WBS 1.2.5: ``headless=True``.

        Rationale: CI has no display; headless is the only mode that
        works out of the box on GitHub Actions. Displayed runs are a
        conscious local override.
        """
        # `is True` rather than `== True`: `bool` is fine, but we
        # specifically want to assert it isn't a truthy non-bool
        # (e.g. the string "true" from a TOML value).
        assert ForgeQAConfig().browser.headless is True

    def test_timeout_ms_defaults_to_10000(self) -> None:
        """WBS 1.2.5: ``timeout_ms=10000``.

        Rationale: 10 s covers a cold-start page load on a developer
        laptop while failing fast enough in CI to avoid the workflow's
        outer timeout.
        """
        assert ForgeQAConfig().browser.timeout_ms == 10_000

    def test_screenshot_on_failure_defaults_to_true(self) -> None:
        """WBS 1.2.5: ``screenshot_on_failure=True``.

        Rationale: evidence-first. Screenshots are cheap (hundreds of
        KB) and enormously reduce time-to-diagnosis. Opting *out* is a
        conscious choice.
        """
        assert ForgeQAConfig().browser.screenshot_on_failure is True

    def test_trace_on_failure_defaults_to_true(self) -> None:
        """WBS 1.2.5: ``trace_on_failure=True``.

        Rationale: evidence-first. Playwright traces capture the full
        DOM timeline and are the single most useful artifact for a
        non-reproducible failure.
        """
        assert ForgeQAConfig().browser.trace_on_failure is True

    # --- APIConfig ---------------------------------------------------------

    def test_base_url_defaults_to_reference_app(self) -> None:
        """WBS 1.2.5: ``base_url="http://127.0.0.1:8000"``.

        Rationale: the Phase 0.6 reference app listens here, so a fresh
        install is runnable against *something real*. ``127.0.0.1`` is
        chosen over ``localhost`` to avoid IPv6-vs-IPv4 resolution
        surprises on Linux CI images (see ADR-011 §Lessons learnt).

        Comparison note: ``AnyHttpUrl`` normalises the bare-origin
        rendered form to include a trailing slash
        (``"http://127.0.0.1:8000/"``). We compare against the
        ``AnyHttpUrl`` value, not the string, because the string is a
        formatting detail -- a future Pydantic version could change it
        without changing the contract.
        """
        assert ForgeQAConfig().api.base_url == AnyHttpUrl("http://127.0.0.1:8000")

    # --- DiagnosticsConfig -------------------------------------------------

    def test_diagnostics_console_logs_defaults_to_true(self) -> None:
        """WBS 1.2.5 (implicitly): console log capture is on by default.

        Rationale: console logs are the most common source of "why did
        this fail?" information for JavaScript-driven apps. This field
        is not one of the nine explicitly named by WBS 1.2.5, but it
        lives in ``DiagnosticsConfig`` and its default matters to the
        out-of-the-box experience -- so it is asserted here to keep the
        module's default set fully covered.
        """
        assert ForgeQAConfig().diagnostics.console_logs is True

    # --- ReportingConfig ---------------------------------------------------

    def test_reporting_junit_xml_defaults_to_true(self) -> None:
        """WBS 1.2.5 (implicitly): JUnit XML emission is on by default.

        Rationale: it is the CI-native report format; a framework whose
        default is "produce no CI report" makes CI integration opt-in
        for no good reason.
        """
        assert ForgeQAConfig().reporting.junit_xml is True

    def test_reporting_json_report_defaults_to_true(self) -> None:
        """WBS 1.2.5 (implicitly): structured JSON emission is on by default.

        Rationale: it is the durable artifact that outlives any
        particular CI's report UI, and it is what Phase 3 analytics
        will consume.
        """
        assert ForgeQAConfig().reporting.json_report is True


# ===========================================================================
# Corner: structural invariants the defaults must satisfy
# ===========================================================================


class TestDefaultsAreConsistent:
    """Cross-cutting invariants that go beyond "each field equals X".

    These catch refactors that accidentally diverge the default set
    between the root model and the sub-models, or that accidentally
    introduce shared mutable state.
    """

    def test_default_construction_is_deterministic(self) -> None:
        """Two independent ``ForgeQAConfig()`` instances must be equal.

        Guards against accidental shared mutable state sneaking into a
        ``default_factory``. If this fails after a refactor, someone
        replaced a ``default_factory=Model`` with a literal
        ``default=Model()`` -- reintroducing cross-instance mutation
        (the classic Pydantic footgun).
        """
        assert ForgeQAConfig() == ForgeQAConfig()

    def test_root_defaults_match_sub_model_defaults(self) -> None:
        """Building the root or a sub-model directly yields the same defaults.

        Users and tests may construct a sub-model in isolation (e.g.
        ``BrowserConfig()`` to unit-test a fixture). The defaults must
        match the root so both entry points agree. If they diverge, the
        out-of-the-box behaviour depends on *how* the config was
        constructed -- which is exactly the kind of surprise WBS 1.2.5
        is supposed to prevent.
        """
        root = ForgeQAConfig()
        assert root.general == GeneralConfig()
        assert root.browser == BrowserConfig()
        assert root.api == APIConfig()
        assert root.diagnostics == DiagnosticsConfig()
        assert root.reporting == ReportingConfig()

    def test_browser_and_api_base_urls_are_independent(self) -> None:
        """UI base URL and API base URL are separate fields.

        A UI root and an API root often differ (e.g. UI at ``/``, API
        at ``/api``). Collapsing them into one field would force every
        project whose UI and API sit at different paths to override
        something. They are distinct in the model, and both are
        independent defaults. This is a structural assertion, not a
        default-value assertion -- it holds under any future default
        change.
        """
        cfg = ForgeQAConfig()
        # Both are AnyHttpUrl instances, but not the same instance and
        # not necessarily the same value. Asserting type + independence,
        # not equality, keeps this test meaningful if the API default
        # ever moves to ``.../api`` in a future revision.
        assert cfg.browser.base_url is not cfg.api.base_url
        assert isinstance(cfg.browser.base_url, type(cfg.api.base_url))


class TestDefaultsAreIsolated:
    """Each field's default is independent of every other field's override.

    This is the "corner" case where a naive defaults implementation
    (shared dict, shared model instance) would fail: overriding one
    field would silently disturb another. Since we use per-field
    ``default=`` and per-model ``default_factory=``, overrides are
    isolated. These tests pin that property.
    """

    def test_overriding_general_does_not_change_browser_defaults(self) -> None:
        cfg = ForgeQAConfig(general=GeneralConfig(environment="ci"))
        assert cfg.general.environment == "ci"
        assert cfg.browser.browser_name == "chromium"
        assert cfg.browser.headless is True
        assert cfg.browser.timeout_ms == 10_000
        assert cfg.browser.screenshot_on_failure is True

    def test_overriding_browser_does_not_change_api_defaults(self) -> None:
        cfg = ForgeQAConfig(browser=BrowserConfig(headless=False))
        assert cfg.browser.headless is False
        # Compare AnyHttpUrl values, not strings: AnyHttpUrl normalises
        # the rendered form to include a trailing slash.
        assert cfg.api.base_url == AnyHttpUrl("http://127.0.0.1:8000")
        assert cfg.api.timeout_seconds == 10

    def test_overriding_api_does_not_change_general_defaults(self) -> None:
        cfg = ForgeQAConfig(api=APIConfig(base_url="https://example.com"))
        # Compare AnyHttpUrl values, not strings: AnyHttpUrl normalises
        # the rendered form to include a trailing slash.
        assert cfg.api.base_url == AnyHttpUrl("https://example.com")
        assert cfg.general.environment == "local"
        assert cfg.general.artifacts_dir == "artifacts"


# ===========================================================================
# Negative: invalid input is rejected, not silently defaulted
# ===========================================================================


class TestRejectsInvalidInput:
    """``extra="forbid"`` and Pydantic constraints must reject bad input.

    These are the safety net for typos in ``forgeqa.toml``: a
    mis-spelled key or an out-of-range value must fail at load time,
    not be silently ignored in favour of a default. See ADR-011
    §Context -- silent fallback is the most expensive class of config
    bug because it is invisible.

    Pydantic raises :class:`pydantic.ValidationError` for every one of
    these cases; the loader (``forgeqa.config.loader``) wraps that in
    :class:`ForgeQAConfigError` with a human-readable message. At the
    model layer we assert on ``ValidationError`` because that is what
    the model itself raises, and testing the loader's formatting is the
    loader's job (``tests/unit/config/test_loader.py``).
    """

    # --- extra="forbid" ----------------------------------------------------

    def test_unknown_field_in_general_is_rejected(self) -> None:
        """A typo'd field name inside a known section must fail.

        ``artifact_dir`` (missing 's') is the canonical example: it
        looks right, and silently ignoring it would leave the user
        wondering why their artifacts aren't in the directory they
        configured.
        """
        with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
            GeneralConfig(environment="local", artifact_dir="typo")  # noqa: E501

    def test_unknown_field_in_browser_is_rejected(self) -> None:
        with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
            BrowserConfig(timout_ms=5_000)  # noqa: E501

    def test_unknown_top_level_section_is_rejected(self) -> None:
        """A typo'd section name at the root must fail.

        ``[brower]`` instead of ``[browser]`` is a realistic mistake
        when hand-writing TOML. Silent acceptance would mean the entire
        browser configuration is ignored -- the worst possible failure
        mode (a green run with no browser customization).
        """
        with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
            ForgeQAConfig(brower=BrowserConfig())  # noqa: E501

    # --- Literal validation -------------------------------------------------

    def test_invalid_log_level_is_rejected(self) -> None:
        """``log_level`` is a ``Literal``; ``"VERBOSE"`` is not in it."""
        with pytest.raises(ValidationError):
            GeneralConfig(log_level="VERBOSE")  # type: ignore[arg-type]

    def test_invalid_browser_name_is_rejected(self) -> None:
        """``browser_name`` is a ``Literal``; ``"edge"`` is not in it."""
        with pytest.raises(ValidationError):
            BrowserConfig(browser_name="edge")  # type: ignore[arg-type]

    # --- String constraints -------------------------------------------------

    def test_empty_environment_is_rejected(self) -> None:
        """``environment`` has ``min_length=1``; empty is invalid."""
        with pytest.raises(ValidationError):
            GeneralConfig(environment="")

    def test_empty_artifacts_dir_is_rejected(self) -> None:
        """``artifacts_dir`` has ``min_length=1``; empty is invalid."""
        with pytest.raises(ValidationError):
            GeneralConfig(artifacts_dir="")

    # --- URL constraints ----------------------------------------------------

    def test_invalid_base_url_is_rejected(self) -> None:
        """``base_url`` is ``AnyHttpUrl``; a bare string is rejected."""
        with pytest.raises(ValidationError):
            APIConfig(base_url="not-a-url")

    def test_ftp_base_url_is_rejected(self) -> None:
        """``AnyHttpUrl`` accepts only ``http`` and ``https``."""
        with pytest.raises(ValidationError):
            APIConfig(base_url="ftp://example.com")

    # --- Required-field absence --------------------------------------------

    def test_all_fields_have_defaults_so_empty_construction_succeeds(self) -> None:
        """The flip side of "every field has a default": the empty call works.

        This is the WBS 1.2.5 contract expressed as a test. If a future
        field is added **without** a default, this test fails and points
        the developer at ADR-011 §Reconsideration Trigger ("a new
        config field is proposed without a default").
        """
        cfg = ForgeQAConfig()
        # Touch every sub-model so a missing field anywhere is caught.
        assert cfg.general is not None
        assert cfg.browser is not None
        assert cfg.api is not None
        assert cfg.diagnostics is not None
        assert cfg.reporting is not None


# ===========================================================================
# Boundary: numeric ranges
# ===========================================================================


class TestBoundaries:
    """Inclusive-bound checks for ``timeout_ms`` and ``timeout_seconds``.

    Both fields are bounded; the boundaries are tested explicitly so a
    future relaxation or tightening of the bound is a deliberate change
    that updates these tests, not an accidental one that slips through.
    """

    # --- timeout_ms (browser) ----------------------------------------------

    def test_timeout_ms_minimum_is_one(self) -> None:
        """``timeout_ms=1`` is legal (useless, but legal).

        Rationale: the lower bound exists to reject ``0`` and negatives
        -- a zero timeout silently breaks Playwright's default-timeout
        resolution. A 1 ms timeout is not useful, but it is not a bug
        the model should reject; the user may be intentionally testing
        a very fast path.
        """
        assert BrowserConfig(timeout_ms=1).timeout_ms == 1

    def test_timeout_ms_below_minimum_is_rejected(self) -> None:
        """``timeout_ms=0`` and negatives are rejected."""
        with pytest.raises(ValidationError):
            BrowserConfig(timeout_ms=0)
        with pytest.raises(ValidationError):
            BrowserConfig(timeout_ms=-1)

    def test_timeout_ms_maximum_is_60000(self) -> None:
        """``timeout_ms=60_000`` is legal (the 1-minute boundary)."""
        assert BrowserConfig(timeout_ms=60_000).timeout_ms == 60_000

    def test_timeout_ms_above_maximum_is_rejected(self) -> None:
        """``timeout_ms=60_001`` is rejected.

        Rationale: 60 s is Playwright's own outer default and the
        upper bound of "a timeout that could plausibly be a per-action
        timeout". A larger value is more likely a units mistake (a user
        who meant seconds) than an intentional choice.
        """
        with pytest.raises(ValidationError):
            BrowserConfig(timeout_ms=60_001)

    # --- timeout_seconds (API) ---------------------------------------------

    def test_timeout_seconds_minimum_is_one(self) -> None:
        assert APIConfig(timeout_seconds=1).timeout_seconds == 1

    def test_timeout_seconds_below_minimum_is_rejected(self) -> None:
        with pytest.raises(ValidationError):
            APIConfig(timeout_seconds=0)

    def test_timeout_seconds_maximum_is_300(self) -> None:
        assert APIConfig(timeout_seconds=300).timeout_seconds == 300

    def test_timeout_seconds_above_maximum_is_rejected(self) -> None:
        """``timeout_seconds=300_001`` is rejected.

        Rationale: the upper bound catches a typo like ``300_000`` (a
        user thinking the field was in milliseconds).
        """
        with pytest.raises(ValidationError):
            APIConfig(timeout_seconds=300_001)


# ===========================================================================
# Non-functional: properties that matter to CI runtime and safety
# ===========================================================================


class TestNonFunctional:
    """Properties that are not about field values, but about the config object.

    These protect guarantees that are easy to lose in a refactor and
    that multiply across every test session -- so they are asserted, not
    just documented.
    """

    def test_construction_does_not_perform_io(self, tmp_path, monkeypatch) -> None:
        """Building ``ForgeQAConfig()`` must not touch the filesystem.

        Rationale: ``import forgeqa.config`` and config construction run
        on every test session; any I/O here multiplies across thousands
        of tests. See ADR-002 and ADR-010 Decision #3. The
        ``artifacts_dir`` validator explicitly does *not* create the
        directory; this test pins that.

        Runs in a ``tmp_path`` so the *only* files that could be
        created by a bug are visible to the assertion.
        """
        monkeypatch.chdir(tmp_path)
        before = set(tmp_path.iterdir())
        ForgeQAConfig()
        after = set(tmp_path.iterdir())
        assert before == after, f"config construction created files: {sorted(after - before)}"

    def test_construction_is_fast(self) -> None:
        """Constructing 1,000 default configs must take < 500 ms.

        Rationale: 500 ms is ~10x headroom over the current ~1 ms
        (measured on a cold venv under CPU contention during a full
        test run). A regression below that headroom is unambiguous --
        a validator that touches the filesystem, a default factory that
        reads a file, or an import that pulls in a heavy dependency
        would all push the time up by 10x or more. At thousands of
        tests that compounds into seconds of wasted CI time, so the
        budget is tight enough to catch real regressions and loose
        enough not to flake under CPU contention.

        History: an earlier 100 ms budget failed at 115 ms on a
        developer machine under full-suite load. The budget was relaxed
        to 500 ms to distinguish a real regression from normal CI
        variance (see ADR-011 §Lessons learnt).
        """
        start = time.perf_counter()
        for _ in range(1_000):
            ForgeQAConfig()
        elapsed = time.perf_counter() - start
        assert elapsed < 0.5, f"1000 constructions took {elapsed:.3f}s"

    def test_config_is_immutable(self) -> None:
        """Mutating a field after construction raises ``ValidationError``.

        Frozen models make the config safe to share across threads and
        pytest-xdist workers. Without freezing, a test that mutates
        ``cfg.general.log_level`` would silently leak the mutation into
        another test in the same xdist worker -- producing an
        unreproducible failure that only appears in a full suite run.
        """
        cfg = ForgeQAConfig()
        with pytest.raises(ValidationError):
            cfg.general.environment = "ci"  # type: ignore[misc]

    def test_config_is_hashable(self) -> None:
        """Frozen models are hashable, which means usable in sets / as dict keys.

        Not strictly required by WBS 1.2.5, but a useful non-functional
        property: it lets downstream code cache derived state keyed on
        the config (e.g. a session-scoped fixture that memoises an HTTP
        client per distinct config). If this ever fails, someone removed
        ``frozen=True``.
        """
        cfg = ForgeQAConfig()
        # Two equal instances must hash equal (consistency with __eq__).
        assert hash(cfg) == hash(ForgeQAConfig())
        assert cfg == ForgeQAConfig()
