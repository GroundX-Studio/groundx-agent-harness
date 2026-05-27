# Workflows

This reference covers the ten workflow operations: creating, listing, getting, updating,
and deleting workflow definitions; looking up the account-level workflow assignment;
assigning and removing a workflow from the account; and assigning and removing a workflow
from a specific group or bucket.

## 1. Workflow overview

A workflow defines the agentic processing pipeline applied to documents during ingest.
`processLevel` controls whether GroundX runs that agentic reprocessing at all:
`full` runs OCR / text extraction, chunking, and the workflow-configurable agentic
pipeline; `none` runs OCR / text extraction and basic chunking but skips GroundX
agentic reprocessing. The workflow controls the details of *how* the `full` pipeline
behaves — chunking strategy, section strategy, custom LLM steps, and extract agent
definitions.

Workflows can also normalize language for RAG: use ingest-time steps to translate
non-English documents into English, and either pre-translate queries or customize the
`search-query` stage to translate/rewrite queries into English before retrieval. If you
do not normalize, keep one language per bucket and configure the bucket for that
language.

For a full conceptual explanation of the pipeline, steps, element types, fields,
strategies, and SDK objects, see `guides/09-workflows.md`.

### 1.1 Workflow scope hierarchy

Workflows can be assigned at three levels. More specific assignments override broader ones:

1. **Account level** — applies to all ingested files by default
2. **Group or bucket level** — overrides the account-level workflow for files in that group or bucket
3. **Document processing depth** — `processLevel` can opt an individual document out of
   the agentic workflow pipeline by using `none` (§1.2 in 02-documents.md)

### 1.2 Workflow fields

| Field | Description |
|---|---|
| `workflowId` | UUID assigned at creation |
| `name` | Display name |
| `chunkStrategy` | How document content is chunked: `element` (by structural element) or `size` (by approximate token size) |
| `sectionStrategy` | How sections are handled: `chunks` (multiple chunks per section) or `page` (one section per page) |
| `steps` | Custom processing steps — see §1.3 and `guides/09-workflows.md` §6 |
| `extract` | Extract agent definitions |

### 1.3 Custom LLM steps

Any pipeline step can be configured with either a custom prompt (using GroundX's
built-in LLM) or a custom LLM endpoint.

#### Pipeline-stage identifiers vs output field names

There are two distinct vocabularies that share a prefix and are easy to confuse: the
nine **pipeline-stage identifiers** (the keys on `WorkflowSteps`) and the eight
**output field names** (the values accepted by `WorkflowStepConfig.field`).

| Pipeline-stage identifier (`WorkflowSteps` key / wire form) | Output field name (`WorkflowStepConfig.field` value) | Description |
|---|---|---|
| `doc-summary` | `doc-sum` | Document-level summary stage. |
| `doc-keys` | `doc-keys` | Document-level keywords stage. |
| `sect-summary` | `sect-sum` | Section-level summary stage. |
| `sect-instruct` | _(no `field=` value — see below)_ | Section-level instructions stage. |
| `sect-keys` | `sect-keys` | Section-level keywords stage. |
| `chunk-summary` | `chunk-sum` | Chunk-level summary stage. |
| `chunk-instruct` | `chunk-instruct` | Chunk-level instructions stage. |
| `chunk-keys` | `chunk-keys` | Chunk-level keywords stage. |
| `search-query` | _(no `field=` value)_ | Search-query rewriting stage. |
| _(any stage)_ | `text` | Write the agent's text output back into the chunk's primary text. |

Two notes that bite:

- **The `field=` enum is narrower than the stage list.** The canonical `field=` values
  per the SDK's `WorkflowStepConfigField` literal are the eight in the right column
  above. The stage identifiers `sect-instruct` and `search-query` are
  **not** in that literal — and the server **silently drops them to `null`** when
  passed (no error, no rejection — just `field` ends up unset on the stored workflow).
  Don't use a stage name where a field name is expected; the SDK literal is the
  authoritative list.
- **Per-stage element-type targeting.** Each step configuration targets one or more
  element types (`all`, `paragraph`, `table`, `figure`, `json`, `table-figure`) — these
  appear as the keys on the `WorkflowStep` SDK class. On the wire the key is `table-figure`;
  the SDK attribute is `table_figure` (and `all` / `json` become `all_` / `json_` in
  Python because they collide with builtins).

See `references/12-python-sdk-objects.md` §6–§9 for the full SDK class details and
the same vocabulary table.

#### Engine configuration

To use a **custom LLM endpoint** instead of GroundX's built-in model for a step,
supply an `engine` object. The same field exists on the wire and on the
`WorkflowEngine` SDK class — wire form is camelCase, SDK form is snake_case:

| Wire/REST key | Python SDK attr | Description |
|---|---|---|
| `apiKey` | `api_key` | Bearer token for the custom LLM endpoint. |
| `baseURL` | `base_url` | Base URL of an OpenAI chat completion-compatible endpoint. |
| `engineID` | `engine_id` | Model name to include in the request. |
| `service` | `service` | Identifies the kind of endpoint — see §1.3.1 below. The field name is `service` on **both** wire and SDK; earlier versions of this reference incorrectly called it `serviceType`. |
| `reasoningEffort` | `reasoning_effort` | One of: `minimal`, `low`, `medium`, `high`. |

See `references/12-python-sdk-objects.md` §3 for the `WorkflowEngine` constructor
example.

### 1.3.1 service vocabulary

`service` is a label describing the kind of OpenAI-compatible endpoint the
engine points at. In practice it does almost nothing — its only behavior is that
two values prepopulate `baseURL` when `baseURL` is not explicitly set. Beyond
that, it is account metadata. The **canonical** values (those listed in the SDK's
`WorkflowEngineService` literal) are:

| Value | Behavior |
|---|---|
| `openai` | Prepopulates the public OpenAI `baseURL`. Override by setting `baseURL` explicitly. |
| `openai-base64` | Same prepopulation as `openai`, but images are base64-encoded into the request payload instead of referenced by URL. Use this against any OpenAI-compatible endpoint — including a hosted one — when the model cannot fetch URLs (network-isolated, private deployment, or the provider doesn't accept image URLs). |
| `azure` | Prepopulates the Azure OpenAI `baseURL`. Override by setting `baseURL` explicitly. |
| `deep-infra` | Account metadata only — no prepopulation. `baseURL` must be supplied. Use for a DeepInfra-hosted endpoint. |
| `hosted` | Account metadata only — no prepopulation. `baseURL` must be supplied. Use for any other third-party-hosted OpenAI-compatible endpoint. |

Only `openai` and `azure` (and their `-base64` variants) actually drive endpoint
behavior. The other values are labels for accounting and reporting; the request
is determined by the explicit `baseURL`, `engineID`, and `apiKey`. Pick whichever
value most accurately describes the deployment.

The server currently still accepts the legacy value `eyelevel` (used historically
for EyeLevel-self-hosted endpoints), but it was removed from the SDK
`WorkflowEngineService` literal — pass `hosted` (with an explicit `baseURL`) for
forward-compatibility.

For configuring **custom prompts** using GroundX's built-in LLM, use the
`WorkflowStepConfig` / `WorkflowPromptGroup` SDK objects described in
`guides/09-workflows.md` §6.

All `steps` and `extract` fields are optional — omit them to use GroundX defaults.

## 2. workflow_create / POST /v1/workflow

Create a new workflow definition. All fields are optional — creating a workflow with no
fields creates a default-configuration workflow.

**MCP:**
```json
{
  "name": "technical-docs",
  "chunkStrategy": "element",
  "sectionStrategy": "chunks"
}
```
Tool: `workflow_create` → returns `workflow.workflowId`

**REST:**
```http
POST /v1/workflow
X-API-Key: YOUR_API_KEY
Content-Type: application/json

{
  "name": "technical-docs",
  "chunkStrategy": "element",
  "sectionStrategy": "chunks"
}
```

**Response:** `{ "workflow": { "workflowId": "uuid", "name": "technical-docs", ... } }`

## 3. workflow_list / GET /v1/workflow

List all workflow definitions associated with the API key.

**MCP:**
```json
{}
```
Tool: `workflow_list`

**REST:**
```http
GET /v1/workflow
X-API-Key: YOUR_API_KEY
```

**Response:** `{ "workflows": [...] }` — array of workflow objects.

## 4. workflow_get / GET /v1/workflow/{id}

Look up a workflow by its `workflowId` (UUID), or by a `groupId` or `bucketId` to find
the workflow currently assigned to that group or bucket.

**MCP:**
```json
{ "id": "workflow-uuid" }
```
Tool: `workflow_get`

**REST:**
```http
GET /v1/workflow/workflow-uuid
X-API-Key: YOUR_API_KEY
```

**Response:** `{ "workflow": { ... } }` — workflow object.

## 5. workflow_update / PUT /v1/workflow/{id}

Update an existing workflow definition. Supply only the fields to change.

**MCP:**
```json
{
  "id": "workflow-uuid",
  "name": "technical-docs-v2",
  "chunkStrategy": "size"
}
```
Tool: `workflow_update`

**REST:**
```http
PUT /v1/workflow/workflow-uuid
X-API-Key: YOUR_API_KEY
Content-Type: application/json

{
  "name": "technical-docs-v2",
  "chunkStrategy": "size"
}
```

**Input parameters:**

| Parameter | Required | Description |
|---|---|---|
| `id` | yes | UUID of the workflow to update (path) |
| `name` | no | New display name for the workflow (body) |
| `chunkStrategy` | no | Chunking strategy: `element` or `size` (body) |
| `sectionStrategy` | no | Section strategy: `chunks` or `page` (body) |
| `steps` | no | Custom processing steps object (body) |
| `extract` | no | Extract agent definitions object (body) |

**Response:** Updated workflow object.

## 6. workflow_delete / DELETE /v1/workflow/{id}

Delete a workflow definition by its `workflowId`. This removes the definition but does
not affect documents already processed with it.

**MCP:**
```json
{ "id": "workflow-uuid" }
```
Tool: `workflow_delete`

**REST:**
```http
DELETE /v1/workflow/workflow-uuid
X-API-Key: YOUR_API_KEY
```

**Response:** `{ "message": "OK" }`

## 7. workflow_get_account / GET /v1/workflow/relationship

Get the workflow currently assigned at the account level (the default workflow applied
to all files unless overridden).

**MCP:**
```json
{}
```
Tool: `workflow_get_account`

**REST:**
```http
GET /v1/workflow/relationship
X-API-Key: YOUR_API_KEY
```

**Response:** `{ "workflow": { ... } }` — the account-level workflow, if one is assigned.

## 8. workflow_add_to_account / POST /v1/workflow/relationship

Assign a workflow to the account level. This becomes the default for all ingested files
unless a more specific assignment (group, bucket) overrides it.

**MCP:**
```json
{ "workflowId": "workflow-uuid" }
```
Tool: `workflow_add_to_account`

**REST:**
```http
POST /v1/workflow/relationship
X-API-Key: YOUR_API_KEY
Content-Type: application/json

{ "workflowId": "workflow-uuid" }
```

**Response:** `{ "message": "OK" }`

## 9. workflow_remove_from_account / DELETE /v1/workflow/relationship

Remove the account-level workflow assignment. After removal, ingest uses the GroundX
default processing unless a group- or bucket-level workflow is assigned.

**MCP:**
```json
{}
```
Tool: `workflow_remove_from_account`

**REST:**
```http
DELETE /v1/workflow/relationship
X-API-Key: YOUR_API_KEY
```

**Response:** `{ "message": "OK" }`

## 10. workflow_add_to_id / POST /v1/workflow/relationship/{id}

Assign a workflow to a specific group or bucket. Files ingested into that group or bucket
will use this workflow instead of the account-level default.

**MCP:**
```json
{ "id": 1234, "workflowId": "workflow-uuid" }
```
Tool: `workflow_add_to_id`

**REST:**
```http
POST /v1/workflow/relationship/1234
X-API-Key: YOUR_API_KEY
Content-Type: application/json

{ "workflowId": "workflow-uuid" }
```

**Input parameters:**

| Parameter | Required | Description |
|---|---|---|
| `id` | yes | ID of the group or bucket to assign the workflow to (path) |
| `workflowId` | yes | UUID of the workflow to assign (body) |

**Response:** `{ "message": "OK" }`

## 11. workflow_remove_from_id / DELETE /v1/workflow/relationship/{id}

Remove the workflow assignment from the group or bucket identified by `id`. After
removal, the account-level workflow (if any) applies again.

**MCP:**
```json
{ "id": 1234 }
```
Tool: `workflow_remove_from_id`

**REST:**
```http
DELETE /v1/workflow/relationship/1234
X-API-Key: YOUR_API_KEY
```

**Response:** `{ "message": "OK" }`
