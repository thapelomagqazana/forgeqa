# ADR-009: Resolve configuration precedence as CLI args > environment variables > forgeqa.toml > defaults

> **Status**: Accepted
> **Date**: 2026-10-28
> **Deciders**: @thapelomagqazana
> **Consulted**: None
> **Informed**: None

## Context

WBS 1.2.3 requires that the configuration loader enforce a four-layer
precedence hierarchy:

1. **CLI args** (or Pytest args — the two are equivalent from the
   loader's perspective: both are "a dict the caller passes in").
2. **Environment variables** (e.g. ``FORGEQA_BASE_URL``).
3. **``forgeqa.toml``**.
4. **Defaults**.

The traceability KPI is "Configuration precedence is deterministic and
fully tested."

WBS 1.2.1 (ADR-007) established the schema. WBS 1.2.2 (ADR-008)
established the loader that reads ``forgeqa.toml`` and falls back to
defaults. This ADR extends the loader with the two higher layers.

The forces at play:

- **Determinism.** The same inputs must produce the same config. A
  precedence rule that is ambiguous ("sometimes env wins, sometimes
  CLI wins") is worse than no precedence rule. The four-layer order
  is fixed and documented.
- **Auditability.** A contributor adding a config field must decide
  whether the field is settable via env var, via CLI, via both, or
  via neither. The decision is explicit — recorded in the env-var
  mapping and in the CLI-override shape — not implicit in a generic
  parser.
- **Explicit is not silent.** A typo in a CLI override should fail
  loudly (the caller is code); a stray env var should be ignored
  silently (the environment is shared with other tools). The
  asymmetry is deliberate.
- **Backwards compatibility.** The 1.2.2 behaviour (TOML over
  defaults) must be preserved when no env vars are set and no CLI
  overrides are passed. Adding the precedence layer is a minor
  release of the config feature, not a major one.
- **Per-field, not per-layer.** A config where ``browser_name`` comes
  from env and ``headless`` comes from TOML is valid and common
  (e.g. in CI, ``FORGEQA_BROWSER_HEADLESS=false`` for a debug run
  while the rest comes from ``forgeqa.toml``). The precedence must be
  applied per field, not per layer.
- **Each layer's invalid value must fail at its own layer.** An
  invalid TOML value should not be silently "fixed" by a valid CLI
  override; the invalid value is a bug in the source, and letting a
  higher layer mask it hides the bug. This is the "layer attribution"
  property: the error message must name the layer that contributed
  the offending value.
- **Typed sub-models, not raw dicts.** The final
  ``ForgeQAConfig`` must have proper sub-model instances
  (``cfg.browser`` is a ``BrowserConfig``, not a ``dict``). Pydantic
  v2's ``model_copy(update=...)`` does **not** enforce this (see the
  design note under Decision).

## Decision

1. **The precedence order is fixed: CLI > env > TOML > defaults.**
   There is no configurable precedence order. A future feature that
   wants to flip env-over-CLI would be a semver-major breaking change
   and would need a new ADR.

2. **Each layer is validated independently, then the layers are
   merged, then the merged dict is constructed once.**

   The implementation is:

   ```python
   toml_data, toml_path = _read_toml(path)
   _validate_layer(toml_data, layer_name="TOML", toml_path=toml_path)

   env_data = read_env_overrides(environ)
   _validate_layer(env_data, layer_name="environment variable")

   cli_data = {section: dict(fields) for section, fields in (cli_overrides or {}).items()}
   _validate_layer(cli_data, layer_name="CLI override")

   merged: dict[str, dict[str, Any]] = {}
   for layer in (toml_data, env_data, cli_data):
       for section, fields in layer.items():
           merged.setdefault(section, {}).update(fields)

   return ForgeQAConfig(**merged)
   ```

   Why not apply each layer to an existing model via
   ``model_copy(update=...)``? **Pydantic v2's
   ``model_copy(update=...)`` does not validate, and does not
   construct sub-models from nested dicts.** Assigning
   ``{"browser": {"browser_name": "firefox"}}`` via
   ``model_copy(update=...)`` sets ``config.browser`` to the raw
   ``dict``, not to a ``BrowserConfig`` instance, and every
   ``cfg.browser.<attr>`` access then fails with
   ``AttributeError: 'dict' object has no attribute '<attr>'``.
   Constructing ``ForgeQAConfig(**layer_dict)`` (which validates and
   constructs sub-models) fixes both problems: it gives typed
   sub-model instances and it catches invalid values at their own
   layer.

   The final ``ForgeQAConfig(**merged)`` is what produces the
   fully-typed config the consumer receives. Because each layer was
   individually valid, the merged dict is also valid — the merge only
   replaces a field's value with a value from a layer that was
   itself valid.

3. **Per-layer validation preserves the "fail at your own layer"
   property.** An invalid TOML value fails during ``_validate_layer``
   on the TOML dict, before the env and CLI layers are applied. Even
   if a valid CLI override would later overwrite the field, the TOML
   error has already been raised. This is the property the tests pin
   (``test_invalid_lower_layer_raises_even_when_higher_layer_overrides``).

4. **Env vars are `FORGEQA_`-prefixed with an explicit mapping.**
   :data:`forgeqa.config.env.ENV_VAR_OVERRIDES` maps each supported
   env var name to a ``(section, field)`` pair. Adding a new env var
   requires editing the mapping (and its test). A generic
   ``FORGEQA_<anything>`` parser was rejected (see Alternatives).

5. **Unknown `FORGEQA_*` env vars are silently ignored.** The
   environment is shared with other tools; a stray var should not
   break the loader. Precedent: Django, Rails, Pydantic Settings.

6. **Unknown CLI-override keys are rejected.** A CLI caller is code,
   not an environment. A typo should fail loudly. The mechanism is
   ``ForgeQAConfig(**cli_dict)`` (via ``_validate_layer``), whose
   ``extra="forbid"`` rejects unknown keys; the error is re-raised
   as ``ForgeQAConfigError``.

7. **The CLI-override shape is a nested dict.** ``cli_overrides={"browser":
   {"headless": True}}`` — not ``cli_overrides={"browser.headless":
   True}`` and not ``load_config(browser_headless=True)``. The
   nested-dict form matches ``forgeqa.toml``'s shape and
   ``ForgeQAConfig``'s constructor, so a caller who knows one form
   knows all three.

8. **`read_env_overrides()` is a separate, pure function.** It takes
   an optional ``environ`` mapping (defaulting to ``os.environ``),
   filters by prefix, maps through ``ENV_VAR_OVERRIDES``, and returns
   the nested dict. Splitting it from ``load_config`` makes it
   testable without touching the filesystem, and makes the
   env-scanning contract explicit.

9. **`load_config` gains two keyword-only parameters: `cli_overrides`
   and `environ`.** Both default to "absent" (``None`` for
   ``cli_overrides``, ``os.environ`` for ``environ``). The
   ``environ`` parameter is primarily for testing; production callers
   should omit it. The signature is:

   ```python
   def load_config(
       path: Path | str | None = None,
       *,
       cli_overrides: Mapping[str, Mapping[str, Any]] | None = None,
       environ: Mapping[str, str] | None = None,
   ) -> ForgeQAConfig: ...
   ```

   The keyword-only markers (``*``) make the call sites explicit:
   ``load_config(path, env)`` is a ``TypeError`` — the caller must
   write ``load_config(path, environ=env)``.

10. **Env-var errors name the var; TOML errors name the file; CLI
    errors name the key.** Each layer's error message is tailored to
    what the user needs to fix:
    - Env: ``"Invalid value in environment variable(s)
      FORGEQA_BROWSER_BROWSER_NAME: ..."`` (via
      ``_env_vars_for_validation_errors``, which inverts
      ``ENV_VAR_OVERRIDES`` to map Pydantic's field-loc back to the
      env var).
    - TOML: ``"Invalid configuration in /path/to/forgeqa.toml: ..."``.
    - CLI: ``"Invalid CLI override: ..."``.

11. **No caching.** Same rationale as ADR-008: a developer who
    changes an env var and calls ``load_config()`` again should see
    the new value. The tests pin this.

12. **Backwards compatibility.** With no env vars and no CLI
    overrides, ``load_config`` behaves exactly as in 1.2.2. Adding
    the precedence layer is a **minor** release of the config
    feature — the public API widens, no existing caller behaviour
    changes. The ``load_config(path)`` signature from 1.2.2 is
    unchanged; the two new parameters are keyword-only with defaults.

## Alternatives Considered

| Alternative | Reason Rejected |
| :--- | :--- |
| Generic ``FORGEQA_<SECTION>_<FIELD>`` parser | Would accept typos as valid attempts (``FORGEQA_BROWSR_HEADLESS`` → ``browsr.headless``, then Pydantic rejects with a confusing message). Would make the set of supported env vars invisible. Would silently accept new env vars for new fields without test coverage. The explicit mapping is auditable. |
| Strict rejection of unknown ``FORGEQA_*`` vars | Breaks the "shared environment" invariant. A stray var from a shell script would fail the loader. Django/Rails/Pydantic Settings all ignore unknown env vars. |
| CLI overrides passed as ``**kwargs`` (``load_config(browser_headless=True)``) | Loses the section structure (``browser_headless`` is ambiguous with a top-level field named ``browser_headless``). Does not scale to partial overrides. The nested dict matches ``forgeqa.toml`` and ``ForgeQAConfig``. |
| CLI overrides passed as a flat dotted-path dict (``{"browser.headless": True}``) | Requires parsing the dotted path. The nested dict is directly usable by ``ForgeQAConfig(**cli_dict)``. |
| Apply precedence via ``model_copy(update=...)`` per layer | **Pydantic v2's ``model_copy(update=...)`` does not validate and does not construct sub-models.** Assigning ``{"browser": {...}}`` sets ``config.browser`` to the raw dict, breaking every ``cfg.browser.<attr>`` access and skipping validation entirely. This is the implementation that was attempted first; the test suite caught it (19 ``AttributeError`` failures + 4 "DID NOT RAISE" failures). |
| Apply precedence via a single "merge all layers into one dict, then instantiate once", without per-layer validation | Would validate only the final merged dict, so an invalid env var could be silently "fixed" by a valid CLI override. The layer-by-layer validation (Decision #3) fails at the layer that is invalid. |
| Apply precedence via "last non-default value wins" | Would require knowing each field's default to decide whether a value is "set". Fragile: a user who explicitly sets a field to its default value via env would not get the default; they would get whatever the next layer set. The layer-by-layer approach is correct: if a layer sets a value, it is applied, even if it equals the default. |
| Configurable precedence order | Would complicate the loader and the tests. The four-layer order is standard (12-factor app, Kubernetes, etc.) and matches user expectations. A future need to flip the order is a semver-major change and should be a new ADR. |
| No environment-variable layer (CLI and TOML only) | Would make CI configuration require writing a temp TOML file per job. Env vars are the standard CI interface. |
| No CLI-override layer (env and TOML only) | Would make per-invocation overrides require mutating the environment, which is fragile (env mutation persists across subshells in some contexts; not all CI systems make it easy). A dedicated CLI-override path is the standard. |
| CLI overrides applied *before* env vars | Would mean env vars always win over CLI, which is the opposite of the WBS's explicit precedence. Users expect "the most specific setting wins", and CLI is the most specific. |
| Env vars and CLI overrides treated as one layer with a tie-break | Would obscure the distinction and complicate the error messages. Two layers, applied in order, is simpler. |
| Cache the resolved config in a module-level dict keyed by inputs | Would need to hash the TOML file contents and the environ mapping. The hash is more expensive than the file read. No caching is simpler. |
| Pass env vars as a dictionary of *parsed* values (not strings) | Would require the caller to parse env vars before calling ``load_config``. The string-in, Pydantic-parses approach means the caller does not need to know the target field's type. |
| Strict ``cli_overrides`` validation against the schema's JSON schema | Would require re-parsing the JSON schema at every call, or caching it. ``ForgeQAConfig(**cli_dict)`` already validates the update dict against the model; the extra JSON-schema layer is redundant. |

## Consequences

### Positive

- **The precedence hierarchy is deterministic and fully tested.** A
  user who sets an env var and a CLI override and a TOML value and a
  default gets the CLI value. The tests pin every combination.
- **Per-field precedence.** A config where ``browser_name`` comes from
  env and ``headless`` comes from TOML works. The tests pin this
  (``test_all_four_layers_different_field``).
- **Typed sub-models.** The final ``ForgeQAConfig`` has
  ``cfg.browser`` as a ``BrowserConfig`` instance, not a raw dict.
  This is what the consumer expects; the ``model_copy`` alternative
  violated it silently.
- **Each layer's error names the layer.** Env-var errors name the
  var; TOML errors name the file; CLI errors name the key. A user
  can fix the right thing.
- **Invalid values at their own layer fail before higher layers can
  mask them.** This is ADR-009 Decision #3; the tests pin it.
- **Backwards compatible with 1.2.2.** No env vars and no CLI
  overrides: same behaviour as before.
- **The env-var mapping is auditable.** Adding a field is an explicit
  edit (and a test). A field without an env var is a deliberate
  decision, not an oversight.
- **The CLI-override shape matches the TOML and schema shapes.** One
  shape, learned once.
- **No caching, no staleness.** A developer who changes an env var and
  calls ``load_config()`` again sees the new value.

### Negative

- **Each layer is validated once, then the merged dict is validated
  again.** This is ~2× the Pydantic work of a single validation.
  Pydantic is fast (~10 µs for a config this size), so the cost is
  negligible. The benefit — layer attribution and typed sub-models —
  is worth the cost.
- **The env-var mapping is manual.** Adding a field to a sub-model
  means editing ``ENV_VAR_OVERRIDES`` (and its test) in addition to
  the model. The mapping's size grows linearly with the config
  surface. For ~14 entries today, this is manageable. The ADR's
  reconsideration trigger names the "past ~20 entries" threshold for
  revisiting (possibly a generic parser with a strict allowlist).
- **Unknown env vars are silently ignored.** A user who typos
  ``FORGEQA_BROWSER_BROWSER_NAM`` (missing E) gets no error; the
  field simply uses the TOML or default value. This is the standard
  convention but it is a footgun. Mitigation: the
  ``test_env_var_overrides_mapping_is_complete_for_public_fields``
  test catches the "new field with no env var" case; the "typo in an
  env var name" case is not caught (by design — it would break the
  shared-environment invariant).
- **The `_env_vars_for_validation_errors` helper is a bit of a hack.**
  It inverts the env-var mapping to name the var in the error. If
  Pydantic's error `loc` format changes, the helper silently returns
  no culprits and the error message falls back to ``<unknown>``.
  Mitigated by the test ``test_invalid_env_var_raises_with_var_name``,
  which would fail if the helper stopped working.
- **The `load_config` signature gains two keyword-only parameters.**
  A caller reading the signature sees ``cli_overrides`` and
  ``environ`` and has to learn what they do. This is inherent to
  adding a feature; the docstring and this ADR document them.
- **`read_env_overrides` returns strings, not parsed values.**
  ``FORGEQA_BROWSER_HEADLESS=false`` produces
  ``{"browser": {"headless": "false"}}``, not
  ``{"browser": {"headless": False}}``. Pydantic parses the string
  when the layer is validated. This is intentional: the env-var layer
  does not re-implement Pydantic's coercion. It does mean a caller
  who reads ``read_env_overrides``'s output and inspects it directly
  sees strings, which may be surprising.
- **"Invalid lower layer raises even when higher layer overrides"**
  is a design decision that some users might disagree with. If you
  have an invalid TOML value and a valid env override, you get an
  error. The alternative — silently letting the higher layer fix
  it — was rejected because it masks bugs. Documented in Decision #3.

### Neutral

- `src/forgeqa/config/env.py` is a new module (~150 lines including
  docstrings).
- `src/forgeqa/config/loader.py` grows by ~120 lines (the per-layer
  validation helper, the error-attribution helper, the merge logic).
- `src/forgeqa/config/__init__.py` grows by three exports.
- `tests/unit/config/test_precedence.py` is a new file (~430 lines,
  22 tests).
- `docs/configuration.md` gains a "Precedence" section.
- `docs/engineering-standards.md` §5.2 gains rules 9–12.
- `docs/public-api.md` §`forgeqa.config` gains three names.
- `docs/adr/ADR-009-*.md` is added.
- `docs/adr/README.md` is regenerated.
- No new dependencies. `os` is stdlib.
- No Makefile change. `make verify-config` already runs the whole
  `tests/unit/config/` directory.

## Reconsideration Trigger

Revisit this decision if any of the following occurs:

- **The env-var mapping grows past ~20 entries.** The manual mapping
  becomes a maintenance burden. A generic parser with an explicit
  allowlist (``ENV_VAR_ALLOWLIST: frozenset[str]``) would preserve
  the auditability while removing the per-field edit. The allowlist
  would still need to be updated for a new field, but the mapping
  would not. Decide when the count crosses ~20.
- **A user reports that an unknown env var should have raised.** The
  "silently ignore unknown" decision is standard but not universal.
  If a user's typo in ``FORGEQA_BROWSER_BROWSER_NAM`` cost them
  hours, a "strict mode" option (``load_config(strict_env=True)``)
  could be added. Not needed today.
- **A user reports the "invalid lower layer raises even when higher
  layer overrides" behaviour as surprising.** If the "silently let
  higher layers fix lower layers" model is preferred by users, the
  per-layer validation could be replaced by a single final-merge
  validate. The change would be semver-minor (same signature,
  different error behaviour) but would change what configs are
  accepted; a deprecation cycle might be needed.
- **A user needs to disable the env layer.** E.g. a script that wants
  to ignore the ambient environment and use only TOML. A
  ``load_config(ignore_env=True)`` parameter would address it. Not
  needed today; the explicit ``environ={}`` argument already
  provides this.
- **A user needs to disable the CLI layer.** Symmetric to the above;
  the explicit ``cli_overrides=None`` (the default) already provides
  this. No new parameter needed unless a "disable even the default
  behavior" case emerges.
- **The CLI-override shape changes.** If a future CLI wants a flat
  format (``--browser.headless=true`` → ``{"browser.headless":
  "true"}``), the loader would need to parse dotted paths. The
  current nested dict is the internal shape; a future CLI adapter
  could convert flat to nested before calling ``load_config``. That
  adapter is a separate module, not a change to ``load_config``.
- **A `TypedDict` for `cli_overrides` is desired.** The current
  type is ``Mapping[str, Mapping[str, Any]]``, which does not
  statically enforce the section and field names. A ``TypedDict``
  generated from the schema (or hand-maintained) would. This is a
  static-typing improvement, not a runtime change; it does not
  affect the precedence logic. Defer until a mypy-strict-CLI-adapter
  use case appears.
- **A future cross-field validator is added to a model.** The current
  implementation validates each layer individually and then validates
  the merged dict. A cross-field rule that spans fields from different
  layers (e.g. "if env sets `headless=False`, TOML must set
  `browser_name` to `"firefox"`") would only be exercised on the
  merged dict, not on the individual layers. The error would be
  attributed to the merged-dict validation (which names the TOML
  file if present, per the final fallback). Revisit the error
  attribution at that point.
- **A future config field is CLI-only or env-only.** The env-var
  mapping and the CLI-override shape are independent; a field can
  be settable via env but not via CLI, or vice versa. The
  ``test_env_var_overrides_mapping_is_complete_for_public_fields``
  test checks that *every section* has at least one env var, not
  every field. If a section becomes entirely CLI-only, update the
  test.

## Related

- WBS 1.2.3 — Enforce Configuration Precedence Hierarchy (this
  decision)
- WBS 1.2.2 — Implement TOML Configuration Loader (ADR-008; the
  loader this ADR extends)
- WBS 1.2.1 — Define the Root Pydantic Configuration Schema
  (ADR-007; the schema the precedence applies to)
- WBS 0.4.5 — Configuration Contract (the original requirement)
- ADR-006 — Formalise the public API surface and the private-module
  naming convention (`forgeqa.config.__all__` follows the
  convention)
- ADR-007 — Model the ForgeQA configuration as a strictly-typed
  Pydantic v2 hierarchy with explicit defaults
- ADR-008 — Load forgeqa.toml into ForgeQAConfig with tomllib and a
  custom ForgeQAConfigError
- `src/forgeqa/config/env.py` — the env-var mapping
- `src/forgeqa/config/loader.py` — the loader with precedence applied
- `src/forgeqa/config/__init__.py` — the public re-exports
- `tests/unit/config/test_precedence.py` — the executable contract
- `docs/configuration.md` §"Precedence" — the consumer-facing
  reference
- `docs/engineering-standards.md` §5.2 — the contributor-facing rules
- The Twelve-Factor App — III. Config:
  https://12factor.net/config
- Pydantic v2 `model_copy` documentation (note: does not validate
  the update; see the Decision's design note):
  https://docs.pydantic.dev/latest/api/base_model/#pydantic.BaseModel.model_copy
- Pydantic v2 `model_validate` / model constructor (the validation
  path the loader uses):
  https://docs.pydantic.dev/latest/api/base_model/#pydantic.BaseModel.model_validate
