# Deployment Options — Cross-Environment Tradeoffs

This file documents **the deployer's choice between cluster targets** — AWS EKS, Azure AKS, Google GKE, Red Hat OpenShift, on-prem / bare-metal Kubernetes, and air-gapped. Each option has different node-image story, GPU operator path, backing-service shape, and Day-2 operational burden.

For per-cloud-managed backing-service substitution, route to `service-substitution.md`. For OpenShift-specific chart behaviour, route to `openshift.md`. For air-gapped deployments, route to `air-gapped.md`. For AWS-specific Terraform helpers, route to `terraform-aws.md`.

## 1. The five canonical deployment targets

| Target | Cluster install | GPU story | Backing-service preference | Typical deployer profile |
| --- | --- | --- | --- | --- |
| **AWS EKS** | Terraform (chart-shipped) or eksctl | NVIDIA GPU Operator via Helm | Mostly cloud-managed (RDS, S3, ElastiCache, MSK, OpenSearch Service) | Most common; cloud-native shops |
| **Azure AKS** | Azure CLI / Terraform | NVIDIA GPU Operator via Helm + `runtimeClass: nvidia-container-runtime` | Cloud-managed (Azure DB for MySQL, Blob Storage via S3 gateway, ElasticSearch alternatives) | Microsoft-heavy enterprises |
| **Google GKE** | gcloud / Terraform | GKE-managed (no operator install) | Cloud-managed (CloudSQL, GCS, Memorystore, Confluent on GCP) | GCP-heavy enterprises; common for Workload Identity Federation |
| **Red Hat OpenShift** | OpenShift install | NVIDIA GPU Operator via OperatorHub | Operator-deployed in-cluster (more common than cloud-managed) | Regulated enterprises with Red Hat support contracts |
| **On-prem / bare-metal Kubernetes** | Vanilla K8s, kubeadm, RKE2, k3s, etc. | NVIDIA GPU Operator via Helm | All in-cluster (no cloud equivalent available) | FedRAMP / DoD / air-gapped / data-residency-constrained |

## 2. Per-target tradeoffs

### 2.1 AWS EKS

**Strengths.**
- Most mature managed Kubernetes; reliable upgrade path.
- IRSA (IAM Roles for Service Accounts) integrates cleanly with the chart's `serviceAccount.name` field.
- Full cloud-managed backing-service set (RDS / S3 / MSK / ElastiCache / OpenSearch Service) — chart's substitution mode 3 fits naturally.
- GPU instance options span small (g4dn.xlarge with T4) through large (p4d.24xlarge with A100).
- Terraform helpers ship with the chart under `terraform/aws/{vpc,eks}/`.

**Caveats.**
- Cross-AZ data egress charges accumulate quickly with multi-AZ deployments. Plan VPC layout to minimize.
- GPU node pools (managed node groups) have version-pinned AMIs; GPU driver updates require node pool rolling.
- IRSA requires careful IAM policy authoring; mistakes manifest as runtime 403s.

**Best fit.** Standard production deployment. Cloud-managed RDS + S3 + OpenSearch Service is the cheapest-to-operate path.

### 2.2 Azure AKS

**Strengths.**
- AKS Managed Identity / Pod Identity / Workload Identity Federation provides IRSA equivalent.
- Azure ML integrations for the AI/ML pipeline (less relevant to the chart itself).
- Azure DB for MySQL is RDS-equivalent; Azure Blob Storage works via the chart's S3-compatible `file.existing.serviceType: s3` (assuming the deployer fronts blob with an S3-compatible gateway, or uses one of Azure's S3-compatible options).
- NVIDIA Driver pre-installed on AKS GPU node pools; only the device plugin and toolkit need the operator.

**Caveats.**
- GPU Operator requires `runtimeClass: nvidia-container-runtime` (not the generic `nvidia`). See `services-operators.md` § 2.3 and `gpu-operator.md` § 3.
- Cross-region egress pricing similar to AWS.
- AKS upgrade cadence sometimes lags AWS for the latest K8s versions.

**Best fit.** Microsoft-aligned enterprises. The `values.aks.yaml` seed at the repo root is the canonical starting point.

### 2.3 Google GKE

**Strengths.**
- GKE Autopilot mode handles node sizing automatically (though less control over the GroundX-required node groups).
- Workload Identity Federation maps cleanly to chart `serviceAccount.name` for GCS / CloudSQL / Memorystore access.
- GPU drivers pre-installed on GKE GPU node pools; no operator install needed (GKE manages it).
- Cloud Vision API integration is closest on GCP (route `layout.ocr.type: google` with `layout.ocr.credentials: <gcp-service-account.json>`).

**Caveats.**
- GKE Autopilot's resource model can conflict with the chart's per-pod node selectors. Standard GKE (not Autopilot) is the cleaner target.
- Backing-service shape: CloudSQL for MySQL works; Memorystore for cache works; for Kafka, Google's managed Kafka is limited — Confluent on GCP is the common alternative.

**Best fit.** Google-aligned enterprises; deployments needing tight Google Cloud Vision OCR integration.

### 2.4 Red Hat OpenShift

**Strengths.**
- Strong RBAC / SCC model for security-sensitive deployments.
- OperatorHub provides packaged operator installs (NFD, GPU Operator, Strimzi, etc.) — one-click pattern.
- Mature Day-2 tooling (Route, image stream, build configs).
- Often the only supported choice for FedRAMP-track or regulated enterprises.

**Caveats.**
- Chart's SCC-aware behaviour matters — see `openshift.md` for the security-context, Route-vs-Ingress, and skip-symlink branches.
- Backing-service ecosystem is more in-cluster-via-operators than cloud-managed.
- OpenShift Container Storage (OCS / ODF) is the standard storage layer.

**Best fit.** Regulated enterprises with Red Hat contracts; FedRAMP-track deployments.

### 2.5 On-prem / bare-metal Kubernetes

**Strengths.**
- Full control over hardware, networking, and data residency.
- No per-AZ egress costs.
- Suitable for air-gapped (`air-gapped.md`).

**Caveats.**
- All backing services run in-cluster; no cloud-managed offload.
- GPU driver management, node-pool lifecycle, and storage provisioning are deployer responsibilities.
- Kubernetes distro choice (RKE2, k3s, kubeadm, OpenShift, Tanzu) shapes Day-2 burden.
- Hardware procurement and lifecycle become the deployer's problem.

**Best fit.** Data-residency-constrained, air-gapped, or cost-sensitive deployments where hardware amortization beats cloud per-hour pricing.

## 3. Cost orientation (rough)

| Target | Compute cost orientation | Operational cost orientation |
| --- | --- | --- |
| EKS / AKS / GKE with mostly cloud-managed backing | High per-hour, low ops burden | Lowest TCO when scale is moderate |
| EKS / AKS / GKE with all in-cluster | Lower per-hour, higher ops burden | Cheaper for high scale; trades hours for cloud spend |
| OpenShift on cloud | Medium per-hour, medium ops burden, plus Red Hat support cost | Predictable; expensive when small |
| OpenShift on-prem | Hardware amortization + power/cooling + support | Cheapest at large scale; significant capex |
| Vanilla on-prem | Lowest per-month compute; highest ops burden | Best fit for >100% utilization workloads |

For the manual cost-modelling workflow, route to `cost-estimation.md` § 8.

## 4. Cross-target chart settings

The chart's behaviour varies per target:

| `cluster.type` | Implications |
| --- | --- |
| `eks` (default) | Standard Kubernetes behaviour; `runAsUser` set from `groundx.container.username`. |
| `aks` | Same as eks for chart logic; GPU Operator uses `runtimeClass: nvidia-container-runtime`. |
| `gke` | Same as eks for chart logic; deployer skips GPU Operator install (GKE-managed). |
| `openshift` | `runAsUser` omitted (SCC owns it); Route rendered instead of Ingress; symlink creation skipped. See `openshift.md`. |
| `minikube` | Local-dev convenience; symlink creation skipped. Not for production. |

The chart's `groundx.clusterType` helper (`_helpers/main.tpl:51–54`) defaults to `eks`. Other branches: `groundx.isOpenshift` (`_helpers/main.tpl:108–111`), `groundx.createSymlink` (`_helpers/main.tpl:56–59`).

## 5. Per-target seed values files

The chart ships per-target seeds at the repo root and under `src/groundx/values/`:

| Target | Seed file (root) | Seed file (chart-internal) |
| --- | --- | --- |
| AWS / EKS-shaped | `sample.values.yaml` (legacy; uses a non-canonical field name — see § 1 of `license-and-admin.md`); `values.aws.services.yaml` (canonical) | `src/groundx/values/values.aws.services.yaml` |
| AKS | `values.aks.yaml` + `values.aks.secret.yaml` | (no chart-internal AKS-specific seed; chart values.yaml + values.aks.yaml is the pattern) |
| Existing-everything | (no root seed) | `src/groundx/values/values.existing.yaml` |
| OpenAI summary | (no root seed) | `src/groundx/values/values.openai.yaml` |
| Minikube | (no root seed) | `src/groundx/values/minikube/values.yaml` |
| OpenShift | (no root seed) | `src/groundx/values/openshift/values.yaml` |
| Chainguard hardened | (no root seed) | `src/groundx/values/chainguard/values.yaml` + per-operator chainguard variants |

Each seed is opinionated for its target. Use as the starting point and layer overrides.

## 6. Migration paths between targets

Migration patterns to know:

- **EKS → AKS**: Re-deploy chart with `values.aks.yaml` seed; migrate data from RDS to Azure DB for MySQL; migrate S3 to Blob (via S3-gateway or rewrite). NVIDIA Operator changes to AKS variant.
- **AKS → EKS**: Reverse; same complexity.
- **On-prem → cloud-managed**: Re-deploy with cloud seed; export and import backing-service data; verify NetworkPolicy and IAM. Significant work; rarely done as a single migration — usually a fresh start.
- **OpenShift → vanilla K8s (or vice versa)**: SCC vs PSP rework; Route vs Ingress rework; storage class realignment. See `openshift.md` for SCC notes.

The chart itself migrates cleanly between targets when the deployer reconciles each environmental difference. The hard work is the data layer.

### 6.1 Migrating from a non-chart or hosted deployment (Lambda / EC2 / ECS)

The patterns above are chart-to-chart moves. Migrating a deployment that is **not** a chart install — a hosted GroundX, or a self-run stack on Lambda / EC2 / ECS — is a different exercise: there is no `values.yaml` to carry over and no `helm rollback` to fall back on. Treat it as standing up a fresh chart deployment beside the old stack, moving data and traffic across, and keeping a switch-back path at every step. If part of the source is *already* a GroundX chart install (a common hybrid — some services on Lambda / EC2 / ECS, some already on an EKS chart deployment), split the plan: treat the chart piece as a brownfield upgrade (`install-flow.md` § 3.5.1, then `upgrades.md`) and the non-chart pieces with the steps below.

1. **Audit the source first.** Use the source deployment's owning repositories and live AWS resources to inventory what is actually running and what it uses. For any chart-installed portion, use `install-flow.md` § 3.5.2. Flag anything with no chart equivalent — for example an OCR backend like AWS Textract (`ocr-mode.md` § 1) — because those force a functional change, not a lift-and-shift.
2. **Stand up and validate the new chart deployment.** Install per `install-flow.md` and run the full post-install validation, including the ingest-to-search smoke test (`install-flow.md` § 7), before any production traffic reaches it.
3. **Choose a coexistence model for the backing stores.** The chart consumes external backing services (`service-substitution.md`); decide whether the new deployment shares the old stack's stores or gets its own:
   - **Shared stores (in-place):** point the new chart deployment at the *same* RDS / S3 / OpenSearch / queue the old stack uses. Lowest data-copy effort, but old and new now share one data plane — you must guarantee each queue is consumed by exactly one side at a time (step 4), and accept that both write the same DB and object store during the window.
   - **Copied stores (parallel):** replicate data into new stores (RDS snapshot, S3 replication, search reindex) and run the new deployment isolated. Cleaner blast radius, at the cost of a data freeze plus a final delta-sync at cutover.
4. **Cut each queue over from old to new, one at a time.** GroundX moves work through the `stream` queues/topics (`service-substitution.md` § 6). Whether both stacks consuming one queue at once causes trouble depends on the queue's own semantics, not on the switch being instantaneous: two Kafka consumers in the *same* consumer group split the partitions (each message handled once, though ownership churns), while consumers in *different* groups each receive the full stream (duplicate processing); an SQS queue leases each message to one consumer for its visibility timeout, so a second consumer reprocesses only work whose lease expires before it is acknowledged. Rather than depend on getting those controls right across two stacks, sequence a clean cutover for each queue: (a) quiesce the producers feeding it, wherever they currently run (stop or repoint them), so no new messages arrive after you check the depth — a drain check is not a quiescence guarantee while producers are still live; (b) let the old consumer finish its in-flight work and acknowledge it, waiting out the SQS visibility timeout (or Kafka's in-flight/commit window) so nothing is still leased or unacked; (c) stop the old consumer; (d) start the new side's consumer — for a Kafka topic, reuse the **same consumer group** so committed offsets carry over: set the new deployment's per-topic `groupId` (the `groupId` field under `stream.topics.<topic>`) to the old value (the chart maps it to the Kafka `group.id`), which needs no manual offset work. Only if you cannot reuse the group id, migrate offsets by file — both groups must be idle (the old consumer stopped at step (c), the new one not yet started), and every command needs `--bootstrap-server <broker:port>` (plus `--command-config <client.properties>` on a secured cluster). Export the old group's committed offsets with `kafka-consumer-groups --bootstrap-server <broker> --group <old> --topic <topic> --reset-offsets --to-current --dry-run --export > offsets.csv`; preview the import into the new group with `kafka-consumer-groups --bootstrap-server <broker> --group <new> --reset-offsets --from-file offsets.csv --dry-run` (the CSV carries its own scope, so no `--topic` on the import); apply it with `kafka-consumer-groups --bootstrap-server <broker> --group <new> --reset-offsets --from-file offsets.csv --execute`; then verify with `kafka-consumer-groups --bootstrap-server <broker> --group <new> --describe` before starting the new consumer. A fresh group id with nothing carried over instead resumes from `auto.offset.reset` (`earliest` replays the whole topic, `latest` skips everything produced since); SQS has no offsets, so the queue itself is the shared position; (e) resume the producers on the new side. Cut the queues over in pipeline-dependency order (an upstream stage's output queue before the stage that consumes from it), one queue at a time, so you can verify each stage on the new deployment before moving the next.
5. **Cut traffic over at your own edge.** The old side is not a chart install, so the chart's DR DNS-flip (`dr-cross-region-runbook.md` § 5.5) is only the mechanic, not the whole story: shift request traffic from the old endpoint to the new ingress at whatever fronts them (Route53 weighted records, an ALB / API gateway, or client config), ideally gradually, confirming new-side health (`install-flow.md` § 7) at each weight step.
6. **Roll back by switching back, not by `helm rollback`.** Because the old stack is not a chart release, `helm rollback` cannot revert this migration — and even on the chart side it does not revert PVCs, external stores, or data migrations (`upgrades.md` § 6). The normal rollback for each step above is to **switch back**: repoint the queue consumer or the traffic edge to the old side. Reserve restore-from-snapshot for confirmed data corruption, as a separate deliberate decision, not the routine rollback. Switch-back is clean for traffic; for the shared-stores model it is clean only if the new version wrote nothing the old version cannot read — no incompatible DB schema migration, no changed search-index mapping, no new object-store layout, and no changed queue/message payload format. If the new version did any of those, old instances may fail or mis-read on switch-back, so prove backward compatibility of the database, search index, object store, and message formats across the two versions before treating shared-store switch-back as safe. And once the new side has written into *copied* stores, switching back does not reconcile the diverged data — weigh both when choosing the coexistence model in step 3.

This is deployment-process guidance: the chart supplies the destination and the validation, not an automated migrator. Use the brownfield audit (`install-flow.md` § 3.5.2) only for a chart-installed part of the source.

## 7. Choosing — the 5-minute decision

Ask:

1. **Where is my data subject to residency / compliance constraints?** Drives in-cluster vs cloud-managed and air-gapped.
2. **What cloud are my engineers / ops team aligned with?** Drives EKS vs AKS vs GKE.
3. **Do I have Red Hat support / OpenShift expertise?** Drives OpenShift vs vanilla.
4. **What is my GPU budget shape?** Drives self-hosted summary inference vs external LLM; drives GPU instance choice.
5. **How much ops capacity do I have?** Drives "rent ops-load via cloud-managed services" vs "own ops-load via in-cluster operators."

The most common production shape that this skill has documented experience with: **EKS with cloud-managed RDS + S3 + OpenSearch Service + (Strimzi-on-cluster Kafka OR cloud-managed alternative), self-hosted Gemma inference on g5 / p4d GPUs**. That's the "Selective substitution" pattern from `service-substitution.md` § 5.3.

## 8. Cross-field implications

| Target choice | Sets these chart fields implicitly |
| --- | --- |
| EKS | `cluster.type: eks`; usually `serviceAccount.name: <irsa-sa>`; `cluster.pvClass: gp3` or similar. |
| AKS | `cluster.type: aks`; NVIDIA Operator uses AKS values file. |
| GKE | `cluster.type: gke`; `cluster.pvClass: standard-rwo` or `filestore`. |
| OpenShift | `cluster.type: openshift`; SCC controls UID; Route may be rendered. |
| Air-gapped | `admin.imageRepository` set; `cluster.imagePullSecrets` set; no external engines or OCR. |

## 9. What this file does not cover

- **Per-target Terraform / provisioning scripts** → `terraform-aws.md` for AWS; consult cloud-provider docs for AKS/GKE.
- **OpenShift-specific install** → `openshift.md`.
- **Air-gapped specifics** → `air-gapped.md`.
- **Cost-modelling math** → `cost-estimation.md` § 8.
- **Automated migration / ETL tooling from a non-chart source** → not provided; § 6.1 is a manual process runbook, not a migrator.
- **Substitution decision matrix** → `service-substitution.md` § 5.
- **Operator install per backing service** → `services-operators.md`.
- **DR across regions** → `dr-cross-region-runbook.md`.
