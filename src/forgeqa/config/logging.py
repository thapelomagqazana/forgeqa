"""Per-module logger factory for the ForgeQA configuration subsystem.

This module exists so that :mod:`forgeqa.config.errors` and
:mod:`forgeqa.config.loader` can obtain a logger without importing a
not-yet-existing top-level logging module. It will be promoted to
:mod:`forgeqa.logging` (or absorbed into a Phase 3 diagnostics module)
when the rest of the framework needs it; until then, keeping it in
``config/`` is the least surface-area option and avoids a circular
import from ``config/`` into the package root.

Design
------
* **One logger per module, namespaced under** ``"forgeqa.config"``. A
  user who wants to configure the config subsystem's logging can use
  ``logging.getLogger("forgeqa.config").setLevel(...)`` without
  touching the rest of the framework.
* **No handlers.** The library does not install handlers on its own
  loggers; a library that adds a handler to the root logger (or to its
  own loggers) hijacks the consuming application's logging
  configuration. This is the "logging is configured by the application,
  not the library" rule. The library only *emits*; the application
  decides what to do with the records. See `Python Logging
  HOWTO <https://docs.python.org/3/howto/logging.html#configuring-logging-for-a-library>`_
  for the rationale.
* **`logging.getLogger(__name__)`** is the standard idiom; no factory
  *function* is needed for the common case. The one customisation we
  add is :func:`get_logger`, which gives the config subsystem a single
  well-known name prefix regardless of where the module lives relative
  to the package root (``forgeqa.config.errors`` → logger named
  ``"forgeqa.config.errors"``, which is a child of
  ``"forgeqa.config"`` — a hierarchy, as logging intends).
* **Idempotent and side-effect free.** Calling :func:`get_logger`
  multiple times returns the same logger instance (that is
  :mod:`logging`'s behaviour) and does **not** add handlers, does
  **not** set levels, and does **not** touch the root logger.

Not yet in scope
----------------
* Structured (JSON) record formatting — Phase 3, after the reporting
  subsystem lands and can dictate the record shape.
* A `NullHandler` attached to the top-level ``"forgeqa"`` logger — the
  standard "library that doesn't want to crash on unconfigured logging"
  pattern. It belongs in a top-level module (``forgeqa/__init__.py`` or
  ``forgeqa/logging.py``), not here; adding it to ``"forgeqa.config"``
  alone would suppress config errors silently if the rest of the
  framework still logs. **TODO:** add it at package import in Phase 1.
"""

from __future__ import annotations

import logging

#: The logger name prefix for the whole configuration subsystem. Exposed
#: so that tests (and users who configure logging) can reference the
#: literal rather than re-typing it. Adding a sub-logger for a future
#: module in ``forgeqa.config`` is ``logging.getLogger(f"{PREFIX}.mymodule")``.
PREFIX = "forgeqa.config"

#: A module-level constant used by the loader and the exception class
#: to indicate the log level at which config errors are emitted. Kept
#: at ERROR (not CRITICAL) because a bad config is recoverable by the
#: user editing the file — CRITICAL is for "the runner itself is
#: broken". Documented in ADR-012 §Decision #1.
CONFIG_ERROR_LEVEL = logging.ERROR


def get_logger(name: str) -> logging.Logger:
    """Return a logger under the ``"forgeqa.config"`` namespace.

    Parameters
    ----------
    name
        The module's ``__name__``. This is the standard Python idiom;
        do not pass a short name (``"errors"``) — a bare name would
        collide with the application's own loggers if it happened to be
        called ``"errors"``.

    Returns
    -------
    logging.Logger
        The logger for ``"forgeqa.config.<name>"``, or for
        ``"forgeqa.config"`` if ``name`` is already that prefix (e.g.
        ``get_logger("forgeqa.config")``). Idempotent: the same call
        with the same argument always returns the same instance
        (Python's logging cache).

    Notes
    -----
    The function does not configure the logger. Attaching a handler,
    setting a level, or propagating a record is the *application's*
    job. A library that configures logging has taken a decision away
    from its consumer, and downstream that decision is almost always
    wrong (see "logging is configured by the application, not the
    library" in the module docstring).

    Examples
    --------
    Inside ``src/forgeqa/config/loader.py``::

        log = get_logger(__name__)  # logger named "forgeqa.config.loader"
        log.error("Invalid configuration: %s", message)

    A user who wants to silence config errors entirely::

        logging.getLogger("forgeqa.config").addHandler(logging.NullHandler())
        logging.getLogger("forgeqa.config").propagate = False
    """
    # If the caller passed a dotted name that already begins with the
    # prefix (e.g. another module constructing a sub-logger), respect
    # it verbatim rather than producing "forgeqa.config.forgeqa.config.x".
    if name == PREFIX or name.startswith(f"{PREFIX}."):
        return logging.getLogger(name)
    return logging.getLogger(f"{PREFIX}.{name}")


__all__ = ["CONFIG_ERROR_LEVEL", "PREFIX", "get_logger"]
