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
| What it holds | Source bytes (uploaded documents), intermediate pipeline artifacts, X-Ray files. (Model weights are **not** held here — they are `wget`'d from the hardcoded `upload.groundx.ai` host into a model-cache PVC created **once per inference service** — `layout-model`, `ranker-model`, `summary-model` — and **mounted by every replica** of that Deployment. The volume outlives any single pod, so a failed download's false `complete.<version>` marker poisons the whole service and is **not** cleared by restarting a pod; see `install-flow.md § 9` and `references/air-gapped.md § 6.5`.) |
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

**Inference model-cache PVCs and node loss.** The per-inference model-cache PVCs (`layout-model`, `ranker-model`, `summary-model`) are created once per inference service and mounted by every replica. On the default `cluster.pvAccessMode: ReadWriteMany` path (EFS, the `setup-eks`-recommended default) the shared filesystem has no single-attachment stranding, and this caveat does not apply, except that on any access mode a pod lost mid-download can leave a `downloading` lock that keeps every new pod waiting in Init; on `ReadWriteMany`, clear it in place rather than replacing the claim, with the `ReadWriteMany` recovery below. The stranding caveat applies when `pvAccessMode` is `ReadWriteOnce` (EBS block storage). On that path an RWO claim can be mounted from only one node, so keep each inference service on one node (for example 1 replica with its HPA off; `summary.inference` defaults to 2 replicas) or use `ReadWriteMany` for replicas on more than one node. On ungraceful node loss a single-replica RWO volume can be stranded (it cannot detach cleanly) or corrupted (a force-detach mid-write can leave the ext4 filesystem inconsistent). Treat these caches as **disposable**: they hold re-downloadable model weights, not authoritative state. Recovery, after confirming the old node is actually gone (terminated or fenced, not merely `NotReady`, so it can no longer write): taint the node `node.kubernetes.io/out-of-service=nodeshutdown:NoExecute` (the `NoExecute` effect is required; the bare key does nothing), which force-deletes the pod and detaches the volume. Then replace the cache rather than reuse it (a reused cache can be corrupt, carry a stale `complete.<version>` marker, or carry a `downloading` lock that keeps every new pod waiting in Init), with the `ReadWriteOnce` recovery below. That node-down confirmation is **mandatory** for stateful backing-service volumes; see `cluster-requirements.md` § 5. See GX-43 for the related rollout-deadlock / zone-locked-EBS exposure, and `cluster-requirements.md` § 5 for the same caveat on stateful backing-service PVCs.

**Model-cache recovery.** `cluster-requirements.md` § 5 and `references/air-gapped.md` § 6.5 give the same order. Every path starts by scaling the inference Deployment (`layout-inference`, `ranker-inference` or `summary-inference` by default) to 0, which keeps replacement pods away: Kubernetes stops an HPA from acting on a Deployment scaled to 0. A `helm upgrade`, or a `terraform apply` that upgrades the GroundX release, renders the replica count again, so run neither until cleanup is done.

- **`ReadWriteMany`: clear the lock in place.** After scaling to 0, run `kubectl get pods -n <namespace> -l app=<inference-service>` until it returns no pods; the scale command returns before the pods stop. A pod left `Terminating` on a terminated or fenced node is cleared by the `out-of-service` taint above, or by force-deleting only that pod. Then, and only after that wait succeeds, start a short-lived pod that mounts the claim, and from it delete `complete.<version>`, any partial `*.tar.gz.part.*` files and the `downloading` lock, which sit at the root of the volume. On an air-gapped cluster the same short-lived pod also re-seeds the volume (`references/air-gapped.md` § 6.5). Then delete the short-lived pod before you restore the replicas (scale back to the previous count, or re-run your `helm upgrade`).
- **`ReadWriteOnce`: replace the claim.** After scaling to 0, wait until no pod using the claim remains, with the same `kubectl get pods` check and `Terminating`-pod handling as the `ReadWriteMany` step above: while such a pod exists, even one left `Terminating` on the lost node, the claim is in use and its deletion does not finish. Only after that wait succeeds, delete the PVC, then wait until the deleted claim is gone, then re-run your `helm upgrade` with your original values. A claim that `kubectl get pvc` still lists, including one in `Terminating`, is not gone. The claim is a separate chart resource that the Deployment only mounts, so nothing recreates it on its own: the `helm upgrade` recreates the claim and restores the replicas, and `download-model` repopulates it as the pod starts. On an air-gapped cluster the recreated claim comes back empty and the init container still exits 0, so scale the Deployment back to 0 and re-seed it with the `ReadWriteMany` order above, from its first step.
- **Both paths: check the model works.** The init container's exit 0 and the `complete.<version>` marker do not prove the model is complete, because a failed download still writes the marker. Check the recovered service with its own test. For `summary-inference`, ingest a PDF with text per `install-flow.md` § 7.4 steps 1-3, then fetch that document's X-Ray (`GET /v1/ingest/document/xray/{documentId}`, or the document's `xrayUrl`; for the call shape, route to `groundx-api/`) and confirm its `fileSummary` is present and is not the literal `None`: an ingest status of complete and an empty `statusMessage` do not reveal summary failures. For `layout-inference`, the ingest completing (not `error`) is the check. For `ranker-inference`, the § 7.4 search must return the test document. Whichever check applies, if it fails, delete `complete.<version>` before retrying, using the `ReadWriteMany` order above so no pod using the claim can start while you do.

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

#### RDS and RDS Proxy

These facts hold for GroundX 0.2.7: the chart and the GroundX service code at the 0.2.7 tag, which includes the RDS Proxy connection fix.

**When to use RDS Proxy.** Put RDS Proxy in front of RDS when many GroundX pods or workers reach the database, or when queue traffic is bursty. For chart-managed Percona or any other MySQL that is not RDS, RDS Proxy does not apply, and the pool facts below still do.

**Endpoints.** Set both `db.existing.ro` and `db.existing.rw` to the proxy's own DNS name, using the proxy's default endpoint (read/write) for both. With TLS on, GroundX checks the proxy's certificate against the hostname it is given, so use the proxy's DNS name itself, not a CNAME alias. With only one of the two set, the chart ignores both and points every service at the in-cluster Percona hostnames. A proxy whose target is a single RDS instance has no working read-only endpoint. Optional: an Aurora cluster or a Multi-AZ DB cluster with at least one reader can use a proxy read-only endpoint for `db.existing.ro`; readers can lag the writer, so those reads can be slightly stale. A read-only endpoint never goes in `db.existing.rw`. Sources: [RDS Proxy endpoints](https://docs.aws.amazon.com/AmazonRDS/latest/UserGuide/rds-proxy-endpoints.html), [RDS Proxy endpoints for Aurora](https://docs.aws.amazon.com/AmazonRDS/latest/AuroraUserGuide/rds-proxy-endpoints.html), [Replication with Aurora](https://docs.aws.amazon.com/AmazonRDS/latest/AuroraUserGuide/Aurora.Replication.html).

**Authentication.** GroundX logs in with a username and password, so the proxy needs an AWS Secrets Manager secret for the user in `db.username`, and client IAM authentication is not used. Source: [Setting up database credentials for RDS Proxy](https://docs.aws.amazon.com/AmazonRDS/latest/UserGuide/rds-proxy-secrets-arns.html).

**TLS.** Through the proxy, `db.existing.rootCerts` holds the Amazon Trust Services root CAs (all of them in one PEM), not the RDS CA bundle. A direct RDS connection uses the RDS CA bundle (global-bundle.pem). Without `db.existing.rootCerts`, GroundX connects without TLS, and a proxy with Require Transport Layer Security on rejects that client with ERROR 3159. The opt-in workspace services connect without TLS in the 0.2.7 chart, so they fail against a proxy that requires TLS. Sources: [RDS Proxy concepts, TLS/SSL](https://docs.aws.amazon.com/AmazonRDS/latest/UserGuide/rds-proxy.howitworks.html), [Using SSL/TLS with RDS](https://docs.aws.amazon.com/AmazonRDS/latest/UserGuide/UsingWithRDS.SSL.html), [Troubleshooting RDS Proxy](https://docs.aws.amazon.com/AmazonRDS/latest/UserGuide/rds-proxy.troubleshooting.html).

**Setup with a proxy.** Create the GroundX database and the app user on RDS before install, and grant the app user ALL PRIVILEGES on the GroundX database; GroundX creates and alters its own tables as that user. Leave `db.privilegedUsername` and `db.privilegedPassword` empty for an install through a proxy. If the `groundx` pod fails at startup, check the proxy's log group in CloudWatch Logs and that the proxy has a secret for the app user.

**Pools.** Each GroundX Go pod opens a read pool and a write pool. Each pool keeps at most 1 idle connection and closes it after 2 minutes idle, so `db.maxIdle` has no effect. `db.maxOpen` (chart default 10) caps each pool, so one pod can open up to 2 x `db.maxOpen` connections. Every connection lives at most 5 minutes, inside the proxy's fixed 24 hours client connection limit and its 30 minutes default idle client timeout. GroundX interpolates query parameters on the client, so most queries avoid prepared statements, which pin a proxy session; its startup migration briefly pins one connection (GET_LOCK, SET SESSION). Sources: [RDS Proxy connection settings](https://docs.aws.amazon.com/AmazonRDS/latest/UserGuide/rds-proxy-connections.html), [Avoiding pinning](https://docs.aws.amazon.com/AmazonRDS/latest/UserGuide/rds-proxy-pinning.html).

**Sizing.** Under chart defaults, 7 Go services run 1 pod each, so with 2 pools and `db.maxOpen` 10 per pool they can open up to 140 client connections, at most 14 of them idle. With `cluster.hpa` true at the chart-default replica maximums, 152 Go pods can open up to 3,040. Add the schema-migration Job during `helm upgrade` (2 pools), `largeFileDeliver` when enabled (2 pools per replica), and the workspace services when `workspace.enabled` is true (one short connection per operation). Set MaxConnectionsPercent at least 30% above the maximum recent observed use (compare DatabaseConnections with MaxDatabaseConnectionsAllowed), and not below 30 for db.t3.small or 20 for db.t3.medium and larger. The proxy reserves some connections for monitoring and failover, so MaxDatabaseConnectionsAllowed can be lower than the setting implies. Source: [RDS Proxy connection settings](https://docs.aws.amazon.com/AmazonRDS/latest/UserGuide/rds-proxy-connections.html).

**Monitoring.** Watch these RDS Proxy metrics in CloudWatch: `DatabaseConnectionsBorrowLatency` (microseconds the proxy takes to get a database connection), `DatabaseConnections`, `MaxDatabaseConnectionsAllowed`, `DatabaseConnectionsCurrentlySessionPinned`, and `AvailabilityPercentage`. Source: [Monitoring RDS Proxy metrics](https://docs.aws.amazon.com/AmazonRDS/latest/UserGuide/rds-proxy.monitoring.html).

**Error 9501.** When the proxy cannot get a database connection within `ConnectionBorrowTimeout` (default 120 seconds), GroundX services log `Error 9501 (HY000): Timed-out waiting to acquire database connection`. AWS gives two causes: the proxy has reached its maximum connections, or the database is unavailable. No CloudWatch metric for RDS Proxy counts these timeouts, so find them in the service logs. Sources: [RDS Proxy connection settings](https://docs.aws.amazon.com/AmazonRDS/latest/UserGuide/rds-proxy-connections.html), [Troubleshooting RDS Proxy](https://docs.aws.amazon.com/AmazonRDS/latest/UserGuide/rds-proxy.troubleshooting.html).

On that error, check target health first (the `TargetHealth` field from `aws rds describe-db-proxy-targets --db-proxy-name <proxy-name>`), then pinning, then connection limits, before scaling RDS. Only some summary lookups requeue on this error; other paths can still fail the document.

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
| Mode 2: operator-deployed | Separate `opensearch/opensearch` Helm release with no operator; the chart only consumes its service |
| Mode 3 — cloud-managed | Set `search.existing.url` to point at AWS OpenSearch managed |
| Default operator | None |
| Credentials | `search.password` and `search.privilegedPassword` are required from the first chart release after 0.2.7 whenever `mode` is not `ingest`, supplied by values or by `SEARCH_PASSWORD` / `SEARCH_INIT_PASSWORD` in the cluster credentials Secret (the Secret route needs the `groundx` and `process` images that the same chart release deploys by default (both log in to OpenSearch: the API to search, the indexing worker to write the index); if you override either with `groundx.image` or `process.image`, override both with images built from that chart release or later, and for a tag that is not a version number (such as `chainguard` or a mirrored tag) confirm with the image provider that both images read `SEARCH_PASSWORD` / `SEARCH_INIT_PASSWORD`, or set `search.password` and `search.privilegedPassword` in values instead); there is no chart default from that release, and published 0.2.7 and earlier still ship the public default, so set both in values there (the Secret route does not apply on those versions). For chart-deployed OpenSearch, `search.privilegedPassword` (or `SEARCH_INIT_PASSWORD`) must equal the OpenSearch admin password (`values-authoring.md` section 3.5.4). |
| Architecture depth | `groundx-architecture/references/store.md`, `groundx-architecture/references/hybrid-search.md` |

Both keyword and vector indices live in OpenSearch — no separate vector database. See `groundx-architecture/references/hybrid-search.md` for the index shape.

In Mode 2, OpenSearch is a separate `opensearch/opensearch` Helm release (community chart 2.23.1) with no operator, no OperatorHub step and no CRDs; the GroundX chart only consumes its service. The bundled Terraform names the release `opensearch-operator` by default (the search service name plus `-operator`). That name does not mean an operator is installed.

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

For a Red Hat OpenShift deployment, the OpenShift AI quickstart path defaults to Mode 2 across the board — see `references/openshift.md`.

## 5. Version floors

The chart does **not** enforce version floors on the existing-customer-managed (Mode 1) endpoints. The deployer is responsible for ensuring their in-house services run a version compatible with the GroundX pipeline (modern MySQL 8.x, recent Redis, OpenSearch 2.x, Kafka 3.x at minimum based on the Mode 2 defaults).

For the operator-deployed Mode 2 path, the chart pulls in the operator's own defaults — the operator vendors specify their supported versions.

**Engine-version lifecycle, not just the floor.** A version floor is a minimum, not a safe default. A managed engine version (RDS / ElastiCache / OpenSearch) also carries a standard-support end date that is independent of whether the version still accepts new instances: a version can resolve as `available` for new instances yet already sit past standard support, at which point the provider adds an extended-support surcharge (for RDS, billed per-vCPU-hour) that can exceed the instance cost itself. Check the end date before pinning a version:

- **RDS:** `aws rds describe-db-major-engine-versions` — its `SupportedEngineLifecycles[]` carry `LifecycleSupportName` (standard vs extended) and `LifecycleSupportEndDate`. (The plain instance-availability listing carries no support-end field, so it cannot be the end-date source.)
- **ElastiCache / OpenSearch:** these expose no end-date field through their engine-version APIs — use the provider's published version-lifecycle calendar / console.

Carry the check commands, not specific dates. See `cost-estimation.md` § 7.3 for the cost framing.

**Parking a managed store has a per-service lifecycle, not a single pause.** RDS can be stopped to pause compute but **auto-restarts after 7 days**, so the saving is temporary; ElastiCache and OpenSearch Service have **no stop operation**, so a provisioned cluster keeps billing until deleted (delete-and-restore from backup is the only real park for those two). Plan the per-service lifecycle before relying on parking a store to save cost. See `cost-estimation.md` § 7.2-7.3 for the cost framing.

## 6. Operator-specific subsystems

When in Mode 2, the chart depends on several operators that ship separately:

| Operator | Service | Notes |
| --- | --- | --- |
| **Strimzi** | Kafka | The chart's queue when `stream.enabled=true`. |
| **Percona Operator for MySQL** | Process metadata DB | The chart's MySQL when `db.enabled=true`. |
| **MinIO operator** | Object store | The chart's file storage when `file.enabled=true`. |
| **NVIDIA GPU Operator** | GPU scheduling | Not a backing service per se — needed for `layout-inference`, `ranker-inference`, `summary-inference` to acquire GPUs. See `references/cluster-requirements.md` § 2.4 + `references/gpu-operator.md`. |

OpenSearch is not in this table: in Mode 2 it is a plain Helm release with no operator (§ 3.4).

For the per-operator install workflow and ordering (operators first, then GroundX), route to `references/install-flow.md`.

## 7. What this file does not cover

- **What each store actually holds (X-Ray, JSONL, intermediate vs persistent, audit log)** → `groundx-architecture/references/store.md`.
- **Customer-isolation enforcement at the store layer** → `groundx-architecture/references/multi-tenancy.md`.
- **Hybrid-search index shape inside OpenSearch** → `groundx-architecture/references/hybrid-search.md`.
- **Field-by-field `values.yaml` reference for the `file` / `db` / `cache` / `search` / `stream` blocks** → `references/values-yaml.md`.
- **Install workflow ordering** → `references/install-flow.md`.
- **NVIDIA GPU Operator setup** → `references/gpu-operator.md`.
- **OpenShift AI quickstart** → `references/openshift.md`.
- **Air-gapped deployment changes** → `references/air-gapped.md`.
- **Disaster recovery and cross-region failover** → `groundx-architecture/references/disaster-recovery.md` + `references/dr-cross-region-runbook.md`.
- **Cost estimation across the three modes** → `references/cost-estimation.md`.
