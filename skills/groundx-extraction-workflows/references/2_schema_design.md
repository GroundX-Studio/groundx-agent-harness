# 2. Schema design

The YAML schema is the durable artifact. Every other output of this skill
derives from it. This reference describes how to author one well.

## 1. The three groups you'll always have

A GroundX extraction schema has top-level groups. The runner
(`skills/groundx-extraction-workflows/templates/extract.py`) recognizes three by
convention:

| Group name | Output shape | Workflow slot | When to use |
|---|---|---|---|
| `statement` | One flat object | `chunk_instruct` | Per-document fields that appear once per file |
| `charges` | Array of objects | `chunk_keys` | Repeating records (line items, transactions) |
| `meters` | Array of objects | No-extract stub (returned as `[]`) | Utility-style per-meter usage records; stub it for documents without physical meters |

The names matter: the runner wires `statement` to `chunk_instruct` and
`charges` to `chunk_keys` based on these exact strings. `meters` is
recognized as a no-extract stub group in the current scope — the
post-processor (`xray_to_extract.py`) always returns `meters: []` and
richer per-meter aggregation is deferred. If the document type does not
have repeating records, omit the `charges` group. If it has no
per-document fields and is purely a list of records, omit the
`statement` group.

### 1.1 statement: per-document fields

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

### 1.2 charges: repeating records

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

### 1.3 meters: utility-style usage records

Use this group for utility-style per-meter usage records: documents where
each meter on a property reports its own consumption over a billing
period (kWh used, gallons consumed, demand readings). The intended
output shape is an array of meter objects, one per physical meter.

In the current scope, `meters` is a **recognized but no-extract stub
group**. `compile_workflow.py` does not yet wire meters to a dedicated
workflow slot, and the post-processor always returns `"meters": []`.
Including the group in the YAML keeps the schema honest about what the
document does or does not contain, and reserves the key for richer
per-meter aggregation in a later version.

For documents that do not contain metered services (most invoice types),
include `meters` as a no-extract stub: a group-level `prompt.instructions`
block that tells the model not to extract anything, and no `fields:`
block. Warner is the worked example — telecom invoices have no physical
meters, so the YAML is:

```yaml
meters:
  prompt:
    instructions: |
      This invoice does not contain metered utility services.
      No meters should be extracted.
```

The output for Warner-shaped documents is therefore always:

```json
{
  "meters": []
}
```

### 1.4 When you have neither

If the document type is neither a per-document object nor a repeating list
(e.g. a free-form report with hierarchical structure), the schema-first
runner does not yet support it. The right path is to surface this to the
user and either model the document as one of the two shapes (typically
`statement` with nested fields rendered as JSON strings) or escalate per
§3.3 in `6_known_limitations.md`.

### 1.5 Categories and agent load

Use **category** for a functional grouping of fields, such as
`statement`, `charges`, or `meters`. Each category has a corresponding
extraction agent that handles extraction, reconciliation, and QA for
that category. Do not design one pre-process extraction agent per field.

As a rule of thumb, keep each category's extraction load to **20 fields
or fewer**. Above that, LLM cognitive load starts to work against
accuracy and consistency. If a category grows beyond 20 fields, split it
into smaller coherent categories rather than adding one agent per field.
The category boundary should follow the document's natural structure:
one-per-document statement fields, repeating charge/service rows,
per-meter usage records, or another domain-specific group that the user
and downstream system can reason about.

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

The GroundX platform requires three hardcoded field names for charge-style
extractions. Use these names exactly in the YAML even if the application
or ground truth uses different names:

- `charge_amount` — numeric value
- `charge_description_as_printed` — verbatim description
- `meter_number` — used for utility-style documents; include as a stub for
  non-metered documents (the model returns empty values, which is the
  intended behavior)

The comparison harness reads aliases (e.g. CSV column `CHG_AMT` ↔ output
key `charge_amount`) so the ground truth does not have to match. See §1 in
`6_known_limitations.md` for the full alias map and rationale.

## 5. A worked example

`skills/groundx-extraction-workflows/examples/warner-telecom/prompt.yaml` is a
production-grade schema with 23 statement fields and 10 charge fields,
including a multi-paragraph group-level prompt for `charges` that
distinguishes line items from subtotals. Read it before authoring a new
schema for any invoice-shaped document.
