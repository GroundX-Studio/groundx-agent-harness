# Identity & Trust

GroundX's identity model is **intentionally narrow**: a single API-key header (`X-API-Key`) carries both customer-tier and partner-tier credentials; partner-on-behalf-of-customer requests add `X-Customer-Key`; Basic Auth is reserved for the partner-tier login / register flow that issues partner keys. No key rotation, no per-customer RBAC, no SSO. The trust boundary of the deployment is well-defined and crossed only by a small set of explicit configurations (3rd-party LLM, Google Cloud Vision OCR). This file documents the auth surfaces, the trust-boundary shape, and the things that are explicitly *not* part of the model — so downstream skills don't claim them.

## 1. Marketing altitude

Not the canonical place — auth and trust shape are buyer-level discussions, not marketing-level. The marketing-altitude story about security defers to deployment posture (`groundx-on-prem`) and `master-brand-gtm` / `product-brand-gtm` for the words.

## 2. Product altitude

GroundX authenticates API callers through a small set of header patterns:

- **Customer-tier** — the surface customers and customer-built applications use. `X-API-Key` set to the customer's key. Issued by the partner (via the partner API) and lives for the life of the account.
- **Partner-tier (partner account)** — partners, internal middleware, and the Studio Harness operating on their own partner account. `X-API-Key` set to the partner key; no `X-Customer-Key`.
- **Partner-tier (on behalf of a customer)** — partners operating *as* one of their managed customer accounts. `X-API-Key` set to the partner key; `X-Customer-Key` set to the target customer's key.
- **Basic Auth** — reserved for the partner-tier login / register / password-reset flow that exchanges username + password for a partner API key. Not used for ongoing API operations.

There is **no SSO, no OIDC, no SAML** at the customer-tier today. There is **no RBAC** inside a customer account — the `X-API-Key` is the entire customer-tier authentication surface. Query-time scoping (limiting a request to specific buckets, groups, or documents) is done via the API's filter parameters, not via a roles/users model.

## 3. Conceptual / algorithmic altitude

Three architectural ideas shape the identity model:

**Issue-once API keys, not rotation.** Customer API keys are issued once and live with the account. The system does not maintain a key-rotation mechanism. Operationally, this means a customer's key is its long-term identity — and a leaked key requires partner-side intervention (revocation + re-issue) rather than a rolling rotation flow.

**Single ingress; in-namespace trust beyond it.** All external API calls — customer-tier and partner-tier — enter through the `groundx` pod (per `overview.md` § 2). `groundx` authenticates the request and hands work off through the queue layer. Downstream pods do not re-authenticate; they are inherently trusted by virtue of living inside the same Kubernetes namespace. The namespace itself is the trust enclosure; auth lives at the external boundary.

**Backing-service-owned encryption-at-rest.** GroundX does not maintain a separate KMS or key-management layer. Encryption-at-rest is owned by the chosen backing services — RDS for MySQL, OpenSearch's own encryption, S3 SSE-KMS for file storage. Deployments inherit whatever encryption posture their `values.yaml` selections provide.

## 4. System altitude

The identity surfaces and where they're enforced:

```
external caller → groundx (auth check)  ───  customer X-API-Key (most calls)
                                        └──  partner/admin API key (Workspace facade, customer provisioning, customer-scoped operations via X-Customer-Key)

groundx → Redis (cached auth) → MySQL/RDS (auth of record)        on cache miss
                              → workspace-api (Workspace facade routing only; not externally reachable)
                              → queue layer → downstream pods (no re-auth)
```

For the full system topology see `overview.md` § 2. For the queue handoff after auth see `ingest-service.md` § 5.

## 5. Implementation altitude

### 5.1 Auth surfaces

| Pattern | Headers | Identity | Rotation | Used by |
| --- | --- | --- | --- | --- |
| Customer-tier | `X-API-Key: <customer key>` | Customer account | **None — issue once** | Customer applications; SDKs; customer-built frontends; the Studio Harness's customer-tier surfaces |
| Partner-tier (partner account) | `X-API-Key: <partner key>` | Partner account itself | Not specified at this altitude | Partner middleware operating on its own account; partner-account introspection |
| Partner-tier (on behalf of a customer) | `X-API-Key: <partner key>` + `X-Customer-Key: <customer key>` | Partner authenticated; acting as the named customer | (inherits from partner key) | Partner middleware operating on behalf of one of its managed customers |
| Workspace facade | `X-API-Key: <workspace-capable key>` | Partner/admin or workspace-enabled account | (inherits from account key) | Studio Harness managed-project operations via `groundx-api` Workspace endpoints |
| Basic Auth (login / register only) | `Authorization: Basic <user:pass>` | Partner credential exchange | n/a (credential flow) | Partner login, register, password reset — exchanges username + password for a partner API key. Not used for ongoing API operations. |

*Source: auth headers and the X-API-Key / X-Customer-Key composition pattern align with GroundX customer and partner API documentation. The "issue-once, no rotation" + "no customer-tier SSO/OIDC/SAML" framing is a scoped internal-review finding, 2026-05-17.*

### 5.2 Auth lookup path

`groundx` resolves auth on every request via the standard cached-then-DB pattern (per `store.md` § 5.2):

1. Check Redis for the cached auth record.
2. On cache miss, read from MySQL/RDS and populate Redis.

This applies to every API request — search included; it is not search-specific.

### 5.3 In-namespace trust (a feature, not a gap)

Once `groundx` authenticates a request, downstream pods receive the work through the queue layer and do not re-authenticate. They are inherently trusted because they live inside the same Kubernetes namespace as `groundx`. The Kubernetes namespace boundary is the trust enclosure; the authentication boundary is the `groundx` ingress at the external edge. This is what makes the **stateless-pod + queue-handoff** architecture clean to operate: pods don't carry credentials or replay auth checks on internal work.

### 5.4 What is NOT in the model

This list exists because downstream skills must not claim these:

- **No customer API key rotation.** Issue-once.
- **No RBAC inside a customer account.** `X-API-Key` is the entire customer-tier surface; per-call scope narrowing is done via the API's filter parameters.
- **No SSO / OIDC / SAML.** Not supported today at the customer tier.
- **No GroundX-managed KMS.** Encryption-at-rest is delegated to backing services.

### 5.5 Workspace runner ingress invariant

The workspace runner (`workspace-api` + 5 worker pods, per `workspace-architecture.md`) is reachable **only through `groundx` as the Workspace facade**. There is no direct external path. This is an architectural invariant.

## 6. Security / compliance altitude

### 6.1 Audit logging

The `groundx` pod emits a raw log that catalogs every API action. **This is the only comprehensive audit log GroundX maintains.** Everything else — store-level logs, queue-level logs, downstream-pod logs — is whatever the backing services and pod runtimes emit natively. For the broader observability framing see `observability.md`.

### 6.2 Trust boundary

The default deployment is **closed** — document content and customer data do not leave the deployment's trust boundary on the ingest, search, or extraction paths. Two configurations cross the boundary:

| Crossing | Triggered by | What leaves the deployment |
| --- | --- | --- |
| 3rd-party LLM call | `summary.serviceType` set to a hosted engine (`openai`, `azure`, `openai-base64`, `deep-infra`, `eyelevel` pointed at a hosted endpoint) | Document content during the agentic pipeline's LLM calls (per `summary-service.md` § 6 + `agentic-pipeline.md` § 6) |
| Google Cloud Vision OCR | `gcv.json` GCP service account file provided | Page images on every OCR call (per `layout-ocr.md` § 6) |

The bundled-self-hosted summary stack and the customer-hosted-LLM mode both keep document content inside the deployment's trust boundary. The hybrid-search path is **entirely in-cluster** regardless of which summary mode is in use during ingest (per `hybrid-search.md` § 6).

### 6.3 Blast radius of compromised credentials

| Credential leaked | Attacker can |
| --- | --- |
| Customer `X-API-Key` | Read and write everything in that single customer account |
| Partner Basic Auth | Read AND write **everything in every customer account** the partner manages, plus Partner lifecycle/provisioning operations |
| Workspace-capable key | Run managed-project Workspace facade operations exposed through `groundx-api` when the account has that capability |

There is no scope-narrowing inside the partner-tier — a leaked partner key has full blast radius across all customers the partner provisions.

### 6.4 Encryption-at-rest

Delegated to the backing services per `values.yaml`:

- MySQL/RDS — backing-service encryption (RDS encryption-at-rest, or the equivalent for self-hosted MySQL).
- OpenSearch — OpenSearch's own encryption.
- File storage (MinIO/S3) — S3 SSE-KMS or MinIO's encryption configuration.

GroundX does not maintain a separate KMS layer. Compliance-sensitive deployments inherit whatever the chosen backings provide.

## 7. Operations / SRE altitude

Auth lookups hit the Redis cache for most requests; cache misses fall through to MySQL/RDS. A surge in cache misses (e.g., after a Redis restart) increases MySQL/RDS load. For the broader observability framing see `observability.md`. For the auth-lookup pattern see `store.md` § 5.2.

## 8. Data architecture altitude

Auth state lives in the **Process Metadata DB** (MySQL/RDS for durable rows; Redis for cached hot records). Per-customer isolation enforcement at the data-store level — how customer rows / indices / file prefixes are kept separate — is documented in `multi-tenancy.md`. The audit log emitted by `groundx` is the canonical record of authenticated API actions; per `observability.md` for storage and retention specifics.

## 9. Cost / FinOps altitude

Identity and trust are not significant cost drivers at this altitude — the auth path is a Redis hit on the cached case and a small MySQL/RDS lookup on the miss case. The cost implications of trust-boundary choices (3rd-party LLM vs bundled self-hosted, Tesseract vs GCV) live with the respective subsystems (`summary-service.md` § 9, `layout-ocr.md` § 9).

## 10. What this topic does not cover

- **Per-customer isolation enforcement at the data-store level** (how rows / indices / file prefixes are kept separate): `multi-tenancy.md`.
- **The partner API surface and customer lifecycle operations** (registration, login, password reset, profile lookup, customer key provisioning): partner API documentation.
- **The customer-tier API surface and filter parameters** (the scope-narrowing mechanism inside a customer account): `groundx-api`.
- **What the `metrics` pod measures + the audit-log retention story**: `observability.md`.
- **Compliance certifications (GDPR, HIPAA, FedRAMP) and regional residency**: `data-residency.md`.
- **The `groundx` audit-log retention / storage / query surface** beyond noting it exists: `observability.md`.
