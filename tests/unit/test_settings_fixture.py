"""Unit tests for the ``settings`` fixture (WBS 1.3.2).

The tests cover:

* The fixture is importable from the stable paths documented in
  :mod:`forgeqa.fixtures` and :mod:`forgeqa.fixtures.settings`.
* The fixture is registered with pytest via ``pytest_plugins`` in
  :mod:`forgeqa.pytest_plugin` — the only mechanism that makes it
  discoverable by a consumer without a ``conftest.py`` override.
* The fixture is declared session-scoped (WBS acceptance criterion
  "settings is session-scoped"). Checked at the **source** level
  (``@pytest.fixture(scope="session")`` is present) rather than via
  pytest's runtime introspection, whose API (`_pytestfixturefunction`,
  `_fixture_function`, …) is private and changes between minor
  versions.
* The fixture body is ``return load_config()`` — no arguments, no
  ``try``/``except``. Checked at the source level, for the same reason.
* The returned config exposes the fields the WBS acceptance criterion
  names (specifically ``settings.api.base_url``).

**Why source-level checks, not runtime introspection.** Pytest's
fixture-wrapper attributes (`_pytestfixturefunction` in pytest 7,
`FixtureFunctionDefinition._fixture_function` in pytest 8.4, and
whatever it becomes next) are private implementation details.
Attempting to read them makes this test suite fragile against every
pytest minor release. The **behaviour** of the fixture — is it
session-scoped, does it call ``load_config`` once, does it propagate
errors — is what the ATDD suite
(``tests/integration/plugin/test_settings_fixture_smoke.py``) verifies
end-to-end, with a real pytest subprocess. The tests here verify the
**shape** of the declaration (the decorator, the body) so a
regression is caught in a fast, hermetic test, and the ATDD suite
verifies the **behaviour** so a regression is caught with a real
pytest session.

See also
--------
* ADR-014 — the decision record for this fixture.
* ``docs/plugins.md`` §"Fixtures the plugin provides" — consumer-facing
  reference.
* ``tests/integration/plugin/test_settings_fixture_smoke.py`` — the
  end-to-end behaviour tests.

Run only these tests:

    pytest tests/unit/test_settings_fixture.py -v
"""

from __future__ import annotations

import inspect

import pytest
from pydantic import AnyHttpUrl

from forgeqa.fixtures import settings as settings_module
from forgeqa.pytest_plugin import pytest_plugins

pytestmark = pytest.mark.unit


# =============================================================================
# Import surface — stable paths
# =============================================================================


def test_settings_fixture_is_importable_from_documented_path() -> None:
    """``from forgeqa.fixtures.settings import settings`` works.

    The import path is a contract: a consumer who wants to type-check
    ``settings: ForgeQAConfig`` in their test file can import the
    fixture function from this path without importing the plugin
    module. That matters because the plugin module is loaded by
    pytest; importing it explicitly from a test file would double-load
    it (harmless but confusing in stack traces).
    """
    assert hasattr(settings_module, "settings")
    assert callable(settings_module.settings)


def test_settings_is_in_fixtures_all() -> None:
    """The fixture is listed in ``forgeqa.fixtures.__all__``.

    ``__all__`` is the documented surface of the subpackage (per
    ``docs/engineering-standards.md`` §4.14 — same convention as the
    top-level package). Adding a fixture without updating ``__all__``
    means the fixture works but is undocumented in the "what does this
    package export" sense; the test catches that.
    """
    import forgeqa.fixtures as pkg

    assert "settings" in pkg.__all__


# =============================================================================
# Registration — pytest_plugins is the discovery mechanism
# =============================================================================


def test_pytest_plugin_declares_settings_subplugin() -> None:
    """``pytest_plugins`` in ``forgeqa.pytest_plugin`` lists ``forgeqa.fixtures.settings``.

    Without this declaration, the fixture exists but pytest does not
    discover it: pytest only auto-discovers a project's own
    ``conftest.py``, not a third-party plugin's submodules. The
    ``pytest_plugins`` tuple is the load-bearing mechanism — see
    ADR-014 §Decision #1.

    The assertion is on the *tuple*, not on pytest having loaded the
    module, because a unit test does not run pytest's plugin manager.
    The end-to-end proof is in the ATDD test.
    """
    assert "forgeqa.fixtures.settings" in pytest_plugins


def test_pytest_plugins_is_a_tuple() -> None:
    """``pytest_plugins`` is an immutable tuple.

    Same rationale as ``FORGEQA_MARKERS`` in the plugin module: an
    immutable value, not a mutable global. A test that wants to
    simulate an addition constructs a new tuple; the module-level
    tuple is not mutated.
    """
    assert isinstance(pytest_plugins, tuple)
    for entry in pytest_plugins:
        assert isinstance(entry, str)


# =============================================================================
# Fixture declaration — scope, docstring, body shape (source-level)
# =============================================================================


def test_settings_fixture_is_session_scoped() -> None:
    """WBS 1.3.2 acceptance: the fixture is declared session-scoped.

    Checks the module source for the ``@pytest.fixture(scope="session")``
    decorator. This is robust to pytest's runtime introspection API
    changing (which it has, repeatedly: ``_pytestfixturefunction``
    in pytest 7, ``FixtureFunctionDefinition._fixture_function`` in
    pytest 8.4, and whatever comes next).

    The end-to-end proof that pytest *honours* session scope is the
    ATDD test (``test_settings_fixture_is_discovered_and_session_scoped``),
    which counts ``load_config`` calls across two test files in one
    session and asserts the count is exactly 1.
    """
    source = inspect.getsource(settings_module)
    assert '@pytest.fixture(scope="session")' in source, (
        "settings fixture is not declared with scope='session'; "
        "WBS 1.3.2 requires session scope. If the decorator's "
        "formatting changed (e.g. `scope='session'` with single "
        "quotes), update this assertion."
    )


def test_settings_fixture_has_a_useful_docstring() -> None:
    """The fixture carries a docstring, visible in ``pytest --fixtures``.

    A fixture without a docstring appears as a bare name in
    ``pytest --fixtures`` output — a consumer who runs that command
    has no idea what the fixture provides. The docstring is part of
    the consumer-facing surface.

    Reads the source (not the wrapper's ``__doc__``) for the same
    reason as the scope test: pytest's fixture wrapper does not
    reliably expose the wrapped function's docstring across versions.
    """
    source = inspect.getsource(settings_module.settings)
    # Find the docstring: the first triple-quoted string after `def settings`.
    # A proper docstring is at least 50 chars and mentions the config type.
    first_triple = source.find('"""')
    if first_triple == -1:
        raise AssertionError("settings fixture has no docstring")
    second_triple = source.find('"""', first_triple + 3)
    if second_triple == -1:
        raise AssertionError("settings fixture docstring is not closed")
    doc = source[first_triple + 3 : second_triple].strip()
    assert len(doc) >= 50, (
        f"settings fixture docstring is too short ({len(doc)} chars); add a real description"
    )
    mentions_purpose = any(keyword in doc for keyword in ("ForgeQAConfig", "load_config", "config"))
    assert mentions_purpose, (
        "settings fixture docstring does not mention ForgeQAConfig, "
        "load_config, or config; it should say what the fixture provides"
    )


def test_fixture_source_contains_return_load_config() -> None:
    """The fixture body is ``return load_config()`` (no arguments).

    A consumer who takes ``settings`` as a parameter expects the
    default search: ``forgeqa.toml`` in CWD, then ``FORGEQA_*`` env
    vars, then defaults. A future change that adds an argument (e.g.
    ``load_config(path=...)`` from a pytest option) would break that
    contract and, more importantly, would make the fixture's behaviour
    depend on pytest configuration — the hidden-coupling failure mode
    ADR-013 §Context warns about.

    Checks the source rather than calling the body: the body's
    invocation through pytest's wrapper is version-specific, and the
    ATDD test already proves the *behaviour* (a temp project's
    ``forgeqa.toml`` is reflected in ``settings.api.base_url``).
    """
    source = inspect.getsource(settings_module.settings)
    # The last non-blank line of the body should be `return load_config()`.
    body_lines = [
        line.strip()
        for line in source.splitlines()
        if line.strip() and not line.strip().startswith(('"""', "#"))
    ]
    # Find the `return` statement.
    return_lines = [line for line in body_lines if line.startswith("return")]
    assert return_lines, "fixture body has no `return` statement"
    assert "load_config()" in return_lines[-1], (
        f"fixture body returns {return_lines[-1]!r}; "
        "expected `return load_config()` with no arguments"
    )


def test_fixture_body_does_not_swallow_errors() -> None:
    """The fixture body has no ``try``/``except`` around ``load_config``.

    A ``try``/``except`` in the body would swallow
    ``ForgeQAConfigError`` and either return a default config or
    re-raise a different exception — both hide the user's actual
    config bug. The body is ``return load_config()``; this test
    asserts that shape.

    The end-to-end proof is the ATDD test that runs pytest against a
    broken ``forgeqa.toml`` and asserts a non-zero exit and an error
    naming the file and field.
    """
    source = inspect.getsource(settings_module.settings)
    # Look for try/except in the *body* (not the docstring or decorator).
    # A simple heuristic: the body is the lines after the docstring's
    # closing `"""`.
    close_doc = source.find('"""', source.find('"""') + 3)
    body = source[close_doc + 3 :] if close_doc != -1 else source
    assert "try:" not in body, "fixture body contains a try/except"
    assert "except" not in body, "fixture body contains an except clause"


# =============================================================================
# Loader contract — what the fixture re-exposes
# =============================================================================


def test_load_config_returns_a_forgeqa_config() -> None:
    """``load_config()`` with no arguments returns a :class:`ForgeQAConfig`.

    The fixture body is ``return load_config()``, so this is the
    contract the fixture re-exposes. Testing the loader here (rather
    than through the fixture wrapper) keeps the test hermetic and
    version-independent.

    **Why the class comes from the loader's output, not an import.**
    If ``forgeqa`` is importable from two paths (editable install
    alongside a wheel, or a duplicate ``sys.path`` entry), the
    ``ForgeQAConfig`` the test file imports can be a *different class
    object* from the one ``load_config`` returns. ``isinstance`` then
    returns ``False`` for an object that prints identically to the
    expected type. Reading ``type(config)`` and ``type(config).__name__``
    from the object itself makes the test independent of the
    environment's import resolution.
    """
    from forgeqa.config import load_config

    config = load_config()
    assert type(config).__name__ == "ForgeQAConfig", (
        f"load_config returned a {type(config).__name__!r}, expected 'ForgeQAConfig'"
    )
    # The type's module path should be forgeqa.config.models. This is
    # a stronger assertion than __name__ and catches the duplicate-
    # module case with a specific message.
    assert type(config).__module__ == "forgeqa.config.models", (
        f"load_config returned a {type(config).__name__} from "
        f"{type(config).__module__!r}, expected 'forgeqa.config.models'. "
        f"This usually means forgeqa is importable from two paths "
        f"(editable install + wheel install, or duplicate sys.path entry). "
        f'Run `pip uninstall -y forgeqa && pip install -e ".[dev]"`.'
    )


def test_load_config_default_api_base_url() -> None:
    """WBS 1.3.2 acceptance: the config exposes ``api.base_url``.

    The WBS calls this out by name; the test does too. ``base_url``
    is a Pydantic ``AnyHttpUrl`` (not a ``str``) — comparing against
    ``AnyHttpUrl`` is the pattern established in ADR-011's "compare
    semantically, not textually" lesson.

    Uses the default config; a separate ATDD test with a real
    ``forgeqa.toml`` proves the fixture reads a *custom* config.
    """
    from forgeqa.config import load_config

    config = load_config()
    assert config.api.base_url == AnyHttpUrl("http://127.0.0.1:8000")


def test_load_config_exposes_all_five_sub_models() -> None:
    """The config exposes all five sub-models the schema defines.

    The WBS acceptance criterion only names ``api.base_url``, but a
    fixture that returned a broken sub-model (e.g. a raw dict instead
    of a ``BrowserConfig``) would still pass the ``api.base_url``
    check. This test broadens the guarantee to "the fixture returns a
    fully-typed config".

    **Why ``type(...).__name__`` not ``isinstance``.** Same duplicate-
    module hazard as :func:`test_load_config_returns_a_forgeqa_config`:
    importing ``GeneralConfig`` etc. from ``forgeqa.config.models``
    can resolve to a different class object from the one the loader
    constructed if ``forgeqa`` is importable from two paths. Reading
    each sub-model's ``type(...).__name__`` and ``type(...).__module__``
    makes the test independent of import resolution and still catches
    the "raw dict" failure mode.
    """
    from forgeqa.config import load_config

    config = load_config()
    expected = {
        "general": "GeneralConfig",
        "browser": "BrowserConfig",
        "api": "APIConfig",
        "diagnostics": "DiagnosticsConfig",
        "reporting": "ReportingConfig",
    }
    for attr, expected_type_name in expected.items():
        sub = getattr(config, attr)
        actual_type = type(sub)
        assert actual_type.__name__ == expected_type_name, (
            f"config.{attr} is {actual_type.__name__!r}, expected {expected_type_name!r}"
        )
        assert actual_type.__module__ == "forgeqa.config.models", (
            f"config.{attr} is from {actual_type.__module__!r}, "
            f"expected 'forgeqa.config.models'. This usually means "
            f"forgeqa is importable from two paths; see the "
            f"test_load_config_returns_a_forgeqa_config docstring."
        )
