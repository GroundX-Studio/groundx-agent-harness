# 2. Schema design

The YAML schema is the durable artifact. Every other output of this skill
derives from it. This reference describes how to author one well.

## 1. Final groups, workflow groups, and the proven slot menu

A GroundX extraction schema has real top-level groups that define the **final
data object**. These names are the customer-facing output contract after
extraction and reassembly.

The workflow execution shape can be the same as the final shape, or it can be
different through optional `_pseudo_groups`. A pseudo group is workflow-only:
it is addressable by name in workflow artifacts, but it does not appear in the
final output object. Use pseudo groups to split a large final group into
smaller agents or to combine small sibling final groups into one agent.

Each prepared workflow group maps to a **workflow slot**; the compiler
(`skills/groundx-extraction-workflows/templates/compile_workflow.py`) resolves a
workflow group's slot by precedence — SDK-resolved workflow metadata such as
explicit or inherited `slot:`, then a top-level `domain:` profile keyed by
workflow group name, then a hard error. Group names are arbitrary; only the
**slot** is constrained, to the three proven for structured extraction:

| Slot (`slot:`) | Output shape | X-Ray field read back | When to use |
|---|---|---|---|
| `chunk-instruct` | One flat object | `sectionSummary` | Per-document fields that appear once per file |
| `chunk-keys` | Array of objects | `chunkKeywords` | Repeating records (line items, transactions) |
| `chunk-summary` | Array of objects | `chunkSummary` | A second repeating record type (e.g. meters) |

The `invoice` domain profile (`templates/domains/invoice.yaml`) supplies the
canonical billing decomposition — `statement` → `chunk-instruct`,
`charges` → `chunk-keys`, `meters` → `chunk-summary` — so an invoice YAML need
only declare `domain: invoice` and omit per-group `slot:`. A new domain either
declares an explicit `slot:` per workflow group or adds its own profile.
`xray_to_extract.py` reads each slot's X-Ray field back into the aggregated
output. Omit any final group a document does not have. Multiple workflow groups
may resolve to the same slot; the compiler renders a combined slot prompt.

The public syntax walkthrough is
[Structured Extraction Workflow](https://docs.groundx.ai/documentation/structured-extraction-workflow).

### 1.1 `_defs` and `_pseudo_groups`

`_defs` is a fields-only authoring helper. Shared prompt context belongs under
real final groups or pseudo groups, not inside `_defs`. `_defs` expands into
final groups before pseudo routing.

`_pseudo_groups` routes workflow fields to final fields using final-output JSON
Pointer paths:

```yaml
statement:
  prompt:
    instructions: Extract statement-level fields for the final object.
  fields:
    account_number:
      prompt:
        description: The account number printed on the statement.
        identifiers: ["Account Number"]
        instructions: Return the account number exactly as printed.
        type: str
    total_due:
      prompt:
        description: The total amount due.
        identifiers: ["Total Due"]
        instructions: Return the total as a number.
        type: float

_pseudo_groups:
  statement_identity:
    slot: chunk-instruct
    fields:
      account_number:
        path: /statement/account_number
  statement_totals:
    slot: chunk-summary
    fields:
      total_due:
        path: /statement/total_due
```

Pseudo groups may contain `prompt`, `fields`, and documented workflow metadata
such as `slot`. Arbitrary pseudo-group author metadata is rejected in v1.
Route paths are final-output JSON Pointers such as
`/statement/account_number`, not dot-separated strings.

### 1.2 statement: per-document fields

Use this group for fields that appear once per document, even if they are
scattered across pages: account numbers, dates, totals, addresses,
identifiers. Each chunk of the document contributes whichever of these
fields it can see; the platform reconciles them into one flat object.

Each field appears as a top-level key in the extraction output:

```yaml
statement:
  fields:
    invoice_date:
      prompt: { ... }
    total_due:
      prompt: { ... }
```

```json
{
  "invoice_date": "2026-01-22",
  "total_due": 38.99
}
```

### 1.3 charges: repeating records

Use this group for records that repeat — typically line items, transactions,
charges, or service rows. Each chunk contributes complete records (not
partial fields of one record); the platform aggregates them into an array.

The output appears under the `account_charges` array key:

```yaml
charges:
  fields:
    charge_description_as_printed:
      prompt: { ... }
    charge_amount:
      prompt: { ... }
```

```json
{
  "account_charges": [
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
output shape is an array of meter objects, one per physical meter.

`compile_workflow.py` wires `meters` to `chunk_summary` and writes to the
`chunk-sum` field. The prompt wrapper must return a top-level
`{"meters": [...]}` object. The local X-Ray helper reads each chunk's
`chunkSummary` JSON and accumulates records into the final `meters` array.

For documents that contain metered services, define the concrete meter
fields in the group:

```yaml
meters:
  prompt:
    instructions: |
      Extract one record per physical meter or metered service shown in
      the document. Do not invent meters that are not visible.
  fields:
    meter_number:
      prompt:
        description: "Meter identifier exactly as printed."
        identifiers: ["Meter #", "Meter Number"]
        instructions: "Return the printed meter identifier."
        type: str
    meter_usage:
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
only because an agent has too many fields; split workflow load with
`_pseudo_groups` instead.

As a rule of thumb, keep each workflow group's extraction load to **20 fields
or fewer**. Above that, LLM cognitive load starts to work against
accuracy and consistency. If a final group grows beyond 20 fields but should
remain one final object, keep the final group intact and create smaller coherent
pseudo groups. If two sibling final groups each have fewer than roughly 10
fields and appear in the same document region, consider one pseudo workflow
group that routes fields back to both final groups. Do not design one
pre-process extraction agent per field.

## 2. Field anatomy

Every field in the YAML has the same shape. The top-level YAML key becomes
the JSON key in the output.

```yaml
field_key:
  prompt:
    description: "..."
    format: "..."
    identifiers:
      - "Label 1"
      - "Label 2"
    instructions: "..."
    type: str
```

### 2.1 The five required keys

| Key | What it does | Required? |
|---|---|---|
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
  fields:
    charge_description_as_printed: { prompt: { ... } }
    charge_amount: { prompt: { ... } }
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
synthetic invoice-domain schema: `domain: invoice` groups (`statement` +
`charges` + `meters`) with per-field prompts, a group-level prompt that
distinguishes line items from subtotals, and inline business-logic metadata.
Read it before authoring a new schema for any invoice-shaped document.
`examples/insurance-claim/prompt.yaml` is the non-invoice counterpart (explicit
`slot:` per group). Real customer schemas live out-of-repo, never in the skill.
