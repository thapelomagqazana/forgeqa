"""Exceptions raised by the ForgeQA configuration subsystem.

These exceptions are part of the public API (re-exported from
:mod:`forgeqa.config`). Consumers who call
:func:`forgeqa.config.load_config` should catch
:class:`ForgeQAConfigError` to handle any configuration-loading failure —
both malformed TOML (a syntax error) and semantically invalid config (a
value rejected by the Pydantic schema, e.g. ``browser_name = "safari"``).

The single exception type is deliberate. From the caller's perspective,
both cases mean "the config file does not produce a valid
:class:`~forgeqa.config.ForgeQAConfig`." Splitting them into two exception
classes would force the caller to catch both, and the appropriate
response (show the error, fix the file) is the same. The *message*
distinguishes the two cases clearly, and the ``__cause__`` chain
preserves the original exception for debugging.
"""

from __future__ import annotations


class ForgeQAConfigError(Exception):
    """Raised when a ForgeQA configuration file cannot be loaded or is invalid.

    This exception is raised by :func:`forgeqa.config.load_config` for:

    * **Malformed TOML.** The file exists but is not valid TOML. The
      underlying :class:`tomllib.TOMLDecodeError` is preserved as
      ``__cause__``; the ``str(error)`` includes the file path and the
      line/column when available.
    * **Semantically invalid config.** The file parses as TOML but does
      not produce a valid :class:`~forgeqa.config.ForgeQAConfig` (e.g.
      ``browser_name = "safari"``, ``timeout_ms = -1``, an unknown
      key). The underlying :class:`pydantic.ValidationError` is
      preserved as ``__cause__``; the ``str(error)`` includes the
      file path and Pydantic's field-level error.

    The exception is intentionally a single class for both cases; see
    the module docstring for the rationale.

    Attributes
    ----------
    path
        The path of the config file that failed, if a file was involved.
        ``None`` if the failure was not file-specific (e.g. an
        environment-variable override that could not be applied — a
        future use case).
    """

    def __init__(self, message: str, *, path: str | None = None) -> None:
        super().__init__(message)
        self.path = path
