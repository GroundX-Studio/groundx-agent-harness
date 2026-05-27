# Install Flow

This file documents the **ordered install workflow** for deploying GroundX onto a Kubernetes cluster. It covers the canonical AWS EKS happy path (the upstream `groundx-on-prem` repo's shipped workflow), plus the deviations needed for Mode-1 (existing customer-managed backing services) and Mode-2 (operator-deployed-dedicated backing services).

For values.yaml authoring, route to `references/values-yaml.md`. For backing-service decision logic, route to `references/services-prereqs.md`. For cluster prerequisites (chips, GPUs, k8s/helm versions, namespace, PV class), route to `references/cluster-requirements.md`.

## 1. The shipped install path

The upstream `groundx-on-prem` repo ships two scripts that together describe the canonical AWS EKS install:

- **`terraform/aws/setup-eks`** — interactive bootstrap. Stands up the VPC + EKS cluster + storage class. Calls `bin/environment` under the hood. Writes `values.aws.local.yaml` + `storageclass/values.aws.local.yaml` based on the chosen storage driver (EFS or EBS).
- **`bin/environment`** — terraform wrapper used by `setup-eks`. Drives `terraform/aws/vpc` and `terraform/aws/eks` (deploy and destroy).

The two phases (cluster bootstrap → helm install) are kept separate. Deployers bringing their own EKS cluster (or running on AKS / GKE / OpenShift / on-prem Kubernetes) skip phase 1 and go straight to phase 2.

## 2. Pre-install — outside the chart

Before any helm command runs, the following must already be in place. The chart does **not** create these for the deployer:

| Prereq | What | When required |
| --- | --- | --- |
| **Kubernetes cluster** | Reachable cluster, `kubectl` configured. | Always. |
| **Helm v3.8+** | `helm` binary on the operator's machine. | Always. |
| **Default StorageClass** | A `StorageClass` that dynamic-provisions `ReadWriteOnce` (or `ReadWriteMany` for EFS-style shared) PVs. | When the chart deploys any backing service or workspace PVC. |
| **NVIDIA GPU Operator** | Cluster-level operator for GPU scheduling. | When GPU microservices are deployed (`layout-inference`, `ranker-inference`, `summary-inference` with `summary.api.enabled: true` + `summary.inference.enabled: true`). |
| **TLS certificates + Ingress controller + DNS** | TLS secret, ingress controller (e.g., NGINX, AWS Load Balancer Controller, OpenShift Route), DNS A/CNAME record pointing at the ingress endpoint. | Before the deployer wires external API traffic. The chart exposes Services; the ingress is the deployer's responsibility. |
| **Backing-service infrastructure** | Per backing service, in whichever of the three modes the deployer chose (see `references/services-prereqs.md` § 2). For Mode 1: in-house service reachable from the cluster. For Mode 2: operator already installed (Strimzi, Percona, MinIO, OpenSearch). For Mode 3: cloud-managed endpoint and credentials. | Before the main `groundx` chart install. |
| **Image registry access** | Image pull secrets configured for `cluster.imagePullSecrets`. | When pulling from a private registry (e.g., Chainguard's). |
| **License key + admin credentials** | From EyeLevel / GroundX. | Required when the deployment is licensed. Set via `licenseKey` + `admin.*` in the secret companion file. |

For TLS / DNS / ingress wiring details (cert-manager, ingress controller selection, OpenShift Route quirks), route to `references/tls-and-certs.md`.

## 3. Phase 1 — cluster bootstrap (AWS EKS shipped path)

Skip this phase when bringing an existing cluster. The `terraform/aws/setup-eks` script orchestrates:

1. **Interactive prompts** for region, storage driver (EFS recommended; EBS supported), VPC ownership, cluster name, AWS role / SSH key.
2. **VPC creation** — `bin/environment aws-vpc` runs `terraform apply` in `terraform/aws/vpc/`. Output: `vpc_id`, subnets, SSH security group.
3. **EKS cluster + node groups** — `bin/environment eks` runs `terraform apply` in `terraform/aws/eks/`. The terraform writes node groups labeled `eyelevel_node=eyelevel-cpu-only`, `eyelevel_node=eyelevel-cpu-memory`, `eyelevel_node=eyelevel-gpu-layout`, `eyelevel_node=eyelevel-gpu-ranker`, `eyelevel_node=eyelevel-gpu-summary` (label *values* are configurable via the env tfvars). Storage class is provisioned via the EFS or EBS CSI driver based on the chosen driver.
4. **Generated values files** — `terraform/aws/setup-eks` writes two files the helm install will consume:
   - `src/groundx/prereqs/storageclass/values.aws.local.yaml` — generated StorageClass definition.
   - `values.aws.local.yaml` — `cluster.pvClass`, `cluster.pvAccessMode`, and (when workspace is enabled) the workspace PVC details.

After phase 1 completes, `kubectl get nodes` shows the labeled node groups and the cluster is ready for helm.

For deeper Terraform details (VPC sizing, node-group autoscaling configuration, NVIDIA driver), route to `references/terraform-aws.md` (planned).

## 4. Phase 2 — helm install (canonical sequence)

The canonical helm sequence after the cluster is ready:

### 4.1 Create the namespace

```bash
kubectl create namespace eyelevel
```

The default namespace name is `eyelevel`. Match whatever `namespace:` is set to in values.yaml (see `references/values-yaml.md` § 2.1).

### 4.2 Add Helm repos

```bash
helm repo add groundx https://registry.groundx.ai/helm --force-update
helm repo add nvidia https://helm.ngc.nvidia.com/nvidia
helm repo update
```

`registry.groundx.ai/helm` hosts the official chart releases. `helm.ngc.nvidia.com/nvidia` hosts the NVIDIA GPU Operator chart. Air-gapped deployments mirror these locally — see `references/air-gapped.md` (planned).

### 4.3 Install the NVIDIA GPU Operator

```bash
helm install nvidia-gpu-operator \
  nvidia/gpu-operator \
  -n nvidia-gpu-operator \
  --create-namespace \
  --atomic \
  -f helm/values/nvidia/values.yaml
```

The operator installs into its own namespace (`nvidia-gpu-operator`), not the GroundX namespace. The `--atomic` flag rolls back on failure. The bundled `helm/values/nvidia/values.yaml` configures the operator for the GroundX use case.

**Verify:**

```bash
kubectl get pods -n nvidia-gpu-operator
kubectl get nodes -o json | jq '.items[].status.allocatable["nvidia.com/gpu"]'
```

The pods should reach `Running`; the allocatable `nvidia.com/gpu` on GPU nodes should report a non-empty number.

For NVIDIA GPU Operator specifics (driver mode, AKS `runtimeClass` quirk), route to `references/gpu-operator.md` (planned).

### 4.4 Install the prereq charts

The chart family ships **three companion charts** that install supporting Kubernetes resources before the main GroundX chart. Install in this order:

```bash
helm upgrade --install groundx-storageclass \
  groundx/groundx-storageclass \
  -n eyelevel

helm upgrade --install groundx-secret \
  groundx/groundx-secret \
  -n eyelevel \
  -f values.<env>.secret.yaml

helm upgrade --install groundx-service-account \
  groundx/groundx-service-account \
  -n eyelevel
```

| Prereq chart | What it installs | Why first |
| --- | --- | --- |
| `groundx-storageclass` | The `StorageClass` resource the main chart's PVCs reference. | Must exist before any chart-managed PVC is created. Skip when the cluster's existing default StorageClass is being reused. |
| `groundx-secret` | A Kubernetes `Secret` containing the credentials referenced via `existingSecret` fields in the main chart. | Must exist before any pod referencing the Secret tries to start. |
| `groundx-service-account` | The ServiceAccount(s) referenced by chart-managed pods (workspace runner, etc.). | Must exist before any pod requesting that ServiceAccount tries to start. |

The prereq charts live under `src/groundx/prereqs/{storageclass,secret,serviceaccount}/` in the upstream repo and are also published to the `groundx` helm repository.

### 4.5 Install the ingress controller (cluster-specific)

On AWS EKS, the upstream workflow installs the AWS Load Balancer Controller + the IRSA wiring needed for it to provision ALBs:

```bash
helm upgrade --install aws-load-balancer-controller \
  eks/aws-load-balancer-controller \
  -n kube-system \
  --set clusterName=<cluster-name> \
  --set serviceAccount.create=true \
  --set serviceAccount.name=aws-load-balancer-controller \
  --set region=<region>

# Annotate with the IRSA role
kubectl annotate serviceaccount \
  -n kube-system aws-load-balancer-controller \
  eks.amazonaws.com/role-arn=arn:aws:iam::<account>:role/<role-name> \
  --overwrite

# Reload after annotation
kubectl -n kube-system rollout restart deployment aws-load-balancer-controller
```

On Azure AKS, generic Kubernetes, OpenShift, or air-gapped clusters, this step is replaced by whatever ingress mechanism the cluster uses (AKS Application Gateway Ingress Controller, NGINX Ingress, OpenShift Route, etc.). The chart does not ship `Ingress` resources — the deployer wires the cluster's ingress against the chart's `Service` (`groundx`, and `workspace-api` when workspace is enabled). For details, route to `references/tls-and-certs.md`.

### 4.6 Install the main `groundx` chart

```bash
helm upgrade --install groundx \
  src/groundx \
  -n eyelevel \
  -f values.<env>.yaml \
  -f values.<env>.secret.yaml \
  -f values.aws.local.yaml         # phase-1 generated file, EKS only
```

Multiple `-f` flags layer values files left-to-right (later wins). The conventional layering:

1. `values.<env>.yaml` — environment-specific overrides (sizing, mode, engines, node-label scheme).
2. `values.<env>.secret.yaml` — credentials (see `references/values-yaml.md` § 8).
3. `values.aws.local.yaml` — phase-1 generated (EKS only); contains pvClass + workspace PVC details.

**Verify (full checklist):**

```bash
# Are pods up?
kubectl get pods -n eyelevel

# Are helm releases healthy?
helm list -n eyelevel --all

# Logs from any not-Ready pod
kubectl logs -n eyelevel <pod-name>

# Application health
kubectl port-forward -n eyelevel svc/groundx 8080:80
curl http://localhost:8080/health
```

For a full smoke-test (end-to-end ingest of a known-good document, search round-trip), route to `groundx-api/` for the API call shape after install.

## 5. Phase 2 — Mode-2 deviation (operator-deployed backing services)

When backing services are operator-deployed-dedicated (Mode 2), the deployer installs the backing-service operators **between** the prereq charts (§ 4.4) and the main chart (§ 4.6). The chart's `<service>.enabled: true` fields hand off to whatever operator is already installed in the cluster.

Suggested ordering, per backing service:

| Service | Operator | Install before |
| --- | --- | --- |
| Cache (Redis) | Bitnami Redis chart or operator-equivalent | `groundx` main chart |
| DB (MySQL) | Percona Operator for MySQL | `groundx` main chart |
| File (Object store) | MinIO operator | `groundx` main chart |
| Search (OpenSearch) | OpenSearch operator | `groundx` main chart |
| Stream (Kafka) | Strimzi | `groundx` main chart |

Each backing-service operator has its own CRD + values surface; consult the operator's documentation for installation. The chart only requires that the operator be installed *and* its provisioned service be reachable when the main chart's pods start. The chart's `<service>.enabled: true` block then drives the chart's own provisioning of the service via the operator's CRDs.

When all five operators are in place and their backing services are healthy, run the main chart install (§ 4.6) as usual.

## 6. Phase 2 — Mode-1 / Mode-3 deviation (existing or cloud-managed backing services)

When backing services are existing customer-managed (Mode 1) or cloud-managed (Mode 3), the deployer:

1. **Skips** the backing-service operator install steps from § 5.
2. **Sets `<service>.enabled: false`** in the main values.yaml for each backing service that is being supplied externally.
3. **Sets `<service>.existing.*`** to point at the external endpoint (and provides credentials in the secret companion file).

Otherwise the helm sequence (§ 4.1 → § 4.6) is identical. For contributor/internal verification only, upstream customer-specific values files include real-world examples of Mode-1 / Mode-3 mixes; use them to verify field shape, but do not surface those file names in user-facing output unless the user explicitly asks about upstream source files.

## 7. Verification checklist (post-install)

A full health check covers four layers:

### 7.1 Pod / release state

```bash
# All pods Running?
kubectl get pods -n eyelevel

# Helm releases reporting deployed (not failed)?
helm list -n eyelevel --all

# Any restart loops?
kubectl get pods -n eyelevel --field-selector=status.phase!=Running
```

### 7.2 Backing-service connectivity

```bash
# DB readiness
kubectl get pods -n eyelevel -l app.kubernetes.io/component=mysql

# Cache readiness
kubectl get pods -n eyelevel -l app.kubernetes.io/component=redis

# Search readiness
kubectl get pods -n eyelevel -l app.kubernetes.io/component=opensearch
```

The exact label selectors depend on which mode (operator-deployed vs existing-customer-managed) and which operator versions are in use. For operator-specific health, consult each operator's CRD status (e.g., `kubectl get perconaservermysql -n eyelevel`).

### 7.3 GroundX application health

```bash
# Application /health endpoint
kubectl port-forward -n eyelevel svc/groundx 8080:80
curl http://localhost:8080/health
```

Expected: `200 OK` once the application has connected to all backing services. Failure here typically means the chart could not reach a backing service — inspect the pod logs (`kubectl logs -n eyelevel <pod-name>`) for the failure reason.

### 7.4 End-to-end smoke test

Run an ingest against a known-good document through the GroundX API, wait for processing to complete, run a search query, verify the result. For the API call shape, route to `groundx-api/`.

For common failure modes (stuck documents, queue back-pressure, GPU scheduling failures, summary engine misconfig), route to `references/troubleshooting.md` (planned).

## 8. Uninstall

The reverse of install. Suggested ordering:

```bash
# Stop accepting traffic — uninstall the ingress wiring first
helm uninstall aws-load-balancer-controller -n kube-system   # EKS-specific

# Uninstall the main chart
helm uninstall groundx -n eyelevel

# Uninstall prereqs (storage class can usually stay)
helm uninstall groundx-service-account -n eyelevel
helm uninstall groundx-secret -n eyelevel
# helm uninstall groundx-storageclass -n eyelevel              # only if dropping the SC

# Uninstall the NVIDIA GPU Operator
helm uninstall nvidia-gpu-operator -n nvidia-gpu-operator

# Drop the namespace (also removes any remaining PVCs)
kubectl delete namespace eyelevel
```

For Mode-2 backing-service operators (Strimzi / Percona / MinIO / OpenSearch / Redis), uninstall those after the main chart but before deleting the namespace — each has its own `helm uninstall` + CRD-finalizer cleanup.

**PVC reclamation.** When `StorageClass.reclaimPolicy` is `Retain` (the default for EFS-backed installs in the shipped Terraform), deleting the namespace does *not* delete the underlying PVs. The deployer reclaims storage manually. When `reclaimPolicy` is `Delete` (the EBS default), namespace deletion triggers PV deletion.

For full cluster teardown (uninstall + `bin/environment` destroy), reverse the bootstrap: `bin/environment -c eks` then `bin/environment -c aws-vpc`.

## 9. Air-gapped deployment

Air-gapped deployments add three concerns to the canonical flow:

1. **Image registry mirroring** — every container image the chart references (main chart pods, NVIDIA GPU Operator, ingress controller, operators, busybox init container) is mirrored to an in-cluster or in-network registry, and the chart's `image:` references are overridden via values.yaml to point at the mirror.
2. **Model-weight S3 mirroring** — `layout-inference` and `ranker-inference` pull model weights from S3 at pod init. The air-gapped deployer mirrors these blobs to an internal S3-compatible object store and overrides the model-source URL.
3. **NVIDIA GPU Operator offline mode** — the GPU operator's driver and toolkit images must be in the internal registry; the operator chart values override the image source.

For the full air-gapped runbook, route to `references/air-gapped.md` (planned).

## 10. What this file does not cover

- **Field-by-field values.yaml** → `references/values-yaml.md`.
- **Backing-service decision logic** → `references/services-prereqs.md`.
- **Cluster prerequisites (chips, GPUs, k8s/helm versions, namespace, PV class)** → `references/cluster-requirements.md`.
- **Node-group label scheme + per-microservice node-label overrides** → `references/node-groups.md`.
- **NVIDIA GPU Operator install details (driver mode, AKS quirk)** → `references/gpu-operator.md` (planned).
- **Terraform AWS EKS specifics** → `references/terraform-aws.md` (planned).
- **TLS, certs, custom CA, ingress controller choice** → `references/tls-and-certs.md`.
- **Air-gapped deployment full runbook** → `references/air-gapped.md` (planned).
- **Disaster recovery / cross-region failover runbook** → `references/dr-cross-region-runbook.md` (planned) + `groundx-architecture/references/disaster-recovery.md`.
- **Common failure modes + fixes** → `references/troubleshooting.md` (planned).
- **API calls post-install** → `groundx-api/`.
- **Marketing / positioning on why on-prem** → `product-brand-gtm/` or `master-brand-gtm/`.
