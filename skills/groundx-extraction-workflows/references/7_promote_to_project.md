# 7. Promote to project — deferred

Production deployment scaffolding (a Python project shape with
`manager.py`, per-group prompt modules under `prompts/`, and a
comparison harness under `test/compare_extraction.py`) is **not part
of v1**. This reference exists to document the rationale and the path
forward.

## 1. Why deferred

Three reasons:

### 1.1 Studio is the eventual deployment surface

`studio.eyelevel.ai` is on the path to becoming the primary place where
finished extraction schemas are run and re-run by non-engineers (sales
engineers, customer integrators). When Studio's prompt-import API
matures and is documented in `groundx-python/reference.md`, the
"deployment" question becomes: upload the YAML to Studio.

If we shipped a Python-project deployable now, we would either retire it
when Studio matures or maintain two deployment paths in parallel. Both
are wasteful.

### 1.2 More complex use cases require broader survey

`internal-arcadia-agents` (the production extraction service for the
Arcadia client) does more than this skill currently teaches: it has
**reconciliation** and **QA** microservices on top of extraction. Those
patterns are not yet captured in this skill, and they may change what
"deployable" means — for example, a deployable shape that does
extraction *and* reconciliation has different boundaries than one that
does extraction only.

This skill will be extended to cover those patterns once
`internal-arcadia-agents` is surveyed. At that point, "promote to
project" is informed by the full pattern — not just the warner-style
shape.

### 1.3 Earn it first

The current skill is **schema authoring**. Until extraction schemas
authored through this skill are running in production at customer-scale,
adding production scaffolding is speculative. The harness principle is
to add complexity when measured demand exists, not in anticipation.

## 2. The path forward

When this skill needs to support a deployable shape:

1. Survey `internal-arcadia-agents` for the reconciliation + QA patterns
2. Decide whether the deployable shape is extraction-only (warner-style)
   or extraction+reconcile+QA (arcadia-style) or parameterized
3. Author the templates in `templates/deployable/` with a documented
   purpose
4. Restore the test in `evals/evals.json` that exercises the
   promote-to-project flow
5. Update `SKILL.md` to route Claude to this reference when a user asks
   to ship as a project

## 3. What users do today instead

For production deployment of a finished YAML, the path today is:

1. Use the YAML as-is — it is already a portable artifact
2. POST it to GroundX as a workflow (see `groundx-api`'s
   `references/06-workflows.md` for the API operations)
3. Attach the workflow to a bucket and run extractions through that
   bucket on an ongoing basis

No Python project is required for this path. The YAML + the standard
GroundX workflow API are the deployment.

If a user explicitly needs a Python project — for example, to wrap the
extraction in a customer-specific service with auth, batching, or
custom output transformation — they can hand-author one off the YAML.
The `compile_workflow.py` script in `templates/` produces the workflow
JSON the project would POST.
