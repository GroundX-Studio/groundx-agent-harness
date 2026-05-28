# Python SDK Typed Objects

> **Scope:** this reference is for **using** the GroundX Python SDK from your own code
> (consumer-side). For **contributing to the SDK repo itself** (fixing a bug in
> extract, adding a `groundx[extract]` dep, working with the Fern boundary), use the
> `groundx-python` skill instead — it routes to the SDK repo's own `AGENTS.md` as the
> canonical contribution guide.

Companion to the operation-family references (`02-documents.md`, `03-search.md`,
`06-workflows.md`, etc.) which document the wire form (camelCase JSON dicts as sent over
REST or MCP). This reference documents the **typed object form** the Python SDK exposes —
what classes the SDK wants you to construct, what their attribute names are (snake_case),
and which wire-form keys map to which Python attribute.

**Read this before generating Python SDK code.** The SDK is not a thin wrapper around the
REST shape: it has typed classes, snake_case attribute names, an enum surface that's
narrower than the wire-form documentation suggests in two places, and one element-type
field name that uses `_` in Python and `-` in the wire form.

For wire-form details (REST examples, MCP tool calls, validation messages), use the
operation-family reference files. This file is exclusively about the Python class
surface.

## How to read each section

Each typed object has:

- A **REST/wire ⇄ SDK attribute** table: `Wire key | SDK attr | Type | Required | Notes`.
- A minimal Python constructor example.
- Cross-link to the operation reference where the wire form is documented.

All classes are imported from the top-level `groundx` package:

```python
from groundx import (
    Document,
    DocumentUpdate,
    WorkflowEngine,
    WorkflowPrompt,
    WorkflowPromptGroup,
    WorkflowStep,
    WorkflowStepConfig,
    WorkflowSteps,
)
```

## 1. Document

The single-document descriptor passed to `client.ingest(documents=[...])`. Used for both
local-file and remote-URL ingest from the SDK helper. See `02-documents.md` §3 for the
local pre-signed-URL flow `client.ingest()` runs under the hood.

| Wire key | SDK attr | Type | Required | Notes |
|---|---|---|---|---|
| `bucketId` | `bucket_id` | `int` | yes | Target bucket. |
| `filePath` | `file_path` | `str` | yes | Local file path *or* remote URL. |
| `fileName` | `file_name` | `Optional[str]` | no | Display name; defaults to URL/path filename. |
| `fileType` | `file_type` | `Optional[DocumentType]` | no | One of the values listed in `02-documents.md` §1.3. |
| `processLevel` | `process_level` | `Optional[ProcessLevel]` | no | `"none"` or `"full"` (default `"full"`). |
| `searchData` | `search_data` | `Optional[Dict[str, Any]]` | no | Custom search metadata. |
| `filter` | `filter` | `Optional[Dict[str, Any]]` | no | Pre-filter metadata. |

```python
from groundx import Document
Document(
    bucket_id=1234,
    file_path="/local/path/report.pdf",
    file_name="report.pdf",
    file_type="pdf",
    process_level="full",
    search_data={"source": "q3-batch"},
)
```

## 2. DocumentUpdate

Passed as a list to `client.documents.update(documents=[...])`. Each entry mutates one
document's `fileName`, `filter`, or `searchData`. Wire form documented at
`02-documents.md` §11.

| Wire key | SDK attr | Type | Required | Notes |
|---|---|---|---|---|
| `documentId` | `document_id` | `str` | yes | UUID of the document to update. |
| `fileName` | `file_name` | `Optional[str]` | no | New display name. |
| `filter` | `filter` | `Optional[Dict[str, Any]]` | no | Replaces existing (not merged). |
| `searchData` | `search_data` | `Optional[Dict[str, Any]]` | no | Replaces existing (not merged). |

```python
from groundx import DocumentUpdate
client.documents.update(documents=[
    DocumentUpdate(
        document_id="9f7c11a6-24b8-4d52-a9f3-90a7e70a9e49",
        filter={"department": "finance", "version": 3},
        search_data={"review_cycle": "Q3-2026"},
    ),
])
```

## 3. WorkflowEngine

Custom LLM endpoint configuration for a workflow step. Used inside
`WorkflowStepConfig(engine=...)`. Wire form documented at `06-workflows.md` §1.3.

| Wire key | SDK attr | Type | Required | Notes |
|---|---|---|---|---|
| `apiKey` | `api_key` | `Optional[str]` | no | Bearer token sent as `Authorization` to the LLM endpoint. |
| `baseURL` | `base_url` | `Optional[str]` | no | Base URL preceding `/chat/completion`. |
| `engineID` | `engine_id` | `Optional[str]` | no | Model name placed in the request. |
| `reasoningEffort` | `reasoning_effort` | `Optional[Literal["minimal", "low", "medium", "high"]]` | no | OpenAI reasoning-effort value. |
| `service` | `service` | `Optional[Literal["openai", "openai-base64", "azure", "deep-infra", "hosted"]]` | no | Endpoint kind. **Note:** the field is `service`, not `serviceType` — passing `serviceType` to the server is silently ignored and the actual `service` value gets stored as `""`. The SDK literal lists the canonical values above; the server still accepts the legacy `eyelevel` value but the SDK literal removed it, so pass `hosted` (with an explicit `baseURL`) for forward-compatibility. The `reasoning_effort` literal similarly omits `max`, which the server still accepts. |

```python
from groundx import WorkflowEngine
engine = WorkflowEngine(
    api_key="...",
    base_url="https://api.openai.com/v1",
    engine_id="gpt-4o-mini",
    reasoning_effort="medium",
    service="openai",   # not service_type, not serviceType
)
```

## 4. WorkflowPrompt

A single prompt sent to the LLM at a workflow step. Wire form documented at
`06-workflows.md` §1.

| Wire key | SDK attr | Type | Required | Notes |
|---|---|---|---|---|
| `abbreviated` | `abbreviated` | `Optional[str]` | no | Short version included in chat-history prompt context. |
| `prompt` | `prompt` | `Optional[str]` | no | Full prompt sent to the LLM. |
| `role` | `role` | `Optional[Literal["assistant", "developer", "system", "user"]]` | no | OpenAI chat-completion role. |

```python
from groundx import WorkflowPrompt
WorkflowPrompt(
    abbreviated="Classify this chunk",
    prompt="Classify this chunk into one of: medical_event, injury_detail, or null.",
    role="system",
)
```

## 5. WorkflowPromptGroup

Pairs a system-side `task` prompt with a user-side `request` prompt for a step. Wire
form documented at `06-workflows.md` §1.

| Wire key | SDK attr | Type | Required | Notes |
|---|---|---|---|---|
| `request` | `request` | `Optional[WorkflowPrompt]` | no | User-side request prompt. |
| `task` | `task` | `Optional[WorkflowPrompt]` | no | System-side task prompt. |

```python
from groundx import WorkflowPrompt, WorkflowPromptGroup
group = WorkflowPromptGroup(
    task=WorkflowPrompt(role="system", prompt="You classify document chunks."),
    request=WorkflowPrompt(role="user", prompt="Classify the following chunk."),
)
```

## 6. WorkflowStepConfig

Configures one element-type entry within a `WorkflowStep` — the LLM, the prompt group,
and which output field the model writes to. Wire form documented at
`06-workflows.md` §1.3.

| Wire key | SDK attr | Type | Required | Notes |
|---|---|---|---|---|
| `engine` | `engine` | `Optional[WorkflowEngine]` | no | LLM endpoint config. Omit to use GroundX's built-in LLM. |
| `field` | `field` | `Optional[Literal["doc-sum", "doc-keys", "sect-sum", "sect-keys", "chunk-sum", "chunk-keys", "chunk-instruct", "text"]]` | no | Output field the agent writes to. **Note:** these are the *output field names*, not the *pipeline-stage names* — see §9 below. |
| `includes` | `includes` | `Optional[Dict[str, bool]]` | no | Toggles for optional inputs (e.g. `{"pageImages": True}`). |
| `prompt` | `prompt` | `Optional[WorkflowPromptGroup]` | no | Task + request prompts for this element type. |

```python
from groundx import WorkflowStepConfig
config = WorkflowStepConfig(
    field="chunk-keys",
    includes={"pageImages": True},
    prompt=group,   # from §5 above
)
```

## 7. WorkflowStep

Maps element types to step configs. The SDK exposes one attribute per element type;
`all` is a fallback that applies when a more specific type is not set. Wire form
documented at `06-workflows.md` §1.

| Wire key | SDK attr | Type | Required | Notes |
|---|---|---|---|---|
| `all` | `all_` | `Optional[WorkflowStepConfig]` | no | Trailing underscore in Python because `all` is a Python builtin. |
| `figure` | `figure` | `Optional[WorkflowStepConfig]` | no | |
| `json` | `json_` | `Optional[WorkflowStepConfig]` | no | Trailing underscore in Python because `json` shadows the stdlib module. |
| `paragraph` | `paragraph` | `Optional[WorkflowStepConfig]` | no | |
| `table` | `table` | `Optional[WorkflowStepConfig]` | no | |
| `table-figure` | `table_figure` | `Optional[WorkflowStepConfig]` | no | Hyphen on the wire, underscore in Python. |

```python
from groundx import WorkflowStep
step = WorkflowStep(
    paragraph=config,   # from §6 above
    figure=None,
    json_=None,
    table=None,
    table_figure=None,
)
```

## 8. WorkflowSteps

Maps each pipeline stage to a `WorkflowStep`. Wire form documented at `06-workflows.md`
§1. **All wire keys are hyphenated; all SDK attrs are underscored.**

| Wire key | SDK attr | Type | Required | Notes |
|---|---|---|---|---|
| `chunk-instruct` | `chunk_instruct` | `Optional[WorkflowStep]` | no | |
| `chunk-keys` | `chunk_keys` | `Optional[WorkflowStep]` | no | |
| `chunk-summary` | `chunk_summary` | `Optional[WorkflowStep]` | no | |
| `doc-keys` | `doc_keys` | `Optional[WorkflowStep]` | no | |
| `doc-summary` | `doc_summary` | `Optional[WorkflowStep]` | no | |
| `search-query` | `search_query` | `Optional[WorkflowStep]` | no | |
| `sect-instruct` | `sect_instruct` | `Optional[WorkflowStep]` | no | |
| `sect-keys` | `sect_keys` | `Optional[WorkflowStep]` | no | |
| `sect-summary` | `sect_summary` | `Optional[WorkflowStep]` | no | |

```python
from groundx import WorkflowSteps
steps = WorkflowSteps(
    chunk_summary=step,   # from §7 above
)
client.workflows.create(name="my-workflow", steps=steps)
```

## 9. Pipeline stage identifiers vs output field names

Two distinct vocabularies that share a prefix and are easy to confuse:

| Pipeline-stage identifier (key on `WorkflowSteps` / wire form) | Output field name (value on `WorkflowStepConfig.field`) | Description |
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

**The `field=` parameter doesn't take every stage name.** The canonical values are the
eight in the right-hand column above. Stage names like `sect-instruct`
and `search-query` are **not** in the SDK literal — and the server **silently drops
them to `null`** when passed (no error, no rejection — just `field` ends up unset on
the stored workflow). Always pick from the canonical list above.

The naming pattern for the output fields:

- `<level>-sum` for summary stages → `doc-sum`, `sect-sum`, `chunk-sum`
- `<level>-keys` for keyword stages → `doc-keys`, `sect-keys`, `chunk-keys`
- `chunk-instruct` for the chunk-instructions stage (no `-sum` / `-keys` suffix)

Don't pass a stage identifier where a `field=` value is expected. The SDK enum is the
authoritative list — see §6 above.

## 10. Edge cases worth knowing

A handful of behaviours that bite agents writing typed-SDK Python:

### 10.1 Status enum has a `training` value

The `ProcessingStatus` literal documented at `02-documents.md` §1.1 lists 7 values, but
GroundX returns an additional value, `training`, while the parser is running. Treat it
the same as `processing` in poll loops. (See `02-documents.md` §1.1 for the documented
lifecycle including `training`.)

### 10.2 `progress.complete` may be `None` even when `status == "complete"`

The five `progress` buckets returned by `client.documents.get_processing_status_by_id`
are each `Optional`. A guard is required before indexing — see `02-documents.md` §5 for
the canonical pattern.

### 10.3 Two distinct fields are both called `process_id`

The ingest-job process ID returned by `client.ingest(...)` and the document-lineage
process ID stored on each document record (and copied to every search-result chunk) use
the same name but identify different things. They are not equal. See `02-documents.md`
§10 for the disambiguation.

### 10.4 `file_type` canonical values vs accepted variants

The SDK's `DocumentType` literal lists only the canonical names — `"heif"`, `"jpg"`,
`"tiff"`. The server accepts a slightly wider set: the canonical names **plus** the
common spelling variants `"heic"`, `"jpeg"`, `"tif"`. Truly unknown extensions like
`"mp4"` or `"zip"` are rejected with HTTP 415 (`The Content-Type header you provided
is invalid [...]`). Pass the canonical form to stay aligned with the SDK literal. See
`02-documents.md` §1.3 for the full canonical list.

### 10.5 SDK literals are advisory, not enforced — three failure modes

The typed enums on these classes (`DocumentType`, `WorkflowEngineService`,
`WorkflowStepConfigField`, `ProcessingStatus`, etc.) are declared as
`Union[Literal[...], typing.Any]`. The `typing.Any` arm makes the literal
**advisory** — passing an out-of-literal string still parses, and the constructors
silently accept any kwarg (`extra="allow"` on every model). Three failure modes
worth knowing:

- **Misspelled field name (silent)** — `WorkflowEngine(service_type="azure")` does
  **not** raise. The unknown kwarg is **preserved in the SDK's wire body** as
  `{"service_type": "azure"}`, and the server then silently ignores unknown engine
  fields. Net result: `service` ends up unset on the workflow. Type-check at the
  call site (mypy/pyright will catch the literal mismatch even though pydantic
  won't).
- **Out-of-literal `service` value (silent server-side coercion)** — known legacy
  values like `service="eyelevel"` are sent over the wire and stored as-is. **But
  truly unknown values like `service="oepnai"` (typo) or `service="totally-bogus"`
  are silently coerced to `"hosted"` by the server** — no error, no warning, the
  workflow ends up with `service="hosted"`. The server validates against an internal
  allowlist (current canonical + a few legacy values + an empty-string sentinel) and
  falls back to `hosted` for everything else. This is the single biggest typo-footgun
  in the API surface.
- **Out-of-literal enum on other endpoints (silent server-side null)** — for
  `WorkflowStepConfig.field`, an unknown value like `field="sect-instruct"` returns
  HTTP 200 but the stored `field` ends up `null`. Same shape: parses fine in the SDK,
  silently dropped on the server.

Treat the literals as the *target* surface to write against; treat the lack of a
runtime exception as a footgun, not a green light. Use mypy/pyright to catch literal
mismatches at the call site, since neither pydantic nor the server will raise.

### 10.6 Two SDK attributes use trailing underscores

`WorkflowStep.all_` and `WorkflowStep.json_` carry trailing underscores because `all`
and `json` are Python keywords / stdlib module names. The wire form is just `all` and
`json`.
