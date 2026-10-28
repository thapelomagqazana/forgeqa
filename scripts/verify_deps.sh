#!/usr/bin/env bash
# =============================================================================
# ForgeQA - Verify optional dependency groups
# =============================================================================
#
# Purpose
# -------
# Prove, in isolated virtual environments, that the four extras declared in
# pyproject.toml behave exactly as documented:
#
#   1. `pip install forgeqa`          -> NO  playwright, NO  httpx
#   2. `pip install forgeqa[ui]`      -> YES playwright, NO  httpx
#   3. `pip install forgeqa[api]`     -> NO  playwright, YES httpx
#   4. `pip install forgeqa[all]`     -> YES playwright, YES httpx
#   5. `pip install forgeqa[dev]`     -> NO  playwright, NO  httpx (tooling only)
#
# This is the executable form of WBS 1.1.3's acceptance criteria. It is run
# in CI (see .github/workflows/quality.yml) and locally via `make verify-deps`.
#
# Why real venvs and not `pip install --dry-run`
# ----------------------------------------------
# `--dry-run` reports what pip would install but does not verify that the
# resulting environment imports cleanly, nor that the wheel installs
# successfully end-to-end. A real venv catches:
#   - Metadata errors that only surface on install
#   - Transitive dependency leaks (e.g. a runtime dep that itself pulls in
#     httpx)
#   - Name-shadowing issues (an editable install of forgeqa on the parent
#     PATH masking the wheel-installed copy)
# Isolation is also the only way to prove "core does not install playwright"
# without uninstalling it from the developer's environment.
#
# Design choices
# --------------
# - Builds a wheel from local source, installs from that wheel (not
#   `pip install -e .`). Editable installs use a different metadata path and
#   do not prove the wheel is self-contained. A PyPI consumer installs a
#   wheel; the verifier must too.
# - Each scenario gets a fresh venv, deleted on exit (trap), so scenarios
#   cannot leak into each other.
# - Uses `python -m pip` (not bare `pip`) to avoid PATH ambiguity when a venv
#   is active in the parent shell.
# - Diagnostic output (log, info, pass) is written to **stderr**, so that a
#   future `$(run_* ...)` capture sees only data. This is the standard shell
#   rule: stdout is data, stderr is diagnostics.
# - `make_venv` is invoked inside `$(...)`; its exit status is checked in
#   the caller so a `fail` inside the subshell stops the script rather than
#   leaving the caller with an empty `${py}` path.
# - Exits non-zero on the first failure with a clear diagnostic block.
# - Runs under `set -euo pipefail` so a mid-script failure cannot leave a
#   half-built state.
#
# Usage
# -----
#   ./scripts/verify_deps.sh                 # all scenarios
#   ./scripts/verify_deps.sh core            # only the "no optional deps" scenario
#   ./scripts/verify_deps.sh ui api          # only the ui and api scenarios
#   PYTHON_BIN=python3.12 ./scripts/verify_deps.sh
#
# Exit codes
# ----------
#   0  all requested scenarios passed
#   1  a scenario failed (diagnostic printed to stderr)
#   2  usage error / prerequisites missing (python3 not found, etc.)
#
# Environment variables
# ---------------------
#   PYTHON_BIN   Interpreter used to create venvs and build the wheel.
#                Default: python3.
#   KEEP_VENVS   If set to "1", temporary venvs are NOT cleaned up on exit.
#                Useful for debugging a failed scenario.
#   VENV_BASE    Directory under which temp venvs are created.
#                Default: a mktemp directory. Override for reproducibility.
# =============================================================================

set -euo pipefail

# -----------------------------------------------------------------------------
# Configuration
# -----------------------------------------------------------------------------
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
DIST_DIR="${REPO_ROOT}/dist"
PYTHON_BIN="${PYTHON_BIN:-python3}"
KEEP_VENVS="${KEEP_VENVS:-0}"

# Base directory for temporary venvs. Prefer $VENV_BASE (set by caller), else
# mktemp -d for a unique path per invocation (safe under parallel CI runs).
if [[ -n "${VENV_BASE:-}" ]]; then
    VENV_ROOT="${VENV_BASE}"
    mkdir -p "${VENV_ROOT}"
else
    VENV_ROOT="$(mktemp -d "${TMPDIR:-/tmp}/forgeqa-verify-deps.XXXXXX")"
fi

# Scenarios in run order. "core" runs first so that if it fails the rest are
# skipped — a broken core install makes the extras meaningless.
ALL_SCENARIOS=(core ui api all dev)

# -----------------------------------------------------------------------------
# Helpers
# -----------------------------------------------------------------------------
# All diagnostics go to stderr (>&2). stdout is reserved for data that the
# caller captures with $(...). Mixing the two is a well-known shell bug:
# a future `results="$(run_core ...)"` would otherwise capture the progress
# lines along with the exit status, and parse the wrong content.
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

# Create a throwaway venv at the given path. Echoes the venv's python path
# on stdout (data); all diagnostics go to stderr.
#
# IMPORTANT: called as `py="$(make_venv ...)"`, so:
#   - stdout must contain **only** the python path (no diagnostics)
#   - a `fail` inside this function exits the subshell only, not the parent;
#     callers must check the subshell's exit code (see `make_venv_or_fail`).
make_venv() {
    local path="$1"
    rm -rf "${path}"
    "${PYTHON_BIN}" -m venv "${path}" >/dev/null
    printf '%s\n' "${path}/bin/python"
}

# Wrapper around make_venv that checks the subshell's exit code and fails
# loudly in the parent if the venv could not be created. Use this instead
# of `py="$(make_venv ...)"` everywhere — it is the only correct way to
# call make_venv without inheriting the "exit inside $(...) exits the
# subshell only" trap.
make_venv_or_fail() {
    local path="$1"
    local py
    if ! py="$(make_venv "${path}")"; then
        fail "Failed to create venv at ${path}."
    fi
    if [[ -z "${py}" ]]; then
        fail "make_venv returned an empty python path for ${path}."
    fi
    printf '%s\n' "${py}"
}

# Install a wheel from ${DIST_DIR} into the given venv with the given extras
# spec (empty string = bare install). Also installs `packaging` for the
# optional semantic version comparison at the end of each scenario.
#
# Arguments:
#   $1  venv python path
#   $2  extras spec, e.g. "", "[ui]", "[api]", "[all]", "[dev]"
#   $3  wheel path (determined once in main())
install_wheel() {
    local python="$1"
    local extras="$2"
    local wheel="$3"

    # --no-cache-dir: fresh resolution every run; no stale cache masking a
    #                 dependency change. Slightly slower, much safer.
    # --disable-pip-version-check: suppress "new pip available" noise in CI.
    "${python}" -m pip install --quiet --disable-pip-version-check \
        --no-cache-dir "${wheel}${extras}" packaging
}

# Assert that a module is importable in the given venv (exit 1 if not).
assert_installed() {
    local python="$1"
    local module="$2"
    if ! "${python}" -c "import ${module}" >/dev/null 2>&1; then
        fail "Expected module '${module}' to be installed, but import failed."
    fi
}

# Assert that a module is NOT importable in the given venv (exit 1 if it is).
assert_not_installed() {
    local python="$1"
    local module="$2"
    if "${python}" -c "import ${module}" >/dev/null 2>&1; then
        fail "Expected module '${module}' to be absent, but it was importable."
    fi
}

# Assert forgeqa itself imports and __version__ is a non-empty string.
assert_forgeqa_sane() {
    local python="$1"
    "${python}" - <<'PY' || fail "forgeqa sanity check failed"
import sys
import forgeqa
assert isinstance(forgeqa.__version__, str) and forgeqa.__version__, (
    f"forgeqa.__version__ is not a non-empty string: {forgeqa.__version__!r}"
)
sys.exit(0)
PY
}

# -----------------------------------------------------------------------------
# Scenario runners
# -----------------------------------------------------------------------------
run_core() {
    log "Scenario: core install (no extras) — expect: no playwright, no httpx"
    local py wheel
    wheel="$1"
    py="$(make_venv_or_fail "${VENV_ROOT}/core")"
    install_wheel "${py}" "" "${wheel}"
    assert_not_installed "${py}" "playwright"
    assert_not_installed "${py}" "httpx"
    # Sanity: the wheel itself is functional and version is queryable.
    assert_forgeqa_sane "${py}"
    pass
}

run_ui() {
    log "Scenario: forgeqa[ui] — expect: playwright installed, httpx absent"
    local py wheel
    wheel="$1"
    py="$(make_venv_or_fail "${VENV_ROOT}/ui")"
    install_wheel "${py}" "[ui]" "${wheel}"
    assert_installed "${py}" "playwright"
    assert_not_installed "${py}" "httpx"
    # Sanity: the declared extra does not accidentally break forgeqa itself.
    assert_forgeqa_sane "${py}"
    pass
}

run_api() {
    log "Scenario: forgeqa[api] — expect: httpx installed, playwright absent"
    local py wheel
    wheel="$1"
    py="$(make_venv_or_fail "${VENV_ROOT}/api")"
    install_wheel "${py}" "[api]" "${wheel}"
    assert_installed "${py}" "httpx"
    assert_not_installed "${py}" "playwright"
    assert_forgeqa_sane "${py}"
    pass
}

run_all() {
    log "Scenario: forgeqa[all] — expect: playwright and httpx both installed"
    local py wheel
    wheel="$1"
    py="$(make_venv_or_fail "${VENV_ROOT}/all")"
    install_wheel "${py}" "[all]" "${wheel}"
    assert_installed "${py}" "playwright"
    assert_installed "${py}" "httpx"
    assert_forgeqa_sane "${py}"
    pass
}

run_dev() {
    log "Scenario: forgeqa[dev] — expect: neither playwright nor httpx (dev is tooling only)"
    local py wheel
    wheel="$1"
    py="$(make_venv_or_fail "${VENV_ROOT}/dev")"
    install_wheel "${py}" "[dev]" "${wheel}"
    assert_not_installed "${py}" "playwright"
    assert_not_installed "${py}" "httpx"
    # Sanity: dev tooling is importable. If `ruff` isn't installed, the
    # [dev] group is broken (this catches an accidental removal).
    "${py}" -c "import ruff" 2>/dev/null \
        || fail "Expected ruff to be importable in [dev] scenario."
    "${py}" -c "import mypy" 2>/dev/null \
        || fail "Expected mypy to be importable in [dev] scenario."
    assert_forgeqa_sane "${py}"
    pass
}

# -----------------------------------------------------------------------------
# Cleanup
# -----------------------------------------------------------------------------
cleanup() {
    local rc=$?
    if [[ "${KEEP_VENVS}" != "1" ]]; then
        rm -rf "${VENV_ROOT}" 2>/dev/null || true
    else
        info "KEEP_VENVS=1: leaving venvs under ${VENV_ROOT}"
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

    log "Building wheel from local source"
    ( cd "${REPO_ROOT}" \
        && "${PYTHON_BIN}" -m build --wheel --outdir "${DIST_DIR}" >/dev/null )
    local wheel
    wheel="$(find "${DIST_DIR}" -maxdepth 1 -name 'forgeqa-*.whl' -print -quit)"
    [[ -n "${wheel}" ]] || fail "Wheel build produced no artifact in ${DIST_DIR}."
    info "Built: ${wheel}"

    # Parse scenarios. No args = all scenarios in canonical order.
    local -a scenarios
    if [[ "$#" -eq 0 ]]; then
        scenarios=("${ALL_SCENARIOS[@]}")
    else
        scenarios=("$@")
    fi

    # Validate scenario names before running any of them. A typo would
    # otherwise surface as a run_<typo> command-not-found error after the
    # expensive wheel build.
    local s
    for s in "${scenarios[@]}"; do
        local known=0
        for k in "${ALL_SCENARIOS[@]}"; do
            [[ "${s}" == "${k}" ]] && { known=1; break; }
        done
        [[ "${known}" == "1" ]] \
            || fail "Unknown scenario: '${s}'. Valid: ${ALL_SCENARIOS[*]}"
    done

    # Run scenarios in the order provided (so `./verify_deps.sh api ui`
    # runs api first; a user debugging [ui] after fixing [api] controls
    # the order).
    for s in "${scenarios[@]}"; do
        "run_${s}" "${wheel}"
    done

    log "All requested scenarios passed: ${scenarios[*]}"
}

main "$@"
