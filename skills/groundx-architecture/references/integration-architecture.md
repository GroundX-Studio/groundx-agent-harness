# Integration Architecture

This file is a **thin inventory of integration surfaces** — the shapes through which customer systems, partner middleware, and end-user applications connect to GroundX. The architecture skill documents what surfaces exist and at what altitude; the depth (request/response shapes, exact endpoint paths, parameter schemas) lives in the harness skills (`groundx-api`, internal partner-tier API guidance, internal managed-project publish workflow, internal scaffold UI workflow). When the harness has the answer, this file routes there.

## 1. Marketing altitude

Not the canonical place — integration surface marketing is owned by `master-brand-gtm` / `product-brand-gtm`. The technical inventory below is the source of truth those skills draw from.

## 2. Product altitude

GroundX exposes a small set of integration surfaces:

- **Customer-tier REST API** — the primary surface customer applications use.
- **Customer-tier SDKs** — Python and TypeScript, both Fern-generated.
- **Workspace facade endpoints** — GroundX API control-plane routes for Studio Harness managed projects: create, git-session, deploy-config, diagnostics, publish, cleanup, and fallback file operations. Endpoint semantics live in `groundx-api`; the agent workflow lives in internal managed-project publish workflow.
- **Partner-tier REST API** — for partners managing customer accounts and provisioning customer resources.
- **Callbacks** — outbound HTTP POST notifications GroundX sends to customer-supplied URLs on ingest progress.
- **X-Ray retrieval** — the customer-facing aggregate JSON for each ingested document; usable as a per-document bulk-export pattern.
- **`ws.eyelevel.ai` websocket** — partner-tier web-chat streaming surface for chat-style request/response.
- **Customer-built frontends** — the integration pattern of building a UI that calls GroundX through the customer-tier API (often via a middleware proxy that holds the API key).

There is **no** SSO at the customer-tier API today, **no** generic streaming endpoint (only `ws.eyelevel.ai` for chat), and **no** native data-warehouse / Snowflake-share / scheduled-export integration.

## 3. Conceptual / algorithmic altitude

Three architectural ideas shape the integration surface:

**REST + SDK + Fern as the canonical surface.** The customer-tier and partner-tier REST APIs are the canonical integration surfaces for platform and partner lifecycle operations. The Python and TypeScript SDKs are Fern-generated from the OpenAPI spec (`openapi.yml`) and stay in lockstep with the customer-tier REST surface automatically; new customer-tier endpoints appear in both SDKs without hand-maintenance work. Workspace facade endpoints are a separate GroundX API control-plane surface for managed project operations and are documented in `groundx-api`, not in the public SDK surface. The exceptions are a handful of hand-maintained convenience methods in the Python SDK (`ingest`, `ingest_directories`, plus the `extract` submodule) that don't have direct REST equivalents — these are documented in `api-surface.md`.

**Callbacks, not webhooks.** GroundX uses the term "callback" for what's structurally a webhook: a `callbackUrl` field on ingest / update endpoints causes GroundX to POST progress notifications to that URL during processing, with an optional `callbackData` echo field. The integration is per-request (not subscription-based) — a customer attaches a callback URL to a specific ingest, rather than registering an endpoint that fires on all events.

**Streaming is narrow and chat-specific.** The customer-tier REST API does not support streaming responses. The only streaming-shaped surface in the architecture is the partner-tier `ws.eyelevel.ai` websocket, which is purpose-built for web-chat request/response. All other interactions (ingest, search, X-Ray retrieval, Workspace facade operations) are request/response with polling when async work is involved.

## 4. System altitude

```
customer application → groundx-python / groundx-typescript SDK ──┐
customer application → direct REST                              ──┤
agent / harness → Workspace facade REST                         ──┤
partner middleware → groundx-python / direct REST + partner key ──┤
                                                                 ─→ groundx pod (single ingress)
customer chat UI → ws.eyelevel.ai websocket ─────────────────────┘

groundx pod → workspace-api  (Workspace facade operations)

groundx pod → customer-supplied callback URL  (HTTP POST during ingest)
groundx pod → customer-supplied callback URL  (HTTP POST during extraction completion)

customer application → GET /v1/ingest/document/xray/{documentId} → file storage (capability URL)
                                                                   (or via xrayUrl in document_get response)
```

The single external ingress is `groundx`. The single external egress (for outbound integration) is the callback POST. Everything else is request/response. For the full system topology see `overview.md` § 4.4.

## 5. Implementation altitude

### 5.1 Integration surfaces — inventory

| Surface | Tier | Direction | Mechanism | Canonical reference |
| --- | --- | --- | --- | --- |
| Customer-tier REST API | Customer | Inbound | HTTPS request/response | `groundx-api` |
| Customer-tier SDKs (`groundx-python`, `groundx-typescript`) | Customer | Inbound | Fern-generated client over REST | `api-surface.md` (this skill) + `groundx-api` |
| Workspace facade endpoints | Workspace | Inbound | HTTPS request/response + polling | `groundx-api` § Workspace endpoints + internal managed-project publish workflow |
| Partner-tier REST API | Partner | Inbound | HTTPS request/response | internal partner-tier API guidance |
| Callbacks (per-request, on `callbackUrl`) | Customer | Outbound | HTTP POST | `groundx-api` § documents |
| X-Ray retrieval | Customer | Inbound (pull) | `GET /v1/ingest/document/xray/{documentId}` + `xrayUrl` capability URL | `groundx-api` § documents + `agentic-pipeline.md` § 5 |
| `ws.eyelevel.ai` websocket | Partner | Bidirectional | WebSocket | the private EyeLevel SSP frontend reference + the private GroundX Dashboard frontend reference |
| Customer-built frontends (pattern, not a surface) | Customer | Inbound | Per-customer paired-app shape | the private frontend inventory + the private Studio Harness frontend-pattern reference |
| Studio Harness scaffold (paired React/MUI + TS middleware) | Customer-tier + Partner-tier; Workspace facade for managed-project workflow | Inbound | Generated app shape | internal managed-project publish workflow + internal scaffold UI workflow + `groundx-api` Workspace reference |

### 5.2 Callbacks — what they cover

Callbacks are attached to specific ingest / update operations via the `callbackUrl` field on the request body. The optional `callbackData` field is echoed unchanged in the callback body. GroundX POSTs **one notification per document on completion** — success or error — covering the full ingest flow including the agentic pipeline and (when enabled) the extraction microservice. The callback is fire-and-forget: **GroundX does not retry**. Customers needing guaranteed delivery should poll the document status via the customer-tier API rather than rely solely on callbacks.

Callbacks are available on ingest endpoints (`document_ingestremote`, `document_crawlwebsite`, `document_update` per the harness `groundx-api` skill). Extraction does not have its own separate callback — extraction completion flows into the same document-completion callback because extraction is part of the ingest pipeline.

The exact payload shape is documented in `groundx-api`. This file does not duplicate it.

### 5.3 X-Ray as a bulk-export pattern

The X-Ray (per `agentic-pipeline.md` § 5) is the aggregated, enriched JSON for each ingested document — document and section summaries, keywords, chunk-level text in three versions, bounding boxes, page URLs, and per-chunk multimodal URLs for tables / figures. Customers retrieve the X-Ray two ways:

- `GET /v1/ingest/document/xray/{documentId}` — the canonical API endpoint.
- `xrayUrl` field on `document_get` — a capability URL pointing directly to file storage; no authentication required to fetch (the URL itself is the access token).

Customers wanting bulk export of their GroundX-understood content typically paginate `document_get`, pull each document's `xrayUrl`, and fetch the X-Ray directly. GroundX does not provide a higher-level bulk-export mechanism (no S3 sync, no Snowflake share, no scheduled CSV export) — the X-Ray-per-document pattern is the available shape.

### 5.4 `ws.eyelevel.ai` websocket

`ws.eyelevel.ai` is the partner-tier-gated websocket server used for chat-style request/response. It is consumed by EyeLevel SSP and GroundX Dashboard (per the private EyeLevel SSP frontend reference + the private GroundX Dashboard frontend reference) and is **limited to web-chat-style request/response** — not a general-purpose streaming surface for search, ingest, or other API operations.

At the integration-surface altitude, `ws.eyelevel.ai` is conceptually a sibling of `api.groundx.ai`: another callable surface from external clients, scoped to its purpose. Frontend depth lives in the frontend-* files.

### 5.5 Customer-built frontends as an integration pattern

The dozens of customer-built frontends in production (per the private frontend inventory) are themselves an integration pattern: each customer builds an application on top of the customer-tier API. The pattern is typically **frontend + middleware proxy + customer-tier API**, where the middleware holds the customer's `X-API-Key` so the frontend never sees it. The Studio Harness scaffold formalizes this pattern; older customer frontends predate the scaffold and are ad-hoc.

For the scaffold pattern see the private Studio Harness frontend-pattern reference and internal scaffold UI workflow. For the inventory of company-owned and customer-built frontends see the private frontend inventory.

### 5.6 Customer SSO — not natively supported

GroundX does not natively support SSO / OIDC / SAML at the customer-tier (per `identity-and-trust.md` § 2). Partners that need SSO for their customer-facing applications build it themselves: the partner's middleware authenticates the user via the chosen IdP, then translates that authenticated session into a partner-tier API call — either `customer_create` to provision a new GroundX customer account on first login, or `customer_login` against an already-provisioned account on subsequent logins. The `groundx-ai-middleware` historically included a register-screen hook that supported this pattern; the hook was removed from the UI but the underlying mechanism (partner-tier `customer_create` / `customer_login`) remains. There is no GroundX-provided IdP-side configuration today.

### 5.7 Legacy / unsupported integration surfaces

Several integration surfaces from the EyeLevel SSP era (WordPress plugin, Zapier integration, Marketo integration) may still exist in production deployments but are **considered legacy and unsupported**. The current architecture does not depend on them; new customer integrations should not target them. The WordPress plugin specifically continues to be supported through the legacy Lambda pipeline (per the private legacy Lambda pipeline reference). The others are out of scope for this skill — treat as historical context rather than current integration shape.

## 6. Security / compliance altitude

Callback URLs are customer-supplied and the POST happens from inside the deployment's trust boundary outward — content (event metadata, document ID, the customer-supplied `callbackData` echo) leaves the cluster on every callback. The shape of the data leaving is small (status / progress notification), not full document content. The `xrayUrl` capability URL is a credential-equivalent — possession of the URL grants access to the X-Ray without further authentication; treat it as a secret. For the broader trust-boundary inventory see `identity-and-trust.md` § 6.2.

`ws.eyelevel.ai` is partner-tier-gated. Customer-side SSO is partner-implemented and inherits the partner's IdP trust posture; the GroundX side sees only authenticated partner-tier calls. For the full identity / trust model see `identity-and-trust.md`.

## 7. Operations / SRE altitude

Callback delivery (the outbound POST) is fire-and-forget — GroundX makes **one attempt** per document on completion and **does not retry** on failure. The customer's endpoint reliability determines whether the customer hears about ingest progress at all. Customers that need guaranteed-delivery integration patterns should poll the document status via the customer-tier API rather than rely solely on callbacks. For the broader observability framing see `observability.md`.

## 8. Data architecture altitude

The integration surfaces touch every store in the system: the customer-tier, Workspace facade, and partner-tier APIs read / write the Process Metadata DB where their records live; the customer-tier API reads OpenSearch on the search path; X-Ray retrieval reads File Storage; Workspace facade operations also coordinate with the workspace runner's managed-repository storage. The callback POST contains progress metadata only, not document content. The `xrayUrl` capability URL grants direct file-storage read for the X-Ray. For canonical artifact placement see `store.md`. For data-residency implications of cross-boundary traffic on callbacks see `data-residency.md`.

## 9. Cost / FinOps altitude

Integration surfaces themselves are not significant cost drivers — the SDKs are static client libraries, callbacks are small outbound HTTP POSTs, X-Ray retrieval is a file-storage read. The dominant cost drivers (GPU services, store capacity) are exercised *through* the integration surfaces but are not properties of them. Deployment-level cost framing is owned by `groundx-on-prem`.

## 10. What this topic does not cover

- **The exact REST endpoints, request/response shapes, parameter schemas** for the customer-tier API, Workspace facade, and partner-tier API: `groundx-api`, internal partner-tier API guidance.
- **The SDK call patterns, hand-maintained extras, Fern generation**: `api-surface.md`.
- **The callback event types and payload shape**: `groundx-api` § documents.
- **The X-Ray field-by-field schema**: `agentic-pipeline.md` § 5 + `groundx-api/guides/05-document-understanding.md` § 5.
- **The Studio Harness scaffold pattern** for customer-built frontends: the private Studio Harness frontend-pattern reference, internal scaffold UI workflow, internal managed-project publish workflow.
- **The inventory of company-owned and customer-built frontends**: the private frontend inventory.
- **The legacy WordPress / Zapier / Marketo plugins**: the private legacy Lambda pipeline reference for WordPress; others are out of scope.
- **The auth model (X-API-Key, X-Customer-Key, Basic Auth login flow)**: `identity-and-trust.md`.
- **The per-tenant isolation enforcement at the API and store layers**: `multi-tenancy.md`.
- **Partner-built customer SSO patterns (partner middleware, IdP integration)**: out of scope for this skill — partner-specific.
