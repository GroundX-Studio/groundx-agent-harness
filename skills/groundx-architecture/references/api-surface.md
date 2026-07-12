# API Surface: SDKs, REST, Docs

The external API surface to GroundX consists of three things: two language SDKs (`groundx-python` and `groundx-typescript`), the direct REST API, and a public documentation site. SDK baselines and the docs site are generated from a single OpenAPI specification; both SDKs add hand-maintained ergonomic methods on top. This file describes the *shape* of the surface, not the installed-agent execution order. For call patterns, dev/prod base URLs, and semantics see `groundx-api` for customer-tier and Workspace facade behavior. Partner-tier lifecycle behavior is separate from this public SDK surface. Installed agents should follow the owning API skill's SDK/REST guidance; MCP is optional for prod only.

## 1. Marketing altitude

GroundX ships first-class Python and TypeScript SDKs plus a direct REST API. SDK baselines and the public docs site are generated from the same OpenAPI specification, so they stay in sync with the API — customers using the SDKs are never far from the latest capabilities.

## 2. Product altitude

Three external surfaces today: the **`groundx-python`** SDK, the **`groundx-typescript`** SDK, and the direct **REST API**. Both SDKs cover customer-tier operations. The Python SDK additionally ships a hand-maintained `extract` submodule, high-level extraction workflow helpers (`load_extraction_definition`, `load_extraction_definition_from_yaml`, `load_extraction_definition_from_workflow`, `create_extraction_workflow`, `update_extraction_workflow`), and convenience methods `ingest` and `ingest_directories`; the TypeScript SDK ships a hand-maintained `ingest` method. Workspace facade operations (managed projects, git sessions, deploy config, diagnostics, publish, cleanup) and Partner-tier operations (customer lifecycle, project / bucket / group setup) are reachable outside the SDKs. Public docs are at **`docs.eyelevel.ai`**. For call semantics and authentication details see `groundx-api` for customer and Workspace facade behavior; Partner lifecycle/resource behavior is outside this public SDK-surface topic.

## 3. Conceptual / algorithmic altitude

The external API surface follows a **spec-first** design pattern: a single OpenAPI specification is the source of truth, and Fern (a third-party SDK generator) produces both the SDK baselines and the public docs site from it. This is what keeps Python, TypeScript, and the docs in lockstep as the API evolves. The hand-maintained methods on top of each SDK (`extract` submodule, high-level extraction workflow helpers, and `ingest` / `ingest_directories` in Python; `ingest` in TypeScript) exist for three reasons: **convenience** (wrapping multi-step workflows like upload + register + poll into a single call), **Python's popularity** (the Python SDK gets richer ergonomic extras than TypeScript because it's the primary SDK in the ecosystem), and **business logic that can't be expressed in OpenAPI** (anything procedural or stateful — poll loops, multi-step orchestration — has to live in code, not in the spec). The pattern is most directly meaningful to anyone extending the SDKs or the docs: the spec is where API changes start.

## 4. System altitude

Not the canonical place for this content — see `overview.md` § 4.4 and the `groundx` pod. The API surface is an external client tier; the system-altitude topology lives in `overview.md`. All external surfaces converge on `groundx` as the single ingress.

## 5. Implementation altitude

**The three surfaces:**

| Surface | Generated from | Hand-maintained extras |
| --- | --- | --- |
| `groundx-python` SDK | OpenAPI spec via Fern | `extract` submodule; high-level extraction workflow helpers; `ingest`; `ingest_directories` |
| `groundx-typescript` SDK | OpenAPI spec via Fern | `ingest` (no `ingest_directories`; no `extract` submodule) |
| Direct REST API | OpenAPI spec (the spec IS the API contract) | — |
| Public docs site (`docs.eyelevel.ai`) | OpenAPI spec via Fern | — |

**Generation pipeline:** the OpenAPI spec is the canonical source. When the API changes, the spec is updated and Fern regenerates SDKs and docs in lockstep. The hand-maintained methods (Python's `extract` submodule + extraction workflow helpers + `ingest` + `ingest_directories`; TypeScript's `ingest`) are **ignored by Fern** during regeneration — they live in the SDK repos directly and are versioned alongside the Fern-generated baseline.

**SDK coverage:**

- Both SDKs cover **customer-tier** operations only.
- **Workspace facade** operations (managed projects, git sessions, deploy config, diagnostics, publish, cleanup) are outside SDK coverage. See the GroundX API skill's Workspace endpoint guidance for route semantics.
- **Partner-tier** operations (customer lifecycle, project / bucket / group setup) are outside SDK coverage and outside this public SDK-surface topic.

**Adding or extending a surface:** changes to the API surface start with the OpenAPI spec, not the SDKs or docs — Fern regenerates the rest. Hand-maintained extras live in the SDK repos and aren't touched by Fern regen.

## 6. Security / compliance altitude

Customer-tier API access uses customer-tier credentials; each customer is a single customer account to GroundX, with key count and key management up to the customer. Partner-tier API access uses partner credentials. Both auth flows enter through `groundx`. The full identity and trust model lives in `identity-and-trust.md` — refer there for the canonical security framing across the API surface.

## 7. Operations / SRE altitude

Not the canonical place — see `observability.md`. The API surface itself does not have meaningful SRE-altitude content separate from the `groundx` pod's metrics (API response-time thresholds; see `overview.md` § 4.7).

## 8. Data architecture altitude

Not the canonical place — see `data-residency.md`. The API surface is a transport layer; data-architecture concerns are downstream of the request.

## 9. Cost / FinOps altitude

The SDKs themselves carry no runtime cost. Per-call cost lives at the deployment level — the `groundx` pod handles each request and runs the rest of the pipeline. Deployment-level cost framing is owned by `groundx-on-prem`.

## 10. What this topic does not cover

- **Call semantics, endpoint behavior, auth header format, error codes, retry behavior:** `groundx-api` for customer-tier and Workspace facade behavior; Partner-tier details are outside this public SDK-surface topic.
- **The `groundx` pod itself** (the API Handler that all external surfaces hit): `overview.md` § 4.5, `ingest-service.md`, and `search-service.md`.
- **Frontends that consume the API:** `integration-architecture.md` covers the pattern; per-frontend repo inventories are outside this public architecture topic.
- **The Agent Harness as a development surface above the API:** Harness publishing and UI-building skills own the workflow details; this file covers only API-surface shape.
