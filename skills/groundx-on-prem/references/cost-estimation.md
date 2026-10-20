# Cost Estimation

This file documents **what drives the cost of running GroundX on-prem and how to derive a per-deployment estimate** — the cost-relevant chart knobs, where cost concentrates across the five `eyelevel-*` node groups, and the manual sizing pattern (values.yaml plus an external pricing source).

GroundX is a **cloud-agnostic Helm chart**. There is no canonical cost-estimation tool inside the chart itself; cost modelling is a deployer responsibility done against the cluster's underlying compute and storage pricing (cloud-provider line items, on-prem capacity costs, etc.). The chart's contribution is exposing per-microservice `replicas` and `resources` in `values.yaml` so the deployer can sum them.

For per-microservice resource defaults and node-group targets, route to `node-groups.md`. For cluster-wide minimums and GPU model classes, route to `cluster-requirements.md`. For the decision between chart-deployed vs cloud-managed backing services (which materially shifts cost), route to `service-substitution.md`. For the architectural cost picture, route to `groundx-architecture/references/data-residency.md` and `groundx-architecture/references/disaster-recovery.md`.

## 1. The manual sizing pattern

The chart's `src/groundx/values.yaml` is the source of truth for per-microservice CPU / memory / replica defaults. To estimate cluster capacity:

1. Render the merged values (chart defaults + your overrides):

   ```sh
   helm template groundx ./src/groundx -f my-overrides.yaml > rendered.yaml
   ```

   When `metrics.enabled: true` (not the chart default), `rendered.yaml` also contains a chart-generated `metrics-tls` private key — redact before sharing, treat the file as secret, and delete it afterwards; see `references/credentials.md`.
2. For each microservice (`groundx`, `layout.*`, `extract.*`, `summary.*`, `ranker.*`, `preProcess`, `process`, `queue`, `upload`, `summaryClient`, `layoutWebhook`, `metrics`, `workspace.*` when enabled), read:
   - `replicas.desired` (and `replicas.max` if `cluster.hpa: true`).
   - `resources.requests.{cpu, memory}` and `resources.limits.{cpu, memory}`.
   - `node` (the target node group label).
3. Sum per node group: `Σ (replicas × resources.requests.{cpu, memory})` for the minimum footprint, `Σ (replicas.max × resources.limits.{cpu, memory})` for max burst at full HPA scale-out.
4. Add backing-service capacity (cache, db, file, search, stream — each chart-deployed via its own operator-managed Helm release, see `services-operators.md`).
5. Add storage (PVCs from chart-deployed backing services, plus the workspace cache PVC if enabled).
6. Pair the per-node-group footprint with the underlying compute pricing (cloud-provider instance pricing, on-prem hardware amortization, etc.).

The chart sets reasonable production-shaped defaults; tune them based on observed load.

> **AWS-only optional helper.** The upstream `groundx-on-prem` repo ships a Terraform-backed convenience tool at `bin/estimate` (with `bin/estimate.py`) that automates steps 1–3 for the AWS EKS deployment path — it renders the chart through `terraform/estimate/` and aggregates the result by node group. This is **optional AWS tooling** that builds on Terraform, not the canonical chart workflow. Deployers on Azure AKS, GKE, OpenShift, on-prem Kubernetes, or any non-AWS Kubernetes cluster do the same sums manually against the rendered values.

## 2. Where cost concentrates

Cost shows up in four buckets that materially differ in scale:

| Bucket | What drives it | Order of magnitude |
| --- | --- | --- |
| **GPU compute** | `layout-inference`, `ranker-inference`, `summary-inference` deployments. Each needs an NVIDIA GPU with specific memory minimums. | Highest. Single biggest line item on most deployments. |
| **CPU compute — orchestration + non-inference pipeline** | API tier, queue, pre-process, process, summary-client, the layout sub-microservices (correct, map, ocr, process, save), workspace runner, extract subsystem. | Medium. Scales with throughput and HPA settings. |
| **Backing services (cache, db, file, search, stream)** | Mode-dependent — chart-deployed in-cluster (operator-managed Helm releases) vs cloud-managed (RDS / S3 / OpenSearch Service / MSK / ElastiCache). | Highly variable. Cloud-managed is usually higher per unit but eliminates ops cost. |
| **Persistent storage** | OpenSearch index, MinIO bucket / S3, MySQL data, optional workspace PVC. | Grows with ingested document volume + retention. |

Network egress (between AZs, to/from cloud-managed services) is a fifth bucket; the chart doesn't drive it directly but trust-boundary-crossing engines (Google Cloud Vision OCR, external LLMs) generate measurable egress. See `ocr-mode.md` § 2 and `engines.md`.

## 3. GPU compute — the single biggest line item

The three inference deployments are the dominant cost driver on a vanilla deployment. Their chart defaults are documented at `cluster-requirements.md` § 2.2:

| Inference deployment | Default GPU memory per pod | Notes |
| --- | --- | --- |
| `summary-inference` | ~24 GB (Gemma 3 at default `1×1` workers/threads) | Disable via `summary.api.enabled: false` + `summary.inference.enabled: false` to drop this entirely and route to an external LLM (OpenAI / Azure / Bedrock). See `engines.md` and `service-substitution.md` § 4.6. |
| `ranker-inference` | ~17.5 GB estimated footprint at `14×1` workers/threads; budget a 24 GB card class | Cannot reasonably be disabled — search ranking is core to RAG quality. CPU fallback is unreliable. |
| `layout-inference` | ~2.5 GB × `worker × thread` (default `1×6` ≈ 15 GB) | CPU fallback is possible via `layout.inference.deviceType: cpu` (chart 0.2.7), which auto-strips the GPU request/limit; retargeting off `eyelevel-gpu-layout` is a separate step. Layout-only: it does not touch `ranker` (an explicit `nvidia.com/gpu` request) or `summary` (no GPU device request; placed on the `eyelevel-gpu-summary` node group). See `values-authoring.md` § 3.11. |

**Host RAM is a second GPU-node cost input, separate from VRAM.** A GPU instance must also clear a host-RAM floor — `eyelevel-gpu-ranker` 30 GB, `eyelevel-gpu-layout` 12 GB, `eyelevel-gpu-summary` 30 GB (the RAM column of the Terraform README "Total Recommended Resources"; this citation is scoped to the RAM/disk columns, not the README's divergent VRAM column). Cost each GPU node on both its VRAM figure above and this host RAM floor, plus its root disk (`cluster-requirements.md` § 6.2) — an instance picked for VRAM alone can still be undersized on host RAM. See `cluster-requirements.md` § 2.3.

The cost levers:

1. **Drop summary-inference entirely** by routing to an external LLM. This is the single biggest GPU-cost reduction available; the `eyelevel-gpu-summary` node group disappears.
2. **Right-size the layout GPU** by tuning `layout.inference.workers` and `layout.inference.threads`. Reducing from `1×6` to `1×3` cuts the GPU memory requirement to ~7.5 GB, opening up smaller (cheaper) cards like the L4 16 GB.
3. **Co-locate workloads via MIG / time-slicing** when GPU memory budget allows — single A100 80 GB can host `layout-inference` + `ranker-inference` + `summary-inference` simultaneously via MIG.

HPA on the inference deployments multiplies the GPU footprint by `replicas.max`. Each replica needs its own GPU (or MIG slice). Plan accordingly.

## 4. CPU compute — the orchestration + pipeline tier

For a vanilla deployment with all features enabled and HPA off, `cluster-requirements.md` § 6 documents the rough envelope: ~8-16 vCPU baseline for the orchestration tier, plus ~4-8 vCPU for the layout pipeline non-inference, plus ~1-2 vCPU each for `ranker-api` and `summary-api`. Total ~15-30 vCPU baseline at idle.

HPA multiplies this. With HPA on, `replicas.max` (often 16-32 for the high-throughput pods like `groundx`, `layout-api`, `process`) governs peak footprint. Compute the max-burst delta by reading `replicas.max × resources.limits` from rendered values; the difference between min and max-burst is the autoscaling headroom the cluster needs.

`workspace` adds ~5-10 vCPU baseline when enabled (6 deployments — see `workspace-service.md`). `extract` adds another ~2-5 vCPU baseline.

## 5. Backing services — chart-deployed vs cloud-managed

The substitution decision (see `service-substitution.md`) materially shifts cost.

### 5.1 Chart-deployed (operator-managed, in-cluster)

Each backing service runs in-cluster via its own Helm release (see `services-operators.md`). Cost is **node-group capacity** the deployer provisions:

| Backing service | Default footprint (rough, chart-deployed) | Node group target |
| --- | --- | --- |
| Cache (Redis StatefulSet) | ~0.2 vCPU / 0.5 GiB requests per pod, 1 replica default | `eyelevel-cpu-only` |
| Cache metrics | ~0.2 vCPU / 0.5 GiB per pod, 1 replica | `eyelevel-cpu-only` |
| MySQL (Percona) | ~0.6 vCPU / 0.5 GiB per pod + HAProxy ~0.6 vCPU / 1 GiB, `pxc.size: 1` default | `eyelevel-cpu-only` |
| Object store (MinIO) | ~0.1 vCPU / 0.25 GiB per pod, 1 server × 20 GiB default | `eyelevel-cpu-only` |
| Search (OpenSearch) | ~0.2 vCPU / 0.5 GiB per pod, 1 replica, single-node default | `eyelevel-cpu-only` |
| Stream (Kafka via Strimzi) | ~0.5-1 vCPU / 1-2 GiB per broker, 1 replica default | `eyelevel-cpu-only` |

Production scaling pushes each materially higher. `pxc.size: 3` (Percona quorum), `tenant.pools[0].servers: 4` (MinIO redundancy), OpenSearch with 3+ replicas, Strimzi with 3+ brokers — each adds ~3-5x the baseline footprint.

### 5.2 Cloud-managed

Backing-service cost shifts off the cluster's node budget onto cloud-provider line items:

| Backing service | Cloud-managed option | Cost driver |
| --- | --- | --- |
| Cache | AWS ElastiCache, GCP Memorystore | Instance size + cluster shards. |
| MySQL | AWS RDS, GCP CloudSQL, Azure Database for MySQL | Instance class + storage + read-replica count. |
| Object store | AWS S3, GCP Cloud Storage, Azure Blob | Storage GB + request count + egress. |
| Search | AWS OpenSearch Service, Aiven OpenSearch | Instance class + storage + replica count. |
| Stream | AWS MSK, Confluent Cloud | Broker instance class + storage + throughput tier. |

The cluster's node budget drops correspondingly. Whether total cost is lower depends on per-deployment specifics (cloud provider, instance class, scale).

### 5.3 Hybrid — most production deployments

Most production deployments end at **selective substitution**: stateful subsystems (db, file, stream, summary-inference) externalized to cloud-managed services for backup / DR / scaling; chart-deployed for lighter-state subsystems (cache, search if small). The chart-deployed half's footprint lives in the rendered values; the cloud-managed half is on the cloud-provider's pricing pages.

## 6. Persistent storage

For chart-deployed backing services, PVCs are provisioned against `cluster.pvClass`. Defaults (from the chart's seed values files under `src/groundx/values/{percona,minio,opensearch}/`):

| Service | Default PVC size | Notes |
| --- | --- | --- |
| MySQL (Percona) | `pxc.persistence.size: 20Gi` | Single-node default. Production scales to 100s of GiB. |
| MinIO tenant | `tenant.pools[0].size: 20Gi`, `volumesPerServer: 1` | Production scales to TiBs. |
| OpenSearch | `persistence.size: 20Gi` | Production scales with index size (function of ingested document count × dimension × replica factor). |
| Cache (Redis) | `persistence.capacity: 10Gi` (when `persistence.enabled: true` — default off) | Cache is normally ephemeral; persistence enabled only when the deployment uses Redis-backed durable state. |
| Workspace cache | `pvc.capacity: 20Gi` (chart-default, always rendered when `workspace.enabled: true`) | The chart always materializes a `{workspace.serviceName}-data` PVC for the secondary file API cache. Override `workspace.pvc.capacity` to size; the chart does not support an `emptyDir` mode. |

Storage costs scale linearly with the ingested document volume in the OpenSearch index and the MinIO bucket. A rule-of-thumb for the OpenSearch index: ~3-5x the source document size, depending on the chunking and embedding dimension.

## 7. Standing and recurring costs

### 7.1 Network egress

Outbound network from the cluster has cost implications for:

| Egress path | When it happens | Approximate cost |
| --- | --- | --- |
| Cross-AZ within a single cloud region | When the cluster spans multiple AZs (typical for HA deployments) | Per-GB charge between AZs. |
| To Google Cloud Vision | When `layout.ocr.type: google` is set | Per-API-call charge plus egress per image bytes. See `ocr-mode.md` § 2. |
| To external LLM endpoints | When `summary.existing.url` routes to OpenAI / Azure / Bedrock, or an enabled extract agent (`extract.agent.apiBaseUrl`) routes to an external model endpoint | Egress per request bytes + the LLM provider's per-token charge. |
| To the configured Git provider API | When `workspace.enabled: true` — the workspace runner reaches its `gitProvider` remote (`github` by default, `api.github.com`; `gitlab.com/api/v4` for `gitlab`, both overridable). See `values-yaml.md` § 7. | Per-request egress to the git provider; avoidable by disabling workspace or using a Git server reachable without external egress. |
| To Google Drive / Sheets | When `extract.save.driveId` + `extract.save.templateId` are set (extraction output written to Google Drive / Sheets). See `values-yaml.md` § 7. | Per-API-call egress; avoidable by leaving `extract.save` unset. |
| To a public image registry | When images are pulled directly from a public registry (`public.ecr.aws`, or `cgr.dev` when `imageType: chainguard`) instead of from a mirror | Per-pull egress; avoidable by mirroring the images into a private registry (private ECR or a pull-through cache). |
| To AWS Cognito | When `cognito.mode: cognito` (Cognito-backed password login) | Per-auth outbound call to `cognito-idp.<region>.amazonaws.com`; not air-gap-valid. See `identity-model.md` § 1. |
| To `upload.groundx.ai` (model weights) | Inference pod first start, unless the model-cache PVC is pre-seeded | One-time weight download per model version; avoidable by pre-seeding the PVC — see `air-gapped.md` § 6.5. |
| To cloud-managed backing services (cross-AZ) | RDS / OpenSearch Service / MSK / S3 in a different AZ than the cluster | Per-GB cross-AZ charge. |

For a fully self-hosted air-gapped deployment, these egress paths do not apply — no external egress is possible. In a cloud-connected shape, NAT/egress is a hard requirement whenever an external engine (e.g. OpenAI) is reached or images are pulled directly from a public registry (`public.ecr.aws`): no VPC endpoint removes the external-engine egress, and a direct public-registry pull needs egress unless the images are first mirrored into a private registry (e.g. a private ECR or a pull-through cache). For high-throughput deployments with external services, egress can become a meaningful line item (10-20% of total cost in some shapes).

**Which configurations are actually offline-capable.** The egress list is not only about engines and images — identity matters too. When `cognito.mode: cognito` is set for password login, the pod makes an outbound call to `cognito-idp.<region>.amazonaws.com` on each auth; that is a mandatory egress path and is not air-gap-valid (per `identity-model.md` § 1). **Full offline operation requires every external egress path in the table above — every row except the cross-AZ data-transfer rows, which are cost-only and do not cross the air gap — to be disabled, pointed at an in-cluster endpoint, mirrored into the cluster, or pre-seeded.** The table above is the list this recipe draws from, so a newly added egress feature is closed off by giving it a row there rather than by maintaining a second enumeration in this sentence. Per-row levers include: a self-hosted `summary.inference` engine with no external `summary.existing` engine (the self-hosted summary path makes no external call); extraction either left disabled (`extract.enabled: false`, the chart default) or, if enabled, with `extract.agent.apiBaseUrl` pointed at an in-cluster endpoint rather than an external provider such as Bedrock and `extract.save` Google Drive / Sheets left unset; an **offline identity mode** (`apiKeyOnly` or `local`, per `identity-model.md` § 1), **not** `cognito`, which is not air-gap-valid; `layout.ocr.type: tesseract`; `workspace` left disabled or its Git provider pointed at an in-cluster remote; and the prepared-in-advance paths handled — `public.ecr.aws` / `cgr.dev` images mirrored into a private registry and the `upload.groundx.ai` model-cache PVC pre-seeded (see `air-gapped.md` § 6.5).

### 7.2 What a parked cluster still costs

Scaling a cluster to zero nodes stops compute spend but not every line. A parked (zero-node) cluster still bills:

- **The EKS control-plane base charge** — AWS bills the control plane per hour regardless of node count.
- **The extended-support surcharge** — when the cluster's upgrade policy is `EXTENDED` and its Kubernetes version has passed standard support, AWS adds a per-cluster hourly extended-support surcharge that applies even at zero nodes. `groundx-on-prem` does not itself set an EKS upgrade policy, so a newly created cluster carries AWS's default of `EXTENDED`; an existing cluster may carry a policy set outside this repo. Read the live policy with `aws eks describe-cluster --name <cluster> --query cluster.upgradePolicy`.
- **CloudWatch control-plane log ingest** — when control-plane logging is enabled, the log streams keep ingesting (and billing) while the cluster is parked. Check which log types are enabled with `aws eks describe-cluster --name <cluster> --query cluster.logging`.
- **Idle NAT gateway + Elastic IP** — a provisioned NAT gateway and its Elastic IP bill hourly whether or not traffic flows.
- **Chart-created PersistentVolumeClaims** — the PVCs the chart provisions for its in-cluster stateful workloads stay allocated and keep billing after the cluster is scaled to zero nodes; the control plane is still up on a parked cluster, so list them with `kubectl get pvc -A`. Whether deleting a PVC stops the charge depends on its storage class (set by the `prereqs/storageclass` variant the deployment installed):
  - **EBS gp3** (`prereqs/storageclass/values.ebs.example.yaml`: `provisioner: ebs.csi.aws.com`, `type: gp3`, `reclaimPolicy: Delete`) — each PVC provisions its own EBS volume, so under the default `Delete` reclaim policy deleting the PVC deletes that volume and its data and stops its charge. Back up any store that must survive the park before deleting its PVC. A `Retain` reclaim policy instead keeps the volume, which then still bills until it is deleted manually.
  - **EFS** (`prereqs/storageclass/values.efs.example.yaml`: `provisioner: efs.csi.aws.com`, `provisioningMode: efs-ap`, a `fileSystemId` of an existing filesystem) — each PVC is an access point on a shared, pre-existing EFS filesystem, not its own volume. The EFS storage charge is on that filesystem, which is operator-provisioned and managed outside the chart, so deleting PVCs does not stop it (and the example's `reclaimPolicy: Retain` keeps the released PV and its access point as well). Manage and verify the filesystem separately, e.g. `aws efs describe-file-systems`.

Budget these before parking a cluster, and decide per line whether to delete the resource (NAT / EIP), disable control-plane logging, or set a `STANDARD` upgrade policy before standard support ends (see below) — rather than assuming a zero-node cluster is free. Each of those carries a tradeoff; decide it deliberately rather than defaulting to the cheapest:

- **Disabling control-plane logging** stops the CloudWatch ingest charge, but it **loses the audit / forensic trail** — the control-plane log streams are the record of API-server, authenticator, and controller activity, so turning them off leaves no evidence to reconstruct what happened during the parked window.
- **The `STANDARD` upgrade policy** avoids the per-cluster extended-support surcharge, but only when it is set **before** the cluster's Kubernetes version reaches end of standard support. Under `STANDARD`, AWS performs an **automatic minor-version upgrade** of the cluster to the next supported version once standard support ends, whether or not that upgrade was planned (the groundx-on-prem chart repository `README.md`, "What happens when standard support ends"). A cluster that has **already entered extended support cannot be switched to `STANDARD`** to stop the surcharge: the only way out is to **upgrade its Kubernetes version** to one still in standard support (AWS EKS [upgrade-policy guidance](https://docs.aws.amazon.com/eks/latest/userguide/view-upgrade-policy.html): "Once your cluster has entered extended support, you cannot disable it. To change the version support policy setting, your cluster must be running on a Kubernetes version in standard support."). So `STANDARD`, chosen in time, trades the surcharge for losing version-pinning control, while `EXTENDED` keeps the version pinned but keeps paying, and leaving extended support later still requires a version upgrade. Pick per the deployment's change-control needs, not purely on cost.

### 7.3 Managed-engine version lifecycle

A managed backing-engine version (RDS / ElastiCache / OpenSearch) carries a standard-support end date that is independent of whether the version still accepts new instances: a version can resolve as `available` for new instances yet already sit past standard support. Once a version passes that standard-support end date, the provider adds an extended-support surcharge (for RDS, billed per-vCPU-hour) that can exceed the instance cost itself, so a "supported-looking" default can quietly bill extended support.

Check the end date before pinning a version:

- **RDS:** `aws rds describe-db-major-engine-versions` — its `SupportedEngineLifecycles[]` carry `LifecycleSupportName` (standard vs extended) and `LifecycleSupportEndDate`. (The plain instance-availability listing carries no support-end field, so it is not the end-date source.)
- **ElastiCache / OpenSearch:** these expose no end-date field through their engine-version APIs — use the provider's published version-lifecycle calendar / console.

Carry the check commands, not specific dates: lifecycle dates move, and a pinned date goes stale. For the prerequisite framing, see `services-prereqs.md` § 5.

**Parking a managed engine is not uniform across services.** Stopping a managed backing engine to pause its compute charge behaves differently per engine, so a single "pause it while idle" assumption is wrong:

- **RDS** can be stopped (`aws rds stop-db-instance`), but AWS **restarts automatically after 7 days** (the instance's `AutomaticRestartTime` shows when), so a stopped RDS resumes billing on its own — it is a temporary pause, not an indefinite park.
- **ElastiCache** and **OpenSearch** Service have **no stop operation** — a provisioned cluster bills continuously until it is deleted (ElastiCache exposes only `batch-stop-update-action`, which pauses service-update application, not the cluster). To stop paying for these, back up and delete, then restore when needed.

So park / stop savings apply to RDS compute only, and only for up to 7 days at a time; for ElastiCache and OpenSearch, delete-and-restore is the only real park. See `services-prereqs.md` § 5.

## 8. Cost-modelling discipline

When estimating cost for a new deployment:

1. **Make the substitution decisions first** (see `service-substitution.md`). The chart-deployed vs cloud-managed split is the biggest single cost driver after GPU choice.
2. **Decide on the summary engine** (see `engines.md`). Self-hosted gemma vs external LLM materially changes the GPU footprint and the per-call LLM cost.
3. **Set HPA expectations.** Will the deployment run at low/medium/high throughput? Set `replicas.max` and `cluster.hpa` accordingly before estimating.
4. **Sum the rendered values.** Reuse the `rendered.yaml` from step 1 (or re-render), walk per-microservice replicas/resources, sum per node group. (AWS deployers may use `bin/estimate` to automate this; non-AWS deployers do it manually or via their own tooling.) When `metrics.enabled: true` (not the chart default), that render contains a chart-generated `metrics-tls` private key — read the resource figures off it, do not paste it into chat, logs, or a PR, and if you save it, treat that file as secret and delete it afterwards.
5. **Add cloud-managed line items** for any externalized backing services. Get per-service pricing from the cloud provider.
6. **Add storage** — sum the chart-deployed PVC defaults (or cloud-managed equivalent), plus the OpenSearch / MinIO scale factor over expected document volume.
7. **Add egress** — only meaningful if external engines or cross-AZ cloud-managed services are in play.
8. **Add ops cost** — chart-deployed backing services need ops attention (upgrades, backups, monitoring); cloud-managed offloads that. Reflect this in TCO, not just compute spend.

Don't skip step 1. Substitution choices propagate through every other estimate.

## 9. What this file does not cover

- **Per-microservice resource defaults** → `node-groups.md`.
- **Cluster-wide minimums and GPU model classes** → `cluster-requirements.md`.
- **Chart-deployed vs cloud-managed decision** → `service-substitution.md`.
- **Operator installation specifics** → `services-operators.md`.
- **Summary engine selection (the biggest single GPU lever)** → `engines.md`.
- **Workspace runner subsystem footprint** → `workspace-service.md`.
- **HPA / autoscaling specifics** → `autoscaling.md`.
- **AWS-specific helpers (e.g., `bin/environment` for VPC/EKS setup, `bin/estimate` for capacity aggregation)** → optional AWS tooling not required by the chart; out of scope here. The chart itself is cloud-agnostic.
- **Cloud-provider pricing math** → out of scope; consult cloud-provider pricing calculators. The chart only models the in-cluster footprint, not the per-instance / per-service pricing.
- **TCO modelling (license + support + ops + compute)** → out of scope; depends on procurement model.
- **Architectural cost rationale (why these GPUs at these sizes)** → `groundx-architecture/references/ai-ml-lifecycle.md`, `vision-model.md`, `hybrid-search.md`, `summary-service.md`.
