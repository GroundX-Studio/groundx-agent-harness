# 3. Prompt pipeline

How the YAML becomes the actual text the LLM receives. Read this when
designing a new group, choosing between extraction shapes, or debugging
why a field is or is not producing output.

## 1. Overview

```
prompt.yaml
  │
  ▼
prepare → final groups + workflow groups + route map (groundx.extract)
  │
  ▼
parse workflow groups → Group + ExtractedField data model
  │
  ▼
render → field-spec text + field-description bullets + group definition
  │
  ▼
wrap → "request" message (user) + "task" message (developer)
  │
  ▼
register → WorkflowStepConfig wired into a workflow slot
  │
  ▼
upload → server-side per-chunk LLM calls produce JSON
```

The compiler (`skills/groundx-extraction-workflows/templates/compile_workflow.py`)
does steps 2-4 inline. Steps 5-6 happen on the GroundX platform.

## 2. Step 1: YAML parsing

The SDK parses the YAML into a typed data model:

- Real top-level YAML groups define the final data object.
- `_defs`, when present, expands into final groups before workflow routing.
- `_pseudo_groups`, when present, defines workflow-only groups. These groups are
  addressable by authored name in workflow artifacts, but do not appear in final
  output.
- The SDK emits `workflow_field_paths`, a route map from workflow field aliases
  to final-output JSON Pointer paths such as `/statement/account_number`.
- Each entry under a prepared workflow group's `fields:` block becomes an `ExtractedField`
  with a `Prompt` carrying its description, format, identifiers,
  instructions, and type
- Each field's `attr_name` is set automatically from its YAML key — this
  is the JSON key the LLM is instructed to use in workflow output

The data model is read-only; the YAML is the only edit surface.

## 3. Step 2: Field rendering

Each `ExtractedField` renders to a structured spec block:

```
## field_key

Field:                  field_key
Description:            <description>
Format:                 <format>
Example Identifiers:    <identifiers, comma-separated>
Special Instructions:
<instructions>
```

All fields in one group concatenate into the field-spec block the user
message will inject.

A condensed version — the field-description bullets — is also produced
for the developer message:

```
- **field_key** - <description>
- **other_key** - <description>
```

## 4. Step 3: Group prompt rendering

If the YAML group has a top-level `prompt.instructions` block, it renders
as:

```
# <group_name> Definition

<instructions>
```

This becomes the "Extraction Guidelines" section in the user message for
that group.

## 5. Step 4: Wrapper templates

The runner wraps the rendered blocks in two messages — one user
("request"), one developer ("task"):

- **User message (request):** field-spec block + group definition (for
  `charges`-style groups) + final-notes about output format. This is the
  per-extraction prompt the LLM acts on.
- **Developer message (task):** identity + process steps + the
  field-description bullets + few-shot examples. This is the system-level
  context.

The default wrapper templates are inlined in `compile_workflow.py`. To
customize wrapper text, provide a prompt-manager or wrapper module through
`EXTRACT_WRAPPER_MODULE`; use `templates/prompt_manager.py` for the minimal
adapter contract. See section 3 in `4_sdk_integration.md`.

## 6. Choosing chunk_instruct vs chunk_keys

Each workflow group is wired to one of the proven workflow slots. The choice
determines how the platform reconciles per-chunk outputs.

### 6.1 chunk_instruct

- **Output shape:** one flat object
- **Cross-chunk behavior:** reconcile and merge (each chunk contributes
  partial fields)
- **Used for:** per-document workflow groups, often a `statement` group or a
  pseudo split such as `statement_identity`
- **Mental model:** assembling one puzzle from pieces scattered across
  the document

A statement field like `invoice_date` may appear on chunk A only; an
address field may appear on chunk B only. Both chunks return JSON with
just their visible fields; the platform merges them into one flat
top-level object.

### 6.2 chunk_keys

- **Output shape:** array of objects
- **Cross-chunk behavior:** aggregate (each chunk contributes complete
  records)
- **Used for:** repeating workflow groups, often a `charges` group
- **Mental model:** collecting stamps — each chunk adds more instances of
  a record

Each chunk that contains a record returns a complete record object. The
platform appends them into the `account_charges` array. There is no
reconciliation problem because each record is self-contained.

### 6.3 Decision rules

| Question | If yes |
|---|---|
| Does the field appear at most once per document? | `chunk_instruct` |
| Are there many of these, each with the same shape? | `chunk_keys` |
| Will the same field appear in two chunks with different values? | `chunk_keys` (the values are different records, not a reconciliation conflict) |

If a field is conceptually one-per-document but accidentally appears in
multiple chunks (e.g. a footer reprints the account number on every
page), `chunk_instruct` handles it correctly — the reconciliation step
de-duplicates identical values.

If a field is conceptually repeating but the runner produces one merged
object instead of an array, the workflow group is wired to the wrong slot.
Move that workflow group to a repeating slot, or route the field through a
different pseudo group.

## 7. Current extraction QA field contract

The extraction QA microservice has a stricter field-slot contract than
generic workflow customization. This is current platform behavior, not
the long-term ideal API. The expected evolution is more override-safe
fields at each level so extraction can coexist with RAG without taking
over RAG fields.

| Extraction category | Stage to run | Output field to write | Why |
|---|---|---|---|
| `statement` fields | `chunk_instruct` | `sect-sum` | Statement extraction needs chunk-level prompts, but the QA microservice reads statement candidates from the section summary field. |
| `charges` fields | `chunk_keys` | `chunk-keys` | Charges are repeating chunk-level records and `chunk-keys` is not used by default RAG. |
| `meters` fields | `chunk_summary` | `chunk-sum` | Meter extraction needs an available chunk-level field the QA microservice can read. |

The `statement` mapping is intentionally odd: running the extraction at
`sect_summary` would operate over multi-page sections instead of
individual chunks, which is too coarse for statement-field extraction.
So the workflow runs a `chunk_instruct` agent, then writes the output
into `sect-sum` because that field is propagated and checked by the QA
microservice. The write is still a complete overwrite of `sect-sum`;
the normal section summary is not retained.

For hybrid RAG + extraction today, only `chunk-keys` is relatively safe.
It is not generated by default and is the usual home for charge-style
data extraction. Overriding `chunk-sum` has a massive RAG impact because
it replaces `suggestedText`, which search returns and which applications
usually send to an LLM. Overriding `chunk-instruct` has a major impact
for tables and figures because the default table/figure processing
instructions are no longer generated. Overriding `doc-sum`,
`doc-keys`, or `sect-sum` removes document or section context from
search; it may be technically possible, but it weakens RAG and usually
has little extraction benefit.

`search-query` is a query-time rewrite stage for long search queries,
not a data-ingest output field. Do not use it for extraction output.

## 8. What the LLM sees at runtime

For every chunk the platform processes, the LLM receives:

1. The developer message (process instructions + field-description bullets
   + few-shot examples)
2. The user message (field-spec block + group definition + the chunk's
   text content + the chunk's page images, if `pageImages: True` is set)

The LLM responds with a JSON object whose keys are the field `attr_name`
values from the YAML. The platform either reconciles (`chunk_instruct`) or
aggregates (`chunk_keys`) those responses across chunks, then runs a QA
pass, then makes the result available via `get_extract()`.

When `_pseudo_groups` are used, that raw workflow output is an intermediate
shape. Arcadia reassembles it into the final data object with
`workflow_field_paths` before final scoring/output and final-group business
logic that depends on the customer-facing shape.

For debugging — if a field is missing from the final JSON, the per-chunk
LLM response is visible via `get_xray()`. See §3 in `6_known_limitations.md`
for when to use X-Ray vs. tightening the prompt.
