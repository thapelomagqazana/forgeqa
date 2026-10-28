"""ForgeQA configuration schema.

This package defines the strictly-typed Pydantic v2 models that represent
the ForgeQA configuration (see ``docs/configuration.md`` and ADR-008).

The public API is:

* :class:`ForgeQAConfig` — the root model; consumers pass this everywhere.
* :class:`GeneralConfig`, :class:`BrowserConfig`, :class:`APIConfig`,
  :class:`DiagnosticsConfig`, :class:`ReportingConfig` — the sub-models,
  available for consumers who want to construct a single section in
  isolation (e.g. in tests, or to type-check a partial config).
* :data:`BrowserName`, :data:`LogLevel` — the ``Literal`` aliases, for
  consumers who want to type their own helpers against the same value
  sets.

The implementation lives in :mod:`forgeqa.config.models`. Import from
:mod:`forgeqa.config` (this package), not from
:mod:`forgeqa.config.models` — the submodule is an implementation detail
and may be split into ``browser.py`` / ``api.py`` / etc. without a
breaking change. See ``docs/public-api.md`` for the public-API rules.
"""

from __future__ import annotations

from forgeqa.config.models import (
    APIConfig,
    BrowserConfig,
    BrowserName,
    DiagnosticsConfig,
    ForgeQAConfig,
    GeneralConfig,
    LogLevel,
    ReportingConfig,
)

__all__ = (
    "APIConfig",
    "BrowserConfig",
    "BrowserName",
    "DiagnosticsConfig",
    "ForgeQAConfig",
    "GeneralConfig",
    "LogLevel",
    "ReportingConfig",
)
