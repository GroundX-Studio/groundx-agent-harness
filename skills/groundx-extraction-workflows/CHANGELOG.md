# Changelog

All notable changes to the `groundx-extraction-workflows` skill are documented here.
The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this skill adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## 0.x — initial development

This skill is in **initial development (0.x)**. Per semver, anything may
change between minor versions in this phase. Each `0.N.0` bump captures
a coherent iteration milestone informed by real customer use cases. The
`1.0.0` release will mark the first stable public contract.

Tier coverage today: **basic**. Single-stage extraction (extract →
compare → iterate). Advanced tier (reconcile + QA, multi-stage agents)
is the subject of in-progress work informed by internal multi-stage
extraction implementations.

Schema scope today: **single billing example**. Group names
`statement`, `charges`, and `meters` are wired into
`templates/compile_workflow.py`. The planned progression for future
minor versions:

1. **Single worked example** (current).
2. **Schema-family generalization in the same domain**. Validates that
   the YAML-schema-first design center holds
   across multiple customers sharing the billing-invoice schema family
   (statement + charges + meters).
3. **Multi-domain generalization** — adds a different schema family
   (e.g. fraud/insurance). Breaks the initial group-name hardcoding in
   `compile_workflow.py` and introduces mode-key dispatch.

Each step adds one variability dimension against the prior baseline.

## [0.1.5] — 2026-05-13

### Added (documentation only — no API or runtime behavior changes)

Two new reference docs and three doc consistency fixes from AGE-15
review feedback (PR #3, Ben Fletcher).

#### New references

Split into two files because testing (proactive verification) and
debugging (reactive investigation) are different activities with
different lifecycles. Ordered so testing comes before debugging in the
natural dev sequence.

- `references/9_testing_methodology.md` — **Two-audience testing +
  clean-room sub-agent test as the pre-PR gate.** Codifies the
  Customer-via-Claude-Code (A) vs Developer-maintainer (B) split,
  documents the clean-room sub-agent test convention that caught two
  real bugs during v0.1.3 and v0.1.4, and lists what to record in a
  skill-change PR (test recipes per audience, what-was-verified,
  AC/DoD audit).
- `references/10_debugging_methodology.md` — **Diff-before-debug
  discipline.** When a known-working reference exists, compare the
  artifact the system consumes (workflow JSON, request body) before
  forming behavioral hypotheses. Uses the v0.1.2 bug as the worked
  example: ~3 hours and 6 ingests chasing behavioral hypotheses on a
  problem that was visible in a 5-minute JSON diff.

#### Consistency fixes from review feedback

- `references/2_schema_design.md` — adds §1.3 documenting the third
  canonical group `meters` (utility-style usage records). Previously
  reference 2 only documented `statement` and `charges`, contradicting
  SKILL.md and the warner-telecom example which both name three
  groups.
- `references/8_iteration_and_feedback.md` — adds §2.4 "Stop on
  non-convergence within the budget" — the *soft* stop signal that
  complements the existing hard stop on budget exhaustion. Names three
  non-convergence patterns (regression, oscillation, stochastic) and
  three corrective branches (schema restructure, accept FAIL,
  escalate) so the reader knows what to do instead of tightening
  prompts again.
- `references/1_extraction_loop.md` and `references/5_validation.md` —
  both "When to stop" sections now cross-link to
  `references/8_iteration_and_feedback.md` §2 without restating the
  budget number. Single source of truth, surfaced at decision points.

### Notes

- Patch release — documentation only. No API surface or YAML contract
  changes. Existing customer YAMLs continue to work unchanged.

## [0.1.4] — 2026-05-12

### Added

- `templates/cleanup_orphans.py` — janitor script that lists orphan
  workflows (workflows with empty `relationships.ids` — created but never
  attached to a bucket) and deletes them on `--yes`. Defaults to dry-run.
  Supports `--name-prefix` to scope deletions to a single customer's
  naming convention. Run periodically or before quota gets tight.

### Hardened

- `templates/run_extraction.py` — the setup phase (workflow create →
  bucket create → attach) is now wrapped in a try/except rollback. On
  any exception or `KeyboardInterrupt` before attach completes, the
  workflow and bucket created during the run are deleted, so a crash
  mid-setup no longer leaks resources to the platform. Resources passed
  via `--reuse-workflow` / `--reuse-bucket` are never deleted. Once
  attach succeeds, rollback no longer fires — ingest/poll failures keep
  the resources in place for inspection.
- `templates/validate_workflow_json.py` — added a scan for unresolved
  Python format placeholders (e.g. `{field_desc}`) in any string under
  `steps` or `extract`. Catches the silent-degradation class where a
  `.format()` call drops a kwarg and emits literal placeholder text to
  the LLM. Reported alongside the existing slot/variant checks.

### Notes

- Patch release — additive cleanup capability plus hardening. No API
  surface or YAML contract changes. Existing customer YAMLs and run
  scripts continue to work unchanged.

## [0.1.3] — 2026-05-12

### Added (iteration aids — no behavior changes to existing surfaces)

- `templates/xray_to_extract.py` — reads an X-Ray JSON file and synthesizes
  the same dict shape `gx.documents.get_extract()` returns. Lets you
  iterate on comparison logic, field aliases, and dedupe rules locally
  against a captured X-Ray without paying for re-ingest. Re-ingest is
  only required when YAML or prompts actually change.
- `templates/validate_workflow_json.py` — structural self-check on
  compiled workflow JSON. Asserts the seven `WorkflowSteps` slot keys
  and the six `WorkflowStep` variant keys are present (may be null).
  Catches the slot-wiring regression class before a live ingest.
- `templates/run_log.py` — JSONL logger module. Each event is written
  line-buffered to disk so sub-agent termination does not lose inspection
  context. Includes a `quota_snapshot(gx_client)` helper for recording
  `file_tokens` / `searches` deltas at run start and end.
- `templates/run_extraction.py` — canonical end-to-end runner. Compiles
  YAML, validates the workflow JSON, creates workflow + bucket, attaches,
  ingests, polls, captures X-Ray + extract, writes artifacts. Replaces
  ~80 lines of repeated per-customer SDK orchestration with a single
  invocation that emits structured events to `run.log`.

### Notes

- Patch release — additive helpers. No API surface or YAML contract
  changes. Existing customer YAMLs continue to compile and run unchanged.
- No reference doc changes; each template's docstring documents its use.

## [0.1.2] — 2026-05-12

### Fixed

- `templates/compile_workflow.py` — `workflow_steps_for_yaml()` now passes
  every `WorkflowStep` variant (`all_`, `figure`, `paragraph`, `json_`,
  `table`, `table_figure`) and every `WorkflowSteps` slot (`chunk_instruct`,
  `chunk_keys`, `chunk_summary`, `doc_keys`, `doc_summary`, `sect_instruct`,
  `sect_summary`) explicitly, with `None` for unused slots. `_to_dict()`
  now uses `model_dump(by_alias=True)` (or `.dict(by_alias=True)` fallback)
  to preserve those `None` values in the serialized JSON.
- `templates/compile_workflow.py` — `_charges_request` and `_charges_task`
  prompt wrappers enforce a consistent `{"charges": [...]}` wrapper on
  chunk_keys output. The LLM may not return a raw array or a different
  wrapper key. Includes a few-shot example and an explicit "do not invent
  records" instruction.

### Why this matters

The load-bearing fix is the slot wiring. Before this release, Pydantic
v1's `.dict()` silently dropped fields left unset, so the compiled
workflow JSON was missing 5 of 7 `WorkflowSteps` keys and 3 of 6
`WorkflowStep` variant keys per populated step. The GroundX platform's
`chunk_keys → account_charges` aggregator only runs when those slot keys
are present (even if `null`). With the keys missing, the workflow was
accepted, ingest ran, X-Ray populated correctly — but the aggregator
silently skipped, and the `account_charges` key on the `get_extract()`
response always returned `[]` even when per-chunk extractions were
correct in X-Ray.

The wrapper enforcement is defensive: it ensures the LLM produces a
consistent `{"charges": [...]}` shape on every chunk, which makes the
aggregator's job easier and prevents one class of per-chunk output
drift across runs.

This was caught and validated during the warner-001 live test. The fix
was verified end-to-end against the account that previously failed: the
same YAML and the same per-chunk prompts now produce `account_charges`
with the expected 3/3 charge records.

### Notes

- Patch release — fixes broken behavior without changing the YAML
  contract or API surface. Existing customer YAMLs continue to work
  unchanged; they will simply start producing populated `account_charges`
  where they previously returned `[]`.
- No reference doc changes were needed for this fix. The bug was in
  serialization, not in the conventions the skill teaches.

## [0.1.1] — 2026-05-11

### Added (documentation only — no API or runtime behavior changes)

- `references/8_iteration_and_feedback.md` — the operational layer on
  top of the basic extraction loop. Documents:
  - Iteration budget convention (default: 2 iterations max per
    working session)
  - Journey storage convention (per-run artifacts in an external
    `extractx-runs/<customer>-<run>/` location)
  - Finalization criteria (when a YAML is "done")
  - Compounding feedback flow — finalized YAML → `examples/<customer>/`,
    per-customer lessons → `LESSONS.md`, generalizable lessons →
    `references/` updates
  - X-Ray as a first-class iteration artifact (`get_xray` captured
    alongside `compare-report.txt` for sub-agent v2 authoring)
  - Per-iteration quota tracking (file_tokens before/after, recorded
    in run.md)
- `SKILL.md`: added reference 8 to the "Before producing anything,
  read" list and to the task → reference quick map (new entry for
  "onboarding a new customer end-to-end")

### Notes

- Backwards-compatible with v0.1.0. No YAML format changes; no
  compile-script behavior changes. Existing customer YAMLs continue
  to work without modification.
- This is a **patch release** because it adds documentation only.
  The next planned minor release (v0.2.0) is the multi-domain
  generalization (mode-key dispatch in `compile_workflow.py`); see
  `notes/AGE-15-design.md` for the design analysis.

## [0.1.0] — 2026-05-07

### Added

- Initial skill: `groundx-extraction-workflows`
- `SKILL.md` with installed-skill retrieval contract
- 7 reference docs:
  - `references/1_extraction_loop.md` — end-to-end loop
  - `references/2_schema_design.md` — group decomposition, field anatomy
  - `references/3_prompt_pipeline.md` — YAML → LLM input rendering
  - `references/4_sdk_integration.md` — compile script + delegated API operations
  - `references/5_validation.md` — comparison patterns
  - `references/6_known_limitations.md` — AGE-6, AGE-7, escalation playbook
  - `references/7_promote_to_project.md` — deferred-with-rationale doc
- `templates/compile_workflow.py` — offline YAML → workflow JSON translator
- `templates/compare.py` — comparison harness with date/float/casing
  normalization and charge alias mapping
- `templates/prompt.yaml` — starter schema (warner-shaped, statement + charges)
- `templates/.env.sample` — placeholder credentials only
- `templates/requirements.txt` — minimal dependency set
- `examples/warner-telecom/` — full worked example (schema, PDF,
  answer key) adapted from the billing example
- `evals/evals.json` with 4 tests + `evals/fixtures/warner-telecom/`
  fixtures (PDF, CSV, expected JSON)
- New validate gate: `scripts/tests/test-groundx-extraction-workflows.mjs` (dry-run only,
  no GroundX API calls in CI)
- Repo-wide registration: `marketplace.json`, `README.md`, `AGENTS.md`,
  `validate.mjs` check #10, `scan-skill-coverage.mjs` coverage entry

### Notes

- **Warner-pattern only.** Group names `statement` and `charges` are
  hardcoded in `compile_workflow.py`. Documents that don't fit this
  shape will not auto-wire correctly.
- **Workflow + ingest delegated to `groundx-api`.** No API operations
  duplicated inline; the skill is authoring-focused.
- **Deployable Python project scaffolding deferred** — see
  `references/7_promote_to_project.md` for rationale.

### Linked

- Linear: AGE-15 (umbrella issue for the skill)
- Related: AGE-1 (Warner PoC, source pattern), AGE-6, AGE-7 (platform-side)
