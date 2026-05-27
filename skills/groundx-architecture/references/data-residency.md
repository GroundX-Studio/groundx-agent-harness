# Data Residency

GroundX has two residency postures: the **hosted cloud service** (today: single-region in **us-west-2** for production, multi-AZ; dev in us-east-1; no cross-region replication; no customer-selectable region) and **on-prem deployments** (whatever region the deployer points `values.yaml` at). Customer-data deletion is supported through three endpoints (per document, per bucket, per customer); deletes run **asynchronously** (typically complete within seconds) and cascade across every store **except audit logs and Redis cache entries**. Compliance posture today: **SOC2 Type 1 + HIPAA**; SOC2 Type 2 in progress. Audit logs are retained **1 year** in the cloud service per SOC2 requirements; on-prem deployments choose their own retention. Customers needing region choice, cross-region replication, or compliance attestations beyond these select on-prem.

## 1. Marketing altitude

Not the canonical place — compliance and residency claims for marketing surfaces are owned by `master-brand-gtm` / `product-brand-gtm`. The architectural facts those claims rest on live here.

## 2. Product altitude

GroundX customers have two paths for data residency:

- **Cloud service** — all customer data lives in the GroundX-hosted cluster in **us-west-2** (production), spread across multiple Availability Zones for durability. No customer-selectable region. No cross-region replication today.
- **On-prem deployment** — the customer (or their deployer) chooses the region by configuring the Helm chart's backing-service endpoints. Any region with the customer's chosen object store / managed DB / managed OpenSearch is supported.

For compliance, the cloud service is **SOC2 Type 1 + HIPAA** today; **SOC2 Type 2 is in progress**. Customers needing FedRAMP, IL6, GDPR-attested deployments, or any other certification not on this list deploy on-prem and attest at the deployment level.

Customer data deletion is supported through the API at three granularities — per document, per bucket, per customer. Deletes run as asynchronous background tasks (similar shape to an ingest request, but typically complete in seconds rather than minutes) and propagate across the production stores.

## 3. Conceptual / algorithmic altitude

Three architectural ideas shape residency:

**Region is a deployment-level property, not a per-customer property.** A single GroundX deployment runs in exactly one region; all customers provisioned into that deployment have their data in that region. There is no per-customer region selection inside a deployment, no automatic data routing by customer geography, and no cross-region replication today. Customer residency = deployment residency.

**Compliance is per-deployment.** The cloud service's SOC2 Type 1 + HIPAA posture applies to the GroundX-hosted us-west-2 production deployment. On-prem deployments inherit whatever compliance posture their deployer can attest — GroundX provides the architecture; the deployer provides the compliance certification.

**Customer-data deletion is asynchronous (seconds-scale) and cascades across most stores.** The API deletion endpoints accept the request and dispatch the underlying store deletes as a background task — similar in shape to an ingest request, but typically completing in seconds rather than minutes. Source files, intermediate artifacts, X-Rays, OpenSearch chunks, and MySQL/RDS rows are all removed. Audit logs and Redis cache entries are not removed by these deletes (Redis entries expire naturally). After deletion completes, the only retained record of the customer's existence is the `groundx` audit log — retained per the cloud-service SOC2 contract (1 year today), or per the on-prem operator's chosen policy.

## 4. System altitude

```
Cloud service:
  Region        us-west-2 (production)
                us-east-1 (dev / staging)
  Availability  Multi-AZ within region (all 6 us-west-2 AZs typical)
  Replication   None across regions
  Customer pick None — every cloud customer lands in us-west-2 prod

On-prem deployment:
  Region        Whatever the deployer's values.yaml points at — region is baked into:
                  - file storage endpoint URL (e.g., s3.us-west-2.amazonaws.com)
                  - process metadata DB endpoint (e.g., RDS instance in us-east-2)
                  - retrieval DB endpoint (e.g., OpenSearch in us-east-2)
                  - stream / queue endpoints (e.g., SQS queue URLs in us-east-2)
  Availability  Whatever the chosen backings provide
  Replication   Whatever the chosen backings provide

Customer deletion (synchronous across stores):
  DELETE /v1/ingest/document/{documentId}  → document cascade
  DELETE /bucket/{bucketId}                 → bucket cascade (partner API)
  DELETE /customer/{$USERNAME}              → customer cascade (partner API)
```

For the deletion API surfaces see `groundx-api` (`document_delete1`) and the partner API deletion docs (bucket / customer delete). For the underlying stores see `store.md` § 5.

## 5. Implementation altitude

### 5.1 Cloud-service deployment topology

| Aspect | Detail |
| --- | --- |
| Production region | us-west-2 |
| Dev / staging region | us-east-1 |
| Multi-AZ | Yes — production runs across multiple AZs in us-west-2 (typically all 6) |
| Cross-region replication | None today |
| Customer-selectable region | Not exposed today; all cloud customers are in us-west-2 prod |

*Source: scoped internal-review finding, 2026-05-17.*

### 5.2 On-prem regional configuration

On-prem deployments are region-agnostic at the application layer — **nothing in GroundX's app code routes by region**. Region is determined by the endpoint URLs each backing service points at in `values.yaml`:

- File storage URL (e.g., `s3.us-west-2.amazonaws.com/<bucket>`)
- Process metadata DB endpoint (e.g., `<id>.us-east-2.rds.amazonaws.com`)
- Retrieval DB endpoint (e.g., `<id>.us-east-2.es.amazonaws.com`)
- Stream / queue endpoints (e.g., `sqs.us-east-2.amazonaws.com/<queue>`)

The deployer points each at the desired region; the cluster runs wherever the Kubernetes nodes live. There is no multi-region operation of a single GroundX deployment.

### 5.3 Compliance posture

| Certification | Status | Scope |
| --- | --- | --- |
| **SOC2 Type 1** | Held | GroundX cloud-service production |
| **HIPAA** | Held | GroundX cloud-service production |
| **SOC2 Type 2** | In progress | GroundX cloud-service production |
| FedRAMP | Not held | — |
| GDPR attestation | Not held; cloud service delete-on-request supports the deletion-rights piece of GDPR | — |
| Other certifications (IL6, etc.) | Deployer-attested for on-prem; not held by the cloud service | On-prem only |

*Source: scoped internal-review finding, 2026-05-17. Verify with the cloud-service compliance owner before external use.*

Customers needing certifications not on this list select on-prem and attest at the deployment level. Air-gapped / FedRAMP-aligned on-prem deployments are supported architecturally (per `overview.md` § 4.4) but the certification is the deployer's, not GroundX's.

### 5.4 Customer-data deletion: endpoints and cascade behavior

| Endpoint | Scope | What it removes |
| --- | --- | --- |
| `DELETE /v1/ingest/document/{documentId}` | One document | The document's source file in file storage, its X-Ray, its OpenSearch chunks, and its MySQL/RDS row(s) |
| `DELETE /bucket/{bucketId}` (partner API) | One bucket + all documents in it | The bucket record, all documents in the bucket, all per-document file-storage artifacts, all per-document OpenSearch chunks, all per-document MySQL/RDS rows |
| `DELETE /customer/{$USERNAME}` (partner API) | One customer + all owned resources | The customer record, all owned projects, groups, buckets, documents, and all the per-document store artifacts above |

**What deletes do NOT remove:**

- **Audit log entries** — the `groundx` raw audit log (per `identity-and-trust.md` § 6.1) is preserved across deletes. This is the only system-of-record that a deleted customer existed.
- **Redis cache entries** — not deleted by the cascade. Redis entries have natural TTL expiration; they age out without explicit cleanup.

Deletion is **asynchronous** — the API call accepts the request, dispatches a background deletion task, and returns; the cascade runs across the stores out-of-band. The shape is the same as an ingest request, but typical wall-clock time is seconds rather than minutes. Callers that need to confirm deletion has completed should poll the relevant resource (document / bucket / customer) until it returns not-found.

*Source: scoped internal-review finding, 2026-05-17, on cascade behavior + async timing. Endpoint paths source from `groundx-api` § documents and partner API customer/bucket endpoints.*

### 5.5 Cascading cleanup invariants

The cascade follows ownership: deleting a higher-level entity removes the lower-level entities it owns. Customer delete → all owned projects, groups, buckets, documents → their store artifacts. Bucket delete → all documents in it → their store artifacts. Document delete → that document's store artifacts.

The audit-log retention is the only intentional residual; everything else is removed.

## 6. Security / compliance altitude

### 6.1 Compliance-cert alignment

The cloud service's SOC2 Type 1 + HIPAA posture is what authorizes regulated-vertical use (per `master-brand-gtm/references/verticals.md` — Healthcare on HIPAA, regulated environments on SOC2). The architecture supports more (FedRAMP / IL6 / GDPR-explicit) via on-prem; certifications at that altitude are deployer-attested.

### 6.2 Deletion-rights mechanics

Customer-deletion endpoints exist and run as **asynchronous background tasks** that complete in seconds — this is the architectural primitive that supports GDPR-style right-to-be-forgotten requests. Audit logs are retained per the deployment's log-retention policy; everything else is removed by the cascade.

**Audit-log retention:**

- **Cloud service:** 1-year retention per the SOC2 contract. After 1 year, audit log entries are removed.
- **On-prem:** the deployer chooses the retention policy; the architecture imposes nothing.

Customers needing a guarantee that audit logs are also purged immediately on delete would need a deployment-level operational contract beyond the standard cascade.

*Source: scoped internal-review finding, 2026-05-17.*

### 6.3 Trust boundary

The cloud-service trust boundary is the us-west-2 GroundX-owned VPC. Data in transit from the customer enters at the API ingress; data at rest lives across the three stores (per `store.md` § 5). External trust-boundary crossings — 3rd-party LLM for summary (configurable), Google Cloud Vision for OCR (configurable per `gcv.json`) — are documented in `identity-and-trust.md` § 6.2.

## 7. Operations / SRE altitude

Customer-data deletion runs as a background task that typically completes in seconds — it is asynchronous from the API caller's perspective but fast enough that it's effectively interactive. The cascade fans out across the production stores (file storage, OpenSearch, MySQL/RDS) out-of-band; callers can poll the resource to confirm not-found if confirmation is needed. Audit-log retention policy and customer-data-residency operational contracts are deployment-specific; the cloud service's specifics live with the SRE / compliance team. For the broader observability framing see `observability.md`. For the broader DR posture see `disaster-recovery.md`.

## 8. Data architecture altitude

**Cloud-service residency by store:**

- File storage (S3) — us-west-2 prod; multi-AZ (S3 native).
- Process metadata DB (RDS) — us-west-2 prod; multi-AZ.
- Retrieval DB (OpenSearch) — us-west-2 prod; multi-AZ.
- No cross-region replication of any store today.

**On-prem residency by store:** the deployer's choice via `values.yaml` endpoint URLs. Each store can be in a different region in principle, though typical deployments co-locate all three for latency.

**Deletion-residue:** per § 5.4, audit logs are preserved; Redis cache entries age out naturally; everything else is removed on delete.

## 9. Cost / FinOps altitude

Cross-region replication would roughly double the per-store cost (each region needs its own provisioned capacity); the architecture supports it but the cloud service doesn't do it today. Multi-AZ within us-west-2 is included in the managed-AWS-service cost of the chosen backings — not a separate line item.

Deployment-level cost framing is owned by `groundx-on-prem`.

## 10. What this topic does not cover

- **The auth surfaces and trust-boundary inventory**: `identity-and-trust.md`.
- **The customer-isolation enforcement** that backs deletion-rights (only deleting the right customer's data): `multi-tenancy.md`.
- **The store backings each store-tier can use**: `store.md`.
- **The deletion-endpoint payloads and exact request/response shapes**: `groundx-api` (customer / document) and partner API docs (bucket / customer).
- **DR posture, backup strategy, RPO/RTO**: `disaster-recovery.md`.
- **The audit-log storage, retention, and query surface**: `observability.md`.
- **Per-deployment cost numbers for cloud-service replication**: `groundx-on-prem`.
- **The deployer-attested certifications for on-prem deployments**: deployer-specific; out of scope at the architecture-skill altitude.
