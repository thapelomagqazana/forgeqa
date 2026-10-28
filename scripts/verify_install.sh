#!/usr/bin/env bash
# =============================================================================
# ForgeQA - Verify clean installation from the built wheel
# =============================================================================
#
# Purpose
# -------
# Prove, from a fresh virtual environment and a working directory that is
# *not* the source checkout, that:
#
#   1. `pip install <forgeqa-X.Y.Z.whl>` succeeds in a clean environment.
#   2. `import forgeqa` works without the source tree being on `sys.path`
#      (i.e. no `PYTHONPATH` pollution, no `.pth` file pointing at `src/`).
#   3. `forgeqa.__version__` matches the version in the wheel's `METADATA`
#      (so a stale editable install cannot mask a wheel regression).
#   4. `pytest` from a temporary working directory discovers the installed
#      package (proves the package is on `sys.path` as an installed
#      distribution, not as a `src/` shadow).
#   5. The temporary venv and temporary working directory are cleaned up.
#
# This is the executable form of WBS 1.1.5's acceptance criteria. It is run
# in CI (see .github/workflows/quality.yml) and locally via
# `make verify-install`.
#
# Why a fresh venv and not the developer's `.venv`
# ------------------------------------------------
# The developer's `.venv` almost certainly has `pip install -e .` applied
# (from `make install`), which puts `src/` on `sys.path` via a `.pth` file
# in `site-packages`. Any test of "does the wheel install?" run in that venv
# is meaningless: the editable install shadows the wheel, and `import
# forgeqa` succeeds regardless of whether the wheel is broken. A fresh venv
# has no editable install, no `PYTHONPATH`, and no `.pth` files, so it can
# only succeed if the wheel is genuinely installable and usable.
#
# Why a temporary working directory
# ---------------------------------
# Even inside a fresh venv, running `python -c "import forgeqa"` from the
# repo root would put the current directory on `sys.path[0]`, and `src/`
# is one `cd` away — a bug in the test or a forgotten `cd` could silently
# shadow the installed package. Running from `/tmp/forgeqa-verify-install.XXXXXX`
# eliminates that class of false positives. The `pytest` invocation goes
# one step further: it creates a *minimal* test file in the temp dir so
# `pytest` has something to collect, and asserts the collection itself
# resolves against the installed package.
#
# Design choices
# --------------
# - Installs from a wheel built in this script (not `dist/` verbatim) so a
#   stale `dist/` cannot mask a broken build. The wheel is built into a
#   fresh temp dir (not `dist/`) for the same reason as `verify_build.sh`.
# - Clears `PYTHONPATH` in every subprocess, even though `--no-site` and a
#   fresh venv should already do so; belt-and-braces against a dev's shell
#   exporting it.
# - Compares `forgeqa.__version__` against the wheel's `METADATA`, not
#   against a hard-coded string. A version mismatch means the installed
#   package is not the wheel we built (e.g. an editable install leaked in).
# - Runs `pytest` with `-p no:cacheprovider` to avoid writing `.pytest_cache`
#   into the temp dir (keeps cleanup trivial and the test hermetic).
# - Uses `mktemp -d` for both the venv and the temp cwd; both are `trap`-cleaned
#   on `EXIT INT TERM` unless `KEEP_INSTALL=1`.
# - Exits non-zero on the first failure with a clear diagnostic block.
# - Runs under `set -euo pipefail`.
#
# Usage
# -----
#   ./scripts/verify_install.sh            # full verification
#
# Exit codes
# ----------
#   0  verification passed
#   1  a check failed (diagnostic printed to stderr)
#   2  usage error / prerequisites missing (python3, unzip, tar not found)
#
# Environment variables
# ---------------------
#   PYTHON_BIN     Interpreter used to create the venv and build the wheel.
#                  Default: python3.
#   KEEP_INSTALL   If set to "1", the temp venv and temp cwd are NOT cleaned
#                  up on exit. Useful for debugging a failed verification.
#   INSTALL_DIR    If set, use this directory for the venv instead of a fresh
#                  mktemp dir. Useful for reproducibility.
#   CWD_DIR        If set, use this directory for the temp cwd instead of a
#                  fresh mktemp dir.
# =============================================================================

set -euo pipefail

# -----------------------------------------------------------------------------
# Configuration
# -----------------------------------------------------------------------------
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
PYTHON_BIN="${PYTHON_BIN:-python3}"
KEEP_INSTALL="${KEEP_INSTALL:-0}"

# Fresh temp dirs for the venv and the cwd. Both are trap-cleaned.
if [[ -n "${INSTALL_DIR:-}" ]]; then
    VENV_DIR="${INSTALL_DIR}"
    mkdir -p "${VENV_DIR}"
else
    VENV_DIR="$(mktemp -d "${TMPDIR:-/tmp}/forgeqa-verify-install-venv.XXXXXX")"
fi

if [[ -n "${CWD_DIR:-}" ]]; then
    WORK_CWD="${CWD_DIR}"
    mkdir -p "${WORK_CWD}"
else
    WORK_CWD="$(mktemp -d "${TMPDIR:-/tmp}/forgeqa-verify-install-cwd.XXXXXX")"
fi

# Wheel is built into its own temp dir, so the verifier inspects the wheel
# it just built — not a stale `dist/` artifact from a prior run.
WHEEL_DIR="$(mktemp -d "${TMPDIR:-/tmp}/forgeqa-verify-install-wheel.XXXXXX")"

# -----------------------------------------------------------------------------
# Helpers
# -----------------------------------------------------------------------------
# All diagnostics go to stderr. stdout is reserved for data. Same invariant
# as scripts/verify_build.sh and scripts/verify_deps.sh.
log()   { printf '\n\033[1m==> %s\033[0m\n' "$*" >&2; }
info()  { printf '    %s\n' "$*" >&2; }
pass()  { printf '    \033[32mPASS\033[0m\n' >&2; }
fail()  {
    printf '\n\033[31m[FAIL]\033[0m %s\n' "$*" >&2
    exit 1
}

require_command() {
    command -v "$1" >/dev/null 2>&1 || fail "Required command not found: $1"
}

require_python() {
    command -v "${PYTHON_BIN}" >/dev/null 2>&1 \
        || fail "Python interpreter not found: ${PYTHON_BIN}. Set PYTHON_BIN to a valid path."
    "${PYTHON_BIN}" -c 'import sys; assert sys.version_info >= (3, 11), sys.version' \
        || fail "${PYTHON_BIN} is not Python >= 3.11."
}

# Run a command in a subprocess with PYTHONPATH explicitly cleared. Even
# though a fresh venv has no `.pth` pointing at src/, a developer's shell
# could be exporting PYTHONPATH; clear it defensively.
run_clean() {
    env -u PYTHONPATH -u PYTHONHOME -u PYTHONSTARTUP "$@"
}

# Extract the version from the wheel's METADATA. Uses Python's stdlib
# `zipfile` module, which is present in the venv we just created; the
# interpreter used here is the venv's, not the system one, so the check
# runs in the same Python as the installed package.
wheel_version() {
    local wheel_path="$1"
    local python="$2"
    "${python}" - "${wheel_path}" <<'PY'
import sys
import zipfile

wheel = sys.argv[1]
with zipfile.ZipFile(wheel) as zf:
    meta_name = next(
        name for name in zf.namelist()
        if name.endswith(".dist-info/METADATA")
    )
    text = zf.read(meta_name).decode("utf-8")
for line in text.splitlines():
    if line.startswith("Version:"):
        print(line.split(":", 1)[1].strip())
        break
else:
    sys.exit("Version field not found in METADATA")
PY
}

# -----------------------------------------------------------------------------
# Cleanup
# -----------------------------------------------------------------------------
cleanup() {
    local rc=$?
    if [[ "${KEEP_INSTALL}" != "1" ]]; then
        rm -rf "${VENV_DIR}" "${WORK_CWD}" "${WHEEL_DIR}" 2>/dev/null || true
    else
        info "KEEP_INSTALL=1: leaving artifacts under:"
        info "  venv:  ${VENV_DIR}"
        info "  cwd:   ${WORK_CWD}"
        info "  wheel: ${WHEEL_DIR}"
    fi
    exit "${rc}"
}
trap cleanup EXIT INT TERM

# -----------------------------------------------------------------------------
# Main
# -----------------------------------------------------------------------------
main() {
    require_command find
    require_command mktemp
    require_python

    # 1. Build the wheel into a fresh temp dir.
    log "Building wheel into ${WHEEL_DIR}"
    ( cd "${REPO_ROOT}" \
        && "${PYTHON_BIN}" -m build --wheel --outdir "${WHEEL_DIR}" >/dev/null )
    local wheel
    wheel="$(find "${WHEEL_DIR}" -maxdepth 1 -name 'forgeqa-*.whl' -print -quit)"
    [[ -n "${wheel}" ]] || fail "Wheel build produced no artifact in ${WHEEL_DIR}."
    info "Built: $(basename "${wheel}")"

    # 2. Create a fresh venv under /tmp. This is the core of the contract:
    #    a venv that has *never* seen `pip install -e .` and has no
    #    `src/` on `sys.path`.
    log "Creating fresh venv at ${VENV_DIR}"
    "${PYTHON_BIN}" -m venv "${VENV_DIR}"
    local py="${VENV_DIR}/bin/python"
    [[ -x "${py}" ]] || fail "venv python not found at ${py}."

    # 3. Install the wheel. `--no-deps` would skip installing forgeqa's
    #    *dependencies*, which would make `import forgeqa` fail (the
    #    package imports `pydantic` transitively via its settings module in
    #    Phase 1). Install with dependencies: this is what a consumer does.
    log "Installing wheel into venv"
    run_clean "${py}" -m pip install --quiet --disable-pip-version-check \
        --no-cache-dir "${wheel}"
    info "Installed: $(basename "${wheel}")"

    # 4. Assert import succeeds and version matches the wheel's METADATA.
    #    A mismatch means the venv is not the one we installed into (or an
    #    editable install leaked in via a `sitecustomize`/`.pth` we did not
    #    anticipate). The wheel's METADATA is the authoritative source; the
    #    runtime `__version__` (from `importlib.metadata.version`) must agree.
    log "Asserting import and version"
    local wheel_ver runtime_ver
    wheel_ver="$(wheel_version "${wheel}" "${py}")"
    [[ -n "${wheel_ver}" ]] || fail "Could not read Version from wheel METADATA."
    runtime_ver="$(run_clean "${py}" -c 'import forgeqa; print(forgeqa.__version__)')"
    [[ -n "${runtime_ver}" ]] || fail "import forgeqa produced no __version__."
    [[ "${runtime_ver}" == "${wheel_ver}" ]] \
        || fail "Version mismatch: wheel=${wheel_ver} runtime=${runtime_ver}. A stale editable install is probably shadowing the wheel."
    info "Version: ${runtime_ver} (matches wheel METADATA)"
    pass

    # 5. Assert forgeqa is imported from *outside* the source tree. The
    #    install location must be under the venv's site-packages, not under
    #    ${REPO_ROOT}/src. This is the WBS acceptance criterion
    #    "package is importable without the repo being on PYTHONPATH".
    log "Asserting import path is outside the source checkout"
    local import_path
    import_path="$(run_clean "${py}" -c 'import forgeqa; print(forgeqa.__file__)')"
    [[ -n "${import_path}" ]] || fail "forgeqa.__file__ is empty."
    # The venv's site-packages path; check that the resolved path is under it.
    local site_packages
    site_packages="$(run_clean "${py}" -c 'import sysconfig; print(sysconfig.get_paths()["purelib"])')"
    [[ -n "${site_packages}" ]] || fail "Could not resolve site-packages path."
    case "${import_path}" in
        "${site_packages}"/*) : ;;  # OK
        *) fail "forgeqa.__file__ is not under the venv's site-packages.
  file:          ${import_path}
  site-packages: ${site_packages}
  This means the package is not installed from the wheel. Common causes:
    - PYTHONPATH is set in the calling shell.
    - A .pth file in site-packages points at ${REPO_ROOT}/src.
    - The wheel install silently failed." ;;
    esac
    info "forgeqa.__file__: ${import_path}"
    pass

    # 6. Assert `pytest` from a temp cwd discovers the installed package.
    #    Create a minimal test file that imports forgeqa and asserts its
    #    version; run pytest from the temp cwd. If the source tree were
    #    accidentally on `sys.path`, pytest would collect against the
    #    installed package either way, but the test's `sys.path` sanity
    #    check (below) would fail because `src/` would be visible.
    log "Running pytest from a temporary working directory"
    cat > "${WORK_CWD}/test_installed.py" <<'PY'
"""Smoke test: the installed forgeqa is usable from a clean directory.

This file is created by scripts/verify_install.sh in a temporary directory
and run with pytest. It asserts that:

* ``import forgeqa`` succeeds (proves the package is installed).
* ``forgeqa.__version__`` is a non-empty string (proves the wheel's metadata
  is intact and ``importlib.metadata`` can resolve the distribution).
* ``forgeqa.__file__`` points at the installed location, not at a ``src/``
  directory in the current working tree (proves the source tree is not
  shadowing the install).
"""

from __future__ import annotations

import sys
from pathlib import Path

import forgeqa


def test_import() -> None:
    """Importing the installed forgeqa succeeds."""
    assert forgeqa is not None


def test_version() -> None:
    """forgeqa.__version__ is a non-empty string."""
    assert isinstance(forgeqa.__version__, str)
    assert forgeqa.__version__


def test_not_imported_from_src() -> None:
    """forgeqa is imported from site-packages, not from a sibling src/ tree.

    If ``sys.path`` contains a directory whose ``forgeqa/`` subdirectory is
    the *source* tree, ``forgeqa.__file__`` would be under that directory,
    not under ``site-packages``. This test guards against the "temporary
    working directory happens to be inside the source tree" failure mode.
    """
    package_file = Path(forgeqa.__file__).resolve()
    # site-packages is where pip installs wheels; a src/ tree would be under
    # the repo root, not under site-packages.
    assert "site-packages" in package_file.parts, (
        f"forgeqa imported from {package_file}; expected it under site-packages"
    )
    # And nothing on sys.path should be the source tree.
    for entry in sys.path:
        if not entry:
            continue
        candidate = Path(entry).resolve()
        if candidate.name == "src" and (candidate / "forgeqa").is_dir():
            raise AssertionError(
                f"sys.path contains a source-tree 'src' directory: {candidate}"
            )
PY
    ( cd "${WORK_CWD}" \
        && run_clean "${py}" -m pytest -q -p no:cacheprovider test_installed.py )
    pass

    log "All clean-install checks passed"
}

main "$@"
