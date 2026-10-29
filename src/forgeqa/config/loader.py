"""Load a ForgeQA configuration from ``forgeqa.toml`` and overrides.

This module implements :func:`load_config`, the function a consumer
calls to obtain a :class:`~forgeqa.config.ForgeQAConfig`. It applies
the **precedence hierarchy** from WBS 1.2.3:

    CLI overrides  >  environment variables  >  forgeqa.toml  >  defaults

Each layer is optional; the loader degrades gracefully when a layer is
absent:

* **Defaults** are always present (the models have defaults).
* **``forgeqa.toml``** is read if present (see ADR-008 for search
  behaviour). If absent, the TOML layer is empty.
* **Environment variables** are read from
  :func:`forgeqa.config.env.read_env_overrides`. If none are set, the
  env layer is empty.
* **CLI overrides** are passed as the ``cli_overrides`` argument to
  :func:`load_config`. If not passed, the CLI layer is empty.

**Each layer is validated independently, then the layers are merged.**
Validating each layer in isolation (rather than validating only the
final merged dict) is what makes ADR-009 Decision #2 true: "an invalid
value at any layer fails at that layer, even if a higher layer would
override it." An invalid env var is a bug in the environment, and
silently letting a CLI override "fix" it would mask the bug.

Validating each layer by constructing a fresh
:class:`~forgeqa.config.ForgeQAConfig` (via :func:`_validate_layer`)
also avoids a Pydantic v2 gotcha: ``model_copy(update=...)`` does
**not** validate, so using it to layer nested sub-model dicts produces
a config whose ``.browser`` is a raw ``dict``, not a
:class:`~forgeqa.config.BrowserConfig` instance. Constructing the
model gives fully-typed sub-model instances.

The loader is intentionally narrow. It does not:

* Resolve environment-variable overrides beyond the
  :data:`forgeqa.config.env.ENV_VAR_OVERRIDES` allowlist (see ADR-009).
* Merge multiple config files.
* Cache the result across calls (each call reads the file and the
  environment fresh; see the "Determinism" note in
  ``docs/configuration.md``).
"""

from __future__ import annotations

import tomllib
from collections.abc import Mapping
from pathlib import Path
from typing import Any, cast

from pydantic import ValidationError

from forgeqa.config.env import read_env_overrides
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
    would be ambiguous when the working directory changes.
    """
    directory = Path.cwd() if directory is None else Path(directory)
    candidate = directory / DEFAULT_CONFIG_FILENAME
    if candidate.is_file():
        return candidate.resolve()
    return None


def _read_toml(path: Path | str | None) -> tuple[dict[str, Any], Path | None]:
    """Read and parse a TOML file into a plain dict.

    Parameters
    ----------
    path
        The path to read, or ``None`` to search the current directory
        (with no-file-means-default semantics).

    Returns
    -------
    tuple[dict[str, Any], Path | None]
        The parsed TOML as a nested dict (empty dict if no file is
        present), and the resolved path of the file that was read (or
        ``None`` if no file was read). The path is returned so that
        :func:`load_config` can name the file in error messages
        without a second ``find_config_path`` call.

    Raises
    ------
    ForgeQAConfigError
        If the file is present but cannot be read (including a
        non-UTF-8 encoding), or is not valid TOML.
    """
    resolved: Path | None
    if path is None:
        resolved = find_config_path()
        if resolved is None:
            return {}, None
    else:
        resolved = Path(path)
        if not resolved.is_file():
            raise ForgeQAConfigError(
                f"Config file not found: {resolved}",
                path=str(resolved),
            )

    try:
        text = resolved.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        raise ForgeQAConfigError(
            f"Could not read config file {resolved}: {exc}",
            path=str(resolved),
        ) from exc

    try:
        return tomllib.loads(text), resolved
    except tomllib.TOMLDecodeError as exc:
        raise ForgeQAConfigError(
            f"Invalid TOML in {resolved}: {exc}",
            path=str(resolved),
        ) from exc


def _env_vars_for_validation_errors(
    exc: ValidationError,
    env_data: Mapping[str, Mapping[str, Any]],
) -> list[str]:
    """Map a Pydantic ``ValidationError`` to the env var names that caused it.

    Parameters
    ----------
    exc
        The ``ValidationError`` raised while validating the env layer.
    env_data
        The nested dict that was applied. Keys are sections, values
        are field dicts.

    Returns
    -------
    list[str]
        The environment variable names whose values are (at least
        partly) responsible for the error. May be empty if the error
        path does not match a field we can map back (should not
        happen in practice).

    Notes
    -----
    This helper exists because Pydantic's error messages name *fields*
    (``("browser", "headless")``), not *environment variables*
    (``FORGEQA_BROWSER_HEADLESS``). For an env-var user, the field
    name is not directly actionable: they need to know which env var
    to fix. This helper inverts
    :data:`forgeqa.config.env.ENV_VAR_OVERRIDES` to find the var name.

    Pydantic v2's ``error["loc"]`` is a ``tuple[int | str, ...]`` —
    the first element can be an int for list indices. The config
    schema has no list-typed fields today, so we defensively reject
    locs whose first two elements are not both ``str``. If a future
    schema adds a list-typed field, this helper will silently skip
    the error (returning no culprits for it) rather than raising a
    ``TypeError`` on the tuple lookup; the error message falls back
    to ``"<unknown>"``, which is the correct fallback for a loc we
    cannot map to an env var.
    """
    # Lazy import to avoid a circular dependency at module load:
    # env.py imports from models.py; loader.py imports from both.
    from forgeqa.config.env import ENV_VAR_OVERRIDES  # noqa: PLC0415

    # Invert the mapping: (section, field) -> var name.
    inverse: dict[tuple[str, str], str] = {value: key for key, value in ENV_VAR_OVERRIDES.items()}
    culprits: list[str] = []
    for error in exc.errors():
        loc = error.get("loc", ())
        if len(loc) != 2:
            continue
        section, field = loc
        # Pydantic v2's loc elements are int | str. The config schema
        # has no list-typed fields, so a non-str element here would
        # mean an unexpected schema shape; skip rather than raise.
        if not isinstance(section, str) or not isinstance(field, str):
            continue
        var_name = inverse.get((section, field))
        if var_name is not None and var_name not in culprits:
            culprits.append(var_name)
    return culprits


def _validate_layer(
    data: Mapping[str, Any],
    *,
    layer_name: str,
    toml_path: Path | None = None,
) -> None:
    """Validate one layer's dict against the schema.

    Parameters
    ----------
    data
        The layer's nested dict (e.g.
        ``{"browser": {"browser_name": "firefox"}}``).
    layer_name
        A human-readable name for the layer, used in the error
        message: ``"TOML"``, ``"environment variable"``, or
        ``"CLI override"``.
    toml_path
        The resolved TOML path, if ``layer_name == "TOML"``. Used to
        name the file in the error.

    Raises
    ------
    ForgeQAConfigError
        If ``data`` is not a valid partial override. The message names
        the layer (and, for env, the offending environment variable;
        for TOML, the file path).

    Notes
    -----
    Uses ``ForgeQAConfig(**data)``, which validates the layer's fields
    (including nested sub-models — this is why we construct rather
    than ``model_copy(update=...)``) and fills the others from
    defaults. The resulting object is discarded; only the validation
    side effect matters, because :func:`load_config` merges the raw
    dicts and constructs the final config once.

    Empty ``data`` is a no-op — an absent layer is not "invalid".
    """
    if not data:
        return
    try:
        # The result is discarded; we only want validation. The
        # ``cast`` is needed because ``**data`` with a
        # ``dict[str, Any]`` key type cannot be statically narrowed
        # to the model's per-field sub-types; the runtime call is
        # correct because ``data`` is config-shaped.
        ForgeQAConfig(**cast(dict[str, Any], dict(data)))
    except ValidationError as exc:
        if layer_name == "TOML":
            path_part = str(toml_path) if toml_path is not None else "(unknown path)"
            raise ForgeQAConfigError(
                f"Invalid configuration in {path_part}: {exc}",
                path=path_part,
            ) from exc
        if layer_name == "environment variable":
            culprits = _env_vars_for_validation_errors(exc, data)
            var_list = ", ".join(culprits) if culprits else "<unknown>"
            raise ForgeQAConfigError(
                f"Invalid value in environment variable(s) {var_list}: {exc}",
            ) from exc
        # layer_name == "CLI override"
        raise ForgeQAConfigError(
            f"Invalid CLI override: {exc}",
        ) from exc


def load_config(
    path: Path | str | None = None,
    *,
    cli_overrides: Mapping[str, Mapping[str, Any]] | None = None,
    environ: Mapping[str, str] | None = None,
) -> ForgeQAConfig:
    """Load the ForgeQA configuration with the precedence hierarchy applied.

    Precedence, from highest to lowest priority:

    1. **CLI overrides** (``cli_overrides`` argument).
    2. **Environment variables** (``FORGEQA_*``; see
       :data:`forgeqa.config.env.ENV_VAR_OVERRIDES`).
    3. **``forgeqa.toml``** (search: see :func:`find_config_path`).
    4. **Defaults** (the models' field defaults).

    Parameters
    ----------
    path
        The path to a ``forgeqa.toml`` file. If ``None`` (the default),
        the loader searches the current working directory for
        :data:`DEFAULT_CONFIG_FILENAME`. If the file is not found and
        ``path`` is ``None``, the TOML layer is empty. If the file is
        not found and ``path`` is provided, :class:`ForgeQAConfigError`
        is raised.
    cli_overrides
        Overrides supplied by the CLI (or a test harness, or any
        programmatic caller). Shape: a nested dict matching
        ``ForgeQAConfig``'s constructor, e.g.
        ``{"browser": {"headless": True}}``. Only the fields present
        are overridden. Unknown sections or fields raise
        :class:`ForgeQAConfigError`.
    environ
        The environment mapping to read from. Defaults to
        :data:`os.environ`. Pass an explicit mapping in tests to
        avoid mutating the real environment.

    Returns
    -------
    ForgeQAConfig
        The fully-resolved configuration.

    Raises
    ------
    ForgeQAConfigError
        If any layer fails to produce a valid override dict, or if
        the final merged config is invalid. The message names the
        failing layer.

    Notes
    -----
    **Layering mechanics.** The loader:

    1. Reads the TOML file into a dict (or ``{}`` if no file).
    2. Reads the env vars into a dict (or ``{}`` if none).
    3. Validates each layer in isolation by constructing a fresh
       :class:`~forgeqa.config.ForgeQAConfig`. This gives fully-typed
       sub-model instances and catches an invalid value at its own
       layer, even if a higher layer would override it.
    4. Merges the raw dicts in precedence order (TOML first, then
       env, then CLI) so each later layer's values override the
       earlier layer's values at the field level.
    5. Constructs the final :class:`~forgeqa.config.ForgeQAConfig`
       from the merged dict.

    Because the layers were individually valid, the merged dict is
    also valid (the merge only replaces fields with values from a
    layer that was itself valid). The final construction is the
    place the merged result becomes a proper config object with
    typed sub-models.

    **Determinism.** Each call re-reads the file and re-reads the
    environment. No caching.

    **Backwards compatibility.** With no env vars set and
    ``cli_overrides=None``, ``load_config`` behaves exactly as it did
    before the precedence hierarchy was added (TOML over defaults).

    **Encoding.** The file is read as UTF-8. A non-UTF-8 file raises
    :class:`ForgeQAConfigError` (the underlying
    :class:`UnicodeDecodeError` is preserved as ``__cause__``).

    **Error message shape.** TOML syntax errors: ``"Invalid TOML in
    /path: ..."``. TOML validation errors: ``"Invalid configuration
    in /path: ..."``. Env errors: ``"Invalid value in environment
    variable(s) FORGEQA_...: ..."``. CLI errors: ``"Invalid CLI
    override: ..."``. Each names the layer.
    """
    # --- Read and validate each layer in isolation ------------------------
    toml_data, toml_path = _read_toml(path)
    _validate_layer(toml_data, layer_name="TOML", toml_path=toml_path)

    env_data = read_env_overrides(environ)
    _validate_layer(env_data, layer_name="environment variable")

    cli_data: dict[str, dict[str, Any]] = (
        {section: dict(fields) for section, fields in cli_overrides.items()}
        if cli_overrides is not None
        else {}
    )
    _validate_layer(cli_data, layer_name="CLI override")

    # --- Merge raw dicts in precedence order (lowest first) ---------------
    # Deep-merge at the section level: a section's fields are merged
    # individually, not replaced wholesale. This preserves per-field
    # precedence (e.g. TOML sets `browser.headless`, env sets
    # `browser.browser_name` — both survive).
    merged: dict[str, dict[str, Any]] = {}
    for layer in (toml_data, env_data, cli_data):
        for section, fields in layer.items():
            merged.setdefault(section, {}).update(fields)

    # --- Construct the final config --------------------------------------
    # ``**merged`` with a ``dict[str, dict[str, Any]]`` key type cannot
    # be statically narrowed to ``ForgeQAConfig``'s per-field sub-types
    # (GeneralConfig, BrowserConfig, ...). The runtime call is correct
    # because ``merged`` is config-shaped (each section's value is the
    # dict form of the corresponding sub-model); the ``cast`` documents
    # that intent to the type checker.
    try:
        return ForgeQAConfig(**cast(dict[str, Any], merged))
    except ValidationError as exc:
        # Should not happen: each layer was individually valid and the
        # merge only replaces fields with values from a validated
        # layer. If a future cross-field validator is added, the
        # error will land here; the fallback names the TOML file if
        # present, otherwise gives a generic message.
        if toml_path is not None:
            raise ForgeQAConfigError(
                f"Invalid merged configuration (TOML: {toml_path}): {exc}",
                path=str(toml_path),
            ) from exc
        raise ForgeQAConfigError(
            f"Invalid merged configuration: {exc}",
        ) from exc
