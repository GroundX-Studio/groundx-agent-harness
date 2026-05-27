# Backing Services Prerequisites

This file documents **the five surrounding services GroundX depends on** — object store, relational DB, cache, retrieval DB, queue — the three deployment modes each can run in, and the decision logic a deployer uses to pick a mode per service.

For what each store *holds* (X-Ray vs JSONL, intermediate vs persistent artifacts, process metadata, queueing state, audit log), route to `groundx-architecture/references/store.md`. For customer-isolation enforcement on these stores, route to `groundx-architecture/references/multi-tenancy.md`.

## 1. The five backing services

GroundX needs four backing services for any deployment, plus a fifth (retrieval DB) for any deployment that serves search / RAG. An **ingest-only** deployment (`mode: ingest`) skips the retrieval DB.

| Backing | Purpose | Always required? |
| --- | --- | --- |
| **File Storage** | Source bytes, intermediate artifacts, X-Ray files | Yes |
| **Process Metadata DB** | Process metadata, auth state, queueing state | Yes |
| **Cache** | Hot process state, frequently-accessed API queries, metrics | Yes |
| **Queue** | Inter-pod handoff for the ingest pipeline | Yes |
| **Retrieval DB** | JSONL chunks, keyword index, vector index | Only when serving search / RAG. **Not required** when `mode: ingest`. |

For the canonical "which artifact lands where" map, route to `groundx-architecture/references/store.md`. For deployment-mode mechanics (`mode: ingest` vs the full platform), route to `references/deployment-modes.md`.

## 2. The three deployment modes

Each backing service can run in one of three modes, selected through `values.yaml`:

| Mode | Pattern | When it makes sense |
| --- | --- | --- |
| **1. Existing customer-managed** | Deployer points the chart at an existing in-house service (their own MySQL, Redis, OpenSearch, Kafka, S3-compatible store) | Customer already operates the technology at production grade. Cost optimization. Compliance / governance preference for centrally-managed infra. |
| **2. Operator-deployed dedicated** | Chart installs an operator (or the chart itself provisions the service) per-deployment | Default and simplest path. No external dependency. Fully isolated per deployment. Best for greenfield deployments without existing infra. |
| **3. Cloud-managed equivalent** | Deployer points the chart at the cloud provider's managed service (AWS RDS, ElastiCache, OpenSearch managed, SQS, S3; Azure equivalents) | Cloud-native operational model. Managed backups, scaling, SLAs. Per-instance HA without operator complexity. |

The three modes are not mutually exclusive *across services*. A deployer can run file storage in S3 (Mode 3), the relational DB in operator-deployed Percona (Mode 2), and the cache against their existing in-house Redis (Mode 1) — every service is independently configured.

## 3. Per-service: field paths, modes, operators

### 3.1 File Storage

| Aspect | Value |
| --- | --- |
| What it holds | Source bytes (uploaded documents), intermediate pipeline artifacts, X-Ray files, model-weight blobs (read-only cache) |
| Mode 1 — existing | `file.bucketName` + `file.existing.url` → in-house S3-compatible endpoint with credentials |
| Mode 2 — operator-deployed | Chart deploys MinIO (with `file.username` + `file.password`) |
| Mode 3 — cloud-managed (AWS S3) | `file.bucketName` + `file.existing.url` (e.g. `https://<bucket>.s3.<region>.amazonaws.com`) + `file.existing.region` + `file.existing.serviceType: s3`. IAM creds via top-level `file.username` / `file.password` (the schema's `file.existing` block carries only `port`, `region`, `serviceType`, `url`; credentials live one level up), or via IRSA on the ServiceAccount. |
| Default operator | MinIO operator |
| Architecture depth | `groundx-architecture/references/store.md` |

The same `file.existing.*` shape covers both Mode 1 (an in-house S3-compatible object store) and Mode 3 (AWS S3 / S3-compatible managed). The distinguishing fact is whether the endpoint is in-house or cloud-managed.

For contributor/internal verification only, upstream customer-specific sample values files show the canonical AWS-S3 block shape. Do not surface those file names in user-facing output unless the user explicitly asks about upstream source files. The block shape is:

```yaml
file:
  bucketName: <bucket-name>
  existing:
    url: https://<bucket-name>.s3.<region>.amazonaws.com
    region: <region>
    serviceType: s3
```

The chart does not invent a bucket layout — multi-tenancy on the object store is owner-username-tagged at the key prefix level. See `groundx-architecture/references/multi-tenancy.md`.

### 3.2 Process Metadata DB

| Aspect | Value |
| --- | --- |
| What it holds | Process metadata, auth state, queueing state, audit log |
| Mode 1 — existing | `db.existing.ro` / `db.existing.rw` / `db.existing.port` → in-house MySQL endpoints |
| Mode 2 — operator-deployed | Chart deploys **Percona Distribution for MySQL** via the Percona operator |
| Mode 3 — cloud-managed | Set `db.existing.*` to point at AWS RDS / Azure Database for MySQL |
| Default operator | Percona Operator for MySQL |
| Architecture depth | `groundx-architecture/references/store.md` |

The chart distinguishes read-only (`ro`) and read-write (`rw`) endpoints, which lets a deployer point reads at a replica and writes at the primary even in Mode 1.

Sample resource sizing for the operator-deployed Percona deployment is ~**600m CPU / 1 GiB memory** per pod at baseline; production load needs more. The deployer tunes this via the Percona operator's own CRDs.

### 3.3 Cache

| Aspect | Value |
| --- | --- |
| What it holds | Hot process state, frequently-accessed API query results, metric scratch |
| Mode 1 — existing | `cache.existing.addr` → in-house Redis endpoint |
| Mode 2 — operator-deployed | Chart deploys Redis (operator-managed) |
| Mode 3 — cloud-managed | Set `cache.existing.addr` to point at AWS ElastiCache (Redis) or Azure Cache for Redis |
| Default operator | Redis operator (chart-managed) |
| Architecture depth | `groundx-architecture/references/store.md` |

Redis is treated as ephemeral state — durability is not assumed. Authoritative state lives in the relational DB.

### 3.4 Retrieval DB

| Aspect | Value |
| --- | --- |
| What it holds | JSONL chunks (post-extraction document chunks), keyword index, vector index |
| When required | Any deployment that serves search / RAG. **Skipped entirely when `mode: ingest`** — the retrieval DB does not need to be present or wired. |
| Mode 1 — existing | `search.existing.url` → in-house OpenSearch endpoint |
| Mode 2 — operator-deployed | Chart deploys OpenSearch via the OpenSearch operator |
| Mode 3 — cloud-managed | Set `search.existing.url` to point at AWS OpenSearch managed |
| Default operator | OpenSearch operator |
| Architecture depth | `groundx-architecture/references/store.md`, `groundx-architecture/references/hybrid-search.md` |

Both keyword and vector indices live in OpenSearch — no separate vector database. See `groundx-architecture/references/hybrid-search.md` for the index shape.

### 3.5 Queue

| Aspect | Value |
| --- | --- |
| What it holds | Inter-pod handoff messages for the ingest pipeline (groundx → upload → queue → pre-process → process) |
| Mode 1 — existing | `stream.existing.domain` / `stream.existing.port` → in-house Kafka endpoint |
| Mode 2 — operator-deployed | Chart deploys Kafka via **Strimzi** |
| Mode 3 — cloud-managed | per-topic `stream.topics.<topic-name>.type: sqs` → AWS SQS (or other cloud-managed queue) |
| Default operator | Strimzi |
| Architecture depth | `groundx-architecture/references/data-flow.md`, `groundx-architecture/references/store.md` |

SQS substitution is supported but changes operational semantics (ordering, batching, visibility timeouts). The chart's pipeline microservices abstract the queue interface so the application code does not need different paths.

## 4. Decision logic — which mode to pick

The decision is per-service. For each backing service, walk the deployer through:

1. **Is there an existing in-house deployment of this technology at production grade?**
   - Yes → strong candidate for Mode 1 (existing customer-managed). Pros: cost optimization, existing operational expertise, central governance. Cons: cross-team coordination, blast radius if shared.
2. **If not, is this a cloud deployment with the cloud's managed equivalent already in scope?**
   - Yes → strong candidate for Mode 3 (cloud-managed). Pros: managed backups / scaling / patching, cloud-native HA, integrated IAM. Cons: cloud lock-in, per-service cost, network egress when calling from the cluster.
3. **Otherwise** → Mode 2 (operator-deployed dedicated). Pros: simplest greenfield path, no external dependency, fully isolated per deployment, air-gap-compatible. Cons: deployer is on the hook for backups / scaling / patching of each operator-managed service.

For an air-gapped deployment, **Mode 2 is the default for every service** unless the deployer has air-gap-internal infrastructure they want to point at.

For a Red Hat OpenShift deployment, the OpenShift AI quickstart path defaults to Mode 2 across the board — see `references/openshift.md` (planned).

## 5. Version floors

The chart does **not** enforce version floors on the existing-customer-managed (Mode 1) endpoints. The deployer is responsible for ensuring their in-house services run a version compatible with the GroundX pipeline (modern MySQL 8.x, recent Redis, OpenSearch 2.x, Kafka 3.x at minimum based on the operator defaults).

For the operator-deployed Mode 2 path, the chart pulls in the operator's own defaults — the operator vendors specify their supported versions.

## 6. Operator-specific subsystems

When in Mode 2, the chart depends on several operators that ship separately:

| Operator | Service | Notes |
| --- | --- | --- |
| **Strimzi** | Kafka | The chart's queue when `stream.enabled=true`. |
| **Percona Operator for MySQL** | Process metadata DB | The chart's MySQL when `db.enabled=true`. |
| **MinIO operator** | Object store | The chart's file storage when `file.enabled=true`. |
| **OpenSearch operator** | Retrieval DB | The chart's search when `search.enabled=true`. |
| **NVIDIA GPU Operator** | GPU scheduling | Not a backing service per se — needed for `layout-inference`, `ranker-inference`, `summary-inference` to acquire GPUs. See `references/cluster-requirements.md` § 2.4 + `references/gpu-operator.md` (planned). |

For the per-operator install workflow and ordering (operators first, then GroundX), route to `references/install-flow.md`.

## 7. What this file does not cover

- **What each store actually holds (X-Ray, JSONL, intermediate vs persistent, audit log)** → `groundx-architecture/references/store.md`.
- **Customer-isolation enforcement at the store layer** → `groundx-architecture/references/multi-tenancy.md`.
- **Hybrid-search index shape inside OpenSearch** → `groundx-architecture/references/hybrid-search.md`.
- **Field-by-field `values.yaml` reference for the `file` / `db` / `cache` / `search` / `stream` blocks** → `references/values-yaml.md` (planned).
- **Install workflow ordering** → `references/install-flow.md` (planned).
- **NVIDIA GPU Operator setup** → `references/gpu-operator.md` (planned).
- **OpenShift AI quickstart** → `references/openshift.md` (planned).
- **Air-gapped deployment changes** → `references/air-gapped.md` (planned).
- **Disaster recovery and cross-region failover** → `groundx-architecture/references/disaster-recovery.md` + `references/dr-cross-region-runbook.md` (planned).
- **Cost estimation across the three modes** → `references/cost-estimation.md` (planned).
