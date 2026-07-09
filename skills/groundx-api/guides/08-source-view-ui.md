# Source-View UIs

How to build UIs that let users inspect the exact source material behind an LLM
response — the rendered document page, the highlighted chunk region, visual element
clippings, and document attribution. This pattern is essential for any chat
application where users need to verify or explore the content the LLM drew on.

## 1. The pattern

A source-view UI pairs an LLM chat response with one or more **source cards** — each
card shows the document page the chunk came from, with the relevant passage
highlighted, plus document attribution (title, publisher, filename). Users click a
source card to inspect the evidence behind the answer.

```
User query
  ↓
search_content (verbosity: 2)
  ↓ search.text → LLM → answer
  ↓ search.results → source cards (page image + bounding box overlay + attribution)
```

The LLM and the source view are driven by the same search call. `search.text` goes
to the LLM; `search.results` powers the UI.

## 2. Required search configuration

Source-view UIs usually start with `verbosity: 2`. At lower verbosity levels,
`searchData` is absent from chunks, which means no custom metadata for the
attribution card. Core source fields such as `pages`, `boundingBoxes`,
`fileSummary`, and `sectionSummary` are part of the search result contract when
that data exists on the indexed result.

```json
{
  "id": 1234,
  "query": "What are the indemnification limits?",
  "n": 5,
  "verbosity": 2
}
```

Tool: `search_content`

Set `n` to the number of source cards you want to show. Five to ten is typical — the
reranker already ensures they are all relevant.

## 3. Connecting source cards to the LLM response

There are two approaches, used independently or together.

### 3.1 Ambient sourcing (recommended)

Show all `n` result chunks as source cards alongside the chat response. The user
sees the top-ranked evidence the LLM drew on without needing the LLM to cite
anything. This is the most robust approach — the reranker orders the strongest
available evidence ahead of weaker matches, and there is no risk of the LLM
hallucinating citation numbers.

The cards are ordered by `score` descending (the array is already sorted), so the
highest-scored source appears first.

### 3.2 Inline citation markers

When you need the LLM to identify which specific chunks support specific claims,
inject numbered markers into the context block and instruct the LLM to cite them:

```
system:
  Answer using only the numbered sources below. Cite sources as [1], [2], etc.

  [1] {search.results[0].suggestedText}
  [2] {search.results[1].suggestedText}
  [3] {search.results[2].suggestedText}
  ...

user:
  {query}
```

Map `[1]` → `search.results[0]`, `[2]` → `search.results[1]`, and so on. When
the LLM includes `[2]` in its response, render `search.results[1]` as a source
card. Use this approach when the UI needs to link specific sentences in the answer
to specific source passages.

Note: use `suggestedText` rather than `search.text` when injecting numbered
chunks — `search.text` is a merged string, not individually addressable. See §3
in 03-search.md for the distinction.

### 3.3 The attribution challenge

Understanding the relationship between the LLM answer and the source document
requires understanding the full transformation chain:

```
atoms (words + coordinates)
  ↓  OCR + X-Ray parsing
text  ←  raw extracted text, directly tied to atom bounding boxes
  ↓  LLM rewrite (GroundX agent)
suggestedText  ←  semantically equivalent but NOT word-for-word; no word-level mapping
  ↓  all chunks merged
search.text  ←  the full context block sent to the LLM
  ↓  LLM completion
answer  ←  selects from and synthesizes across multiple chunks; no direct traceability
```

`suggestedText` is an LLM-agent rewrite of the raw `text`. It is more readable and
performs better in LLM context, but it is not directly tied to specific words or
atoms in the document — it is semantically derived from the chunk, not a verbatim
copy of it. The LLM completion then draws from the merged `search.text` and
synthesizes across multiple chunks, making it impossible to deterministically trace
which words in the answer came from which chunk.

**Practical approaches to attribution:**

The most reliable approach is **ambient sourcing** (§3.1) — display bounding boxes
for the whole chunk region for all returned chunks. The chunk-level `boundingBoxes`
in search results are the primary source-view geometry when present. If an older
indexed result or deployment returns only base fields, use `document_getxray` or
`xrayUrl` to repair or enrich the source-view data instead of assuming MCP search
only supports the base shape.

When you need finer attribution, use a secondary LLM call to identify which
`suggestedText` passages most closely correspond to specific claims in the answer,
then highlight the bounding box region for those chunks. This is an approximation —
the highlighted region covers the whole chunk, not specific words — but it reliably
points the user to the right section of the source.

Word-level highlighting using the OCR map (§10) is feasible for direct quotes that
appear verbatim in `text`, but will generally not match paraphrased content in
either `suggestedText` or the final answer. Use it selectively for exact-match
highlighting, not as a general attribution mechanism.

## 4. Rendering a page with a bounding box overlay

Each chunk in `search.results` carries a `pages` array and a `boundingBoxes` array.
Use them together to render the source page with the chunk highlighted.

### 4.1 Data relationships

```
chunk.boundingBoxes[n].pageNumber  →  matches  →  chunk.pages[m].number
chunk.pages[m].imageUrl            →  the rendered JPG of that page
chunk.pages[m].width               →  native pixel width of the page image
chunk.pages[m].height              →  native pixel height of the page image
chunk.boundingBoxes[n].topLeftX    →  upper-left X in native coordinates
chunk.boundingBoxes[n].topLeftY    →  upper-left Y in native coordinates
chunk.boundingBoxes[n].bottomRightX → lower-right X in native coordinates
chunk.boundingBoxes[n].bottomRightY → lower-right Y in native coordinates
```

Bounding box coordinates are expressed in the native pixel space of the page image
(`pages[m].width` × `pages[m].height`). When you display the image at a different
size, scale the coordinates proportionally.

### 4.2 Coordinate scaling

Bounding box coordinates are in native page pixel space. When rendering the page
image at any display size, scale the coordinates proportionally:

```
scale        = displayWidth / page.width
displayHeight = page.height * scale

overlayX      = box.topLeftX      * scale
overlayY      = box.topLeftY      * scale
overlayWidth  = (box.bottomRightX - box.topLeftX) * scale
overlayHeight = (box.bottomRightY - box.topLeftY) * scale
```

Position the overlay element absolutely over the page image using these scaled
values. `page.width` and `page.height` are the dimensions of the image at
`page.imageUrl` — the coordinate space the box values were recorded in.

## 5. Multi-page chunks

A single chunk can span two pages. In this case `boundingBoxes` contains multiple
entries with different `pageNumber` values. Render each page separately with its
own overlay:

```
for each box in chunk.boundingBoxes:
  page = chunk.pages.find(p => p.number == box.pageNumber)
  renderPageWithOverlay(page, box, displayWidth)
```

Present the pages sequentially in the source card, with each page labeled
(e.g. "Page 4" / "Page 5") so the user can see where the content continues.

## 6. Visual elements: multimodalUrl

When a chunk represents a table, chart, or figure, `multimodalUrl` is an image
clipping of that element extracted directly from the document. It is present only
when the chunk is a visual element — check for it before rendering.

Use `multimodalUrl` as a compact preview in the source card: display it alongside
or instead of the full page image when it is available. For tables and charts it is
usually more readable than the full-page rendering with a bounding box overlay.

```
if chunk.multimodalUrl:
  show multimodalUrl image as the primary visual (table/chart clipping)
  offer full page image as "View in context" link
else:
  show page image with bounding box overlay
```

## 7. Source card layout

A complete source card draws from these chunk fields:

| Field | Use in UI |
|---|---|
| `pages[n].imageUrl` | Page thumbnail / full-page viewer |
| `boundingBoxes` | Highlight overlay coordinates |
| `multimodalUrl` | Visual element clipping (tables, charts) |
| `searchData.fullTitle` | Document title in the card header |
| `searchData.publisher` | Publisher / source attribution |
| `searchData.sectionSummary` | Section context — show as a subtitle or tooltip |
| `fileName` | Filename badge |
| `sourceUrl` | "Open original" link |
| `suggestedText` | Readable passage preview beneath the page image |
| `score` | Relevance indicator (optional — can be shown as a confidence bar) |
| `documentId` | Stable identifier for deep-linking to the source |
| `processId` | Ingest process ID — combine with `documentId` to fetch the word-level OCR map (§10) |

A minimal source card shows the page image with overlay, the document title,
and a "View source" link to `sourceUrl`. A richer card adds the section summary,
filename, publisher, and a text excerpt from `suggestedText`.

## 8. End-to-end example

```
// 1. Search with full verbosity
result = search_content({
  id: bucketId,
  query: userQuery,
  n: 5,
  verbosity: 2
})

// 2. Pass search.text to the LLM
answer = llm({
  system: instructions + "\n===\n" + result.search.text + "\n===",
  user: userQuery
})

// 3. Render answer + source cards
display(answer)

for each chunk in result.search.results:
  card = {
    title:     chunk.searchData.fullTitle,
    publisher: chunk.searchData.publisher,
    section:   chunk.searchData.sectionSummary,
    fileName:  chunk.fileName,
    sourceUrl: chunk.sourceUrl,
    text:      chunk.suggestedText,
    score:     chunk.score,
    pages:     chunk.pages,
    boxes:     chunk.boundingBoxes,
    visual:    chunk.multimodalUrl  // null if not a visual element
  }
  renderSourceCard(card, displayWidth = 400)
```

Source cards are shown in relevance order (`search.results` is already sorted by
`score` descending). The first card is the strongest source.

## 9. Verbosity and performance

`verbosity: 2` returns the full `searchData` object on every chunk. If source-view
UIs are only shown on demand (e.g., user clicks "Show sources"), consider a two-call
pattern: make the initial chat call at `verbosity: 1` (lighter response), then
re-fetch at `verbosity: 2` only when the user opens the source panel. Both calls
use the same query and `n` — the second call is fast because the query has already
been processed.

Alternatively, cache the `verbosity: 2` response on the first call and display it
lazily — this avoids the second round-trip at the cost of holding more data in
memory.

## 10. Word-level OCR extraction map

In addition to the chunk-level bounding boxes returned by search, GroundX stores a
raw OCR extraction file for every processed document. This file contains bounding
boxes at individual word granularity — useful for text selection overlays,
copy-to-clipboard from a rendered page, word-level highlighting, and accessibility
features that chunk-level boxes cannot support.

### 10.1 URL pattern

The OCR map is not returned by any API endpoint. Construct its URL from the
`processId` and `documentId` embedded in the page image URLs already present in
every search result chunk:

```
https://upload.eyelevel.ai/layout/processed/{processId}/{documentId}-118-map.json
```

The `-118-map.json` suffix is fixed — it identifies the processing pipeline version
and does not vary per document.

### 10.2 Getting processId and documentId

Both IDs are direct fields on every `search.results` chunk:

```
chunk.processId   — UUID of the ingest process that produced this document
chunk.documentId  — UUID of the document
```

Construct the map URL directly:

```
mapUrl = `https://upload.eyelevel.ai/layout/processed/${chunk.processId}/${chunk.documentId}-118-map.json`
```

The same IDs are also embedded as path segments in `pages[n].imageUrl`,
`pageImages[n]`, and `multimodalUrl`:

```
https://upload.eyelevel.ai/layout/raw/prod/{processId}/{documentId}/{page}.jpg
```

If for any reason the direct fields are absent, the IDs can be parsed from those
URLs as a fallback.

### 10.3 Schema

The map is a JSON object with two top-level fields:

| Field | Type | Description |
|---|---|---|
| `locale` | string | Detected language of the document (e.g. `"en"`, `"ru"`) |
| `pages` | array | One entry per page — see Page below |

**Page:**

| Field | Type | Description |
|---|---|---|
| `pageNumber` | integer | 1-based page number |
| `width` | integer | Page image width in pixels — same space as atom coordinates |
| `height` | integer | Page image height in pixels |
| `pageFile` | string | URL of the page JPG — identical to `pages[n].imageUrl` in search results |
| `molecules` | array | Logical content blocks on this page — see Molecule below |

**Molecule** — a paragraph or figure block:

| Field | Type | Description |
|---|---|---|
| `type` | string | `"paragraph"` or `"figure"` |
| `paraID` / `figureID` | string | Unique ID for this block |
| `paraText` | string | Full reconstructed text of the paragraph (paragraph molecules only) |
| `pageNumber` | array of integers | Pages this molecule spans (1-based) |
| `minPoint` | `{x, y}` | Upper-left corner of the molecule bounding box |
| `maxPoint` | `{x, y}` | Lower-right corner of the molecule bounding box |
| `middlePoint` | `{x, y}` | Center point of the molecule bounding box |
| `rows` | array | Text rows within this paragraph (paragraph molecules only) — see Row |
| `children` | array | Paragraph molecules inside this figure (figure molecules only) |
| `url` | string | Image clipping URL for the figure (figure molecules only) |
| `corrected` | boolean | Whether the OCR output was post-corrected |

**Row** — a single line of text within a paragraph:

| Field | Type | Description |
|---|---|---|
| `type` | string | Always `"paragraph-row"` |
| `atoms` | array | Individual word tokens on this line — see Atom |
| `minPoint`, `maxPoint`, `middlePoint` | `{x, y}` | Bounding box for the row |
| `pageNumber` | array of integers | Page(s) this row appears on |
| `vary` | `{x, y}` | Character and word spacing variance metrics for the row |

**Atom** — an individual word or token (the most granular unit):

| Field | Type | Description |
|---|---|---|
| `elementId` | string | Unique ID for this atom |
| `rawId` | string | Sequential index of this atom in the raw OCR output (e.g. `"0"`, `"1"`) |
| `type` | string | Always `"text"` |
| `text` | string | The word text, including any trailing space. Joining all atom texts in order exactly reproduces the parent molecule's `paraText`. |
| `minX`, `minY` | number | Upper-left corner in page pixel coordinates |
| `maxX`, `maxY` | number | Lower-right corner in page pixel coordinates |
| `width`, `height` | integer | Pixel dimensions of the word bounding box |
| `middle` | `{x, y}` | Center point of the bounding box |
| `points` | array of 4 `{x, y}` | Four corners as a quadrilateral in order: top-left → top-right → bottom-right → bottom-left. Always has exactly 4 entries. Use these instead of `minX`/`maxX` for skewed or rotated text. |
| `score` | float | OCR confidence (0–1). Mean is typically ~0.97; values below 0.9 indicate low-confidence recognition (~10% of words in a typical document). |
| `parents` | array of strings | IDs of the containing molecule(s) — links the atom back to its paragraph or figure |

All coordinates are in the native pixel space of the page image (`page.width` ×
`page.height`) — the same coordinate space as bounding boxes in search results.

**Typical uses:**

- **Text selection**: render atom boxes as invisible, selectable regions over the
  page image so users can click-drag to select and copy text
- **Word-level highlighting**: find atoms whose `text` matches terms in the LLM
  answer and highlight them individually
- **Copy to clipboard**: map a user's drag-selection rectangle to all overlapping
  atoms, then join their `text` values in reading order
- **Paragraph reconstruction**: use `paraText` on each molecule to get the full
  text of a block without iterating atoms
- **Figure detection**: `type: "figure"` molecules identify image/chart regions;
  their `children` contain any embedded caption paragraphs
- **Accessibility**: position screen-reader text nodes over the page image using
  atom coordinates and `text` values

### 10.4 Fetching the map

The map URL is publicly accessible given the correct `processId` and `documentId`.
Fetch it client-side or server-side — no API key is required:

```
mapUrl = buildMapUrl(chunk.pages[0].imageUrl)
mapData = await fetch(mapUrl).then(r => r.json())
```

Cache the map per `documentId` — it does not change after ingestion completes and
can be large for multi-page documents. Fetch it lazily when the user opens a source
card rather than on every search result.
