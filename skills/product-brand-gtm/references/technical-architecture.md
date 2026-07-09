# Technical Architecture: The "Why" Behind Accuracy

This is the messaging-side explanation of why GroundX can support high-accuracy document understanding and retrieval. Use it when a buyer asks *how* the accuracy claim works — typically a technical audience (VP Eng, Data Lead, ML team, architect). For external/public-facing content, use the descriptive phrasing here; do not name the underlying vision-model architecture by its open-source name.

For the deployment/operational story, see `differentiation.md` § 1. For the accuracy claim itself, see `differentiation.md` § 2 and `proof-points.md`.

**Architecture skill as canonical source.** The technical facts below are restated at product-altitude. The canonical source-of-truth for each component lives in the `groundx-architecture` skill — route there for depth when a buyer needs implementation specifics:

| Topic in this file | Canonical source |
| --- | --- |
| § 2 The vision model | `groundx-architecture/references/vision-model.md` |
| § 3 The agentic pipeline | `groundx-architecture/references/agentic-pipeline.md` (+ `extraction-architecture.md` for the QA microservice) |
| § 4 The hybrid search | `groundx-architecture/references/hybrid-search.md` |
| § 5 Why this beats stitched-together systems | `groundx-architecture/references/altitudes.md` § 3 |
| § 7 What this architecture does not do | `groundx-architecture/references/identity-and-trust.md` (closed-system / model-agnostic posture) |

## 1. The mental model

All downstream benefits — extraction quality, RAG accuracy, cost efficiency, model-agnostic flexibility — trace back to two design decisions:

1. **Accurately break apart documents** into their constituent elements.
2. **Focus narrow agents on small, narrow tasks** instead of asking an LLM to reason about the whole document.

Everything below is a consequence of those two design decisions.

## 2. The vision model

At the core of GroundX is a proprietary vision model fine-tuned on more than 1 million pages of enterprise documents. It is not a generic image model retrofitted for documents and it is not an OCR layer that hands raw text to an LLM. It is purpose-built to identify the elements of a page *before* any reasoning happens.

The insight: every document is composed of three basic element types — **tables, paragraphs, and figures**. The vision model identifies those elements on every page with high accuracy. Section boundaries, columns, captions, and figure regions are detected too. The result: a clean, structured map of *what is on the page and where*, before a single LLM token is spent.

External-facing description: *"a proprietary, fine-tuned vision model trained on over 1 million pages of enterprise documents."* Do not name the underlying open-source architecture in public content.

## 3. The agentic pipeline

LLMs have what we call *"ADD"* — they fail at long tasks. Ask a general-purpose model to read a 200-page policy document and pull every fare rule and you will get hallucinations, omissions, and reasoning drift. The agentic pipeline solves this by breaking the document apart and running narrow agents over each piece.

GroundX runs a set of agents at **three levels of granularity**: **document, section, and chunk.** At each level the agents generate metadata — summaries and keywords — that downstream search and reasoning depend on. At the chunk level specifically, the agents also produce the three versions of the chunk text used by the search layer (one tuned for LLM completions, one tuned for search, one preserving the original extracted text — see § 4 for how those are consumed).

Because each agent works on a small, narrow piece — a section to summarize, a chunk to keyword, a paragraph to enrich — older and cheaper models can do many jobs reliably. The system was designed when GPT-3 was state of the art. That history is why it can still work with small, self-hostable models for focused steps today.

Do not turn this into a blanket cost-scaling claim. The top-level ingest path has sequential stages, while specific stages can parallelize per page, section, or chunk. Stage-level parallelism can improve wall-clock throughput and focused tasks can reduce model cost, but storage, OpenSearch, retained artifacts, and much of processing still scale with document size, element count, and chunk volume. For deployment-level cost estimates, route to `groundx-on-prem`.

For extraction work specifically, a dedicated **QA microservice** reconciles conflicting field extractions and QAs the final structured-data output — the layer that turns *"agents pulled candidate values"* into *"this is the row we will return."*

## 4. The hybrid search

When GroundX is used as full end-to-end RAG, the same ingest pipeline outputs **JSON metadata chunks stored in OpenSearch** — not in a vector database by default. Each chunk carries rich attributes:

- Document summary and document keywords.
- Section summary and section keywords.
- Chunk keywords.
- Three versions of the chunk text — one tuned for LLM completions, one tuned for search, one preserving the original extracted text (including layout context like *which table this row came from*).

Retrieval is a two-stage hybrid:

1. **Weighted relevance pre-filter.** A proprietary OpenSearch weighted query uses the attributes above to pre-filter the corpus to the top ~100–200 chunks by relevance.
2. **Semantic similarity scoring.** Those candidates go through a fine-tuned re-ranker that returns a similarity score per candidate chunk.
3. **Blended score.** Relevance and semantic scores combine into one final score per chunk.

The result is better than either pure relevance search or pure similarity search running alone. Most competitors use vector databases that do similarity matching only; GroundX's intentional integration of ingest output with the search architecture gives it the edge.

## 5. Why this beats stitched-together systems

The Apple-vs-PC argument from `differentiation.md` § 4 has a technical version here. A Frankenstein stack — open-source parser + open-source vector DB + open-source reranker — gives you three vendors' best-effort behavior with no joint optimization. GroundX is designed so the ingest output is *exactly* what the store and search were built to consume. The chunks carry the attributes the weighted search expects. The re-ranker is tuned for the chunk shapes the ingest produces. Joint optimization across the stack is what produces the accuracy delta.

## 6. Why this enables both functional capabilities

The same architecture serves both:

- **Document understanding** (extraction, structured data, fine-tuning data for models). The vision model + agentic pipeline produce structured data directly.
- **Full end-to-end RAG.** Same ingest, plus the hybrid search, supports high-accuracy retrieval.

A buyer can use one capability or both. See `capabilities-and-surfaces.md` for the consumption surfaces that expose them.

## 7. What this architecture does not do

- It does not invent facts. It grounds answers in source documents with attribution.
- It does not require buyers to be on a specific LLM vendor. The output is model-agnostic; pick best-fit model per task.
- It is not a closed system. The on-prem Helm chart is open-beta and self-deployable; the hosted version offers white-glove support and closed-source enhancements.
