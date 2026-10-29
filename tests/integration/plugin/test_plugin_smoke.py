"""ATDD: the ForgeQA plugin is auto-discovered and registers its markers.

These tests invoke a real ``pytest`` subprocess in a temporary project
directory. They are the only way to prove the WBS 1.3.1 acceptance
criteria end-to-end:

* ``pytest --trace-config`` shows the ForgeQA plugin is loaded.
* No ``PytestUnknownMarkWarning`` appears when using ``@pytest.mark.ui``.

The unit tests (``tests/unit/test_plugin_registration.py``) prove the
module is importable and the hook registers markers **when called**.
These integration tests prove that **pytest actually calls the hook**
— i.e. the entry point is discovered and the plugin is loaded in a
real session.

**Common failure mode.** These tests fail with a generic "not
discovered" message when the *installed* ``forgeqa`` distribution's
metadata predates the ``pytest11`` entry point. Adding the entry
point to ``pyproject.toml`` does not refresh an editable install's
metadata; run ``pip install --force-reinstall --no-deps -e ".[dev]"``
to regenerate it. The tests assert ``returncode == 0`` before any
substring check so the failure message is the actual subprocess
output, not a mismatch, when this happens.

See also
--------
* ``tests/integration/plugin/conftest.py`` — ``isolated_project``
  fixture and ``run_pytest_in`` helper
* ADR-013 — the design decision
"""

from __future__ import annotations

from pathlib import Path

import pytest

from .conftest import run_pytest_in

pytestmark = [pytest.mark.integration]


# =============================================================================
# Sanity: the plugin module is importable from the outer process
# =============================================================================


def test_plugin_module_is_importable_in_outer_process() -> None:
    """The plugin module exists and imports in the *outer* process.

    This is the failure mode that most often causes the subprocess
    tests below to fail: ``pyproject.toml`` declares the entry point
    but ``src/forgeqa/pytest_plugin.py`` is missing, or the editable
    install did not pick it up. This test fails first with a specific
    message, so a reader of the CI output sees the real cause instead
    of "forgeqa.pytest_plugin not in --trace-config".

    Note this test checks the *outer* process's view. The subprocess
    tests check the *subprocess's* view — and the subprocess may be a
    different Python if a developer has an unusual ``PATH``.
    """
    import forgeqa.pytest_plugin

    assert hasattr(forgeqa.pytest_plugin, "pytest_configure"), (
        "forgeqa.pytest_plugin is importable but does not define "
        "pytest_configure. Check src/forgeqa/pytest_plugin.py."
    )


# =============================================================================
# ATDD: --trace-config shows the plugin
# =============================================================================


def test_pytest_trace_config_shows_forgeqa_plugin(isolated_project: Path) -> None:
    """ATDD acceptance: ``pytest --trace-config`` names ForgeQA's plugin module.

    ...

    **Exit code note.** The subprocess runs in an *empty* project
    directory (the ``isolated_project`` fixture creates nothing), so
    pytest exits with code **5** ("no tests collected") even when
    everything is healthy. That's the correct behaviour for pytest,
    not a plugin failure. The test asserts (a) the plugin appears in
    the output, and (b) the exit code is **0 or 5** — the two codes
    that mean "the plugin loaded; the run itself had no tests to
    collect or executed them successfully". Any *other* code (1, 2,
    3, 4) means a real failure (internal error, interrupted, usage
    error, etc.) and the test fails with the output.
    """
    result = run_pytest_in(isolated_project, "--trace-config")
    combined = result.stdout + result.stderr
    # Pytest exit codes:
    #   0 = all collected tests passed
    #   5 = no tests collected
    # Any other value means something went wrong during the run itself
    # (1 = tests failed, 2 = interrupted, 3 = internal error,
    #  4 = usage error). In an empty directory, we expect 5.
    assert result.returncode in (0, 5), (
        f"pytest --trace-config exited with {result.returncode}; "
        f"expected 0 (tests passed) or 5 (no tests collected). "
        f"Codes 1–4 mean the run itself failed — check the output.\n"
        f"--- stdout ---\n{result.stdout}\n--- stderr ---\n{result.stderr}"
    )
    assert "forgeqa.pytest_plugin" in combined, (
        "pytest --trace-config did not list forgeqa.pytest_plugin. "
        "The plugin is not registered in the installed distribution's "
        'metadata. Run `pip install --force-reinstall --no-deps -e ".[dev]"` '
        "to regenerate it.\n"
        f"--- stdout ---\n{result.stdout}\n--- stderr ---\n{result.stderr}"
    )


# =============================================================================
# ATDD: @pytest.mark.ui does not warn
# =============================================================================


def test_ui_marker_does_not_warn(isolated_project: Path) -> None:
    """ATDD acceptance: ``@pytest.mark.ui`` produces no PytestUnknownMarkWarning.

    Writes a test file that uses ``@pytest.mark.ui`` and asserts the
    marker is applied (not silently dropped). Runs ``pytest -W
    error::pytest.PytestUnknownMarkWarning``, which turns the warning
    into an error — the strictest possible check that the marker is
    registered. A project that does **not** have ``forgeqa``
    installed would fail this test with ``PytestUnknownMarkWarning``.

    The test also asserts the test itself ran (not just "no
    warning"), so a future refactor that collects zero tests does
    not pass by accident.

    **Failure mode.** If the subprocess exits non-zero with
    ``PytestUnknownMarkWarning`` in the output, the plugin is not
    loaded. If the subprocess exits non-zero without the warning, the
    marked test itself failed (unlikely for ``assert True`` — check
    for a typo in the marker name).
    """
    (isolated_project / "test_marked.py").write_text(
        "import pytest\n\n@pytest.mark.ui\ndef test_marked():\n    assert True\n",
        encoding="utf-8",
    )

    result = run_pytest_in(
        isolated_project,
        "-W",
        "error::pytest.PytestUnknownMarkWarning",
    )
    combined = result.stdout + result.stderr

    # If we hit a PytestUnknownMarkWarning, the plugin is not loaded.
    # Check that first, because the exit code and the "1 passed" check
    # would both fail for the same reason but the message would be
    # less specific.
    assert "PytestUnknownMarkWarning" not in combined, (
        "PytestUnknownMarkWarning appeared in output; the plugin is not "
        "registering @pytest.mark.ui. "
        'Run `pip install --force-reinstall --no-deps -e ".[dev]"` '
        "to regenerate the installed distribution's metadata, then "
        "verify with `python -m pytest --markers | grep pytest.mark.ui`.\n"
        f"--- stdout ---\n{result.stdout}\n--- stderr ---\n{result.stderr}"
    )
    assert result.returncode == 0, (
        f"pytest exited with {result.returncode}; the marked test did not "
        f"pass.\n"
        f"--- stdout ---\n{result.stdout}\n--- stderr ---\n{result.stderr}"
    )
    assert "1 passed" in combined, f"expected `1 passed` in output, got:\n{combined}"


@pytest.mark.parametrize("marker_name", ["ui", "api", "unit", "integration"])
def test_each_forgeqa_marker_does_not_warn(isolated_project: Path, marker_name: str) -> None:
    """Every ForgeQA-registered marker must be usable without warning.

    Parametrized over the four markers the plugin registers. A
    regression that removes one marker from ``FORGEQA_MARKERS`` but
    leaves the others is caught here — the single-marker test above
    would still pass, this parametrization would fail for the
    removed one.

    **Failure mode.** Same as ``test_ui_marker_does_not_warn``, one
    marker at a time. A failure for a single marker means that marker
    is missing from ``FORGEQA_MARKERS`` (or from the installed
    metadata, if all four fail).
    """
    (isolated_project / f"test_{marker_name}_marker.py").write_text(
        "import pytest\n"
        "\n"
        f"@pytest.mark.{marker_name}\n"
        f"def test_{marker_name}_marked():\n"
        "    assert True\n",
        encoding="utf-8",
    )

    result = run_pytest_in(
        isolated_project,
        "-W",
        "error::pytest.PytestUnknownMarkWarning",
        f"test_{marker_name}_marker.py",
    )
    combined = result.stdout + result.stderr
    assert result.returncode == 0, (
        f"marker {marker_name!r}: pytest exited {result.returncode}. "
        f"If PytestUnknownMarkWarning appears below, the marker is not "
        f"registered.\n{combined}"
    )
    assert "1 passed" in combined, f"marker {marker_name!r}: expected `1 passed`, got:\n{combined}"


# =============================================================================
# ATDD: pytest --markers lists ForgeQA's markers with descriptions
# =============================================================================


def test_pytest_markers_lists_forgeqa_markers(isolated_project: Path) -> None:
    """``pytest --markers`` lists each ForgeQA marker with a description.

    ``--markers`` is what a consumer runs to discover what markers
    are available. The output must name each marker (with its
    description) so a consumer sees ForgeQA's contribution. This is
    the human-facing side of the same contract the other tests
    assert programmatically.
    """
    result = run_pytest_in(isolated_project, "--markers")
    combined = result.stdout + result.stderr
    assert result.returncode == 0, (
        f"pytest --markers exited with {result.returncode}.\n"
        f"--- stdout ---\n{result.stdout}\n--- stderr ---\n{result.stderr}"
    )
    missing = [
        name
        for name in ("ui", "api", "unit", "integration")
        if f"pytest.mark.{name}" not in combined
    ]
    assert not missing, (
        f"markers {missing!r} not listed in pytest --markers; the "
        f"plugin is not loading or the manifest is missing them. "
        f'Run `pip install --force-reinstall --no-deps -e ".[dev]"` '
        f"to regenerate the installed metadata.\n{combined}"
    )


# =============================================================================
# Edge: a project that does not use ForgeQA markers is unaffected
# =============================================================================


def test_plugin_does_not_break_plain_pytest_session(isolated_project: Path) -> None:
    """A project that does not use ForgeQA's markers still works.

    The plugin is loaded in **every** pytest session in **every**
    project where ``forgeqa`` is installed. This test writes a plain
    test (no ForgeQA marker, no ForgeQA import) and asserts it runs
    normally — a broken plugin must not break unrelated test suites.
    This is the "do no harm" property of a pytest11 plugin.
    """
    (isolated_project / "test_plain.py").write_text(
        "def test_plain():\n    assert 1 + 1 == 2\n",
        encoding="utf-8",
    )

    result = run_pytest_in(isolated_project)
    combined = result.stdout + result.stderr
    assert result.returncode == 0, (
        f"plain pytest run failed; a pytest11 plugin is breaking an "
        f"unrelated test suite.\n"
        f"--- stdout ---\n{result.stdout}\n--- stderr ---\n{result.stderr}"
    )
    assert "1 passed" in combined, f"plain pytest run did not report `1 passed`:\n{combined}"
