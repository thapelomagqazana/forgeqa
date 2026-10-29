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

**Error messages are user-facing, not developer-facing.** The message a
user sees is a single line: it names the failing layer (file path, env
var, or CLI override), the field path (``browser.timeout_ms``), the
constraint (``must be between 1 and 60000``), and the offending value
(``got 0``). It does **not** include Pydantic's raw
``pydantic_core._pydantic_core.ValidationError:`` traceback line, its
internal ``[type=..., input_value=..., input_type=...]`` annotations, or
any multi-line traceback. See ADR-010 for the rationale and
``docs/configuration.md`` §"Validation" for the message shapes.

**Range note (WBS 1.2.5 / ADR-011).** ``browser.timeout_ms``'s lower
bound was relaxed from ``100`` to ``1`` in WBS 1.2.5 (the WBS boundary
test requires ``timeout_ms=1`` to be legal). The formatter is data-
driven: it reads the bounds from the model's JSON schema, so it
naturally emits the current bound (``"between 1 and 60000"``) without a
code change. The docstrings and examples below were updated to match.
``api.timeout_seconds`` was **not** relaxed — its bound is still
``[1, 300]``. See ADR-011 §Decision #5.

The formatting is done by :func:`format_validation_error` in this
module. It is a pure function (no I/O, no persistent state) so it can be
tested in isolation and reused by consumers who build their own configs.

**Why the formatter consults the model schema.** Pydantic v2 emits one
error per violated bound, and each error's ``ctx`` carries only *that*
bound. So a single error from ``Annotated[int, Field(ge=1, le=60_000)]``
is either ``{"type": "greater_than_equal", "ctx": {"ge": 1}}`` (when
the value is below 1) or ``{"type": "less_than_equal", "ctx": {"le":
60_000}}`` (when it is above 60_000) — never both. To render the
combined ``"must be between X and Y"`` form that the ADR and the docs
promise, :func:`_declared_bounds_for` looks up the *other* bound from
:class:`ForgeQAConfig`'s JSON schema. Pydantic caches the schema per
class, so the lookup is ~10 µs after the first call.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from pydantic import ValidationError

from forgeqa.config.models import ForgeQAConfig


class ForgeQAConfigError(Exception):
    """Raised when a ForgeQA configuration file cannot be loaded or is invalid.

    This exception is raised by :func:`forgeqa.config.load_config` for:

    * **Malformed TOML.** The file exists but is not valid TOML. The
      underlying :class:`tomllib.TOMLDecodeError` is preserved as
      ``__cause__``; the ``str(error)`` includes the file path and the
      line/column when available.
    * **Semantically invalid config.** The file parses as TOML but does
      not produce a valid :class:`~forgeqa.config.ForgeQAConfig` (e.g.
      ``browser_name = "safari"``, ``timeout_ms = 0``, an unknown
      key). The underlying :class:`pydantic.ValidationError` is
      preserved as ``__cause__``; the ``str(error)`` includes the
      file path and a **human-readable** description of the field, the
      constraint, and the offending value (e.g.
      ``"browser.timeout_ms must be between 1 and 60000, got 0"``).
      It does **not** include Pydantic's raw error or a traceback.
    * **Invalid environment variable or CLI override.** Same as the
      TOML case, but the message names the env var (or the CLI layer)
      instead of the file path. See
      :func:`format_validation_error` and ADR-010.

    The exception is intentionally a single class for all cases; see
    the module docstring for the rationale.

    Attributes
    ----------
    path
        The path of the config file that failed, if a file was involved.
        ``None`` if the failure was not file-specific (e.g. an
        environment-variable override that could not be applied, or a
        CLI override that was invalid).
    """

    def __init__(self, message: str, *, path: str | None = None) -> None:
        super().__init__(message)
        self.path = path


#: Human-readable verbs for the Pydantic error ``type`` values that we
#: reformat when only one bound is known. Used by :func:`_format_error`
#: as the one-sided fallback (e.g. when :func:`_declared_bounds_for`
#: cannot find the field in the schema, or when the field only declares
#: one side). The formatter's fallback for unrecognised types uses
#: Pydantic's own ``msg`` instead.
_ERROR_TYPE_NAMES: dict[str, str] = {
    "greater_than": "greater than",
    "greater_than_equal": "at least",
    "less_than": "less than",
    "less_than_equal": "at most",
    "string_too_short": "at least",
    "string_too_long": "at most",
}


def _format_loc(loc: tuple[Any, ...]) -> str:
    """Format a Pydantic error ``loc`` as ``"section.field"`` or ``"field"``.

    Parameters
    ----------
    loc
        The ``error["loc"]`` from a Pydantic ``ValidationError``.

    Returns
    -------
    str
        - ``"section.field"`` when ``loc`` has ≥ 2 elements (a
          sub-model field, e.g. from
          ``ForgeQAConfig(browser={"timeout_ms": 0})``).
        - ``"field"`` when ``loc`` has exactly 1 element (a direct
          sub-model construction, e.g. ``BrowserConfig(timeout_ms=0)``).
        - ``"<root>"`` when ``loc`` is empty.

    Notes
    -----
    The function returns the bare field name for length-1 locs so that
    :func:`format_validation_error` can decide whether to prepend a
    section prefix. The prefix is only useful when ``loc`` carries a
    section; for length-1 locs, ``_format_error`` already names the
    field, so prepending would produce ``"timeout_ms timeout_ms must
    be ..."`` (a real bug in a previous version of the formatter).
    """
    if not loc:
        return "<root>"
    return ".".join(str(part) for part in loc)


def _declared_bounds_for(loc: tuple[Any, ...]) -> tuple[Any, Any] | None:
    """Return the ``(lower, upper)`` bounds declared on the field at ``loc``.

    Pydantic v2 emits one error per violated bound, and each error's
    ``ctx`` carries only that bound. So a single error from
    ``Annotated[int, Field(ge=1, le=60_000)]`` never carries both
    ends. To render the combined ``"must be between X and Y"`` form
    that the ADR (Decision #5) and ``docs/configuration.md``
    §"Validation" promise, the formatter looks up the *other* bound
    from :class:`ForgeQAConfig`'s JSON schema.

    Parameters
    ----------
    loc
        The ``error["loc"]`` from a Pydantic ``ValidationError``.

    Returns
    -------
    tuple[Any, Any] | None
        ``(lower, upper)`` where each is the declared bound value
        (``None`` when that side is not declared), or ``None`` if no
        bounds were found.

    Notes
    -----
    The function handles two ``loc`` shapes:

    - **Length 1** (``("timeout_ms",)``): the caller constructed the
      sub-model directly (``BrowserConfig(timeout_ms=0)``). The field
      name is looked up in *every* sub-model's properties; the first
      match wins. ForgeQA's field names are unique across sub-models
      today, so the lookup is unambiguous.
    - **Length 2** (``("browser", "timeout_ms")``): the caller
      constructed ``ForgeQAConfig`` with a nested dict. The section is
      looked up in the top-level properties, and the field in that
      section's sub-schema.

    A **length-1 lookup is ambiguous** if a future schema adds the
    same field name to two sub-models with different bounds. In that
    case the function picks the first match; callers should construct
    ``ForgeQAConfig`` (giving length-2 locs) to be unambiguous, or
    keep field names unique across sub-models. Documented in ADR-010's
    reconsideration trigger.

    Cost is ~10 µs per call after the first (Pydantic caches the
    schema per class). The function runs only on the validation-
    failure path, so the cost is not paid by successful config loads.
    """
    if not loc:
        return None
    if not all(isinstance(part, str) for part in loc):
        # Pydantic v2 can put ints in `loc` for list indices. The
        # ForgeQA schema has no list fields; a non-str element means
        # an unexpected shape, and the caller falls back to the
        # one-sided form.
        return None

    schema = ForgeQAConfig.model_json_schema()
    defs = schema.get("$defs", {})

    field_schema: dict[str, Any] | None = None

    if len(loc) == 2:
        section, field_name = loc
        section_schema = schema.get("properties", {}).get(section, {})
        section_ref = section_schema.get("$ref")
        if not isinstance(section_ref, str):
            return None
        def_name = section_ref.rsplit("/", 1)[-1]
        sub_schema = defs.get(def_name, {})
        candidate = sub_schema.get("properties", {}).get(field_name)
        if isinstance(candidate, dict):
            field_schema = candidate
    elif len(loc) == 1:
        field_name = loc[0]
        # Scan every sub-model for a property named `field_name`. The
        # current schema has unique field names across sub-models, so
        # the first match is unambiguous.
        for sub_schema in defs.values():
            if not isinstance(sub_schema, dict):
                continue
            candidate = sub_schema.get("properties", {}).get(field_name)
            if isinstance(candidate, dict):
                field_schema = candidate
                break

    if field_schema is None:
        return None

    # Pydantic emits inclusive bounds as ``minimum`` / ``maximum``, and
    # exclusive bounds as ``exclusiveMinimum`` / ``exclusiveMaximum``.
    # The ForgeQA schema uses ``ge`` / ``le`` (inclusive), so we
    # primarily see ``minimum`` / ``maximum``; handling both forms
    # keeps a future ``gt=`` / ``lt=`` field working without a
    # formatter change.
    lower = field_schema.get("minimum", field_schema.get("exclusiveMinimum"))
    upper = field_schema.get("maximum", field_schema.get("exclusiveMaximum"))
    if lower is None and upper is None:
        return None
    return (lower, upper)


def _format_error(
    err: Mapping[str, Any],
    *,
    bounds: tuple[Any, Any] | None = None,
) -> str:
    """Format a single Pydantic error as a human-readable string.

    Parameters
    ----------
    err
        One element of ``ValidationError.errors()``. Typed as
        :class:`~collections.abc.Mapping` (not ``dict``) because
        Pydantic v2 returns :class:`pydantic_core.ErrorDetails`, a
        ``TypedDict`` that is assignable to ``Mapping[str, Any]`` but
        **not** to a mutable ``dict[str, Any]``.
    bounds
        The declared ``(lower, upper)`` bounds for the field, if known.
        When both ends are present, the message uses the combined
        ``"must be between X and Y"`` form. When only one is present
        (or ``bounds`` is ``None``), the one-sided form from Pydantic's
        ``ctx`` is used, or the raw ``msg``.

    Returns
    -------
    str
        A single-line description. Examples:

        - ``"timeout_ms must be between 1 and 60000, got 0"``
        - ``"browser_name must be one of: 'chromium', 'firefox' or 'webkit'; got 'safari'"``
        - ``"artifacts_dir must be a creatable directory: parent /nope does not exist"``
        - ``"unexpected field: timout_ms"``

        The ``1`` in the first example is the current lower bound per
        WBS 1.2.5 / ADR-011 §Decision #5; it was ``100`` before that
        change. The formatter reads the bound from the schema, so no
        code change is required to keep this docstring honest across
        a future bound change — but the example is worth updating
        when the bound changes, so a reader is not surprised.

    Notes
    -----
    The combined "between" form is used only when ``bounds`` has both
    ends (i.e. the field's ``Annotated`` constraint declared both
    ``ge`` and ``le``, or both ``gt`` and ``lt``). Pydantic v2's
    per-error ``ctx`` carries only the violated bound; the other bound
    comes from the schema, passed in as ``bounds`` by
    :func:`format_validation_error`.

    If ``bounds`` is ``None`` or has only one end, the function falls
    back to the one-sided form derived from ``error["ctx"]``. If even
    that is missing, it falls back to Pydantic's ``msg`` (already
    human-readable, just without the section prefix that
    :func:`format_validation_error` adds). The fallback chain is
    deliberate: a slightly-less-pretty message is better than a crash
    in the error formatter.
    """
    # Explicit annotations: mypy's `warn_return_any` fires when a
    # return expression is inferred as `Any`, which happens when the
    # values interpolated into the message are unannotated `Any` from
    # `err.get(...)`. Pinning `error_type` to `str`, `input_value` to
    # `object`, and `field_name` to `str` gives mypy a concrete type
    # to reason about, and the f-strings are unambiguously `str`.
    error_type: str = err.get("type", "") or ""
    input_value: object = err.get("input", "<missing>")
    loc = err.get("loc") or ()
    field_name: str = str(loc[-1]) if loc else "<root>"
    # The per-error `ctx` dict. Declared once at the top of the function
    # (rather than once per branch) because Python's function scoping
    # treats `ctx` as a single name: annotating it in multiple branches
    # is a mypy `no-redef`. All three branches read the same value, so
    # fetching it once is also simpler and avoids three dictionary
    # constructions per call.
    ctx: Mapping[str, Any] = err.get("ctx") or {}

    # Constrained integers / strings with lower and/or upper bounds.
    if error_type in {
        "greater_than_equal",
        "greater_than",
        "less_than_equal",
        "less_than",
    }:
        # Prefer the two-sided form when the schema told us both
        # bounds. Pydantic's per-error ctx only carries the violated
        # bound, so a below-minimum error has no idea what the maximum
        # is; the schema lookup is what makes "between" possible.
        if bounds is not None and bounds[0] is not None and bounds[1] is not None:
            lower, upper = bounds
            return f"{field_name} must be between {lower} and {upper}, got {input_value!r}"
        # Fall back to the one-sided form from the error's own ctx.
        lower = ctx.get("ge", ctx.get("gt"))
        upper = ctx.get("le", ctx.get("lt"))
        if lower is not None and upper is not None:
            return f"{field_name} must be between {lower} and {upper}, got {input_value!r}"
        if lower is not None:
            return str(
                f"{field_name} must be {_ERROR_TYPE_NAMES[error_type]} {lower}, got {input_value!r}"
            )
        if upper is not None:
            return str(
                f"{field_name} must be {_ERROR_TYPE_NAMES[error_type]} {upper}, got {input_value!r}"
            )
        # No bounds in ctx or schema: fall through to the generic message.

    # Constrained string lengths.
    if error_type in {"string_too_short", "string_too_long"}:
        bound = ctx.get("min_length", ctx.get("max_length"))
        bound_name = _ERROR_TYPE_NAMES[error_type]
        if bound is not None:
            return str(f"{field_name} must be {bound_name} {bound} characters, got {input_value!r}")

    # Literal (enumerated) values.
    if error_type == "literal_error":
        expected = ctx.get("expected", "<valid values>")
        return str(f"{field_name} must be one of: {expected}; got {input_value!r}")

    # Extra fields (unknown keys).
    if error_type == "extra_forbidden":
        return f"unexpected field: {field_name}"

    # Custom errors raised by ForgeQA validators (see
    # `GeneralConfig.artifacts_dir`). The error message is already
    # human-readable; Pydantic's `msg` has it.
    if error_type == "value_error":
        # Pydantic's `msg` for a ValueError is "Value error, <message>".
        # Strip the prefix.
        raw = str(err.get("msg", ""))
        prefix = "Value error, "
        return raw[len(prefix) :] if raw.startswith(prefix) else raw

    # Anything else: Pydantic's own message, which is already human-readable.
    return str(err.get("msg", "<unknown error>"))


def format_validation_error(
    exc: ValidationError,
    *,
    layer: str,
    path: str | None = None,
) -> str:
    """Format a Pydantic ``ValidationError`` as a one-line, human-readable message.

    Parameters
    ----------
    exc
        The ``ValidationError`` raised by ``ForgeQAConfig(**data)``.
    layer
        A human-readable name for the source of the invalid data:
        ``"TOML"``, ``"environment variable"``, or ``"CLI override"``.
        Used in the message prefix.
    path
        The resolved TOML path, if ``layer == "TOML"``. Used in the
        message prefix.

    Returns
    -------
    str
        A single-line message. Examples (bounds shown are the
        WBS 1.2.5 / ADR-011 values; ``browser.timeout_ms`` uses
        ``[1, 60_000]``, ``api.timeout_seconds`` uses ``[1, 300]``):

        - TOML: ``"Invalid configuration in /path/to/forgeqa.toml: browser.timeout_ms must be between 1 and 60000, got 0"``
        - Env:  ``"Invalid environment variable: browser.timeout_ms must be between 1 and 60000, got 0"``
        - CLI:  ``"Invalid CLI override: browser.timeout_ms must be between 1 and 60000, got 0"``

        **No Pydantic traceback is included.** The message is a single
        line, ends with the offending value, and names the field path
        and the constraint. The caller's response is "fix this value",
        not "read a Python traceback".

    Notes
    -----
    Multiple errors: the function formats the **first** error and
    appends ``" (and N more)"`` if more than one field is invalid. A
    full multi-line list is a follow-up (see ADR-010's reconsideration
    trigger); the single-error case is by far the most common.

    The function is pure: it reads only its arguments and the model
    schema (which Pydantic caches per class). It does no I/O and has
    no persistent state. It can be called from tests, from a CLI
    adapter, or from a consumer's own config-loading wrapper.

    The two-sided bounds form requires consulting
    :class:`ForgeQAConfig`'s JSON schema; see
    :func:`_declared_bounds_for` for why. A field without declared
    bounds (e.g. ``browser_name`` with ``Literal[...]``) skips the
    schema lookup's result and uses the one-sided form from Pydantic's
    ``ctx``, or the raw ``msg`` for ``literal_error`` /
    ``value_error`` / etc.

    **Field-path prefix.** ``_format_error`` already names the field
    (its ``field_name`` is ``loc[-1]``). This function prepends
    ``_format_loc(loc)`` only when ``loc`` carries a section (length
    ≥ 2), so the message reads ``"browser.timeout_ms must be ..."``.
    For length-1 locs (direct sub-model construction) the section is
    unknown, and the message reads ``"timeout_ms must be ..."`` — no
    duplication.

    **Total-function guarantee.** The ``message`` local is initialised
    to a safe default *before* the ``try``-equivalent branches below,
    so the function returns a string for any ``ValidationError`` and
    never raises ``UnboundLocalError``. This matters for two reasons:
    (a) a caller who passes a ``ValidationError`` whose ``errors()``
    list is empty still gets a meaningful message; (b) a future
    refactor that restructures the branch logic cannot accidentally
    introduce a code path where the local is unassigned. The cost is
    one extra assignment per call; the benefit is a formatter that is
    safe to call from anywhere.
    """
    errors = exc.errors()
    if not errors:
        return f"Invalid configuration ({layer}): <no errors reported>"
    first = errors[0]
    loc = first.get("loc", ())
    bounds = _declared_bounds_for(loc)
    detail = _format_error(first, bounds=bounds)
    extra = ""
    if len(errors) > 1:
        extra = f" (and {len(errors) - 1} more)"

    # `detail` already names the field (via `_format_error`'s
    # `field_name`). Prepend `_format_loc(loc)` only when it carries a
    # section, to avoid `"timeout_ms timeout_ms must be ..."`.
    # Ternary rather than if/else to satisfy ruff SIM108.
    prefix = _format_loc(loc) + " " if len(loc) >= 2 else ""

    # `message` is initialised before the branches so the function is
    # total (see "Total-function guarantee" above). Each branch below
    # overrides it; the default is only returned if a future refactor
    # adds a branch that forgets to assign.
    message = f"Invalid configuration ({layer}): {prefix}{detail}{extra}"

    if layer == "TOML":
        path_part = path if path is not None else "(unknown path)"
        message = f"Invalid configuration in {path_part}: {prefix}{detail}{extra}"
    elif layer == "environment variable":
        message = f"Invalid environment variable: {prefix}{detail}{extra}"
    else:
        message = f"Invalid CLI override: {prefix}{detail}{extra}"

    return message
