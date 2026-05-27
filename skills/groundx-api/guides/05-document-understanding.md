# Document Understanding (X-Ray)

How to access X-Ray — GroundX's structural document analysis — and when to use it
instead of, or alongside, plain search.

X-Ray makes GroundX useful beyond RAG. You can ingest documents and consume X-Ray
output entirely without running a search query — for e-discovery pipelines, compliance
workflows, structured extraction workflows, or any application that needs a complete
structural parse of a document rather than ranked retrieval.

> **SDK version requirement:** X-Ray support requires Python SDK ≥ 1.3.19 or
> TypeScript SDK ≥ 1.3.24. Older SDK versions do not include X-Ray support.

## 1. What X-Ray is

Every document ingested by GroundX is automatically processed by the X-Ray parser.
X-Ray is not a text splitter. The pipeline works in four stages:

1. **Element detection** — a bespoke vision model identifies structural elements
   on each page: paragraphs, tables, figures, forms, headers, and footers.
2. **OCR and reformatting** — advanced OCR extracts text from each element and
   a repair pipeline converts tables, multi-column layouts, and forms into
   clean, LLM-readable text. Extraneous content (headers, footers, page numbers)
   is removed.
3. **Semantic chunking** — elements are grouped into chunks at natural idea
   boundaries, not at fixed character counts. Each chunk is a complete semantic
   unit — a paragraph, a table, a figure — rather than an arbitrary slice.
4. **Re-contextualization** — each chunk is enriched with a `sectionSummary`
   and the document-level `fileSummary` and `fileKeywords`, making every chunk
   self-contained for retrieval. A chunk returned by search carries its own
   context rather than depending on surrounding chunks.

X-Ray produces a detailed structural analysis of the document, including:

- A document-level summary and keyword list
- Per-page layout analysis with bounding boxes
- Semantic chunk extraction with content type classification (paragraph, table, figure)
- LLM-optimized rewrites of each chunk (`suggestedText`)
- JSON and narrative representations of tables and figures
- Section-level contextual summaries

X-Ray runs as part of the default `processLevel: full` ingest path — there is no
separate API call to trigger it. `processLevel: full` keeps GroundX agentic reprocessing
enabled: after OCR / text extraction and chunking, GroundX enriches the document with
the summaries, keywords, instructions, and workflow outputs that make X-Ray and search
useful. The result is available after the ingest `status` reaches `complete`.

If a document is ingested with `processLevel: none`, GroundX still performs OCR / text
extraction and basic chunking, but skips the agentic reprocessing that produces enriched
X-Ray-style summaries and workflow outputs.

## 1.1 Intermediate processing artifacts

X-Ray is the final, supported form of the document — it's what `document_getxray`
returns and what consumers should normally read. But the pipeline produces three
intermediate JSON files along the way that are exposed at well-known URLs on
EyeLevel-hosted storage. They are not part of the public API contract — schemas
can change without notice — but they are useful when an evaluator, debugger, or
auditor needs to inspect a specific stage of the processing pipeline.

| Artifact | Stage produced | What it contains |
|---|---|---|
| **MAP** | After layout detection + OCR (stages 1–2) | Per-page structural map: every detected element, its bounding box, and its raw OCR text. The first machine-readable form of the document. |
| **Enriched chunks** | After semantic chunking + re-contextualization (stages 3–4) | Chunks at semantic boundaries, each enriched with `sectionSummary`, document-level `fileSummary`, and `fileKeywords`. |
| **JSONL** | After reformatting for the search index | The final, line-delimited JSON form ingested into the vector and inverted indices — the format the search engine actually reads. |
| **X-Ray** | Aggregated final form | The structural payload returned by `document_getxray` — document-level summary, parsed pages and elements, semantic chunks, links to source, page images. The supported public surface. |

### URL templates

Substitute `{processId}`, `{documentId}`, and `{bucketId}` from any
ingest/search/lookup response:

```
MAP       https://upload.eyelevel.ai/layout/processed/{processId}/{documentId}-118-map.json
ENRICHED  https://upload.eyelevel.ai/layout/processed/{processId}/{documentId}-enriched.json
JSONL     https://upload.eyelevel.ai/gpt3/model/{bucketId}/{documentId}.answers.jsonl
```

`processId` is returned by every ingest operation (§2 / §3 in 02-documents.md).
`documentId` is on the document record (§10 in 02-documents.md) and on every
search result chunk (§1.2 in 03-search.md). `bucketId` is on the document record
and on search results.

### When to reach for each form

- **Use X-Ray for production code.** It's the supported, schema-stable surface
  and contains everything the intermediate forms contain plus the document-level
  rollups. Default to `document_getxray` or the `xrayUrl` field on `document_get`.
- **Inspect MAP** when investigating layout-detection or OCR quality — wrong
  bounding boxes, dropped elements, garbled OCR. The MAP shows what the parser
  saw before any chunking or re-contextualization happened.
- **Inspect Enriched chunks** when investigating chunk boundaries, agentic
  enrichment, or section-summary quality. This is where chunk-shape decisions
  are made and where re-contextualization runs.
- **Inspect JSONL** when reproducing what the search engine actually has
  indexed — the same chunks reformatted for the index. Handy when search
  results disagree with what an evaluator expects from looking at X-Ray.
- **Use X-Ray (or its `xrayUrl`)** for everything else.

The intermediate URLs return raw JSON over HTTPS; auth is the same `X-API-Key`
header used elsewhere in the API.

## 2. Search vs. X-Ray — when to use each

| Need | Use |
|---|---|
| Answer a user's question from document content | `search_content` — it's faster and returns ranked, relevant chunks |
| Inspect the full structure of a specific document | `document_getxray` |
| Extract all tables or figures from a document | `document_getxray` — filter chunks by `contentType` |
| Build a document outline or chapter map | `document_getxray` — walk top-level `chunks[]` using `sectionSummary` and `pageNumbers` |
| Verify what was extracted from a specific page | `document_getxray` — filter top-level `chunks[]` by `pageNumbers` (or use `documentPages[n].chunks`, which mirrors the top-level array filtered to that page) |
| Get document-level metadata (summary, keywords, page images) | `document_getxray` |

Use `search_content` for retrieval. Use `document_getxray` when you need the full
structural picture of a document, need to enumerate all elements of a specific type,
or need spatial/layout information.

## 3. Getting the documentId

`document_getxray` requires a `documentId` (UUID). Obtain it from:

- The ingest response `progress.complete.documents[n].documentId` after polling to
  `complete`
- `document_list` → `documents[n].documentId`
- `document_lookup` filtered by `bucketId`, `groupId`, or `processId`
- `document_get` by a known `documentId`

The `document_get` response also includes a `xrayUrl` field — a pre-signed URL
pointing to the X-Ray JSON payload. You can fetch `xrayUrl` directly instead of
calling `document_getxray` via the API. Both paths return the same data.

## 4. Calling document_getxray

**MCP:**
```json
{ "documentId": "9f7c11a6-24b8-4d52-a9f3-90a7e70a9e49" }
```
Tool: `document_getxray`

**REST:**
```http
GET /v1/ingest/document/xray/9f7c11a6-24b8-4d52-a9f3-90a7e70a9e49
X-API-Key: YOUR_API_KEY
```

See §16 in 02-documents.md for the operation reference.

**Errors:** 400 — invalid document ID format; 401 — API key lacks access to this
document.

## 5. X-Ray response schema

```
{
  fileType        string     — file type of the source document
  language        string     — language detected on page 1
  fileKeywords    string     — comma-delimited keyword list for the whole document
  fileName        string     — name given at ingest
  fileSummary     string     — auto-generated document summary
  sourceUrl       string     — hosted URL of the source document

  chunks          array      — PRIMARY: all semantic chunks for the document; always read content from here
    chunk             string    — unique chunk ID (e.g. "bvzx4u-0")
    contentType       array     — single-element array: ["paragraph"], ["table"], or ["figure"]
    pageNumbers       array     — pages where this chunk appears; can span multiple pages
    text              string    — raw extracted OCR text
    suggestedText     string    — see §6; format differs by contentType
    sectionSummary    string    — section-level context; often repeats across consecutive same-section chunks
    boundingBoxes     array     — spatial coordinates of the chunk on its page(s)
      pageNumber      number
      topLeftX        number
      topLeftY        number
      bottomRightX    number
      bottomRightY    number
      corrected       boolean   — true if GroundX adjusted the coordinate (e.g. for a rotated/landscape page)
    json              array     — structured content; shape varies by contentType (see §6)
    narrative         array     — string[]; narrative[i] describes json[i] at the same index (tables and figures only)
    multimodalUrl     string    — image URL for the element (tables and figures only)

  documentPages   array      — SECONDARY: use only for pageUrl and page dimensions; dimensions vary per
                               page (a landscape page in a portrait document has swapped width/height —
                               always look up dynamically, never assume consistent dimensions)
    pageNumber    number     — 1-indexed page number
    pageUrl       string     — hosted image of the page (PNG)
    height        number     — pixel height of page image
    width         number     — pixel width of page image
    chunks        array      — duplicate of top-level chunks[] filtered to this page; do not use for content
}
```

## 6. Key fields and their uses

**`fileSummary`** — Use for document-level overviews without reading individual chunks.
Useful for catalogue-style applications that need a one-paragraph description of each
document.

**`fileKeywords`** — Comma-delimited. Use for topic classification, tag generation, or
filtering documents before deciding which to retrieve from.

**`documentPages[n].pageUrl`** — Hosted image of the page. Use when you need to display
or process the original page visually (e.g., multimodal LLM tasks, visual verification).

**`chunks[n].contentType`** — Single-element array indicating the chunk type. There are
exactly three possible values:

| Value | What is classified as this type |
|---|---|
| `["paragraph"]` | Body text, headers, footers, captions, running text — anything that is not a table or figure |
| `["table"]` | Structured tabular data |
| `["figure"]` | Charts, illustrations, cover pages, diagrams, images |

Note: headers, footers, and captions are `["paragraph"]`, not `["figure"]`. Cover pages are
`["figure"]`, not `["paragraph"]`.

To enumerate only tables across a document: walk top-level `chunks[]`, filter where
`contentType[0] === "table"`, and read their `json` or `narrative` fields.

**`chunks[n].suggestedText`** — The same text that appears in `search.text` when this
chunk is returned by search. Format differs by `contentType`:
- **`["paragraph"]`** — LLM-optimized markdown prose. Use directly as LLM context.
- **`["table"]` / `["figure"]`** — A combined string that contains the structured JSON
  representation of the element followed by narrative text. Both parts are also separately
  extracted into `json[]` and `narrative[]`. When consuming X-Ray output programmatically,
  read `json[]` and `narrative[]` directly rather than parsing `suggestedText` for these
  types.

**`chunks[n].text`** — Raw extracted OCR text. Behavior differs by content type:
- **`["paragraph"]`** — Always populated. Newlines may be inconsistent; line breaks from
  the original layout are imperfectly preserved.
- **`["table"]`** — Always populated, but table structure is flattened: columns are
  collapsed to space-separated text. Useful for string comparison but not for understanding
  structure — use `json[]` for structured data.
- **`["figure"]`** — Usually an empty string `""`. OCR yields nothing useful on figures.
  Always check before rendering.

**`chunks[n].json`** — Structured content present on all chunk types, but with different
shapes depending on `contentType`:
- **`["paragraph"]`** — Always a single-element array: `[{ "contents": [{ "text": "..." }, ...] }]`.
  The single outer object holds a `contents` array of text blocks. Less useful than
  `suggestedText` for most purposes.
- **`["table"]`** — `json[0]` is always a metadata object (`table_title`, `table_number`,
  `summary`, `keywords`). Data elements begin at `json[1]`. Table data elements have no
  `type` discriminator field — infer the element type from which keys are present. Some
  simple table chunks have only `json[0]` and no data rows; in that case `json[0].summary`
  describes the entire table.
- **`["figure"]`** — `json[0]` is always a metadata object (`figure_title`,
  `figure_number` (may be null), `summary`, `keywords`, `source`, `components`,
  `relationships`). Visual sub-elements begin at `json[1]`. Never treat `json[0]` as a
  data row. The `json[0].summary` field is a plain-English description of this specific
  table or figure — distinct from `sectionSummary`, which describes the surrounding
  document section.

**`chunks[n].narrative`** — String array present on table and figure chunks. `narrative[i]`
is a prose description of `json[i]` at the exact same index — the alignment is exact, do
not offset by 1. Use when passing visual-element content to an LLM that cannot process
JSON directly.

**`chunks[n].sectionSummary`** — Contextual summary of the section containing this chunk.
Present on all chunk types. Frequently repeats identically across many consecutive chunks
that belong to the same document section — it is section-level context, not chunk-specific.
For extraction workflows that process chunks in sequence, deduplicate consecutive identical
values. For chunk-specific descriptions of tables and figures, use `chunks[n].json[0].summary`
instead.

**`chunks[n].boundingBoxes`** — Spatial coordinates for the chunk on its page(s). A chunk
can have multiple boxes — both across pages (a chunk spanning pages 3–4 has boxes on each)
and within a single page (a paragraph spanning two columns has one box per column region).
Always render all boxes, not just the first. Use `box.pageNumber` to associate each box with
the correct page image and dimensions from `documentPages`.

**`chunks[n].multimodalUrl`** — Hosted image of an individual table or figure element.
Always present on `["figure"]` chunks. Present on `["table"]` chunks. Absent on
`["paragraph"]` chunks. Use when passing a specific visual element to a multimodal model
for analysis, or as the primary display element for a table or figure in a UI.

## 7. Field presence by contentType

Quick-reference matrix for which fields are populated on each chunk type.

| Field | `["paragraph"]` | `["table"]` | `["figure"]` |
|---|---|---|---|
| `text` | ✅ always populated | ✅ always; structure flattened to space-separated | ❌ usually empty `""` |
| `suggestedText` | markdown prose | serialized JSON + narrative string | serialized JSON + narrative string |
| `json[]` | `[{ contents: [{text}] }]` single outer element | `json[0]` = metadata; `json[1+]` = data rows (no type discriminator) | `json[0]` = metadata; `json[1+]` = visual sub-elements |
| `json[0].summary` | ❌ absent | ✅ sometimes | ✅ sometimes |
| `narrative[]` | ❌ absent | ✅ `narrative[i]` → `json[i]` | ✅ `narrative[i]` → `json[i]` |
| `sectionSummary` | ✅ | ✅ | ✅ |
| `multimodalUrl` | ❌ absent | ✅ present | ✅ always present |
| `boundingBoxes` | ✅ (may have multiple per page for non-contiguous regions) | ✅ (typically one) | ✅ (typically one) |

## 8. File types and X-Ray availability

X-Ray runs on all supported file types, but the visual layout analysis pipeline does
not apply to non-visual formats. The following file types produce X-Ray data **without**
the visual bounding box and page image output:

- `csv`, `tsv`, `xlsx`, `json`, `txt`

For these types, `documentPages[n].pageUrl`, `boundingBoxes`, and `multimodalUrl`
will be absent or empty. `suggestedText`, `sectionSummary`, and `fileSummary` remain
available. See §2 in 02-ingest-patterns.md for the full file type list.

## 9. Extract results (document_getextract)

`document_getextract` returns structured extraction results produced by an attached
extract workflow. Extraction is separate from X-Ray: X-Ray is the structural document
understanding payload, while extract results are workflow-defined fields and values.

Attach the extract workflow to the account, bucket, group, or document before ingesting
the document. Without that workflow, `document_getextract` returns 404 even when the
document used the default `processLevel: full`. `processLevel: full` is still the right
processing depth for extraction because it keeps GroundX's agentic reprocessing enabled;
`processLevel: none` skips that reprocessing and should not be used for extraction
workflows.

**MCP:**
```json
{ "documentId": "9f7c11a6-24b8-4d52-a9f3-90a7e70a9e49" }
```
Tool: `document_getextract`

See §15 in 02-documents.md for the operation reference. Use `groundx-extraction-workflows` first
for schema-first extraction authoring, then return here for workflow registration,
document ingest, polling, and extraction retrieval semantics. See `guides/09-workflows.md`
for the workflow processing pipeline.
