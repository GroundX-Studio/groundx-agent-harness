# Deployer-Altitude Architecture

This file documents **how the pieces compose at deploy time** — the runtime topology a deployer needs to reason about when standing up GroundX on a Kubernetes cluster. It is *not* the canonical architecture description; for pipeline shape, pod responsibilities, identity model, and trust-boundary inventory, route to `groundx-architecture`. Treat this file as a deployment-facing consumer of architecture facts, not as a second source of truth.

The architecture skill describes the system at 9 altitudes. This file translates the system-altitude facts into a **deployer's runtime topology**: what talks to what, what stays inside the cluster, what crosses the cluster boundary, what's the deployer's responsibility versus the chart's.

## 1. Data flow at deployer altitude

End-to-end ingest of a document flows through the cluster like this:

1. **Client / SDK** hits the `groundx` orchestration microservice at the cluster ingress.
2. `groundx` writes initial metadata to the **relational DB**, places source bytes in the **object store**, and emits a **queue** message.
3. `upload` / `queue` / `pre-process` / `process` consume queue messages and orchestrate the pipeline. Process state is held in the **cache** and the **relational DB**.
4. The **layout sub-pipeline** (`layout-api` → `layout-process` → `layout-inference` (GPU) → `layout-correct` → `layout-ocr` → `layout-map` → `layout-save`) extracts the document's visual structure. `layout-inference` is the vision model; `layout-ocr` is Tesseract by default (or Google Cloud Vision when `gcv.json` is provided).
5. The **ranker pair** (`ranker-api` + `ranker-inference` (GPU)) generates retrieval-time signals.
6. The **summary stack** (`summary-client` orchestrator + `summary-api` + `summary-inference` (GPU, Gemma 3)) generates context summaries — *only if* `summary.api.enabled: true` + `summary.inference.enabled: true`. When `false`, `summary-client` calls an external LLM instead.
7. Chunked output (JSONL) lands in the **retrieval DB** (OpenSearch); X-Ray files land in the **object store**; process metadata closes out in the **relational DB**.
8. Search and RAG queries hit `groundx` directly and read from the retrieval DB plus the object store.

For the canonical pipeline depth (which microservice writes which artifact at which step, which state lives where, intermediate ↔ persistent distinction), route to `groundx-architecture/references/data-flow.md`. For per-microservice responsibilities, route to `groundx-architecture/references/ingest-service.md`, `vision-model.md`, `layout-ocr.md`, `hybrid-search.md`, `summary-service.md`.

## 2. Trust boundaries at deployer altitude

The **Kubernetes namespace is the trust enclosure**. Everything inside the namespace is mutually trusted by GroundX's default identity model; everything outside is treated as a boundary crossing.

For the canonical trust-boundary inventory (where customer identity is asserted, where it's checked, what's signed vs unsigned, the audit-log emission points), route to `groundx-architecture/references/identity-and-trust.md`. For customer-isolation enforcement on the store layer, route to `groundx-architecture/references/multi-tenancy.md`.

The deployer's side of the trust contract:

- **Namespace boundary.** GroundX assumes it owns its namespace. Co-tenanting GroundX with other workloads in the same namespace is not supported and is not how the chart is designed to be operated.
- **Backing-service authentication.** Credentials for the relational DB, cache, object store, retrieval DB, and queue are passed in through `values.yaml` (or Kubernetes Secrets that values.yaml references). The chart does not invent identities — the deployer provisions or accepts whatever identities the backing services require. See `references/services-prereqs.md` for per-service auth shape.
- **External LLM calls.** When `summary.api.enabled: false` + `summary.inference.enabled: false` and the summary engine is a 3rd-party endpoint, the chart passes the configured API key to `summary-client` and that key is what authenticates outbound calls. The trust-boundary implication (document content leaves the cluster) lives at `groundx-architecture/references/summary-service.md` § 6 + `identity-and-trust.md` § 6.2.
- **Workspace git credentials.** When `workspace.enabled=true`, the deployer provides a `workspace.token` or `workspace.existingSecret`. That credential is what authenticates outbound `git push` to GitHub / GitLab. See `groundx-architecture/references/workspace-architecture.md` § 5.3.
- **Per-customer identity.** Multi-tenancy is enforced by owner-username tagging on every stored artifact, not by namespace partitioning. The chart does *not* spin up a namespace per customer — see `groundx-architecture/references/multi-tenancy.md`.

## 3. Internal vs external communication

A deployer should be able to predict what stays inside the cluster and what doesn't. The breakdown:

### 3.1 Internal-only (never leaves the cluster by default)

All inter-pod communication uses **Kubernetes-native DNS** (`<service>.<namespace>.svc.cluster.local`). No service mesh ships with the chart. The traffic that stays inside the cluster:

- All API + orchestration ↔ pipeline-microservice calls.
- All pipeline-microservice ↔ pipeline-microservice handoffs (queue-mediated where the architecture requires durability; direct HTTP where it doesn't).
- All pipeline ↔ backing-service traffic *when* the backing service is operator-deployed-dedicated (Mode 2 — in-cluster MinIO / Percona / Redis / OpenSearch / Strimzi).
- Inference-pod ↔ orchestration-pod model calls (`layout-inference`, `ranker-inference`, `summary-inference`).

### 3.2 External by configuration (leaves the cluster only when the deployer opts in)

When backing services are in **existing customer-managed** (Mode 1) or **cloud-managed** (Mode 3) mode, the corresponding traffic leaves the cluster to whatever endpoint the deployer configured:

| Toggle | What leaves the cluster |
| --- | --- |
| `file.serviceType=s3` (or `file.existing.url` pointing externally) | All source-byte / X-Ray / intermediate-artifact reads and writes leave the cluster to the object store endpoint. |
| `db.existing.*` pointing externally | Process metadata + auth + queueing state reads/writes leave the cluster to the DB endpoint. |
| `cache.existing.addr` pointing externally | Hot process state and metric reads/writes leave the cluster to the cache endpoint. |
| `search.existing.url` pointing externally | JSONL chunk and search reads/writes leave the cluster to the retrieval DB endpoint. |
| Per-topic `stream.topics.<topic-name>.type: sqs` (or `stream.existing.*` pointing externally) | All inter-pod queue handoffs leave the cluster. |

These are intentional configurations. The chart does not surreptitiously route around them.

### 3.3 External by capability toggle (leaves the cluster only when a specific capability is enabled)

- **3rd-party summary LLM.** When the deployer configures `summary.existing` to point at an external endpoint (either `summary.existing.serviceType` is one of `openai` / `openai-base64` / `azure`, OR `summary.existing.url` is set for any other engine), the chart skips the in-cluster summary stack and `summary-client` calls the external `/chat/completions` endpoint on every summary generation. Document content (preprocessed chunks) crosses the cluster boundary on each call. See `references/engines.md` for the engine-selection mechanics and `groundx-architecture/references/summary-service.md` § 6 for the trust-boundary framing.
- **Google Cloud Vision OCR.** When a `gcv.json` GCP service account file is provided, `layout-ocr` switches from in-cluster Tesseract to GCV. Page images cross the cluster boundary on each OCR call. See `groundx-architecture/references/layout-ocr.md` § 5.2.
- **Workspace git remote.** When `workspace.enabled=true`, managed project publish operations push to GitHub / GitLab. See `groundx-architecture/references/workspace-architecture.md` § 5.3.

### 3.4 Always-external (these always cross the cluster boundary)

- **Model-weight downloads.** `layout-inference` and `ranker-inference` pull model blobs from S3 on pod init and when `config.py` targets change. In air-gapped deployments, these blobs must be mirrored locally — see `references/air-gapped.md` (planned).
- **Container image pulls.** The chart pulls from whatever registry is configured. Air-gapped deployments mirror images — see `references/air-gapped.md` (planned).

### 3.5 What does *not* leave the cluster

- **No model-update phone-home.** Models do not auto-update from a remote signal. Version changes are deployer-driven via chart values.
- **No telemetry, no usage analytics, no crash reports.** The chart does not call back to EyeLevel / GroundX / Anthropic / OpenAI / any vendor for anything other than the explicit configurations above. Observability is local — `/metrics` endpoints scraped by the deployer's Prometheus.
- **No managed-service control-plane callbacks.** The chart does not contact a SaaS control plane. `api.groundx.ai` is a separate distribution and is *not* called by an on-prem deploy.

For the canonical egress inventory (with full endpoint URLs and per-endpoint trust-boundary classification), route to `groundx-architecture/references/data-residency.md`.

## 4. Network policy is the deployer's responsibility

The Helm chart ships **zero `NetworkPolicy` resources**. The deployer authors their own based on the egress and internal-communication maps above.

This is intentional: GroundX runs on AWS EKS, Azure AKS, generic Kubernetes, Red Hat OpenShift, AWS private cloud, and air-gapped on-prem clusters. CNI capabilities, default-deny posture, and policy authoring conventions differ across all of them. The chart does not assume one and ship the wrong default.

For a deployer authoring NetworkPolicy, the practical input map:

- **Allow egress within the namespace** for all pipeline pods to reach all backing-service pods (when backing services are in-namespace).
- **Allow egress to whatever external backing-service endpoints** are configured (Mode 1 / Mode 3).
- **Allow egress to the configured summary LLM endpoint** (if `summary.api.enabled: false` + `summary.inference.enabled: false`).
- **Allow egress to `vision.googleapis.com`** (if `gcv.json` is provided).
- **Allow egress to the configured git remote** (if `workspace.enabled=true`).
- **Allow egress to the configured model-weight S3 endpoint** (always).
- **Allow egress to the container image registry** (always, at pod start).
- **Allow ingress to `groundx` on the configured ingress port** for API traffic.
- **Deny everything else** by default if the deployer's compliance posture requires it.

The author of this file is not the canonical NetworkPolicy producer — `references/troubleshooting.md` (planned) will capture the most common policy-misconfiguration failure modes when that file ships.

## 5. Service mesh and ingress

- **Service mesh: none.** The chart does not deploy Istio, Linkerd, or any mesh sidecar. All inter-pod communication uses native Kubernetes DNS. If the deployer runs a mesh, GroundX is mesh-agnostic — the chart neither requires nor configures one.
- **Ingress: deployer-supplied.** The chart exposes `groundx` (and `workspace-api` when workspace is enabled) as a Kubernetes `Service`. The deployer wires whatever ingress controller, load balancer, or API gateway their cluster uses to terminate TLS and route external traffic to the service. The chart does not ship an Ingress resource — for production-grade ingress authoring, route to `references/tls-and-certs.md`.

## 6. What this file does not cover

- **Canonical pipeline shape and pod responsibilities** → `groundx-architecture/references/data-flow.md`, `ingest-service.md`, `vision-model.md`, `layout-ocr.md`, `hybrid-search.md`, `summary-service.md`, `extraction-architecture.md`, `workspace-architecture.md`.
- **Canonical trust-boundary inventory and identity model** → `groundx-architecture/references/identity-and-trust.md`.
- **Customer-isolation enforcement at the store layer** → `groundx-architecture/references/multi-tenancy.md`.
- **Canonical egress endpoint inventory** → `groundx-architecture/references/data-residency.md`.
- **Cluster sizing — chips, GPUs, total resources, NVIDIA GPU Operator** → `references/cluster-requirements.md`.
- **Node-group label scheme and per-group resource profiles** → `references/node-groups.md`.
- **Backing-service field-by-field selection mechanics** → `references/services-prereqs.md`.
- **Field-by-field `values.yaml` reference** → `references/values-yaml.md` (planned).
- **Install workflow** → `references/install-flow.md` (planned).
- **TLS / cert / custom-CA authoring** → `references/tls-and-certs.md`.
- **NetworkPolicy templates and common misconfigurations** → `references/troubleshooting.md` (planned) when it ships.
