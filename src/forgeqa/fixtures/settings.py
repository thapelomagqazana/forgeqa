"""Session-scoped ``settings`` fixture for ForgeQA.

The fixture returns the :class:`~forgeqa.config.ForgeQAConfig` produced
by :func:`forgeqa.config.load_config` (WBS 1.2.2). It is the **only**
place in a test session where ForgeQA reads ``forgeqa.toml`` and
``FORGEQA_*`` environment variables; every other ForgeQA fixture
(``browser``, ``api_client``) consumes this fixture rather than calling
``load_config`` itself. That is the "resolved once per session and
shared" property of WBS 1.3.2.

The description of what the fixture provides and how to use it lives on
the :func:`settings` function itself, so it appears in
``pytest --fixtures`` without a separate constant to keep in sync. The
prose below is the **rationale** — why this design, why not the
alternatives — which does not belong in ``pytest --fixtures`` and would
be noise in the function docstring.

Why session scope?
------------------
* **Cost.** ``load_config`` reads a file and parses TOML (and, on a
  fresh process, imports Pydantic for the first time — ~30 ms). Paying
  that per test would dominate the runtime of a large suite.
* **Determinism.** A test that mutates ``forgeqa.toml`` or an env var
  mid-session would see different configs depending on test order;
  session scope makes the config a snapshot.
* **Correctness of the "resolved once" claim.** The WBS acceptance
  criterion is that the config is resolved once per session; session
  scope is the mechanism, not an optimisation. Pinned by
  ``tests/unit/test_settings_fixture.py::test_settings_fixture_is_session_scoped``
  and ``tests/integration/plugin/test_settings_fixture_smoke.py``
  (which counts ``load_config`` calls across a session-scoped fixture
  via ``unittest.mock.patch``).

Why not function scope?
-----------------------
Function scope would call ``load_config`` per test. That defeats both
the "resolved once" criterion and the "shared" criterion — the whole
point is that ``browser`` and ``api_client`` see the same config
object. Function scope would also be slow (~30 ms × N tests).

Why no ``autouse``?
-------------------
``autouse=True`` would load the config even for test sessions that
never use a ForgeQA fixture — e.g. a pytest run that collects a
non-ForgeQA project that happens to have ``forgeqa`` installed. That
would violate the "do no harm" property of a pytest plugin (the
plugin's fixtures must not impose cost on projects that don't use
them). The fixture is opt-in: a test that takes ``settings`` as a
parameter gets it; a test that does not, does not.

Why no cached property / ``functools.lru_cache``?
-------------------------------------------------
Pytest's session-scoped fixture cache **is** the cache. Adding an
``lru_cache`` to ``load_config`` would (a) break the loader's
"no caching" contract (see ``docs/engineering-standards.md`` §5.2,
rule 4) and (b) prevent a developer from seeing a config change in
a fresh pytest session (which they would expect to). The fixture is
the scope boundary; the loader stays stateless.

Why the fixture body has no parameters
--------------------------------------
The body takes no ``request``, no ``config``, no other pytest-provided
object. That makes the body testable by calling the wrapped function
directly (``settings._fixture_function()`` under pytest 8; see
``tests/unit/test_settings_fixture.py::_fixture_body``) without needing
an active fixture request. It also prevents the hidden-coupling
failure mode of reading ``request.config.option`` to decide what to
load. A consumer who needs a different config overrides ``settings``
in their own ``conftest.py`` — a two-line change that does not require
the plugin to grow parameters.

Why no ``_FIXTURE_DOC`` constant
--------------------------------
The original design put the description in a module-level
``_FIXTURE_DOC`` constant and kept the function's docstring as a short
pointer to it. That created two copies of the same prose, and the
copies drifted — which a parity test correctly caught. The current
design has one source of truth: the function's docstring, which is
what ``pytest --fixtures`` shows and what a reader sees when they open
the file. The module docstring's rationale (above) is a different
thing (why, not what) and does not need to match the function's
docstring.

See also
--------
* ADR-014 — the decision record for this fixture.
* ``docs/plugins.md`` §"Fixtures the plugin provides" — the
  consumer-facing reference (the fixture's table entry, an example,
  the session-scope caveat, the error behaviour, the override
  pattern).
* ``docs/configuration.md`` §"Loading configuration" — what
  ``load_config`` does.
"""

from __future__ import annotations

import pytest

from forgeqa.config import ForgeQAConfig, load_config

__all__ = ("settings",)


@pytest.fixture(scope="session")
def settings() -> ForgeQAConfig:
    """Session-scoped :class:`~forgeqa.config.ForgeQAConfig` for the test session.

    The fixture calls :func:`forgeqa.config.load_config` **exactly once**
    per session and returns the resulting config object. Every other
    ForgeQA fixture (``browser``, ``api_client``) depends on this
    fixture, so the config is resolved once and shared across the whole
    test session.

    The config is loaded with **no arguments** — the default search
    applies: ``forgeqa.toml`` in the current working directory (see
    :func:`forgeqa.config.find_config_path`), then ``FORGEQA_*``
    environment variables, then the field defaults. To use a different
    path or a different environment mapping, write your own fixture in
    your project's ``conftest.py`` that calls ``load_config`` with
    those arguments and override ``settings`` for the tests that need
    it.

    Example
    -------
    .. code-block:: python

        # tests/test_api.py
        from pydantic import AnyHttpUrl

        def test_api_root(settings):
            # settings is a ForgeQAConfig; attribute access works normally.
            assert settings.api.base_url == AnyHttpUrl("http://127.0.0.1:8000")

    **Session scope means the config is a snapshot.** A test that
    mutates ``forgeqa.toml`` or an env var mid-session will not see
    the change in a ``settings`` fixture that was already created.
    The underlying model is frozen, so you cannot mutate a
    ``settings`` object either — use
    ``settings.model_copy(update=...)`` for a modified copy.

    **Error behaviour.** If ``forgeqa.toml`` is malformed or contains
    an invalid value, pytest reports a **fixture-setup error** naming
    the offending file and field. The fixture does not swallow
    :class:`~forgeqa.config.ForgeQAConfigError` and does not fall
    back to defaults — a broken config must be visible.

    Returns
    -------
    ForgeQAConfig
        The config produced by ``load_config()`` with no arguments.

    Raises
    ------
    ForgeQAConfigError
        If the configuration cannot be loaded — a malformed
        ``forgeqa.toml``, an invalid value, an unreadable file, or an
        invalid ``FORGEQA_*`` environment variable. The exception
        propagates out of the fixture, which pytest reports as a
        fixture-setup error naming the offending file/var. This is
        the same exception ``load_config`` raises when called
        directly; the fixture does not wrap it, so the caller sees
        the original error message.
    """
    return load_config()
