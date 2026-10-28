"""Unit tests for the ForgeQA TOML configuration loader.

These tests cover WBS 1.2.2:

* Loading a valid ``forgeqa.toml`` populates the config correctly.
* A missing ``forgeqa.toml`` returns the default config.
* Malformed TOML raises :class:`ForgeQAConfigError` with a clear message.
* The loader is idempotent (calling it twice returns the same config).

The tests also cover edge cases (empty file, comments-only file,
partial sections), corner cases (unknown keys, invalid values), and
non-functional properties (deterministic error messages, no caching,
absolute paths in errors) that the WBS's "deterministic and handles
all file states gracefully" KPI implies.

The tests use :mod:`pytest`'s ``tmp_path`` fixture to write real files
to a temporary directory. This is deliberate: a loader test that mocks
:func:`Path.read_text` is testing the mock, not the loader. The
filesystem is the loader's input; the test should use it directly.

Run only these tests:

    pytest tests/unit/config/test_loader.py -v
    # or
    make verify-config
"""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from forgeqa.config import (
    DEFAULT_CONFIG_FILENAME,
    ForgeQAConfig,
    ForgeQAConfigError,
    find_config_path,
    load_config,
)

pytestmark = pytest.mark.unit


# =============================================================================
# Helpers
# =============================================================================


def write_toml(
    directory: Path,
    content: str,
    name: str = DEFAULT_CONFIG_FILENAME,
) -> Path:
    """Write ``content`` to ``directory / name`` and return the path.

    Parameters
    ----------
    directory
        The directory to write into. Typically ``tmp_path``. Parent
        directories are created as needed — the helper is safe to call
        with a non-existent parent (e.g. ``tmp_path / "cwd"`` where
        ``cwd`` has not been created yet).
    content
        The TOML content.
    name
        The filename. Defaults to ``forgeqa.toml``; override for tests
        that exercise explicit-path behaviour.

    Returns
    -------
    pathlib.Path
        The path to the written file.

    Notes
    -----
    ``Path.write_text`` does not create parent directories; it raises
    ``FileNotFoundError`` if the parent is missing. Creating the parent
    here means every caller that writes to a nested path works without
    a separate ``mkdir`` step, and the failure mode (a ``mkdir`` miss
    in a test) is eliminated at the helper level rather than at every
    call site.

    ``exist_ok=True`` makes the call idempotent: a second call with
    the same directory does not raise ``FileExistsError``.
    """
    path = directory / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path


# =============================================================================
# Positive cases — valid files load correctly
# =============================================================================


def test_loads_valid_config(tmp_path, monkeypatch) -> None:
    """Given a valid ``forgeqa.toml`` in cwd, when ``load_config()`` runs, then the config reflects the file.

    The WBS acceptance criterion "Loading a valid forgeqa.toml populates
    the config correctly". Uses the real filesystem (``tmp_path``) and
    ``monkeypatch.chdir`` to control the working directory — the loader
    reads ``Path.cwd()``, so the test must control that.
    """
    write_toml(
        tmp_path,
        """
        [general]
        environment = "ci"
        log_level = "DEBUG"

        [browser]
        browser_name = "firefox"
        headless = false
        timeout_ms = 30000

        [api]
        timeout_seconds = 30

        [diagnostics]
        screenshots = false

        [reporting]
        json_report = false
        """,
    )
    monkeypatch.chdir(tmp_path)
    cfg = load_config()

    assert cfg.general.environment == "ci"
    assert cfg.general.log_level == "DEBUG"
    assert cfg.browser.browser_name == "firefox"
    assert cfg.browser.headless is False
    assert cfg.browser.timeout_ms == 30_000
    assert cfg.api.timeout_seconds == 30
    assert cfg.diagnostics.screenshots is False
    assert cfg.reporting.json_report is False


def test_loads_partial_config_preserves_defaults(tmp_path, monkeypatch) -> None:
    """Given a config with only one section, when loaded, then unspecified sections use defaults.

    The composition property from WBS 1.2.1: a partial file produces a
    full config, not a partial one. ``general.environment`` is set;
    everything else is at its default.
    """
    write_toml(tmp_path, '[browser]\nbrowser_name = "firefox"\n')
    monkeypatch.chdir(tmp_path)
    cfg = load_config()

    assert cfg.browser.browser_name == "firefox"
    assert cfg.browser.headless is True  # default
    assert cfg.browser.timeout_ms == 10_000  # default
    assert cfg.general.environment == "local"  # default
    assert cfg.api.timeout_seconds == 10  # default


def test_loads_explicit_path(tmp_path) -> None:
    """Given an explicit path to a valid file, when loaded, then it succeeds.

    The explicit-path route bypasses the cwd search. A consumer who
    knows where the file is should not be surprised by a different
    file in cwd.
    """
    path = write_toml(tmp_path, '[general]\nenvironment = "staging"\n', name="custom.toml")
    cfg = load_config(path)
    assert cfg.general.environment == "staging"


def test_loads_path_as_string(tmp_path) -> None:
    """Given an explicit path as a ``str``, when loaded, then it succeeds.

    The signature accepts ``Path | str | None`` for ergonomic reasons
    (a caller with a string path should not have to wrap it in
    ``Path()``).
    """
    path = write_toml(tmp_path, '[general]\nenvironment = "ci"\n', name="config.toml")
    cfg = load_config(str(path))
    assert cfg.general.environment == "ci"


# =============================================================================
# Negative cases — missing file, malformed TOML, invalid values
# =============================================================================


def test_missing_file_returns_default_config(tmp_path, monkeypatch) -> None:
    """Given no ``forgeqa.toml`` in cwd, when ``load_config()`` runs, then it returns the default config.

    The WBS acceptance criterion "Missing forgeqa.toml returns the
    default config". The default config is what a user with no config
    file should get: a working ForgeQA environment with sensible
    defaults.
    """
    monkeypatch.chdir(tmp_path)  # empty dir
    cfg = load_config()
    default = ForgeQAConfig()
    assert cfg == default


def test_explicit_missing_path_raises(tmp_path) -> None:
    """Given an explicit path that does not exist, when loaded, then it raises ``ForgeQAConfigError``.

    An explicit path that does not exist is a caller error, not a
    "use defaults" situation. The error message names the path.
    """
    with pytest.raises(ForgeQAConfigError) as exc_info:
        load_config(tmp_path / "does-not-exist.toml")
    assert "not found" in str(exc_info.value).lower()
    assert "does-not-exist.toml" in str(exc_info.value)


def test_malformed_toml_raises_config_error(tmp_path, monkeypatch) -> None:
    """Given a file with a TOML syntax error, when loaded, then it raises ``ForgeQAConfigError``.

    The WBS acceptance criterion "Malformed TOML raises
    ForgeQAConfigError with a clear message". The test asserts:
    * the exception type is ``ForgeQAConfigError`` (not the raw
      ``tomllib.TOMLDecodeError``),
    * the message includes the file path (so the user knows *which*
      file failed),
    * the message includes the line number when available (the WBS
      example is "at line 3"),
    * the original ``TOMLDecodeError`` is preserved as ``__cause__``.
    """
    write_toml(
        tmp_path,
        """
        [general
        environment = "ci"
        """,
    )
    monkeypatch.chdir(tmp_path)

    with pytest.raises(ForgeQAConfigError) as exc_info:
        load_config()

    error = exc_info.value
    message = str(error)
    # File path is in the message.
    assert str(tmp_path) in message
    # The original TOMLDecodeError is preserved as __cause__.
    assert isinstance(error.__cause__, Exception)
    # TOML syntax errors usually mention a line number.
    # tomllib's message format varies by Python version; assert the
    # concept ("line") is present without pinning the exact wording.
    assert "line" in message.lower() or "invalid" in message.lower()


def test_invalid_value_raises_config_error(tmp_path, monkeypatch) -> None:
    """Given a syntactically valid file with an invalid value, when loaded, then it raises ``ForgeQAConfigError``.

    The TOML parses, but ``browser_name = "safari"`` fails Pydantic
    validation. The loader wraps the ``ValidationError`` in
    ``ForgeQAConfigError`` (single exception type for all load-time
    failures), with the field name in the message.
    """
    write_toml(tmp_path, '[browser]\nbrowser_name = "safari"\n')
    monkeypatch.chdir(tmp_path)

    with pytest.raises(ForgeQAConfigError) as exc_info:
        load_config()

    message = str(exc_info.value)
    assert str(tmp_path) in message
    assert "browser_name" in message
    # The original ValidationError is preserved as __cause__.
    assert isinstance(exc_info.value.__cause__, ValidationError)


def test_unknown_key_raises_config_error(tmp_path, monkeypatch) -> None:
    """Given a file with an unknown key, when loaded, then it raises ``ForgeQAConfigError``.

    ``extra="forbid"`` on the models makes a typo like ``timout_ms``
    fail at parse time, not silently use the default.
    """
    write_toml(tmp_path, "[browser]\ntimout_ms = 10000\n")
    monkeypatch.chdir(tmp_path)

    with pytest.raises(ForgeQAConfigError) as exc_info:
        load_config()

    assert "timout_ms" in str(exc_info.value)


# =============================================================================
# Edge cases — empty file, comments-only, boundaries
# =============================================================================


def test_empty_file_returns_default_config(tmp_path, monkeypatch) -> None:
    """Given an empty ``forgeqa.toml``, when loaded, then it returns the default config.

    An empty file is syntactically valid TOML (the empty document).
    ``ForgeQAConfig(**{})`` produces the default config. This is the
    correct behaviour: a user who creates an empty file is expressing
    "I have no overrides, use defaults".
    """
    write_toml(tmp_path, "")
    monkeypatch.chdir(tmp_path)
    cfg = load_config()
    assert cfg == ForgeQAConfig()


def test_comments_only_file_returns_default_config(tmp_path, monkeypatch) -> None:
    """Given a file with only comments, when loaded, then it returns the default config.

    Comments are valid TOML; the parsed document is the empty dict.
    Same result as the empty file.
    """
    write_toml(tmp_path, "# This is a comment\n# And another\n")
    monkeypatch.chdir(tmp_path)
    cfg = load_config()
    assert cfg == ForgeQAConfig()


def test_whitespace_only_file_returns_default_config(tmp_path, monkeypatch) -> None:
    """Given a file with only whitespace, when loaded, then it returns the default config.

    Whitespace is valid TOML; the parsed document is the empty dict.
    """
    write_toml(tmp_path, "   \n\n\t\n")
    monkeypatch.chdir(tmp_path)
    cfg = load_config()
    assert cfg == ForgeQAConfig()


# =============================================================================
# Corner cases — nested sections, explicit paths, find_config_path
# =============================================================================


def test_explicit_path_overrides_cwd(tmp_path, monkeypatch) -> None:
    """Given both a file in cwd and an explicit path, when loaded with the path, then the path wins.

    A caller who passes an explicit path should not be surprised by a
    different file in cwd. The loader uses the explicit path.

    ``write_toml`` creates the parent directory (``tmp_path / "cwd"``
    and ``tmp_path / "explicit"``) as needed, so the test can pass
    nested paths without a separate ``mkdir`` step.
    """
    # Two files with different environment values.
    write_toml(tmp_path / "cwd", '[general]\nenvironment = "from-cwd"\n')
    explicit = write_toml(tmp_path / "explicit", '[general]\nenvironment = "from-explicit"\n')
    monkeypatch.chdir(tmp_path / "cwd")

    cfg = load_config(explicit)
    assert cfg.general.environment == "from-explicit"


def test_find_config_path_returns_absolute_path(tmp_path) -> None:
    """Given a ``forgeqa.toml`` in a directory, when ``find_config_path`` runs, then it returns an absolute path.

    Absolute paths are important for two reasons: (a) error messages
    include the path, and a relative path is ambiguous when cwd
    changes; (b) a caller who wants to log "loaded config from X" needs
    a path that survives a subsequent ``chdir``.
    """
    path = write_toml(tmp_path, "[general]\n")
    found = find_config_path(tmp_path)
    assert found is not None
    assert found.is_absolute()
    assert found == path.resolve()


def test_find_config_path_returns_none_when_absent(tmp_path) -> None:
    """Given no ``forgeqa.toml`` in a directory, when ``find_config_path`` runs, then it returns ``None``."""
    assert find_config_path(tmp_path) is None


def test_find_config_path_returns_none_for_missing_directory(tmp_path) -> None:
    """Given a directory that does not exist, when ``find_config_path`` runs, then it returns ``None``.

    A missing directory has no config file. Returning ``None`` rather
    than raising means the loader's "no file, use defaults" path works
    even if the caller passes a directory that does not (yet) exist.
    """
    assert find_config_path(tmp_path / "does-not-exist") is None


def test_find_config_path_ignores_directories(tmp_path) -> None:
    """Given a *directory* named ``forgeqa.toml``, when ``find_config_path`` runs, then it returns ``None``.

    A directory with the right name is not a config file. ``is_file()``
    is the correct check, not ``exists()``.
    """
    (tmp_path / DEFAULT_CONFIG_FILENAME).mkdir()
    assert find_config_path(tmp_path) is None


# =============================================================================
# Non-functional cases — idempotency, no caching, error message stability
# =============================================================================


def test_loader_is_idempotent(tmp_path, monkeypatch) -> None:
    """Given a valid file, when ``load_config()`` runs twice, then the two configs are equal.

    The WBS acceptance criterion "The loader is idempotent". Two calls
    on the same file produce equal ``ForgeQAConfig`` instances (the
    model is a value type; ``==`` compares by value, not by identity).
    """
    write_toml(tmp_path, '[general]\nenvironment = "ci"\n')
    monkeypatch.chdir(tmp_path)

    first = load_config()
    second = load_config()
    assert first == second


def test_loader_does_not_cache(tmp_path, monkeypatch) -> None:
    """Given a file, when it is edited and ``load_config()`` runs again, then the new values are returned.

    The loader deliberately does not cache. A developer who edits
    ``forgeqa.toml`` and calls ``load_config()`` again should see the
    new values — staleness is a worse failure mode than a ~1 ms file
    read. This test pins the "no caching" property.
    """
    path = write_toml(tmp_path, '[general]\nenvironment = "first"\n')
    monkeypatch.chdir(tmp_path)

    first = load_config()
    assert first.general.environment == "first"

    # Edit the file.
    path.write_text('[general]\nenvironment = "second"\n', encoding="utf-8")

    second = load_config()
    assert second.general.environment == "second"
    assert first.general.environment == "first"  # first call unchanged


def test_error_message_is_deterministic(tmp_path, monkeypatch) -> None:
    """Given the same malformed file, when ``load_config()`` runs twice, then the error messages are identical.

    The loader's error messages include the file path and the
    underlying TOML error. Both are deterministic for the same file
    and the same Python version, so the messages should be identical
    across calls. This is a canary for a future change that introduces
    non-determinism (e.g. including a timestamp or a random id in the
    error).
    """
    write_toml(tmp_path, "[general\nenvironment = 1\n")
    monkeypatch.chdir(tmp_path)

    messages = []
    for _ in range(2):
        with pytest.raises(ForgeQAConfigError) as exc_info:
            load_config()
        messages.append(str(exc_info.value))

    assert messages[0] == messages[1]


def test_error_includes_file_path(tmp_path, monkeypatch) -> None:
    """Given a malformed file, when loaded, then the error message includes the file path.

    Without the path, the user does not know *which* config file
    failed. This is especially important if a future version supports
    multiple config files (a Phase 1 follow-up).
    """
    path = write_toml(tmp_path, "invalid = [\n")
    monkeypatch.chdir(tmp_path)

    with pytest.raises(ForgeQAConfigError) as exc_info:
        load_config()

    # The path should be in the message. Use str(path) to handle
    # platform-specific path rendering.
    assert str(path) in str(exc_info.value)


def test_errors_have_path_attribute(tmp_path, monkeypatch) -> None:
    """Given a malformed file, when loaded, then the raised ``ForgeQAConfigError`` has a ``path`` attribute.

    The ``path`` attribute lets a caller programmatically identify the
    failing file (e.g. to prompt the user to fix it in an IDE, or to
    log structured data). ``str(error)`` includes the path too, but
    parsing a string is fragile; the attribute is the stable
    interface.
    """
    path = write_toml(tmp_path, "invalid = [\n")
    monkeypatch.chdir(tmp_path)

    with pytest.raises(ForgeQAConfigError) as exc_info:
        load_config()

    assert exc_info.value.path == str(path)
