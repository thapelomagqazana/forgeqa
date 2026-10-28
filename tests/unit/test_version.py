"""Unit tests pinning the relationship between ``forgeqa.__version__``,
the version in ``pyproject.toml``, and the installed distribution's
``METADATA``.

These tests cover WBS 1.1.7:

* ``forgeqa.__version__`` matches the version in ``pyproject.toml``.
* The installed distribution's ``METADATA`` version matches
  ``pyproject.toml`` (the wheel and the source agree).
* The version string is valid SemVer 2.0.0 (with a documented relaxation
  to PEP 440 pre-release suffixes; see below).

Together they prevent the class of bug where the source attribute,
``pyproject.toml``, and the published wheel disagree — a silent failure
mode that costs a release to diagnose if undetected.

The tests run in <100 ms and are part of ``make test``. ``make
verify-version`` runs only these tests for quick local iteration.

Run only these tests:

    pytest tests/unit/test_version.py -v
    # or
    make verify-version
"""

from __future__ import annotations

import re
import sys
import tomllib
from pathlib import Path

import pytest

pytestmark = pytest.mark.unit


#: The repository root, resolved relative to this file.
REPO_ROOT = Path(__file__).resolve().parents[2]
PYPROJECT = REPO_ROOT / "pyproject.toml"
SRC_DIR = REPO_ROOT / "src"


#: SemVer 2.0.0 regex (https://semver.org/#is-there-a-suggested-regular-expression-regex-to-check-a-semver-string),
#: with one relaxation documented at :func:`test_version_is_valid_semver`.
#:
#: SemVer proper: ``MAJOR.MINOR.PATCH[-PRERELEASE][+BUILD]``.
#:
#: Relaxation for ForgeQA: the fallback string ``"0.0.0+unknown"`` must
#: pass this regex (it is not a release, but it must not be rejected by
#: tooling that parses ``__version__``). The SemVer regex already accepts
#: it because ``unknown`` is a valid build-metadata identifier, so no
#: relaxation is actually needed for that case.
#:
#: The real reason for the two ``FALLBACK`` cases below is PEP 440
#: local-version suffixes like ``+unknown`` (used by ``_FALLBACK_VERSION``)
#: — those are valid *local versions* under PEP 440 and valid *build
#: metadata* under SemVer, so the SemVer regex accepts them as-is. If a
#: future release uses a PEP 440 pre-release like ``0.2.0rc1`` (no dot
#: before ``rc``), that would not match SemVer and would be rejected
#: here. The stability promise in ``docs/public-api.md`` is PEP 440,
#: not SemVer, so if the project ever ships a PEP 440 pre-release, the
#: test must be updated to accept PEP 440 pre-release forms as well.
_SEMVER_RE = re.compile(
    r"^(?P<major>0|[1-9]\d*)\."
    r"(?P<minor>0|[1-9]\d*)\."
    r"(?P<patch>0|[1-9]\d*)"
    r"(?:-(?P<prerelease>(?:0|[1-9]\d*|\d*[a-zA-Z-][0-9a-zA-Z-]*)"
    r"(?:\.(?:0|[1-9]\d*|\d*[a-zA-Z-][0-9a-zA-Z-]*))*))?"
    r"(?:\+(?P<buildmetadata>[0-9a-zA-Z-]+"
    r"(?:\.[0-9a-zA-Z-]+)*))?$"
)


# =============================================================================
# Helpers
# =============================================================================


def _read_pyproject_version() -> str:
    """Return the ``[project].version`` string from ``pyproject.toml``.

    Returns
    -------
    str
        The raw version string as written in the file.

    Notes
    -----
    Uses :mod:`tomllib` (stdlib since Python 3.11). ``requires-python``
    guarantees ``tomllib`` is present; no version guard is needed.
    """
    pyproject = tomllib.loads(PYPROJECT.read_text(encoding="utf-8"))
    return pyproject["project"]["version"]


def _import_forgeqa() -> object:
    """Import ``forgeqa`` from the source tree, bypassing any installed copy.

    Returns
    -------
    object
        The imported :mod:`forgeqa` module.

    Notes
    -----
    Ensures the test runs against the checked-out source, not an installed
    wheel, so a developer's ``pip install -e .`` cannot mask a mismatch
    between ``pyproject.toml`` and ``src/forgeqa/__init__.py``. The cached
    module is removed from :data:`sys.modules` after import so later tests
    in the session see a clean state. Same pattern as
    ``test_install_contract.py`` and ``test_public_api.py``.
    """
    sys.path.insert(0, str(SRC_DIR))
    try:
        import forgeqa  # noqa: PLC0415 - intentional late import

        return forgeqa
    finally:
        sys.path.remove(str(SRC_DIR))
        for name in list(sys.modules):
            if name == "forgeqa" or name.startswith("forgeqa."):
                del sys.modules[name]


def _read_installed_metadata_version() -> str:
    """Return the ``Version`` field from the installed distribution's ``METADATA``.

    Reads the installed ``forgeqa`` distribution's metadata via
    :func:`importlib.metadata.metadata`. This is the same value ``pip show
    forgeqa`` reads.

    Returns
    -------
    str
        The ``Version:`` field from ``METADATA``.

    Raises
    ------
    importlib.metadata.PackageNotFoundError
        If ``forgeqa`` is not installed in the current interpreter.

    Notes
    -----
    This function reads the *installed* distribution, not the source
    tree. In an editable install (``pip install -e .``), it reflects the
    value ``pip`` recorded at install time — which is why the test
    additionally checks that the installed version *matches*
    ``pyproject.toml``. In a wheel install, it reflects the wheel's
    ``METADATA``.
    """
    from importlib.metadata import metadata  # noqa: PLC0415

    return metadata("forgeqa")["Version"]


# =============================================================================
# Positive cases — the version string is present and consistent
# =============================================================================


def test_forgeqa_version_matches_pyproject() -> None:
    """Given ``src/forgeqa/__init__.py``, when imported, then ``__version__`` equals ``pyproject.toml``'s version.

    This is the core assertion of WBS 1.1.7. It catches the class of bug
    where ``pyproject.toml`` is bumped for a release but
    ``src/forgeqa/__init__.py``'s ``__version__`` is not (or vice
    versa) — a silent failure that would ship a wheel whose
    ``METADATA`` and runtime attribute disagree.

    Because ``__version__`` is resolved via :func:`importlib.metadata.version`,
    this test is effectively "does the installed distribution match
    ``pyproject.toml``". It runs in the developer's environment, so it
    catches the mismatch early (before the wheel is built), and again in
    CI after the wheel is installed.
    """
    mod = _import_forgeqa()
    pyproject_version = _read_pyproject_version()
    assert mod.__version__ == pyproject_version, (
        f"Version mismatch between pyproject.toml and forgeqa.__version__:\n"
        f"  pyproject.toml:  {pyproject_version!r}\n"
        f"  forgeqa.__version__: {mod.__version__!r}\n"
        f"Both must move together. If you bumped pyproject.toml for a "
        f"release, ensure `pip install -e .` (or the CI install step) "
        f"was re-run so importlib.metadata sees the new value."
    )


def test_installed_metadata_matches_pyproject() -> None:
    """Given the installed distribution, when read, then its ``METADATA`` version equals ``pyproject.toml``'s version.

    ``forgeqa.__version__`` is resolved from the installed distribution's
    ``METADATA`` (see ADR-002). In an editable install, that metadata is
    the one ``pip`` wrote at install time; in a wheel install, it is the
    wheel's ``METADATA``. Either way, it must match ``pyproject.toml``.

    A mismatch here (with ``test_forgeqa_version_matches_pyproject``
    passing) would indicate a *stale editable install* — the developer
    bumped ``pyproject.toml`` but did not re-run ``pip install -e .``.
    The test fails with a message explaining the fix, so the failure is
    actionable.
    """
    try:
        installed_version = _read_installed_metadata_version()
    except Exception as exc:  # noqa: BLE001 - explicit: any failure here is "not installed"
        pytest.skip(
            f"forgeqa is not installed in this interpreter ({exc!r}); "
            f"skipping installed-metadata check."
        )
    pyproject_version = _read_pyproject_version()
    assert installed_version == pyproject_version, (
        f"Installed METADATA version does not match pyproject.toml:\n"
        f"  pyproject.toml:  {pyproject_version!r}\n"
        f"  installed METADATA: {installed_version!r}\n"
        f"This usually means a stale editable install. Re-run "
        f"`pip install -e .` (or `uv sync`) to refresh the metadata."
    )


# =============================================================================
# Negative cases — the version string is not empty and not the fallback
# =============================================================================


def test_version_is_not_empty() -> None:
    """Given ``forgeqa.__version__``, when inspected, then it is non-empty.

    A basic sanity check: the string must be present and non-empty. The
    fallback ``"0.0.0+unknown"`` also satisfies this, which is why the
    "not the fallback" check is separate
    (:func:`test_version_is_not_fallback`).
    """
    mod = _import_forgeqa()
    assert isinstance(mod.__version__, str)
    assert mod.__version__


def test_version_is_not_fallback() -> None:
    """Given ``forgeqa.__version__``, when read, then it is not the ``"0.0.0+unknown"`` fallback.

    The fallback exists so that ``import forgeqa`` never crashes from an
    uninstalled source checkout. But in the test suite, we *do* expect an
    installed distribution — either a wheel or an editable install. If
    the fallback is returned, the test environment is misconfigured
    (no ``.dist-info`` on ``sys.path``), and every subsequent assertion
    about version consistency would compare against the fallback, not the
    real version. Failing explicitly here makes the misconfiguration
    visible instead of masking a real mismatch.
    """
    mod = _import_forgeqa()
    # Importing the private helper is acceptable in the package's own test
    # suite; it is explicitly documented as "not for public use" in
    # docs/public-api.md §"Detecting the fallback (advanced)".
    assert not mod._is_version_fallback(), (
        f"forgeqa.__version__ is the fallback {mod.__version__!r}, not a "
        f"real version. Ensure forgeqa is installed "
        f"(`pip install -e .` or `pip install dist/*.whl`) before running "
        f"this test suite."
    )


# =============================================================================
# SemVer format — the version parses as SemVer 2.0.0
# =============================================================================


def test_version_is_valid_semver() -> None:
    """Given ``forgeqa.__version__``, when parsed, then it is valid SemVer 2.0.0.

    SemVer 2.0.0 (https://semver.org/) is the version format the project
    documents in ``docs/public-api.md`` §"Stability promise". The regex
    below is the SemVer project's official suggested regex.

    **Scope of this check.** It validates the *format* the project
    promises, not PEP 440 (which is the format PyPI / ``pip`` use).
    ForgeQA's published versions are valid SemVer *and* valid PEP 440
    (e.g. ``0.1.0``). Pre-release forms like ``0.2.0rc1`` (no dot
    before ``rc``) are valid PEP 440 but not valid SemVer; if a future
    release uses one, the stability promise in ``docs/public-api.md``
    should be updated to PEP 440 pre-release forms and this test
    broadened accordingly. The current policy is SemVer-only for the
    published line, which is why the regex is strict.

    The fallback ``"0.0.0+unknown"`` is valid SemVer (build metadata
    ``unknown``); this is intentional, so that tools which parse
    ``__version__`` do not crash on the fallback.
    """
    mod = _import_forgeqa()
    match = _SEMVER_RE.match(mod.__version__)
    assert match is not None, (
        f"forgeqa.__version__ is not valid SemVer 2.0.0: "
        f"{mod.__version__!r}.\n"
        f"Expected MAJOR.MINOR.PATCH[-prerelease][+build], e.g. '0.1.0'.\n"
        f"See https://semver.org/#is-there-a-suggested-regular-expression-"
        f"regex-to-check-a-semver-string."
    )


def test_version_components_are_nonnegative_integers() -> None:
    """Given a valid SemVer version, when parsed, then ``MAJOR``, ``MINOR``, ``PATCH`` are non-negative integers.

    The regex already enforces this, but parsing the components explicitly
    gives a clearer error message if the regex is ever relaxed and a
    non-integer slips through.
    """
    mod = _import_forgeqa()
    match = _SEMVER_RE.match(mod.__version__)
    if match is None:
        pytest.fail(f"Version is not valid SemVer: {mod.__version__!r}")
    for component in ("major", "minor", "patch"):
        value = match.group(component)
        assert value is not None, f"Missing {component} in {mod.__version__!r}"
        assert int(value) >= 0, f"{component} is negative in {mod.__version__!r}: {value}"


def test_version_major_matches_project_stability() -> None:
    """Given ``forgeqa.__version__``, when parsed, then ``MAJOR`` is ``0`` while the project is pre-alpha.

    The project is pre-alpha (``Development Status :: 3 - Alpha``); a
    version with ``MAJOR >= 1`` would contradict the stability promise
    in ``docs/public-api.md`` §"Version support policy" and the project
    status banner in the README. This test fails if someone bumps the
    version to ``1.0.0`` without changing the status metadata.

    When the project graduates to 1.0, this test is updated (or removed)
    in the same PR that changes the PyPI classifier and the README
    banner. The ADR's reconsideration trigger covers this case.
    """
    mod = _import_forgeqa()
    match = _SEMVER_RE.match(mod.__version__)
    if match is None:
        pytest.fail(f"Version is not valid SemVer: {mod.__version__!r}")
    major = int(match.group("major"))
    assert major == 0, (
        f"forgeqa.__version__ is {mod.__version__!r} but the project is "
        f"still pre-alpha (Development Status :: 3 - Alpha). If this is a "
        f"1.0 graduation, update the PyPI classifier, the README project-"
        f'status banner, docs/public-api.md §"Version support policy", '
        f"and this test in the same PR."
    )


# =============================================================================
# Non-functional cases — the version is stable across imports
# =============================================================================


def test_version_is_stable_across_imports() -> None:
    """Given two imports of ``forgeqa``, when compared, then ``__version__`` is identical.

    The version must be deterministic. A future change that computes it
    dynamically (e.g. from a ``datetime`` or a random seed) would be
    caught here before it reaches a release.
    """
    first = _import_forgeqa()
    second = _import_forgeqa()
    assert first.__version__ == second.__version__, (
        f"forgeqa.__version__ is not stable across imports: "
        f"{first.__version__!r} vs {second.__version__!r}"
    )
