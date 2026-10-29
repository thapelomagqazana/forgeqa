"""Exceptions raised by the ForgeQA configuration subsystem.

This module defines :class:`ForgeQAConfigError` — the single exception
raised by :func:`forgeqa.config.load_config` for every configuration
failure (malformed TOML, invalid field value, unknown key, invalid
environment variable, invalid CLI override). It also defines the
formatting helpers that turn Pydantic's ``ValidationError`` into the
human-readable message the user sees, plus the structured fields
(``field``, ``value``, ``expected``) a caller can use programmatically.

**Why a single exception type.** From the caller's perspective, every
failure mode means "the config does not produce a valid
:class:`~forgeqa.config.ForgeQAConfig`". The appropriate response is the
same — show the message, fix the file. Splitting into
``TOMLSyntaxError`` / ``ConfigValidationError`` / etc. would force every
caller to catch multiple types or a base class; either way, they would
do the same thing. The single-class design is documented in ADR-010 and
preserved here.

**What makes the message actionable.** Every error carries not just a
human-readable string (in ``str(error)``) but **structured fields** on
the exception object:

* ``layer``    — ``"TOML"``, ``"environment variable"``, ``"CLI override"``
* ``path``     — the file path, if the layer is TOML; else ``None``
* ``field``    — the dotted field path (``"browser.timeout_ms"``); else ``None``
* ``value``    — the offending value, stringified; else ``None``
* ``expected`` — the constraint description (``"between 1 and 60000"``); else ``None``

The structured fields let a caller (a test, a UI, an IDE integration)
identify *which* field failed without regex-parsing the string. The
string is the fallback for ``str(error)`` and for log records; the
fields are the stable interface.

**Every error is logged at ERROR level.** A bad config is not a debug
curiosity — it is the first failure a user encounters, and it should be
in their terminal even if they didn't catch the exception (a surprising
number of "my config isn't being applied" issues turn out to be a
swallowed exception). The log call lives in
:meth:`ForgeQAConfigError.__init__`, so **every** construction,
everywhere, produces exactly one record. The record is emitted to
``logging.getLogger("forgeqa.config.errors")`` at
:data:`forgeqa.config.logging.CONFIG_ERROR_LEVEL` (i.e.
``logging.ERROR``). The library does **not** install a handler — that
would hijack the application's logging configuration; it emits, and
the application decides what to do with the record. See ADR-012.

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
It returns a ``(message, fields)`` tuple: the human string plus the
structured triple, so the caller can construct a
:class:`ForgeQAConfigError` that carries both.

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

See also
--------
* ADR-010 — validation strategy and error formatter design
* ADR-011 — safe defaults (bounds changed in WBS 1.2.5)
* ADR-012 — why every error is logged at ERROR level (WBS 1.2.6)
* ``docs/configuration.md`` §"Validation" and §"Error logging" —
  user-facing message shapes
"""

from __future__ import annotations

import contextlib
from collections.abc import Mapping
from typing import Any, NamedTuple

from pydantic import ValidationError

from forgeqa.config.logging import CONFIG_ERROR_LEVEL, get_logger
from forgeqa.config.models import ForgeQAConfig

#: Per-module logger. Named ``"forgeqa.config.errors"`` — a child of
#: the subsystem logger ``"forgeqa.config"``, so a user can configure
#: the whole subsystem with ``logging.getLogger("forgeqa.config")`` or
#: just this module with ``logging.getLogger("forgeqa.config.errors")``.
log = get_logger(__name__)


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

    **Every construction emits a log record at ERROR level** to the
    ``"forgeqa.config.errors"`` logger. The record is the same
    human-readable string as ``str(error)``, plus structured extras
    (``forgeqa_layer``, ``forgeqa_path``, ``forgeqa_field``,
    ``forgeqa_value``, ``forgeqa_expected``) that a structured-logging
    handler can consume. The library does not install a handler; a
    user who wants silence can set the logger's level or add a
    ``NullHandler``. See ADR-012.

    Attributes
    ----------
    layer
        The layer that produced the error (``"TOML"``,
        ``"environment variable"``, ``"CLI override"``). Always set.
    path
        The path of the config file that failed, if a file was
        involved. ``None`` for env-var and CLI-override failures.
    field
        The dotted field path (``"browser.timeout_ms"``). ``None`` if
        the error is not field-specific (e.g. a top-level TOML syntax
        error with no field context).
    value
        The offending value, stringified. ``None`` if not applicable
        (e.g. a missing-file error, or a ``required`` sentinel).
    expected
        A human-readable constraint description (``"between 1 and
        60000"``, ``"one of: 'chromium', 'firefox', 'webkit'"``).
        ``None`` if not applicable (e.g. an unknown field, which has
        no "expected value" in the constraints sense).

    Notes
    -----
    ``str(error)`` is the human message. The structured fields are the
    stable, parseable interface. A caller that wants the field name
    **must not** regex the message — read ``error.field`` instead.

    The exception is picklable (see
    ``tests/unit/config/test_errors.py::test_exception_is_picklable``),
    which matters for ``pytest-xdist`` and any future
    ``multiprocessing`` integration. The ``__cause__`` chain is
    **not** preserved across a pickle round-trip (stdlib limitation);
    a future WBS may add ``__reduce__`` if a consumer needs it. See
    ADR-012 §Reconsideration Trigger.
    """

    #: Type hints for the instance attributes, for readers and for
    #: ``mypy``. Also assigned in ``__init__`` below; the class-level
    #: annotations make the attributes discoverable without reading
    #: ``__init__``.
    layer: str
    path: str | None
    field: str | None
    value: str | None
    expected: str | None

    def __init__(
        self,
        message: str,
        *,
        layer: str = "TOML",
        path: str | None = None,
        field: str | None = None,
        value: str | None = None,
        expected: str | None = None,
    ) -> None:
        """Construct a :class:`ForgeQAConfigError` and emit an ERROR log record.

        Parameters
        ----------
        message
            The human-readable message (as returned by
            :func:`format_validation_error`, or the ``str()`` of a
            :class:`tomllib.TOMLDecodeError` wrapped in our
            path-prefixed form). This is what ``str(error)`` returns
            and what appears in the log record's ``message``.
        layer
            Which layer produced the error. One of ``"TOML"``,
            ``"environment variable"``, ``"CLI override"``. Defaults
            to ``"TOML"`` so that legacy callers who only pass
            ``message`` and ``path`` (e.g. the pre-1.2.6 signature)
            still get a sensible value. Used both in the log record's
            structured extras and (implicitly) in the message.
        path
            The file path for TOML-layer errors. ``None`` for
            env-var/CLI failures.
        field
            Dotted field path. ``None`` if not field-specific.
        value
            Stringified offending value. ``None`` if not applicable.
        expected
            Constraint description. ``None`` if not applicable.

        Notes
        -----
        The log record is emitted **at construction**. A caller that
        catches the exception to convert it (e.g. a CLI wrapper that
        turns it into an exit code) will see the record even if the
        caller then re-raises a different exception or suppresses this
        one. That is deliberate: "the error happened" is a fact worth
        recording regardless of what the caller does with it. The
        record is not emitted at ``str(error)``-time (which could
        happen multiple times) — that would produce duplicate log
        lines.

        Logging at the exception site is unusual (most code logs at the
        catch site), but it's the right choice here because:

        * The exception class is the natural single place to emit.
          Putting the log call in the loader would mean a test that
          constructs the exception directly (for a unit test of the
          formatter) sees no log record — and testing the log shape
          then requires a fake loader. Logging at construction means
          every construction, everywhere, produces one log record.
        * The ``message`` argument is the fully-formatted user
          message. A caller who constructs the exception with a
          *different* message (e.g. ``ForgeQAConfigError("custom
          message", layer="custom")``) still gets a log record —
          which is what "log every error" means.

        **Failure of logging must not mask the error.** If the log
        call raises (a pathological handler that throws, a formatter
        that fails), the ``contextlib.suppress`` around it swallows
        the logging failure and the exception is constructed and
        raised as normal. The config error is the user's problem; the
        logging failure is the application's problem, and the
        application can debug it from its own logging subsystem
        (which is where the misbehaving handler lives). We do not log
        "log failed" — that would recurse.
        """
        super().__init__(message)
        self.layer = layer
        self.path = path
        self.field = field
        self.value = value
        self.expected = expected

        # Emit the log record. The `extra` dict attaches structured
        # fields so a JSON handler (Phase 3) can surface them as
        # top-level record attributes (record.forgeqa_layer, …)
        # rather than requiring consumers to parse the message. The
        # `forgeqa_` prefix avoids collision with the application's
        # own `extra=` keys.
        #
        # `contextlib.suppress(Exception)` is the "failure of logging
        # must not mask the error" contract in code: a misbehaving
        # application handler (a formatter that raises, a queue
        # handler whose queue is full) must not turn a config error
        # into an unrelated traceback. The config error is the user's
        # problem; the logging failure is the application's problem,
        # and the application can debug it from its own logging
        # subsystem. We do not log "log failed" — that would recurse.
        #
        # `suppress(Exception)` (not `suppress(BaseException)`) is
        # deliberate: `KeyboardInterrupt` and `SystemExit` propagate,
        # as they should. Behaviourally identical to the
        # `try`/`except Exception: pass` it replaces; satisfies
        # ruff SIM105.
        with contextlib.suppress(Exception):
            log.log(
                CONFIG_ERROR_LEVEL,
                message,
                # `stacklevel=2` attributes the log record to the
                # caller's frame (loader.py's line) rather than to the
                # exception constructor. A user reading the log sees
                # "at loader.py:NN", which is where they can act.
                # Without stacklevel, they would see "at errors.py:NN"
                # — the exception's ``__init__`` — which is less useful.
                stacklevel=2,
                extra={
                    "forgeqa_layer": layer,
                    "forgeqa_path": path,
                    "forgeqa_field": field,
                    "forgeqa_value": value,
                    "forgeqa_expected": expected,
                },
            )


# =============================================================================
# Pydantic message extraction
# =============================================================================
#
# The helpers below build both the human message AND the structured
# fields (field / value / expected). Keeping the two views in one module
# (and sharing the loc / bounds / ctx logic between them) ensures a
# future refactor that changes one cannot silently drift from the other.
# =============================================================================


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


class _ErrorFields(NamedTuple):
    """The structured fields extracted from a single Pydantic error.

    Returned alongside the formatted message by
    :func:`format_validation_error` and attached to
    :class:`ForgeQAConfigError` by the loader. A ``NamedTuple`` (not a
    dataclass) because it is a lightweight internal value, and the
    tuple form makes it trivial to construct in a test.
    """

    #: The dotted field path (``"browser.timeout_ms"``). ``None`` if
    #: the error is not field-specific (e.g. a top-level TOML parse
    #: error).
    field: str | None
    #: The stringified offending value. ``None`` if the value is not
    #: representable as a string for the user's purposes (e.g. a
    #: Pydantic ``"missing"`` sentinel, which we map to ``None`` so a
    #: UI can render "this field is required" rather than "got
    #: 'missing'").
    value: str | None
    #: The human-readable constraint description
    #: (``"between 1 and 60000"``, ``"one of: 'chromium', 'firefox' or
    #: 'webkit'"``). ``None`` if the error has no constraint (e.g.
    #: ``extra_forbidden``, which has no "expected" in the
    #: constraints sense).
    expected: str | None


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


def _extract_fields(
    err: Mapping[str, Any],
    *,
    bounds: tuple[Any, Any] | None = None,
) -> _ErrorFields:
    """Extract the structured (field, value, expected) triple from a Pydantic error.

    Parameters
    ----------
    err
        One element of ``ValidationError.errors()``.
    bounds
        The declared bounds, if known. Same semantics as
        :func:`_format_error`'s ``bounds``.

    Returns
    -------
    _ErrorFields
        The structured fields, with ``None`` for any that do not apply.

    Notes
    -----
    The extraction is deliberately minimal and does not attempt to
    reverse-engineer Pydantic's message. It returns what the formatter
    already knows:

    * ``field`` from ``err["loc"]`` — always available when the error
      is field-specific.
    * ``value`` from ``err["input"]`` — ``None`` if the input is
      Pydantic's ``"missing"`` sentinel, since "the user forgot this
      field" is not a "value" the user can inspect.
    * ``expected`` — built from the same bound/constraint logic the
      formatter uses, but as a *constraint phrase* (``"between 1 and
      60000"``) rather than a full sentence. This is what a UI would
      put next to the field.

    The intent is that a consumer can build a form (field, value,
    expected) from these three attributes without parsing ``str()``.
    It is not a guarantee that every error has all three — some do not
    (``extra_forbidden`` has no value, some root errors have no field).
    """
    error_type: str = err.get("type", "") or ""
    input_value: object = err.get("input", "<missing>")
    loc = err.get("loc") or ()
    ctx: Mapping[str, Any] = err.get("ctx") or {}

    field_path = _format_loc(loc) if loc else None

    # Pydantic uses the string "missing" as the `input` sentinel for a
    # required field. "Got 'missing'" reads awkwardly; map it to None
    # so a UI can render its own "this field is required" message.
    value: str | None
    if input_value == "missing":
        value = None
    elif isinstance(input_value, str):
        value = input_value
    else:
        value = repr(input_value)

    expected: str | None = None

    if error_type in {
        "greater_than_equal",
        "greater_than",
        "less_than_equal",
        "less_than",
    }:
        if bounds is not None and bounds[0] is not None and bounds[1] is not None:
            expected = f"between {bounds[0]} and {bounds[1]}"
        else:
            lower = ctx.get("ge", ctx.get("gt"))
            upper = ctx.get("le", ctx.get("lt"))
            if lower is not None and upper is not None:
                expected = f"between {lower} and {upper}"
            elif lower is not None:
                expected = f"{_ERROR_TYPE_NAMES[error_type]} {lower}"
            elif upper is not None:
                expected = f"{_ERROR_TYPE_NAMES[error_type]} {upper}"

    elif error_type in {"string_too_short", "string_too_long"}:
        bound = ctx.get("min_length", ctx.get("max_length"))
        if bound is not None:
            expected = f"{_ERROR_TYPE_NAMES[error_type]} {bound} characters"

    elif error_type == "literal_error":
        expected = f"one of: {ctx.get('expected', '<valid values>')}"

    elif error_type == "extra_forbidden":
        # An unknown field has no "expected value" — the field itself
        # is the problem, not the value. Returning None here lets a UI
        # render "unknown field" specifically rather than "expected:
        # None".
        expected = None
        # The value is meaningless (the user did not set it; they set a
        # field we don't recognize). Set to None for the same reason.
        value = None

    return _ErrorFields(field=field_path, value=value, expected=expected)


def format_validation_error(
    exc: ValidationError,
    *,
    layer: str,
    path: str | None = None,
) -> tuple[str, _ErrorFields]:
    """Format a Pydantic ``ValidationError`` as a one-line message plus structured fields.

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
    tuple[str, _ErrorFields]
        ``(message, fields)`` where ``message`` is the human-readable
        single-line string (same shape as before this WBS) and
        ``fields`` is the structured ``(field, value, expected)``
        triple to attach to the exception.

        Example messages (bounds shown are the WBS 1.2.5 / ADR-011
        values; ``browser.timeout_ms`` uses ``[1, 60_000]``,
        ``api.timeout_seconds`` uses ``[1, 300]``):

        - TOML: ``"Invalid configuration in /path/to/forgeqa.toml: browser.timeout_ms must be between 1 and 60000, got 0"``
        - Env:  ``"Invalid environment variable: browser.timeout_ms must be between 1 and 60000, got 0"``
        - CLI:  ``"Invalid CLI override: browser.timeout_ms must be between 1 and 60000, got 0"``

        **No Pydantic traceback is included.** The message is a single
        line, ends with the offending value, and names the field path
        and the constraint. The caller's response is "fix this value",
        not "read a Python traceback".

    Notes
    -----
    **Signature change (WBS 1.2.6).** The return type changed from
    ``str`` to ``tuple[str, _ErrorFields]``. The only caller
    (``forgeqa.config.loader._raise_config_error``) is updated in the
    same commit. ``format_validation_error`` is **not** exported from
    :mod:`forgeqa.config` (it is internal), so the change is not
    user-facing. See ADR-012 §Decision #6.

    Multiple errors: the function formats the **first** error and
    appends ``" (and N more)"``. A full multi-line list is a follow-up
    (see ADR-010's reconsideration trigger); the single-error case is
    by far the most common. The structured fields describe the *first*
    error; that's what a UI or a one-line log record can reasonably
    display.

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
    to a safe default *before* the branch logic, so the function
    returns a string for any ``ValidationError`` and never raises
    ``UnboundLocalError``. This matters for two reasons: (a) a caller
    who passes a ``ValidationError`` whose ``errors()`` list is empty
    still gets a meaningful message; (b) a future refactor that
    restructures the branch logic cannot accidentally introduce a code
    path where the local is unassigned. The cost is one extra
    assignment per call; the benefit is a formatter that is safe to
    call from anywhere.
    """
    errors = exc.errors()
    if not errors:
        return (
            f"Invalid configuration ({layer}): <no errors reported>",
            _ErrorFields(field=None, value=None, expected=None),
        )
    first = errors[0]
    loc = first.get("loc", ())
    bounds = _declared_bounds_for(loc)
    detail = _format_error(first, bounds=bounds)
    fields = _extract_fields(first, bounds=bounds)
    extra = ""
    if len(errors) > 1:
        extra = f" (and {len(errors) - 1} more)"

    # `detail` already names the field (via `_format_error`'s
    # `field_name`). Prepend `_format_loc(loc)` only when it carries a
    # section, to avoid `"timeout_ms timeout_ms must be ..."`.
    # Ternary rather than if/else to satisfy ruff SIM108.
    prefix = _format_loc(loc) + " " if len(loc) >= 2 else ""

    # `message` is initialised before the branches so the function is
    # total; see "Total-function guarantee" above.
    message = f"Invalid configuration ({layer}): {prefix}{detail}{extra}"

    if layer == "TOML":
        path_part = path if path is not None else "(unknown path)"
        message = f"Invalid configuration in {path_part}: {prefix}{detail}{extra}"
    elif layer == "environment variable":
        message = f"Invalid environment variable: {prefix}{detail}{extra}"
    else:
        message = f"Invalid CLI override: {prefix}{detail}{extra}"

    return message, fields


__all__ = [
    "ForgeQAConfigError",
    "format_validation_error",
]
