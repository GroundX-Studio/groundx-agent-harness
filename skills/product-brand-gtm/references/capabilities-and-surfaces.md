# Functional Capabilities and Consumption Surfaces

GroundX has two functional capabilities and three buyer-facing consumption
surfaces: the Harness knowledge layer, Studio UI, and direct integrations.
GroundX MCP is optional connected execution inside the direct-integration
surface. These are independent axes — a buyer picks one or both capabilities and
uses one or more surfaces.

The Harness surface has two bundles: the public GroundX Agent Harness and the
private expanded GroundX Studio Harness. The host AI client may supply separate
creation capabilities; do not attribute those to a GroundX bundle.

For the technical mechanism that powers both capabilities, see `technical-architecture.md`.

## 1. The two functional capabilities

A buyer can use either or both.

### 1.1 Document understanding

Convert documents into structured outputs with human-like reasoning — not pure OCR. Use cases:

- **Data extraction.** Pull fields, values, relationships, and context from
  varied document formats and normalize them into consistent structured output.
- **Structured data for graph databases.** Populate knowledge graphs from documents at scale.
- **Fine-tuning data for models.** Turn document corpora into training data in the formats models expect.

GroundX is strongest where document understanding must become structured, usable data —
that capability is what powers everything else (see `technical-architecture.md`).

### 1.2 Full end-to-end RAG

The same ingest pipeline, plus the proprietary hybrid search architecture, supports
high-accuracy retrieval for grounded LLM answers. Use cases:

- **Chat with your documents** with source citations and attribution.
- **Agentic workflows that need to ground answers** in private corporate knowledge.
- **Smart reports** — pre-compiled RAG queries assembled into a report format with follow-up chat.

GroundX's RAG accuracy comes from the intentional design of the ingest to produce objects the search was built for. See `technical-architecture.md` § 4.

## 2. The three buyer-facing consumption surfaces

Pick by where the user touches the work; this is not a universal priority order.
Lead with the Harness when the pain is implementation velocity, Studio when a business user
wants a ready UI, and APIs/SDKs when an engineering team is embedding GroundX directly. In
the direct-integration surface, use MCP when a connected agent operates GroundX tools; use
REST/SDKs for direct app/backend integration, development targets, and fallback paths.

### 2.1 GroundX Harnesses — the AI Agent Harness surface

- **GroundX Agent Harness** is the public GroundX knowledge and workflow bundle.
- **GroundX On-Prem workspace service** can be enabled and operated by customers
  using public deployment and operator guidance.
- **GroundX Studio Harness** is the private expanded bundle with prebuilt Studio
  production, authoring, publishing, administration, and operational workflows
  that may use the workspace service.
- **GroundX MCP** is optional connected execution, separate from either
  installed knowledge bundle.
- **Host-agent capabilities** remain separately labeled when Claude, Codex,
  ChatGPT, Gemini, or another client supplies them independently.

**Why lead with the Harness surface.** It answers implementation-scale pain by
giving agents GroundX-specific knowledge instead of forcing each team to
rediscover the platform for every workflow.

Use `harness-pitch.md` for buyer-facing pattern attribution. Use bundle policy
and generated manifests, not GTM prose, for exact membership.

### 2.2 GroundX Studio — the no-code single UI

A single web product with three common use cases ready out of the box:

- **Extract** — data extraction.
- **Interact** — chat interactions / RAG.
- **Report** — smart pre-compiled RAG queries assembled into a report, with follow-up chat.

For non-technical immediate use. Zero engineering lift. Live in days. Built for business users, ops teams, departmental users — the buyer who wants a working tool, not a platform.

Use *Extract*, *Interact*, *Report* as the canonical product names. Do not invent alternates.

### 2.3 Direct APIs, SDKs, and GroundX MCP

For engineering teams embedding GroundX in their own SaaS, internal platforms, or existing
apps, REST APIs and SDKs are the direct integration paths. For AI agents, the GroundX MCP
server is the preferred execution path when the tools are connected and the target
environment supports them. GroundX runs behind the scenes; the end user does not need to
know which direct-integration path is in use.

## 3. The capability-by-surface matrix

You can mix any capability with any surface.

| Capability \ Surface | Harness knowledge layer | Studio (UI) | Direct Integration (API / SDK / MCP) |
| --- | --- | --- | --- |
| Document understanding | Guide agents to ingest and extract through a supported execution path; prebuilt Studio production workflows require the private bundle or a separately labeled host capability | Extract use case in the UI | REST/SDK ingest + extraction API; MCP ingest when connected |
| Full end-to-end RAG | Guide agents to ingest, retrieve, and ground answers through a supported execution path | Interact and Report use cases in the UI | REST/SDK search + retrieval API; MCP search when connected |

## 4. How to talk about the matrix in a pitch

The matrix is a closing tool, not an opening one. Lead with the capability the buyer cares
about (extraction for a CFO; RAG for a customer-service exec; both for a CIO).
Then map to the consumption surface that fits the team — the appropriate Harness
bundle for agent guidance, Studio for non-technical use, APIs/SDKs for
engineering embed, and MCP for connected-agent operation inside the
direct-integration path.

A common bad framing: pitching three surfaces as if they're the value prop. The value prop is the accuracy, on-prem story, integrated architecture, and heritage (see `differentiation.md`). Surfaces are how the buyer touches that value, not the value itself.

## 5. What this section does not claim

- The surfaces are not feature-different — same intelligence, same accuracy, same on-prem deployability.
- The Harness is not a competitive moat. It is the answer to a specific articulated pain. See `differentiation.md` § 5.
- The Studio UI is not a separate product roadmap. It is a packaged consumption surface over the same engine.
- MCP is not just a thin wrapper in agent contexts. When connected, it is the preferred way an agent operates GroundX tools. REST and SDKs remain the direct integration and fallback surfaces.
