"""Pydantic v2 models for the ForgeQA configuration.

This module defines the **strictly typed configuration schema** that a
consumer's ``forgeqa.toml`` will be loaded into (see
``docs/configuration.md`` for the consumer-facing reference and
``ADR-007`` for the design decision).

Design principles:

1. **Strict typing.** Every field has a precise type. Constrained strings
   use ``Literal[...]``; URLs use ``AnyHttpUrl``; bounded integers use
   ``Annotated[int, Field(ge=..., le=...)]``. A malformed value fails at
   parse time with a message that names the field and lists the valid
   values.
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
7. **Validation errors are human-readable.** Field-level constraints
   (``Annotated[int, Field(ge=..., le=...)]``) and custom validators
   (the ``artifacts_dir`` check) produce errors that the loader
   formats via :func:`forgeqa.config.errors.format_validation_error`
   into a single-line message naming the field, the constraint, and
   the offending value. No Pydantic traceback reaches the user. See
   ADR-010.
8. **Validation has no side effects.** The ``artifacts_dir``
   validator checks that the path *can* be created; it does **not**
   create it. A config that is loaded but never used does not touch
   the filesystem. See ADR-010 Decision #3.

The models are intentionally **not** responsible for loading a file.
Loading a ``forgeqa.toml`` (environment overlays, secret resolution,
path expansion) is a separate concern and belongs in the loader module.
Separating the schema from the loader means the schema is testable
without files on disk, and the loader is testable without re-testing the
schema.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Annotated, Literal

from pydantic import (
    AnyHttpUrl,
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
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

    The ``artifacts_dir`` field has a validator (see
    :meth:`_artifacts_dir_must_be_creatable`) that proves the path can
    be created. The validator does **not** create the directory.
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
            "created on first write; the validator checks that it *can* "
            "be created (nearest existing ancestor is writable) but does "
            "not create it. Never deleted automatically; retention is a "
            "Phase 3 concern."
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

    @field_validator("artifacts_dir", mode="after")
    @classmethod
    def _artifacts_dir_must_be_creatable(cls, value: str) -> str:
        """Ensure ``artifacts_dir`` is creatable (or already a directory).

        Parameters
        ----------
        value
            The candidate ``artifacts_dir`` string. Already whitespace-
            stripped by the model config.

        Returns
        -------
        str
            The value, unchanged. The validator is a check, not a
            transformation.

        Raises
        ------
        ValueError
            If ``value`` cannot be created as a directory. The message
            names the specific reason (parent does not exist, path is
            an existing file, parent is not writable) so the user can
            fix it without guessing.

        Notes
        -----
        The validator does **not** create the directory. It checks:

        1. If the path already exists as a **directory**, accept it.
        2. If the path already exists as a **file**, reject it (the
           user almost certainly meant a different path; silently
           accepting would fail later when ForgeQA tried to write
           into the file).
        3. If the path does not exist, walk up to the nearest existing
           ancestor and check that it is a directory and writable. If
           it is, ``mkdir(parents=True)`` would succeed, so the path
           is acceptable.
        4. If no existing ancestor is a directory, or the nearest one
           is not writable, reject with a specific message.

        The check is done on ``Path.resolve(strict=False)`` so that
        symlinks and relative paths are resolved the same way
        ``mkdir`` would resolve them.

        This is a check, not an action: validation has no side
        effects. See ADR-010 Decision #3.
        """
        # Resolve without requiring the path to exist; this also
        # normalises relative paths against the current working
        # directory, which is what the eventual `mkdir` will do.
        resolved = Path(value).resolve(strict=False)

        # 1. Existing directory: accept.
        if resolved.is_dir():
            return value

        # 2. Existing file: reject with a specific message.
        if resolved.exists():
            raise ValueError(
                f"artifacts_dir points at an existing file, not a directory: {resolved}"
            )

        # 3. Find the nearest existing ancestor and check it.
        parent = resolved.parent
        while not parent.exists() and parent != parent.parent:
            parent = parent.parent
        if not parent.is_dir():
            raise ValueError(
                f"artifacts_dir cannot be created: parent is not a directory: {parent}"
            )
        if not os.access(parent, os.W_OK):
            raise ValueError(f"artifacts_dir cannot be created: parent is not writable: {parent}")

        return value


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

    The ``timeout_ms`` field is bounded to ``[100, 60_000]``; values
    outside that range are rejected with a message naming the bound.
    See ADR-010 Decision #1.
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

    timeout_ms: Annotated[int, Field(ge=100, le=60_000)] = Field(
        default=10_000,
        description=(
            "Default navigation and action timeout, in milliseconds. "
            "Must be between 100 and 60000 (inclusive). Playwright's "
            "own default is 30 000 ms; ForgeQA uses 10 000 to fail "
            "faster in CI. Individual actions may override this."
        ),
    )


class APIConfig(BaseModel):
    """Configuration for ForgeQA's API (HTTPX) adapter.

    Concern: how to talk to an HTTP API under test. Base URL, timeouts,
    and default headers.

    This sub-model is only meaningful when ``forgeqa[api]`` is installed;
    the model itself does not import HTTPX, so it is safe to construct
    even in a core install.

    The ``timeout_seconds`` field is bounded to ``[1, 300]``; values
    outside that range are rejected with a message naming the bound.
    The upper bound catches a typo like ``300_000`` (a user thinking
    the field was in milliseconds). See ADR-010 Decision #1.
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

    timeout_seconds: Annotated[int, Field(ge=1, le=300)] = Field(
        default=10,
        description=(
            "Default request timeout, in seconds. Must be between 1 "
            "and 300 (inclusive). HTTPX's own default is 5 s; ForgeQA "
            "uses 10 s to accommodate slow test environments. "
            "Individual requests may override this."
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

    The ``traces`` field is a strict ``bool``. Pydantic accepts the
    usual string forms for a boolean (``"true"/"false"``,
    ``"yes"/"no"``, ``"on"/"off"``, ``"1"/"0"``, case-insensitive);
    ambiguous strings like ``"maybe"`` are rejected. See
    ``docs/configuration.md`` §"Boolean coercion".
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
            "flaky test. Requires ``forgeqa[ui]``. Must be a boolean; "
            "Pydantic accepts the usual string forms (see "
            "``docs/configuration.md`` §'Boolean coercion')."
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
