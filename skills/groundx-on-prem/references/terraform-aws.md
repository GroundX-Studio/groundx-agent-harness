# Terraform for AWS EKS

This file documents **the optional AWS-specific Terraform tooling shipped with the upstream `groundx-on-prem` repo** — the `bin/environment` helper for VPC + EKS provisioning, the `terraform/aws/{vpc,eks}/` modules, the `setup-eks` convenience script, and how the Terraform-provisioned cluster aligns with the chart's node-group expectations.

These tools are **AWS-specific and optional**. The GroundX chart is cloud-agnostic; AWS deployers can use any EKS provisioning approach. This file covers the *bundled* convenience tooling.

For the cross-environment decision (EKS vs AKS vs GKE vs OpenShift vs on-prem), route to `deployment-options.md`. For the install flow that follows cluster provisioning, route to `install-flow.md`. For cost-modelling, route to `cost-estimation.md`.

## 1. What ships under `terraform/aws/`

The upstream repo organizes AWS-specific Terraform under `terraform/aws/` plus a `bin/environment` wrapper:

```
groundx-on-prem/
├── bin/
│   └── environment              # shell wrapper around terraform
└── terraform/
    └── aws/
        ├── common.tf
        ├── env.tfvars           # generated; populated by the deployer
        ├── env.tfvars.example   # template
        ├── setup-eks            # convenience script for end-to-end EKS setup
        ├── setup-eks.command    # macOS double-click variant
        ├── variables.tf
        ├── vpc/                 # VPC + subnets module (~11 .tf files)
        │   ├── vpc.tf
        │   ├── common.tf
        │   ├── security_groups.tf
        │   ├── node_assignments.tf
        │   ├── env.auto.tfvars
        │   ├── outputs.tf
        │   ├── shared_variables.tf
        │   ├── variables.tf
        │   └── versions.tf
        └── eks/                 # EKS cluster + node groups module (~13 .tf files)
            ├── eks.tf
            ├── autoscaler.tf
            ├── ebs.tf
            ├── efs.tf
            ├── helm_release.tf
            ├── irsa.tf
            ├── node_assignments.tf
            ├── common.tf
            ├── env.auto.tfvars
            ├── outputs.tf
            ├── shared_variables.tf
            ├── variables.tf
            └── versions.tf
```

The two modules (`vpc`, `eks`) are independent. VPC is provisioned first; its outputs feed `env.tfvars` for the EKS module.

## 2. The `bin/environment` wrapper

`bin/environment` is a bash script that wraps `terraform init` / `apply` / `destroy` for the two modules. From its usage:

```sh
bin/environment [component] [options]
```

Components:
- `aws-vpc` — creates VPC + subnets for an EKS cluster.
- `eks` — creates the EKS cluster, node groups, IRSA roles, autoscaler.

Options:
- `-c` — clear (destroy) mode. Reverses operations.
- `-t` — test mode. Skips `terraform apply` / `destroy`; useful for dry-run.

Example usage:

```sh
# 1. Provision the VPC + subnets
bin/environment aws-vpc

# 2. Provision the EKS cluster (uses VPC outputs)
bin/environment eks

# Tear down (reverse order)
bin/environment eks -c
bin/environment aws-vpc -c
```

The wrapper requires `aws` CLI and `terraform` binaries on PATH, plus a working AWS authentication context (typically `aws sso login` first or assume-role via env vars).

## 3. The `setup-eks` convenience script

`terraform/aws/setup-eks` (and `setup-eks.command` for macOS) wraps the VPC + EKS workflow in a single end-to-end script. It:

1. Prompts for environment parameters (region, cluster name, instance types, GPU node count).
2. Populates `env.tfvars` automatically.
3. Runs `bin/environment aws-vpc` then `bin/environment eks`.
4. Configures `kubectl` to talk to the new cluster.

The script is convenience tooling for first-time deployers. Production deployments typically use the underlying Terraform modules directly with version-controlled tfvars.

## 4. What the EKS Terraform module provisions

From `terraform/aws/eks/`:

| File | Provisions |
| --- | --- |
| `eks.tf` | EKS cluster control plane, OIDC provider for IRSA. |
| `node_assignments.tf` | EKS managed node groups for each of the five `eyelevel-*` node-group labels (`eyelevel-cpu-only`, `eyelevel-cpu-memory`, `eyelevel-gpu-layout`, `eyelevel-gpu-ranker`, `eyelevel-gpu-summary`). Each labeled with `eyelevel_node=<value>` for the chart's nodeAffinity to match. |
| `autoscaler.tf` | Kubernetes Cluster Autoscaler — scales node groups based on Pod-pending events. Complements (doesn't replace) the chart's HPA-on-pods. |
| `ebs.tf` | EBS CSI driver + IRSA role + default `gp3` StorageClass. |
| `efs.tf` | EFS CSI driver + IRSA role + ReadWriteMany-capable StorageClass. |
| `helm_release.tf` | Optional bootstrap Helm releases (e.g., AWS Load Balancer Controller). |
| `irsa.tf` | IAM Roles for Service Accounts — IRSA roles for S3, SQS, RDS access. |
| `outputs.tf` | Cluster endpoint, kubeconfig data, node-group names. |

The node-group labeling pattern is the load-bearing piece: it produces nodes with the labels the chart's `nodeAffinity` matches. Without these labels (or without the chart's `cluster.nodeLabels` overrides), pods fail to schedule. See `node-groups.md` § 1.

## 5. Aligning Terraform with the chart's node-group labels

The chart expects node-group label values under the **key `eyelevel_node`** (not the bare `node` key). The Terraform module produces five EKS-managed node groups (`cpu_memory`, `cpu_only`, `gpu_layout`, `gpu_ranker`, `gpu_summary`) with the matching labels.

The Terraform actually splits this across two files:

- `terraform/aws/eks/eks.tf` consumes `local.node_groups` (computed from per-group `*_desired_size` / `*_max_size` / `*_min_size` locals) and passes it as `eks_managed_node_groups` to the upstream EKS module.
- `terraform/aws/eks/node_assignments.tf` resolves the per-group label values via `var.node_labels.<group>` (overridable) coalesced over `var.cluster.nodes.<group>` (defaults that match the chart's `eyelevel-*` scheme).

The sizing variables and label overrides ultimately come from `env.tfvars` (§ 8). The conceptual shape — five labeled node groups (`cpu_memory`, `cpu_only`, `gpu_layout`, `gpu_ranker`, `gpu_summary`), each with `desired/min/max` sizes, each labeled `eyelevel_node=<value>` — matches what the chart's `nodeAffinity` selectors expect.

GPU node groups also carry taints (also configured through the same Terraform path), reserving them for GroundX inference pods. The chart's tolerations match those taints, allowing inference pods to schedule on GPU nodes while keeping other workloads off the expensive GPU instances.

If the deployer wants different label values (`my-cpu-pool` instead of `eyelevel-cpu-only`), override both:
- In Terraform: change the label value in `node_assignments.tf`.
- In chart values.yaml: override `cluster.nodeLabels.cpuOnly: my-cpu-pool` to match.

See `node-groups.md` § 1.1.

## 6. IRSA — IAM Roles for Service Accounts

The EKS module (`terraform/aws/eks/`) creates these IRSA roles:

| IRSA role | Used by | Permits |
| --- | --- | --- |
| `eyelevel-s3-sqs-worker-irsa` | Chart pods with `serviceAccount.name: s3-sqs-worker` | S3 access for `file.existing.serviceType: s3`, SQS access for per-topic `type: sqs` (`irsa.tf`) |
| `AmazonEKSTFAutoscalerRole-<cluster>` (only when Terraform enables the cluster autoscaler) | Cluster Autoscaler SA in `kube-system` (installed by the same Terraform) | Node-group scaling (`autoscaler.tf`) |
| `AmazonEKSTFEBSCSIRole-<cluster>` (only with the EBS storage driver) | `ebs-csi-controller-sa` in `kube-system` | EBS volume provisioning (`ebs.tf`) |
| `AmazonEKSTFEFSCSIRole-<cluster>` (only with the EFS storage driver) | `efs-csi-controller-sa` in `kube-system` | EFS volume provisioning (`efs.tf`) |

The EKS Terraform does **not** create an external-dns / Route53 role or an AWS-Load-Balancer-Controller role. If you run either operator, create its IRSA role yourself — see § 6.1 for the external-dns / Route53 role.

**The bundled `s3-sqs-worker` policy is broad, not least-privilege.** `irsa.tf` grants `s3:*` and `sqs:*` on `Resource: *` — account-wide S3 and SQS administration. IRSA controls *which* identity the pod assumes (its ServiceAccount), not *what* that identity may do. For production, replace the bundled policy with one restricted to the exact buckets and queues the deployment uses (and, where possible, the specific actions), rather than shipping the `*:*`-on-`*` grant.

Wire the chart pods to use IRSA via:

```yaml
serviceAccount:
  name: s3-sqs-worker
```

The named ServiceAccount must be pre-created (typically by Terraform) with the right `eks.amazonaws.com/role-arn` annotation. See `credentials.md` § 9 for the credential-isolation context.

### 6.1 Automated DNS with external-dns (Route53)

By default the chart does **not** create DNS records — the install prereqs treat the ingress A/CNAME as a manual step (`install-flow.md` § 2). To have records created and updated automatically in Route53, run the `external-dns` operator and let it manage records off each ingress hostname:

1. **IAM** — the GroundX Terraform does **not** create a Route53 IRSA role, so create one yourself: an IAM role whose trust policy is the IRSA trust for the external-dns ServiceAccount (the same `sts:AssumeRoleWithWebIdentity` / OIDC-subject shape the module uses for `s3-sqs-worker` in `irsa.tf`), with the Route53 policy the external-dns AWS provider requires — `route53:ChangeResourceRecordSets` on your hosted zone plus `route53:ListHostedZones`, `route53:ListResourceRecordSets`, and `route53:ListTagsForResources` (the external-dns AWS tutorial is the authoritative source for the exact action set). Bind it to the external-dns ServiceAccount via the `eks.amazonaws.com/role-arn` annotation.
2. **Install external-dns itself** — it is a standard upstream operator (its own Helm chart / manifest), **not shipped by the GroundX chart**. Scope it to your hosted zone with `--provider=aws` and `--source=ingress`.
3. **Annotate each ingress** so external-dns picks up the hostname. Every ingress-bearing microservice already exposes `ingress.hostName` and `ingress.annotations` (`values-yaml.md` § 5.10); add the external-dns hostname annotation there:

```yaml
groundx:
  ingress:
    enabled: true
    ingressClassName: alb
    hostName: api.mycorp.example.com
    annotations:
      external-dns.alpha.kubernetes.io/hostname: api.mycorp.example.com
```

external-dns then creates and updates the Route53 record pointing at the ingress load balancer, and reconciles it as the LB address changes. Repeat the `hostName` + annotation on every ingress-bearing service you expose (`groundx` — the primary API, the one configured in the example above — plus `layout.api`, `layoutWebhook`, `ranker.api`, `summary.api`, `extract.api`, `workspace.api`, `file`).

If you do not run external-dns, DNS stays manual: create the A/CNAME records yourself after the ingress has an address (`install-flow.md` § 2).

### 6.2 Scope the cluster administrative access plane (access entries, CI deploy role, OIDC trust)

IRSA (§ 6) gives each *pod* its own **workload identity** — but not least privilege by default: the bundled `s3-sqs-worker` policy is broad (`s3:*` / `sqs:*` on `*`; see § 6), so IRSA scopes *who* the pod is, not *what* it may do. This section is a different plane: who and what may **administer** the cluster. Scope that access plane deliberately: an over-broad CI or admin role is a production-wide exposure. The harness's own Terraform builds the cluster, so this section keeps a harness-built cluster secure-by-default on the admin plane.

**Prefer EKS access entries over the legacy `aws-auth` ConfigMap**, and grant each principal a scoped access policy rather than blanket `system:masters`:

- **Deploy / CI principal** — the role that runs `helm upgrade --install` is **not** a pure namespace-scoped role: with the external-metrics adapter enabled the install creates a cluster-scoped object, and the install-flow preflight writes in other namespaces, so a `namespace: eyelevel`-only policy may not complete the install. Scope it to exactly what the install needs, still short of cluster-admin:
  - **Namespaced work (the bulk)** — an `AmazonEKSEditPolicy` (or a custom Role / RoleBinding) with an **access scope of `namespace: eyelevel`** for the workloads, Services, ConfigMaps, and Secrets the chart renders there.
  - **External-metrics adapter (`metrics.enabled: true`, required for HPA — `autoscaling.md` § 5)** — enabling it renders the `metrics` microservice, which creates both a cluster-scoped `APIService` (`v1beta1.external.metrics.k8s.io`) **and** a `Role` + `RoleBinding` in `namespace: eyelevel`. Two grants beyond the namespaced edit are then needed: a **custom ClusterRole** (never `AmazonEKSClusterAdminPolicy`) with the full helm-lifecycle verbs — `get`, `list`, `watch`, `create`, `update`, `patch`, `delete` (not `create`/`update` alone, or `helm upgrade`, rollback, and uninstall cannot manage the object) — on `apiservices.apiregistration.k8s.io`; and, in the `eyelevel` scope, those same lifecycle verbs (**no `bind`**) on `roles.rbac.authorization.k8s.io` and `rolebindings.rbac.authorization.k8s.io` — `AmazonEKSEditPolicy` maps to the built-in `edit` role, which withholds RBAC writes to prevent privilege escalation, so it cannot create these (use an `admin`-level namespaced policy instead). The `bind` verb is **not** needed here: it guards creating a binding that references a role whose permissions you don't already hold, but the metrics `Role` grants only `get`/`list`/`watch` on `deployments` and `pods` — already covered by `edit` — so the escalation check passes without it. If a future Role exceeded that, scope `bind` with `resourceNames` to the exact Role rather than granting it broadly. A ClusterRole grants nothing until it is **bound**: create the CI principal's EKS access entry with a Kubernetes group (`aws eks create-access-entry --kubernetes-groups …`) and bind the ClusterRole to that group with a `ClusterRoleBinding` whose subject is `kind: Group`. The managed EKS Access Policies are a fixed coarse set (view / edit / admin / cluster-admin) and none grants this scoped cluster-wide `apiservices` permission short of `AmazonEKSClusterAdminPolicy`, so a narrow grant needs this groups-plus-`ClusterRoleBinding` path — AWS's own guidance: "if none of the access policies meet your requirements … specify … group names … and create and manage Kubernetes RBAC objects" (*Create an access entry using Kubernetes groups*). With `metrics.enabled: false` (the default) the chart creates no cluster-scoped objects and neither grant is needed.
  - **Node labels** — `patch nodes` for the `eyelevel_node` labels (`install-flow.md` § 3.5), if this principal rather than Terraform applies them.
  - **Other namespaces** — write access in `kube-system` (the ALB-controller ServiceAccount annotation) and `nvidia-gpu-operator` (`--create-namespace` install), per the `install-flow.md` § 3.5 preflight. Grant those explicitly rather than falling back to cluster-admin.
- **Human operators** — give day-to-day users a `namespace`-scoped edit/view policy; reserve `AmazonEKSClusterAdminPolicy` for a small, named break-glass set.

**Constrain the CI deploy role's IAM and its GitHub-OIDC trust.** When CI assumes an AWS role via GitHub Actions OIDC (`credentials.md` § 12), scope both sides:

- IAM permissions: only what the deploy needs — `eks:DescribeCluster` (required by `aws eks update-kubeconfig` to reach the cluster), read the image registry, and read the secret store, never `AdministratorAccess`. The CI principal reaches the cluster by **being** the IAM identity the EKS access entry above maps, or by `sts:AssumeRole` into an IAM role that the access entry maps; you do not "assume" an access entry itself — it is a principal-to-Kubernetes mapping, not a role.
- OIDC trust subject: pin the trust-policy `token.actions.githubusercontent.com:sub` condition to a **specific repo and a protected environment** (for example `repo:my-org/my-repo:environment:production`), never a wildcard such as `repo:my-org/*`, which lets any repo in the org assume the deploy role.

**Minimize standing cluster-admins.** Treat account `:root` and any `aws-auth` `system:masters` entries as break-glass only; move routine access to scoped access entries, and periodically audit who holds cluster-admin.

The harness's Terraform creates the IRSA roles (§ 6) but does **not** create or scope the CI deploy role or the human access entries: you own that design. Authoring the specific IAM policy JSON is a cloud-provider concern (`credentials.md` § 16); this section is about *scoping* the access plane, not the policy syntax.

## 7. Storage classes

The EBS / EFS Terraform modules configure two storage classes:

- **`gp3`** (default) — EBS-backed, ReadWriteOnce. Suitable for most chart-deployed backing services (Percona, OpenSearch, Redis, MinIO).
- **`efs-sc`** — EFS-backed, ReadWriteMany. Suitable for workspace cache PVC when multi-replica access is needed.

Set in values.yaml:

```yaml
cluster:
  pvClass: gp3              # default storage class for most PVCs
  pvAccessMode: ReadWriteOnce

workspace:
  pvc:
    class: efs-sc           # override for the workspace cache when RWX is needed
    access: ReadWriteMany
```

See `workspace-service.md` § 4.3.

## 8. env.tfvars — the configuration surface

`env.tfvars.example` is the template; the deployer copies to `env.tfvars` and edits. Typical fields:

<!-- illustrative -->
```hcl
# env.tfvars
aws_region   = "us-east-2"
cluster_name = "groundx-prod"
vpc_cidr     = "10.0.0.0/16"
azs          = ["us-east-2a", "us-east-2b", "us-east-2c"]

# Node group sizing per label
node_groups = {
  cpu_only = {
    instance_types = ["m6i.xlarge"]
    min_size       = 2
    max_size       = 10
    desired_size   = 2
  }
  gpu_summary = {
    instance_types = ["g5.2xlarge"]
    min_size       = 1
    max_size       = 2
    desired_size   = 1
  }
  # ... similar for cpu-memory, gpu-layout, gpu-ranker
}
```

The actual variable names live in `terraform/aws/eks/variables.tf` and `terraform/aws/vpc/common.tf`. Diff against the example file for the canonical surface.

## 9. Day-2 — updates and tear-down

After install:

- **Cluster autoscaler** auto-scales node groups per pending-pod signals. No manual scaling needed for normal operation.
- **Helm upgrades** to the GroundX chart use the EKS cluster as-is. See `upgrades.md`.
- **Terraform-side updates** (e.g., changing node-group instance types, adding new node groups) require `bin/environment eks` re-run with the updated `env.tfvars`. Terraform plans the diff and applies.

Tear-down order: chart first (`helm uninstall groundx`), then operators (Percona, MinIO, Strimzi, etc.), then `bin/environment eks -c`, then `bin/environment aws-vpc -c`. Reverse order prevents lingering EBS volumes / ELB / IAM resources that block VPC deletion.

## 10. When not to use this tooling

These Terraform helpers are **convenience tooling**, not the canonical chart deployment path. Skip them when:

- The deployer has an existing EKS cluster they want to reuse — install the chart against it directly.
- The deployer's organization has Terraform conventions (e.g., Terragrunt, custom modules) that conflict with the bundled tooling.
- The deployer targets AKS, GKE, OpenShift, or on-prem — these Terraform modules are AWS-only.

The chart itself doesn't depend on these tools. They exist to make first-install easier for new AWS deployers; experienced operators may prefer their own provisioning approach.

## 11. Cross-field implications

| Set this... | …and this is implied or required |
| --- | --- |
| Custom node-group label values (Terraform side) | Must mirror in `cluster.nodeLabels.*` (chart values.yaml) for nodeAffinity to match. |
| `serviceAccount.name: s3-sqs-worker` | ServiceAccount must exist in the install namespace with IRSA annotation. Terraform's IRSA module typically creates this. |
| Cluster Autoscaler enabled + chart HPA enabled | Two-layer autoscaling: pods scale via HPA (chart-side), nodes scale via Cluster Autoscaler (Terraform-side). Both required for full elasticity. |
| Skipping the EFS module (only EBS) | Workspace PVC can't use `ReadWriteMany` storage class. Either keep workspace-api at `replicas.desired: 1` or add EFS. |
| Multi-region deployment | These Terraform modules are single-region. Multi-region deployments need DR-specific provisioning. See `dr-cross-region-runbook.md`. |

## 12. What this file does not cover

- **The chart itself** → see `install-flow.md` for the chart-install workflow.
- **AKS / GKE / OpenShift / on-prem provisioning** → these Terraform modules are AWS-specific. See `deployment-options.md`.
- **Generic Terraform best practices** (state management, remote state, Terragrunt) → upstream Terraform docs.
- **AWS pricing / instance selection for the chart's workloads** → `cost-estimation.md` § 4 + AWS instance pricing pages.
- **Backup / restore for the EKS-side data layer** → `dr-cross-region-runbook.md`.
- **GPU instance availability per region** → AWS docs; varies.
- **VPC peering, transit gateway, multi-account setups** → consult AWS networking docs; out of chart scope.
