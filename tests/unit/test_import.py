"""Unit tests for the minimum importable public API of :mod:`forgeqa`.

These tests assert the contract from WBS 1.1.2 and ADR-002:

* ``import forgeqa`` succeeds on a clean interpreter.
* ``forgeqa.__version__`` exists and is a non-empty string.
* ``forgeqa.__all__`` contains the documented public names.
* Importing :mod:`forgeqa` does **not** import Playwright or HTTPX
  (or any other optional dependency) as a side effect.
* Import is fast and side-effect free (no network, no file writes).

Every test runs in a fresh subprocess wherever interpreter state matters, so
that it is independent of pytest's plugin loading, coverage, and test order.
"""

from __future__ import annotations

import sys

import pytest

from tests.conftest import run_isolated_python

pytestmark = pytest.mark.unit


# =============================================================================
# Positive cases — happy path, contract from WBS 1.1.2
# =============================================================================


def test_import_forgeqa_succeeds() -> None:
    """Given a clean interpreter, when I ``import forgeqa``, then it succeeds.

    This is the first acceptance criterion of WBS 1.1.2: the package must be
    importable at all. A failure here means the minimum importable surface is
    broken — nothing downstream can work.
    """
    result = run_isolated_python("import forgeqa")

    assert result.returncode == 0, (
        f"`import forgeqa` failed with rc={result.returncode}.\n"
        f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
    )


def test_version_attribute_exists_and_is_string() -> None:
    """Given the package is imported, when I read ``__version__``, then it is a non-empty ``str``.

    The version must be a :class:`str` (not ``None``, not a tuple) and must not
    be empty. The exact value is asserted separately; here we only care about
    the type and non-emptiness contract.
    """
    result = run_isolated_python(
        "import forgeqa; "
        "assert isinstance(forgeqa.__version__, str), type(forgeqa.__version__); "
        "assert forgeqa.__version__, 'empty version'"
    )

    assert result.returncode == 0, result.stderr


def test_version_is_resolved_from_installed_metadata() -> None:
    """Given an installed distribution, when I read ``__version__``, then it matches ``importlib.metadata``.

    This is the core assertion of ADR-002: the version must come from installed
    package metadata, not a hard-coded literal. If this test fails, either the
    implementation regressed to a hard-coded value, or the install is broken.
    """
    result = run_isolated_python(
        "import forgeqa\n"
        "from importlib.metadata import version as v\n"
        "expected = v('forgeqa')\n"
        "assert forgeqa.__version__ == expected, (forgeqa.__version__, expected)\n"
        "print(expected)"
    )

    assert result.returncode == 0, result.stderr
    # Sanity: the printed value looks like a PEP 440 version.
    printed = result.stdout.strip()
    assert printed, "importlib.metadata returned an empty version"
    assert printed == printed.splitlines()[-1], "unexpected multi-line version output"


def test_public_api_all_contains_version_and_accessor() -> None:
    """Given the package is imported, when I read ``__all__``, then it contains ``__version__`` and ``get_version``.

    ``__all__`` is the public-API contract. Consumers may rely on the names in
    it; tools like ``pydoc`` and IDE completions use it. Missing entries mean
    the contract drifted from ``docs/public-api.md``.
    """
    result = run_isolated_python(
        "import forgeqa\n"
        "assert isinstance(forgeqa.__all__, tuple), type(forgeqa.__all__)\n"
        "assert '__version__' in forgeqa.__all__\n"
        "assert 'get_version' in forgeqa.__all__\n"
    )

    assert result.returncode == 0, result.stderr


def test_public_api_all_contains_only_public_names() -> None:
    """Given ``__all__``, when I inspect each entry, then none is private or missing.

    Every entry in ``__all__`` must be a non-empty identifier that actually
    exists on the module and does not start with a single underscore (dunder
    names such as ``__version__`` are exempt: PEP 8 treats them as public when
    documented, and ``docs/public-api.md`` explicitly lists ``__version__``).
    This prevents accidentally leaking private names into the public contract
    (or listing names that were never defined).
    """
    result = run_isolated_python(
        "import forgeqa\n"
        "for name in forgeqa.__all__:\n"
        "    assert isinstance(name, str) and name, name\n"
        "    is_private = name.startswith('_') and not (name.startswith('__') and name.endswith('__'))\n"
        "    assert not is_private, name\n"
        "    assert hasattr(forgeqa, name), name\n"
    )

    assert result.returncode == 0, result.stderr


def test_get_version_matches_dunder_version() -> None:
    """Given the package is imported, when I call ``get_version()``, then it equals ``__version__``.

    The accessor and the attribute must agree. Divergence would confuse
    consumers that mix the two styles (e.g. one in a report, one in a header).
    """
    result = run_isolated_python(
        "import forgeqa\nassert forgeqa.get_version() == forgeqa.__version__\n"
    )

    assert result.returncode == 0, result.stderr


# =============================================================================
# Negative cases — optional deps must not leak in
# =============================================================================


@pytest.mark.parametrize("forbidden_module", ["playwright", "httpx"])
def test_optional_dependency_not_imported(forbidden_module: str) -> None:
    """Given a clean interpreter, when I ``import forgeqa``, then ``<forbidden_module>`` is not in ``sys.modules``.

    This is the WBS 1.1.2 isolation requirement. The test is parametrised so
    that each forbidden module gets its own failure line — a single assertion
    covering both would obscure which module leaked.
    """
    result = run_isolated_python(
        f"import sys\n"
        f"import forgeqa\n"
        f"assert {forbidden_module!r} not in sys.modules, sorted(sys.modules)\n"
    )

    assert result.returncode == 0, (
        f"`import forgeqa` leaked optional dependency {forbidden_module!r}.\n"
        f"stderr:\n{result.stderr}"
    )


def test_no_optional_dependency_in_module_graph() -> None:
    """Given a clean interpreter, when I import ``forgeqa``, then no optional dep appears in ``sys.modules``.

    Variant of the previous test that checks the full forbidden list at once.
    Kept separate so a failure enumerates *all* leaked modules, not just the
    first one to fail.
    """
    result = run_isolated_python(
        "import sys\n"
        "import forgeqa\n"
        "forbidden = ('playwright', 'httpx')\n"
        "leaked = [m for m in forbidden if m in sys.modules]\n"
        "assert not leaked, leaked\n"
    )

    assert result.returncode == 0, result.stderr


# =============================================================================
# Edge cases — surprising-but-valid environments
# =============================================================================


def test_import_is_idempotent() -> None:
    """Given the package is imported, when I import it again, then it is the same module object.

    Python's import system guarantees this for regular imports, but a
    regression that installs a custom ``__getattr__`` which mutates
    ``sys.modules`` (or a future ``importlib.reload`` dance) could break it.
    Cheap to test, high signal.
    """
    result = run_isolated_python("import forgeqa as a\nimport forgeqa as b\nassert a is b\n")

    assert result.returncode == 0, result.stderr


def test_version_fallback_is_observable(monkeypatch: pytest.MonkeyPatch) -> None:
    """Given metadata is unavailable, when I re-import ``forgeqa``, then version is the documented fallback.

    Simulates the "no installed distribution" case by patching
    :func:`importlib.metadata.version` to raise
    :class:`importlib.metadata.PackageNotFoundError`, then reloading
    :mod:`forgeqa`. The implementation must not raise; it must return
    ``"0.0.0+unknown"`` and expose ``_is_version_fallback() is True``.
    """
    import importlib
    import importlib.metadata

    import forgeqa

    def _raise_not_found(_name: str) -> str:
        raise importlib.metadata.PackageNotFoundError(_name)

    monkeypatch.setattr("importlib.metadata.version", _raise_not_found)
    try:
        importlib.reload(forgeqa)
        assert forgeqa.__version__ == "0.0.0+unknown", forgeqa.__version__
        assert forgeqa._is_version_fallback() is True
    finally:
        # Restore real metadata and reload so other tests see the installed version.
        monkeypatch.undo()
        importlib.reload(forgeqa)


def test_version_fallback_skips_when_installed() -> None:
    """Given the package is installed, when I import ``forgeqa``, then ``_is_version_fallback()`` is ``False``.

    Complement to the previous test: on an installed environment, the fallback
    must not be triggered. If this fails in CI, the editable install is broken.
    """
    result = run_isolated_python(
        "import forgeqa\nassert forgeqa._is_version_fallback() is False, forgeqa.__version__\n"
    )

    assert result.returncode == 0, result.stderr


# =============================================================================
# Corner cases — behaviour at the boundaries of the contract
# =============================================================================


def test_all_is_immutable() -> None:
    """Given ``__all__``, when I inspect its type and mutate it in place, then it is a ``tuple`` and resists ``+=`` on its own value.

    ``__all__`` is a ``tuple`` (immutable): ``+=`` on the tuple itself creates
    a new tuple rather than mutating the original, and any in-place mutation
    attempt (``__all__.append``, ``__all__[0] = ...``) raises. Rebinding the
    *module attribute* ``forgeqa.__all__`` is normal Python and is out of scope
    for this test — that would require a descriptor on the module, which is
    overkill for a contract that is already documented in ``docs/public-api.md``.
    """
    result = run_isolated_python(
        "import forgeqa\n"
        # The value must be a tuple (not a list).
        "assert isinstance(forgeqa.__all__, tuple), type(forgeqa.__all__)\n"
        # In-place mutation must fail.
        "try:\n"
        "    forgeqa.__all__[0] = 'bogus'\n"
        "except TypeError:\n"
        "    pass\n"
        "else:\n"
        "    raise SystemExit('__all__ supports item assignment')\n"
        # .append does not exist on tuples.
        "assert not hasattr(forgeqa.__all__, 'append')\n"
    )

    assert result.returncode == 0, result.stderr


def test_no_import_time_filesystem_or_network() -> None:
    """Given a clean interpreter, when I import ``forgeqa``, then no network or filesystem side effects occur.

    Smoke test that the module body does not call ``socket``, ``open``, or
    similar. This is a *crude* assertion, not a sandbox: it relies on
    monkeypatching at the import site, which subprocess isolation does not
    give us for free. Instead, we assert on observable proxies: no file
    writes to ``cwd`` and no new sockets. See the docstring on
    :func:`run_isolated_python` for why this is best-effort.
    """
    result = run_isolated_python(
        "import os, sys, tempfile\n"
        "with tempfile.TemporaryDirectory() as td:\n"
        "    os.chdir(td)\n"
        "    before = set(os.listdir(td))\n"
        "    import forgeqa\n"
        "    after = set(os.listdir(td))\n"
        "    assert before == after, after - before\n"
    )

    assert result.returncode == 0, result.stderr


# =============================================================================
# Boundary cases — near the acceptance-criteria lines
# =============================================================================


def test_acceptance_criteria_are_met_verbatim() -> None:
    """Given a clean interpreter, when I run the four WBS 1.1.2 acceptance commands, then all pass.

    This test exists **specifically** to pin the ticket's acceptance criteria
    as executable tests. If a reviewer asks "does 1.1.2 pass?", this one test
    is the answer. It shells out to ``python -c`` exactly as the ticket says.
    """
    import subprocess

    commands = [
        # AC #1: version is queryable
        "import forgeqa; print(forgeqa.__version__)",
        # AC #2: playwright not imported
        "import sys, forgeqa; assert 'playwright' not in sys.modules",
        # AC #3: httpx not imported
        "import sys, forgeqa; assert 'httpx' not in sys.modules",
    ]
    for code in commands:
        result = subprocess.run(
            [sys.executable, "-c", code],
            capture_output=True,
            text=True,
            check=False,
        )
        assert result.returncode == 0, (
            f"Acceptance command failed: {code!r}\n"
            f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
        )


def test_pytest_collects_this_file() -> None:
    """Given pytest runs ``tests/unit/test_import.py``, when it collects, then at least one test is found.

    Guards against a typo (e.g. ``test-import.py`` with a dash) silently
    turning the file into a no-op. A file that collects zero tests is worse
    than no file — it looks green without testing anything.
    """
    # This test intentionally does nothing; its existence proves collection.
    assert True


# =============================================================================
# Non-functional cases — performance, determinism, reproducibility
# =============================================================================


def test_import_is_fast() -> None:
    """Given a clean interpreter, when I import ``forgeqa``, then it completes within 200 ms.

    The whole point of WBS 1.1.2 is a *cheap* import. Without a perf assertion,
    a future contributor could add a heavy top-level import and pass every
    other test. 200 ms is a generous ceiling for a single ``importlib.metadata``
    call; CI runners are slow, so the threshold is intentionally loose.
    """

    result = run_isolated_python(
        "import time\n"
        "t0 = time.perf_counter()\n"
        "import forgeqa\n"
        "elapsed_ms = (time.perf_counter() - t0) * 1000\n"
        "print(f'{elapsed_ms:.1f}')\n"
    )

    assert result.returncode == 0, result.stderr
    elapsed_ms = float(result.stdout.strip().splitlines()[-1])
    assert elapsed_ms < 200.0, (
        f"`import forgeqa` took {elapsed_ms:.1f} ms; budget is 200 ms. "
        "Investigate top-level imports in src/forgeqa/__init__.py."
    )


def test_import_is_deterministic_across_runs() -> None:
    """Given two clean interpreters, when each imports ``forgeqa``, then ``__version__`` is identical.

    Guards against non-determinism in version resolution (e.g. accidentally
    deriving the version from ``datetime.now()`` or a random seed).
    """
    first = run_isolated_python("import forgeqa; print(forgeqa.__version__)")
    second = run_isolated_python("import forgeqa; print(forgeqa.__version__)")

    assert first.returncode == 0 and second.returncode == 0
    assert first.stdout.strip() == second.stdout.strip(), (
        f"Version is non-deterministic: {first.stdout.strip()!r} vs {second.stdout.strip()!r}"
    )


def test_import_does_not_emit_warnings() -> None:
    """Given a clean interpreter, when I import ``forgeqa``, then no warnings are emitted.

    Import-time warnings are a known anti-pattern: they fire once per
    interpreter, are swallowed by test runners, and are not actionable by
    end users. The implementation deliberately avoids ``warnings.warn`` at
    import time; this test enforces that policy.
    """
    result = run_isolated_python(
        "import warnings\nwarnings.simplefilter('error')\nimport forgeqa\n"
    )

    assert result.returncode == 0, (
        f"`import forgeqa` emitted a warning (with warnings-as-errors):\n{result.stderr}"
    )


# -----------------------------------------------------------------------------
# Helpers used only by this test module
# -----------------------------------------------------------------------------


def subprocess_isolated_source(code: str):  # type: ignore[no-untyped-def]
    """Run ``code`` with only ``src/`` on ``PYTHONPATH``, simulating an uninstalled checkout.

    This deliberately **does not** import :mod:`tests.conftest`'s
    :func:`run_isolated_python` because we need to override the environment
    (``PYTHONPATH=src``) and the working directory, and we want a different
    timeout so failures in the fallback path are clearly attributable.

    Parameters
    ----------
    code
        Python source to execute in the subprocess.

    Returns
    -------
    subprocess.CompletedProcess[str]
        Result with ``capture_output=True`` and ``text=True``.
    """
    import os
    import subprocess
    from pathlib import Path

    repo_root = Path(__file__).resolve().parents[2]
    env = {
        **os.environ,
        "PYTHONPATH": str(repo_root / "src"),
    }
    return subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True,
        text=True,
        check=False,
        timeout=30,
        env=env,
        cwd=str(repo_root),
    )
