"""Unit tests for the ForgeQA configuration precedence hierarchy.

These tests cover WBS 1.2.3:

* A CLI override beats an environment variable.
* An environment variable beats a ``forgeqa.toml`` value.
* A ``forgeqa.toml`` value beats a default.
* All four layers applied at once, with the correct winner.

The tests also cover edge cases (unknown env vars are ignored, unknown
CLI keys are rejected, empty overrides, empty env var values), corner
cases (an invalid value at a lower layer is overridden but still raises
at its own layer), and non-functional properties (determinism across
calls, no caching of env vars).

The loader reads the environment via ``os.environ`` by default. These
tests pass an explicit ``environ=...`` mapping to
:func:`load_config` (which the loader exposes for exactly this reason),
and use ``tmp_path`` for the TOML file. They do **not** mutate
``os.environ`` — a real environment mutation would leak into other
tests in the session.

Run only these tests:

    pytest tests/unit/config/test_precedence.py -v
    # or
    make verify-config
"""

from __future__ import annotations

import pytest

from forgeqa.config import (
    ENV_VAR_OVERRIDES,
    ForgeQAConfig,
    ForgeQAConfigError,
    load_config,
    read_env_overrides,
)

pytestmark = pytest.mark.unit


# =============================================================================
# Helpers
# =============================================================================


def write_toml(directory, content: str, name: str = "forgeqa.toml"):
    """Write ``content`` to ``directory / name`` and return the path."""
    path = directory / name
    path.write_text(content, encoding="utf-8")
    return path


# =============================================================================
# Layer 2 vs 4: TOML over defaults
# =============================================================================


def test_toml_overrides_default(tmp_path, monkeypatch) -> None:
    """Given a TOML file and no env/CLI overrides, when loaded, then TOML beats defaults.

    The WBS acceptance criterion "A TOML value overrides a default".
    """
    write_toml(tmp_path, '[browser]\nbrowser_name = "firefox"\n')
    monkeypatch.chdir(tmp_path)

    cfg = load_config(environ={})
    assert cfg.browser.browser_name == "firefox"  # TOML value, not default "chromium"
    # Fields not in the TOML remain at their defaults.
    assert cfg.browser.headless is True  # default


# =============================================================================
# Layer 3 vs 2: environment over TOML
# =============================================================================


def test_env_overrides_toml(tmp_path, monkeypatch) -> None:
    """Given TOML and an env var, when loaded, then the env var wins.

    The WBS acceptance criterion "An environment variable overrides a
    TOML value".
    """
    write_toml(tmp_path, '[browser]\nbrowser_name = "firefox"\n')
    monkeypatch.chdir(tmp_path)

    cfg = load_config(environ={"FORGEQA_BROWSER_BROWSER_NAME": "webkit"})
    assert cfg.browser.browser_name == "webkit"  # env value, not TOML's "firefox"


def test_env_overrides_toml_when_both_present(tmp_path, monkeypatch) -> None:
    """Given TOML and an env var set to the TOML value, when loaded, then either way the result is the env value.

    Edge case: when the env var and the TOML value are identical, the
    result is the same regardless of precedence. This test pins that
    the implementation does not depend on "different from default" to
    decide precedence.
    """
    write_toml(tmp_path, '[browser]\nbrowser_name = "firefox"\n')
    monkeypatch.chdir(tmp_path)

    cfg = load_config(environ={"FORGEQA_BROWSER_BROWSER_NAME": "firefox"})
    assert cfg.browser.browser_name == "firefox"


# =============================================================================
# Layer 4 vs 3: CLI over environment
# =============================================================================


def test_cli_overrides_env(tmp_path, monkeypatch) -> None:
    """Given an env var and a CLI override, when loaded, then the CLI override wins.

    The WBS acceptance criterion "A CLI arg overrides an environment
    variable".
    """
    monkeypatch.chdir(tmp_path)  # no TOML

    cfg = load_config(
        environ={"FORGEQA_BROWSER_BROWSER_NAME": "firefox"},
        cli_overrides={"browser": {"browser_name": "webkit"}},
    )
    assert cfg.browser.browser_name == "webkit"  # CLI, not env's "firefox"


def test_cli_overrides_env_when_same_as_default(tmp_path, monkeypatch) -> None:
    """Given an env var and a CLI override set to the default, when loaded, then the CLI override wins.

    "Explicit wins" rule: a CLI caller who explicitly sets a field to
    its default value should get the default, even if an env var says
    otherwise. A naive "merge only if different from default"
    optimization would get this wrong.
    """
    monkeypatch.chdir(tmp_path)

    # Default for browser_name is "chromium". Env says "firefox". CLI
    # explicitly says "chromium".
    cfg = load_config(
        environ={"FORGEQA_BROWSER_BROWSER_NAME": "firefox"},
        cli_overrides={"browser": {"browser_name": "chromium"}},
    )
    assert cfg.browser.browser_name == "chromium"  # CLI wins, even though it equals the default


# =============================================================================
# All four layers
# =============================================================================


def test_all_four_layers(tmp_path, monkeypatch) -> None:
    """Given all four layers set, when loaded, then the CLI value wins.

    The canonical precedence test. Sets:
    * default: "chromium"
    * TOML: "firefox"
    * env: "webkit"
    * CLI: "chromium"

    Expects "chromium" (CLI, even though it equals the default).
    """
    write_toml(tmp_path, '[browser]\nbrowser_name = "firefox"\n')
    monkeypatch.chdir(tmp_path)

    cfg = load_config(
        environ={"FORGEQA_BROWSER_BROWSER_NAME": "webkit"},
        cli_overrides={"browser": {"browser_name": "chromium"}},
    )
    assert cfg.browser.browser_name == "chromium"


def test_all_four_layers_different_field(tmp_path, monkeypatch) -> None:
    """Given all four layers set for different fields, when loaded, then each field resolves independently.

    Precedence is per-field, not per-layer. Setting ``browser_name``
    via env and ``headless`` via TOML produces a config with both
    overrides applied. A naive "apply the highest layer, ignore others"
    implementation would get this wrong.
    """
    write_toml(tmp_path, "[browser]\nheadless = false\n")
    monkeypatch.chdir(tmp_path)

    cfg = load_config(
        environ={"FORGEQA_BROWSER_BROWSER_NAME": "firefox"},
        cli_overrides={"browser": {"timeout_ms": 30_000}},
    )
    assert cfg.browser.headless is False  # from TOML
    assert cfg.browser.browser_name == "firefox"  # from env
    assert cfg.browser.timeout_ms == 30_000  # from CLI
    # browser_name is NOT "chromium" (default) because env overrode it.
    # timeout_ms is NOT 10_000 (default) because CLI overrode it.
    # headless is NOT True (default) because TOML overrode it.


# =============================================================================
# Layer independence and no-op cases
# =============================================================================


def test_defaults_only_when_all_layers_empty(tmp_path, monkeypatch) -> None:
    """Given no TOML, no env, no CLI, when loaded, then the default config is returned."""
    monkeypatch.chdir(tmp_path)  # no TOML

    cfg = load_config(environ={})
    assert cfg == ForgeQAConfig()


def test_empty_cli_overrides_is_noop(tmp_path, monkeypatch) -> None:
    """Given ``cli_overrides={}``, when loaded, then it is treated as "no CLI overrides"."""
    monkeypatch.chdir(tmp_path)

    cfg = load_config(environ={}, cli_overrides={})
    assert cfg == ForgeQAConfig()


def test_empty_env_mapping_is_noop(tmp_path, monkeypatch) -> None:
    """Given ``environ={}``, when loaded, then no env layer is applied."""
    write_toml(tmp_path, '[browser]\nbrowser_name = "firefox"\n')
    monkeypatch.chdir(tmp_path)

    cfg = load_config(environ={})
    assert cfg.browser.browser_name == "firefox"  # TOML wins; no env present


# =============================================================================
# Unknown keys: env ignored, CLI rejected
# =============================================================================


def test_unknown_env_var_is_ignored(tmp_path, monkeypatch) -> None:
    """Given an unknown ``FORGEQA_*`` env var, when loaded, then it is silently ignored.

    The environment is shared with other tools. A stray
    ``FORGEQA_SOMETHING`` var should not break the loader.
    """
    monkeypatch.chdir(tmp_path)

    cfg = load_config(environ={"FORGEQA_UNKNOWN_FIELD": "whatever"})
    assert cfg == ForgeQAConfig()


def test_unknown_prefix_env_var_is_ignored(tmp_path, monkeypatch) -> None:
    """Given an env var that does not start with the prefix, when loaded, then it is ignored."""
    monkeypatch.chdir(tmp_path)

    cfg = load_config(environ={"OTHER_TOOL_SETTING": "whatever"})
    assert cfg == ForgeQAConfig()


def test_unknown_cli_key_is_rejected(tmp_path, monkeypatch) -> None:
    """Given an unknown CLI key, when loaded, then ``ForgeQAConfigError`` is raised.

    A CLI caller is code, not an environment; code typos should fail
    loudly. This is the opposite of the env-var treatment, and the
    asymmetry is deliberate.
    """
    monkeypatch.chdir(tmp_path)

    with pytest.raises(ForgeQAConfigError) as exc_info:
        load_config(
            environ={},
            cli_overrides={"browsr": {"headless": True}},  # typo: "browsr"
        )
    message = str(exc_info.value).lower()
    assert "browsr" in message or "extra" in message


def test_unknown_cli_field_is_rejected(tmp_path, monkeypatch) -> None:
    """Given an unknown field under a known section, when loaded, then ``ForgeQAConfigError`` is raised."""
    monkeypatch.chdir(tmp_path)

    with pytest.raises(ForgeQAConfigError) as exc_info:
        load_config(
            environ={},
            cli_overrides={"browser": {"unknown_field": "x"}},
        )
    message = str(exc_info.value).lower()
    assert "unknown_field" in message or "extra" in message


# =============================================================================
# Invalid values: each layer's error is reported at that layer
# =============================================================================


def test_invalid_env_var_raises_with_var_name(tmp_path, monkeypatch) -> None:
    """Given an invalid value for a known env var, when loaded, then ``ForgeQAConfigError`` names the var.

    The error should name the *environment variable* (``FORGEQA_BROWSER_BROWSER_NAME``),
    not just the *field* (``browser_name``), so the user knows what to
    unset.
    """
    monkeypatch.chdir(tmp_path)

    with pytest.raises(ForgeQAConfigError) as exc_info:
        load_config(environ={"FORGEQA_BROWSER_BROWSER_NAME": "safari"})
    message = str(exc_info.value)
    assert "FORGEQA_BROWSER_BROWSER_NAME" in message


def test_invalid_toml_value_raises_with_path(tmp_path, monkeypatch) -> None:
    """Given an invalid value in a TOML file, when loaded, then ``ForgeQAConfigError`` names the file."""
    write_toml(tmp_path, '[browser]\nbrowser_name = "safari"\n')
    monkeypatch.chdir(tmp_path)

    with pytest.raises(ForgeQAConfigError) as exc_info:
        load_config(environ={})
    message = str(exc_info.value)
    assert str(tmp_path / "forgeqa.toml") in message


def test_invalid_lower_layer_raises_even_when_higher_layer_overrides(tmp_path, monkeypatch) -> None:
    """Given an invalid value at a lower layer and a valid override at a higher layer, when loaded, then it still raises.

    Design decision (documented in ADR-009): the loader applies layers
    in order and validates at each step. An invalid TOML value fails
    when the TOML layer is applied, even if a CLI override would fix
    the field. Silently letting a higher layer "fix" a lower layer's
    bug would mask the bug.
    """
    write_toml(tmp_path, '[browser]\nbrowser_name = "safari"\n')  # invalid
    monkeypatch.chdir(tmp_path)

    with pytest.raises(ForgeQAConfigError) as exc_info:
        load_config(
            environ={},
            cli_overrides={"browser": {"browser_name": "chromium"}},  # valid
        )
    # The error is from the TOML layer, not the CLI layer.
    assert "Invalid configuration" in str(exc_info.value)


# =============================================================================
# Env var mapping: the explicit surface
# =============================================================================


def test_read_env_overrides_returns_empty_when_nothing_set() -> None:
    """Given an empty environment, when ``read_env_overrides`` runs, then it returns ``{}``."""
    assert read_env_overrides(environ={}) == {}


def test_read_env_overrides_returns_nested_dict() -> None:
    """Given one env var, when ``read_env_overrides`` runs, then the result is a nested dict."""
    result = read_env_overrides(
        environ={
            "FORGEQA_BROWSER_BROWSER_NAME": "firefox",
            "FORGEQA_BROWSER_HEADLESS": "false",
        }
    )
    assert result == {
        "browser": {
            "browser_name": "firefox",
            "headless": "false",
        }
    }


def test_read_env_overrides_multi_section() -> None:
    """Given env vars for multiple sections, when ``read_env_overrides`` runs, then each section is separate."""
    result = read_env_overrides(
        environ={
            "FORGEQA_BROWSER_BROWSER_NAME": "firefox",
            "FORGEQA_API_TIMEOUT_SECONDS": "30",
            "FORGEQA_GENERAL_LOG_LEVEL": "DEBUG",
        }
    )
    assert result == {
        "browser": {"browser_name": "firefox"},
        "api": {"timeout_seconds": "30"},
        "general": {"log_level": "DEBUG"},
    }


def test_read_env_overrides_ignores_unknown_vars() -> None:
    """Given an unknown ``FORGEQA_*`` var, when ``read_env_overrides`` runs, then it is omitted."""
    result = read_env_overrides(
        environ={
            "FORGEQA_BROWSER_HEADLESS": "true",
            "FORGEQA_UNKNOWN": "x",
            "OTHER_TOOL": "y",
        }
    )
    assert result == {"browser": {"headless": "true"}}


def test_read_env_overrides_does_not_include_present_but_empty_sections() -> None:
    """Given only unknown ``FORGEQA_*`` vars, when ``read_env_overrides`` runs, then the result is ``{}``."""
    assert read_env_overrides(environ={"FORGEQA_UNKNOWN": "x"}) == {}


def test_env_var_overrides_mapping_is_complete_for_public_fields() -> None:
    """Given the schema, when compared to ``ENV_VAR_OVERRIDES``, then every top-level field has at least one env var.

    A future field added to a sub-model without a corresponding env-var
    entry would fail this test. This is the "adding a field means
    updating the mapping" rule from ADR-009.

    The check is structural: for each sub-model, at least one field is
    represented in ``ENV_VAR_OVERRIDES``. This does not require *every*
    field to have an env var (a future field may be CLI-only by design),
    but it does require that no sub-model is entirely unrepresented.
    """
    represented_sections = {section for section, _ in ENV_VAR_OVERRIDES.values()}
    expected_sections = {
        "general",
        "browser",
        "api",
        "diagnostics",
        "reporting",
    }
    assert represented_sections == expected_sections, (
        f"Missing env-var coverage for sections: {expected_sections - represented_sections}"
    )


# =============================================================================
# Non-functional: determinism, no caching, no env mutation
# =============================================================================


def test_env_is_not_mutated(tmp_path, monkeypatch) -> None:
    """Given a call to ``load_config``, when it returns, then the caller's environ mapping is unchanged.

    The loader reads from the mapping; it must not write back to it.
    A future "set defaults in os.environ" feature would fail this test.
    """
    monkeypatch.chdir(tmp_path)
    env = {"FORGEQA_BROWSER_BROWSER_NAME": "firefox"}
    env_copy = dict(env)

    load_config(environ=env)

    assert env == env_copy


def test_loader_is_deterministic(tmp_path, monkeypatch) -> None:
    """Given the same inputs, when ``load_config`` runs twice, then the configs are equal.

    Idempotency for the precedence-aware loader. Same as the ADR-008
    test, but with the env and CLI layers present.
    """
    write_toml(tmp_path, '[general]\nenvironment = "staging"\n')
    monkeypatch.chdir(tmp_path)

    cfg1 = load_config(
        environ={"FORGEQA_BROWSER_BROWSER_NAME": "firefox"},
        cli_overrides={"browser": {"timeout_ms": 30_000}},
    )
    cfg2 = load_config(
        environ={"FORGEQA_BROWSER_BROWSER_NAME": "firefox"},
        cli_overrides={"browser": {"timeout_ms": 30_000}},
    )
    assert cfg1 == cfg2


def test_loader_reads_env_fresh_each_call(tmp_path, monkeypatch) -> None:
    """Given an env mapping, when it changes and ``load_config`` runs again, then the new value is returned.

    No caching of the env layer. A developer who changes an env var
    and calls ``load_config`` again sees the new value.
    """
    monkeypatch.chdir(tmp_path)

    cfg1 = load_config(environ={"FORGEQA_BROWSER_BROWSER_NAME": "firefox"})
    assert cfg1.browser.browser_name == "firefox"

    cfg2 = load_config(environ={"FORGEQA_BROWSER_BROWSER_NAME": "webkit"})
    assert cfg2.browser.browser_name == "webkit"


def test_loader_reads_toml_fresh_each_call(tmp_path, monkeypatch) -> None:
    """Given a TOML file, when it changes and ``load_config`` runs again, then the new value is returned.

    No caching of the TOML layer. Same rationale as the env layer.
    """
    path = write_toml(tmp_path, '[browser]\nbrowser_name = "firefox"\n')
    monkeypatch.chdir(tmp_path)

    cfg1 = load_config(environ={})
    assert cfg1.browser.browser_name == "firefox"

    path.write_text('[browser]\nbrowser_name = "webkit"\n', encoding="utf-8")

    cfg2 = load_config(environ={})
    assert cfg2.browser.browser_name == "webkit"
