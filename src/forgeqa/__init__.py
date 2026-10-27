"""
ForgeQA - A reusable, evidence-first Python test automation foundation.

This package provides the core framework for building, executing, and
maintaining automated tests across UI, API, and CI/CD workflows.

For more information, see the project documentation:
https://github.com/thapelomagqazana/forgeqa
"""

from __future__ import annotations

__version__ = "0.1.0"
__author__ = "ForgeQA Maintainer"
__license__ = "MIT"


def get_version() -> str:
    """Return the current ForgeQA version string."""
    return __version__


# Public API re-exports will be added in Phase 1.
# Example: from forgeqa.fixtures import browser, api_client
