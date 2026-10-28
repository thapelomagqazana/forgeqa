"""Test support helpers for ForgeQA.

This module is intentionally **not** named ``conftest.py`` so that tests can
import its helpers directly (``from tests.support import run_isolated_python``)
without colliding with pytest's conftest auto-loading. Put pytest *fixtures*
in ``tests/conftest.py``; put plain helper functions here.
"""

from __future__ import annotations

import subprocess
import sys

#: Modules that must **not** be imported as a side effect of ``import forgeqa``.
#: Kept as a module-level constant so tests, docs, and CI share one source of
#: truth. Extending this list is a maintenance action: whenever a new optional
#: dependency is introduced, add its import name here.
FORBIDDEN_IMPORTS_ON_TOP_LEVEL: tuple[str, ...] = (
    "playwright",
    "httpx",
)


def run_isolated_python(code: str) -> subprocess.CompletedProcess[str]:
    """Run ``code`` in a fresh Python subprocess and return the result.

    Parameters
    ----------
    code
        Python source to execute. Passed via ``-c`` to avoid writing to disk.

    Returns
    -------
    subprocess.CompletedProcess[str]
        Result with ``capture_output=True`` and ``text=True``. Callers should
        assert on ``returncode`` and use ``stdout`` / ``stderr`` for evidence.

    Notes
    -----
    Using a subprocess is the only reliable way to test import-time behaviour
    (what ends up in ``sys.modules``) without interference from pytest's own
    plugin loading, coverage instrumentation, and module caching.
    """
    return subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True,
        text=True,
        check=False,
        timeout=30,
    )
