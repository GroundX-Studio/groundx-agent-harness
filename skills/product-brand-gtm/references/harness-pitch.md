# GroundX Studio Harness Pitch

Use this reference when copy needs to explain GroundX Studio Harness, especially on one-sheeters, technical references, leave-behinds, sales decks, product overviews, or internal enablement. This file is intentionally short-form. It gives agents the words to describe the Harness without drifting into generic agent-platform language.

## Canonical short pitch

GroundX Studio Harness is an **AI Agent Harness**: a plugin of skills, connectors, and design patterns that gives AI agents fluency in the GroundX platform. Load it into Claude, ChatGPT Codex, Replit, Cursor, openclaw, or any plugin-supporting agent runtime, and agents can implement RAG, extraction, smart reports, classification, Studio UIs, portals, review workflows, and integrations directly against GroundX.

For connected agent execution, GroundX MCP is the preferred path when available.
The Harness makes the agent fluent in what to do and which references to load;
MCP tools execute GroundX operations; REST APIs and SDKs remain the direct
integration and fallback surfaces.

## One-sentence form

GroundX Studio Harness gives AI agents the GroundX-specific skills, connectors, and design patterns they need to build document intelligence workflows in days instead of months.

## What it is

- **Category:** AI Agent Harness.
- **Form:** a plugin of skills, references, templates, connectors, and design patterns.
- **Job:** make AI agents fluent in GroundX so they can implement useful work instead of rediscovering product, API, design, and workflow rules from scratch.
- **Audience:** executives and IT teams asking how to scale many GroundX-backed AI use cases without a one-by-one engineering build.
- **Status:** alpha. Use product-state claims from `product.md` before promising customer availability or runtime support.

## Buyer-facing pattern descriptions

| Pattern | Say | Do not say |
| --- | --- | --- |
| Document RAG | Ask questions over complex documents and get grounded answers with citations back to the source material. | "Hybrid search over buckets with element-level citations" as the whole description. That is mechanism, not buyer value. |
| Data Extraction | Turn varied document formats into consistent structured fields, records, and reviewable outputs. | "No LLM in the loop", "QA-reconciled across agents", or claims that extraction is deterministic in every context. |
| Smart Reports | Run a defined set of grounded questions and assemble the answers into a source-backed report that can be reviewed or extended. | "Pre-compiled RAG queries" without explaining the report outcome. |
| Document Classification | Route documents by type, intent, or workflow need so the right extraction, review, or answer path runs next. | Narrow the audience with words like "scan" unless the source material is specifically scanned documents. |
| Studio UIs | Build guided GroundX product experiences for extraction, chat, reporting, review, and demo workflows. | Treat every Studio-shaped surface as a full dashboard or admin workspace. |
| Customer-facing portals | Give end users a focused GroundX-backed interface for uploading, asking, reviewing, or receiving document outputs. | Promise account, billing, or workspace controls unless the product spec calls for them. |
| Operator review UIs | Let human reviewers inspect extracted values, source evidence, confidence, and warnings before handoff. | Imply the agent removes human review where the workflow needs accountability. |
| Integrations | Connect GroundX workflows to an application's existing API, storage, callback, or review path. | Invent custom webhook behavior or claim unsupported handoffs without checking the relevant API skill. |

## Claim boundaries

- Use the patterns above as supported implementation categories.
- Use `product.md` for product state and lifecycle claims.
- Use `proof-points.md` for numbers, customer outcomes, benchmarks, and logos.
- Do not claim bulk reprocessing of historical documents under a new extraction schema with no re-ingest unless an authoritative product or API reference explicitly supports it.
- Do not say a runtime is certified or officially supported unless a current source says so. For broad compatibility, say "plugin-supporting agent runtime" or "agent surfaces such as..." rather than promising every runtime behaves identically.
- Do not imply the Harness is the exclusive GroundX integration path. Co-list MCP for connected agents and REST/SDKs for direct application integration when the surface needs the full integration landscape.

## Register

Default to prospect register unless the prompt says the reader is already a customer. Prefer "the GroundX platform", "a corpus", "existing GroundX deployments", "an evaluation", and "end users". Use "your buckets", "your existing GroundX", "your downstream systems", or "your team" only when the audience is already a customer or the user explicitly wants customer-tense copy.
