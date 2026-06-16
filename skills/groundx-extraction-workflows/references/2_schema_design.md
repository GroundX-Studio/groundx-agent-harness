# 2. Schema design

The YAML schema is the durable artifact. Every other output of this skill
derives from it. This reference describes how to author one well.

## 1. Final groups, workflow groups, and workflow execution

A GroundX extraction schema has real top-level groups that define the **final
data object**. These names are the customer-facing output contract after
extraction and reassembly.

The harness-supported workflow execution shape uses those same real top-level
groups. Each real group is assigned to one custom workflow step with
`workflow_step:`.

For new custom extraction workflows, assign each prepared workflow group with
`workflow_step: <custom_step_name>` and put the executable step definitions under
top-level `workflow.custom_steps`. Field-level `workflow_output_key` names the
safe custom output key that maps the step output back to the final field. It
must match `^[a-z][a-z0-9_]{0,63}$`. The YAML field key remains the final
customer-facing JSON key inside its group; use a safe `workflow_output_key`
when the customer-facing key is not a valid custom output key. The
compiler emits the public workflow fields `customSteps`, `outputRoutes`,
`leafFields`, and optional workflow-level `template`; X-Ray readback uses
`customChunkOutputs`, `customSectionOutputs`, and `customDocumentOutputs`.

The harness compiler accepts only the custom workflow shape. Define each
executable step under `workflow.custom_steps`, then assign each workflow group to
one step with `workflow_step:`. The SDK preparation layer emits `customSteps`,
`outputRoutes`, and `leafFields`; local X-Ray readback uses
`customChunkOutputs`, `customSectionOutputs`, or `customDocumentOutputs`.

Use step kinds to describe the extraction shape:

| Step kind | Output shape | Typical use |
|---|---|---|
| `instruct` | One flat object | Per-document fields that appear once per file |
| `keys` | Array of objects | Repeating records such as charge lines, line items, transactions, or service rows |
| `summary` | Array of objects | A second repeating record type such as physical meters or usage records |

For example, a custom step named `charge_lines` uses `kind: keys` because it
extracts many records with the same shape. Each chunk returns zero or more
complete charge objects, and GroundX aggregates those objects into an array.
Do not use `kind: keys` for a field that should appear once in the final JSON;
use `kind: instruct` for those fields.

The `level` controls where the step runs:

| Level | Readback map | Typical use |
|---|---|---|
| `chunk` | `customChunkOutputs` | Most extraction work; each chunk sees local text and page evidence |
| `section` | `customSectionOutputs` | Section-level summaries or records when chunks are too narrow |
| `document` | `customDocumentOutputs` | Document-level aggregation when a full-document step is supported |

`kind: instruct` is invalid with `level: document` in the harness validator.

The harness intentionally does not load `domain:` or `slot:` YAML forms. Use the
public GroundX Python SDK helper directly when you need SDK-level YAML loading
outside the harness templates. Omit any final group a document does not have.

The public syntax walkthrough is
[Structured Extraction Workflow](https://docs.groundx.ai/documentation/structured-extraction-workflow).

### 1.1 `_defs` and unsupported `_pseudo_groups`

`_defs` is a fields-only authoring helper. Shared prompt context belongs under
real final groups, not inside `_defs`.

Do not author `_pseudo_groups` in harness YAML today. The compiler rejects them
with a clear error because that path does not yet have a real compile fixture
covering route generation, validation, readback, and reassembly. If a final
group is too large for one extraction agent, split it into real final groups
only when the user accepts that JSON shape, or escalate the grouping need.

### 1.2 statement: per-document fields

Use this group for fields that appear once per document, even if they are
scattered across pages: account numbers, dates, totals, addresses,
identifiers. Each chunk of the document contributes whichever of these
fields it can see; the platform reconciles them into one flat object.

The `statement` group appears as an object in the extraction output:

```yaml
workflow:
  custom_steps:
    - name: statement_fields
      level: chunk
      kind: instruct

statement:
  workflow_step: statement_fields
  fields:
    invoice_date:
      workflow_output_key: invoice_date
      prompt: { ... }
    total_due:
      workflow_output_key: total_due
      prompt: { ... }
```

```json
{
  "statement": {
    "invoice_date": "2026-01-22",
    "total_due": 38.99
  }
}
```

### 1.3 charges: repeating records

Use this group for records that repeat — typically line items, transactions,
charges, or service rows. Each chunk contributes complete records (not
partial fields of one record); the platform aggregates them into an array.

Compiled custom routes write the output under the authored final group key,
such as `charges`.

```yaml
workflow:
  custom_steps:
    - name: charge_lines
      level: chunk
      kind: keys

charges:
  workflow_step: charge_lines
  fields:
    charge_description_as_printed:
      workflow_output_key: charge_description_as_printed
      prompt: { ... }
    charge_amount:
      workflow_output_key: charge_amount
      prompt: { ... }
```

```json
{
  "charges": [
    {
      "charge_description_as_printed": "Classic Cable - Bulk",
      "charge_amount": 36.75
    },
    {
      "charge_description_as_printed": "Franchise Fee",
      "charge_amount": 1.84
    }
  ]
}
```

### 1.4 meters: utility-style usage records

Use this group for utility-style per-meter usage records: documents where
each meter on a property reports its own consumption over a billing
period (kWh used, gallons consumed, demand readings). The intended
output shape is an array of meter objects, one per physical meter. In harness
YAML, meters are just another workflow group assigned to a custom step. Use
`kind: summary` when the meter extraction should produce a second repeating
record stream distinct from `kind: keys` charge lines.

For documents that contain metered services, define the concrete meter
fields in the group:

```yaml
workflow:
  custom_steps:
    - name: meter_records
      level: chunk
      kind: summary

meters:
  workflow_step: meter_records
  prompt:
    instructions: |
      Extract one record per physical meter or metered service shown in
      the document. Do not invent meters that are not visible.
  fields:
    meter_number:
      workflow_output_key: meter_number
      prompt:
        description: "Meter identifier exactly as printed."
        identifiers: ["Meter #", "Meter Number"]
        instructions: "Return the printed meter identifier."
        type: str
    meter_usage:
      workflow_output_key: meter_usage
      prompt:
        description: "Usage quantity for this billing period."
        identifiers: ["Usage", "Consumption"]
        instructions: "Return the numeric usage value without units."
        type: float
```

The output appears under the `meters` array key:

```json
{
  "meters": [
    {
      "meter_number": "A12345",
      "meter_usage": 1842
    }
  ]
}
```

### 1.5 When the shape does not fit

If the document type is not a per-document object, a repeating record list,
or a metered-usage list (e.g. a free-form report with hierarchical structure),
the schema-first runner does not yet support it cleanly. The right path is to
surface this to the user and either model the document as one of the supported
shapes (typically `statement` with nested fields rendered as JSON strings) or
escalate per §3.3 in `6_known_limitations.md`.

### 1.6 Final group shape and agent load

Use **final group** for a functional grouping of fields in the final output,
such as `statement`, `charges`, or `meters`. Do not split the final data object
only because an agent has too many fields.

As a rule of thumb, keep each workflow group's extraction load to **20 fields
or fewer**. Above that, LLM cognitive load starts to work against
accuracy and consistency. If a final group grows beyond 20 fields, split it into
coherent real final groups only when that output shape is acceptable to the
user. If the final JSON must remain one large object, pause and escalate the
unsupported workflow-grouping need. Do not design one pre-process extraction
agent per field.

## 2. Field anatomy

Every field in the YAML has the same shape. The field key under its group
becomes the JSON key inside that final group.

```yaml
field_key:
  workflow_output_key: field_key
  prompt:
    description: "..."
    format: "..."
    identifiers:
      - "Label 1"
      - "Label 2"
    instructions: "..."
    type: str
```

### 2.1 Required field keys

Every routed field also needs `workflow_output_key`. Use the field key itself
when it already matches `^[a-z][a-z0-9_]{0,63}$`; otherwise choose a safe
snake_case internal key for the workflow output.

| Key | What it does | Required? |
|---|---|---|
| `workflow_output_key` | Safe internal key used by custom workflow output routing | Yes for routed fields |
| `description` | Plain-language description of what the field represents | Yes |
| `format` | Output format constraint | Optional but strongly recommended for dates and codes |
| `identifiers` | Label hints — where to look on the document | Yes |
| `instructions` | Extraction rules and edge cases | Yes |
| `type` | JSON value type: `str`, `int`, `float`, or `[int, float]` | Yes |

### 2.2 description

A short, factual sentence about what this value represents. The model uses
this as the field's purpose statement. Avoid restating the YAML key.

```yaml
description: the primary customer account identifier assigned by the provider
```

### 2.3 format

A constraint on the output format. Most useful for:

- Dates: always specify `YYYY-mm-dd date string` to force ISO format
- Codes: `ISO 4217 three-letter code`, `two-letter US state abbreviation`
- Numerics: leave unset; use `type` instead

```yaml
format: YYYY-mm-dd date string
```

### 2.4 identifiers

A list of labels or phrases that appear next to this value on the document.
The model uses these to locate the value on the page. Include the most
common 1–3 phrasings; do not enumerate exhaustively.

```yaml
identifiers:
  - Account Number
  - Acct #
```

If a value is rarely labeled (e.g. inferred from context), add one
identifier and explain the inference in `instructions`.

### 2.5 instructions

The most important key. A bulleted list of extraction rules, edge cases,
and negative examples. Each line is a directive to the model.

Patterns that produce reliable extractions:

- One concrete rule per line (model handles short directives better than
  long paragraphs)
- A formatting rule: "Strip any spaces or formatting characters"
- A disambiguation rule when the value collides with similar values on the
  page: "Do not confuse with invoice numbers, telephone numbers, or
  barcodes"
- A fallback rule when the value may be missing or implicit: "If no
  explicit invoice number is found, construct one by concatenating account
  number + invoice date in YYYYMMDD format"
- A casing or whitespace rule: "Preserve the original casing exactly as
  printed"

```yaml
instructions: |
  - Capture the full account number exactly as labeled
  - Strip any spaces or formatting characters
  - This must have an explicit "Account Number" label nearby
  - Do not confuse with invoice numbers, telephone numbers, or barcodes
```

### 2.6 type

The expected JSON value type. The model uses this to know whether to
return a string, integer, float, or numeric (either int or float).

```yaml
type: str          # for strings
type: int          # for integers only
type: float        # for floats only
type:              # for "either int or float" (most numeric fields)
  - int
  - float
```

## 3. Group-level prompts

The `charges` group accepts a top-level `prompt.instructions` block that
provides extraction rules for the group as a whole — not per-field, but
about how to identify what counts as one record. This is critical for
distinguishing individual records from subtotal or section-header lines.

```yaml
charges:
  workflow_step: charge_lines
  fields:
    charge_description_as_printed:
      workflow_output_key: charge_description_as_printed
      prompt: { ... }
    charge_amount:
      workflow_output_key: charge_amount
      prompt: { ... }
  prompt:
    instructions: |
      Extract every individual line item.

      A record IS:
        - One distinct service charge with its own line and amount
        - One distinct tax or regulatory fee

      A record is NOT:
        - A section header or subtotal
        - A summary line aggregating multiple items
```

A group-level prompt is the single highest-leverage YAML edit when a
`charges`-style group over-extracts subtotals or under-extracts records.

## 4. Hardcoded field names

The GroundX platform requires two hardcoded field names for charge-style
extractions. Use these names exactly in the YAML even if the application
or ground truth uses different names:

- `charge_amount` — numeric value
- `charge_description_as_printed` — verbatim description

Meter identifiers belong in the `meters` group unless the downstream charge
schema explicitly needs a meter identifier on each charge row.

The comparison harness matches by field name and scores null-vs-miss; answer
keys are JSON in the runner's output shape with field names that match the YAML.
See §1 in `6_known_limitations.md` for the platform-locked charge field names.

## 5. A worked example

`skills/groundx-extraction-workflows/examples/utility-invoice/prompt.yaml` is a
synthetic invoice-shaped schema: `statement`, `charges`, and `meters` groups with
custom workflow steps, per-field prompts, a group-level prompt that distinguishes
line items from subtotals, and inline business-logic metadata. Read it before
authoring a new schema for any invoice-shaped document.
`examples/insurance-claim/prompt.yaml` is the non-invoice custom-step
counterpart. Real customer schemas live out-of-repo, never in the skill.
