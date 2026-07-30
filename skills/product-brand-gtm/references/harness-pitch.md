# GroundX Harness Positioning

Use this reference when copy needs to explain the public GroundX Agent Harness,
the private GroundX Studio Harness, GroundX MCP, or capabilities supplied by the
host AI client. Keep capability attribution clear without turning repository
generation topology into buyer-facing product value.

## Capability attribution

| Surface | User-facing definition | Do not attribute |
| --- | --- | --- |
| **GroundX Agent Harness** | The public GroundX knowledge and workflow bundle. It gives compatible agents portable guidance for GroundX APIs, MCP, extraction, architecture, on-prem deployment, SDKs, and approved product messaging. | Private prebuilt Studio authoring, publishing, administration, or partner-lifecycle workflows, or a host client's general creation tools |
| **GroundX Studio Harness** | The private expanded AI Agent Harness with prebuilt workflows for Studio production, authoring, publishing, administration, and operational work in addition to the shared GroundX knowledge layer. | Public availability, universal runtime support, or exclusive ownership of the underlying workspace service |
| **GroundX MCP** | Optional connected execution for live GroundX operations when the server and tools are available. | The installed knowledge layer or a requirement for the Harness to remain useful |
| **Host AI client** | Capabilities supplied by Claude, Codex, ChatGPT, Gemini, or another client independently of a GroundX bundle. | A GroundX Harness capability unless the relevant GroundX skill actually ships in that bundle |

For exact file or skill membership, public/private emission, or source
generation, route contributors to bundle policy and generated manifests. Do not
copy an exhaustive inventory into product copy.

## On-Prem workspace service and Studio workflows

On-Prem customers can enable and operate the workspace service using the public
deployment, configuration, architecture, and operator guidance. GroundX Studio
Harness is separate: it supplies prebuilt Studio authoring and publishing
workflows that use the service. Do not infer that the service requires the
private bundle, and do not attribute the private workflow skills to GroundX
Agent Harness.

## Canonical short pitches

### GroundX Agent Harness

GroundX Agent Harness is the public knowledge and workflow bundle that makes
compatible AI agents fluent in GroundX, so teams can plan and implement grounded
document workflows without rediscovering the platform from scratch.

### GroundX Studio Harness

GroundX Studio Harness is the private expanded AI Agent Harness for producing
and operating GroundX Studio work, including prebuilt authoring, application
production, publishing, administration, and internal operational workflows.

### Execution relationship

The Harness supplies GroundX knowledge and workflow guidance. GroundX MCP can
execute live GroundX operations when connected. REST APIs and SDKs remain direct
application integration paths. The host client may separately supply artifact
creation or research capabilities.

## What it is

- **Category:** AI Agent Harness.
- **Form:** installed skills and references, with optional connected execution.
- **Job:** make agents fluent in GroundX so they can produce useful work without
  rediscovering product, API, design, and workflow rules.
- **Audience:** teams scaling GroundX-backed use cases beyond a one-by-one
  engineering build.
- **Status:** use `product.md` before promising availability, lifecycle, or
  runtime support for either bundle.

## Buyer-facing pattern descriptions

| Pattern | Capability supplier | Say | Do not say |
| --- | --- | --- | --- |
| Document RAG | Agent Harness knowledge plus MCP or REST/SDK execution | Ask questions over complex documents and get grounded answers with citations back to the source material. | Describe the mechanism as the whole buyer value. |
| Data Extraction | Agent Harness knowledge plus MCP, SDK, or REST execution | Turn varied document formats into structured fields, records, and reviewable outputs. | Claim extraction is deterministic in every context. |
| Smart Reports | GroundX workflow knowledge plus a Studio Harness or host artifact capability | Run grounded questions and assemble answers into a source-backed report that can be reviewed or extended. | Attribute report production to the public Agent Harness when the relevant producer does not ship there. |
| Document Classification | Agent Harness knowledge plus a supported execution path | Route documents by type, intent, or workflow need so the right extraction, review, or answer path runs next. | Claim unsupported runtime behavior. |
| Studio UIs | Studio Harness, or a separately labeled host-client capability | Build guided GroundX product experiences for extraction, chat, reporting, review, and demos. | Attribute Studio UI production to the public Agent Harness. |
| Customer-facing portals | Studio Harness, or a separately labeled host-client capability | Give end users a focused GroundX-backed interface for uploading, asking, reviewing, or receiving document outputs. | Promise account, billing, or workspace controls unless the product spec calls for them. |
| Operator review UIs | Studio Harness, or a separately labeled host-client capability | Let human reviewers inspect extracted values, source evidence, confidence, and warnings before handoff. | Imply the agent removes human review where accountability is required. |
| Integrations | Agent Harness knowledge plus MCP or REST/SDK execution | Connect GroundX workflows to an application's existing API, storage, callback, or review path. | Invent webhook behavior or unsupported handoffs. |

## Claim boundaries

- Use the patterns above as supported implementation categories.
- Use `product.md` for product state and lifecycle claims.
- Use `proof-points.md` for eligible customer outcomes, benchmarks,
  technical-corpus evidence, and partner validation. Customer-count, adoption,
  and logo claims require a current approved source supplied for the job.
- Do not claim bulk reprocessing of historical documents under a new extraction schema with no re-ingest unless an authoritative product or API reference explicitly supports it.
- Do not say a runtime is certified or officially supported unless a current source says so. For broad compatibility, say "plugin-supporting agent runtime" or "agent surfaces such as..." rather than promising every runtime behaves identically.
- Do not imply either Harness is the exclusive GroundX integration path. Co-list
  MCP for connected agents and REST/SDKs for direct application integration when
  the surface needs the full landscape.
- Do not use GroundX Agent Harness and GroundX Studio Harness as synonyms.
- Do not attribute a host-client capability to a GroundX bundle without checking
  that the relevant GroundX skill ships there.

## Register

Default to prospect register unless the prompt says the reader is already a customer. Prefer "the GroundX platform", "a corpus", "existing GroundX deployments", "an evaluation", and "end users". Use "your buckets", "your existing GroundX", "your downstream systems", or "your team" only when the audience is already a customer or the user explicitly wants customer-tense copy.
