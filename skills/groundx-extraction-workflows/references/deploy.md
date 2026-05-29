# Deploy A Finished YAML

Use this when `prompt.yaml` is finished and the next step is registering or
attaching the workflow.

## Decision Table

| Situation | Use |
| --- | --- |
| Agent has GroundX MCP tools and is doing live workflow create/update/attach | `groundx-api` MCP tools |
| User wants one local deploy command for a finished YAML | `templates/deploy_workflow.py` |
| User wants deploy + ingest + poll + X-Ray + extract | `templates/run_extraction.py` |

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

Set `GROUNDX_API_KEY` in `.env` or in the shell environment. Leave API keys out
of prompts and command-line arguments.

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

## Interactive MCP Recipe

Use this path when GroundX MCP tools are visible in the agent session:

1. Compile the YAML to `workflow.json`.
2. Use `groundx-api/references/06-workflows.md` for the exact
   `workflow_create` or `workflow_update` arguments. Pass the compiled workflow
   fields from `workflow.json`; do not hand-build a different schema. Use
   `workflow_update` only when you already have the existing workflow ID.
3. Save the returned workflow ID.
4. Attach it with `workflow_add_to_id` for a bucket/group or
   `workflow_add_to_account` for the account default.

Minimal field mapping:

| Artifact or target | MCP tool | What to pass |
| --- | --- | --- |
| New compiled workflow | `workflow_create` | Top-level fields from `workflow.json`: `name`, `chunkStrategy`, `sectionStrategy`, `steps`, and `extract` when present. |
| Existing workflow | `workflow_update` | `id` set to the existing workflow ID, plus only the compiled fields that should change. |
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

## Outputs

`deploy_workflow.py` writes:

- `workflow.json` — compiled workflow body
- `deploy.json` — status, workflow action, attachment target, and API response
- `workflow_id.txt` — workflow ID when a workflow was created or updated
- `bucket_id.txt` — bucket ID when a bucket attachment was resolved

It does not ingest files, poll status, retrieve X-Ray, or retrieve extract
output. Use `run_extraction.py` for that full local path.
