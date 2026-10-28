# ADR-001: Adopt MIT license file and PEP 621-compliant package metadata

> **Status**: Accepted
> **Date**: 2026-10-28
> **Deciders**: Solo Developer
> **Consulted**: None
> **Informed**: None

## Context

WBS 0.5.2 established the initial `pyproject.toml` with `license = { text = "MIT" }`.
When WBS 1.1.1 required the built wheel to contain the `LICENSE` file itself
(acceptance criterion: "The LICENSE file is included in the built wheel"),
the `text =` form proved insufficient: PEP 621's `text` form embeds the
license *string* in `METADATA` but does not bundle the file into
`.dist-info/licenses/`.

Two further inconsistencies surfaced during 1.1.1 verification:

1. The build/verify loop depends on `twine check`, but neither `twine` nor
   `build` was declared in any dependency group, so a clean checkout could
   not reproduce the acceptance run.
2. `[project.optional-dependencies].all` used a self-reference
   (`forgeqa[ui,api,dev]`). This works on modern pip but (a) emits resolver
   warnings on older pip and (b) hides the concrete dependency set from
   readers and from tools that flatten extras.

Separately, `requires-python = ">=3.11,<3.13"` was already decided in the
Phase 0.5.1 support matrix. During 1.1.1 verification we confirmed PEP 440
canonicalises it to `<3.13,>=3.11` in `METADATA`, which is semantically
identical and is the form `pip` reads. Declared form stays human-readable;
emitted form is canonical.

Forces at play:

- **Correctness:** the wheel must be self-contained (license bundled).
- **Reproducibility:** a clean `pip install -e ".[dev]"` must reproduce the
  acceptance run.
- **Portability:** the manifest must resolve identically on old and new pip.
- **Forward-compatibility:** avoid build-backend-specific escape hatches
  (e.g. hatchling `force-include`) for something PEP 621 expresses
  declaratively.
- **Human readability:** `pyproject.toml` should remain legible to a reviewer
  who is not familiar with PEP 440 canonicalisation.

## Decision

1. **License declaration:** use `license = { file = "LICENSE" }` in
   `[project]`. The `LICENSE` file at repo root is the single source of
   truth and is bundled into
   `forgeqa-0.1.0.dist-info/licenses/LICENSE` in the built wheel. The
   `License :: OSI Approved :: MIT License` classifier is retained for
   PyPI display.
2. **Build tooling:** declare `build>=1.2` and `twine>=5.1` in
   `[project.optional-dependencies].dev`, and in the flattened `all` extra.
   The `make build` target runs `twine check dist/*` as part of the build,
   so the acceptance gate is exercised every time.
3. **Extras:** flatten `all` to an explicit list; no self-referencing
   extras.
4. **Python support:** `requires-python = ">=3.11,<3.13"` remains the
   declared support window, matching the Phase 0.5.1 matrix (3.11 and 3.12).
   The canonical `<3.13,>=3.11` form emitted in `METADATA` is accepted as
   correct per PEP 440.
5. **Makefile hygiene:** remove duplicate `build` / `clean` recipes
   (overriding-recipe warnings); use `$(VENV_PYTHON)` for build/twine so
   they run inside `.venv`; make `clean` portable by using `find … -name
   "*.egg-info" -exec rm -rf {} +` instead of an unquoted glob that aborts
   under `zsh` when nothing matches.

## Alternatives Considered

| Alternative | Reason Rejected |
| :--- | :--- |
| Keep `license = { text = "MIT" }` | Fails the acceptance criterion that the `LICENSE` file itself be in the wheel; PEP 621's `text` form does not bundle a file. |
| Ship `LICENSE` via `[tool.hatch.build.targets.wheel] force-include` | Build-backend-specific escape hatch for something PEP 621 already expresses declaratively via `license.file`. Less portable, less obvious to readers. |
| Keep `all = ["forgeqa[ui,api,dev]"]` self-reference | Flattens to the same set, but hides the concrete deps and warns on older pip; the explicit list is what the README's `pip install forgeqa[all]` actually installs. |
| Add legacy `homepage` / `author` keys so `pip show` is prettier | PyPI deprecates these in favour of `project.urls` / `project.authors`; "fixing" the pip UI would regress correctness. |
| Force `requires-python` to render as `">=3.11,<3.13"` in `METADATA` | PEP 440 mandates canonical form in metadata; forcing display order is not supported by hatchling and would fight the spec. |
| Keep duplicate `build` / `clean` recipes in the `Makefile` | `make` warns (`overriding recipe` / `ignoring old recipe`) and silently picks the later definition; ambiguity is a maintenance trap. |
| Leave `Makefile` `clean` using `rm -rf … *.egg-info` | Unquoted glob aborts the whole `rm` under `zsh` with `NOMATCH` when there are no `*.egg-info` dirs; the build then runs against stale artifacts. |

## Consequences

### Positive

- The wheel is self-contained: `LICENSE` ships inside
  `.dist-info/licenses/`, satisfying WBS 1.1.1 acceptance criterion #3.
- `pip show forgeqa` displays `License: MIT License` plus the full MIT body,
  and `Summary` / `Version` as expected.
- `twine check dist/*` passes with zero warnings on both wheel and sdist.
- A clean `pip install -e ".[dev]"` reproduces the acceptance run — no
  undeclared tooling.
- `make build` now exercises the acceptance gate (`twine check`) every time,
  so a regression cannot slip past a local build.
- `forgeqa[all]` resolves identically on old and new pip.
- `make` no longer emits duplicate-recipe warnings; the `Makefile` has one
  authoritative definition per target.
- `clean` is portable across bash, dash, and zsh; no `NOMATCH` abort.
- `Requires-Python` in `METADATA` is PEP 440 canonical
  (`<3.13,>=3.11`), which is what `pip` and `packaging` compare against;
  the declared form in `pyproject.toml` stays human-readable
  (`>=3.11,<3.13`).

### Negative

- `license = { file = "LICENSE" }` writes the full MIT text into the
  `License:` METADATA field, making `pip show` verbose. Accepted: the
  bundling requirement outweighs display cosmetics.
- `pip show` leaves `Home-page:` and `Author:` blank because those fields
  come from legacy metadata keys, not `[project.urls]` /
  `[project.authors]`. This is a `pip` UI limitation; PyPI renders
  `project.urls.Homepage` correctly. We deliberately do **not** add legacy
  keys to "fix" it.
- The build now depends on `twine` being present in `.venv`; `make build`
  fails loudly if `.venv` is missing or stale rather than silently using a
  global `python`. That is intentional (fail-fast), but it is a behavioural
  change for anyone running `make build` without first running
  `make install`.

### Neutral

- `[project.optional-dependencies].all` is longer (explicit list vs. one
  self-reference). Trade-off: more lines, no ambiguity, no resolver
  warnings.
- `Makefile` `clean` uses `find` rather than a glob. Same effect, slightly
  more verbose, portable.
- `LICENSE` is now bundled in `.dist-info/licenses/`; previously it lived
  only at repo root. No behavioural impact on consumers, only on packaging
  tools.

## Reconsideration Trigger

Revisit this decision if any of the following occurs:

- **PEP 639 adoption:** hatchling ≥ 1.27 becomes our floor and PEP 639 is
  finalised; migrate to `license = "MIT"` + `license-files = ["LICENSE"]`
  and drop the `License ::` classifier. Track as a 0.5.2 revision
  follow-up.
- **Python matrix change:** Phase 0.5.1 matrix is revised (e.g. drop 3.11,
  add 3.13); update `requires-python` accordingly and re-verify the
  canonical form.
- **Build backend change:** if we leave hatchling, re-validate that the new
  backend honours `license.file` bundling and `[tool.*.build]` mappings
  equivalently.
- **`pip show` UX becomes a real complaint:** if downstream users ask why
  `Home-page:` is blank, document the `pip` UI limitation and point them to
  `pip show --verbose` or PyPI, rather than regressing metadata correctness.
- **A new verification script needs `packaging` directly:** add it to
  `[dev]` (not `[project].dependencies`); this ADR's decision on tooling
  scope remains, but the concrete list grows.

## Related

- WBS 1.1.1 — Finalise Package Metadata & License (this decision)
- WBS 0.5.2 — Initial `pyproject.toml` (predecessor)
- Phase 0.5.1 — Python support matrix (3.11, 3.12)
- PEP 621 — Storing project metadata in pyproject.toml:
  https://peps.python.org/pep-0621/
- PEP 440 — Version Identification and Dependency Specification
  (canonical form of `Requires-Python`):
  https://peps.python.org/pep-0440/#version-specifiers
- PEP 639 — Improving License Clarity with Better Package Metadata
  (future migration, not adopted here):
  https://peps.python.org/pep-0639/
- Hatchling build configuration:
  https://hatch.pypa.io/latest/config/build/
- `packaging.specifiers.SpecifierSet`:
  https://packaging.python.org/en/latest/specifications/version-specifiers/
- `docs/engineering-standards.md` — "Supported Python Versions"
- `pyproject.toml`, `LICENSE`, `README.md`, `Makefile` — files changed by
  this decision
