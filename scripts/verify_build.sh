#!/usr/bin/env bash
# =============================================================================
# ForgeQA - Verify built artifacts contain exactly the intended files
# =============================================================================
#
# Purpose
# -------
# Prove, from the built artifacts themselves, that:
#
#   1. `python -m build` produces both a wheel (.whl) and an sdist (.tar.gz).
#   2. The wheel contains `forgeqa/__init__.py` (the importable package).
#   3. The wheel contains the project LICENSE (bundled via
#      `[project].license = { file = "LICENSE" }`).
#   4. The wheel does NOT contain `tests/`, `docs/`, `examples/`, or
#      `scripts/` — those are source-repo-only.
#   5. The sdist contains the source tree, tests, and docs — so downstream
#      consumers can install from sdist and run the test suite offline.
#   6. The sdist does NOT contain build artifacts (dist/, build/,
#      *.egg-info/, .venv/).
#
# This is the executable form of WBS 1.1.4's acceptance criteria. It is
# run in CI (see .github/workflows/quality.yml) and locally via
# `make verify-build`.
#
# Why inspect the built artifact and not just `pyproject.toml`
# ------------------------------------------------------------
# The `[tool.hatch.build.targets.wheel]` config declares intent; the wheel
# is the *result*. Hatchling's defaults, VCS-aware file selection, and
# `.gitignore` rules can all subtly change what ends up in the archive.
# The only way to prove "the wheel does not contain tests/" is to open
# the wheel and look. This script does exactly that.
#
# Why both wheel and sdist
# ------------------------
# The wheel is what `pip install forgeqa` consumes from PyPI. The sdist is
# what `pip install forgeqa --no-binary :all:` consumes (and what some
# downstream packagers use). Both must be correct, and their contracts are
# *different*: the wheel ships only the package; the sdist ships the source
# tree so downstream can build and test. A single verifier covering both
# scenarios keeps the two contracts in one auditable place.
#
# Design choices
# --------------
# - Builds into a clean temp directory, not `dist/`, so the verifier
#   cannot accidentally inspect a stale artifact from a previous run.
# - Uses `unzip -l` for the wheel and `tar -tzf` for the sdist (portable,
#   present on every supported CI runner and dev machine). No Python
#   dependency, so the script also works in a bare shell.
# - Diagnostic output (log, info, pass) is written to **stderr**, so that
#   `$(build_artifacts)` captures only the two artifact paths on stdout.
#   This is the standard shell rule: stdout is data, stderr is diagnostics.
# - Exits non-zero on the first failure with a clear diagnostic block.
# - Runs under `set -euo pipefail` so a mid-script failure cannot leave a
#   half-built state.
# - `build_artifacts` is invoked inside `$(...)`; its exit code is checked
#   in `main()` so a failure inside the subshell stops the script (a bare
#   `exit` inside `$(...)` exits only the subshell, not the parent).
#
# Usage
# -----
#   ./scripts/verify_build.sh             # full verification
#   ./scripts/verify_build.sh wheel       # only the wheel checks
#   ./scripts/verify_build.sh sdist       # only the sdist checks
#
# Exit codes
# ----------
#   0  all requested checks passed
#   1  a check failed (diagnostic printed to stderr)
#   2  usage error / prerequisites missing (unzip, tar, python not found)
#
# Environment variables
# ---------------------
#   PYTHON_BIN   Interpreter used to build the wheel and sdist.
#                Default: python3.
#   KEEP_BUILD   If set to "1", the temp build directory is NOT cleaned up.
#                Useful for debugging a failed inspection.
#   BUILD_DIR    If set, use this directory for build artifacts instead of
#                a fresh mktemp directory. Useful for reproducibility.
# =============================================================================

set -euo pipefail

# -----------------------------------------------------------------------------
# Configuration
# -----------------------------------------------------------------------------
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
PYTHON_BIN="${PYTHON_BIN:-python3}"
KEEP_BUILD="${KEEP_BUILD:-0}"

# Build into a fresh temp directory. This guarantees the verifier inspects
# the artifact it just built, not a stale one from a prior run in `dist/`.
if [[ -n "${BUILD_DIR:-}" ]]; then
    WORK_DIR="${BUILD_DIR}"
    mkdir -p "${WORK_DIR}"
else
    WORK_DIR="$(mktemp -d "${TMPDIR:-/tmp}/forgeqa-verify-build.XXXXXX")"
fi

# Required and forbidden entries in the wheel. Pattern-matched against
# `unzip -l` output with `grep -E`. Kept as arrays so extending the
# contract (e.g. adding a new top-level package) is a one-line change.
WHEEL_REQUIRED=(
    "forgeqa/__init__.py"
    "forgeqa-.*\.dist-info/licenses/LICENSE"
    "forgeqa-.*\.dist-info/METADATA"
    "forgeqa-.*\.dist-info/WHEEL"
)
WHEEL_FORBIDDEN=(
    "(^|/)tests/"
    "(^|/)docs/"
    "(^|/)examples/"
    "(^|/)scripts/"
    "\.egg-info/"
    "__pycache__/"
    "\.pyc$"
)

# Required and forbidden entries in the sdist.
SDIST_REQUIRED=(
    "src/forgeqa/__init__.py"
    "tests/unit/"
    "docs/"
    "README\.md"
    "LICENSE"
    "pyproject\.toml"
)
SDIST_FORBIDDEN=(
    "(^|/)dist/"
    "(^|/)build/"
    "/\.venv/"
    "\.egg-info/"
    "__pycache__/"
    "\.pyc$"
)

# -----------------------------------------------------------------------------
# Helpers
# -----------------------------------------------------------------------------
# All diagnostics go to stderr (>&2). stdout is reserved for data that the
# caller captures with $(...). Mixing the two is a well-known shell bug:
# `artifacts="$(build_artifacts)"` would otherwise capture progress lines
# along with the paths, and `sed -n '1p'` would return the wrong line.
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
}

# Assert that a required pattern is present in the given text blob.
assert_contains() {
    local label="$1"
    local haystack="$2"
    local pattern="$3"
    if ! printf '%s\n' "${haystack}" | grep -Eq "${pattern}"; then
        fail "${label}: expected to find pattern /${pattern}/, but it was absent."
    fi
}

# Assert that a forbidden pattern is absent from the given text blob.
assert_absent() {
    local label="$1"
    local haystack="$2"
    local pattern="$3"
    if printf '%s\n' "${haystack}" | grep -Eq "${pattern}"; then
        fail "${label}: forbidden pattern /${pattern}/ was present. Matching lines:"
        printf '%s\n' "${haystack}" | grep -E "${pattern}" >&2
    fi
}

# -----------------------------------------------------------------------------
# Wheel checks
# -----------------------------------------------------------------------------
verify_wheel() {
    local wheel_path="$1"
    log "Verifying wheel: $(basename "${wheel_path}")"

    # `unzip -l` lists the archive contents; we search the output text.
    # This avoids extracting to disk (faster, safer, no temp dirs).
    local contents
    contents="$(unzip -l "${wheel_path}")"

    local p
    for p in "${WHEEL_REQUIRED[@]}"; do
        assert_contains "wheel" "${contents}" "${p}"
    done
    info "All required entries present (${#WHEEL_REQUIRED[@]})"

    for p in "${WHEEL_FORBIDDEN[@]}"; do
        assert_absent "wheel" "${contents}" "${p}"
    done
    info "No forbidden entries present (${#WHEEL_FORBIDDEN[@]})"

    pass
}

# -----------------------------------------------------------------------------
# sdist checks
# -----------------------------------------------------------------------------
verify_sdist() {
    local sdist_path="$1"
    log "Verifying sdist: $(basename "${sdist_path}")"

    # `tar -tzf` lists the archive contents. The sdist root is a single
    # directory `forgeqa-X.Y.Z/`; patterns are anchored to allow a
    # leading path component.
    local contents
    contents="$(tar -tzf "${sdist_path}")"

    local p
    for p in "${SDIST_REQUIRED[@]}"; do
        assert_contains "sdist" "${contents}" "${p}"
    done
    info "All required entries present (${#SDIST_REQUIRED[@]})"

    for p in "${SDIST_FORBIDDEN[@]}"; do
        assert_absent "sdist" "${contents}" "${p}"
    done
    info "No forbidden entries present (${#SDIST_FORBIDDEN[@]})"

    pass
}

# -----------------------------------------------------------------------------
# Build
# -----------------------------------------------------------------------------
# build_artifacts prints exactly two lines to stdout: the wheel path and
# the sdist path. All diagnostics go to stderr. `main()` captures stdout
# with `$(...)` and splits the two lines. If the build fails (or either
# artifact is missing), it exits non-zero — and `main()` checks the exit
# status because `exit` inside `$(...)` only exits the subshell.
build_artifacts() {
    log "Building wheel and sdist into ${WORK_DIR}"
    ( cd "${REPO_ROOT}" \
        && "${PYTHON_BIN}" -m build --outdir "${WORK_DIR}" >/dev/null )

    local wheel sdist
    wheel="$(find "${WORK_DIR}" -maxdepth 1 -name 'forgeqa-*.whl' -print -quit)"
    sdist="$(find "${WORK_DIR}" -maxdepth 1 -name 'forgeqa-*.tar.gz' -print -quit)"

    [[ -n "${wheel}" ]] || fail "Build produced no wheel in ${WORK_DIR}."
    [[ -n "${sdist}" ]] || fail "Build produced no sdist in ${WORK_DIR}."
    info "Wheel: $(basename "${wheel}")"
    info "sdist: $(basename "${sdist}")"

    printf '%s\n' "${wheel}"
    printf '%s\n' "${sdist}"
}

# -----------------------------------------------------------------------------
# Cleanup
# -----------------------------------------------------------------------------
cleanup() {
    local rc=$?
    if [[ "${KEEP_BUILD}" != "1" ]]; then
        rm -rf "${WORK_DIR}" 2>/dev/null || true
    else
        info "KEEP_BUILD=1: leaving build artifacts under ${WORK_DIR}"
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
    require_command unzip
    require_command tar
    require_python

    # Parse which checks to run. Default: both.
    local -a checks
    if [[ "$#" -eq 0 ]]; then
        checks=("wheel" "sdist")
    else
        checks=("$@")
        local c
        for c in "${checks[@]}"; do
            [[ "${c}" == "wheel" || "${c}" == "sdist" ]] \
                || fail "Unknown check: '${c}'. Valid: wheel sdist"
        done
    fi

    # Build both artifacts regardless of which checks run — the WBS
    # acceptance criterion is "python -m build produces both wheel and
    # sdist", which is itself a contract. If the build fails, fail early.
    #
    # `fail` inside `$(build_artifacts)` exits the subshell, not the parent,
    # so we must check the subshell's exit code here. Without this check,
    # a build failure would leave ${artifacts} empty, ${wheel} and ${sdist}
    # empty, and the verifier would proceed with a confusing `unzip` error
    # instead of stopping at the real failure.
    local artifacts wheel sdist
    if ! artifacts="$(build_artifacts)"; then
        fail "Build failed. See diagnostic above."
    fi
    wheel="$(printf '%s\n' "${artifacts}" | sed -n '1p')"
    sdist="$(printf '%s\n' "${artifacts}" | sed -n '2p')"

    # Defensive: build_artifacts should have printed exactly two lines, but
    # if a future edit adds a stray stdout write, fail loudly rather than
    # silently mis-parse.
    if [[ -z "${wheel}" || -z "${sdist}" ]]; then
        fail "Internal error: build_artifacts did not produce two artifact paths. Got: ${artifacts@Q}"
    fi

    for c in "${checks[@]}"; do
        case "${c}" in
            wheel) verify_wheel "${wheel}" ;;
            sdist) verify_sdist "${sdist}" ;;
        esac
    done

    log "All requested checks passed: ${checks[*]}"
}

main "$@"
