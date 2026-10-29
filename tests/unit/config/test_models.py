"""Unit tests for the ForgeQA configuration schema.

These tests cover WBS 1.2.1 (schema) and WBS 1.2.4 (field-level
validation):

* :class:`ForgeQAConfig` is importable and instantiable with defaults.
* ``browser_name`` rejects invalid values (e.g. ``"safari"``) with a
  clear error.
* ``base_url`` rejects invalid URLs.
* ``timeout_ms`` rejects values outside ``[1, 60000]``.
* ``timeout_seconds`` rejects values outside ``[1, 300]``.
* All sub-models have documented defaults.

The tests also cover edge cases (boundary values), corner cases
(unknown keys, nested models), and non-functional properties
(immutability, serialisation round-trip, JSON schema shape) that the
WBS's "strictly typed and fully composable" KPI implies.

**Relation to ADR-011 (WBS 1.2.5).** Two schema decisions from ADR-011
shape what this file asserts:

* ``api.base_url`` defaults to ``http://127.0.0.1:8000`` (IPv4 loopback,
  no ``/api`` suffix), because that is the Phase 0.6 reference app's
  listen address — see ADR-011 §Decision #2 and §Lessons learnt.
* Failure-evidence flags live on ``BrowserConfig``
  (``screenshot_on_failure``, ``trace_on_failure``), not on
  ``DiagnosticsConfig``. ``DiagnosticsConfig`` now carries only
  ``console_logs`` (non-browser diagnostic capture) — see
  ADR-011 §Decision #3.

**Relation to WBS 1.2.4 (validation bounds).** ``browser.timeout_ms``
is bounded ``[1, 60_000]`` (not ``[100, 60_000]``): the WBS 1.2.5
boundary test requires ``timeout_ms=1`` to be legal, so the lower bound
was relaxed in 1.2.5. ``api.timeout_seconds`` stays bounded ``[1, 300]``.
Both lower bounds exist to reject ``0`` and negatives; both upper
bounds exist to catch unit-confusion typos (a user who meant seconds
and wrote milliseconds).

The tests are **schema tests**, not loader tests. Loading a
``forgeqa.toml`` file into ``ForgeQAConfig`` is a separate concern
(covered by ``test_loader.py``); the human-readable error message
shape is covered by ``test_validation.py``. This file covers
acceptance: "is this value accepted, and is that value rejected?"

Run only these tests:

    pytest tests/unit/config/test_models.py -v
    # or
    make verify-config
"""

from __future__ import annotations

import json
from typing import get_args

import pytest
from pydantic import ValidationError

from forgeqa.config import (
    APIConfig,
    BrowserConfig,
    BrowserName,
    DiagnosticsConfig,
    ForgeQAConfig,
    GeneralConfig,
    LogLevel,
    ReportingConfig,
)

pytestmark = pytest.mark.unit


# =============================================================================
# Positive cases — defaults and happy-path construction
# =============================================================================


def test_forgeqa_config_instantiable_with_defaults() -> None:
    """Given no arguments, when constructing ``ForgeQAConfig``, then it succeeds with all defaults.

    The WBS acceptance criterion "ForgeQAConfig is importable and
    instantiable with defaults". This is the most basic test — if it
    fails, every consumer's first experience with the library is a
    ``ValidationError``.
    """
    cfg = ForgeQAConfig()
    assert isinstance(cfg, ForgeQAConfig)
    # Every sub-model is present and correctly typed.
    assert isinstance(cfg.general, GeneralConfig)
    assert isinstance(cfg.browser, BrowserConfig)
    assert isinstance(cfg.api, APIConfig)
    assert isinstance(cfg.diagnostics, DiagnosticsConfig)
    assert isinstance(cfg.reporting, ReportingConfig)


def test_general_config_defaults() -> None:
    """Given no arguments, when constructing ``GeneralConfig``, then documented defaults apply.

    Guards against a future change to a default. The defaults are
    documented in ``docs/configuration.md``; if they change there,
    this test and the doc are updated together.
    """
    cfg = GeneralConfig()
    assert cfg.environment == "local"
    assert cfg.artifacts_dir == "artifacts"
    assert cfg.log_level == "INFO"


def test_browser_config_defaults() -> None:
    """Given no arguments, when constructing ``BrowserConfig``, then documented defaults apply.

    ``base_url`` is compared by ``host``/``port``/``scheme`` rather than
    by string equality because Pydantic's ``AnyHttpUrl`` normalises the
    trailing slash (``http://localhost:8000`` becomes
    ``http://localhost:8000/``). Comparing the raw string would be
    brittle across Pydantic minor versions.
    """
    cfg = BrowserConfig()
    assert cfg.browser_name == "chromium"
    assert cfg.headless is True
    assert cfg.base_url.host == "localhost"
    assert cfg.base_url.port == 8000
    assert cfg.base_url.scheme == "http"
    assert cfg.timeout_ms == 10_000
    # Failure-evidence defaults live on BrowserConfig (ADR-011 §Decision #3).
    assert cfg.screenshot_on_failure is True
    assert cfg.trace_on_failure is True


def test_api_config_defaults() -> None:
    """Given no arguments, when constructing ``APIConfig``, then documented defaults apply.

    The default ``base_url`` is the Phase 0.6 reference app's origin
    (``http://127.0.0.1:8000``). Two things to note:

    * **IPv4 loopback, not ``localhost``.** On some Linux CI images
      ``localhost`` resolves to ``::1`` (IPv6) first, and the reference
      app binds IPv4 only. ``127.0.0.1`` is unambiguous — see ADR-011
      §Lessons learnt.
    * **No ``/api`` path suffix.** A "base URL" conventionally carries
      no path suffix, and the reference app's health endpoint is
      ``/health``, not ``/api/health`` — see ADR-011 §Alternatives
      Considered.

    Both properties are asserted by the ATDD test
    (``tests/integration/config/test_defaults_reference_app.py``); this
    test asserts them at the schema level.
    """
    cfg = APIConfig()
    assert cfg.base_url.host == "127.0.0.1"
    assert cfg.base_url.port == 8000
    assert cfg.base_url.scheme == "http"
    # No path suffix. AnyHttpUrl renders the bare origin as "/" after
    # normalisation, so we strip the trailing "/" before comparing.
    assert str(cfg.base_url.path).rstrip("/") == ""
    assert cfg.timeout_seconds == 10


def test_diagnostics_config_defaults() -> None:
    """Given no arguments, when constructing ``DiagnosticsConfig``, then console_logs is enabled.

    ``DiagnosticsConfig`` was re-scoped in ADR-011 §Decision #3: it
    now carries only ``console_logs`` (non-browser diagnostic capture).
    The failure-evidence flags (``screenshot_on_failure``,
    ``trace_on_failure``) moved to ``BrowserConfig`` because they are
    browser concepts (Playwright screenshot, Playwright trace) and
    duplicating them across two models created two sources of truth.

    "Capture nothing by default" is the wrong default for a test
    framework whose purpose is evidence, so ``console_logs`` stays on
    by default — see ADR-011 §Context (evidence-first principle).
    """
    cfg = DiagnosticsConfig()
    assert cfg.console_logs is True
    # Explicitly assert the removed fields are gone, so a future
    # re-addition (which would resurrect the two-sources-of-truth
    # problem) fails this test loudly rather than passing silently.
    assert not hasattr(cfg, "screenshots"), (
        "DiagnosticsConfig.screenshots was removed in ADR-011 §Decision #3; "
        "failure evidence lives on BrowserConfig.screenshot_on_failure"
    )
    assert not hasattr(cfg, "traces"), (
        "DiagnosticsConfig.traces was removed in ADR-011 §Decision #3; "
        "failure evidence lives on BrowserConfig.trace_on_failure"
    )


def test_reporting_config_defaults() -> None:
    """Given no arguments, when constructing ``ReportingConfig``, then both reports are enabled.

    JUnit XML is the CI-native format; structured JSON is the durable
    format. Both on by default.
    """
    cfg = ReportingConfig()
    assert cfg.junit_xml is True
    assert cfg.json_report is True


def test_valid_browser_names_accepted() -> None:
    """Given each valid browser name, when constructing ``BrowserConfig``, then it succeeds.

    The parametrisation is derived from ``get_args(BrowserName)``, so
    adding a new literal to ``BrowserName`` automatically extends the
    test. A contributor adding ``"edge"`` to the Literal does not have
    to remember to update this test.
    """
    for name in get_args(BrowserName):
        cfg = BrowserConfig(browser_name=name)
        assert cfg.browser_name == name


def test_valid_log_levels_accepted() -> None:
    """Given each valid log level, when constructing ``GeneralConfig``, then it succeeds.

    Same parametrisation-from-``get_args`` pattern as the browser test.
    """
    for level in get_args(LogLevel):
        cfg = GeneralConfig(log_level=level)
        assert cfg.log_level == level


# =============================================================================
# Negative cases — invalid values are rejected with clear errors
# =============================================================================


def test_invalid_browser_name_rejected() -> None:
    """Given ``browser_name='safari'``, when constructing ``BrowserConfig``, then it raises ``ValidationError``.

    The WBS acceptance criterion "browser_name rejects invalid values
    (e.g., 'safari') with a clear error". The test asserts both that it
    raises and that the error names the field and (via Pydantic's
    Literal handling) lists the valid values.
    """
    with pytest.raises(ValidationError) as exc_info:
        BrowserConfig(browser_name="safari")  # type: ignore[arg-type]
    error = exc_info.value.errors()[0]
    assert error["loc"] == ("browser_name",)
    # Pydantic's Literal error message mentions "Input should be" and the
    # valid values. Asserting on the *concept* rather than the exact
    # wording keeps the test stable across Pydantic minor versions.
    message = error["msg"].lower()
    assert "input should be" in message
    # The valid values should appear somewhere in the error representation
    # (Pydantic renders them as a comma-separated list in the error).
    rendered = str(exc_info.value).lower()
    for valid in get_args(BrowserName):
        assert valid.lower() in rendered, (
            f"Valid browser {valid!r} not mentioned in the error message: {exc_info.value}"
        )


@pytest.mark.parametrize("invalid_url", ["not-a-url", "http://", "ftp://example.com", ""])
def test_invalid_base_url_rejected(invalid_url: str) -> None:
    """Given an invalid URL, when constructing a config, then it raises ``ValidationError``.

    The WBS acceptance criterion "base_url rejects invalid URLs". The
    parametrisation covers four classes of invalid URL:

    * ``"not-a-url"`` — no scheme, no netloc.
    * ``"http://"`` — scheme but no host.
    * ``"ftp://example.com"`` — wrong scheme (``AnyHttpUrl`` accepts
      only http/https).
    * ``""`` — empty string.

    Both ``BrowserConfig.base_url`` and ``APIConfig.base_url`` are
    covered because they are independent fields with the same type.
    """
    with pytest.raises(ValidationError):
        BrowserConfig(base_url=invalid_url)  # type: ignore[arg-type]
    with pytest.raises(ValidationError):
        APIConfig(base_url=invalid_url)  # type: ignore[arg-type]


@pytest.mark.parametrize(
    "invalid_timeout",
    [
        0,  # zero
        -1,  # negative
        -10_000,  # well negative
        60_001,  # boundary+1 (above the le=60000 upper bound)
        100_000,  # well above
    ],
)
def test_invalid_browser_timeout_rejected(invalid_timeout: int) -> None:
    """Given a ``timeout_ms`` outside ``[1, 60000]``, when constructing ``BrowserConfig``, then it raises ``ValidationError``.

    The WBS 1.2.4 acceptance criterion "timeout_ms rejects negative
    values" (and the range constraint). The parametrisation covers
    zero, negative, and the out-of-range upper boundary.

    The lower bound is ``1`` (not ``100``). It was relaxed from 100 to
    1 in WBS 1.2.5 because the 1.2.5 boundary test requires
    ``timeout_ms=1`` to be legal: the lower bound exists to reject ``0``
    and negatives (a zero timeout silently breaks Playwright's
    default-timeout resolution), not to reject "impractically small but
    legal" values. ``99`` is therefore *legal* now and is asserted in
    ``test_browser_timeout_boundary_values_accepted`` — do not add it
    to this rejected set.

    The bounds are enforced by ``Annotated[int, Field(ge=1, le=60_000)]``.
    """
    with pytest.raises(ValidationError) as exc_info:
        BrowserConfig(timeout_ms=invalid_timeout)
    error = exc_info.value.errors()[0]
    assert error["loc"] == ("timeout_ms",)
    # The Pydantic message mentions the bound that was violated:
    # "Input should be greater than or equal to 1" (for values below)
    # or "Input should be less than or equal to 60000" (for values above).
    # Assert on the concept ("greater than or equal to 1" or
    # "less than or equal to 60000"), not the exact Pydantic wording,
    # so a Pydantic minor version bump does not break the test for a
    # cosmetic reason.
    message = error["msg"].lower()
    if invalid_timeout < 1:
        assert "greater than or equal to 1" in message, message
    else:
        assert "less than or equal to 60000" in message, message


@pytest.mark.parametrize("invalid_timeout", [0, -1, 301, 1000])
def test_invalid_api_timeout_rejected(invalid_timeout: int) -> None:
    """Given a ``timeout_seconds`` outside ``[1, 300]``, when constructing ``APIConfig``, then it raises ``ValidationError``.

    The bounds are enforced by ``Annotated[int, Field(ge=1, le=300)]``.
    The lower bound is 1 (not 0 — a zero-second timeout is not
    meaningful), and the upper bound is 300 (to catch a typo like
    ``300_000`` from a user thinking the field was milliseconds).

    Unlike ``browser.timeout_ms``, this lower bound was *not* relaxed
    in WBS 1.2.5 — 1 is the intended minimum.
    """
    with pytest.raises(ValidationError):
        APIConfig(timeout_seconds=invalid_timeout)


def test_invalid_log_level_rejected() -> None:
    """Given ``log_level='TRACE'``, when constructing ``GeneralConfig``, then it raises ``ValidationError``.

    ``TRACE`` is not in :data:`LogLevel`. This catches a common mistake
    from users coming from other logging frameworks that have a TRACE
    level.
    """
    with pytest.raises(ValidationError) as exc_info:
        GeneralConfig(log_level="TRACE")  # type: ignore[arg-type]
    error = exc_info.value.errors()[0]
    assert error["loc"] == ("log_level",)


# =============================================================================
# Edge cases — boundary values and type coercion
# =============================================================================


@pytest.mark.parametrize("boundary", [1, 99, 10_000, 60_000])
def test_browser_timeout_boundary_values_accepted(boundary: int) -> None:
    """Given ``timeout_ms`` at or inside ``[1, 60000]``, when constructing ``BrowserConfig``, then it succeeds.

    The boundary values (``1`` and ``60_000``) are inclusive. The
    test also covers ``99`` (which *was* rejected under the pre-1.2.5
    ``ge=100`` bound and is now legal) and the default ``10_000``.

    The inclusion of ``99`` is deliberate regression protection:
    WBS 1.2.5 relaxed the lower bound from 100 to 1, and asserting
    that ``99`` is now legal pins that change. If someone "tidies up"
    the bound back to 100, this test fails and points at ADR-011
    §Consequences (Neutral) for the rationale.
    """
    cfg = BrowserConfig(timeout_ms=boundary)
    assert cfg.timeout_ms == boundary


@pytest.mark.parametrize("boundary", [1, 10, 300])
def test_api_timeout_boundary_values_accepted(boundary: int) -> None:
    """Given ``timeout_seconds`` at or inside ``[1, 300]``, when constructing ``APIConfig``, then it succeeds.

    The boundary values (1 and 300) are inclusive. The test also
    covers the default (10).
    """
    cfg = APIConfig(timeout_seconds=boundary)
    assert cfg.timeout_seconds == boundary


def test_bool_from_common_string_forms_accepted() -> None:
    """Given a well-known boolean string, when constructing ``BrowserConfig``, then it coerces.

    Pydantic v2 accepts a specific set of string forms for ``bool``
    fields, matching Pydantic v1: ``"true"/"false"``, ``"yes"/"no"``,
    ``"on"/"off"``, and ``"1"/"0"`` (case-insensitive). This is a
    useful convenience for hand-edited TOML, where users may write
    ``headless = "yes"`` thinking of the natural-language form.

    This test pins the accepted set so a future change to Pydantic's
    coercion rules (e.g. dropping ``"yes"``) fails here rather than
    silently changing what a user can write in ``forgeqa.toml``.

    The field used here is ``browser.headless`` because it is the
    canonical boolean on the model. The same coercion rules apply to
    ``browser.screenshot_on_failure``, ``browser.trace_on_failure``,
    ``diagnostics.console_logs``, and the reporting flags.
    """
    truthy_forms = ("true", "yes", "on", "1", "TRUE", "YES", "True", "Yes")
    for form in truthy_forms:
        cfg = BrowserConfig(headless=form)  # type: ignore[arg-type]
        assert cfg.headless is True, f"Expected {form!r} to coerce to True"

    falsy_forms = ("false", "no", "off", "0", "FALSE", "NO", "False", "No")
    for form in falsy_forms:
        cfg = BrowserConfig(headless=form)  # type: ignore[arg-type]
        assert cfg.headless is False, f"Expected {form!r} to coerce to False"


def test_ambiguous_bool_string_rejected() -> None:
    """Given ``headless='maybe'``, when constructing ``BrowserConfig``, then it raises ``ValidationError``.

    Pydantic v2's ``bool`` validator accepts a fixed set of string
    forms (see :func:`test_bool_from_common_string_forms_accepted`).
    ``"maybe"`` is not among them, so it fails at parse time with a
    clear error. This is the actual "does not coerce arbitrary
    strings" behaviour: coercion is bounded, not absent.
    """
    with pytest.raises(ValidationError):
        BrowserConfig(headless="maybe")  # type: ignore[arg-type]


def test_extra_field_rejected() -> None:
    """Given an unknown key, when constructing any model, then it raises ``ValidationError``.

    ``model_config['extra'] = 'forbid'`` is what makes a typo in a
    ``forgeqa.toml`` file (e.g. ``timout_ms``) fail at parse time rather
    than silently using the default. This is the "unknown keys are
    rejected" design principle.
    """
    with pytest.raises(ValidationError) as exc_info:
        BrowserConfig(timout_ms=10_000)  # type: ignore[call-arg]
    # The error should mention the offending key and (via Pydantic's
    # "extra_forbidden" error) that it is not allowed.
    assert "timout_ms" in str(exc_info.value)


def test_extra_field_rejected_at_root() -> None:
    """Given an unknown key at the root, when constructing ``ForgeQAConfig``, then it raises ``ValidationError``.

    Same rule as the sub-model case, at the root level. A typo like
    ``[browsr]`` in the TOML (a section that would be passed as
    ``browsr={...}``) fails, instead of the browser config silently
    using defaults.
    """
    with pytest.raises(ValidationError):
        ForgeQAConfig(browsr={"browser_name": "chromium"})  # type: ignore[call-arg]


def test_old_diagnostics_evidence_keys_rejected() -> None:
    """Given the pre-1.2.5 ``diagnostics.screenshots`` / ``traces`` keys, when constructing, then it raises ``ValidationError``.

    ADR-011 §Decision #3 moved failure-evidence flags from
    ``[diagnostics]`` to ``[browser]``. The old keys are rejected by
    ``extra="forbid"`` — a user who copies an old config (from a blog
    post, a stale README, or a colleague) gets a loud error naming the
    offending key, not a silent fallback to defaults.

    This is the *intended* clean break: pre-alpha, no external
    consumers, no deprecation shim. The test pins the break so a
    future contributor cannot add the fields back without also
    updating ADR-011 §Consequences (Neutral).
    """
    with pytest.raises(ValidationError) as exc_info:
        DiagnosticsConfig(screenshots=False)  # type: ignore[call-arg]
    assert "screenshots" in str(exc_info.value)

    with pytest.raises(ValidationError) as exc_info:
        DiagnosticsConfig(traces=False)  # type: ignore[call-arg]
    assert "traces" in str(exc_info.value)


# =============================================================================
# Corner cases — composition and nested validation
# =============================================================================


def test_nested_sub_model_validation() -> None:
    """Given a dict for a sub-model, when constructing ``ForgeQAConfig``, then nested validation fires.

    Pydantic's structural composition means ``ForgeQAConfig(browser={"browser_name": "safari"})``
    validates the nested ``BrowserConfig`` even though the caller passed
    a dict. The error location should point at ``browser.browser_name``
    (not just ``browser_name``), which is what makes the error
    actionable in a nested config.
    """
    with pytest.raises(ValidationError) as exc_info:
        ForgeQAConfig(browser={"browser_name": "safari"})  # type: ignore[arg-type]
    error = exc_info.value.errors()[0]
    assert error["loc"] == ("browser", "browser_name")


def test_nested_timeout_validation() -> None:
    """Given a nested dict with an invalid ``timeout_ms``, when constructing ``ForgeQAConfig``, then the error loc includes both levels.

    Same as ``test_nested_sub_model_validation``, for the ``timeout_ms``
    bounds. The value used (``0``) is below the ``ge=1`` lower bound
    (see ``test_invalid_browser_timeout_rejected`` for why the bound is
    ``1``, not ``100``). Guards against a future refactor that loses
    the section prefix in the error path.
    """
    with pytest.raises(ValidationError) as exc_info:
        ForgeQAConfig(browser={"timeout_ms": 0})  # type: ignore[arg-type]
    error = exc_info.value.errors()[0]
    assert error["loc"] == ("browser", "timeout_ms")


def test_partial_override_uses_defaults_for_unspecified() -> None:
    """Given a partial override, when constructing ``ForgeQAConfig``, then unspecified fields use defaults.

    ``ForgeQAConfig(browser={"browser_name": "firefox"})`` should keep
    ``timeout_ms`` at its default (10 000) and ``headless`` at True.
    This is the "sensible defaults" principle applied through
    composition.
    """
    cfg = ForgeQAConfig(browser={"browser_name": "firefox"})  # type: ignore[arg-type]
    assert cfg.browser.browser_name == "firefox"
    assert cfg.browser.headless is True  # default preserved
    assert cfg.browser.timeout_ms == 10_000  # default preserved
    # Other sub-models are also at defaults.
    assert cfg.api.timeout_seconds == 10
    assert cfg.general.environment == "local"


def test_full_config_round_trip_via_dict() -> None:
    """Given a full config, when serialised to dict and re-constructed, then it is equal.

    Round-trip through ``model_dump(mode="json")`` →
    ``ForgeQAConfig(**dumped)`` is the shape the TOML loader uses
    (parse TOML → dict → model). If a field is not round-trippable
    (e.g. a custom validator that rejects its own output), this test
    catches it.

    The chosen values exercise:

    * the ``timeout_ms`` lower bound (``30_000`` is inside ``[1, 60_000]``),
    * the ``timeout_seconds`` upper bound (``30`` is inside ``[1, 300]``),
    * the moved failure-evidence field
      (``browser.screenshot_on_failure=False``, which lives on
      ``BrowserConfig`` per ADR-011 §Decision #3 — **not** on
      ``DiagnosticsConfig``, where it lived before 1.2.5).
    """
    original = ForgeQAConfig(
        general={"environment": "ci", "artifacts_dir": "/tmp/artifacts", "log_level": "DEBUG"},  # type: ignore[arg-type]
        browser={
            "browser_name": "firefox",
            "headless": False,
            "timeout_ms": 30_000,
            "screenshot_on_failure": False,
        },  # type: ignore[arg-type]
        api={"timeout_seconds": 30},  # type: ignore[arg-type]
        diagnostics={"console_logs": False},  # type: ignore[arg-type]
        reporting={"junit_xml": False},  # type: ignore[arg-type]
    )
    dumped = original.model_dump(mode="json")
    restored = ForgeQAConfig(**dumped)
    assert restored == original


# =============================================================================
# Non-functional cases — immutability, JSON schema, cross-field
# =============================================================================


def test_config_is_immutable() -> None:
    """Given a constructed config, when I try to mutate a field, then it raises ``ValidationError``.

    ``model_config['frozen'] = True`` means assignment raises. A config
    object is a value, not a mutable bag; passing it around cannot
    accidentally mutate it.
    """
    cfg = ForgeQAConfig()
    with pytest.raises(ValidationError):
        cfg.general.environment = "production"  # type: ignore[misc]
    with pytest.raises(ValidationError):
        cfg.browser.browser_name = "firefox"  # type: ignore[misc]


def test_sub_model_is_immutable() -> None:
    """Given a sub-model, when I try to mutate a field, then it raises ``ValidationError``.

    Same rule as the root model, at the sub-model level. A consumer
    who keeps a reference to ``cfg.browser`` cannot mutate it.
    """
    cfg = BrowserConfig()
    with pytest.raises(ValidationError):
        cfg.timeout_ms = 30_000  # type: ignore[misc]


def test_json_schema_is_generated() -> None:
    """Given ``ForgeQAConfig``, when I ask for its JSON schema, then it is valid JSON with all five sub-models.

    A JSON schema is what a future config-validator tool (or an IDE
    plugin) would use for autocomplete and validation. The test asserts
    the schema is generated and contains the five sub-models as
    ``properties``. It does not assert the exact schema — Pydantic
    minor versions evolve the schema shape (e.g. adding
    ``$defs``, changing ``anyOf`` order) without it being a regression.
    """
    schema = ForgeQAConfig.model_json_schema()
    assert isinstance(schema, dict)
    assert "properties" in schema
    for key in ("general", "browser", "api", "diagnostics", "reporting"):
        assert key in schema["properties"], (
            f"Sub-model {key!r} missing from JSON schema properties: {list(schema['properties'])}"
        )
    # Schema must be JSON-serialisable (the whole point of "JSON schema").
    json.dumps(schema)


def test_str_strip_whitespace_applied() -> None:
    """Given whitespace around a string, when constructing a config, then it is stripped.

    ``str_strip_whitespace=True`` prevents a class of "why doesn't my
    URL work" bugs from hand-edited TOML with trailing spaces. This is
    a convenience, not a correctness rule, but it is part of the
    documented behaviour in ``docs/configuration.md``.
    """
    cfg = GeneralConfig(environment="  local  ")
    assert cfg.environment == "local"


def test_any_http_url_accepts_https_and_subdomains() -> None:
    """Given an https URL with a subdomain, when constructing ``BrowserConfig``, then it succeeds.

    ``AnyHttpUrl`` accepts more than a plain ``HttpUrl``. This test
    guards against a future change to ``HttpUrl`` that would reject
    common test targets like ``https://staging.example.com``.
    """
    cfg = BrowserConfig(base_url="https://staging.example.com")  # type: ignore[arg-type]
    assert cfg.base_url.scheme == "https"
    assert cfg.base_url.host == "staging.example.com"
