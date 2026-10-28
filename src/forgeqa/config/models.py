"""Pydantic v2 models for the ForgeQA configuration.

This module defines the **strictly typed configuration schema** that a
consumer's ``forgeqa.toml`` will be loaded into (see
``docs/configuration.md`` for the consumer-facing reference and
``ADR-008`` for the design decision).

Design principles:

1. **Strict typing.** Every field has a precise type. Constrained strings
   use ``Literal[...]``; URLs use ``AnyHttpUrl``; positive integers use
   ``PositiveInt``. A malformed value fails at parse time with a
   message that names the field and lists the valid values.
2. **Sensible defaults.** Every field has a default, so ``ForgeQAConfig()``
   is valid with no arguments. The defaults are the "when you don't
   configure anything" behaviour, and they are documented in
   ``docs/configuration.md``.
3. **Composition over inheritance.** The root model composes five
   sub-models; each sub-model owns one concern. A consumer can construct
   a single sub-model in isolation (e.g. in a test) without pulling in
   the others.
4. **Immutability.** ``ForgeQAConfig`` instances are frozen. A config
   object is a value, not a mutable bag of settings; passing it around
   cannot accidentally mutate it.
5. **Unknown keys are rejected.** ``extra="forbid"`` catches a typo like
   ``timout_ms`` at parse time, rather than silently using the default.
6. **Assignment validation.** ``validate_assignment=True`` means that
   even a caller who subclasses the model and unfreezes it cannot assign
   an invalid value without going through validation.

The models are intentionally **not** responsible for loading a file.
Loading a ``forgeqa.toml`` (environment overlays, secret resolution,
path expansion) is a separate concern and belongs in a follow-up module.
Separating the schema from the loader means the schema is testable
without files on disk, and the loader is testable without re-testing the
schema.
"""

from __future__ import annotations

from typing import Literal

from pydantic import (
    AnyHttpUrl,
    BaseModel,
    ConfigDict,
    Field,
    PositiveInt,
)

# ---------------------------------------------------------------------------
# Literal aliases (public, re-exported from forgeqa.config)
# ---------------------------------------------------------------------------

#: The set of browser engines that ForgeQA's UI adapter supports. Adding a
#: new browser engine is a code change (it requires a corresponding adapter
#: update), not a user-facing configuration change — which is why this is a
#: ``Literal`` and not an arbitrary ``str``.
BrowserName = Literal["chromium", "firefox", "webkit"]

#: The set of log levels that ForgeQA's diagnostics system emits. Matches
#: Python's :mod:`logging` levels; ``CRITICAL`` is deliberately excluded
#: because a CRITICAL log line in a test-runner context means the runner
#: itself is broken, not the test.
LogLevel = Literal["DEBUG", "INFO", "WARNING", "ERROR"]


# ---------------------------------------------------------------------------
# Sub-models
# ---------------------------------------------------------------------------


class GeneralConfig(BaseModel):
    """General ForgeQA configuration.

    Concern: identity of the run. Which environment are we in, where do
    artifacts go, at what log level should the framework emit. These are
    the settings that apply across all test types (UI, API, integration).

    All fields have defaults; see :mod:`forgeqa.config.models`'s module
    docstring for the "sensible defaults" principle.
    """

    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        str_strip_whitespace=True,
        validate_assignment=True,
        validate_default=True,
    )

    environment: str = Field(
        default="local",
        min_length=1,
        description=(
            "The environment this run targets. A free-form label such as "
            "'local', 'ci', 'staging', or 'production'. ForgeQA uses it "
            "to select environment-specific overlays when loading a "
            "config file (Phase 1) and to tag artifacts (Phase 3)."
        ),
    )

    artifacts_dir: str = Field(
        default="artifacts",
        min_length=1,
        description=(
            "Directory where ForgeQA writes diagnostic artifacts "
            "(screenshots, traces, JUnit XML, structured JSON). Relative "
            "to the working directory unless absolute. The directory is "
            "created on first write and never deleted automatically; "
            "retention is a Phase 3 concern."
        ),
    )

    log_level: LogLevel = Field(
        default="INFO",
        description=(
            "The framework's log level. Applied to the ``forgeqa`` "
            "logger, not the root logger — the consumer's own logging "
            "configuration is not affected. See "
            "``docs/configuration.md`` for what each level enables."
        ),
    )


class BrowserConfig(BaseModel):
    """Configuration for ForgeQA's UI (Playwright) adapter.

    Concern: how to launch a browser. Which engine, whether to run
    headless, how long to wait for navigation, and the base URL that
    relative navigation resolves against.

    This sub-model is only meaningful when ``forgeqa[ui]`` is installed;
    the model itself does not import Playwright, so it is safe to
    construct even in a core install (the ``browser`` fixture, when it
    lands in Phase 1, will assert that Playwright is available before
    trying to launch).
    """

    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        str_strip_whitespace=True,
        validate_assignment=True,
        validate_default=True,
    )

    browser_name: BrowserName = Field(
        default="chromium",
        description=(
            "The browser engine to use. One of 'chromium', 'firefox', "
            "'webkit'. Adding a new engine requires a corresponding "
            "ForgeQA adapter update; it is not a user-configurable "
            "choice."
        ),
    )

    headless: bool = Field(
        default=True,
        description=(
            "Whether to run the browser in headless mode. Headless is "
            "the default for CI and local automation; set to False for "
            "debugging in a real browser window."
        ),
    )

    base_url: AnyHttpUrl = Field(
        default=AnyHttpUrl("http://localhost:8000"),
        description=(
            "Base URL for relative navigation. Playwright's "
            "``page.goto('/foo')`` resolves against this. Must be an "
            "``http`` or ``https`` URL with a valid host. Note: "
            "Pydantic's ``AnyHttpUrl`` does not require a trailing "
            "slash; ForgeQA normalises when joining (Phase 1)."
        ),
    )

    timeout_ms: PositiveInt = Field(
        default=10_000,
        description=(
            "Default navigation and action timeout, in milliseconds. "
            "Must be strictly positive. Playwright's own default is "
            "30 000 ms; ForgeQA uses 10 000 to fail faster in CI. "
            "Individual actions may override this."
        ),
    )


class APIConfig(BaseModel):
    """Configuration for ForgeQA's API (HTTPX) adapter.

    Concern: how to talk to an HTTP API under test. Base URL, timeouts,
    and default headers.

    This sub-model is only meaningful when ``forgeqa[api]`` is installed;
    the model itself does not import HTTPX, so it is safe to construct
    even in a core install.
    """

    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        str_strip_whitespace=True,
        validate_assignment=True,
        validate_default=True,
    )

    base_url: AnyHttpUrl = Field(
        default=AnyHttpUrl("http://localhost:8000/api"),
        description=(
            "Base URL for API requests. Must be an ``http`` or "
            "``https`` URL. The ``api_client`` fixture (Phase 1) will "
            "resolve relative paths against this."
        ),
    )

    timeout_seconds: PositiveInt = Field(
        default=10,
        description=(
            "Default request timeout, in seconds. Must be strictly "
            "positive. HTTPX's own default is 5 s; ForgeQA uses 10 s "
            "to accommodate slow test environments. Individual requests "
            "may override this."
        ),
    )


class DiagnosticsConfig(BaseModel):
    """Configuration for what evidence ForgeQA captures on test execution.

    Concern: *capture*. Screenshots, traces, console logs. The
    counterpart is :class:`ReportingConfig`, which controls *emission*
    (JUnit XML, structured JSON). They are separate because a consumer
    might want full diagnostics but no JUnit XML (a local debugging
    run), or minimal diagnostics but full JUnit XML (a CI run that only
    needs pass/fail).

    Capture is opt-in per artifact type. All three are enabled by
    default because a test framework whose default is "capture nothing"
    provides no evidence when a test fails in CI.
    """

    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        str_strip_whitespace=True,
        validate_assignment=True,
        validate_default=True,
    )

    screenshots: bool = Field(
        default=True,
        description=(
            "Whether to capture a screenshot at the point of a UI "
            "test's failure. Requires ``forgeqa[ui]``. A "
            "``diagnostics.screenshots = false`` config disables "
            "screenshot capture for the whole run."
        ),
    )

    traces: bool = Field(
        default=True,
        description=(
            "Whether to capture a Playwright trace at the point of a "
            "UI test's failure. Traces are larger than screenshots "
            "(typically a few MB each) but contain the full browser "
            "interaction log, which is often necessary to diagnose a "
            "flaky test. Requires ``forgeqa[ui]``."
        ),
    )

    console_logs: bool = Field(
        default=True,
        description=(
            "Whether to capture browser console logs for UI tests. "
            "Requires ``forgeqa[ui]``. Console logs are the most "
            'common source of "why did this fail?" information for '
            "JavaScript-driven applications."
        ),
    )


class ReportingConfig(BaseModel):
    """Configuration for what ForgeQA emits as reports.

    Concern: *emission*. JUnit XML, structured JSON. The counterpart is
    :class:`DiagnosticsConfig`, which controls *capture*. See that model's
    docstring for the split.

    Emission is opt-in per report format. JUnit XML is enabled by
    default because it is the CI-native format; structured JSON is
    enabled by default because it is the durable, parseable artifact
    that outlives any particular CI's report UI.
    """

    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        str_strip_whitespace=True,
        validate_assignment=True,
        validate_default=True,
    )

    junit_xml: bool = Field(
        default=True,
        description=(
            "Whether to write a JUnit XML report to "
            "``general.artifacts_dir / 'junit.xml'``. The path is "
            "fixed; changing it requires a ForgeQA code change (Phase "
            "3 will add configurability)."
        ),
    )

    json_report: bool = Field(
        default=True,
        description=(
            "Whether to write a structured JSON report to "
            "``general.artifacts_dir / 'results.json'``. The schema is "
            "documented in ``docs/architecture.md`` (Phase 3)."
        ),
    )


# ---------------------------------------------------------------------------
# Root model
# ---------------------------------------------------------------------------


class ForgeQAConfig(BaseModel):
    """Root ForgeQA configuration.

    This is the single model consumers pass around. It composes the five
    sub-models, one per concern:

    * :class:`GeneralConfig` — run identity and artifacts location.
    * :class:`BrowserConfig` — how to launch a browser (UI adapter).
    * :class:`APIConfig` — how to talk to an HTTP API (API adapter).
    * :class:`DiagnosticsConfig` — what evidence to capture.
    * :class:`ReportingConfig` — what reports to emit.

    Construction with no arguments produces a fully-defaulted,
    valid configuration::

        >>> from forgeqa.config import ForgeQAConfig
        >>> cfg = ForgeQAConfig()
        >>> cfg.browser.browser_name
        'chromium'
        >>> cfg.general.environment
        'local'

    The model is frozen and forbids unknown keys. A typo in a
    ``forgeqa.toml`` file (e.g. ``[browser] timeout_ms = 10_000``
    instead of ``timeout_ms`` under a ``[browser]`` section that
    ForgeQA expects) fails at parse time with a message naming the
    offending key.

    Composition is structural: each sub-model is constructed from its
    own section of the ``forgeqa.toml`` (see ``docs/configuration.md``).
    The root model does not merge or reinterpret; it validates.
    """

    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        str_strip_whitespace=True,
        validate_assignment=True,
        validate_default=True,
        # Pydantic v2's default is to populate the JSON schema with the
        # field descriptions; leaving that on. No additional config
        # needed for that.
    )

    general: GeneralConfig = Field(
        default_factory=GeneralConfig,
        description="General run configuration (environment, artifacts, logs).",
    )

    browser: BrowserConfig = Field(
        default_factory=BrowserConfig,
        description="UI (Playwright) adapter configuration.",
    )

    api: APIConfig = Field(
        default_factory=APIConfig,
        description="API (HTTPX) adapter configuration.",
    )

    diagnostics: DiagnosticsConfig = Field(
        default_factory=DiagnosticsConfig,
        description="What evidence to capture on test execution.",
    )

    reporting: ReportingConfig = Field(
        default_factory=ReportingConfig,
        description="What reports to emit after test execution.",
    )
