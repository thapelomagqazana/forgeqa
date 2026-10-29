"""Unit tests for ForgeQA's field-level validators and error formatter.

These tests cover WBS 1.2.4:

* Invalid ``timeout_ms`` raises a clear error mentioning the field
  and the valid range.
* Invalid ``browser_name`` raises a clear error listing the valid
  options.
* The error message does **not** expose internal Pydantic tracebacks
  (no ``pydantic_core``, no ``[type=..., input_value=..., input_type=...]``
  annotations, no multiline traceback).
* Every custom validator and every formatted error has a test.

The tests are in a separate file from ``test_models.py`` because the
WBS lists a distinct deliverable (``test_validation.py``) and because
the assertions here are about the *message*, not the *acceptance*.
``test_models.py`` covers "is this value valid?"; this file covers
"what does the user see when it is not?".

**Relation to ADR-011 (WBS 1.2.5).** The ``browser.timeout_ms`` lower
bound was relaxed from ``100`` to ``1`` in WBS 1.2.5, because that
WBS's boundary test requires ``timeout_ms=1`` to be legal. As a
consequence:

* The formatted error message now says ``"between 1 and 60000"``, not
  ``"between 100 and 60000"``.
* Values ``50`` and ``99`` are now legal — the tests that used them as
  "invalid" examples have been updated to use ``0`` or ``-1`` (which
  are still invalid).
* Every test in this file that used ``timeout_ms=50`` as a "this must
  raise" input now uses ``timeout_ms=0``, which has the same shape
  (below the lower bound) but is actually invalid under the new
  bound.

The ``api.timeout_seconds`` lower bound was **not** relaxed — it is
still ``1``, and values ``0``, ``-1``, ``301``, ``1000`` are still
rejected. See ADR-011 §Decision #5.

**Relation to ADR-012 (WBS 1.2.6).** ``format_validation_error`` now
returns a ``(message, fields)`` tuple (see ADR-012 §Decision #6); the
``message`` is byte-for-byte identical to the pre-1.2.6 string, and
``fields`` is a ``_ErrorFields`` NamedTuple carrying ``field``,
``value``, and ``expected`` for structured access. This file unpacks
the tuple at every call site — a future test that wants to assert on
the structured fields can read ``fields.field`` etc., but the
assertions here are about the *string*, so the unpacking uses ``_``
for the unused half. This is the "comparison semantics, not string
equality" rule applied to the return type: compare against what the
contract guarantees, not against a particular shape.

Run only these tests:

    pytest tests/unit/config/test_validation.py -v
    # or
    make verify-config
"""

from __future__ import annotations

import re

import pytest
from pydantic import ValidationError

from forgeqa.config import (
    APIConfig,
    BrowserConfig,
    ForgeQAConfig,
    ForgeQAConfigError,
    GeneralConfig,
    load_config,
)
from forgeqa.config.errors import format_validation_error

pytestmark = pytest.mark.unit


#: Pydantic's internal error annotations look like
#: ``[type=greater_than_equal, input_value=50, input_type=int]``.
#: The formatter must strip them; the tests assert the pattern is
#: absent from the final message.
_PYDANTIC_INTERNAL_RE = re.compile(r"\[type=|input_value=|input_type=|pydantic_core")


def _assert_clean(message: str) -> None:
    """Assert the message has no Pydantic internals or traceback text.

    Parameters
    ----------
    message
        The formatted message to check. This is the *string* half of
        the ``(message, fields)`` tuple returned by
        :func:`format_validation_error` — the caller unpacks the
        tuple and passes the message here. Passing the tuple itself
        would raise ``TypeError`` on ``search``; that would be a test
        bug, not a formatter bug.

    Raises
    ------
    AssertionError
        If the message contains Pydantic's internal type annotations,
        ``pydantic_core``, or a multi-line traceback.
    """
    assert _PYDANTIC_INTERNAL_RE.search(message) is None, (
        f"Pydantic internals leaked into the message: {message!r}"
    )
    assert "Traceback" not in message, f"Traceback text leaked into the message: {message!r}"
    assert "\n" not in message.strip(), (
        f"Message is multi-line (should be single-line): {message!r}"
    )


# =============================================================================
# Custom validators: timeout_ms (bounded integer)
# =============================================================================


@pytest.mark.parametrize(
    "value",
    [
        0,  # zero — the *only* small-integer invalid value now (lower bound is 1)
        -1,  # negative
        -10_000,  # well negative
        60_001,  # boundary+1 (above maximum)
        100_000,  # well above
    ],
)
def test_invalid_timeout_ms_rejected_with_range(value: int) -> None:
    """Given a ``timeout_ms`` outside [1, 60000], when constructing ``BrowserConfig``, then it raises ``ValidationError``.

    The error's ``msg`` and the formatted message must mention the
    field, the valid range, and the offending value.

    **Range note.** The lower bound was relaxed from ``100`` to ``1``
    in WBS 1.2.5 / ADR-011 §Decision #5. Values ``50`` and ``99``,
    which the pre-1.2.5 version of this test treated as invalid, are
    now legal — they are covered by
    :func:`test_valid_timeout_ms_accepted` with the new boundaries.
    Only ``0`` and negatives are rejected below the lower bound.

    **Return-type note.** ``format_validation_error`` returns
    ``(message, fields)`` since WBS 1.2.6; the tuple is unpacked here
    and ``_`` discards the structured half (this test is about the
    string).
    """
    with pytest.raises(ValidationError) as exc_info:
        BrowserConfig(timeout_ms=value)

    error = exc_info.value.errors()[0]
    assert error["loc"] == ("timeout_ms",)
    # The formatted message names the range and the value. Unpack the
    # (message, fields) tuple from the 1.2.6 formatter; discard the
    # structured fields (this test asserts on the string).
    formatted, _ = format_validation_error(exc_info.value, layer="TOML", path="forgeqa.toml")
    assert "timeout_ms" in formatted
    # Range string changed 100→1 in WBS 1.2.5 (see ADR-011 §Decision #5).
    assert "between 1 and 60000" in formatted
    assert str(value) in formatted
    _assert_clean(formatted)


@pytest.mark.parametrize("value", [1, 99, 100, 10_000, 60_000])
def test_valid_timeout_ms_accepted(value: int) -> None:
    """Given a ``timeout_ms`` inside [1, 60000], when constructing ``BrowserConfig``, then it succeeds.

    Boundary values (``1`` and ``60_000``) are included; the field is
    inclusive on both bounds. ``99`` and ``100`` are included
    explicitly because ``99`` was *rejected* under the pre-1.2.5
    ``ge=100`` bound and is now legal — this test pins the relaxation
    (see ADR-011 §Consequences, Neutral).
    """
    cfg = BrowserConfig(timeout_ms=value)
    assert cfg.timeout_ms == value


# =============================================================================
# Custom validators: timeout_seconds (bounded integer)
# =============================================================================


@pytest.mark.parametrize("value", [0, -1, 301, 1000])
def test_invalid_timeout_seconds_rejected(value: int) -> None:
    """Given a ``timeout_seconds`` outside [1, 300], when constructing ``APIConfig``, then it raises ``ValidationError``.

    The formatted message names the field and the range. The bounds
    are unchanged from WBS 1.2.4 (only ``browser.timeout_ms`` was
    relaxed in WBS 1.2.5).

    **Return-type note.** Same as
    :func:`test_invalid_timeout_ms_rejected_with_range` — the
    ``(message, fields)`` tuple is unpacked and the structured half
    is discarded.
    """
    with pytest.raises(ValidationError) as exc_info:
        APIConfig(timeout_seconds=value)
    formatted, _ = format_validation_error(exc_info.value, layer="TOML", path="forgeqa.toml")
    assert "timeout_seconds" in formatted
    assert "between 1 and 300" in formatted
    _assert_clean(formatted)


@pytest.mark.parametrize("value", [1, 10, 300])
def test_valid_timeout_seconds_accepted(value: int) -> None:
    """Given a ``timeout_seconds`` inside [1, 300], when constructing ``APIConfig``, then it succeeds."""
    cfg = APIConfig(timeout_seconds=value)
    assert cfg.timeout_seconds == value


# =============================================================================
# Custom validators: browser_name (Literal)
# =============================================================================


def test_invalid_browser_name_lists_valid_options() -> None:
    """Given ``browser_name='safari'``, when constructing ``BrowserConfig``, then the error lists valid options.

    The formatted message must say ``must be one of:`` and list
    chromium, firefox, and webkit.
    """
    with pytest.raises(ValidationError) as exc_info:
        BrowserConfig(browser_name="safari")  # type: ignore[arg-type]

    formatted, _ = format_validation_error(exc_info.value, layer="TOML", path="forgeqa.toml")
    assert "browser_name" in formatted
    assert "one of:" in formatted
    for valid in ("chromium", "firefox", "webkit"):
        assert valid in formatted
    assert "safari" in formatted
    _assert_clean(formatted)


# =============================================================================
# Custom validators: artifacts_dir (creatable directory)
# =============================================================================


def test_artifacts_dir_accepts_default() -> None:
    """Given the default ``artifacts_dir="artifacts"``, when constructing ``GeneralConfig``, then it succeeds.

    The default is a relative path; the validator resolves it against
    cwd, whose nearest existing ancestor is cwd itself (writable on a
    normal dev machine).
    """
    cfg = GeneralConfig()
    assert cfg.artifacts_dir == "artifacts"


def test_artifacts_dir_accepts_existing_directory(tmp_path) -> None:
    """Given an existing directory, when constructing ``GeneralConfig``, then it succeeds."""
    cfg = GeneralConfig(artifacts_dir=str(tmp_path))
    assert cfg.artifacts_dir == str(tmp_path)


def test_artifacts_dir_accepts_nonexistent_under_writable_parent(tmp_path) -> None:
    """Given a nonexistent path under a writable parent, when constructing, then it succeeds.

    The validator's job is to prove the path *can* be created; it must
    not require the path to exist (the directory is created on first
    write, per ADR-010 Decision #3).
    """
    candidate = tmp_path / "new-run-abc"
    assert not candidate.exists()
    cfg = GeneralConfig(artifacts_dir=str(candidate))
    assert cfg.artifacts_dir == str(candidate)


def test_artifacts_dir_rejects_existing_file(tmp_path) -> None:
    """Given a path that is an existing file, when constructing, then it raises ``ValidationError``.

    The message names the path and says it points at a file, not a
    directory.
    """
    file_path = tmp_path / "some_file"
    file_path.write_text("x", encoding="utf-8")

    with pytest.raises(ValidationError) as exc_info:
        GeneralConfig(artifacts_dir=str(file_path))

    formatted, _ = format_validation_error(exc_info.value, layer="TOML", path="forgeqa.toml")
    assert "existing file" in formatted
    assert str(file_path) in formatted
    _assert_clean(formatted)


def test_artifacts_dir_rejects_unwritable_parent(tmp_path) -> None:
    """Given a path whose parent is not writable, when constructing, then it raises ``ValidationError``.

    The test uses ``chmod`` on a tmp directory to make it read-only;
    this works on POSIX. On platforms where ``chmod`` is a no-op (some
    Windows filesystems), the test is skipped.
    """
    import os
    import stat

    read_only = tmp_path / "read_only"
    read_only.mkdir()
    original_mode = read_only.stat().st_mode
    try:
        os.chmod(read_only, stat.S_IREAD | stat.S_IEXEC)
        # Skip if the OS did not actually make it read-only (e.g. running
        # as root, or on a filesystem that ignores chmod).
        if os.access(read_only, os.W_OK):
            pytest.skip("Filesystem does not enforce read-only permissions")

        with pytest.raises(ValidationError) as exc_info:
            GeneralConfig(artifacts_dir=str(read_only / "subdir"))

        formatted, _ = format_validation_error(exc_info.value, layer="TOML", path="forgeqa.toml")
        assert "not writable" in formatted
        _assert_clean(formatted)
    finally:
        os.chmod(read_only, original_mode)


# =============================================================================
# No traceback in the ForgeQAConfigError message (end-to-end)
# =============================================================================


def test_loader_wraps_timeout_error_without_traceback(tmp_path, monkeypatch) -> None:
    """Given an invalid ``timeout_ms`` in TOML, when loaded, then the error names the range and has no traceback.

    This is the WBS acceptance criterion "Invalid timeout_ms raises a
    clear error mentioning the field and valid range" and "The error
    message does not expose internal Pydantic tracebacks", end-to-end
    through the loader.

    **Invalid value note.** Uses ``timeout_ms = 0`` (below the
    ``ge=1`` lower bound). The pre-1.2.5 version used ``50``, which is
    now legal (see ADR-011 §Decision #5) and therefore would not
    raise.

    **Exception-shape note.** ``str(exc_info.value)`` is the
    human-readable message (unchanged by WBS 1.2.6); the new
    structured fields are on the exception's attributes and are
    asserted in ``test_errors.py``. This test is about the message.
    """
    (tmp_path / "forgeqa.toml").write_text("[browser]\ntimeout_ms = 0\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path)

    with pytest.raises(ForgeQAConfigError) as exc_info:
        load_config(environ={})

    message = str(exc_info.value)
    assert "browser.timeout_ms" in message
    # Range string changed 100→1 in WBS 1.2.5.
    assert "between 1 and 60000" in message
    assert "0" in message
    _assert_clean(message)


def test_loader_wraps_browser_name_error_without_traceback(tmp_path, monkeypatch) -> None:
    """Given an invalid ``browser_name`` in TOML, when loaded, then the error lists valid options and has no traceback."""
    (tmp_path / "forgeqa.toml").write_text('[browser]\nbrowser_name = "safari"\n', encoding="utf-8")
    monkeypatch.chdir(tmp_path)

    with pytest.raises(ForgeQAConfigError) as exc_info:
        load_config(environ={})

    message = str(exc_info.value)
    assert "browser.browser_name" in message
    assert "one of:" in message
    for valid in ("chromium", "firefox", "webkit"):
        assert valid in message
    _assert_clean(message)


def test_loader_wraps_artifacts_dir_error_without_traceback(tmp_path, monkeypatch) -> None:
    """Given an invalid ``artifacts_dir`` in TOML, when loaded, then the error names the directory problem and has no traceback."""
    bad_file = tmp_path / "not_a_dir"
    bad_file.write_text("x", encoding="utf-8")

    (tmp_path / "forgeqa.toml").write_text(
        f'[general]\nartifacts_dir = "{bad_file}"\n', encoding="utf-8"
    )
    monkeypatch.chdir(tmp_path)

    with pytest.raises(ForgeQAConfigError) as exc_info:
        load_config(environ={})

    message = str(exc_info.value)
    assert "general.artifacts_dir" in message
    assert "existing file" in message
    _assert_clean(message)


def test_env_var_error_has_no_traceback(tmp_path, monkeypatch) -> None:
    """Given an invalid ``timeout_ms`` env var, when loaded, then the error names the var, the range, and has no traceback.

    **Invalid value note.** Uses ``"0"`` (below the ``ge=1`` lower
    bound). The pre-1.2.5 version used ``"50"``, which is now legal.
    """
    monkeypatch.chdir(tmp_path)

    with pytest.raises(ForgeQAConfigError) as exc_info:
        load_config(environ={"FORGEQA_BROWSER_TIMEOUT_MS": "0"})

    message = str(exc_info.value)
    assert "FORGEQA_BROWSER_TIMEOUT_MS" in message
    # Range string changed 100→1 in WBS 1.2.5.
    assert "between 1 and 60000" in message
    _assert_clean(message)


def test_cli_override_error_has_no_traceback(tmp_path, monkeypatch) -> None:
    """Given an invalid CLI override, when loaded, then the error names the field, the range, and has no traceback.

    **Invalid value note.** Uses ``timeout_ms=0`` (below the ``ge=1``
    lower bound). The pre-1.2.5 version used ``50``, which is now
    legal.
    """
    monkeypatch.chdir(tmp_path)

    with pytest.raises(ForgeQAConfigError) as exc_info:
        load_config(
            environ={},
            cli_overrides={"browser": {"timeout_ms": 0}},
        )

    message = str(exc_info.value)
    assert "browser.timeout_ms" in message
    # Range string changed 100→1 in WBS 1.2.5.
    assert "between 1 and 60000" in message
    _assert_clean(message)


# =============================================================================
# format_validation_error: direct tests
# =============================================================================


def test_format_validation_error_toml_layer() -> None:
    """Given a ``ValidationError`` and ``layer="TOML"``, then the message starts with ``"Invalid configuration in <path>:"``.

    **Invalid value note.** Uses ``timeout_ms=0`` so the ``try`` body
    actually raises. The pre-1.2.5 version used ``50``, which is now
    legal and therefore does not raise — which caused the previous
    version of this test to fail with ``UnboundLocalError`` (the
    ``except`` block never ran, so the local ``message`` was never
    assigned).

    **Return-type note.** ``format_validation_error`` returns
    ``(message, fields)`` since WBS 1.2.6; the tuple is unpacked
    here so ``message`` remains a ``str``. The structured half is
    discarded (this test asserts on the string prefix).
    """
    try:
        BrowserConfig(timeout_ms=0)
    except ValidationError as exc:
        message, _ = format_validation_error(exc, layer="TOML", path="/p/forgeqa.toml")
    assert message.startswith("Invalid configuration in /p/forgeqa.toml: ")
    assert "browser.timeout_ms" in message or "timeout_ms" in message


def test_format_validation_error_env_layer() -> None:
    """Given a ``ValidationError`` and ``layer="environment variable"``, then the message starts with ``"Invalid environment variable:"``.

    **Invalid value note.** Uses ``timeout_ms=0`` (still invalid under
    the ``ge=1`` lower bound). The pre-1.2.5 version used ``50``, which
    is now legal and would not raise.
    """
    try:
        BrowserConfig(timeout_ms=0)
    except ValidationError as exc:
        message, _ = format_validation_error(exc, layer="environment variable")
    assert message.startswith("Invalid environment variable: ")


def test_format_validation_error_cli_layer() -> None:
    """Given a ``ValidationError`` and ``layer="CLI override"``, then the message starts with ``"Invalid CLI override:"``.

    **Invalid value note.** Uses ``timeout_ms=0`` (still invalid under
    the ``ge=1`` lower bound). The pre-1.2.5 version used ``50``, which
    is now legal and would not raise.
    """
    try:
        BrowserConfig(timeout_ms=0)
    except ValidationError as exc:
        message, _ = format_validation_error(exc, layer="CLI override")
    assert message.startswith("Invalid CLI override: ")


def test_format_validation_error_with_multiple_errors() -> None:
    """Given a ``ValidationError`` with multiple errors, then the message names the first and says ``"(and N more)"``.

    A full multi-line list is a follow-up (ADR-010 reconsideration
    trigger); the single-line form with the "and N more" suffix is
    what a user sees today.

    **Invalid value note.** Uses ``timeout_ms=0`` (still invalid) so
    two errors are produced. The pre-1.2.5 version used ``timeout_ms=50``,
    which is now legal — that produced only one error
    (``api.timeout_seconds``), so the ``"(and 1 more)"`` suffix was
    never present.
    """
    try:
        ForgeQAConfig(
            browser={"timeout_ms": 0},
            api={"timeout_seconds": 999},
        )
    except ValidationError as exc:
        message, _ = format_validation_error(exc, layer="TOML", path="forgeqa.toml")
    assert "(and 1 more)" in message


def test_format_validation_error_extra_forbidden() -> None:
    """Given a ``ValidationError`` for an unknown key, then the message says ``"unexpected field: <name>"``."""
    try:
        BrowserConfig(**{"timout_ms": 1000})  # type: ignore[arg-type]
    except ValidationError as exc:
        message, _ = format_validation_error(exc, layer="TOML", path="forgeqa.toml")
    assert "unexpected field: timout_ms" in message
    _assert_clean(message)
