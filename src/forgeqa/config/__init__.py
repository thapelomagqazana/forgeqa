"""ForgeQA configuration schema and loader.

This package defines the strictly-typed Pydantic v2 models that represent
the ForgeQA configuration (see ``docs/configuration.md`` and ADR-007),
and the loader that reads a ``forgeqa.toml`` file into those models (see
ADR-008).

The public API is:

* :class:`ForgeQAConfig` — the root model; consumers pass this everywhere.
* :class:`GeneralConfig`, :class:`BrowserConfig`, :class:`APIConfig`,
  :class:`DiagnosticsConfig`, :class:`ReportingConfig` — the sub-models,
  available for consumers who want to construct a single section in
  isolation (e.g. in tests, or to type-check a partial config).
* :data:`BrowserName`, :data:`LogLevel` — the ``Literal`` aliases, for
  consumers who want to type their own helpers against the same value
  sets.
* :func:`load_config` — the loader. Reads ``forgeqa.toml`` from the
  current directory (or an explicit path) and returns a
  :class:`ForgeQAConfig`. Falls back to defaults if no file is present.
* :data:`DEFAULT_CONFIG_FILENAME` — the filename ``load_config``
  searches for (``"forgeqa.toml"``).
* :func:`find_config_path` — the file-search helper. Returns the
  absolute path to the config file in a directory, or ``None``.
* :class:`ForgeQAConfigError` — the exception raised by
  :func:`load_config` for malformed TOML, invalid config values, or a
  missing explicit path.

The implementation lives in :mod:`forgeqa.config.models` (schema),
:mod:`forgeqa.config.loader` (loader), and :mod:`forgeqa.config.errors`
(exceptions). Import from :mod:`forgeqa.config` (this package), not from
the submodules — they are implementation details and may be split or
reorganised without a breaking change. See ``docs/public-api.md`` for
the public-API rules.
"""

from __future__ import annotations

from forgeqa.config.errors import ForgeQAConfigError
from forgeqa.config.loader import DEFAULT_CONFIG_FILENAME, find_config_path, load_config
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
    "DEFAULT_CONFIG_FILENAME",
    "DiagnosticsConfig",
    "ForgeQAConfig",
    "ForgeQAConfigError",
    "GeneralConfig",
    "LogLevel",
    "ReportingConfig",
    "find_config_path",
    "load_config",
)
