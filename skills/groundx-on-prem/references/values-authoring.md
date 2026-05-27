# values.yaml Authoring — Discovery Questionnaire

This file is the **first-entry workflow for producing a values.yaml**. The agent runs the discovery questionnaire below *before* emitting any chart configuration. Every question pins one or more fields the agent will set; every answer narrows the next set of questions; the exit gate at the end gates emission until every question has an answer.

For the field reference the questionnaire pins fields *into*, route to `values-yaml.md`. For the install ordering that consumes the produced values.yaml, route to `install-flow.md`. For backing-service decision logic per question, route to `services-prereqs.md`.

## 1. Workflow contract

**Before producing any values.yaml**, the agent:

1. Walks every question group in § 3 with the user (or with the requesting agent).
2. Records every answer. Marks any question that cannot be answered as "blocking" and asks the user to resolve before continuing.
3. After every question has an answer, runs the validation gate in § 5.
4. Only then emits values.yaml using the field shapes documented in `values-yaml.md`.
5. Emits the file in two parts: a main `values.<env>.yaml` and a `values.<env>.secret.yaml` companion (or refers credentials to a Kubernetes Secret per § 8 of `values-yaml.md`).

**Misuse cases to refuse:**

- "Generate a values.yaml for an AWS EKS deployment" with no further context → refuse; ask the questionnaire.
- "Fill in the defaults and let the deployer override later" → refuse; chart defaults assume context the agent cannot guess (mode, GPU availability, summary engine, backing-service modes).
- "Copy values.arcadia.yaml and change the names" → refuse unless the requesting agent has explicitly confirmed an archetype match (§ 4); customer-specific values files are not canonical templates.

Customer-specific upstream values files are internal verification aids only. Do not surface those file names in user-facing output unless the user explicitly asks about upstream source files; use the sanitized templates in `examples/` for external examples.

## 2. How to use this file

The questionnaire in § 3 is **canonical**. Walk every group in order — earlier answers narrow the option space for later ones (e.g., "no GPU available" forces "external summary engine" in § 3.4).

The archetypes in § 4 are **worked examples**, not shortcuts. When a deployment matches an archetype exactly, the agent can collapse several questions by referencing the archetype's pre-canned answers — but the agent must still confirm each answer with the user, not assume it.

Per-question annotation in § 3 shows: the answer's implication, the exact values.yaml fields it pins, cross-field constraints, gotchas. Match the level of detail to the question — never skip the implication just because the question seems obvious.

## 3. The questionnaire

### 3.1 Target platform

**Q:** Where is GroundX going to run?

| Option | Implication | Fields pinned |
| --- | --- | --- |
| AWS EKS | Cloud-managed equivalents available; AWS Load Balancer Controller for ingress; IRSA for workload identity; EFS or EBS CSI for storage. | `cluster.type: eks`. Often paired with `serviceAccount.name` bound to an IAM role. |
| Azure AKS | Azure-managed equivalents available; Application Gateway Ingress Controller (AGIC) or NGINX for ingress; Workload Identity for workload identity; Azure Files (RWX) or managed disks (RWO) for storage. The NVIDIA GPU Operator needs `runtimeClass: nvidia-container-runtime` on AKS. | `cluster.type: aks`. |
| Google GKE | GCP-managed equivalents available; GKE-native ingress; Workload Identity Federation for workload identity. | `cluster.type: gke`. |
| Red Hat OpenShift | OpenShift Route for ingress (not standard `Ingress` resource); OpenShift Container Storage or external CSI for storage; SCC constraints affect Chainguard image fit. | `cluster.type: openshift`. Often paired with `serviceType: Route` on exposed microservices. |
| Generic Kubernetes (on-prem) | Deployer-supplied ingress controller; deployer-supplied StorageClass; no workload-identity defaults; usually paired with operator-deployed-dedicated backing services. | `cluster.type: ""` or unset. |
| Minikube / kind (dev) | Single-node; everything bundled; GPU usually unavailable; ingress via `minikube tunnel` or NodePort. | `cluster.type: minikube`. |
| Air-gapped on-prem | Same as generic Kubernetes plus image-registry mirroring, model-weight mirroring, NVIDIA GPU Operator offline install. | `cluster.type: ""` plus `cluster.imagePullSecrets` for mirror, plus per-microservice `image` overrides. |

**Cross-field implications:** Platform choice cascades into § 3.7 (security: Chainguard images often paired with OpenShift / on-prem), § 3.8 (identity: IRSA only on EKS, Workload Identity on AKS / GKE), and § 3.11 (node-group scheme: defaults assume EKS-style labels).

**Gotchas:** On AKS, the NVIDIA GPU Operator chart needs `runtimeClass: nvidia-container-runtime` instead of the default `nvidia`. On OpenShift, anyuid / privileged SCCs may be needed for non-Chainguard images.

### 3.2 Deployment mode

**Q:** Is this a full GroundX deployment, or ingest-only?

| Option | Implication | Fields pinned |
| --- | --- | --- |
| Full platform | Default. Ingest + retrieval / RAG. All microservices deploy. | `mode: "all"` (or omit). |
| Ingest-only | Upstream ingest pipeline only; no retrieval. The retrieval DB (OpenSearch) is **not required**; many microservices can be disabled. Common for benchmarking, sizing runs, or upstream-only deployments that hand off to a separate retrieval cluster. | `mode: ingest`. Often paired with `search.*` left at defaults (or `search.enabled: false`) and many `<microservice>.enabled: false`. |

**Cross-field implications:** `mode: ingest` collapses § 3.5.4 (retrieval DB) — that question becomes optional. It does not, by itself, disable extraction or workspace.

### 3.3 GPU availability + budget

**Q:** Are NVIDIA GPUs available in the target cluster?

| Option | Implication | Fields pinned |
| --- | --- | --- |
| Yes, 24 GB+ per GPU available, multiple GPUs | Self-hosted summary stack is viable. Layout, ranker, and summary inference all run on GPU. | No specific field; informs § 3.4. |
| Yes, smaller GPUs (e.g., T4 16 GB) | Self-hosted summary stack is **not** viable at default sizing (Gemma 3 needs 24 GB). Layout and ranker can still run. | Forces § 3.4 to "external LLM". |
| No GPUs available | Forces all inference to external services. Significant cost-and-trust-boundary implications. | Forces § 3.4 to "external LLM"; `summary.api.enabled: false`, `summary.inference.enabled: false`. `layout.inference.deviceType: cpu` required, with the caveat that it is degraded performance. `ranker.inference` is not architecturally supported on CPU for production. |

**Cross-field implications:** No GPUs → forced external summary + degraded layout + unsupported ranker. The agent should surface this trade-off explicitly to the user before continuing.

**Gotchas:** A100 / H100 with MIG partitioning is fine but the deployer must set `cluster.hasMig: true` to signal MIG scheduling. Spot instances are not recommended for the inference tier — pre-emption mid-extraction loses in-flight work.

### 3.4 Summary engine choice

**Q:** Where does summary generation run?

| Option | Implication | Fields pinned |
| --- | --- | --- |
| Self-hosted (Gemma 3, default) | Requires GPU per § 3.3. ~24 GB GPU memory. No document content leaves the cluster on summary generation. | `summary.api.enabled: true`, `summary.inference.enabled: true`, `summary.inference.model.name`, `summary.inference.deviceUtilize`. |
| External — OpenAI | Document content leaves cluster on every summary call. Outbound API key required. Allow egress to `api.openai.com`. | `summary.api.enabled: false`, `summary.inference.enabled: false`, `summary.existing.serviceType: openai`, `summary.existing.apiKey`. |
| External — OpenAI-base64 | Same as OpenAI but base64-encodes image data in-request vs URL. Use when the model endpoint can't reach the cluster's storage. | `summary.existing.serviceType: openai-base64`. |
| External — Azure OpenAI | Same trust-boundary implications as OpenAI; Azure-hosted endpoint. | `summary.existing.serviceType: azure`, `summary.existing.url`, `summary.existing.apiKey`. |
| External — DeepInfra (or any other OpenAI-compatible endpoint) | The chart helper doesn't special-case `deep-infra` — the URL is what disables self-hosted, not the `serviceType` value. | `summary.existing.serviceType: deep-infra` (passes through to runtime), `summary.existing.url` (**required**), `summary.existing.apiKey`. See `references/engines.md` § 3.5. |
| ⚠ Not an external option: `serviceType: eyelevel` | `eyelevel` is the chart's *default* `summary.existing.serviceType` — it triggers self-hosted, not external. Don't pick this expecting an EyeLevel-hosted endpoint. | See `references/engines.md` § 3.6. |

**Cross-field implications:** External summary removes the need for the `eyelevel-gpu-summary` node group entirely. Document content crossing the cluster boundary is a trust-boundary event — note for the user. See `groundx-architecture/references/summary-service.md` § 6 for the full trust framing.

**Gotchas:** Test with the chart-default model first; switch engine afterward. Different engines have different output shape and latency profiles — answer-quality is not guaranteed equivalent across engines.

### 3.5 Backing services — one decision per service

For each of the five backing services, ask: existing in-house, chart-deployed dedicated, or cloud-managed equivalent? See `services-prereqs.md` § 2 for the three-mode decision rubric.

#### 3.5.1 Object Store (file)

| Option | Fields pinned |
| --- | --- |
| Existing customer-managed (in-house S3-compatible) | `file.enabled: false`, `file.bucketName`, `file.existing.url`, `file.existing.serviceType: minio` (or `s3` if S3-compatible). Credentials via `file.username` / `file.password` or `cluster.secrets`-referenced Secret. |
| Chart-deployed dedicated (MinIO operator) | `file.enabled: true`, `file.bucketName`, `file.username` / `file.password`. MinIO operator must be pre-installed. |
| Cloud-managed (AWS S3 / equivalent) | `file.enabled: false`, `file.bucketName`, `file.existing.url`, `file.existing.region`, `file.existing.serviceType: s3`. Credentials via `file.username` / `file.password`, `cluster.secrets`-referenced Secret, or IRSA on `serviceAccount.name`. |

**Cross-field implications:** S3 on EKS strongly prefers IRSA over inline keys. Mode-1 in-house S3-compatible at non-default port → set `file.existing.port`.

#### 3.5.2 Process Metadata DB (db)

| Option | Fields pinned |
| --- | --- |
| Existing customer-managed (in-house MySQL) | `db.enabled: false`, `db.dbName`, `db.existing.ro` / `db.existing.rw` / `db.existing.port`, `db.username` / `db.password`, `db.privilegedUsername` / `db.privilegedPassword`. If TLS, `db.existing.rootCerts`. |
| Chart-deployed dedicated (Percona operator) | `db.enabled: true`, `db.dbName`. Percona operator must be pre-installed. |
| Cloud-managed (AWS RDS / Azure Database for MySQL) | `db.enabled: false`, `db.dbName`, `db.existing.ro`/`rw`/`port`, credentials + `db.existing.rootCerts` (required when `require_secure_transport=ON`). |

**Gotchas:** RDS / Azure Database for MySQL with `require_secure_transport=ON` requires `db.existing.rootCerts`. See `values.aks.yaml` for the canonical DigiCert root CA example.

#### 3.5.3 Cache (Redis)

| Option | Fields pinned |
| --- | --- |
| Existing customer-managed | `cache.enabled: false`, `cache.existing.{addr, port, isCluster, ssl}`. |
| Chart-deployed dedicated | `cache.enabled: true`. Optional persistence via `cache.persistence.{enabled, capacity}`. |
| Cloud-managed (AWS ElastiCache / Azure Cache for Redis) | Same shape as existing customer-managed; `cache.existing.addr` points at the cloud endpoint. |

**Cross-field implications:** When a separate metrics Redis is preferred (independent endpoint for metrics scratch), set `cache.metrics.existing.{addr, port, isCluster, ssl}`.

#### 3.5.4 Retrieval DB (OpenSearch) — skip if `mode: ingest`

| Option | Fields pinned |
| --- | --- |
| Existing customer-managed | `search.enabled: false`, `search.existing.url`, `search.indexName`, `search.{username, password, privilegedUsername, privilegedPassword}`. |
| Chart-deployed dedicated (OpenSearch operator) | `search.enabled: true`, `search.indexName`, plus credentials. OpenSearch operator must be pre-installed. |
| Cloud-managed (AWS OpenSearch managed) | Existing customer-managed shape; `search.existing.url` points at managed endpoint. |

**Cross-field implications:** Skipped entirely when `mode: ingest`. Pinned by § 3.2.

#### 3.5.5 Queue (Kafka or SQS)

| Option | Fields pinned |
| --- | --- |
| Existing customer-managed Kafka | `stream.enabled: false`, `stream.existing.{domain, port}`. Per-topic `stream.topics.<name>.type: kafka` + `topic` + `groupId`. |
| Chart-deployed dedicated Kafka (Strimzi) | `stream.enabled: true`. Strimzi operator must be pre-installed. |
| Cloud-managed (AWS SQS) | `stream.enabled: false`. Per-topic `stream.topics.<name>.type: sqs` + `url` + `region`. AWS creds via `stream.{key, secret}` or per-topic, or via IRSA on `serviceAccount.name`. Visibility timeout must be 10+ minutes per queue. |

**Cross-field implications:** Mixing Kafka + SQS across topics is supported. Five canonical topics: `preProcess`, `process`, `summary`, `update`, `upload`.

### 3.6 Capability toggles

#### 3.6.1 Extraction microservices

**Q:** Will this deployment run schema-first extraction workflows?

| Option | Fields pinned |
| --- | --- |
| No (default) | `extract.enabled: false`. Extract microservices do not render. |
| Yes | `extract.enabled: true`, `cluster.preProcessors: [{processorId: 13, type: extract}]`. Configure `extract.agent.{serviceType, apiKey or existingSecret/secretName, modelId}`. If Google Drive output, `extract.save.{driveId, templateId, gcpCredentials or existingSecret/secretName}`. If callback, `extract.callbackUrl` + `extract.callbackApiKey`. |

**Cross-field implications:** Extract activation per document is gated by the workflow API request carrying an extraction YAML — see `groundx-architecture/references/extraction-architecture.md`. Pair with `groundx-extraction-workflows/` for the YAML authoring loop.

#### 3.6.2 Workspace runner subsystem

**Q:** Will this deployment manage developer / customer-facing UI projects (git-clone, edit, publish loop)?

| Option | Fields pinned |
| --- | --- |
| No (default) | `workspace.enabled: false`. GroundX Workspace facade endpoints return errors. |
| Yes — GitHub | `workspace.enabled: true`, `workspace.gitProvider: github`, `workspace.token` *or* `workspace.existingSecret` + `WORKSPACE_RUNNER_TOKEN` in the referenced Secret. If GitHub App, `workspace.github.{appId, installationId, privateKeyPem or privateKeySecret}`. `workspace.managedRepoOwner`. ReadWriteMany PVC for `workspace.pvc`. `workspace.publishDryRun: true` until ready to push for real. |
| Yes — GitLab | Same shape, `workspace.gitProvider: gitlab`, `workspace.gitlab.{apiBaseUrl, token, tokenSecret}`. |

**Cross-field implications:** The workspace runner emits outbound traffic to GitHub / GitLab on publish. Network policy must allow that egress. RWX storage class strongly preferred for the workspace PVC.

#### 3.6.3 OCR mode

**Q:** Tesseract (default, in-cluster, no egress) or Google Cloud Vision (per-call egress to GCP)?

| Option | Fields pinned |
| --- | --- |
| Tesseract (default) | No fields pinned. `layout.ocr.type` left unset. |
| Google Cloud Vision | `layout.ocr.type: google`, `layout.ocr.project: <gcp-project>`, and `layout.ocr.credentials: files/ocr/credentials.json` (the value is a path to a chart-packaged JSON file the deployer adds at install time; chart materializes a ConfigMap from it). See `references/ocr-mode.md` for the full setup. |

**Cross-field implications:** GCV crosses the cluster trust boundary on every OCR call. Allow egress to `vision.googleapis.com`.

### 3.7 Security & compliance

**Q:** Are there FedRAMP / SOC2-stringent / air-gapped / custom-CA constraints?

| Option | Fields pinned |
| --- | --- |
| None — standard deployment | No fields pinned beyond the chart defaults. |
| FedRAMP / SOC2-stringent (Chainguard images) | `imageType: chainguard`. Pods run as UID `65532`. Storage classes must permit non-root file ownership. `cluster.imagePullSecrets: [<chainguard-pull-secret>]`. `busybox.image` overridden to a Chainguard variant. |
| Air-gapped | Image registry mirroring: every microservice `image` field overridden to point at the in-network mirror; `busybox.image` overridden; NVIDIA GPU Operator and ingress controller charts also overridden. Plus model-weight mirroring (out-of-band). |
| Custom CA / in-cluster TLS | `cluster.tls.existingSecret: <secret-name>` referencing a `kubernetes.io/tls` Secret. May also need `db.existing.rootCerts` for downstream DB connection. |

**Cross-field implications:** Chainguard + air-gapped often paired (FedRAMP). Custom CA can stack on either.

### 3.8 Identity

**Q:** How should the cluster authenticate to cloud services (AWS, Azure, GCP)?

| Option | Fields pinned |
| --- | --- |
| Workload identity (IRSA on EKS, Workload Identity on AKS / GKE) | `serviceAccount.name: <pre-provisioned-sa>`. The ServiceAccount is annotated externally with the IAM role / Workload Identity binding. Credentials in `file.*`, `db.*`, `stream.*` left unset. |
| Static keys in Kubernetes Secret | Pre-install the Secret via the `groundx-secret` prereq chart. `cluster.secrets: [<secret-name>]`. Credentials read from env vars (`AWS_ACCESS_KEY_ID`, etc.) mounted from the Secret. |
| Inline in values.yaml | Credentials directly in `db.{username, password}`, `file.{username, password}`, `stream.{key, secret}`, etc. — typically in a `values.<env>.secret.yaml` companion kept out of version control. |
| Mixed | Common: IRSA for cloud services + Kubernetes-Secret-referenced for tokens (workspace runner, LLM API keys) + inline for low-sensitivity DB credentials. |

**Cross-field implications:** § 3.8 mode affects every backing service in § 3.5, the summary engine in § 3.4, the workspace runner in § 3.6.2, and the extract pipeline in § 3.6.1. Pick the strongest pattern the deployment can support.

### 3.9 HPA + observability

**Q:** Will this deployment use Horizontal Pod Autoscaling?

| Option | Fields pinned |
| --- | --- |
| No (default, fixed replicas) | `cluster.hpa: false`. Per-microservice `replicas.desired` used directly. |
| Yes | `cluster.hpa: true`, `metrics.enabled: true` (required — HPA scales against metrics). Per-microservice `replicas.{min, max, hpa, threshold, throughput}` tuned. Per-microservice `throughput.services.*` targets set. |

**Q:** Is there an existing Prometheus stack to wire a ServiceMonitor against?

| Option | Fields pinned |
| --- | --- |
| No | `metrics.serviceMonitor.enabled: false`. |
| Yes | `metrics.serviceMonitor.enabled: true`. kube-prometheus-stack or equivalent must be pre-installed. |
| Already running a separate metrics collector | `metrics.useExisting: true`. Skips the chart-deployed metrics microservice. |

**Cross-field implications:** Enabling HPA without metrics yields autoscalers with no signal — the chart will create HPAs but they have nothing to act on.

### 3.10 License + admin bootstrap

**Q:** Has a license key been procured?

If yes → set `licenseKey: <key>` in the secret companion file (or `cluster.secrets`-referenced Secret with `GROUNDX_LICENSE_KEY`).

**Q:** Should a bootstrap admin user be created at install time?

| Option | Fields pinned |
| --- | --- |
| No | `admin: {}` (empty). Admin users created via the management API after install. |
| Yes | `admin.{apiKey, email, password, username}` — provide at least one. Treat as credentials (secret companion or `cluster.secrets`-referenced). |

### 3.11 Node-group scheme

**Q:** Does the cluster's node-group labelling match the chart defaults?

The chart defaults expect five node-group label values applied to the cluster's nodes under the label key **`eyelevel_node`**:
- `eyelevel-cpu-only` — general CPU work
- `eyelevel-cpu-memory` — memory-heavy CPU work (e.g., `pre-process`)
- `eyelevel-gpu-layout` — layout-inference GPUs
- `eyelevel-gpu-ranker` — ranker-inference GPUs
- `eyelevel-gpu-summary` — summary-inference GPUs (only when self-hosted summary)

| Option | Fields pinned |
| --- | --- |
| Matches chart defaults | No fields pinned. `cluster.nodeLabels` left at defaults. |
| Different label values, same five categories | `cluster.nodeLabels.{cpuOnly, cpuMemory, gpuLayout, gpuRanker, gpuSummary}` overridden. |
| Different label key entirely | Per-microservice `nodeSelector` block override (set under each microservice). The chart key `eyelevel_node` itself is not configurable through values.yaml. |
| Fewer node groups (e.g., one GPU pool for everything) | Override all five `cluster.nodeLabels.*` to the same value. Acceptable for dev / small deployments; not recommended for production because GPU scaling axes collapse. |

**Cross-field implications:** Do not use the bare label key `node` — it collides with reserved metric labels in Prometheus / Grafana. See `references/node-groups.md` § 1 for the full reasoning.

## 4. Archetypes (worked examples)

Five named archetypes. When a deployment matches an archetype exactly, the agent can collapse the questionnaire's per-question dialogue to a single confirmation per archetype. The agent must still confirm each answer; do not assume the archetype matches without checking.

### 4.1 AWS-EKS-cloud-managed

**Profile:** Production AWS deployment. All backing services cloud-managed (S3, RDS, ElastiCache, SQS, AWS OpenSearch managed). GPUs available on EC2 (g5 / p4d instance families). IRSA for workload identity. HPA on. Self-hosted summary stack. No air-gapped / Chainguard constraints.

**Pre-canned answers:**
- 3.1 Target platform → AWS EKS.
- 3.2 Deployment mode → Full platform.
- 3.3 GPU availability → Yes, 24 GB+.
- 3.4 Summary engine → Self-hosted (Gemma 3).
- 3.5 Backing services → Cloud-managed across the board (S3 / RDS / ElastiCache / AWS OpenSearch managed / SQS).
- 3.6 Capability toggles → Extract: per deployment. Workspace: per deployment. OCR: Tesseract default.
- 3.7 Security → Standard (non-Chainguard).
- 3.8 Identity → IRSA via `serviceAccount.name`.
- 3.9 HPA + observability → HPA on; ServiceMonitor wired to kube-prometheus-stack.
- 3.10 License + admin → Procured key + bootstrap admin.
- 3.11 Node-group scheme → Chart defaults (Terraform-provisioned EKS managed node groups apply the labels).

**Internal upstream verification reference:** customer-specific values files cover extract + workspace variants. Do not surface those file names in user-facing output unless the user explicitly asks about upstream source files.

### 4.2 AKS-with-Azure-services

**Profile:** Production Azure deployment. Backing services cloud-managed (Azure Database for MySQL with TLS, Azure Cache for Redis, Azure Blob via S3-compat or AKS-bundled MinIO, AKS-bundled Strimzi or Event Hubs). Chainguard images for compliance. Workload Identity for cloud auth. GPUs on `NC` / `ND` series. Self-hosted summary stack on a 24 GB GPU.

**Pre-canned answers:**
- 3.1 Target platform → Azure AKS.
- 3.2 Deployment mode → Full platform (or ingest-only per deployment).
- 3.3 GPU availability → Yes.
- 3.4 Summary engine → Self-hosted *or* Azure OpenAI (per deployment).
- 3.5 Backing services → Azure Database for MySQL (Mode 3), Azure Cache for Redis (Mode 3), MinIO or Azure Blob (per deployment), AKS-bundled Strimzi (Mode 2).
- 3.6 Capability toggles → per deployment.
- 3.7 Security → Chainguard (`imageType: chainguard`). Plus `db.existing.rootCerts` for Azure Database TLS.
- 3.8 Identity → Workload Identity via `serviceAccount.name`.
- 3.9 HPA + observability → per deployment.
- 3.10 License + admin → per deployment.
- 3.11 Node-group scheme → AKS node pools labeled to match chart defaults.

**Notes:** NVIDIA GPU Operator on AKS needs `runtimeClass: nvidia-container-runtime`. Upstream reference: `values.aks.yaml`.

### 4.3 OpenShift-FedRAMP-air-gapped

**Profile:** Highly regulated / air-gapped on-prem OpenShift deployment. Chainguard images. All backing services chart-deployed-dedicated (no cloud egress). NVIDIA GPU Operator in offline mode. No external LLM (forced self-hosted summary). Custom CA. Long-lived per-customer deployment.

**Pre-canned answers:**
- 3.1 Target platform → Red Hat OpenShift; air-gapped.
- 3.2 Deployment mode → Full platform.
- 3.3 GPU availability → Yes (procured GPU hardware).
- 3.4 Summary engine → Self-hosted (only legal option in an air-gapped deployment).
- 3.5 Backing services → All chart-deployed-dedicated (operators pre-installed via OperatorHub or manual).
- 3.6 Capability toggles → Extract: per deployment; workspace: typically off; OCR: Tesseract (GCV would require external egress).
- 3.7 Security → Chainguard + air-gapped + custom CA (`cluster.tls.existingSecret`).
- 3.8 Identity → Static keys in Kubernetes Secret via `cluster.secrets`.
- 3.9 HPA + observability → HPA per deployment; ServiceMonitor wired to OpenShift's user-workload monitoring.
- 3.10 License + admin → Procured key + bootstrap admin (in Secret).
- 3.11 Node-group scheme → OpenShift MachineSets labeled per chart defaults; non-default scheme acceptable if surfaced.

**Internal upstream verification reference:** a customer-specific values file covers OpenShift + Chainguard-adjacent settings. Do not surface that file name in user-facing output unless the user explicitly asks about upstream source files.

### 4.4 Minikube / dev (everything bundled)

**Profile:** Single-node developer environment. Everything bundled (Mode 2 across the board). Often GPU-less or single GPU. HPA off. External summary engine (because the dev cluster doesn't have a 24 GB GPU). Inline credentials acceptable.

**Pre-canned answers:**
- 3.1 Target platform → Minikube / kind.
- 3.2 Deployment mode → Full platform *or* ingest-only.
- 3.3 GPU availability → Often no.
- 3.4 Summary engine → External (OpenAI is the typical dev choice).
- 3.5 Backing services → All chart-deployed-dedicated. Persistence often disabled to keep the dev cluster small.
- 3.6 Capability toggles → Per task being prototyped.
- 3.7 Security → Standard.
- 3.8 Identity → Inline in values.yaml (acceptable for dev).
- 3.9 HPA + observability → Off.
- 3.10 License + admin → Dev license key; admin bootstrap with `password` (acceptable for dev only).
- 3.11 Node-group scheme → Single-node — `cluster.nodeLabels` collapsed to a single value.

**Upstream reference:** `src/groundx/values/minikube/values.yaml`.

### 4.5 Ingest-only benchmarking

**Profile:** Throughput-benchmarking deployment. Only the ingest pipeline runs. Retrieval DB skipped. Often paired with a separate hand-off cluster.

**Pre-canned answers:**
- 3.2 Deployment mode → `mode: ingest`.
- 3.5.4 Retrieval DB → skipped.
- 3.6 Capability toggles → Extract typically on; workspace typically off; OCR per benchmarking goal.
- Everything else → per § 4.1 / 4.2 / 4.3 depending on platform.

**Internal upstream verification reference:** customer-specific values files cover workspace-enabled variants. Do not surface those file names in user-facing output unless the user explicitly asks about upstream source files.

## 5. Validation gate — before emission

Before producing values.yaml, the agent confirms every item in this checklist:

1. **§ 3.1 Target platform** has a single answer.
2. **§ 3.2 Deployment mode** has a single answer.
3. **§ 3.3 GPU availability + budget** has a single answer.
4. **§ 3.4 Summary engine** is consistent with § 3.3 (no self-hosted-summary answer when § 3.3 is "no GPUs").
5. **§ 3.5.1–§ 3.5.5** each have a single answer. § 3.5.4 may be skipped only when § 3.2 is `mode: ingest`.
6. **§ 3.6.1–§ 3.6.3** each have a single answer. If § 3.6.1 = Yes, the agent has captured at least one engine for the extract agent. If § 3.6.2 = Yes, the agent has captured the git-provider credentials shape. If § 3.6.3 = GCV, the agent has captured the GCP service account JSON path.
7. **§ 3.7 Security & compliance** has a single answer. If Chainguard, the agent has confirmed the image-pull-secret is configured. If air-gapped, the agent has captured the image-mirror endpoints. If custom CA, the agent has captured the Secret name.
8. **§ 3.8 Identity** has a single answer. If "Workload identity" or "Static keys in Kubernetes Secret", the agent has captured the ServiceAccount / Secret name.
9. **§ 3.9 HPA + observability** has an answer pair (HPA yes/no + ServiceMonitor yes/no/useExisting).
10. **§ 3.10 License + admin** has an answer pair (license yes/no + bootstrap admin yes/no with credentials).
11. **§ 3.11 Node-group scheme** has a single answer.

If any check fails, the agent loops back to § 3 and asks the user to resolve, naming the specific question that lacks an answer. The agent does not emit values.yaml with chart defaults filling in for missing answers.

## 6. After validation — emit

After the validation gate passes:

1. The agent emits two files:
   - `values.<env>.yaml` (main configuration, version-controlled).
   - `values.<env>.secret.yaml` (credentials, gitignored) — *or* a reference to a Kubernetes Secret installed via the `groundx-secret` prereq chart.
2. For each capability block, the agent uses the field shapes from `values-yaml.md` (§ 4 for backing services, § 5 for microservices, § 7 for cross-field implications).
3. The agent runs `helm template` against the produced values to confirm the chart renders.
4. The agent hands off to `install-flow.md` for the install ordering.

## 7. What this file does not cover

- **Field shapes** → `values-yaml.md`. Every field this questionnaire pins is documented there.
- **Backing-service decision logic** → `services-prereqs.md`.
- **Node-group label scheme + per-microservice overrides** → `node-groups.md`.
- **Cluster prerequisites (chips, GPUs, k8s/helm versions)** → `cluster-requirements.md`.
- **Install ordering after the values.yaml is produced** → `install-flow.md`.
- **Architectural rationale for any answer** → `groundx-architecture/references/`.
- **Annotated minimum-viable / production example values files** → `examples/`.
- **Secret-handling depth and placeholder discipline** → `credentials.md`.
