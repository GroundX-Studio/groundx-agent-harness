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
- `.env.sample` as `.env`

Concrete setup:

```bash
SKILL_DIR=/absolute/path/to/groundx-extraction-workflows
cp "$SKILL_DIR/templates/deploy_workflow.py" .
cp "$SKILL_DIR/templates/compile_workflow.py" .
cp "$SKILL_DIR/templates/validate_workflow_json.py" .
cp "$SKILL_DIR/templates/.env.sample" .env
```

Set `GROUNDX_API_KEY` in `.env` or in the shell environment. Leave API keys out
of prompts and command-line arguments.

## Local Deploy Command

From the extraction work directory:

```bash
python deploy_workflow.py \
  --yaml prompt.yaml \
  --out deploy/ \
  --workflow-name customer-workflow-v1 \
  --create-bucket-name customer-bucket-v1
```

`--yaml` is the path to the YAML file. It can be a filename in the current
directory or a full path. `--workflow-name` is optional; without it, the script
uses the YAML filename without `.yaml`.

## Interactive MCP Recipe

Use this path when GroundX MCP tools are visible in the agent session:

1. Compile the YAML to `workflow.json`.
2. Read `workflow.json`; pass `name`, `extract`, and `steps` to `workflow_create`
   or `workflow_update`. Use `workflow_update` only when you already have the
   existing workflow ID.
3. Map `chunk_strategy` from `workflow.json` to the API field `chunkStrategy`.
4. Save the returned `workflow.workflowId`.
5. Attach it with `workflow_add_to_id` for a bucket/group or
   `workflow_add_to_account` for the account default.

Never pass a GroundX API key in MCP tool arguments. The MCP connector/session
owns authentication.

For exact arguments and response shapes, use `groundx-api/references/06-workflows.md`.

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
