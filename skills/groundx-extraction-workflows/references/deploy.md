# Deploy A Finished YAML

Before any command here creates local output, read [`local-artifact-closeout.md`](./local-artifact-closeout.md). Planned work must initialize and use its exact absolute run root. Ad-hoc work uses one dedicated root. Settle or hand off useful results, delete raw evidence, verify absence, and report what remains.

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
- `_workflow_source.py`
- `requirements.txt`
- `.env.sample` as `.env`

Concrete setup:

```bash
SKILL_DIR=/absolute/path/to/groundx-extraction-workflows
cp "$SKILL_DIR/templates/deploy_workflow.py" .
cp "$SKILL_DIR/templates/_workflow_source.py" .
cp "$SKILL_DIR/templates/requirements.txt" .
cp "$SKILL_DIR/templates/.env.sample" .env
python -m pip install -r requirements.txt
```

Use one credential mode in `.env` or the shell environment. Ordinary runs use
`GROUNDX_API_KEY`. Delegated runs use `PARTNER_API_KEY` plus
`CUSTOMER_USERNAME`; the partner key identifies the privileged actor and the
customer username owns the workflow, bucket, ingest, and readback. Do not set
`GROUNDX_API_KEY` with either delegated variable. The templates reject missing
or mixed mode configuration before calling the SDK.

Use a prod key for live structured extraction. Dev extraction does not currently work; only use
dev for deploy/run/extract if an operator explicitly confirms it is available.
For dev non-extraction API/debug calls, also set
`GROUNDX_BASE_URL=https://devapi.groundx.ai/api`. For prod, leave
`GROUNDX_BASE_URL` unset. Leave API keys out of prompts and command-line arguments.

## Local Deploy Commands

Create a new workflow from the extraction work directory:

```bash
python deploy_workflow.py \
  --yaml prompt.yaml \
  --out "$RUN_ROOT/deploy" \
  --workflow-name customer-workflow-v1 \
  --create-bucket-name customer-bucket-v1
```

Update an existing workflow:

```bash
python deploy_workflow.py \
  --yaml prompt.yaml \
  --out "$RUN_ROOT/deploy" \
  --workflow-id workflow-123 \
  --bucket-id 12345
```

`--yaml` is the path to the YAML file. It can be a filename in the current
directory or a full path. On create, `--workflow-name` is optional and defaults
to the YAML filename without `.yaml`. On update, omitting `--workflow-name`
preserves the existing workflow name; supply it only to rename. `--workflow-id`
switches the command from create to update.

The deploy script validates the authored YAML with `workflows.validate`, then
submits the exact same bytes to `workflows.create` or `workflows.update`, except
for the compiler-generated legacy update case below. Cashbot is the only
workflow compiler. Local tools read authored custom steps only to estimate
request fanout.

Use the product YAML upload path when certifying product persistence or legacy
normalization. The local SDK command proves source-YAML validation, server
compilation, workflow creation or update, and optional attachment.

This local SDK path is not the same as the product YAML upload path. It bypasses
upload-time normalization, persisted source handling, and any internal legacy
YAML-to-v1 translation owned by the platform. Use it for local deployment,
diagnostics, or controlled extraction runs. Do not use it as proof that a user
upload, product upload, or legacy YAML normalization path works.

## Engine Changes

When the only intended change is a model endpoint, edit the engine in the
authored YAML, validate that complete source, and submit the same exact YAML to
`workflows.update(..., yaml=...)` or `workflow_update`'s `yaml` field. Do not
construct an update from JSON workflow readback. It is compiled state and can
omit the private extraction definition. If the local authored YAML is missing
or not known to be current, retrieve the stored source with raw REST
`GET /v1/workflow/{id}?format=yaml`, then validate and resubmit that complete
YAML. Current MCP and Python SDK readback do not return authored YAML safely.
Compiled-JSON workflows have no stored authored YAML source.

For a compiled-JSON workflow, do not use `deploy_workflow.py` or send an
engine-only partial. Regenerate the complete structured definition from its
owning source and submit the entire definition in one update. Do not reconstruct
it from workflow readback. If the authoritative source is unavailable, recreate
or migrate the workflow through the YAML-authored path before changing engines.

If recovered source contains `legacy_policy_default_provenance`, standalone
validation rejects the compiler-owned field. Submit that YAML directly with an
update, or run `deploy_workflow.py --skip-validate`. The update endpoint
validates it against the stored workflow before writing.

Set a workflow-wide default under `workflow.engines`:

```yaml
workflow:
  engines:
    all:
      engineID: gpt-5.5
      service: openai
      type: all
```

`workflow.engines` sets defaults. Explicit per-step engines take precedence for
the matching custom-step elements. To change every step, update or remove each
existing per-step engine in the same complete YAML.

For one custom step, keep the complete `workflow.custom_steps` list and put the
same `engine` fields under each intended config element:

```yaml
workflow:
  custom_steps:
    - name: statement_fields
      level: section
      kind: instruct
      config:
        all:
          engine:
            engineID: gpt-5.5
            service: openai
```

Preserve every existing group, field, route, prompt, strategy, and non-target
custom step. For AWS Bedrock Gemma 4, use service `bedrock`, engine ID
`google.gemma-4-31b`, and the Bedrock Mantle base URL.

`service: bedrock` is opt-in. It sends every page image as an AWS S3 reference, so the runtime must use S3 file storage that the AWS identity behind the Bedrock request can read. For a Bedrock API key, this is the IAM principal behind the key. Existing `s3://` references pass through. Internal GroundX page URLs are converted to the configured bucket. Inline images, arbitrary HTTPS image URLs, and non-S3 storage are rejected before dispatch. The selected engine's positive `maxImages` caps the combined image count; omission leaves image count uncapped. The independent serialized-request guard may still remove images by byte size. Keep real credentials out of committed files and saved run evidence.

## Optional Prod MCP Recipe

Use this path only when GroundX MCP tools are already visible in the agent
session and the target environment is prod. GroundX MCP is optional and prod-only.
For dev API/debug work, use the local Python SDK with
`GROUNDX_BASE_URL=https://devapi.groundx.ai/api`; do not run live structured
extraction in dev unless an operator explicitly confirms it is available.

1. Validate the authored YAML with `workflow_validate`, except recovered legacy
   YAML containing `legacy_policy_default_provenance`, which goes directly to
   update as described above.
2. Create or update with the same authored YAML in the `yaml` field. Do not
   translate it into a structured workflow body. Use `workflow_update` only
   when you already have the existing workflow ID.
3. Save the returned workflow ID.
4. Attach it with `workflow_add_to_id` for a bucket/group or
   `workflow_add_to_account` for the account default.

Minimal field mapping:

| Source or target | MCP tool | What to pass |
| --- | --- | --- |
| New authored YAML | `workflow_create` | `name` and the exact YAML text in `yaml`. |
| Existing workflow | `workflow_update` | `id` set to the existing workflow ID, plus the exact YAML text in `yaml`. |
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
  --out "$RUN_ROOT/deploy" \
  --workflow-name customer-workflow-v1 \
  --dry-run
```

Dry run reads the YAML, writes exact `prompt.yaml` plus `deploy.json`, and prints
the planned workflow action. It does not call GroundX, does not claim server
validation, and does not require `GROUNDX_API_KEY`.

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

The script reads credentials and optional `GROUNDX_BASE_URL` from the process
environment, `.env` in the current directory, or `.env` beside the YAML file.
Use either `GROUNDX_API_KEY`, or both `PARTNER_API_KEY` and
`CUSTOMER_USERNAME`. In delegated mode, one SDK request-options value adds
`X-Customer-Key` to every customer-scoped API call. The object-store presigned
upload does not receive that header. Do not pass API keys as command-line arguments.

Use a different `GROUNDX_API_KEY` or `PARTNER_API_KEY` per environment. Prod live extraction leaves
`GROUNDX_BASE_URL` unset or sets `https://api.groundx.ai/api`. Dev API/debug
calls use `GROUNDX_BASE_URL=https://devapi.groundx.ai/api`, but dev structured
extraction is unavailable unless an operator confirms otherwise.

## Outputs

`deploy_workflow.py` writes:

- `workflow.json` — server workflow readback after create or update
- `deploy.json` — status, workflow action, attachment target, and API response
- `workflow_id.txt` — workflow ID when a workflow was created or updated
- `bucket_id.txt` — bucket ID when a bucket attachment was resolved

It does not ingest files, poll status, retrieve X-Ray, or retrieve extract
output. Use `run_extraction.py` for that full local path.
