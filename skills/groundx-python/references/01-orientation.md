# 1. Orientation: when to use this skill

The Python SDK shows up in three different shapes of work. Pick the right home
before producing output.

## 1.1 Three shapes of work

| Shape | Who owns it | Quick signal |
|---|---|---|
| **Contributing to the SDK repo itself** — fixing a bug, adding an optional dep, extending extract, working with the Fern generator boundary | **This skill** + the repo's [`AGENTS.md`](https://github.com/eyelevelai/groundx-python/blob/main/AGENTS.md) | The user is editing files in `eyelevelai/groundx-python`. File paths under `src/groundx/`, mentions of `.fernignore` / `.fern/metadata.json`, "add a dep to extract", "fix the extract agent" |
| **Using the SDK from another repo** — writing Python that calls `client.search.content(...)`, `client.workflows.create(...)`, etc. | **`groundx-api`** (see its `references/12-python-sdk-objects.md` for the typed Python class surface) | User code imports `from groundx import GroundX`. Questions about typed classes, async client, error types, retry behavior, request/response shape |
| **Schema-first extraction methodology** — YAML schema authoring, extraction workflow compilation, field-accuracy iteration | **`groundx-extraction-workflows`** | YAML schema, extraction workflow JSON, run-and-compare loops, ground-truth CSVs |

## 1.2 Decision tree

```
Is the user editing files inside the eyelevelai/groundx-python repo?
├── YES → this skill + repo AGENTS.md
└── NO  → it's not contribution work
         │
         Is the user writing Python that calls the SDK from their own code?
         ├── YES → groundx-api (12-python-sdk-objects.md is the SDK reference)
         └── NO  → not Python-SDK-shaped
                  │
                  Is the user authoring an extraction YAML / iterating on a schema?
                  ├── YES → groundx-extraction-workflows
                  └── NO  → architecture / deployment / partner work; route accordingly
```

## 1.3 Common confusions

**"I want to add a new field to the Document class."**
→ Document is *generated* by Fern from the upstream API definition (see
`02-core-sdk.md`). Adding a field there means changing the upstream Fern API
definition, not editing the generated file. This is **SDK-repo contribution
work** — use this skill. The repo's AGENTS.md §3 covers the intake path
(`AGENTS.md` linked from this skill's `02-core-sdk.md`).

**"I want to use Document from my Python code."**
→ This is consumer-side work — use `groundx-api`. The reference
`groundx-api/references/12-python-sdk-objects.md` documents the typed Python
class surface (camelCase wire ↔ snake_case attribute mapping, etc.).

**"I want to fix a bug in the extract module's prompt manager."**
→ Extract is hand-written (per `.fernignore`) — **SDK-repo contribution work**.
Use this skill + the repo's `AGENTS.md` §4 for the extract-specific rules.

**"I want to add an optional dep to `groundx[extract]`."**
→ SDK-repo contribution work. Edit `.fern/metadata.json`, not `pyproject.toml`
(per repo `AGENTS.md` §4 + the harness skill's `02-core-sdk.md`).

**"How does the extract agentic pipeline actually work?"**
→ Architectural question. Use `groundx-architecture`.

**"Where do extract tests live?"**
→ This is borderline. If the question is *"I want to add a test, where does it
go?"* — that's SDK-repo contribution work (use this skill + repo `AGENTS.md` §4).
If the question is *"how is extract tested at the architecture level?"* — use
`groundx-architecture`.

## 1.4 What this skill does not do

- It does not replace the repo's `AGENTS.md`. The AGENTS.md is canonical for
  contribution rules; this skill is the routing layer that helps agents *find*
  the AGENTS.md when they have a contribution-shaped intent.
- It does not document the SDK's consumer API surface. That lives in
  `groundx-api`.
- It does not document extraction workflow methodology. That lives in
  `groundx-extraction-workflows`.
