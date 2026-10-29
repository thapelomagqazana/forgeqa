"""Map ``FORGEQA_``-prefixed environment variables to config overrides.

This module implements the **environment-variable layer** of the
configuration precedence hierarchy (WBS 1.2.3):

    CLI overrides  >  environment variables  >  forgeqa.toml  >  defaults

Each supported environment variable maps to a single ``(section, field)``
pair in the :class:`~forgeqa.config.ForgeQAConfig` schema. The mapping is
**explicit** and **auditable**: a contributor who adds a config field
either registers it in :data:`ENV_VAR_OVERRIDES` (with a test) or does
not, and if they do not, the field is simply not settable via an
environment variable.

Why explicit mapping instead of generic parsing
-----------------------------------------------
A generic parser (``FORGEQA_<SECTION>_<FIELD>`` → ``config.<section>.<field>``)
would be simpler to write but harder to audit:

* It would accept a typo like ``FORGEQA_BROWSR_HEADLESS`` as a valid
  attempt to set ``browsr.headless`` — which would then fail Pydantic
  validation with a confusing message, or worse, silently be ignored if
  the loader's error handling is lenient.
* It would make the *set* of supported environment variables invisible.
  With explicit mapping, ``grep ENV_VAR_OVERRIDES`` lists every var.
* It would silently accept a new env var for a new field without any
  test asserting its behaviour.

The trade-off: adding a field means editing this module (and its test)
in addition to the schema. That is intentional — the extra edit is
what makes the environment-variable surface a *contract* rather than an
implementation detail.

Unknown environment variables
-----------------------------
An environment variable starting with :data:`ENV_VAR_PREFIX` but not
listed in :data:`ENV_VAR_OVERRIDES` is **silently ignored**. This is the
standard convention for env-var-based configuration (Django, Rails,
Pydantic Settings): the environment is shared with other tools, and a
stray ``FORGEQA_*`` var (a leftover from a shell script, a typo in a CI
config) should not break the loader. A *known* var with an invalid value
raises :class:`~forgeqa.config.ForgeQAConfigError` naming the var.

CLI overrides are treated differently: unknown *keys* in the CLI-override
dict are **rejected** (see :func:`forgeqa.config.load_config`). A CLI
caller is code, not an environment; code typos should fail loudly.
"""

from __future__ import annotations

import os
from collections.abc import Mapping
from typing import Any, Final

from forgeqa.config.models import BrowserName, LogLevel

#: The prefix that identifies a ForgeQA environment variable. Kept as a
#: public constant so tests, documentation, and consumers can reference
#: the same value.
ENV_VAR_PREFIX: Final[str] = "FORGEQA_"

#: Mapping from environment variable name to the ``(section, field)`` it
#: configures.
#:
#: Keys are full environment variable names (including the prefix).
#: Values are ``(section_name, field_name)`` pairs matching the
#: :class:`~forgeqa.config.ForgeQAConfig` schema. The section name is
#: the attribute name on ``ForgeQAConfig`` (e.g. ``"browser"``);
#: the field name is the attribute on the sub-model (e.g.
#: ``"browser_name"``).
#:
#: **Adding a new entry** requires:
#: 1. A field on the corresponding sub-model (see ADR-007).
#: 2. An entry in this mapping.
#: 3. A test in ``tests/unit/config/test_precedence.py`` that
#:    exercises the new var's precedence over TOML.
#:
#: The mapping is intentionally *not* auto-derived from the schema. The
#: explicit list is the audit trail.
#:
#: **Value parsing.** The loader uses Pydantic's coercion for the
#: target field's type. So ``FORGEQA_BROWSER_HEADLESS=true`` parses to
#: ``True`` (Pydantic's bool coercion accepts ``"true"`` / ``"false"``
#: and the usual variants — see
#: :class:`~forgeqa.config.BrowserConfig` and
#: ``docs/engineering-standards.md`` §5.1 rule 1). A value that the
#: target field rejects raises ``ForgeQAConfigError`` naming the
#: environment variable.
ENV_VAR_OVERRIDES: Final[dict[str, tuple[str, str]]] = {
    # [general]
    "FORGEQA_GENERAL_ENVIRONMENT": ("general", "environment"),
    "FORGEQA_GENERAL_ARTIFACTS_DIR": ("general", "artifacts_dir"),
    "FORGEQA_GENERAL_LOG_LEVEL": ("general", "log_level"),
    # [browser]
    "FORGEQA_BROWSER_BROWSER_NAME": ("browser", "browser_name"),
    "FORGEQA_BROWSER_HEADLESS": ("browser", "headless"),
    "FORGEQA_BROWSER_BASE_URL": ("browser", "base_url"),
    "FORGEQA_BROWSER_TIMEOUT_MS": ("browser", "timeout_ms"),
    # [api]
    "FORGEQA_API_BASE_URL": ("api", "base_url"),
    "FORGEQA_API_TIMEOUT_SECONDS": ("api", "timeout_seconds"),
    # [diagnostics]
    "FORGEQA_DIAGNOSTICS_SCREENSHOTS": ("diagnostics", "screenshots"),
    "FORGEQA_DIAGNOSTICS_TRACES": ("diagnostics", "traces"),
    "FORGEQA_DIAGNOSTICS_CONSOLE_LOGS": ("diagnostics", "console_logs"),
    # [reporting]
    "FORGEQA_REPORTING_JUNIT_XML": ("reporting", "junit_xml"),
    "FORGEQA_REPORTING_JSON_REPORT": ("reporting", "json_report"),
}


def read_env_overrides(environ: Mapping[str, str] | None = None) -> dict[str, dict[str, Any]]:
    """Read ``FORGEQA_*`` environment variables as a config override dict.

    Parameters
    ----------
    environ
        The mapping to read from. Defaults to :data:`os.environ`. Pass
        an explicit mapping in tests to avoid mutating the real
        environment.

    Returns
    -------
    dict[str, dict[str, Any]]
        A nested dict shaped like ``ForgeQAConfig``'s constructor. For
        example, if ``FORGEQA_BROWSER_HEADLESS=false`` is set, the
        result is ``{"browser": {"headless": "false"}}``. The
        *values* are strings; type coercion happens in Pydantic when
        the dict is applied to the model. This is intentional: the
        env-var layer does not re-implement Pydantic's coercion rules;
        it hands raw strings to Pydantic and lets the model reject
        invalid values with its own error messages.

    Notes
    -----
    * Unknown ``FORGEQA_*`` variables are silently ignored. See the
      module docstring for the rationale.
    * The empty string (``FORGEQA_BROWSER_HEADLESS=``) is treated as
      a present variable with an empty value; Pydantic will reject it
      for typed fields. A caller who wants to unset a field should
      unset the env var, not set it empty.
    * The returned dict preserves only the *sections and fields* that
      have at least one set env var. Sections with no set env vars are
      omitted entirely, so a caller applying the dict via
      ``model_copy(update=...)`` does not accidentally override a
      section with an empty dict.
    """
    if environ is None:
        environ = os.environ

    # Group overrides by section, preserving the field names as
    # attributes of the nested dict.
    result: dict[str, dict[str, Any]] = {}
    for var_name, (section, field) in ENV_VAR_OVERRIDES.items():
        if var_name not in environ:
            continue
        result.setdefault(section, {})[field] = environ[var_name]
    return result


# Silence unused-import warnings for imports used only in type hints.
# The two Literal aliases document which schema fields the mapping
# targets; they are not used at runtime.
_ = BrowserName, LogLevel
