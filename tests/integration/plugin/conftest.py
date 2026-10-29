"""Subprocess helpers for pytest plugin integration tests.

These tests are the **ATDD** half of WBS 1.3.1: they invoke a real
``pytest`` process against a temporary project directory and inspect
its output. That is the only way to prove the entry point is
discovered — a unit test that imports the plugin module proves the
module is importable, not that pytest discovers it.

The helper writes a minimal ``pyproject.toml`` (with no
``[tool.pytest.ini_options]``) and a test file with a
``@pytest.mark.ui`` decorator, then runs ``pytest`` with
``PYTEST_ADDOPTS=""`` (to neutralise the developer's shell) and
``-p no:cacheprovider`` (to keep the temp dir clean), and returns
the ``CompletedProcess``.

The helper does **not** assume ForgeQA is installed in editable mode
— it uses whatever ``pytest`` is on the subprocess ``PATH``. In CI,
that is the same ``pytest`` as the outer process. On a developer's
machine, it may be a different venv; the test's failure mode is
"the entry point is not discovered", which is exactly what the WBS
requires to be true.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest


@pytest.fixture()
def isolated_project(tmp_path: Path) -> Path:
    """Create a temporary project directory with no pytest config.

    Returns the project root. The caller writes ``pyproject.toml`` and
    test files into it and runs ``pytest`` with ``cwd=<project_root>``.

    The project deliberately contains **no** ``pyproject.toml``. A
    ``pyproject.toml`` with a ``[tool.pytest.ini_options]`` section
    would register markers via ini, masking the plugin's registration
    — the whole point of the test is to prove the *plugin* registers
    them.
    """
    return tmp_path


def run_pytest_in(
    project: Path,
    *args: str,
    env_overrides: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    """Run ``pytest`` in ``project`` with controlled environment.

    Parameters
    ----------
    project
        The directory to run in. Typically the ``isolated_project``
        fixture.
    *args
        Extra CLI arguments to pass to pytest after the standard
        ``-p no:cacheprovider -q`` prefix.
    env_overrides
        Extra environment variables. Merged over the inherited
        environment. Useful for ``PYTHONPATH`` injections in edge
        cases.

    Returns
    -------
    subprocess.CompletedProcess
        ``returncode``, ``stdout``, ``stderr`` — all captured.
    """
    env = os.environ.copy()
    # Neutralise any developer-set options that could inject markers
    # or change pytest's behaviour (e.g. an `addopts = -m unit` from
    # a user's pytest.ini).
    env["PYTEST_ADDOPTS"] = ""
    if env_overrides:
        env.update(env_overrides)

    cmd = [sys.executable, "-m", "pytest", "-p", "no:cacheprovider", "-q", *args]
    return subprocess.run(
        cmd,
        cwd=project,
        env=env,
        capture_output=True,
        text=True,
        # 60 s is generous — a normal pytest run in a temp dir is < 1 s.
        # A hang here would mean the plugin broke pytest's startup.
        timeout=60,
    )
