# Workflow Pipeline

How to customize the GroundX document processing pipeline using workflows — for
tuning RAG output, building classification systems, or replacing the default pipeline
entirely with structured extraction logic.

## 1. What workflows do

GroundX has a default processing pipeline designed for general-purpose RAG. A
**workflow** lets you modify that pipeline in two ways:

- **Tune it for a specific RAG use case** — inject custom prompts at any processing
  stage to improve retrieval for a particular domain or document type
- **Replace it with structured extraction** — configure the pipeline to produce
  classification output, key-value extraction, or any other structured data instead
  of (or alongside) RAG chunks

Workflows are defined once and then assigned to a bucket, a group, or the account
as a whole. Every document ingested into that scope is processed by the assigned
workflow. See `references/06-workflows.md` for CRUD operations and scope assignment.

## 2. The default pipeline

The core challenge in document RAG is context. Large documents must be divided into
searchable chunks, but isolated chunks lose meaning without surrounding context. A
chunk containing "Go on walks / Play Sports / Eat Spaghetti" is uninterpretable
without the heading that preceded it.

GroundX solves this by running agents at multiple scopes — document, section, and
chunk — in sequence, so each scope's output is available to the stages below it.

### 2.1 Pipeline stages

Stages execute in this fixed order:

```
doc-summary → doc-keys → sect-summary → sect-instruct → sect-keys
    → chunk-instruct → chunk-summary → chunk-keys → search-query
```

| Step | Scope | Default behavior | On by default |
|---|---|---|---|
| `doc-summary` | Once per document | Summarizes the full document | Yes |
| `doc-keys` | Once per document | Extracts key terms from the document | Yes |
| `sect-summary` | Once per section | Summarizes each section | Yes |
| `sect-instruct` | Once per section | Custom instruction processing per section | No |
| `sect-keys` | Once per section | Extracts key terms per section | Yes |
| `chunk-instruct` | Per chunk | Custom instruction processing per chunk | No |
| `chunk-summary` | Per chunk | Summarizes each chunk | Yes |
| `chunk-keys` | Per chunk | Extracts key terms per chunk | No |
| `search-query` | Per chunk | Generates a retrieval-optimized search query for this chunk | No |

Steps you do not configure continue to use their GroundX defaults. Steps marked
"Off by default" do nothing unless you define them in your workflow.

### 2.2 Language normalization

Workflows are the supported way to normalize language for RAG when the source corpus and
user queries are not already in the same language. GroundX ingests and stores documents
in their native language by default; it does not automatically translate all content to
English. For English-first retrieval over non-English sources, configure ingest-time
workflow steps to translate the document/chunk text into English, and either
pre-translate user queries before search or customize the `search-query` stage to
translate/rewrite queries into English.

If you do not normalize to English, keep documents in one language per bucket and
configure that bucket for the supported language. Mixed-language buckets reduce search
quality because the indexed chunks, query rewrite, and reranker are no longer operating
against a single language distribution.

### 2.3 Step awareness

Each stage can see the output of all stages that ran before it. A `chunk-summary`
step has access to the document summary (`doc-sum`) and section summary (`sect-sum`)
when processing each chunk. It cannot access the output of other chunks or sections —
only the document-level and section-level context above it in the hierarchy.

This is the mechanism that makes each chunk self-contained: its summary is generated
with full awareness of the document and section it belongs to.

## 3. Element types

Within each step, you can configure behavior differently per **element type** —
the structural classification of the chunk being processed:

| Element type | What it matches |
|---|---|
| `all` | Default for any type not explicitly configured in this step |
| `paragraph` | Text paragraphs |
| `table` | Tabular data |
| `figure` | Images, figures, and diagrams |
| `json` | JSON content |
| `table_figure` | Elements that are both tabular and visual |

Configuring `all` sets a default for every element type in that step. Configuring a
specific type (e.g. `paragraph`) overrides `all` for that type only. Specific-type
configurations always take precedence over `all`. This lets you, for example, apply
one prompt to tables and a different prompt to paragraphs within the same step.

## 4. Fields

Each document element has a set of named **fields** — storage slots where agent
output is written during processing. Fields have default names that correspond to
pipeline stages, but any step can write to any field — the name is a label, not a
constraint.

**Pipeline-stage identifiers vs output field names** — these are two distinct
vocabularies that share a prefix and are easy to confuse. Stage names are
`*-summary`; field names are `*-sum`. Use this table to map between them:

| Pipeline stage (`WorkflowSteps` key) | Output field name (`WorkflowStepConfig.field` value) | Default purpose |
|---|---|---|
| `doc-summary` | `doc-sum` | Document summary |
| `doc-keys` | `doc-keys` | Document key terms |
| `sect-summary` | `sect-sum` | Section summary |
| `sect-instruct` | _(no `field=` value — see below)_ | Section-level instructions |
| `sect-keys` | `sect-keys` | Section key terms |
| `chunk-summary` | `chunk-sum` | Chunk summary |
| `chunk-instruct` | `chunk-instruct` | Chunk-level instructions / custom output |
| `chunk-keys` | `chunk-keys` | Chunk key terms |
| `search-query` | _(no `field=` value)_ | Retrieval-optimized search query |
| _(any stage)_ | `text` | Main text content (overwrites the chunk's primary text) |

**The `field=` enum is narrower than the stage list.** The accepted `field=` values are
the eight in the right column above. The otherwise-valid stage identifiers
`sect-instruct` and `search-query` are **not** valid `field=` values — setting
`field="sect-instruct"` is rejected by the SDK enum. Don't use a stage name where a
field name is expected.

When you define a step with `field="chunk-keys"`, that step's output is written to
the `chunk-keys` slot — even if the step is not the `chunk-keys` stage of the
pipeline. You can repurpose fields for custom output, but repurposing a field is a
complete override: the default RAG output for that field is not also saved.
Extraction workflows that need to preserve RAG should follow the stricter field-slot
contract in `groundx-extraction-workflows/references/3_prompt_pipeline.md` §7.

## 5. Chunking and section strategies

### 5.1 chunk_strategy

Controls how document content is grouped into chunks:

| Value | Behavior | When to use |
|---|---|---|
| `"element"` | Each structural element is its own chunk (one paragraph = one chunk, one table = one chunk, one figure = one chunk) | Structured extraction and classification — ensures one agent pass per discrete element |
| `"size"` | Adjacent elements are merged into chunks of approximate token size | General-purpose RAG where larger context windows per chunk improve retrieval |

For extraction and classification workflows, always use `"element"`. Merging elements
blurs boundaries and makes per-element classification unreliable.

### 5.2 section_strategy

Controls how chunks are grouped into sections:

| Value | Behavior | When to use |
|---|---|---|
| `"chunks"` | Sections are groups of chunks at an approximate size | Standard RAG documents with flowing content |
| `"page"` | Each page is its own section | Extraction pipelines, especially PDFs of concatenated independent sub-documents (e.g. a batch of invoices, where each page is a logically independent document) |

Use `"page"` when pages in a document are logically independent — it prevents
section-level context from bleeding across page boundaries.

## 6. Configuring steps — SDK objects

Workflow steps are configured using a hierarchy of SDK objects. Python names are
used below; TypeScript equivalents use camelCase.

### 6.1 WorkflowPrompt

A single message in the LLM call:

| Field | Description |
|---|---|
| `prompt` | The full prompt text |
| `additional_context` / wire `additionalContext` | Extra instructions appended to the default full request/task prompt. Use this to add workflow-specific context without replacing the default prompt. Limited to 4096 UTF-8 bytes. |
| `abbreviated` | A short summary of the prompt — used in logging |
| `role` | Message role: `"system"`, `"developer"`, `"user"`, or `"assistant"`. Use `"system"` or `"developer"` for the task instruction; `"user"` for the per-element query |

`additionalContext` is additive. Workflow-level `template.CUSTOM_INSTRUCTIONS` stays
the global fallback, and a prompt member's `additionalContext` overrides it only for
that prompt render. It is supported on fixed GPT and EyeLevel default `request` and
`task` prompt members. It is not supported under custom workflow steps, nested
`useExtras` prompt objects, or prompt members that replace the full prompt.

### 6.2 WorkflowPromptGroup

Groups a task and a request into a single prompt definition:

| Field | Description |
|---|---|
| `task` | A `WorkflowPrompt` — the system-level instruction (what to do) |
| `request` | A `WorkflowPrompt` — the per-element query (apply the task to this element) |

### 6.3 WorkflowStepConfig

The full configuration for a step applied to one element type:

| Field | Description |
|---|---|
| `field` | The field name where this step's output is written (e.g. `"chunk-keys"`) |
| `prompt` | A `WorkflowPromptGroup` |
| `includes` | Optional dict of additional context to pass to the agent — e.g. `{"pageImages": True}` to include the page image alongside the text |

### 6.4 WorkflowStep

Applies a `WorkflowStepConfig` to specific element types within one pipeline stage.
Each element type is either a `WorkflowStepConfig` or `None` (use default):

```python
from groundx import WorkflowStep

step = WorkflowStep(
    paragraph=my_config,   # custom config for paragraph elements
    figure=None,           # use default for figures
    json_=None,            # use default for JSON (note underscore — "json" is a Python builtin)
    table_figure=None,     # use default for table_figure elements
)
```

### 6.5 WorkflowSteps

Assigns `WorkflowStep` objects to pipeline stages. Each field corresponds to a
configurable stage; `None` means use the GroundX default for that stage:

```python
from groundx import WorkflowSteps

steps = WorkflowSteps(
    doc_summary=None,       # stage: doc-summary
    doc_keys=None,          # stage: doc-keys
    sect_summary=None,      # stage: sect-summary
    sect_instruct=None,     # stage: sect-instruct
    sect_keys=None,         # stage: sect-keys
    chunk_instruct=None,    # stage: chunk-instruct
    chunk_summary=my_step,  # stage: chunk-summary (custom)
    chunk_keys=None,        # stage: chunk-keys
)
```

## 7. Custom LLM endpoints

In addition to configuring prompts, you can replace GroundX's built-in LLM with your
own OpenAI-compatible endpoint for any step. This is done via the `engine` object
within a step configuration. The same field exists on the wire and on the
`WorkflowEngine` SDK class — wire form is camelCase, SDK form is snake_case:

| Wire/REST key | Python SDK attr | Description |
|---|---|---|
| `apiKey` | `api_key` | Bearer token for your LLM endpoint. |
| `baseURL` | `base_url` | Base URL of an OpenAI chat completion-compatible endpoint. |
| `engineID` | `engine_id` | Model name to include in the request. |
| `service` | `service` | Endpoint kind — see below. The field is named `service` on **both** wire and SDK; earlier versions of this guide called it `serviceType`. |
| `reasoningEffort` | `reasoning_effort` | One of: `minimal`, `low`, `medium`, `high`. |

The canonical `service` values (those listed in the SDK's `WorkflowEngineService`
literal) are `openai`, `openai-base64`, `azure`, `deep-infra`, and `hosted`. Only
`openai` and `azure` (plus the `-base64` variants) actually do anything — they
prepopulate `baseURL` when one isn't supplied. `deep-infra` and `hosted` are
account-metadata labels; `baseURL` must be set explicitly. Use `openai-base64`
when the endpoint cannot fetch image URLs and needs images encoded inline. The
server still accepts the legacy value `eyelevel`, but it was removed from the SDK
literal — pass `hosted` (with an explicit `baseURL`) for forward-compatibility.

**Python SDK form** (use the typed `WorkflowEngine` class — passing a plain dict
will not type-check and risks silent attribute drops if a key is misspelled):

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

See `references/06-workflows.md` §1.3.1 for the full vocabulary and rationale, and
`references/12-python-sdk-objects.md` §3 for the full `WorkflowEngine` field table.

## 8. Workflow output and the X-Ray

After a document is processed, GroundX produces an X-Ray — a structured JSON
representation of every chunk. Each chunk's X-Ray entry carries the field values
written during workflow processing. If your workflow wrote classification output to
`chunk-keys`, that output appears in `chunks[n].json` on each chunk.

The default X-Ray fields (`sectionSummary`, `fileSummary`, `fileKeywords`) correspond
to the default workflow pipeline output. Custom field output is stored in the chunk's
extended data under the field name you specified. See `guides/05-document-understanding.md`
for the full X-Ray schema and field reference.

### 8.1 Default RAG fields and override impact

Unset workflow steps use GroundX defaults. Once a step writes to a field, that field's
normal RAG value is replaced; the platform does not keep both. Current field behavior:

| Stage | Default output field | Default behavior | Search/RAG impact if overridden |
|---|---|---|---|
| `doc-summary` | `doc-sum` | Document summary from the first 20,000 tokens. | Removes document-level summary context from search. |
| `doc-keys` | `doc-keys` | Comma-delimited document keywords, including file name, from the document summary plus the first 20,000 tokens. | Removes document-level keyword context from search. |
| `sect-summary` | `sect-sum` | Section summary, created only when there are at least 10 pages of text; has document summary and document keywords as context. | Removes section-level context from search. |
| `sect-keys` | `sect-keys` | Not generated by default; configurable. | No default RAG impact known; propagation is not well-tested. |
| `chunk-summary` | `chunk-sum` | Chunk summary, exposed as `suggestedText` in X-Ray and search results. | Massive impact: replaces the text search returns and the suggested text sent to an LLM. |
| `chunk-keys` | `chunk-keys` | Not generated by default; configurable. | Usually safe for custom chunk-level output and extraction records. |
| `chunk-instruct` | `chunk-instruct` | Generated by default only for tables and figures; creates temporary processing instructions used by `chunk-summary`. | Major impact for tables and figures; instructions are not persisted to files or databases. |
| `search-query` | none | Query rewrite used by default for search queries over 50 words. | Not a valid ingest output field; do not use for extraction output. |

Most workflow outputs propagate to X-Ray / indexed artifacts. `chunk-instruct` and
`search-query` do not. `sect-keys` may not propagate and has not been relied on as a
stable extraction field.

## 9. End-to-end example — document and chunk classification

This example adds classification to ingest: each document is tagged with a document
class and each chunk with a chunk class.

```python
from groundx import (
    GroundX,
    WorkflowPrompt,
    WorkflowPromptGroup,
    WorkflowStep,
    WorkflowStepConfig,
    WorkflowSteps,
)

client = GroundX(api_key=YOUR_API_KEY)

# 1. Define the classification prompt
system_prompt = """Classify the document and the specific chunk. Respond with pure JSON:
{
    "document_class": "<document class or null>",
    "chunk_class": "<chunk class or null>"
}
Valid document classes: deposition, medical_report, peer_clinical_review
Valid chunk classes: medical_event, injury_detail
Use null if a class does not apply."""

task = WorkflowPrompt(
    abbreviated="Classify document and chunk",
    prompt=system_prompt,
    role="system",
)
request = WorkflowPrompt(
    abbreviated="Classify this document and chunk",
    prompt="Classify this document and chunk",
    role="user",
)

# 2. Build the step configuration
config = WorkflowStepConfig(
    field="chunk-keys",
    includes={"pageImages": True},
    prompt=WorkflowPromptGroup(task=task, request=request),
)

# 3. Apply to paragraph elements at the chunk-summary stage
step = WorkflowStep(paragraph=config, figure=None, json_=None, table_figure=None)
steps = WorkflowSteps(chunk_summary=step)

# 4. Create the workflow
workflow = client.workflows.create(
    name="document-classification",
    chunk_strategy="element",
    steps=steps,
)
workflow_id = workflow.workflow.workflow_id

# 5. Create a bucket and assign the workflow
bucket = client.buckets.create(name="classified-docs")
bucket_id = bucket.bucket.bucket_id

client.workflows.add_to_id(id=bucket_id, workflow_id=workflow_id)

# 6. Ingest documents — they will be processed by the workflow
client.ingest_directory(bucket_id=bucket_id, path="/path/to/documents/")

# 7. Search — results carry the classification output
response = client.search.content(id=bucket_id, query="when did the surgery occur?")
print(response.search.results[0].chunk_keywords)
# → {"document_class": "medical_report", "chunk_class": "medical_event"}
```

## 10. CRUD and assignment operations

For creating, listing, updating, and deleting workflow definitions, and for assigning
workflows at account, group, or bucket scope, see `references/06-workflows.md`.
