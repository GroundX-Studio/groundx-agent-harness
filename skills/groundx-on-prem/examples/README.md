# GroundX On-Prem Example values.yaml Files

This directory contains **sanitized starter values.yaml files** for the most common GroundX deployment archetypes. Each file is heavily annotated with inline comments explaining what to change for a real deployment.

These are not customer-specific configurations — every endpoint, credential, region, and bucket name is a placeholder. Replace every `<placeholder>` before installing.

## When to use which example

Match your deployment to the archetype in `references/values-authoring.md` § 4 first. The mapping:

| Archetype | Example file |
| --- | --- |
| AWS-EKS-cloud-managed (S3 / RDS / ElastiCache / SQS / AWS OpenSearch managed) | `values.eks-cloud-managed.example.yaml` |
| AKS-with-Azure-services (Azure Database for MySQL, Azure Cache for Redis, MinIO bundled or Azure Blob) | `values.aks-azure.example.yaml` |
| OpenShift-FedRAMP-air-gapped (Chainguard images, Mode 2 backing services, custom CA, no cloud egress) | `values.openshift-regulated.example.yaml` |
| Minikube / single-node dev | `values.minikube-dev.example.yaml` |
| Ingest-only benchmarking | `values.ingest-only.example.yaml` |
| Smallest working config (every backing service chart-deployed, no opt-in features) | `values.minimum-viable.example.yaml` |

For credentials and TLS / DNS / ingress prereqs, see:

- `values.secret.example.yaml` — sanitized companion file for the `groundx-secret` prereq chart.
- `values.storageclass.efs.example.yaml` — values for the `groundx-storageclass` prereq chart (EFS-backed, `ReadWriteMany`).
- `values.storageclass.ebs.example.yaml` — values for the `groundx-storageclass` prereq chart (EBS-backed, `ReadWriteOnce`).

## Workflow

The recommended sequence:

1. Run the discovery questionnaire in `references/values-authoring.md` § 3. Pin every answer.
2. Pick the matching example file from this directory.
3. Copy to a real path (e.g., `values.prod.yaml`).
4. Replace every `<placeholder>`. Remove fields you don't need; the chart defaults will fill in.
5. Move all credentials into `values.<env>.secret.yaml` (use `values.secret.example.yaml` as the starting shape) — or install them via the `groundx-secret` prereq chart and reference via `cluster.secrets: [<name>]`.
6. Validate with `helm template <release-name> ./src/groundx -n eyelevel -f values.prod.yaml -f values.prod.secret.yaml | head -200` before installing.
7. Install per `references/install-flow.md` § 4.

## Schema validation

These example files are **override files** — they layer on top of the chart's own `src/groundx/values.yaml` (which supplies every required field). The `values.schema.json` validator runs against the **merged** result, not each `-f` file individually.

In other words: don't try to validate an example file alone — it will report many "required property" errors because it intentionally omits fields the chart default provides. The way helm uses these files, those errors don't surface.

To validate the merged result before installing:

```sh
helm template <release> ./src/groundx -n eyelevel \
  -f values.prod.yaml -f values.prod.secret.yaml \
  --debug 2>&1 | head -50
```

If the schema is violated, helm prints a `values don't meet the specifications of the schema(s)` error with the offending path.

## Conventions

- Every `<placeholder>` is angle-bracketed and must be replaced.
- Every credential field appears in `values.secret.example.yaml` (or in the secret-referenced Kubernetes Secret), not in the main yaml. Inline credentials in the main yaml are shown only in `values.minikube-dev.example.yaml` (dev-only convention).
- Every example assumes the three prereq charts (`groundx-storageclass`, `groundx-secret`, `groundx-service-account`) are installed before the main `groundx` chart — see `references/install-flow.md` § 4.4.
- For backing-service mode definitions (existing customer-managed / chart-deployed dedicated / cloud-managed equivalent), see `references/services-prereqs.md` § 2.
- For the field shape of any field in these examples, see `references/values-yaml.md`.

## What this directory does not cover

- Field-by-field reference → `references/values-yaml.md`.
- Discovery questionnaire and decision logic → `references/values-authoring.md`.
- Install ordering → `references/install-flow.md`.
- Backing-service prerequisites → `references/services-prereqs.md`.
- Cluster prerequisites (chip arch, GPU operator, namespace, PV class) → `references/cluster-requirements.md`.
- Air-gapped image mirroring → `references/air-gapped.md`.
- Cost estimation → `references/cost-estimation.md`.
