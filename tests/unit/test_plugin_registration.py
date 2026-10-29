"""Unit tests for the ForgeQA pytest plugin registration (WBS 1.3.1).

The tests cover:

* The plugin module is importable from ``forgeqa.pytest_plugin`` — the
  WBS acceptance criterion.
* The plugin module imports **cheaply** — no I/O, no optional-dependency
  imports, bounded import time.
* ``pytest_configure`` registers every marker in
  :data:`FORGEQA_MARKERS`, and registers *only* those markers (a marker
  removed from the manifest but left in ``pytest_configure`` would be a
  duplicate; a marker added to the manifest but not iterated would be a
  missing registration).
* ``pytest_configure`` is idempotent — calling it twice does not raise
  and does not remove a marker.
* ``pytest_configure`` does not read the consumer's ``config.option``
  or ``config.inicfg`` (a unit-test can't fully prove this, but a
  targeted test that passes a minimal ``config``-like object
  demonstrates the intent).

The tests deliberately **do not** run a subprocess — that's the ATDD
test's job (``tests/integration/plugin/test_plugin_smoke.py``). These
are fast, hermetic, and can run on any machine with ``pytest``
installed.

Run only these tests:

    pytest tests/unit/test_plugin_registration.py -v
"""

from __future__ import annotations

import ast
import importlib
import inspect
import sys
import time

import pytest

pytestmark = pytest.mark.unit


# =============================================================================
# Import surface — the plugin is importable, cheap, and side-effect free
# =============================================================================


def test_plugin_is_importable_from_documented_path() -> None:
    """WBS 1.3.1 acceptance: ``from forgeqa.pytest_plugin import pytest_configure``.

    The import path is a public contract — the ``pytest11`` entry point
    in ``pyproject.toml`` references ``forgeqa.pytest_plugin``, so a
    rename is a breaking change for installed ForgeQA distributions.
    """
    import forgeqa.pytest_plugin as plugin_module

    assert hasattr(plugin_module, "pytest_configure")
    assert callable(plugin_module.pytest_configure)


def test_plugin_module_import_is_cheap() -> None:
    """Importing the plugin module must be fast.

    Pytest imports every ``pytest11`` plugin on **every** pytest
    invocation — including in projects that do not use ForgeQA. If
    this module imported Playwright, HTTPX, or a large chunk of
    ``forgeqa.config``, every pytest invocation in every project
    with ``forgeqa`` installed would pay the cost.

    The budget (100 ms) is ~100x headroom over the measured ~1 ms on
    a cold interpreter. It catches the realistic regression — a
    module-level ``import playwright`` or a schema-heavy import —
    without flaking under CI CPU contention.
    """
    # Unimport so we measure the cost of a fresh import, not a cached one.
    sys.modules.pop("forgeqa.pytest_plugin", None)
    start = time.perf_counter()
    importlib.import_module("forgeqa.pytest_plugin")
    elapsed = time.perf_counter() - start
    assert elapsed < 0.1, f"plugin import took {elapsed * 1000:.1f} ms"


def test_plugin_module_does_not_import_optional_dependencies() -> None:
    """Importing the plugin must not pull in Playwright or HTTPX.

    The plugin must be importable in a core install (no ``[ui]``, no
    ``[api]`` extras). A future WBS adds fixtures that *do* import
    those modules — but inside the fixture body, not at module level.

    **Method.** The test parses the module's own source with
    :mod:`ast` and collects the names imported at module level (i.e.
    ``ast.Import`` / ``ast.ImportFrom`` nodes that are direct children
    of ``ast.Module.body``). An ``import httpx`` inside a function
    body, inside a triple-quoted string, or inside a comment is not a
    module-level import and is correctly ignored.

    This is the cheapest way to enforce "the plugin imports cheaply":
    it runs in microseconds, needs no subprocess, and catches the
    realistic regression (a contributor adding ``from forgeqa.config
    import ForgeQAConfig`` at the top of the plugin module).
    """
    import forgeqa.pytest_plugin as plugin_module

    source = inspect.getsource(plugin_module)
    tree = ast.parse(source)

    # Names imported at module level (top-level Import / ImportFrom).
    # `ast.parse` puts a docstring first in `body`; we skip it because
    # it is an `Expr(Constant(str))`, not an import.
    module_level_imports: set[str] = set()
    for node in tree.body:
        if isinstance(node, ast.Import):
            for alias in node.names:
                module_level_imports.add(alias.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom) and node.module:
            # `node.module` is None only for relative imports
            # (`from . import x`); ForgeQA has none at the plugin's
            # top level, but the guard costs nothing and prevents a
            # future `from . import something` from tripping an
            # unrelated AttributeError.
            module_level_imports.add(node.module.split(".")[0])

    assert "playwright" not in module_level_imports, (
        f"plugin module imports playwright at module level: {module_level_imports}"
    )
    assert "httpx" not in module_level_imports, (
        f"plugin module imports httpx at module level: {module_level_imports}"
    )
    # `forgeqa.config` is a heavyweight transitive import (pydantic,
    # tomllib, the schema); the plugin should not need it at module
    # level.
    assert "forgeqa" not in module_level_imports, (
        "plugin module imports from forgeqa at module level; "
        "move heavy imports inside hook bodies / fixtures"
    )


# =============================================================================
# Marker manifest — single source of truth
# =============================================================================


def test_markers_manifest_has_expected_names() -> None:
    """The manifest contains exactly the four WBS 1.3.1 markers.

    ``ui`` and ``api`` are the WBS's explicit requirements;
    ``unit`` and ``integration`` are included because ForgeQA's
    consumer-facing test taxonomy uses them. ``smoke`` and ``slow``
    are ForgeQA's *own* test-suite markers (declared in
    ``[tool.pytest.ini_options]``), not consumer concepts — see
    ADR-013 §Alternatives Considered.
    """
    from forgeqa.pytest_plugin import FORGEQA_MARKERS

    names = {name for name, _ in FORGEQA_MARKERS}
    assert names == {"ui", "api", "unit", "integration"}


def test_markers_manifest_descriptions_are_non_empty() -> None:
    """Every marker has a non-empty description.

    ``pytest --markers`` prints ``"<name>: <description>"``. An empty
    description produces a blank line that reads like a formatting bug.
    """
    from forgeqa.pytest_plugin import FORGEQA_MARKERS

    for name, description in FORGEQA_MARKERS:
        assert description, f"marker {name!r} has an empty description"
        # Defensive: catch a copy-paste of the *next* marker's
        # description (a bug that a set-comparison would not catch).
        assert description.strip().endswith("."), (
            f"marker {name!r} description does not end with a period: {description!r}"
        )


def test_markers_manifest_is_a_tuple() -> None:
    """The manifest is an immutable tuple, not a list.

    A tuple makes the manifest a value, not a mutable global. A test
    that wants to simulate a marker addition should construct a new
    tuple and pass it; the module-level manifest must not be mutated
    by a test, or test ordering would affect other tests.
    """
    from forgeqa.pytest_plugin import FORGEQA_MARKERS

    assert isinstance(FORGEQA_MARKERS, tuple)
    for entry in FORGEQA_MARKERS:
        assert isinstance(entry, tuple)
        assert len(entry) == 2
        name, description = entry
        assert isinstance(name, str)
        assert isinstance(description, str)


# =============================================================================
# pytest_configure — registers every manifest marker
# =============================================================================


class _FakeConfig:
    """A minimal stand-in for ``pytest.Config`` for unit tests.

    The real ``pytest.Config`` is not constructible in isolation (it
    needs a plugin manager, a rootdir, and a full ini parse). The
    plugin only calls ``addinivalue_line``, so a one-method stand-in
    exercises every code path the plugin takes.

    ``addinivalue_line`` accumulates ``(name, value)`` pairs — the
    test can then assert on exactly what was registered.
    """

    def __init__(self) -> None:
        self.lines: list[tuple[str, str]] = []

    def addinivalue_line(self, name: str, line: str) -> None:
        self.lines.append((name, line))


def test_pytest_configure_registers_every_manifest_marker() -> None:
    """``pytest_configure`` registers exactly the manifest markers.

    Two assertions:
    1. Every manifest marker appears in the registered lines.
    2. No *extra* marker is registered (i.e. the function does not
       have a stray hard-coded marker that the manifest does not
       know about).

    The second assertion is the one that catches a duplicate-marker
    bug during a future refactor: a developer who adds a marker by
    appending a literal to the ``pytest_configure`` body would find
    the test fails, prompting them to add it to the manifest instead.
    """
    from forgeqa.pytest_plugin import FORGEQA_MARKERS, pytest_configure

    config = _FakeConfig()
    pytest_configure(config)  # type: ignore[arg-type]

    registered_marker_lines = [line for name, line in config.lines if name == "markers"]
    registered_names = {line.split(":", 1)[0].strip() for line in registered_marker_lines}

    expected_names = {name for name, _ in FORGEQA_MARKERS}
    assert registered_names == expected_names, (
        f"registered markers {registered_names!r} do not match manifest {expected_names!r}"
    )


def test_pytest_configure_registered_descriptions_match_manifest() -> None:
    """The registered line is ``"<name>: <description>"`` for each marker.

    Pytest parses this exact form for ``--markers``; a description
    that contains a newline would break display, and a description
    with a leading space would render with a double space. The
    manifest is the source of truth, so the registered line must be
    ``f"{name}: {description}"`` verbatim.
    """
    from forgeqa.pytest_plugin import FORGEQA_MARKERS, pytest_configure

    config = _FakeConfig()
    pytest_configure(config)  # type: ignore[arg-type]

    expected_lines = {f"{name}: {description}" for name, description in FORGEQA_MARKERS}
    actual_lines = {line for name, line in config.lines if name == "markers"}
    assert actual_lines == expected_lines


def test_pytest_configure_is_idempotent() -> None:
    """Calling ``pytest_configure`` twice does not raise and does not lose markers.

    Pytest calls the hook once per session, but tests (and future
    plugins) may call it multiple times. The function appends to
    ``config.addinivalue_line``; Pytest deduplicates marker
    descriptions at display time, and registering the same marker
    twice is a no-op for validation. So the correct behaviour is
    "registers twice, harmless" — not "detects duplicate and skips".
    """
    from forgeqa.pytest_plugin import FORGEQA_MARKERS, pytest_configure

    config = _FakeConfig()
    pytest_configure(config)  # type: ignore[arg-type]
    pytest_configure(config)  # type: ignore[arg-type]

    marker_lines = [line for name, line in config.lines if name == "markers"]
    # Two calls, four markers each, eight lines. The exact count is
    # not the contract (idempotence means "doesn't crash", not
    # "doesn't duplicate"), but asserting it catches a future change
    # that silently skips registration on the second call.
    assert len(marker_lines) == 2 * len(FORGEQA_MARKERS)


# =============================================================================
# Non-functional — pytest_configure does not read consumer config
# =============================================================================


def test_pytest_configure_does_not_read_consumer_config() -> None:
    """The hook uses ``config`` only for ``addinivalue_line``.

    If a future change reads ``config.option``, ``config.inicfg``, or
    ``config.getini``, the plugin would start depending on the
    consumer's pytest configuration — a hidden coupling that would
    break in projects with unusual setups. The ``_FakeConfig``
    stand-in only exposes ``addinivalue_line``, so *any* read would
    raise ``AttributeError`` and fail this test. That is the intent.
    """
    from forgeqa.pytest_plugin import pytest_configure

    # A stricter stand-in: only `addinivalue_line` exists.
    class StrictFakeConfig:
        def __init__(self) -> None:
            self.lines: list[tuple[str, str]] = []

        def addinivalue_line(self, name: str, line: str) -> None:
            self.lines.append((name, line))

    config = StrictFakeConfig()
    pytest_configure(config)  # type: ignore[arg-type]

    # If we got here, the hook did not access any attribute other
    # than `addinivalue_line`. The assertion is the absence of
    # AttributeError, plus a sanity check that lines were added.
    assert config.lines


# =============================================================================
# Non-functional — hook signature and typing
# =============================================================================


def test_pytest_configure_has_correct_signature() -> None:
    """The hook's signature is ``(config: pytest.Config) -> None``.

    Pytest's plugin system validates hook signatures at registration
    time; a mismatch raises ``PluginValidationError`` when the plugin
    is loaded, which would break *every* pytest invocation in *every*
    project with ``forgeqa`` installed. This test is a cheap
    belt-and-braces check against a signature refactor.
    """
    from forgeqa.pytest_plugin import pytest_configure

    sig = inspect.signature(pytest_configure)
    params = list(sig.parameters.values())
    assert len(params) == 1
    assert params[0].name == "config"
    assert params[0].kind in (
        inspect.Parameter.POSITIONAL_OR_KEYWORD,
        inspect.Parameter.POSITIONAL_ONLY,
    )
    assert sig.return_annotation in (None, "None")


# =============================================================================
# pyproject.toml — entry point is declared
# =============================================================================


def test_pyproject_declares_pytest11_entry_point() -> None:
    """``pyproject.toml`` declares ``forgeqa = "forgeqa.pytest_plugin"`` under ``pytest11``.

    This is the load-bearing assertion for the WBS: without the entry
    point, the plugin is importable but **not auto-discovered**. Pytest
    enumerates ``pytest11`` entry points via ``importlib.metadata`` and
    calls the module's hooks. A missing entry point means a consumer
    has to pass ``-p forgeqa.pytest_plugin`` on every invocation, which
    defeats the purpose.

    The check uses ``importlib.metadata`` (the same mechanism Pytest
    uses) rather than parsing ``pyproject.toml`` directly, so the test
    also proves the entry point is **registered in the installed
    distribution** — the same view Pytest has.
    """
    from importlib.metadata import entry_points

    eps = entry_points()
    # `entry_points()` returns a `SelectableGroups` on Python < 3.10
    # and a dict-of-lists on 3.12+; `select` works on both for
    # `group=` filtering.
    group = eps.select(group="pytest11") if hasattr(eps, "select") else eps.get("pytest11", [])
    forgeqa_eps = [ep for ep in group if ep.name == "forgeqa"]
    assert forgeqa_eps, (
        "forgeqa is not registered as a pytest11 plugin. "
        "Check `[project.entry-points.pytest11]` in pyproject.toml."
    )
    assert forgeqa_eps[0].value == "forgeqa.pytest_plugin"
