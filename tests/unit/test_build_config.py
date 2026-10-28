"""Unit tests for the build-target configuration in ``pyproject.toml``.

These tests are the fast, in-process complement to
``scripts/verify_build.sh`` (which is the slow, end-to-end build-and-inspect
verification). Together they cover WBS 1.1.4:

* ``[tool.hatch.build.targets.wheel]`` declares ``packages = ["src/forgeqa"]``.
* The wheel target explicitly excludes ``tests``, ``docs``, ``examples``,
  ``scripts`` — so a future change to ``packages`` cannot accidentally
  leak them into the wheel.
* ``[tool.hatch.build.targets.sdist]`` includes the source tree and
  excludes build artifacts.

The slow end-to-end scenarios (build the wheel and sdist, inspect the
archive contents) live in ``scripts/verify_build.sh``. This file covers the
*configuration* contract; the script covers the *built artifact* contract.
Both are required by the WBS acceptance criteria.

Run only these tests:

    pytest tests/unit/test_build_config.py -v
"""

from __future__ import annotations

import tomllib
from pathlib import Path

import pytest

pytestmark = pytest.mark.unit


#: The repository root, resolved relative to this file. Keeping it as a
#: module-level constant means a future move of the test file (e.g. under
#: ``tests/integration/``) fails loudly at import time rather than in a
#: distant assertion.
REPO_ROOT = Path(__file__).resolve().parents[2]
PYPROJECT = REPO_ROOT / "pyproject.toml"


@pytest.fixture(scope="module")
def pyproject() -> dict:
    """Parse ``pyproject.toml`` once per test module.

    Returns
    -------
    dict
        Parsed TOML as a nested dict.

    Notes
    -----
    Uses :mod:`tomllib` (stdlib since Python 3.11). ``requires-python``
    guarantees ``tomllib`` is present; no version guard is needed.
    """
    return tomllib.loads(PYPROJECT.read_text(encoding="utf-8"))


# =============================================================================
# Positive cases — the build config declares the expected shape
# =============================================================================


def test_wheel_target_declares_src_package(pyproject: dict) -> None:
    """Given the wheel target, when I read it, then ``packages = ["src/forgeqa"]``.

    Hatchling's wheel target must map ``src/forgeqa`` as the package. A change
    to a flat layout (``packages = ["forgeqa"]``) would move where
    ``forgeqa/__init__.py`` appears in the wheel, breaking the verifier's
    required-pattern check (and, more importantly, the installed package
    layout).

    Guards against WBS 1.1.4 acceptance criterion "The wheel contains
    forgeqa/__init__.py" at the config level — the built-artifact check is
    in ``scripts/verify_build.sh``.
    """
    wheel = pyproject["tool"]["hatch"]["build"]["targets"]["wheel"]
    assert wheel["packages"] == ["src/forgeqa"]


def test_sdist_includes_source_tree_and_docs(pyproject: dict) -> None:
    """Given the sdist target, when I read it, then it includes src/, tests/, docs/, and LICENSE.

    The sdist ships the full source tree so downstream can install from
    source and run the test suite offline. Removing any of these from the
    include list means a downstream consumer loses the ability to build and
    verify from the sdist — the well-known "sdist is not enough" problem.

    Guards against WBS 1.1.4 acceptance criterion "The wheel does not
    contain tests/ or docs/" being satisfied by *deleting* them from the
    sdist too — the wheel and sdist contracts are different on purpose.
    """
    sdist = pyproject["tool"]["hatch"]["build"]["targets"]["sdist"]
    includes = {path.lstrip("/") for path in sdist["include"]}
    for required in ("src", "tests", "docs", "README.md", "LICENSE", "pyproject.toml"):
        assert required in includes, f"sdist include list missing {required!r}: {sorted(includes)}"


# =============================================================================
# Negative cases — the wheel target explicitly excludes repo-only dirs
# =============================================================================


@pytest.mark.parametrize("forbidden", ["tests", "docs", "examples", "scripts"])
def test_wheel_excludes_repo_only_directories(pyproject: dict, forbidden: str) -> None:
    """Given the wheel exclude list, when I read it, then ``<forbidden>`` is excluded.

    Hatchling already excludes these via the ``packages`` narrowing (it only
    includes ``src/forgeqa``), but listing them makes the invariant
    auditable in the config and robust against a future change to
    ``packages`` (e.g. someone adds ``src/forgeqa_tools`` and forgets that
    ``tests`` was relying on the narrowing).

    Guards against WBS 1.1.4 acceptance criterion "The wheel does not
    contain tests/ or docs/" at the config level.
    """
    wheel = pyproject["tool"]["hatch"]["build"]["targets"]["wheel"]
    exclude = wheel.get("exclude", [])
    # Hatchling's exclude entries are simple globs, not regexes. A match
    # is exact-string for directory names (e.g. "tests"), or a glob
    # (e.g. "**/__pycache__"). Check the simple case first.
    matched = any(entry == forbidden for entry in exclude)
    assert matched, (
        f"wheel exclude list does not contain {forbidden!r}: {exclude}. "
        f"Add {forbidden!r} to [tool.hatch.build.targets.wheel].exclude in "
        f"pyproject.toml."
    )


@pytest.mark.parametrize(
    "forbidden",
    ["dist", "build", ".venv", "*.egg-info", "__pycache__"],
)
def test_sdist_excludes_build_artifacts(pyproject: dict, forbidden: str) -> None:
    """Given the sdist exclude list, when I read it, then build artifacts are excluded.

    Without these exclusions, a local build could ship ``dist/``,
    ``build/``, ``.venv/``, or ``*.egg-info/`` inside the sdist — bloating
    it and leaking build-state. Guards against WBS 1.1.4 acceptance
    criterion "The built artifact contains only the intended files".

    ``*.egg-info`` and ``__pycache__`` are matched by entry prefix because
    hatchling's exclude patterns are globs; we accept either the literal
    entry or a glob whose prefix matches.
    """
    sdist = pyproject["tool"]["hatch"]["build"]["targets"]["sdist"]
    exclude = sdist.get("exclude", [])
    # A directory is excluded if any exclude entry matches the directory
    # name exactly, or if any glob entry contains the directory name.
    matched = any(entry.lstrip("/") == forbidden or forbidden in entry for entry in exclude)
    assert matched, (
        f"sdist exclude list does not contain {forbidden!r}: {exclude}. "
        f"Add {forbidden!r} to [tool.hatch.build.targets.sdist].exclude in "
        f"pyproject.toml."
    )


# =============================================================================
# Edge cases — surprising-but-valid configurations
# =============================================================================


def test_wheel_exclude_does_not_include_package_itself(pyproject: dict) -> None:
    """Given the wheel exclude list, when I read it, then it does not exclude ``src/forgeqa``.

    The exclusion patterns are checked against the *wheel path* (e.g.
    ``forgeqa/__init__.py``), not the source path (``src/forgeqa/__init__.py``).
    A future contributor might add ``"src/forgeqa"`` to the exclude list
    thinking it excludes something else, which would silently break the
    wheel. This test catches that.
    """
    wheel = pyproject["tool"]["hatch"]["build"]["targets"]["wheel"]
    exclude = wheel.get("exclude", [])
    for entry in exclude:
        # The source path `src/forgeqa` should never appear in the exclude
        # list for the wheel — the wheel path is `forgeqa/`.
        assert "src/forgeqa" not in entry, (
            f"wheel exclude list contains {entry!r}, which would exclude the "
            f"package itself. The wheel path is 'forgeqa/', not 'src/forgeqa/'."
        )


# =============================================================================
# Corner cases — boundaries of the metadata contract
# =============================================================================


def test_license_file_is_declared_for_bundling(pyproject: dict) -> None:
    """Given ``[project].license``, when I read it, then it references ``LICENSE``.

    ``license = { file = "LICENSE" }`` is what causes hatchling to bundle the
    file into ``.dist-info/licenses/LICENSE``. A switch back to
    ``license = { text = "MIT" }`` would silently drop the file from the
    wheel, violating WBS 1.1.4 acceptance criterion "The wheel contains
    LICENSE". This test is the config-level guard; the built-artifact check
    is in ``scripts/verify_build.sh``.
    """
    license_field = pyproject["project"]["license"]
    assert isinstance(license_field, dict), (
        f"[project].license should be a table (e.g. {{file = 'LICENSE'}}), "
        f"got {type(license_field).__name__}: {license_field!r}"
    )
    assert license_field.get("file") == "LICENSE", (
        f"[project].license must reference the LICENSE file, got: {license_field!r}"
    )


# =============================================================================
# Non-functional cases — file health
# =============================================================================


def test_pyproject_is_parseable(pyproject: dict) -> None:
    """Given ``pyproject.toml`` on disk, when I parse it, then it is valid TOML.

    The fixture already parses it; this test makes the assertion explicit so
    a reviewer reading the file knows it is checked. Any TOML syntax error
    would have made every other test in this file fail with a confusing
    ``tomllib.TOMLDecodeError`` — this test turns that into a named failure.
    """
    assert isinstance(pyproject, dict)
    assert "project" in pyproject
    assert "tool" in pyproject
    assert "hatch" in pyproject["tool"]


def test_build_targets_section_exists(pyproject: dict) -> None:
    """Given ``pyproject.toml``, when I read the hatch build targets, then both wheel and sdist are declared.

    A missing target means hatchling falls back to its defaults, which
    may not match the intended package layout. Explicit is better than
    implicit for build contracts.
    """
    targets = pyproject["tool"]["hatch"]["build"]["targets"]
    assert "wheel" in targets, "missing [tool.hatch.build.targets.wheel]"
    assert "sdist" in targets, "missing [tool.hatch.build.targets.sdist]"
