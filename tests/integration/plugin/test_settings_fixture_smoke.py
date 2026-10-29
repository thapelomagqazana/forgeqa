"""ATDD: the ``settings`` fixture is session-scoped and shared.

These tests invoke a real ``pytest`` subprocess in a temp directory.
They are the only way to prove, end to end:

* pytest discovers the ``settings`` fixture (via ``pytest_plugins``
  in ``forgeqa.pytest_plugin``);
* pytest treats it as session-scoped — the fixture body runs **once**
  even when multiple test files use it;
* the returned config has a working ``api.base_url`` from a real
  ``forgeqa.toml`` that the test wrote into the temp project;
* an invalid ``forgeqa.toml`` causes pytest to report a fixture-setup
  error naming the offending file, not a cryptic failure.

The unit tests (``tests/unit/test_settings_fixture.py``) prove the
fixture body itself works; these prove pytest's invocation of it.

See also
--------
* ``tests/integration/plugin/conftest.py`` — ``isolated_project``
  fixture and ``run_pytest_in`` helper (reused here).
* ADR-014 — the design decision for the fixture.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from .conftest import run_pytest_in

pytestmark = [pytest.mark.integration]


# The `conftest.py` written into each temp project. It wraps the
# fixture body's `load_config` call with a counter and writes the count
# to a file after the session finishes. The count proves session scope:
# 1 means "resolved once per session" (the WBS acceptance criterion),
# 2+ means the fixture body ran per test and the scope is wrong.
_CONFTEST_COUNTER = '''\
"""Test-local conftest: count load_config calls and report them."""

import atexit
from unittest.mock import patch

import forgeqa.fixtures.settings as settings_module

_calls = {"count": 0}
_original = settings_module.load_config


def _counting_load_config(*args, **kwargs):
    _calls["count"] += 1
    return _original(*args, **kwargs)


settings_module.load_config = _counting_load_config


def pytest_sessionfinish(session, exitstatus):
    # Write the count next to the project so the outer test can read it.
    from pathlib import Path
    (Path(__file__).parent / "_load_config_count.txt").write_text(str(_calls["count"]))
'''


# =============================================================================
# ATDD: the fixture is discovered and is session-scoped
# =============================================================================


def test_settings_fixture_is_discovered_and_session_scoped(isolated_project: Path) -> None:
    """ATDD acceptance: two tests in one session use the fixture; it runs once.

    Writes a ``conftest.py`` that counts ``load_config`` calls, plus
    two test files. Each test file has one test that takes ``settings``
    as a parameter. Runs ``pytest`` against the temp project. Asserts
    the count is exactly ``1`` — session scope, shared across tests.

    If ``settings`` were function-scoped, the count would be ``2``.
    If pytest failed to discover the fixture, the tests would error
    with ``fixture 'settings' not found``, which the assertion below
    would show in the output.
    """
    (isolated_project / "conftest.py").write_text(_CONFTEST_COUNTER, encoding="utf-8")
    (isolated_project / "test_a.py").write_text(
        "def test_a(settings):\n    assert settings.api.base_url is not None\n",
        encoding="utf-8",
    )
    (isolated_project / "test_b.py").write_text(
        "def test_b(settings):\n    assert settings.api.base_url is not None\n",
        encoding="utf-8",
    )

    result = run_pytest_in(isolated_project)
    combined = result.stdout + result.stderr

    assert result.returncode == 0, (
        f"pytest exited with {result.returncode}.\n"
        f"--- stdout ---\n{result.stdout}\n--- stderr ---\n{result.stderr}"
    )
    assert "2 passed" in combined, f"expected `2 passed`, got:\n{combined}"
    count_file = isolated_project / "_load_config_count.txt"
    assert count_file.exists(), (
        "conftest.py did not write the load_config count; check the "
        "conftest source embedded in the test"
    )
    count = int(count_file.read_text().strip())
    assert count == 1, (
        f"load_config was called {count} times; a session-scoped fixture "
        f"must call it exactly once per session"
    )


# =============================================================================
# ATDD: the fixture reflects a real forgeqa.toml
# =============================================================================


def test_settings_fixture_uses_toml_in_cwd(isolated_project: Path) -> None:
    """The fixture reads ``forgeqa.toml`` from the temp project's CWD.

    Writes a ``forgeqa.toml`` with a distinctive ``api.base_url``,
    then a test that asserts ``settings.api.base_url`` matches it.
    This proves the fixture's ``load_config()`` call uses the default
    search (CWD), which is the "no arguments" behaviour the fixture
    commits to.

    If a future change made the fixture pass an explicit path or an
    ``environ=`` mapping, this test would fail because the temp
    project's ``forgeqa.toml`` would be ignored.
    """
    (isolated_project / "forgeqa.toml").write_text(
        '[api]\nbase_url = "http://example.test:9000"\n',
        encoding="utf-8",
    )
    (isolated_project / "test_uses_toml.py").write_text(
        "from pydantic import AnyHttpUrl\n"
        "\n"
        "def test_uses_toml(settings):\n"
        "    assert settings.api.base_url == AnyHttpUrl('http://example.test:9000')\n",
        encoding="utf-8",
    )

    result = run_pytest_in(isolated_project)
    combined = result.stdout + result.stderr

    assert result.returncode == 0, (
        f"pytest exited with {result.returncode}.\n"
        f"--- stdout ---\n{result.stdout}\n--- stderr ---\n{result.stderr}"
    )
    assert "1 passed" in combined, f"expected `1 passed`, got:\n{combined}"


# =============================================================================
# ATDD: an invalid config produces a clear fixture error
# =============================================================================


def test_settings_fixture_propagates_config_error(isolated_project: Path) -> None:
    """An invalid ``forgeqa.toml`` produces a fixture-setup error naming the file.

    Writes a ``forgeqa.toml`` with ``browser.timeout_ms = 0`` (below
    the WBS 1.2.5 ``ge=1`` lower bound), then a test that uses
    ``settings``. Pytest must report a fixture error — not a silent
    "used defaults" — and the error must name ``forgeqa.toml`` and
    ``timeout_ms``.

    A fixture that caught ``ForgeQAConfigError`` and returned a
    default config (a tempting "resilient" design) would produce a
    green run against a broken config, which is exactly the failure
    mode the WBS is trying to prevent.
    """
    (isolated_project / "forgeqa.toml").write_text(
        "[browser]\ntimeout_ms = 0\n",
        encoding="utf-8",
    )
    (isolated_project / "test_uses_broken_toml.py").write_text(
        "def test_uses_broken_toml(settings):\n    pass\n",
        encoding="utf-8",
    )

    result = run_pytest_in(isolated_project)
    combined = result.stdout + result.stderr

    # pytest exits non-zero on a fixture error.
    assert result.returncode != 0, (
        f"expected pytest to fail on an invalid forgeqa.toml, exited 0.\n"
        f"--- stdout ---\n{result.stdout}\n--- stderr ---\n{result.stderr}"
    )
    # The error names the file and the field.
    assert "forgeqa.toml" in combined, f"error did not name forgeqa.toml:\n{combined}"
    assert "timeout_ms" in combined, f"error did not name timeout_ms:\n{combined}"
    # The error is a fixture error (pytest's wording varies by version;
    # the concept "error" plus "settings" is the stable part).
    assert "settings" in combined, f"error did not name the settings fixture:\n{combined}"


# =============================================================================
# ATDD: no ForgeQA marker in the test file — the fixture works standalone
# =============================================================================


def test_settings_fixture_works_without_any_forgeqa_marker(isolated_project: Path) -> None:
    """The fixture is usable without ``@pytest.mark.ui`` / ``api`` / etc.

    A consumer who wants to test config-driven logic without exercising
    a browser or an API client should not need to opt into a marker.
    The fixture is available to any test that names it as a parameter.

    This test would fail if a future change made ``settings`` depend
    on a marker-scoped fixture (e.g. ``@pytest.fixture(scope="session")``
    combined with an implicit ``@pytest.mark.ui`` filtering in
    ``pytest_collection_modifyitems``). It's a guard against
    over-scoping.
    """
    (isolated_project / "test_plain.py").write_text(
        "def test_plain(settings):\n"
        "    # No @pytest.mark.* decorator; no browser/api dependency.\n"
        "    assert settings.general.environment == 'local'\n",
        encoding="utf-8",
    )

    result = run_pytest_in(isolated_project)
    combined = result.stdout + result.stderr

    assert result.returncode == 0, (
        f"pytest exited with {result.returncode}.\n"
        f"--- stdout ---\n{result.stdout}\n--- stderr ---\n{result.stderr}"
    )
    assert "1 passed" in combined, f"expected `1 passed`, got:\n{combined}"
