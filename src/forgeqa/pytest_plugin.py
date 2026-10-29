"""Pytest plugin for ForgeQA.

This module is the entry point Pytest loads when it discovers the
``forgeqa`` plugin via the ``pytest11`` entry point group. It is the
**single place** where ForgeQA registers pytest-level concerns: markers,
hook implementations (added in later WBS), and any pytest-level
configuration that must be visible in *the consumer's* pytest session.

Scope of this module (WBS 1.3.1)
--------------------------------
* Register the ForgeQA markers (``ui``, ``api``, ``unit``,
  ``integration``) so that a consumer who writes ``@pytest.mark.ui``
  does not see ``PytestUnknownMarkWarning``.
* Do **not** import Playwright, HTTPX, or any optional dependency.
* Do **not** read any config file at import time.

The registration lives here (rather than in ``pyproject.toml``'s
``[tool.pytest.ini_options].markers``) because that section configures
*ForgeQA's own test suite*, not the consumer's. A consumer who installs
``forgeqa`` from PyPI has no ``pyproject.toml`` from us to inherit —
they get marker registration only via the plugin hook. See ADR-013.

**Import cost is critical.** Pytest imports this module in **every**
pytest invocation in **every** project where ``forgeqa`` is installed
— including projects that do not use ForgeQA at all. That import must
be cheap: no I/O, no heavy imports, no side effects. The expensive
work (the ``pytest_configure`` hook) runs only when Pytest is actually
about to run tests, not for ``pytest --version`` or ``pytest --help``.

To keep the import cheap, this module imports only:
* the stdlib,
* ``pytest`` (already installed as a runtime dependency, so no
  additional cost),
* nothing from ``forgeqa.*`` — the marker manifest is a plain tuple
  of strings and does not need the config schema.

A future WBS (1.3.x — the ``browser`` / ``api_client`` fixtures) will
add imports of ``forgeqa.config`` and optional adapters *inside*
hook implementations or fixtures, so the module-level import stays
cheap. Do not hoist those imports to module level without measuring
the cost first.

Marker manifest
---------------
The tuple :data:`FORGEQA_MARKERS` is the **single source of truth**
for the markers ForgeQA registers. It is also imported by
``tests/unit/test_plugin_registration.py`` to assert that the plugin
registers exactly these markers — so adding a marker is a one-place
change and the tests catch a forgotten registration. It is not
``__all__``-exported from ``forgeqa.config`` (markers are a pytest
concern, not a config concern); a future WBS that wants to expose the
manifest publicly can decide that separately.

Why these four markers?
-----------------------
* ``ui`` — a test that exercises a browser via Playwright.
* ``api`` — a test that exercises an HTTP API via HTTPX.
* ``unit`` — a fast, hermetic test with no I/O.
* ``integration`` — a test that exercises multiple components
  together (may use I/O, may be slow).

``smoke`` and ``slow`` are deliberately **not** registered by the
plugin. They are ForgeQA's own test-suite conventions (declared in
``[tool.pytest.ini_options].markers``); they are not ForgeQA-consumer
concepts. A consumer who wants ``smoke`` or ``slow`` declares them in
their own ``pyproject.toml`` or ``pytest.ini``. See ADR-013
§Alternatives Considered.

See also
--------
* ADR-013 — pytest11 registration and marker manifest design
* ``docs/plugins.md`` — the pytest surface ForgeQA exposes
* ``docs/engineering-standards.md`` §"Pytest markers" — the
  contributor-facing conventions
"""

from __future__ import annotations

import pytest

__all__ = [
    "FORGEQA_MARKERS",
    "pytest_configure",
]


#: The markers ForgeQA registers on **the consumer's** pytest session.
#:
#: The tuple is the single source of truth: ``pytest_configure`` iterates
#: it, and ``tests/unit/test_plugin_registration.py`` asserts against it.
#: Add a marker here and the test file's expectation must be updated —
#: that coupling is deliberate, it makes "add a marker" a two-place
#: change that a reviewer cannot forget.
#:
#: Each entry is ``(marker_name, description)``. The description is
#: what ``pytest --markers`` prints, so it should be one sentence that
#: a consumer can act on. It must **not** reference ForgeQA internals
#: (module names, class names); a consumer does not need to know where
#: the marker is implemented.
#:
#: Order is alphabetical, by convention; the test asserts the set, not
#: the order, so a reordering is not a breaking change.
FORGEQA_MARKERS: tuple[tuple[str, str], ...] = (
    (
        "api",
        "Mark a test that exercises an HTTP API via ForgeQA's api_client fixture.",
    ),
    (
        "integration",
        "Mark a test that exercises multiple components together (may use I/O).",
    ),
    (
        "ui",
        "Mark a test that exercises a browser via ForgeQA's browser fixture.",
    ),
    (
        "unit",
        "Mark a fast, hermetic test with no I/O.",
    ),
)


def pytest_configure(config: pytest.Config) -> None:
    """Register ForgeQA's markers on the consumer's pytest session.

    Called by Pytest once, after the plugin is loaded and before test
    collection. This is the **only** place ForgeQA registers markers;
    the function is idempotent (``config.addinivalue_line`` appends to
    a list, but pytest deduplicates marker descriptions at display
    time, and re-registering a marker is a no-op for validation
    purposes).

    Parameters
    ----------
    config
        The pytest configuration object. We use it only for
        :meth:`addinivalue_line <pytest.Config.addinivalue_line>`; we
        do **not** read ``config.option``, ``config.inicfg``, or any
        consumer configuration here. That is deliberate — the plugin
        must be safe to load in a consumer's project regardless of
        that project's pytest configuration. Reading config is a
        Phase 1 concern (``forgeqa.toml`` loading via a fixture).

    Notes
    -----
    **Why a manifest and not inline strings.** ``config.addinivalue_line``
    is called once per marker; the loop reads from
    :data:`FORGEQA_MARKERS` so the tuple and the registration cannot
    drift. The test file asserts that every name in the manifest
    appears in the plugin's registered markers, so a marker added to
    the manifest but not iterated here (or vice versa) is a CI
    failure. This is the "single source of truth" pattern applied to
    pytest registration.

    **Why not ``config.add_cleanup``.** Markers registered via
    ``addinivalue_line`` in ``pytest_configure`` do not need cleanup —
    they are consumed by Pytest for validation and by ``--markers``
    for display; they have no runtime resource attached. Adding a
    cleanup would be cargo-cult.

    **Failure mode.** If a future Pytest version renames
    ``addinivalue_line`` or changes its signature, this function will
    raise at plugin-load time. That failure is *loud* (the user's
    pytest invocation fails with a clear traceback naming ForgeQA),
    which is the correct failure mode — a silently-missing marker
    registration is worse, because the user gets a confusing
    ``PytestUnknownMarkWarning`` that does not name the plugin.
    """
    for name, description in FORGEQA_MARKERS:
        config.addinivalue_line("markers", f"{name}: {description}")
