# Deploy A Finished YAML

Use this when `prompt.yaml` is finished and the next step is registering or
attaching the workflow.

## Decision Table

| Situation | Use |
| --- | --- |
| User wants one local deploy command for a finished YAML | `templates/deploy_workflow.py` |
| User wants prod deploy + ingest + poll + X-Ray + extract | `templates/run_extraction.py` |
| Agent has prod GroundX MCP tools already connected | `groundx-api` MCP tools are optional |

## Template Setup

Before running the local command, copy these files from
`skills/groundx-extraction-workflows/templates/` into the extraction work
directory:

- `deploy_workflow.py`
- `compile_workflow.py`
- `validate_workflow_json.py`
- `requirements.txt`
- `.env.sample` as `.env`

Concrete setup:

```bash
SKILL_DIR=/absolute/path/to/groundx-extraction-workflows
cp "$SKILL_DIR/templates/deploy_workflow.py" .
cp "$SKILL_DIR/templates/compile_workflow.py" .
cp "$SKILL_DIR/templates/validate_workflow_json.py" .
cp "$SKILL_DIR/templates/requirements.txt" .
cp "$SKILL_DIR/templates/.env.sample" .env
python -m pip install -r requirements.txt
```

Set `GROUNDX_API_KEY` in `.env` or in the shell environment. Use a prod API key
for live structured extraction. Dev extraction does not currently work; only use
dev for deploy/run/extract if an operator explicitly confirms it is available.
For dev non-extraction API/debug calls, also set
`GROUNDX_BASE_URL=https://devapi.groundx.ai/api`. For prod, leave
`GROUNDX_BASE_URL` unset. Leave API keys out of prompts and command-line arguments.

## Local Deploy Commands

Create a new workflow from the extraction work directory:

```bash
python deploy_workflow.py \
  --yaml prompt.yaml \
  --out deploy/ \
  --workflow-name customer-workflow-v1 \
  --create-bucket-name customer-bucket-v1
```

Update an existing workflow:

```bash
python deploy_workflow.py \
  --yaml prompt.yaml \
  --out deploy/ \
  --workflow-id workflow-123 \
  --bucket-id 12345
```

`--yaml` is the path to the YAML file. It can be a filename in the current
directory or a full path. `--workflow-name` is optional; without it, the script
uses the YAML filename without `.yaml`. `--workflow-id` switches the command
from create to update.

The deploy script compiles and validates the YAML first, then sends the
compiled workflow body to the GroundX SDK. It does not re-load the raw YAML path
after compilation. This keeps harness-specific `workflow_step:`,
`workflow.custom_steps`, route metadata, and pilot metadata on the compiler path
that already validated them. The public SDK
`create_extraction_workflow(path=...)` and
`update_extraction_workflow(path=...)` helpers remain valid for YAML that is
directly SDK-loadable, but harness local templates should not compile a YAML and
then pass the same raw path back to those helpers.

This local SDK path is not the same as the product YAML upload path. It bypasses
upload-time normalization, persisted source handling, and any internal legacy
YAML-to-v1 translation owned by the platform. Use it for local deployment,
diagnostics, or controlled extraction runs. Do not use it as proof that a user
upload, product upload, or legacy YAML normalization path works.

## Engine-Only Updates

When the only intended change is the model endpoint for existing workflow steps,
send an engine-only custom overlay and omit `prompt`.

```json
{
  "steps": {
    "chunk-summary": {
      "all": {
        "engine": {
          "apiKey": "CUSTOM_PROVIDER_KEY",
          "baseURL": "https://api.deepinfra.com/v1/openai",
          "engineID": "EyeLevel/gemma-4-31B-it-turbo",
          "service": "deep-infra"
        }
      }
    }
  }
}
```

Workflow updates are treated like workflow creates: the payload is the desired
custom overlay relative to GroundX defaults, not a delta against the currently
stored custom workflow. Omit a step to return it to defaults. Send a step as
`null` only when you intentionally want to disable/clear that default step.
A name-only update is not metadata-only; include custom processing settings again
if they should remain in effect.

Do not send `prompt: {}` as a clearing signal. Omitted `prompt` and `prompt: {}`
both mean "use the default prompt group"; `prompt: null` means "use no prompt
group."

If the target backend predates default-overlay workflow updates, send explicit
prompt objects for any step that must not become empty. For workflows already
stored with `prompt: {}`, restore custom prompt text from prior workflow JSON,
audit logs, backups, or source YAML. If the workflow should use GroundX default
prompts, resubmit the desired overlay after the backend fix or recreate the
workflow from a clean source definition.

## Optional Prod MCP Recipe

Use this path only when GroundX MCP tools are already visible in the agent
session and the target environment is prod. GroundX MCP is optional and prod-only.
For dev API/debug work, use the local Python SDK with
`GROUNDX_BASE_URL=https://devapi.groundx.ai/api`; do not run live structured
extraction in dev unless an operator explicitly confirms it is available.

1. Compile the YAML to `workflow.json`.
2. Validate it with `python validate_workflow_json.py workflow.json`.
3. Use `groundx-api/references/06-workflows.md` for the exact
   `workflow_create` or `workflow_update` arguments. Pass the compiled workflow
   fields from `workflow.json`; do not hand-build a different schema. Use
   `workflow_update` only when you already have the existing workflow ID.
   For custom extraction workflows, keep `customSteps`, `outputRoutes`,
   `leafFields`, and `extract.workflow` together from the compiled payload.
4. Save the returned workflow ID.
5. Attach it with `workflow_add_to_id` for a bucket/group or
   `workflow_add_to_account` for the account default.

Minimal field mapping:

| Artifact or target | MCP tool | What to pass |
| --- | --- | --- |
| New compiled workflow | `workflow_create` | Top-level fields from `workflow.json`: `name`, `chunkStrategy`, `sectionStrategy`, `steps`, and `extract` when present. For custom extraction workflows, include `customSteps`, `outputRoutes`, `leafFields`, and the persisted `extract.workflow` metadata. |
| Existing workflow | `workflow_update` | `id` set to the existing workflow ID, plus the desired custom overlay relative to defaults. |
| Bucket or group attachment | `workflow_add_to_id` | `id` set to the bucket/group ID, and `workflowId` set to the created or updated workflow ID. |
| Account default | `workflow_add_to_account` | `workflowId` set to the created or updated workflow ID. |

Never pass a GroundX API key in MCP tool arguments. The MCP connector/session
owns authentication.

For exact arguments, field casing, and response shapes, use
`groundx-api/references/06-workflows.md`.

## Bucket Options

Use exactly one bucket target option:

| Option | Meaning |
| --- | --- |
| `--bucket-id 12345` | Attach to an existing bucket by ID. |
| `--bucket-name "Existing Name"` | Look up an exact existing bucket name and attach to it. Fails if no exact match exists. |
| `--create-bucket-name "New Name"` | Create a new bucket and attach to it. |

`--bucket-name` does not create a bucket.

Use `--add-to-account` only when the workflow should become the account default.
It may be used with or without a bucket target.

## Dry Run

Before making live changes:

```bash
python deploy_workflow.py \
  --yaml prompt.yaml \
  --out deploy/ \
  --workflow-name customer-workflow-v1 \
  --dry-run
```

Dry run compiles the YAML, validates `workflow.json`, writes `deploy.json`, and
prints the planned workflow action. It does not call GroundX and does not require
`GROUNDX_API_KEY`.

## Verify Deployment

After a live deploy:

1. Confirm the command printed `workflow created` or `workflow updated`.
2. Open `deploy/deploy.json` and confirm `"status": "deployed"`.
3. Confirm `deploy/workflow_id.txt` exists and contains the workflow ID.
4. If bucket attachment was requested, confirm `deploy/bucket_id.txt` exists or
   `deploy.json` has the expected `bucketId`.
5. For interactive sessions, use the `groundx-api` workflow tools or SDK docs to
   fetch the workflow or list bucket/account attachments before ingesting a test
   document.

If the workflow was attached to the wrong target, fix the assignment before ingesting a
new test document:

- use `workflow_remove_from_id` for a wrong bucket or group assignment
- use `workflow_remove_from_account` for a wrong account-default assignment
- rerun the correct `workflow_add_to_id` or `workflow_add_to_account` call afterward

For exact remove/detach arguments, use `groundx-api/references/06-workflows.md`.

## Credentials

The script reads `GROUNDX_API_KEY` and optional `GROUNDX_BASE_URL` from the
process environment, `.env` in the current directory, or `.env` beside the YAML
file. Do not pass API keys as command-line arguments.

Use a different `GROUNDX_API_KEY` per environment. Prod live extraction leaves
`GROUNDX_BASE_URL` unset or sets `https://api.groundx.ai/api`. Dev API/debug
calls use `GROUNDX_BASE_URL=https://devapi.groundx.ai/api`, but dev structured
extraction is unavailable unless an operator confirms otherwise.

## Outputs

`deploy_workflow.py` writes:

- `workflow.json` — compiled workflow body
- `deploy.json` — status, workflow action, attachment target, and API response
- `workflow_id.txt` — workflow ID when a workflow was created or updated
- `bucket_id.txt` — bucket ID when a bucket attachment was resolved

It does not ingest files, poll status, retrieve X-Ray, or retrieve extract
output. Use `run_extraction.py` for that full local path.
