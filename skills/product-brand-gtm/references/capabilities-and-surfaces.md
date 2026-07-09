# Functional Capabilities and Consumption Surfaces

GroundX has two functional capabilities and three buyer-facing consumption surfaces:
Harness, Studio, and APIs/SDKs. GroundX MCP is the preferred connected-agent execution path
inside the direct-integration surface. These are independent axes — a buyer picks one (or
both) capabilities and consumes them through one (or more) surfaces. Lead with the Harness
when the pain is implementation velocity. For an installed agent that already has GroundX
MCP connected, MCP is the preferred tool-execution path; the Harness is the knowledge and
workflow layer that helps the agent use GroundX well.

For the technical mechanism that powers both capabilities, see `technical-architecture.md`.

## 1. The two functional capabilities

A buyer can use either or both.

### 1.1 Document understanding

Convert documents into structured outputs with human-like reasoning — not pure OCR. Use cases:

- **Data extraction.** Pull fields, values, relationships, and context from documents with precision. The same field pulled from 40 different document formats can be normalized into consistent structured output.
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

### 2.1 GroundX Studio Harness — the AI Agent Harness

The Harness is an **AI Agent Harness**: a plugin of skills, connectors, and design patterns that gives agents — Claude, Gemini, ChatGPT, Replit, Cursor, smolagents, openclaw, or any plugin-supporting agent framework — fluency in GroundX so they can build robust end-user or system integrations.

**Why lead with it.** This is GroundX's answer to the implementation-scale pain (*"I have 500 AI agent use cases, how am I going to implement them all?"* — see `buyer.md` § 1). Agents that know GroundX intimately stand up new integrations dramatically faster than a one-by-one engineering build.

**Integration patterns it supports.** API workflow integrations, connected-agent MCP workflows, plugin agentic integrations, customized UI.

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

| Capability \ Surface | Studio Harness | Studio (UI) | Direct Integration (API / SDK / MCP) |
| --- | --- | --- | --- |
| Document understanding | Agents ingest + extract from any framework | Extract use case in the UI | REST/SDK ingest + extraction API; MCP ingest when connected |
| Full end-to-end RAG | Agents ingest + retrieve + ground answers from any framework | Interact and Report use cases in the UI | REST/SDK search + retrieval API; MCP search when connected |

## 4. How to talk about the matrix in a pitch

The matrix is a closing tool, not an opening one. Lead with the capability the buyer cares
about (extraction for a CFO; RAG for a customer-service exec; both for a CIO). Then map to
the consumption surface that fits the team — Harness for engineering velocity, Studio for
non-technical immediate use, APIs/SDKs for engineering embed, and MCP for connected-agent
operation inside that direct-integration path.

A common bad framing: pitching three surfaces as if they're the value prop. The value prop is the accuracy, on-prem story, integrated architecture, and heritage (see `differentiation.md`). Surfaces are how the buyer touches that value, not the value itself.

## 5. What this section does not claim

- The surfaces are not feature-different — same intelligence, same accuracy, same on-prem deployability.
- The Harness is not a competitive moat. It is the answer to a specific articulated pain. See `differentiation.md` § 5.
- The Studio UI is not a separate product roadmap. It is a packaged consumption surface over the same engine.
- MCP is not just a thin wrapper in agent contexts. When connected, it is the preferred way an agent operates GroundX tools. REST and SDKs remain the direct integration and fallback surfaces.
