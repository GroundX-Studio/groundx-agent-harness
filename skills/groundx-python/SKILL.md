---
name: groundx-python
description: >
  Guidance for the public `eyelevelai/groundx-python` SDK repo — the official
  Python SDK for GroundX (`pip install groundx`). Use this skill when the work
  involves editing or contributing to the SDK repo itself: fixing a bug in the
  extract submodule, adding an optional dependency to `groundx[extract]`, working
  with the Fern generator boundary, proposing an upstream API change, navigating
  the hand-written-vs-generated split via `.fernignore`, or extending extract
  agents / prompts / tasks / classes. Use `groundx-api` instead when the user
  only wants to call the SDK from another repo.
---

# GroundX Python SDK Contribution

Use this skill for **contributing to the `eyelevelai/groundx-python` repo**.
The repo's own [`AGENTS.md`](https://github.com/eyelevelai/groundx-python/blob/main/AGENTS.md)
is the canonical contribution guide. This skill helps agents decide whether the
task is SDK-repo contribution work, then points to the right reference.

## Routing Contract

- **Use this skill for:**
  - editing files in `eyelevelai/groundx-python`
  - files under `src/groundx/extract/`
  - `.fernignore`, `.fern/metadata.json`, or Fern-generated SDK boundaries
  - adding an optional dependency to `groundx[extract]`
  - adding tests under `tests/extract/`
  - proposing an upstream API-shape change for generated SDK types or methods
- **Use `groundx-api` instead for:** Python code that calls the SDK from another
  repo, typed SDK request/response examples, REST semantics, MCP semantics, and
  GroundX API behavior.
- **Use `groundx-extraction-workflows` instead for:** schema-first extraction
  YAML, extraction workflow iteration, and field-accuracy methodology.
- **Use `groundx-architecture` instead for:** system behavior, runtime pipeline,
  or "how does GroundX work?" questions.

## Read First

1. `references/README.md` — choose the right path.
2. [`groundx-python/AGENTS.md`](https://github.com/eyelevelai/groundx-python/blob/main/AGENTS.md)
   — canonical setup, contribution, test, release, and generated-code rules.

Then open the matching reference:

| Job | Read |
| --- | --- |
| Decide if this is SDK contribution or SDK usage | `references/01-orientation.md` |
| Fern boundary, `.fernignore`, generated files, upstream API changes | `references/02-core-sdk.md` |
| Extract submodule, optional deps, extract tests, Pydantic conventions | `references/03-extract.md` |

## Guardrails

- Do not edit Fern-generated files directly.
- Do not edit `pyproject.toml` to add dependencies or mypy config; use
  `.fern/metadata.json`.
- Do not route SDK consumer questions here; route them to `groundx-api`.
- Do not invent contribution rules. If this skill and the repo's `AGENTS.md`
  disagree, the repo wins.

## Pre-Return Checklist

- [ ] Confirmed this is SDK-repo contribution work, not SDK usage.
- [ ] Opened the matching reference and checked the repo `AGENTS.md`.
- [ ] For generated-code changes, described the upstream Fern/API-spec path.
- [ ] For dependency changes, pointed at `.fern/metadata.json`.
- [ ] For extract tests, pointed at `tests/extract/`.
