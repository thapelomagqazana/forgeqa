"""ForgeQA configuration schema, loader, and precedence hierarchy.

This package defines the strictly-typed Pydantic v2 models that represent
the ForgeQA configuration (see ``docs/configuration.md`` and ADR-007),
the loader that reads a ``forgeqa.toml`` file into those models and
applies the four-layer precedence hierarchy (see ADR-008 and ADR-009),
and the environment-variable mapping that feeds the env layer.

**Safe defaults (WBS 1.2.5, ADR-011).** Every field in every model has
an explicit, safe default, so ``ForgeQAConfig()`` is valid with no
arguments and with no ``forgeqa.toml`` present. The defaults are chosen
so a fresh install is runnable against the Phase 0.6 reference app
without modification — in particular, ``api.base_url`` defaults to
``http://127.0.0.1:8000`` (the reference app's listen address, chosen
over ``localhost`` to avoid IPv6 resolution surprises on Linux CI
images). Every default is documented in ``docs/configuration.md`` §
"Defaults", asserted one-per-field in
``tests/unit/config/test_defaults.py``, and validated end-to-end in
``tests/integration/config/test_defaults_reference_app.py``. A change
to any default must update all three together.

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
  current directory (or an explicit path), applies the precedence
  hierarchy CLI > env > TOML > defaults, and returns a
  :class:`ForgeQAConfig`. Falls back to defaults if no file is present
  and no overrides are set — see "Safe defaults" above.
* :data:`DEFAULT_CONFIG_FILENAME` — the filename ``load_config``
  searches for (``"forgeqa.toml"``).
* :func:`find_config_path` — the file-search helper. Returns the
  absolute path to the config file in a directory, or ``None``.
* :data:`ENV_VAR_PREFIX` — the prefix that identifies a ForgeQA
  environment variable (``"FORGEQA_"``).
* :data:`ENV_VAR_OVERRIDES` — the explicit mapping from environment
  variable name to ``(section, field)``. Every supported env var is
  listed here.
* :func:`read_env_overrides` — read ``FORGEQA_*`` env vars as a nested
  config-override dict. Unknown vars are ignored.
* :class:`ForgeQAConfigError` — the exception raised by
  :func:`load_config` for malformed TOML, invalid config values, a
  missing explicit path, or an invalid env var / CLI override.

The implementation lives in :mod:`forgeqa.config.models` (schema),
:mod:`forgeqa.config.loader` (loader), :mod:`forgeqa.config.env`
(environment-variable mapping), and :mod:`forgeqa.config.errors`
(exceptions). Import from :mod:`forgeqa.config` (this package), not from
the submodules — they are implementation details and may be split or
reorganised without a breaking change. See ``docs/public-api.md`` for
the public-API rules, and ``docs/configuration.md`` §"Precedence" for
the four-layer hierarchy.

**Import cost.** ``import forgeqa.config`` is cheap and side-effect
free: it imports ``pydantic`` (a core dependency), ``tomllib`` (stdlib),
and ``os`` (stdlib), but does **not** read any files, does **not**
read the environment, and does **not** import Playwright, HTTPX, or
Pytest. The expensive work happens only when :func:`load_config` is
called. This is asserted by
``tests/unit/config/test_defaults.py::TestNonFunctional::test_construction_does_not_perform_io``
for the model layer; the loader's no-I/O-when-nothing-is-present path
is asserted in ``tests/unit/config/test_loader.py``.
"""

from __future__ import annotations

from forgeqa.config.env import ENV_VAR_OVERRIDES, ENV_VAR_PREFIX, read_env_overrides
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
    "ENV_VAR_OVERRIDES",
    "ENV_VAR_PREFIX",
    "ForgeQAConfig",
    "ForgeQAConfigError",
    "GeneralConfig",
    "LogLevel",
    "ReportingConfig",
    "find_config_path",
    "load_config",
    "read_env_overrides",
)
