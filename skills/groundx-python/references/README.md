# GroundX Python SDK References

Fast path for agents working with the public `eyelevelai/groundx-python` SDK
repo.

The repo's own [`AGENTS.md`](https://github.com/eyelevelai/groundx-python/blob/main/AGENTS.md)
is canonical. Use this skill to decide whether the work belongs in the SDK repo
or in another GroundX skill.

## Use This Skill When

| Need | Read |
| --- | --- |
| Decide whether this is SDK-repo work vs SDK usage / extraction / architecture | `01-orientation.md` |
| Understand Fern, `.fernignore`, generated-vs-hand-written files, or upstream API changes | `02-core-sdk.md` |
| Work on `src/groundx/extract/`, optional deps, extract tests, or Pydantic conventions | `03-extract.md` |

## Use Another Skill When

| If the user wants to... | Use |
| --- | --- |
| Write Python that calls the GroundX SDK from their own app | `groundx-api` |
| Author or iterate a schema-first extraction YAML | `groundx-extraction-workflows` |
| Understand GroundX ingest, search, extraction, or runtime architecture | `groundx-architecture` |
| Deploy or configure GroundX on Kubernetes | `groundx-on-prem` |

## Defaults

- `AGENTS.md` in the SDK repo is the source of truth.
- `.fernignore` defines what survives Fern regeneration.
- `pyproject.toml` is regenerated; dependency/extras changes go through
  `.fern/metadata.json`.
- Extract tests live under `tests/extract/`.
