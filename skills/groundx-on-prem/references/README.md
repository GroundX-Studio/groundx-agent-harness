# GroundX On-Prem Reference Index

Use this index when the public GroundX Agent Harness is installed and the work
involves deploying, configuring, scaling, monitoring, upgrading, or troubleshooting
GroundX on Kubernetes.

## Fast Path

1. Start in `../SKILL.md` for the public routing contract.
2. Pick the smallest reference below.
3. For values.yaml authoring, read `values-authoring.md` before emitting config.
4. Keep customer-specific values, secrets, and environment details out of tracked files.

## Reference Map

| Need | Read |
| --- | --- |
| What GroundX is at deploy time | `what-it-is.md`, `architecture.md` |
| Cluster sizing and node groups | `cluster-requirements.md`, `node-groups.md` |
| Supporting services | `services-prereqs.md`, `services-operators.md`, `service-substitution.md` |
| values.yaml authoring | `values-authoring.md`, `values-yaml.md` |
| Install flow | `install-flow.md` |
| Deployment modes | `deployment-modes.md` |
| Summary engine selection | `engines.md` |
| TLS and certificates | `tls-and-certs.md` |
| OCR mode | `ocr-mode.md` |
| Credentials and placeholders | `credentials.md`, `license-and-admin.md` |
| Image variants | `image-variants.md` |
| Troubleshooting and operations | `troubleshooting.md`, `autoscaling.md`, `monitoring.md`, `upgrades.md` |
| GPUs and OpenShift | `gpu-operator.md`, `openshift.md` |
| Air-gapped installs | `air-gapped.md` |
| Cost and deployment tradeoffs | `cost-estimation.md`, `deployment-options.md` |

## Deferrals

| Intent | Start with |
| --- | --- |
| Architecture, pipeline, trust model, or data flow | `groundx-architecture` |
| Customer API behavior after install | `groundx-api` |
| Schema-first extraction workflow authoring | `groundx-extraction-workflows` |
| Product or company messaging | `product-brand-gtm` or `master-brand-gtm` |

This public bundle intentionally omits internal managed-project publishing and
partner-lifecycle surfaces. If the task depends on those internal operations, tell
the user the public harness does not include them.
