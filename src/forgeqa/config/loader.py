"""Load a ForgeQA configuration from ``forgeqa.toml``.

This module implements :func:`load_config`, the function a consumer
calls to obtain a :class:`~forgeqa.config.ForgeQAConfig`. It:

1. Searches for ``forgeqa.toml`` in the current working directory (or
   uses an explicit path if one is given).
2. If the file is absent (and no explicit path was given), returns the
   default config — ``ForgeQAConfig()``.
3. If the file is present, parses it with :mod:`tomllib` and constructs
   a ``ForgeQAConfig`` from the resulting dict.
4. On failure, raises :class:`~forgeqa.config.ForgeQAConfigError` with
   a message that includes the file path and (for syntax errors) the
   line and column.

The loader is intentionally narrow. It does not:

* Resolve environment-variable overrides (a Phase 1 follow-up, WBS
  1.2.3 when scoped).
* Merge multiple config files (a Phase 1 follow-up).
* Cache the result across calls (each call reads the file; see the
  "Determinism" note in ``docs/configuration.md``).

Those are separate concerns with separate tests. Keeping the loader
narrow means its contract is easy to state: "find, parse, validate, or
return defaults." Anything beyond that belongs in a different module.
"""

from __future__ import annotations

import tomllib
from pathlib import Path

from pydantic import ValidationError

from forgeqa.config.errors import ForgeQAConfigError
from forgeqa.config.models import ForgeQAConfig

#: The filename the loader searches for when no explicit path is given.
#: A consumer who wants a differently-named config file must pass an
#: explicit ``path`` to :func:`load_config`. The filename is a constant
#: (not configurable) because "the config file is called
#: ``forgeqa.toml``" is a fact of the framework, not a user setting.
DEFAULT_CONFIG_FILENAME = "forgeqa.toml"


def find_config_path(
    directory: Path | None = None,
) -> Path | None:
    """Find the ForgeQA config file in ``directory``.

    Parameters
    ----------
    directory
        The directory to search. If ``None`` (the default), the current
        working directory is used. If the directory does not exist,
        ``None`` is returned (a missing directory is treated the same
        as a missing file — there is no config there).

    Returns
    -------
    Path or None
        The absolute path to ``forgeqa.toml`` in ``directory``, or
        ``None`` if it does not exist.

    Notes
    -----
    The function returns an *absolute* path. This is important because
    the returned path is included in error messages; a relative path
    would be ambiguous when the working directory changes. It is also
    important for callers that need to compare config paths
    (e.g. logging "loaded config from X").
    """
    directory = Path.cwd() if directory is None else Path(directory)
    candidate = directory / DEFAULT_CONFIG_FILENAME
    if candidate.is_file():
        return candidate.resolve()
    return None


def load_config(path: Path | str | None = None) -> ForgeQAConfig:
    """Load the ForgeQA configuration.

    Parameters
    ----------
    path
        The path to a ``forgeqa.toml`` file. If ``None`` (the default),
        the loader searches the current working directory for
        :data:`DEFAULT_CONFIG_FILENAME`. If the file is not found and
        ``path`` is ``None``, the default config is returned. If the
        file is not found and ``path`` is provided, that is an error —
        an explicit path that does not exist means the caller has a
        bug, not that defaults should be used.

    Returns
    -------
    ForgeQAConfig
        The loaded (and validated) configuration. If no file is found,
        ``ForgeQAConfig()`` — the fully-defaulted configuration.

    Raises
    ------
    ForgeQAConfigError
        If the file cannot be read, is not valid TOML, or does not
        produce a valid :class:`ForgeQAConfig`. The exception message
        includes the file path and, for syntax errors, the line number.
        The original exception is preserved as ``__cause__``.

    Examples
    --------
    Load from the current directory (or defaults if no file is
    present)::

        from forgeqa.config import load_config

        cfg = load_config()

    Load from an explicit path (error if the file is missing)::

        from pathlib import Path
        from forgeqa.config import load_config

        cfg = load_config(Path("configs/ci.toml"))

    Catch any configuration error::

        from forgeqa.config import ForgeQAConfigError, load_config

        try:
            cfg = load_config()
        except ForgeQAConfigError as exc:
            print(f"Configuration error: {exc}")
            raise

    Notes
    -----
    **Determinism.** Each call reads the file fresh. The loader does not
    cache. A test that calls ``load_config`` twice on the same file sees
    two equal configs (the model is a value type, so ``==`` compares by
    value); a developer who edits ``forgeqa.toml`` and calls again
    sees the new values. Caching was rejected because staleness is a
    worse failure mode than a ~1 ms file read.

    **Encoding.** The file is read as UTF-8. ``forgeqa.toml`` files are
    expected to be UTF-8 (the TOML spec requires it); an explicit
    encoding makes the loader deterministic on Windows, where the
    default encoding is platform-dependent.

    **Error message shape.** For a syntax error, the message looks
    like ``"Invalid TOML in /path/to/forgeqa.toml: Expected '=' after
    a key (at line 3, column 7)"``. For a validation error, it looks
    like ``"Invalid configuration in /path/to/forgeqa.toml: 1
    validation error for ForgeQAConfig\\nbrowser\\n  browser_name\\n
    Input should be 'chromium', 'firefox' or 'webkit' ..."``. Both
    include the path.
    """
    resolved: Path | None
    if path is None:
        resolved = find_config_path()
        if resolved is None:
            # No file in cwd, and no explicit path: the default config
            # is the correct result. This is the "graceful fallback"
            # the WBS requires.
            return ForgeQAConfig()
    else:
        resolved = Path(path)
        if not resolved.is_file():
            # An explicit path that does not exist is a caller error,
            # not a "use defaults" situation. The caller asked for a
            # specific file; silently using defaults would hide the
            # mistake.
            raise ForgeQAConfigError(
                f"Config file not found: {resolved}",
                path=str(resolved),
            )

    try:
        text = resolved.read_text(encoding="utf-8")
    except OSError as exc:
        raise ForgeQAConfigError(
            f"Could not read config file {resolved}: {exc}",
            path=str(resolved),
        ) from exc

    try:
        data = tomllib.loads(text)
    except tomllib.TOMLDecodeError as exc:
        raise ForgeQAConfigError(
            f"Invalid TOML in {resolved}: {exc}",
            path=str(resolved),
        ) from exc

    try:
        return ForgeQAConfig(**data)
    except ValidationError as exc:
        raise ForgeQAConfigError(
            f"Invalid configuration in {resolved}: {exc}",
            path=str(resolved),
        ) from exc
