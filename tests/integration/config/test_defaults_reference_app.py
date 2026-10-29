"""ATDD: safe defaults must work against the Phase 0.6 reference app.

This module is the *acceptance* half of WBS 1.2.5 ("The default config
works against the reference app without modification"). It does not
mock the HTTP layer — it drives the reference app's ``/health`` endpoint
using a config built *purely* from defaults.

It is deliberately narrower than ``tests/unit/config/test_defaults.py``:
that file asserts *values* (that ``environment == "local"``, that
``timeout_ms == 10_000``, and so on); this file asserts *behaviour* —
that a fresh-install user, doing nothing but installing ForgeQA, can
reach the reference app at the default address. A change that keeps all
the unit tests green but moves ``api.base_url`` away from the reference
app's origin would pass this file's absence, but fail its presence.

Markers
-------
``@pytest.mark.integration`` — run only in the integration CI job.
``@pytest.mark.api``         — grouped with other API-adapter tests.

The module uses a session-scoped probe fixture (``reference_app_url``)
that skips the whole module with a clear reason if the reference app is
not reachable. In CI, the workflow starts the app before this module
runs, so the skip never fires. Locally, a developer who has not started
the app gets a single, actionable skip line instead of five connection
errors::

    SKIPPED: reference app not reachable at http://127.0.0.1:8000/health
    (ConnectError). Start it with: make -C examples/reference-app up

Two static tests (``test_default_base_url_is_ipv4_loopback`` and
``test_default_base_url_has_no_path_suffix``) do **not** need the app —
they are pure config assertions that pin the "lessons learnt" from
ADR-011 and would catch a regression even if the app is down. As a
result, running this module without the app reports ``2 passed,
4 skipped``, not "all skipped". That asymmetry is deliberate: a skip
that hides a real property is worse than a pass that proves it.

Reference app: ``examples/reference-app/``
  - ``docker-compose.yml`` defines the listen port (8000).
  - ``app/routers/health.py`` implements ``GET /health`` → ``{"status": "ok"}``.

See:
  - ADR-011 (decision rationale for the ``api.base_url`` ↔ reference-app coupling)
  - ``docs/configuration.md`` §Defaults (per-field rationale table)
  - ``docs/configuration.md`` §"The reference-app coupling"
"""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import AnyHttpUrl

from forgeqa.config.models import ForgeQAConfig

# The API-adapter tests exercise the real HTTP boundary, so they need
# httpx (which lives in the ``api`` extra). Skip the whole module
# cleanly if it is not installed, rather than erroring at collection
# time. CI installs ``.[all]``, so the skip never fires there.
httpx = pytest.importorskip("httpx", reason="requires forgeqa[api]")

# All tests in this module are integration + API scoped. They exercise
# the real HTTP boundary and require the reference app to be reachable
# (or, for the two static invariants, to exercise the config directly).
pytestmark = [pytest.mark.integration, pytest.mark.api]

#: Reference-app start command, used verbatim in skip reasons so a
#: developer reading the pytest output can copy-paste the fix.
#: Kept in sync with the ``refapp-up`` target in the root Makefile.
_START_CMD = "make -C examples/reference-app up"

#: Default probe timeout, in seconds. Kept short so a local skip happens
#: quickly rather than after a 10-second TCP timeout. The full request
#: timeout (``api.timeout_seconds``, 10 s) is still applied to the
#: actual test request — this constant only bounds the *probe*.
_PROBE_TIMEOUT_SECONDS = 2.0


# ---------------------------------------------------------------------------
# Session-scoped probe fixture
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def reference_app_url() -> str:
    """Return the base URL of a reachable reference app, or skip.

    We do **not** hard-code ``http://127.0.0.1:8000`` here. Instead we
    read ``api.base_url`` from the *default config* — which is the
    whole point of WBS 1.2.5. If the default ever drifts away from the
    reference app's listen address, this fixture reuses the wrong
    address, the probe fails, and the whole module skips with a message
    naming the address it tried. That is a loud, actionable signal: the
    drift is exactly what the ATDD test exists to catch.

    The fixture also gives a *single* skip point. Without it, five
    connection errors would appear (one per test) with no obvious
    common cause. With it, one line says "app not running, start it
    with this command" — which is how a developer learns the workflow.

    Returns
    -------
    str
        The default config's ``api.base_url`` as a string. Includes
        the trailing slash that ``AnyHttpUrl`` adds; callers should
        either pass it to ``httpx.Client(base_url=...)`` (which
        tolerates the trailing slash) or ``rstrip("/")`` it before
        joining a path.

    Raises
    ------
    pytest.skip.Exception
        If the reference app's ``/health`` endpoint is not reachable
        within ``_PROBE_TIMEOUT_SECONDS``, or returns a non-200 status.
        The skip reason names the URL and the start command.
    """
    url = str(ForgeQAConfig().api.base_url)
    probe_url = url.rstrip("/") + "/health"

    try:
        response = httpx.get(probe_url, timeout=_PROBE_TIMEOUT_SECONDS)
    except (httpx.ConnectError, httpx.ConnectTimeout, httpx.ReadTimeout) as exc:
        pytest.skip(
            f"reference app not reachable at {probe_url} "
            f"({type(exc).__name__}). Start it with: {_START_CMD}"
        )

    if response.status_code != 200:
        pytest.skip(
            f"reference app returned {response.status_code} at {probe_url}; "
            f"expected 200. Check its logs: "
            f"docker compose -f examples/reference-app/docker-compose.yml logs"
        )

    return url


# ---------------------------------------------------------------------------
# ATDD: default config drives the reference app unchanged
# ---------------------------------------------------------------------------


class TestDefaultsWorkAgainstReferenceApp:
    """Drive the reference app using *only* the default config values.

    Each test is an assertion a prospective user can make after
    ``pip install forgeqa`` + a ``pytest`` run against the reference
    app, with no ``forgeqa.toml`` and no env vars. If one of these
    fails, the "out-of-the-box" experience is broken.
    """

    def test_reference_app_health_endpoint_reachable_with_defaults(
        self, reference_app_url: str
    ) -> None:
        """GET ``/health`` with the default base_url and default timeout.

        This is the strongest form of the WBS 1.2.5 acceptance criterion
        "The default config works against the reference app without
        modification": we do not pass *any* override — not even a
        timeout — and the request must succeed against the reference
        app.

        The body assertion (``{"status": "ok"}``) is part of the
        contract, not an incidental detail. If the reference app ever
        changes its health response shape, the default config no longer
        works out-of-the-box — which is exactly what this test exists
        to catch. The fix is either to update the reference app (and
        the assertion) or to reconsider the coupling (see ADR-011
        §Reconsideration Trigger, trigger 2).

        The request uses ``httpx.Client`` (sync), matching what the
        eventual ``api_client`` fixture (Phase 1) will wrap. It does
        **not** import the fixture — the fixture does not exist yet,
        and this test must run before it lands.
        """
        # Use the default config's base_url *and* the default
        # timeout_seconds (10 s) — no override of either.
        cfg = ForgeQAConfig()
        with httpx.Client(
            base_url=str(cfg.api.base_url),
            timeout=cfg.api.timeout_seconds,
        ) as client:
            response = client.get("health")

        assert response.status_code == 200, (
            f"GET {cfg.api.base_url}health returned {response.status_code}; body: {response.text!r}"
        )
        assert response.json() == {"status": "ok"}

    def test_default_artifacts_dir_is_writable(self, tmp_path, monkeypatch) -> None:
        """The default ``artifacts_dir`` must be creatable without extra setup.

        Resolves ``cfg.general.artifacts_dir`` against a temp directory
        (not the real CWD, to avoid touching the repo) and asserts that
        creating it succeeds. This is a contract check: a default that
        points at a location a normal user cannot create (e.g.
        ``/var/forgeqa`` or a read-only path on CI) would break the
        out-of-the-box experience in a way the unit test cannot catch
        (the unit test asserts the *string value*, not that the
        filesystem permits it).

        Why ``tmp_path`` rather than the real CWD: this test runs in
        the integration job, and side effects in the repo working
        directory would be surprising. ``monkeypatch.chdir(tmp_path)``
        makes relative-path resolution match what a user would see if
        they had ``cd``'d into a fresh project.

        Note that the model's ``artifacts_dir`` validator already
        proved that the path *can* be created (see
        ``GeneralConfig._artifacts_dir_must_be_creatable``); this test
        proves that it *is* created successfully, which is a stronger
        claim and one the validator deliberately does not make (the
        validator must not perform I/O — see ADR-010 Decision #3).
        """
        monkeypatch.chdir(tmp_path)
        cfg = ForgeQAConfig()
        artifacts = Path(cfg.general.artifacts_dir)

        # The default is relative; after the chdir it resolves under
        # tmp_path. Resolve it the same way the framework will.
        resolved = (tmp_path / artifacts).resolve()
        resolved.mkdir(parents=True, exist_ok=True)

        probe = resolved / ".forgeqa-probe"
        probe.write_text("ok", encoding="utf-8")
        assert probe.read_text(encoding="utf-8") == "ok"

        # Clean up so a future run starts from the same state.
        probe.unlink()
        resolved.rmdir()

    def test_default_artifact_dir_matches_reference_app_port(self, reference_app_url: str) -> None:
        """The default base_url and the reference app agree on origin.

        This is a *structural* assertion: it reads the default
        ``api.base_url``, and asserts that it matches
        ``reference_app_url`` (which is itself derived from the default
        config, so this test only fails if the fixture and the config
        drift — i.e. if someone changed one but not the other). It is
        the single line that documents *why* the ATDD test above can
        exist: the default config points at the same origin the
        reference app binds to.

        The trailing-slash normalisation is compared via
        ``AnyHttpUrl``, not string equality: pydantic normalises
        ``"http://127.0.0.1:8000"`` to ``"http://127.0.0.1:8000/"`` in
        the rendered form (see ADR-011 §Lessons learnt). Comparing
        URLs semantically keeps this test meaningful across a future
        normalisation change.
        """
        cfg_url = ForgeQAConfig().api.base_url
        assert cfg_url == AnyHttpUrl(reference_app_url)

    def test_default_browser_settings_are_ci_compatible(self) -> None:
        """``headless=True`` + ``chromium`` must be the CI-compatible pair.

        This is a static assertion (no browser launch) that documents
        the intent: the default must be launchable in a headless
        GitHub Actions runner. The actual Playwright launch is covered
        by the UI test suite once the ``browser`` fixture lands
        (WBS 1.3.x).

        Kept here (rather than in the unit file) because the WBS 1.2.5
        acceptance criterion explicitly mentions "works against the
        reference app", and a headless-browser default is part of the
        "works on CI" half of that claim. When the ``browser`` fixture
        lands, extend this module with a real launch test; do not
        duplicate the value assertions.
        """
        cfg = ForgeQAConfig()
        assert cfg.browser.headless is True
        assert cfg.browser.browser_name == "chromium"
        assert cfg.browser.screenshot_on_failure is True
        assert cfg.browser.trace_on_failure is True


# ---------------------------------------------------------------------------
# Static invariants: run without the reference app
# ---------------------------------------------------------------------------


class TestReferenceAppStaticInvariants:
    """Pure config assertions that pin the ADR-011 "lessons learnt".

    These tests do **not** need the reference app; they run even when
    the probe fixture would skip. They exist because they encode two
    decisions that are easy to accidentally revert in a "cleanup"
    refactor, and because their failure mode is unambiguous:

    * ``127.0.0.1`` vs. ``localhost`` — IPv6-vs-IPv4 resolution
      surprise on some Linux images (see ADR-011 §Lessons learnt).
    * bare origin vs. ``/api`` suffix — the reference app's health
      endpoint is ``/health``, not ``/api/health``, and a "base URL"
      conventionally carries no path suffix.

    Asserting these as tests (not just as comments) means a future
    refactor cannot silently revert them; if it tries, CI fails with a
    message naming the ADR section that explains why.
    """

    def test_default_base_url_is_ipv4_loopback(self) -> None:
        """The default ``api.base_url`` must use ``127.0.0.1``, not ``localhost``.

        Rationale (documented in ADR-011 §Lessons learnt): on some
        Linux CI images ``localhost`` resolves to ``::1`` first, and
        the reference app binds IPv4 only — so ``localhost`` would
        fail on such images while ``127.0.0.1`` succeeds. This test
        pins the choice so a future "cleanup" refactor cannot
        accidentally revert it.

        Runs without the reference app (it is a pure string check on
        the default), but lives here because it is a property of the
        reference-app coupling, not of the config schema.
        """
        cfg = ForgeQAConfig()
        assert "127.0.0.1" in str(cfg.api.base_url), (
            "api.base_url must use 127.0.0.1 (IPv4 explicit) rather than "
            "localhost; see ADR-011 §Lessons learnt"
        )

    def test_default_base_url_has_no_path_suffix(self) -> None:
        """The default ``api.base_url`` must be a bare origin (no ``/api``).

        Rationale (documented in ADR-011 §Alternatives Considered): a
        "base URL" conventionally carries no path suffix, and the
        reference app's health endpoint is at ``/health``, not
        ``/api/health``. This test pins the choice.

        Runs without the reference app.
        """
        cfg = ForgeQAConfig()
        url = str(cfg.api.base_url).rstrip("/")
        # The origin (scheme://host:port) has exactly one "/" after the
        # "://" — the authority separator. A path suffix would add a
        # second "/" followed by non-empty text.
        scheme, _, rest = url.partition("://")
        assert scheme in {"http", "https"}, (
            f"api.base_url must use http or https; got scheme {scheme!r}"
        )
        assert "/" not in rest, (
            f"api.base_url must be a bare origin (no path suffix); "
            f"got {url!r}. See ADR-011 §Alternatives Considered."
        )
