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

## 2.5 Cloud-authority gate — before any provisioning

**This gate runs before § 3 Phase 1, not after it.** Phase 1 is not a read-only planning step: `bin/environment aws-vpc` and `bin/environment eks` run `terraform apply` and create a VPC, an EKS control plane, node groups (including GPU), IRSA roles and storage. That is the largest and least reversible mutation in this document, and it happens *before* any cluster exists to run kube-context or RBAC checks against — so cloud-level authority has to be established here.

Skip this section only when Phase 1 is skipped (bring-your-own cluster); then go straight to § 3.5.

**1. Prove cloud identity and target region — before the first `terraform apply`.**

```sh
aws sts get-caller-identity
```

Confirm with the operator that the returned **account** and the configured **region** are the ones they intend to provision into. An EKS cluster created in the wrong account or region is expensive to unwind and cannot be undone by a rollback.

**2. Review the Terraform plan.** `terraform/aws/setup-eks` supports a test pass per stack — run it and show the operator what will be created before anything is applied:

```sh
bin/environment aws-vpc -t     # plan only
bin/environment eks -t         # plan only
```

**3. Get explicit, per-invocation approval before each apply.** `bin/environment` invokes `terraform apply --auto-approve`, so **Terraform itself will not prompt** — the operator's approval must be captured here, separately for the VPC apply and the EKS apply. Treat cluster provisioning and `terraform destroy` as irreversible mutations under § 4.0: they require a second, explicit confirmation naming the specific stack.

Do not proceed to § 3 until identity, plan review, and approval are all confirmed for the stack being applied.

## 3. Phase 1 — cluster bootstrap (AWS EKS shipped path)

Skip this phase when bringing an existing cluster. The `terraform/aws/setup-eks` script orchestrates:

1. **Interactive prompts** for region, storage driver (EFS recommended; EBS supported), VPC ownership, cluster name, AWS role / SSH key.
2. **VPC creation** — `bin/environment aws-vpc` runs `terraform apply` in `terraform/aws/vpc/`. Output: `vpc_id`, subnets, SSH security group.
3. **EKS cluster + node groups** — `bin/environment eks` runs `terraform apply` in `terraform/aws/eks/`. The terraform writes node groups labeled `eyelevel_node=eyelevel-cpu-only`, `eyelevel_node=eyelevel-cpu-memory`, `eyelevel_node=eyelevel-gpu-layout`, `eyelevel_node=eyelevel-gpu-ranker`, `eyelevel_node=eyelevel-gpu-summary` (label *values* are configurable via the env tfvars). Storage class is provisioned via the EFS or EBS CSI driver based on the chosen driver.
4. **Generated values files** — `terraform/aws/setup-eks` writes two files the helm install will consume:
   - `src/groundx/prereqs/storageclass/values.aws.local.yaml` — generated StorageClass definition.
   - `values.aws.local.yaml` — `cluster.pvClass`, `cluster.pvAccessMode`, and (when workspace is enabled) the workspace PVC details.

After phase 1 completes, `kubectl get nodes` shows the labeled node groups and the cluster is ready for helm.

For deeper Terraform details (VPC sizing, node-group autoscaling configuration, NVIDIA driver), route to `references/terraform-aws.md`.

## 3.5 Install-authority preflight

This is the **cluster-level** half of the authority check: it can only run once a cluster exists, so it sits after Phase 1. Cloud-level authority (identity, Terraform plan, approval to provision) is § 2.5 and must already have happened for the Phase-1 path — § 4.1 is the first *in-cluster* mutation, not the first mutation overall.

Before the first in-cluster mutating command (`kubectl create namespace eyelevel`, § 4.1) — regardless of whether Phase 1 ran or was skipped for a bring-your-own cluster — confirm the operator actually has install-level authority, not just a configured `kubectl`. This is distinct from, and additive to, `references/troubleshooting.md § 0`'s access preflight, which is scoped to read/inspect access for debugging an already-running install and never checks install-level write RBAC or cloud identity.

For AWS/EKS targets, first have the operator establish their AWS session per their organization's standard AWS login procedure — e.g. `aws sso login --profile <profile>` for IAM Identity Center setups, or their identity provider's console/CLI flow — before running the checks below. This file does not restate any organization's login steps.

Run and have the operator confirm each of the three checks below before the first in-cluster mutation:

1. **Cloud identity** (when the target is AWS/EKS) — `aws sts get-caller-identity`. Confirm the returned account/role is the one the operator intends to deploy into.
2. **Kube-context / target-cluster confirmation** — `kubectl config current-context` and/or `kubectl cluster-info`. Confirm this is the intended cluster, not a stale or wrong context.
3. **Install-level RBAC — a screening pass, not a guarantee.** The `can-i` list below catches the common "this identity cannot install" case early. It is **not** exhaustive and must not be described as such: what the chart renders changes with values (enabling `metrics` alone adds a cluster-scoped `APIService` plus `Role`/`RoleBinding`), and creating RBAC objects at all requires permissions you may hold only via `escalate`. Treat a clean screening pass as "no obvious blocker", then prove authorization with the server-side dry-run in § 4.5.1 after the namespace and prerequisite APIs exist.

   ```sh
   # Cluster-scoped kinds
   kubectl auth can-i create namespace
   kubectl auth can-i create storageclass
   kubectl auth can-i patch nodes                      # node labeling (§ 4.0 mutation class)
   kubectl auth can-i create customresourcedefinition  # GPU Operator (§ 4.3)
   kubectl auth can-i create clusterrole               # GPU Operator, and metrics RBAC

   # Namespaced kinds — target namespace
   for r in deployment statefulset service configmap secret serviceaccount persistentvolumeclaim; do
     kubectl auth can-i create "$r" -n eyelevel
   done

   # Other namespaces this flow writes to — easy to miss
   kubectl auth can-i create deployment -n nvidia-gpu-operator  # § 4.3 installs with --create-namespace
   kubectl auth can-i patch serviceaccount -n kube-system       # § 4.5 annotates the ALB controller SA

   # Brownfield: `helm upgrade --install` also updates, patches and deletes — not just creates
   for v in update patch delete; do
     kubectl auth can-i "$v" deployment -n eyelevel
   done
   ```

   Confirm the response is `yes` for each.

Do not proceed to § 4.1 until the operator has explicitly confirmed the account/context and the screening checks. This is intentionally not the final authorization proof: a genuine greenfield cluster does not have the target namespace yet, and the prerequisite APIs are installed later, so an actual-manifest server-side dry-run here would fail for ordering reasons rather than permissions. Run the authoritative check at § 4.5.1, after those prerequisites exist and before the main chart is installed.

## 3.5.1 Detect existing install

Before the first Phase-2 mutating command (§ 4.1 `kubectl create namespace`), check whether GroundX is **already installed anywhere on this cluster** — regardless of whether the operator described this as a "deploy" or an "install".

**Do not scope this search.** Neither the namespace nor the release name is fixed: `namespace` is operator-chosen (`references/values-yaml.md` § 2.1 recommends `groundx-prod` / `groundx-stage`), and the Helm release name is chosen at install time and unconstrained by the chart. A live deployment released as `prod-groundx` in `groundx-prod` would return an empty result from a namespace-scoped search — **exit 0, no error, indistinguishable from an empty cluster** — and the fresh-install path would then mutate a running system.

Search cluster-wide and match on the **chart**, not the release name — but do not match the chart name by prefix alone. This deployment is **five charts**, four of which install as their own Helm releases in § 4.4:

| Chart | Installed by | `chart` field value looks like |
|---|---|---|
| `groundx` | § 4.6 — **the main chart** | `groundx-<version>` |
| `groundx-secret` | § 4.4 prereqs | `groundx-secret-0.1.0` |
| `groundx-service-account` | § 4.4 prereqs | `groundx-service-account-0.1.0` |
| `groundx-storageclass` | § 4.4 prereqs | `groundx-storageclass-0.1.1` |
| `groundx-strimzi-kafka-cluster` | § 4.4 prereqs | `groundx-strimzi-kafka-cluster-0.1.1` |

Helm sets the `chart` field to `<chart-name>-<version>`, so **every one of those starts with `groundx-`**. A `startswith("groundx-")` filter therefore returns five rows for a single ordinary install and reads it as five installs. Match the main chart by shape instead — the `groundx-` prefix followed *immediately by a version*:

```bash
helm list -A --all --max 10000 -o json | jq '{main: [.[] | select(.chart | test("^groundx-[0-9]"))], components: [.[] | select(.chart | test("^groundx-(?![0-9])"))]}'
```

`--all` matters on the supported Helm 3.8 floor: without it, pending installs are omitted and can be misread as greenfield. Helm also caps a list at `--max` rows. If this command returns exactly 10,000 total rows, do not make the greenfield/brownfield decision yet; page again with `--offset 10000` (then 20000, and so on), combine every page, and run the same classification over the combined JSON.

Decide on **`main`**, never on the total row count. `components` are expected parts of one install, not installs of their own:

| `main` | `components` | What it means → what to do |
|---|---|---|
| 0 | 0 | Genuine greenfield — cluster-wide absence is real evidence. Proceed to § 4.1. |
| 0 | ≥ 1 | **Prereqs are installed, the main chart is not** — an interrupted or partially-completed install, *not* a deployed GroundX. Resume at § 4.4 (the prereq installs are idempotent `helm upgrade --install`) and continue through § 4.6. **Do not route to `references/upgrades.md`** — there is no deployed release to upgrade. |
| 1 | any | Brownfield. Capture the main row's `namespace` and `name` (the release), then stop the fresh-install path and route to `references/upgrades.md` — its pre-upgrade checklist, schema diff, dry-run, downgrade guard and rollback path govern from here, not § 4.1–§ 4.6. |
| ≥ 2 | any | Several GroundX installs exist (for example prod and staging on one cluster). **Ask the operator which one they are targeting** — do not guess, and do not assume the first row. |

**That one command already carries everything you need** — no follow-up call, and nothing newer than the documented Helm floor. Each `main` row gives:

| Field | Use |
|---|---|
| `name` | the release name to pass as `-n`-scoped `<release>` in every later command |
| `namespace` | the namespace to target, instead of assuming `eyelevel` |
| `chart` | `groundx-<version>` — the **deployed chart version** |

Read the version off a **`main`** row only. Stripping the `groundx-` prefix from a `main` row leaves the version, but the same operation on a component row yields `secret-0.1.0`, which is not a version — which is why the classification above has to come first:

```bash
helm list -A --all --max 10000 -o json | jq -r '.[] | select(.chart | test("^groundx-[0-9]")) | "\(.name)\t\(.namespace)\t\(.chart | ltrimstr("groundx-"))"'
```

This shorthand is for a result below the 10,000-row cap. If pagination was required above, run the extraction against the same combined JSON rather than issuing an unpaged or status-filtered second query.

Deliberately **not** `helm get metadata`: that subcommand was added in Helm **3.13**, while this skill supports **v3.8+** (`references/cluster-requirements.md` § 3). On a v3.8–v3.12 client it fails with `unknown command "metadata"` — and that error looks a lot like "no release found", which is exactly how a live cluster gets misread as greenfield. `helm list`'s `chart` field has been present since v3.8 and carries the same version.

Hand the discovered release, namespace and chart version to `references/upgrades.md` — the downgrade comparison lives there, in the path that actually has a deployed version to compare against.

## 4. Phase 2 — helm install (canonical sequence)

The canonical helm sequence after the cluster is ready:

### 4.0 Approval gate — read before mutating

Before issuing any mutating command anywhere in **§ 3–§ 8** — including the Phase-1 `terraform apply` runs in § 3, which are gated by § 2.5 — stop and present the full enumerated mutation list below, and get the operator's explicit approval before proceeding. This gate is deploy-path-specific — it is not the `references/troubleshooting.md § 0` debug-scoped mutation list, which covers a different (debug-time) set of mutations.

**The enumerated mutation classes**, any one of which requires a stop-and-approve before the corresponding command runs:

- Namespace create/change
- Node labeling — changing node label values on cluster nodes
- Storage resource create/change (StorageClass, PVC)
- NVIDIA GPU Operator install
- Prereq/backing-service chart installs
- Secret/ServiceAccount create/change
- `helm install` / `helm upgrade --install`
- Ingress/TLS/DNS/image-pull changes
- Terraform/cluster-provisioning runs (terraform apply / destroy)
- Delete/destroy operations

Every mutating step in § 3–§ 8 is gated by this list — Phase-1 provisioning (§ 3) included, via § 2.5. **Irreversible or stateful mutations** — Secret writes, IRSA/IAM role binding, any `kube-system` change, PV reclamation, or a delete/destroy operation — require a **second, explicit confirmation naming that specific mutation**, beyond the general approval above.

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

`registry.groundx.ai/helm` hosts the official chart releases. `helm.ngc.nvidia.com/nvidia` hosts the NVIDIA GPU Operator chart. Air-gapped deployments mirror these locally — see `references/air-gapped.md`.

**Pin the chart version — don't just `repo update`.** The public repo can serve a chart version older or newer than the release already deployed (captured from § 3.5.1's `helm list` `chart` field). `--force-update` + `helm repo update` only refresh the local cache to whatever the repo currently serves; they are not a version guard. Installing without a pin risks silently **downgrading** a live release if the public repo lags behind the deployed chart version.

**How you pin depends on where the chart comes from — the two cases are not interchangeable:**

| Install source | Example | How to pin |
| --- | --- | --- |
| **Repository reference** (`groundx/<chart>`) — the § 4.4 prereq charts, and § 4.6 when installing `groundx/groundx` | `helm upgrade --install groundx-secret groundx/groundx-secret --version 0.1.0` | Run `helm search repo groundx --versions`, then pass an explicit **`--version <chart-version>`** on every such command. Each component has its own version; do not reuse the main `groundx` chart's version. |
| **Local path** (`src/groundx`, `./chart`, or a packaged archive such as `groundx-<version>.tgz`) — the § 4.6 command as written | `helm upgrade --install groundx src/groundx` | **`--version` does nothing here and must not be used.** Helm ignores it for a local chart: `helm template src/groundx --version 99.99.99` exits 0 and renders the local chart anyway, so the flag reads as a pin while pinning nothing. Instead read `src/groundx/Chart.yaml`'s `version:` and confirm the checkout's source identity (branch/commit), and use that value in the § 4.6 downgrade comparison. |

Do not add `--version` to a local-path install to "satisfy" the pin rule — a flag that is silently ignored is a **false guarantee**, and worse than an absent pin.

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

For NVIDIA GPU Operator specifics (driver mode, AKS `runtimeClass` quirk), route to `references/gpu-operator.md`.

### 4.4 Install the prereq charts

The chart family ships **three companion charts** that install supporting Kubernetes resources before the main GroundX chart. Install in this order:

These are **repository** installs, so each one carries an explicit `--version` (see § 4.2). Resolve the versions first with `helm search repo groundx --versions`.

```bash
helm upgrade --install groundx-storageclass \
  groundx/groundx-storageclass \
  --version <chart-version> \
  -n eyelevel

helm upgrade --install groundx-secret \
  groundx/groundx-secret \
  --version <chart-version> \
  -n eyelevel \
  -f values.<env>.secret.yaml

helm upgrade --install groundx-service-account \
  groundx/groundx-service-account \
  --version <chart-version> \
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

### 4.5.1 Authoritative manifest authorization check

Now that the target namespace and prerequisite APIs exist, send the *actual* rendered main-chart manifests through the API server's authorization and admission path without persisting them. A `can-i` list covers only kinds someone remembered to list; this is the authoritative answer for the selected values.

**Both forms below are renders.** When `metrics.enabled: true` (not the chart default), the output contains a chart-generated `metrics-tls` private key; other Secrets can appear depending on your values. Read the authorization result, not the manifests; never paste the output into chat, logs, or a PR. See `references/credentials.md` for render-output secret handling.

**On Helm 3.13 or newer:**

```sh
helm upgrade --install groundx src/groundx -n eyelevel \
  -f values.<env>.yaml -f values.<env>.secret.yaml \
  --dry-run=server
```

**On Helm 3.8–3.12:**

```sh
helm template groundx src/groundx -n eyelevel \
  -f values.<env>.yaml -f values.<env>.secret.yaml \
  | kubectl apply -n eyelevel --dry-run=server -f -
```

The fallback exercises Kubernetes authorization and admission but skips Helm's own server-side validation. Piping directly keeps secret-bearing output off the terminal. Plain Helm `--dry-run` validates locally only and does not satisfy this check. Do not proceed to § 4.6 until the operator confirms this server-side dry-run is clean.

### 4.6 Install the main `groundx` chart

**Required: render/dry-run before the live install.** Before running the live command below, render the merged manifest and present it for operator review:

```bash
helm template src/groundx \
  -n eyelevel \
  -f values.<env>.yaml \
  -f values.<env>.secret.yaml \
  -f values.aws.local.yaml         # phase-1 generated file, EKS only
```

(and/or `helm upgrade --install groundx --dry-run` using the same flags). This mirrors the dry-run gate documented for upgrades in `references/upgrades.md § 7`; cross-reference `references/values-authoring.md § 6` step 3 — that step's authoring-confirm render is not a substitute for this install-flow gate. Only proceed to the live command once the operator has reviewed the rendered/previewed output and signed off. **When `metrics.enabled: true` (not the chart default), the rendered output contains a chart-generated `metrics-tls` private key** — see `references/credentials.md` for render-output secret handling before sharing or pasting it anywhere.

**Pin the source version deliberately.** This step runs only on the greenfield branch — § 3.5.1 sent every brownfield cluster to `references/upgrades.md`, so there is no deployed release to compare against here and no downgrade to guard. What matters on this path is knowing exactly which chart you are installing: the explicit `--version` pin from § 4.2 for a repository install, or `src/groundx/Chart.yaml`'s `version:` plus the checkout's branch/commit for a local path. Record that version — it becomes the "deployed version" for every future upgrade. **The downgrade comparison itself lives in `references/upgrades.md` § 2 step 0**, the path that actually has a deployed version.

This command installs from a **local path**, so there is no `--version` to pin (§ 4.2) — verify `src/groundx/Chart.yaml`'s `version:` and the checkout's source identity instead, and carry that value into the downgrade comparison above. If you are installing from the repository rather than a checkout, use `groundx/groundx` **with** an explicit `--version`.

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

For common failure modes (stuck documents, queue back-pressure, GPU scheduling failures, summary engine misconfig), route to `references/troubleshooting.md`.

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

For full cluster teardown (uninstall + `bin/environment` destroy), reverse the bootstrap: `bin/environment eks -c` then `bin/environment aws-vpc -c`.

## 9. Air-gapped deployment

Air-gapped deployments add three concerns to the canonical flow:

1. **Image registry mirroring** — every container image the chart references (main chart pods, NVIDIA GPU Operator, ingress controller, operators, busybox init container) is mirrored to an in-cluster or in-network registry, and the chart's `image:` references are overridden via values.yaml to point at the mirror.
2. **Model-weight fetch is hard-wired to `upload.groundx.ai`** — at pod init a `download-model` init container runs `wget` against a **hardcoded** URL (`https://upload.groundx.ai/<layout|ranker|summary>/model/current/<version>.tar.gz.part.NN`) and `tar`-extracts the weights into a model-cache PVC. The host is a literal in the chart template (`templates/app/inference.yaml`) — it is **not** exposed as a values.yaml field — there is **no values-based override** for the weight host, and no such field exists. With no egress the `wget` fails, but the loop's exit status is never checked and the script still `touch`es the `complete.<version>` marker, so the init container **exits 0** and the pod starts with an empty or partial model cache; the false marker then makes every later replica skip the download too. See `references/air-gapped.md` § 6.5 for the full symptom and the marker cleanup needed to recover. Air-gapped options, in order of preference: **(a) pre-seed the model-cache PVC** — the init container **always renders** (its `pvc` defaults are non-empty, so it cannot be switched off) and **skips the download only when the `complete.<version>` marker already exists on the volume**. The chart creates the claim itself (`layout-model`, `ranker-model`, `summary-model`) and `pvc` overrides are schema-valid **only on `ranker.inference` and `summary.inference`** — `layout.inference` has no `pvc` property. Because the claim and the pod are created together, populating before first start is **not a chart-supported sequence yet** — see `references/air-gapped.md` § 6.5 before relying on it; **(b) intercept the host** — make an in-network mirror answer for `upload.groundx.ai` via internal DNS + a trusted TLS cert; **(c) patch/fork the chart** to change the host. This is a known `groundx-on-prem` chart limitation (the host is not parameterized) — track a chart fix separately; do not tell the operator to "override the URL" through values, because no such value exists.
3. **NVIDIA GPU Operator offline mode** — the GPU operator's driver and toolkit images must be in the internal registry; the operator chart values override the image source.

For the full air-gapped runbook, route to `references/air-gapped.md` — the hardcoded weight-fetch above is covered there as § 6.5.

## 10. What this file does not cover

- **Field-by-field values.yaml** → `references/values-yaml.md`.
- **Backing-service decision logic** → `references/services-prereqs.md`.
- **Cluster prerequisites (chips, GPUs, k8s/helm versions, namespace, PV class)** → `references/cluster-requirements.md`.
- **Node-group label scheme + per-microservice node-label overrides** → `references/node-groups.md`.
- **NVIDIA GPU Operator install details (driver mode, AKS quirk)** → `references/gpu-operator.md`.
- **Terraform AWS EKS specifics** → `references/terraform-aws.md`.
- **TLS, certs, custom CA, ingress controller choice** → `references/tls-and-certs.md`.
- **Air-gapped deployment full runbook** → `references/air-gapped.md`.
- **Disaster recovery / cross-region failover runbook** → `references/dr-cross-region-runbook.md` + `groundx-architecture/references/disaster-recovery.md`.
- **Common failure modes + fixes** → `references/troubleshooting.md`.
- **API calls post-install** → `groundx-api/`.
- **Marketing / positioning on why on-prem** → `product-brand-gtm/` or `master-brand-gtm/`.
