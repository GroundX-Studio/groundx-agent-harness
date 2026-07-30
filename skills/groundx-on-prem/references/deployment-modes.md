# Deployment Modes

This file documents **the three deployment modes a GroundX install can run in** — `mode: all` (default full platform), `mode: ingest` (ingest-only, retrieval skipped), and the **workspace-enabled** axis that overlays both. Each combination has different cluster-sizing, backing-service, and trust-boundary implications.

For the field-by-field reference, route to `values-yaml.md` § 2.4. For the discovery-question framing, route to `values-authoring.md` § 3.2. For the architectural picture of which microservices run in each mode, route to `groundx-architecture/references/overview.md`.

## 1. The two-axis mode model

GroundX has two independent mode dimensions a deployer picks at install time:

```
                       workspace.enabled
                            true                 false
                  ┌─────────────────────┬────────────────────┐
                  │                     │                    │
   mode: all      │  Full + Workspace   │   Full             │
                  │  (managed UI loop)  │   (canonical)      │
                  │                     │                    │
                  ├─────────────────────┼────────────────────┤
                  │                     │                    │
   mode: ingest   │  Ingest-only +      │   Ingest-only      │
                  │  Workspace          │   (benchmarking)   │
                  │                     │                    │
                  └─────────────────────┴────────────────────┘
```

The four cells correspond to four real deployment archetypes. § 2 walks each.

## 2. The four mode combinations

### 2.1 Full platform (`mode: all`, `workspace.enabled: false`)

**The canonical deployment.** Both ingest and retrieval. All microservices render. The deployment serves both document ingestion and search / RAG queries.

| Aspect | Value |
| --- | --- |
| `mode` | `all` (or omit; `all` is the default) |
| `workspace.enabled` | `false` |
| Backing services required | All five (object store, DB, cache, OpenSearch, queue) |
| GPU node groups required | `eyelevel-gpu-layout`, `eyelevel-gpu-ranker`, `eyelevel-gpu-summary` (when `summary.api.enabled: true` + `summary.inference.enabled: true`) |
| API exposure | `groundx` (ingest + search/RAG); optionally `layoutWebhook` (for asynchronous callbacks); optionally `summary.api` |

**When to choose:**
- The deployment serves end-user search / RAG queries directly.
- The deployment is the only one in the organization (not feeding a downstream retrieval cluster).
- Default for first-time deployments.

**Example values file:** `examples/values.eks-cloud-managed.example.yaml`, `examples/values.openshift-regulated.example.yaml`, `examples/values.minikube-dev.example.yaml`, `examples/values.minimum-viable.example.yaml`.

### 2.2 Ingest-only (`mode: ingest`, `workspace.enabled: false`)

**Upstream-only ingest pipeline.** No retrieval. The deployment ingests documents, runs the layout + summary pipeline, and persists the output — but does not serve search queries directly. Useful for:

- **Benchmarking** — measure ingest throughput without retrieval traffic confounding.
- **Sizing runs** — validate cluster sizing under varied document loads.
- **Multi-deployment topologies** — an ingest-only "feeder" deployment writes to a shared retrieval cluster (or another GroundX instance) that handles search.
- **Staging environments** — ingest changes get re-tested without serving production search.

| Aspect | Value |
| --- | --- |
| `mode` | `ingest` |
| `workspace.enabled` | `false` |
| Backing services required | Four (object store, DB, cache, queue). **Retrieval DB (OpenSearch) NOT required.** |
| GPU node groups required | `eyelevel-gpu-layout`, `eyelevel-gpu-summary` (when `summary.api.enabled: true` + `summary.inference.enabled: true`). `eyelevel-gpu-ranker` not needed (ranker serves retrieval). |
| API exposure | `groundx` (ingest only); optionally `layoutWebhook` |

**What's skipped in `mode: ingest`:**
- `search.*` block can be left at defaults; OpenSearch isn't deployed or wired.
- The ranker microservices (`ranker.api`, `ranker.inference`) don't render.
- Retrieval queries return errors — the API only accepts ingest.

**Example values file:** `examples/values.ingest-only.example.yaml`.

**Cross-field implications:**
- The retrieval-side microservices (`ranker.api`, `ranker.inference`) auto-disable when `mode: ingest`. Don't explicitly set their `enabled: false`.
- `search.enabled: false` is implied; setting it has no effect when `mode: ingest`.
- HPA and metrics still apply to the ingest-side microservices.

### 2.3 Full + Workspace (`mode: all`, `workspace.enabled: true`)

**Full platform with managed-scaffold UI loop.** Same as § 2.1 plus the workspace runner subsystem for managing customer-facing UI projects (git clone, edit, publish via GitHub Actions / GitLab CI).

| Aspect | Value |
| --- | --- |
| `mode` | `all` |
| `workspace.enabled` | `true` |
| Backing services required | All five + a shared PVC for workspace data (`workspace.pvc`) |
| Storage class | `ReadWriteMany` strongly preferred for production (EFS on AWS, Azure Files on AKS) |
| API exposure | `groundx` + `workspace.api` (LoadBalancer or Ingress) |
| Outbound egress | GitHub / GitLab (for `git push` on publish) |

**Required workspace credentials:**
- `workspace.token` OR `workspace.existingSecret` with `WORKSPACE_RUNNER_TOKEN`
- For GitHub App auth: `workspace.github.{appId, installationId, privateKeyPem / privateKeySecret, secretName}`
- For GitLab token auth: `workspace.gitlab.{apiBaseUrl, token / tokenSecret / secretName}`

**When to choose:**
- The deployment serves the GroundX Studio managed-UI workflow (Partner-tier customers, managed-scaffold lifecycle).
- The deployment supports end-user-driven UI customization with publish to git.

**Example values file:** `examples/values.ingest-only.example.yaml` shows the workspace block (variant 2.4); for full+workspace, layer `workspace.enabled: true` + `workspace.*` onto `examples/values.eks-cloud-managed.example.yaml`.

For architectural depth, route to `groundx-architecture/references/workspace-architecture.md`.

### 2.4 Ingest-only + Workspace (`mode: ingest`, `workspace.enabled: true`)

**Specialty configuration.** Ingest-only pipeline + workspace runner. Used when:
- A separate cluster (or a downstream service) handles retrieval.
- The deployment is *both* a managed-UI deployment (workspace publishing customer scaffolds) *and* an ingest feeder.

`examples/values.ingest-only.example.yaml` is exactly this archetype — `mode: ingest` + extract + workspace, no retrieval.

| Aspect | Value |
| --- | --- |
| `mode` | `ingest` |
| `workspace.enabled` | `true` |
| Backing services required | Four (no retrieval DB) + workspace PVC |
| GPU node groups required | `eyelevel-gpu-layout`, optionally `eyelevel-gpu-summary` |
| API exposure | `groundx` (ingest) + `workspace.api` |

**When to choose:**
- Federated deployment topology: ingest feeders + a shared retrieval cluster.
- Partner-tier deployments where ingest and managed-UI are co-located but search is elsewhere.

## 3. Switching modes after install

Switching is supported but not trivial:

| Switch | What happens | Disruption |
| --- | --- | --- |
| `all` → `ingest` | Retrieval microservices (`ranker.*`, `search.*`) are deleted on next `helm upgrade`. OpenSearch backing service is no longer wired. In-flight search queries fail. | High. In-flight retrievals lost. Pause traffic before switching. |
| `ingest` → `all` | Retrieval microservices spin up. OpenSearch backing service must be available (Mode 1 / 2 / 3). Search queries succeed after pods are `Ready`. | Low. Search becomes available after ~minutes of pod startup. No data loss (ingest already produced retrievable artifacts). |
| `workspace.enabled: false` → `true` | Six workspace microservices spin up. PVC must be available. Git credentials must be provisioned. | Low. Workspace endpoints become available after pod startup. |
| `workspace.enabled: true` → `false` | Workspace microservices deleted. In-flight workspace operations fail. Workspace PVC remains (manual cleanup needed). | Medium. In-flight runner jobs lost. Drain workspace queue first. |

**Pattern for production-safe switching:**

1. Drain in-flight work for the affected pipeline (search queries / workspace publishes).
2. `helm upgrade --install groundx ./src/groundx -f values.<env>.yaml -f values.<env>.secret.yaml` with updated mode.
3. Wait for pods to converge (`kubectl get pods -n eyelevel` until all `Running`).
4. Smoke-test the affected pipeline before re-enabling traffic.

## 4. Cross-field implications by mode

| Mode | Cross-field implications |
| --- | --- |
| `mode: ingest` | `search.*` block can stay at chart defaults; OpenSearch deploy can be skipped (`search.enabled: false`). `ranker.*` microservices auto-disable. No retrieval-side egress. |
| `mode: ingest` + `workspace.enabled: true` | Combine the above with workspace's RWX PVC + git egress + workspace credentials. Workspace publishes operate independently of the (absent) retrieval pipeline. |
| `workspace.enabled: true` | `workspace.token` or `workspace.existingSecret` required. `workspace.pvc.{access: ReadWriteMany}` strongly preferred. NetworkPolicy must allow egress to the configured git remote. |
| `workspace.enabled: false` | GroundX Workspace facade endpoints return errors. Don't set workspace credentials; they're ignored. |
| External summary configured (via `summary.existing.serviceType` ∈ `{openai, openai-base64, azure}` OR `summary.existing.url` set) | Orthogonal to mode. The chart's `groundx.summary.create` helper returns false → `summary-api` + `summary-inference` not deployed regardless of `mode`. `eyelevel-gpu-summary` node group not needed. See `references/engines.md` § 1. |

## 5. Mode-vs-archetype mapping

The deployment archetypes in `values-authoring.md` § 4 map to mode choices as:

| Archetype | mode | workspace.enabled |
| --- | --- | --- |
| AWS-EKS-cloud-managed | `all` | per deployment |
| AKS-with-Azure-services | `all` | per deployment |
| OpenShift-FedRAMP-air-gapped | `all` | typically `false` |
| Minikube / dev | `all` (or `ingest` for benchmarking) | typically `false` |
| Ingest-only benchmarking | `ingest` | per deployment (often `true` for managed-scaffold integration testing) |

## 6. What this file does not cover

- **Field-by-field reference for `mode` and `workspace.enabled`** → `values-yaml.md` § 2.4 and § 5.6.
- **Discovery questionnaire that selects mode at install time** → `values-authoring.md` § 3.2 and § 3.6.2.
- **Architectural picture of which microservices run when** → `groundx-architecture/references/overview.md`.
- **Workspace runner architecture** → `groundx-architecture/references/workspace-architecture.md`.
- **Per-microservice resource sizing per mode** → `cluster-requirements.md` § 6 + `node-groups.md`.
- **Cost implications of mode choice** → `cost-estimation.md`.
- **Backing-service decision per mode** → `services-prereqs.md`.
