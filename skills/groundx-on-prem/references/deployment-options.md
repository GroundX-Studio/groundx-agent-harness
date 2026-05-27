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
- **Substitution decision matrix** → `service-substitution.md` § 5.
- **Operator install per backing service** → `services-operators.md`.
- **DR across regions** → `dr-cross-region-runbook.md` (planned).
