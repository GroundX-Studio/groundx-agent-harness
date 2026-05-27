# Multi-Tenancy

GroundX is a **single-cluster, ownership-tagged** multi-tenant architecture. There is no per-customer namespace, per-customer index, or per-customer database. Every customer-owned resource (project / group / bucket / document) carries an **owner username**, and the `groundx` pod injects that ownership filter into every query — directly on the API filter parameters or indirectly through bucket / document IDs. Partners can act on behalf of any customer they own; that's the entire partner-tier privilege.

This file documents the tenancy model. Per-file ingest limits, per-customer quotas, the project / group / bucket / document hierarchy details, bucket transfer mechanics, and the API filter parameters all have canonical homes in GroundX customer API docs and partner API docs — this file routes there for depth.

## 1. Marketing altitude

Not the canonical place — tenancy shape is a buyer / compliance discussion, not marketing. The customer-facing framing of "your data is yours" defers to `master-brand-gtm` / `product-brand-gtm` for the words; the architectural facts that back those claims live here and in `identity-and-trust.md`.

## 2. Product altitude

Every GroundX customer account owns its projects, groups, buckets, and documents. Partners that provision the customer can also access everything that customer owns — that's the contractual partner privilege. Inside a customer account, the `X-API-Key` is the entire access surface; narrower scoping (limit to specific buckets or documents) is done via the API's filter parameters at query time.

There is one shared backend cluster and one shared set of stores; customers are kept separate by **owner-username tagging** on every customer-owned record and an ownership check on every request.

## 3. Conceptual / algorithmic altitude

Three architectural ideas drive the tenancy model:

**Ownership lives on the resource, not the namespace.** Every customer-owned resource (project, group, bucket, document) records an **owner username** — the unique UUID of the customer account that owns it. (The customer username can also be used as an API key, per `identity-and-trust.md` § 5.1.) There is no per-customer table, per-customer index, or per-customer file-storage bucket. Isolation is enforced by filtering queries to records whose owner matches the authenticated caller.

**Partner ownership extends customer ownership.** When a partner provisions a customer, the partner can subsequently access everything that customer owns — the partner identity gets the same effective ownership as the customer. There is no scope-narrowing inside the partner-tier; a partner can act as any of its managed customers (per `identity-and-trust.md` § 6.3).

**The filter is injected at `groundx`, not at the store.** Every customer-tier query that hits `groundx` is checked: customer queries verify the customer has access to the requested resource; partner queries verify the partner owns (directly or transitively) the customer being acted on. Store-level filtering (OpenSearch fields, file-storage keys) carries the same owner identity indirectly — through `fileID` (bucket ID, which is owner-tagged) and `documentID` (which is bucket-tagged, transitively owner-tagged). The architecture's primary tenancy enforcement is at the `groundx` API layer; store-level tagging is the backing structure that lets the API filter cleanly.

## 4. System altitude

```
caller (X-API-Key + optional X-Customer-Key) → groundx (ownership check)
                                              ├── MySQL/RDS  ← rows filtered by owner username
                                              ├── OpenSearch ← queries pre-filtered by fileID / documentID (owner-tagged via bucket)
                                              └── File storage ← keys keyed by bucket; bucket has owner username
```

There is **no separate tenant-namespace boundary** at the Kubernetes / cluster level — the same `groundx` + downstream-pod set serves every customer. The trust enclosure is the namespace as a whole (per `identity-and-trust.md` § 5.3); the tenant separator is owner-username tagging at the resource layer.

For the auth surfaces feeding the ownership check see `identity-and-trust.md` § 5.1. For the full system topology see `overview.md` § 4.4.

## 5. Implementation altitude

### 5.1 Tenant hierarchy

| Concept | Tier | Cardinality with customer | Cardinality with bucket | Searchable | Notes |
| --- | --- | --- | --- | --- | --- |
| **Customer** | (root) | (self) | 1 customer : many buckets | n/a | The unit of ownership |
| **Project** | Partner-tier only | 1 customer : many projects | Many buckets per project; bucket can belong to at most one project | Yes (treated as a collection of buckets at search time) | Managed via the partner API. Carries metadata in a dedicated project table; supports per-project pre / post processors. Not exposed at the customer-tier API |
| **Group** | Customer-tier | 1 customer : many groups | Bucket can belong to many groups (many-to-many); recommended 1–4 buckets per group for reranker quality | Yes (treated as a collection of buckets at search time) | Managed via the customer-tier API. No dedicated metadata table. Was called "project" in older customer-tier documentation; the customer-tier surface uses "group" today |
| **Bucket** | Both tiers | 1 customer : many buckets | (self) | Yes | The unit of physical isolation; **bucket-level ownership transfer is supported** through the partner API |
| **Document** | Customer-tier | 1 customer : many docs | 1 bucket : many docs (document has 1:1 relationship with bucket) | Yes | The unit of ingest |

Projects and groups are **both collections-of-buckets** at search time — both fan out to a list of bucket IDs (called `fileID` in OpenSearch) — but they live at **different tiers** and are **not interchangeable**. Projects exist only at the partner-tier API: a partner creates and manages projects on behalf of a customer; a bucket can belong to at most one project (many-to-one). Groups exist at the customer-tier API: customers create and manage their own groups; a bucket can belong to many groups (many-to-many). Projects carry their own metadata table and support per-project pre / post processors that groups don't. The customer API docs carry the group schema; partner API docs carry the project schema. This file stays at the relationship-shape altitude.

### 5.2 Ownership records

Every customer-owned record carries the **owner username**. For the customer-tier surface, the owner is the customer's UUID. For the partner-tier surface, the partner can also act as owner against any customer account it provisioned. Buckets carry the owner username explicitly; projects / groups / documents inherit it transitively (project / group via attached buckets; document via its bucket).

### 5.3 Bucket transfer

Bucket transfer is supported through the partner API (`POST /bucket/transfer/<bucketId>`). The mechanism is straightforward: **the owner username on the bucket changes to the receiving customer**. No artifacts move physically; no document records get re-tagged; the documents continue to live in the same bucket, and the bucket's owner is now a different customer. This is what makes bucket transfer cheap — it's a metadata update, not a data migration.

### 5.4 Partner accounts as tenants

A partner account is **its own fully functional GroundX account** — it can own projects, groups, buckets, and documents just like any customer account. The partner privilege is additive: a partner can act on its own account *and* on any of its managed customer accounts. One pattern this enables: a partner builds a bucket of shared content on its own account, then provisions new customers with a copy of that content (or shared access) via bucket transfer or duplication.

### 5.5 OpenSearch tenancy mechanism

OpenSearch is **one shared cluster** with one set of indices. Per-chunk records carry `fileID` (the bucket ID) and `documentID`. Every search query at `groundx` is pre-filtered by one or more `fileID`, one or more `documentID`, or both. Because buckets are owner-tagged, the `fileID` filter transitively enforces customer ownership at the index. Project and group searches resolve to a list of `fileID` values and apply the standard pre-filter.

### 5.6 File storage tenancy mechanism

File storage is **one shared object store** with key conventions per bucket. Buckets are the unit of physical isolation — every file artifact lives under the bucket that owns it, and the bucket's owner username controls access.

## 6. Security / compliance altitude

### 6.1 Cross-customer leakage prevention

Cross-customer isolation is enforced in **two layers**:

1. **`groundx` API layer** — every customer-tier query is checked against the authenticated caller's owner username before any downstream work happens. Partner-tier queries are checked against the partner's set of owned customers.
2. **Store-level ownership check** — the bucket-access validation runs against the customer username, confirming the caller has access to the bucket(s) the query touches. This is what makes the `fileID` / `documentID` pre-filter on OpenSearch and the bucket-keyed access on file storage trustable: the bucket's owner-username is the gating record, and the store-level lookup validates against it.

If a query escapes the `groundx` API-layer check, the store-level ownership check on the bucket still catches cross-customer access. Both layers gate on the customer username; the API layer scopes by request shape, the store-level layer scopes by bucket ownership.

### 6.2 Partner blast radius

A partner has the same effective access as every customer it provisions (per `identity-and-trust.md` § 6.3). A leaked partner key compromises every customer under the partner. There is no partial / read-only / per-resource scope-narrowing at the partner tier.

### 6.3 Bucket transfer security implications

Bucket transfer is a powerful primitive — it relocates ownership without moving data. Partners initiate it; the receiving customer becomes the new owner; previous-owner access is removed. **The destination customer must be owned by the same partner that initiates the transfer** — partners can shuffle buckets freely within their managed customer base, but they cannot transfer a bucket to a customer they don't own. The receiving partner-of-the-new-owner is necessarily the same partner that initiated, since both endpoints must be under that partner's ownership.

## 7. Operations / SRE altitude

**File ingestion rate limits are enforced in `groundx`.** Per-file hard limits (max page count, max file size, max words / rows for tabular formats) and per-batch limits (max documents per ingest request) all apply at ingest time. The canonical schedule lives in `groundx-api` (specifically the errors-and-limits reference). Different account tiers (trial vs. subscription) have different per-file caps.

**No API rate limits on search at the architecture level.** Beyond the AWS API Gateway DDoS protection on the cloud-service deployment, there are no per-customer search-rate caps in the GroundX pods themselves. On-prem deployments inherit whatever rate-limiting the deployer wires at the ingress layer; the GroundX pods do not enforce rate limits internally.

For broader metrics and alerting see `observability.md`.

## 8. Data architecture altitude

### 8.1 Per-customer quotas

Per-customer quota tracking exists for **token usage** and **search counts** — exposed via the `customer_get` endpoint's `subscription.meters` field (`fileTokens.value` / `fileTokens.max` and `searches.value` / `searches.max`). The harness `groundx-api` skill carries the canonical schedule. The architecture skill does NOT document per-bucket or per-customer **storage size** caps — these are not enforced at the architecture level today.

### 8.2 Per-file ingest hard limits

Per-file hard caps (page count, file size, document-per-batch) are documented authoritatively in `groundx-api/references/08-errors-and-limits.md`. The architecture skill does not duplicate the schedule.

### 8.3 Cross-customer data sharing

The only sanctioned cross-customer data path is **bucket transfer** initiated by a partner. There is no shared / public corpus, no inter-customer search, no read-only sharing primitive. Customers that need shared content rely on partner-orchestrated bucket transfer or duplicate-on-provision patterns (per § 5.4).

## 9. Cost / FinOps altitude

The tenancy model has cost implications at three layers:

- **Store sharing** keeps marginal cost per customer low — one OpenSearch cluster, one file-storage bucket, one MySQL/RDS instance serve all customers in a deployment. There's no per-customer infrastructure overhead.
- **Per-customer quotas** (`fileTokens.max`, `searches.max`) are the per-customer cost surface. They cap the most expensive operations (LLM token spend on ingest, ranker GPU work on search).
- **Per-file ingest hard limits** prevent runaway cost from a single oversized document.

Deployment-level cost framing is owned by `groundx-on-prem`.

## 10. What this topic does not cover

- **The exact per-file rate-limit schedule** (page counts, file size, batch size by account tier): `groundx-api` § errors-and-limits.
- **The `subscription.meters` schema** and other customer-profile fields: `groundx-api` § customer-get.
- **The project / bucket / group endpoint surface** (CRUD, search, transfer mechanics, attach / detach): `groundx-api` (customer-tier) and partner API docs (partner-tier).
- **The X-Ray retrieval pattern** (the customer-facing aggregated artifact): `groundx-api` + `agentic-pipeline.md` § 5.
- **Auth surfaces (X-API-Key, X-Customer-Key, Basic Auth) and the no-rotation / no-RBAC / no-SSO posture**: `identity-and-trust.md`.
- **The trust-boundary shape (what crosses the deployment boundary)**: `identity-and-trust.md` § 6.2.
- **The Kubernetes-namespace trust enclosure**: `identity-and-trust.md` § 5.3.
- **Per-customer audit logging**: `observability.md`.
- **Deployment-level operator concerns (per-tenant DR posture, regional placement)**: `data-residency.md` + `disaster-recovery.md` + `groundx-on-prem`.
