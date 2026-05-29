# API Surface Changelog

Use this versioned surface table before answering whether a response field exists.
It is the first stop for customer questions like "does search return a file
summary?" Older references and examples may describe the richer X-Ray path, but
field availability should be answered from this table first.

## Versioned Surface Table

| Surface | Version | Field or behavior | Guidance |
| --- | --- | --- | --- |
| Search MCP | Current | `search_content` result fields | MCP search should match REST search fields for the same request, indexed result, and verbosity. Do not describe MCP search as a reduced six-field surface. |
| Search results | SDK 3.5.4 | `search.results[*].fileSummary` | Inline document-level summary on each result. Prefer this for search-result cards and RAG enrichment when present. |
| Search results | SDK 3.5.4 | `search.results[*].sectionSummary` | Inline section-level context on each result. Prefer this for source-card subtitles and result explanation when present. |
| X-Ray | Current | `document_getxray` / `xrayUrl` | Richer fallback for full document structure: chunks, tables, figures, `fileKeywords`, page images, bounding boxes, and complete X-Ray JSON. |

## Answer Pattern

When asked whether a field exists on search:

1. Check this versioned surface table.
2. Answer with the latest known `search.results[*]` shape.
3. Mention `document_getxray` only when the user needs the full X-Ray or fields
   beyond inline search-result enrichment.

Example: if the user asks for file and section summaries after search, point them
to `search.results[*].fileSummary` and `search.results[*].sectionSummary` first.
Use `document_getxray` as the richer fallback, not as the default next step.
MCP `search_content` should match REST search for the same request, indexed
result, and verbosity.
If a live MCP search response only shows base fields after rich verbosity was
requested, frame it as missing indexed data or a compatibility issue to check,
not as the intended MCP contract.
