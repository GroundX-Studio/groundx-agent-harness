# 6. Known limitations and escalation

Platform-side constraints, convention ambiguity patterns, and the
escalation playbook for when extraction is wrong despite a clear prompt.

## 1. Platform-locked field names (AGE-6)

The GroundX extraction platform requires two hardcoded field names for
charges-style groups. Renaming them in the YAML breaks charge extraction.
Meter identifiers belong in the `meters` group unless the downstream charge
schema explicitly needs a meter identifier on each charge row.

### 1.1 The locked names

| Required YAML key | What it represents | Notes |
|---|---|---|
| `charge_amount` | Numeric value of one record | Type `[int, float]` |
| `charge_description_as_printed` | Verbatim description from the document | Type `str` |

These names are not configurable. The runner and YAML must use them
exactly. The YAML key for each becomes the JSON key in the extraction
output.

### 1.2 Aligning Expected-Answer Field Names

Use the platform-required names (`charge_amount`,
`charge_description_as_printed`) directly in the YAML, and make mapped
expected-answer JSON use the **same field names** as the extraction output
(both derive from the YAML). The comparator (`templates/score_extraction.py`)
matches by field name and does not bridge differing names, so map spreadsheets,
documents, text files, PDFs, or human-review notes to the runner output shape
with matching field names first.

A documented platform constraint is not a failure mode; an undocumented
divergence between the YAML field names and the expected-answer field names is.

## 2. Convention ambiguity (AGE-7-style)

Some fields have ambiguous extraction conventions: the document text
supports multiple interpretations, and the right one depends on
downstream business logic the extraction layer does not have access to.

### 2.1 Example: pmts_app_thru_date

A bill may show:

```
01/10  Credit Card Payment   -38.99
```

…with an invoice date of `01/22`. The field `pmts_app_thru_date` could
be either:

- The actual payment date (`01/10`) — what the model will naturally
  extract
- The invoice date (`01/22`) — what some downstream systems expect

Both are correct readings of the document. Resolving this requires
asking the user which convention they expect.

### 2.2 Resolution pattern

For convention-ambiguous fields:

1. Document the ambiguity in the field's YAML `instructions` block. State
   both interpretations and which one the prompt currently expects.
2. Run the extraction. If the model picks the wrong convention, tighten
   the instruction explicitly: "Use the date next to the payment line
   item if present; if no payment date is found, use the invoice date as
   a fallback."
3. If the comparison still flags FAIL, surface to the user with the
   document context. Do not guess which convention is correct.

WARN-level mismatches on ambiguous fields are acceptable when the
convention is documented.

## 3. Escalation playbook

When a field will not extract correctly despite a clear, tight prompt,
work through these steps in order before escalating.

### 3.1 Step 1: X-Ray inspection

`gx_client.documents.get_xray(document_id=...)` returns the raw chunks
the platform produced from the document. For custom workflow YAML, inspect
`customChunkOutputs`, `customSectionOutputs`, or `customDocumentOutputs`
under the custom step name and output key. Older platform captures may also
expose diagnostic fields such as `sectionSummary`, `chunkKeywords`/`chunkKeys`,
`chunkSummary`, or `suggestedText`.

Use X-Ray to answer one question: **was the data even parsed correctly?**

- If the value is missing from every chunk — the layout-analysis or
  chunking step did not surface it. The prompt cannot fix a parsing
  problem.
- If the value is in the chunks but the LLM is not returning it — the
  prompt is the problem. Tighten `instructions` and re-run.
- If the value is in the chunks and the LLM returns it for some chunks
  but not others — the LLM is inconsistent across chunks. Tighten
  `identifiers` to make the value easier to lock onto.

### 3.2 Step 2: Prompt tightening

If X-Ray confirms the value is parseable but the LLM is missing it,
common fixes:

- Add a more specific identifier to `identifiers`
- Add a negative example to `instructions` ("Do not confuse with X")
- Add a fallback rule to `instructions` ("If no explicit value is
  found, infer from Y")
- For charges-style under-extraction, tighten the group-level
  `prompt.instructions` rather than the per-field `instructions`

### 3.3 Step 3: File against the AGE team

If X-Ray shows the value is not in the chunks, the issue is platform-side
(layout analysis, chunking, parsing). The right path is to file a
limitation against the AGE team:

- **Owner:** Ben Fletcher (`benjamin.fletcher@eyelevel.ai`), Devansh
  Agrara (`devansh.agrara@eyelevel.ai`)
- **What to include:** the document type, the field name, an example
  document, the X-Ray output for the chunks where the value should
  appear, the prompt that did not work
- **What not to do:** keep tightening the prompt. A prompt cannot
  recover data the parser did not extract.

After filing, document the new limitation in this reference doc (§1 if
it is a name lock, §2 if it is a convention ambiguity, or a new
subsection if it is a category not yet covered). The skill becomes more
useful as more limitations are catalogued explicitly.

## 4. `get_extract` returns 404 for chunk-level workflows

`document_getextract` only returns the **document-level** extract artifact in
some hosted environments. The schema-first workflows this skill produces often
run at chunk or section level, so their structured output may be visible first
in X-Ray custom output maps (`customChunkOutputs`, `customSectionOutputs`, or
`customDocumentOutputs`) rather than the document-level artifact. As a result
`get_extract` can return `404 — "We could not find extractions for the
documentId you provided"` even though the extraction ran correctly and the
workflow was attached before ingest.

Confirmed live (2026-05-30) against the invoice example with a regular user key:
`get_extract` 404'd while the X-Ray held a fully populated statement (23
fields) and 20 charges. Re-confirmed 2026-05-31 with a valid documentId,
`add_to_account`, and ~3 min of post-ingest polling — the hosted tier does not
return server-side extractions; the X-Ray fallback is the working path.

**Resolution (in this skill):** `run_extraction.py` tries `get_extract` first.
When raw extract is available, it writes that payload to `output.json`. When
`get_extract` is empty or 404s, it writes `xray_diagnostic.json` from
`xray_to_extract.py`, writes `xray_reassembly_diagnostic.json` for the full SDK
readback envelope when available, and writes `final_output.json` for local
diagnostic/business-logic output. Add `--require-raw-extract` when the absence
of `output.json` should fail the run. `xray_to_extract.py` remains the
canonical local aggregator for X-Ray-first diagnostics (see `references/README.md`
and `10_debugging_methodology.md`).
