"""ForgeQA - A reusable, evidence-first Python test automation foundation.

This package provides the core framework for building, executing, and
maintaining automated tests across UI, API, and CI/CD workflows.

For more information, see the project documentation:
https://github.com/thapelomagqazana/forgeqa

The full public API contract — what you can rely on, what you cannot, and
how ForgeQA evolves the boundary — is documented in ``docs/public-api.md``
(see ADR-006 for the decision record). In summary:

* Names in :data:`__all__` are public. Currently ``__version__`` and
  ``get_version``.
* Any name or submodule starting with a single underscore
  (``forgeqa._internal``, ``forgeqa._config``, …) is **private** and may
  change without a deprecation cycle. Importing a private name is
  unsupported.
* Public submodules (``forgeqa.fixtures``, ``forgeqa.settings``, …) are
  added in Phase 1 and documented in ``docs/public-api.md`` at the same
  time as they are added to :data:`__all__`.

The rule is enforced by ``tests/unit/test_public_api.py`` on every PR.

Design constraints (see ``docs/public-api.md`` and ``ADR-002``):

1. **Zero-cost import.** Importing :mod:`forgeqa` must not require Playwright
   or HTTPX to be installed, must not read configuration files, must not
   touch the network, and must not emit log records or warnings. This keeps
   CLI tools, type-checkers, doc builders, and package managers fast and
   side-effect free.
2. **Version is the single source of truth.** ``__version__`` is resolved from
   installed package metadata via :func:`importlib.metadata.version`, not
   hard-coded. The value in ``pyproject.toml`` is authoritative; this module
   reflects it. If metadata is missing (e.g. running from a source checkout
   without an editable install), a clearly-marked fallback is returned so that
   ``import forgeqa`` never raises.
3. **Stable public surface.** :data:`__all__` enumerates every name considered
   part of the public API. Anything not in :data:`__all__` is implementation
   detail and may change without a deprecation cycle. This is the contract
   from WBS 0.4.4.

The module deliberately does **not** use :func:`warnings.warn` at import time.
Warnings on import are a known footgun: they surface once per interpreter,
are easily swallowed by test runners, and are not actionable by end users.
Version-resolution problems are instead observable through the public
:func:`get_version` helper (returns a :class:`str`) and the private
:func:`_is_version_fallback` helper (returns :class:`bool`), which is used by
tests to distinguish an installed release from an uninstalled source checkout.
"""

from __future__ import annotations

from importlib.metadata import PackageNotFoundError
from importlib.metadata import version as _distribution_version
from typing import Final

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

#: The distribution name as declared in ``pyproject.toml`` (``[project].name``).
#: Kept private: consumers should treat the project as ``forgeqa`` without
#: needing to know how it is packaged.
_DISTRIBUTION_NAME: Final[str] = "forgeqa"

#: Fallback returned when installed distribution metadata is unavailable, i.e.
#: when the interpreter imported this module from a source tree that has not
#: been installed (no ``.dist-info`` on ``sys.path``). The value is explicitly
#: non-release-shaped to make it obvious that it is not a real version, and it
#: parses under :class:`packaging.version.Version` (as a post-release of
#: ``0.0.0``) so that tools which *do* parse it still succeed and sort it below
#: any real release.
_FALLBACK_VERSION: Final[str] = "0.0.0+unknown"

#: Human-readable author string, exposed for diagnostics and reporting.
#: Not part of :data:`__all__` — consumers who need attribution should read
#: the package's ``METADATA``, not this module.
__author__: Final[str] = "ForgeQA Maintainer"

#: SPDX identifier for the project's license. Kept in sync with
#: ``[project].license`` in ``pyproject.toml`` and with the ``LICENSE`` file
#: at the repository root. Not part of :data:`__all__` for the same reason
#: as :data:`__author__`.
__license__: Final[str] = "MIT"


# ---------------------------------------------------------------------------
# Version resolution
# ---------------------------------------------------------------------------


def _resolve_version() -> tuple[str, bool]:
    """Return ``(version, is_fallback)`` for the installed distribution.

    Attempts to read ``Version`` from the installed distribution metadata via
    :func:`importlib.metadata.version`. This is the same mechanism ``pip show``
    uses, so the value is guaranteed consistent with the installed artifact.

    Returns
    -------
    tuple[str, bool]
        ``(version_string, is_fallback)`` where ``is_fallback`` is ``True``
        when the distribution metadata was unavailable and the value returned
        is :data:`_FALLBACK_VERSION`.

    Notes
    -----
    This function is intentionally narrow: it catches **only**
    :class:`importlib.metadata.PackageNotFoundError`, which is the documented
    signal for "distribution is not installed". Any other exception (e.g. a
    corrupt ``METADATA`` file) is allowed to propagate — a corrupt install is
    a real problem that should surface, not be masked by a fallback.
    """
    try:
        return _distribution_version(_DISTRIBUTION_NAME), False
    except PackageNotFoundError:
        return _FALLBACK_VERSION, True


__version__, _IS_FALLBACK_VERSION = _resolve_version()
"""The ForgeQA version string, resolved from installed package metadata.

Populated at import time from :func:`_resolve_version`. See module docstring
for the rationale behind using :func:`importlib.metadata.version` instead of
a hard-coded literal.

Examples
--------
>>> import forgeqa
>>> isinstance(forgeqa.__version__, str)
True
"""


def get_version() -> str:
    """Return the current ForgeQA version string.

    This is the recommended accessor for any code that embeds the version in
    reports, logs, or artifacts. It returns the same value as
    :data:`forgeqa.__version__`, but insulates callers from a future refactor
    in which the version may become lazily evaluated.

    Returns
    -------
    str
        The PEP 440 version string of the installed ``forgeqa`` distribution,
        or :data:`_FALLBACK_VERSION` (``"0.0.0+unknown"``) when running from
        an uninstalled source checkout.

    Examples
    --------
    >>> from forgeqa import get_version
    >>> isinstance(get_version(), str)
    True
    """
    return __version__


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

__all__: Final[tuple[str, ...]] = (
    "__version__",
    "get_version",
)
"""Public API surface for the top-level :mod:`forgeqa` package.

Only names listed here are part of the supported public API. Anything else
(including module-private names prefixed with ``_``) may change without a
deprecation cycle.

Adding a name here is a **semantic versioning event**: it widens the contract
and must be accompanied by a documentation update in ``docs/public-api.md``
and a note in the changelog at release time. The tuple is immutable on
purpose — a mutable ``list`` would let consumers widen the contract at
runtime by accident.

Enforced by ``tests/unit/test_public_api.py::test_all_matches_documented_surface``,
which compares this tuple against a test-authoritative ``EXPECTED_ALL``
constant (not against ``forgeqa.__all__`` itself, which would be a
tautology). A drift between this tuple, ``docs/public-api.md``, and
``EXPECTED_ALL`` fails CI.
"""


# ---------------------------------------------------------------------------
# Developer ergonomics: make fallback visible to tests, not to user output
# ---------------------------------------------------------------------------


def _is_version_fallback() -> bool:
    """Return ``True`` if :data:`__version__` came from the fallback path.

    Intended for test suites and for tooling that needs to distinguish a real
    release from an uninstalled source checkout. Not part of :data:`__all__`
    because it is diagnostic, not contractual; it may change between releases.

    Returns
    -------
    bool
        ``True`` when ``forgeqa`` is not installed and :data:`__version__`
        equals :data:`_FALLBACK_VERSION`.
    """
    return _IS_FALLBACK_VERSION
