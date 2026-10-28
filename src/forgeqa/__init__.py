"""ForgeQA - A reusable, evidence-first Python test automation foundation.

This package provides the core framework for building, executing, and
maintaining automated tests across UI, API, and CI/CD workflows.

For more information, see the project documentation:
https://github.com/thapelomagqazana/forgeqa
"""

from __future__ import annotations

__version__ = "0.1.0"
__author__ = "ForgeQA Maintainer"
__license__ = "MIT"

__all__ = ["__version__", "__author__", "__license__", "get_version"]


def get_version() -> str:
    """Return the current ForgeQA version string."""
    return __version__
