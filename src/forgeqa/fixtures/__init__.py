"""ForgeQA pytest fixtures.

This subpackage contains the fixtures ForgeQA exposes to consumers.
Each fixture lives in its own module so that importing one fixture does
not import the dependencies of the others: the ``settings`` fixture
needs ``forgeqa.config``; the future ``browser`` fixture needs
Playwright; the future ``api_client`` fixture needs HTTPX. Isolating
them means a project that uses only ``settings`` does not pay for
Playwright, and a project that uses only ``browser`` does not need the
HTTPX import to succeed.

Fixtures are registered via ``pytest_plugins`` in
``forgeqa.pytest_plugin`` (WBS 1.3.2 / ADR-014), not by
``conftest.py`` auto-discovery — the latter only works for a project's
own ``conftest.py``, not for a third-party plugin's submodules.

The public fixture names are:

* ``settings`` — the session-scoped :class:`~forgeqa.config.ForgeQAConfig`
  (WBS 1.3.2).

Future additions (Phase 1):

* ``browser`` — a Playwright ``Browser`` (WBS 1.3.3).
* ``api_client`` — an HTTPX client configured from ``settings`` (WBS 1.3.4).

``__all__`` lists only the **fixture function names**, so a consumer
who wants to re-export them (e.g. from their own ``conftest.py`` for
type-checking) has a stable import path.
"""

from __future__ import annotations

__all__ = ("settings",)
