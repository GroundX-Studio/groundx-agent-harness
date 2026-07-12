# Workspace Service — Optional Managed-Project Runner

This file documents **the optional `workspace` service family** the GroundX Helm chart deploys when Agent Harness publishing is in scope — what it is, how to enable it, the credential and storage surfaces it exposes, the Python-microservice deployment pattern it follows, and the failure modes deployers should plan for.

For the Workspace API endpoints that drive the workspace runner from outside the cluster,
route to the `groundx-api` skill's Workspace endpoint reference. For Partner account or
customer/resource lifecycle behavior, route to Partner API guidance when available. For the
architectural picture of where workspace sits, route to
`groundx-architecture/references/workspace-architecture.md`. For the credential mechanics
around `workspace.token`, route to `credentials.md` § 9. For the schema field-by-field,
route to `values-yaml.md`.

## 1. What it is

The workspace runner is an **internal-only** service family that provisions, edits, and publishes managed code projects on behalf of GroundX Agent Harness agents. Agents call the GroundX API Workspace facade; the GroundX API service calls the workspace runner; the runner owns the actual managed-repository operations.

The runner is **disabled by default**. The chart's `groundx.workspace.create` helper (`_helpers/app/workspace.tpl:10–22`) returns `false` unless the deployer explicitly sets `workspace.enabled: true` and supplies either `workspace.token` or `workspace.existingSecret`. If `workspace.enabled: true` is set without one of those secret sources, the chart hard-fails at `helm install` with the message `"workspace requires workspace.token or workspace.existingSecret when enabled"` (`_helpers/app/workspace.tpl:15`).

Enable the runner when:

- The deployment exposes the Workspace API to agents that need to materialize, edit, build, or publish managed code projects.
- Agent Harness managed-project publishing (create UI / clone repo / publish) is in use.

Skip it when:

- The deployment only handles ingest + search + RAG. There's no Agent Harness use case.
- The Partner API is exposed but only for customer / project / bucket lifecycle (no managed-project provisioning).

## 2. Subsystem layout

The workspace family ships as **6 deployments** under the same Python-microservice deployment pattern as `extract.api`, `extract.download`, etc.:

| Component | Schema block | Pod role |
| --- | --- | --- |
| API | `workspace.api` | Gunicorn HTTP API the GroundX API Workspace facade routes to. Single ingress for runner operations. |
| Worker — provision | `workspace.provision` | Celery worker handling managed-repo creation. |
| Worker — workspace | `workspace.workspace` | Celery worker handling short-lived git sessions (clone / read / write / patch) — same name as the parent block, distinct field. |
| Worker — command | `workspace.command` | Celery worker handling server-side command execution (`go`, `npm`, `pytest`, `python`, `node`, `git` by default — see § 4.1). |
| Worker — publish | `workspace.publish` | Celery worker handling publish operations against the configured Git provider. |
| Worker — cleanup | `workspace.cleanup` | Celery worker handling workspace cleanup and lifecycle. |

All five workers are rendered by the shared `templates/app/celery.yaml` loop, iterating over `groundx.workspace.{cleanup,command,provision,publish,workspace}` services. The API is rendered by the shared gunicorn deployment template. Each component has independent `replicas`, `resources`, `node`, `serviceAccount`, and pod-metadata surfaces.

The subsystem-shared knobs at `workspace.*` (top-level — not under one of the worker blocks) cover credentials, the cache PVC, the allowed-commands allowlist, the celery broker URL, the git-provider configuration, and the managed-repo defaults.

## 3. Bootstrap minimum

A bare-minimum `workspace:` block to enable the runner:

```yaml
workspace:
  enabled: true
  token: "<long-random-shared-secret>"
```

That's enough to enable all six deployments. The `workspace.token` is the shared secret the GroundX API service uses to authenticate to the workspace runner. The chart renders it into:

1. **The generated GroundX config.yaml** as `workspace.token` (consumed by the GroundX API service for outbound calls to the runner).
2. **The runner's `config.py`** as `runner_token` (consumed inside the workspace pods to validate inbound requests).
3. **A `workspace-secret` Kubernetes secret** with `WORKSPACE_RUNNER_TOKEN` as the env-var fallback (mounted into both the GroundX API service and the workspace pods).

For production, prefer `workspace.existingSecret` over `workspace.token`:

```yaml
workspace:
  enabled: true
  existingSecret: "my-workspace-secret"   # must contain WORKSPACE_RUNNER_TOKEN
```

When `existingSecret` is set, the config files render with an empty token value — the runtime resolves it from the `WORKSPACE_RUNNER_TOKEN` environment variable, which is mounted from the deployer-managed secret.

The internal runner URL is rendered into the GroundX `config.yaml` as `workspace.baseURL` (NOT stored as a secret) - the GroundX API service resolves the runner via in-cluster DNS at `workspace-api.{namespace}.svc.cluster.local`.

## 4. Configuration surfaces

### 4.1 Allowed commands

```yaml
workspace:
  allowedCommands: "go,npm,pytest,python,node,git"   # chart default
```

Comma-separated allowlist of executables the runner's `command` worker may invoke. Default matches the most common Agent Harness build / test / publish flows. Restrict for hardened deployments (e.g., `"git"` only) or broaden for custom workflows.

### 4.2 Celery broker

The workspace family runs its own Celery setup, distinct from the main pipeline's Celery topology. Defaults route to the chart's main cache (Redis / Valkey):

```yaml
workspace:
  # Chart defaults (from _helpers/app/workspace.tpl):
  # celeryBrokerUrl: <cache.scheme>://<cache.addr>:<cache.port>/0   (e.g., redis://cache.eyelevel.svc.cluster.local:6379/0 or rediss://… when TLS)
  # celeryResultBackend: <cache.scheme>://<cache.addr>:<cache.port>/0   (same fallback shape as broker)
  # celeryGlobalKeyprefix: "{workspace}"
  # celerySoftTimeLimitSeconds: 900
  # celeryTaskAlwaysEager: false
  # commandTimeoutSeconds: 300
  # mysqlConnectTimeoutSeconds: 10
```

Override to point at an external Celery broker if the deployer wants the workspace runner to use a separate queue infrastructure.

### 4.3 Workspace cache PVC

The workspace runner uses a server-side checkout cache for the secondary file API's reads / writes / patches / commands / diffs. The chart **always** renders this as a `PersistentVolumeClaim` — there's no `emptyDir` fallback in the chart code. The PVC is materialized by the chart (`_helpers/elements/pvc.tpl` via `groundx.renderPVC`) and mounted into the workspace-api pod (`_helpers/app/workspace.tpl:274–279` builds the `workspaceVolume` volume reference).

The chart-default PVC (`_helpers/app/workspace.tpl:262–272`):

| Field | Default | Override surface |
| --- | --- | --- |
| `name` | `{workspace.serviceName}-data` (e.g., `workspace-data`) | `workspace.pvc.name` |
| `class` | `cluster.pvClass` | `workspace.pvc.class` |
| `access` | `cluster.pvAccessMode` | `workspace.pvc.access` |
| `capacity` | `20Gi` | `workspace.pvc.capacity` |

Note: the chart **ignores** a `workspace.pvc.enabled` field — `pvc.enabled` is explicitly `omit`ed at `_helpers/app/workspace.tpl:264`. Setting it has no effect on whether the PVC is created (it always is, when workspace is enabled). The chart relies on the cluster's default `StorageClass` (or whatever `cluster.pvClass` points at) to provision the underlying volume. Git remains the source of truth for managed-project content; the PVC just caches working-tree state for the secondary file API.

To override the cache PVC shape:

```yaml
workspace:
  pvc:
    access: ReadWriteMany       # prefer RWM when multiple workspace pods share the cache
    capacity: 25Gi
    class: efs-sc               # storage class supporting the chosen access mode
    name: workspace-data
```

When `pvc.access` is `ReadWriteMany`, the cache is shared across all workspace pods (recommended for multi-replica deployments). When `pvc.access` is `ReadWriteOnce`, the workspace-api must remain at `replicas: 1`.

The `workspaceMinFreeBytes` and `workspaceMinFreePercent` knobs (also under `workspace.*`) gate cache eviction at runtime.

### 4.4 Managed-repo defaults

```yaml
workspace:
  managedRepoNamePrefix: "studio-harness"   # prefix applied to auto-generated managed repos
  managedRepoOwner: "GroundX-Studio"        # GitHub org / GitLab group that owns managed repos
  managedRepoVisibility: "private"          # one of: private | public
  gitProvider: "github"                     # schema enum: github | gitlab
```

Combined with the credentials block (§ 5), these control where and how managed projects are created.

## 5. Git provider credentials

### 5.1 GitHub (default)

The chart's preferred GitHub auth path is **GitHub App** credentials. Production deployments should use `privateKeySecret` (existing-secret reference); lower environments may use `privateKeyPem` (inline string) for quick setup.

```yaml
workspace:
  gitProvider: github
  github:
    appId: "<github-app-id>"
    installationId: "<installation-id>"
    apiBaseUrl: "https://api.github.com"          # or GHES base URL
    tokenTtlSeconds: 3600
    privateKeySecret:
      name: workspace-github-app                  # secret in the install namespace
      key: github-app-private-key.pem
```

The chart mounts the named secret only into the workspace API and worker pods, at `/var/run/secrets/workspace/github/private-key.pem`. **GitHub credentials are not mounted into the GroundX API service** - the GroundX API Workspace facade delegates managed-repo operations to the workspace runner.

For local / lower-environment testing, `workspace.github.privateKeyPem` accepts the PEM string inline. The chart materializes a `workspace-github-secret` carrying it as `GITHUB_APP_PRIVATE_KEY_PEM` and mounts only into the workspace pods. **Do not commit a real PEM to values.yaml** — see `credentials.md` § 4 for the layered values pattern.

### 5.2 GitLab

```yaml
workspace:
  gitProvider: gitlab  # override (chart default is github)
  gitlab:
    apiBaseUrl: "https://gitlab.example.com/api/v4"   # or gitlab.com
    tokenSecret:
      name: workspace-gitlab
      key: gitlab-token
    # Or inline (lower-environment only):
    # token: <gitlab-pat>
```

Same isolation pattern as GitHub: secret mounted only into workspace pods.

### 5.3 Publish — dry-run by default

```yaml
workspace:
  publishDryRun: true              # chart default
  publishGithubWorkflowId: deploy.yml   # chart default; override to your managed-repo's workflow file
```

`publishDryRun: true` makes the `publish` worker log the action it *would* take and exit successfully without invoking the provider. Set to `false` only when:

1. Provider credentials are fully configured.
2. The deployer has confirmed the publish workflow / pipeline exists in the target managed-repo template.
3. There is operational coverage for the side effects (commits to managed repos, triggered CI, deployments).

## 6. Storage and data model

The workspace runner persists **project metadata and operation state in MySQL** — the same database the rest of GroundX uses (`db.*` configuration applies). The workspace runner connects via the shared MySQL helpers with `mysqlConnectTimeoutSeconds` (default 10) controlling connect-time tolerance.

**Operation state — what's in MySQL:**
- Managed project records (owner, name, provider, creation timestamp).
- Operation history (provision / publish / cleanup events).
- Active short-lived git session metadata.

**Operation state — what's in Git:**
- Source code, branches, commits, the actual managed-project content.

The workspace runner explicitly does **not** depend on the GroundX file store. Workspace artifacts (cloned repos, command outputs, diffs) are not part of the document file store. Cache loss in `/tmp/workspaces` (or the PVC) is recoverable from Git.

## 7. Internal-only — not externally reachable

The workspace API is **intended for in-cluster traffic only**. The GroundX API Workspace facade is the single external entry point that routes to the workspace runner. This is an architectural invariant - see `groundx-architecture/references/identity-and-trust.md` § 6 (workspace runner trust boundary).

The chart's `workspace.api.isInternal` field defaults to `true` (`_helpers/app/workspace-api.tpl:214`), and the workspace API ingress block under `workspace.api.ingress` exists in the schema for clusters that need a cluster-edge ingress (e.g., a service mesh sidecar requirement). A deployer *can* override `isInternal: false` and enable the ingress, but doing so contradicts the trust-boundary design - the workspace runner should be reachable only via the GroundX API Workspace facade.

## 8. Autoscaling

Workspace components use the same external-metrics autoscaling pattern as the rest of GroundX. To enable:

```yaml
cluster:
  hpa: true
metrics:
  enabled: true

workspace:
  api:
    replicas:
      desired: 1
      max: 10
      min: 1
      hpa: true
      threshold: 4000               # default for workspace-api:api metric
      throughput: 50000             # default for workspace-api:throughput metric
  command:
    replicas:
      desired: 1
      max: 8
      min: 1
      hpa: true
      threshold: 10                 # default for workspace-command:task (queue message backlog)
      throughput: 9000              # chart-default worker throughput (tokens/min per worker per thread)
  # ...similar for provision, publish, cleanup, workspace workers
```

Per-worker HPAs emit `workspace-<worker>:task` queue-depth metrics. Chart-defaults for the five workspace workers (`_helpers/app/workspace-{cleanup,command,provision,publish,workspace}.tpl:32–43`): **threshold 10** (queue message backlog), **target 1** (fraction of threshold the HPA aims for), **throughput 9000** (tokens/min per worker per thread). The API has materially higher defaults — threshold 4000 and throughput 50000 — because it serves request-time traffic, not queue work. Per-component overrides keep custom worker queue names in values (so the HPA and metrics-server config stay in sync — do not edit templates).

For the full autoscaling story, route to `autoscaling.md` (planned).

## 9. Disabling — turning off the runner cleanly

Set `workspace.enabled: false` (or omit the block entirely). The chart skips rendering all 6 deployments, the workspace-related ConfigMaps, the workspace Secret, and the workspace-data PVC. The rendered GroundX `config.yaml` has no `workspace:` block. The GroundX API Workspace facade endpoints respond with "workspace not enabled" errors at runtime.

If the workspace runner was previously enabled and the deployer disables it, the managed-project records in MySQL are not automatically deleted — they remain in the schema. Manual cleanup (or a one-off `helm hook` post-disable migration) is required if those records need to be purged.

## 10. Cross-field implications

| Set this... | …and this is implied or required |
| --- | --- |
| `workspace.enabled: true` without `workspace.token` and without `workspace.existingSecret` | The chart hard-fails at `helm install` (`_helpers/app/workspace.tpl:15`). Always pair `enabled: true` with one of the two secret sources. |
| `workspace.gitProvider: github` | `workspace.github.{appId, installationId, privateKeySecret OR privateKeyPem}` must be set. The chart doesn't enforce this at template-render time, but the runner fails at startup without them. |
| `workspace.gitProvider: gitlab` | `workspace.gitlab.{apiBaseUrl, tokenSecret OR token}` must be set. Same runtime check, not template check. |
| `workspace.publishDryRun: false` | Provider credentials must work for real, and the deployer is signing off on the side effects (real commits, real CI). Don't flip this in production without testing first in a separate environment. |
| `workspace.pvc.access: ReadWriteOnce` (or unset, inheriting `cluster.pvAccessMode: ReadWriteOnce`) | Multiple workspace-api replicas cannot share the cache. Keep `workspace.api.replicas.desired: 1` (and `max: 1`) or override `workspace.pvc.access: ReadWriteMany` and supply a matching storage class. |
| `workspace.api.ingress.enabled: true` | The workspace runner exposes a cluster-edge ingress. The chart's `workspace.api.isInternal` defaults to `true` and the architectural intent is internal-only - any ingress should restrict to in-cluster / mesh traffic, not external clients. The runner is reachable from outside only through the GroundX API Workspace facade. |

## 11. Verification — confirming the runner is healthy

After install with `workspace.enabled: true`:

```sh
kubectl -n eyelevel get pods -l app=workspace-api
kubectl -n eyelevel get pods -l app=workspace-cleanup
kubectl -n eyelevel get pods -l app=workspace-command
kubectl -n eyelevel get pods -l app=workspace-provision
kubectl -n eyelevel get pods -l app=workspace-publish
kubectl -n eyelevel get pods -l app=workspace-workspace
```

All 6 deployments should have `READY 1/1` (or higher under HPA). For end-to-end smoke tests, the chart ships `.build/bin/smoke-workspace-runner.sh` plus targeted tests at `.build/bin/workspace-runner-git-e2e.sh` and `workspace-runner-file-api-e2e.sh`. Run these from a workstation with kubectl access to verify the API, workers, cluster DNS, health endpoint, internal `/storage` status endpoint, and GroundX API Workspace facade runner URL wiring.

## 12. What this file does not cover

- **Workspace API endpoints driving the runner** → the GroundX API skill's Workspace endpoint guidance.
- **Agent Harness publish workflow that consumes the runner** → Agent Harness publish guidance.
- **Architectural picture of the workspace runner** → `groundx-architecture/references/workspace-architecture.md`.
- **`workspace.token` / `WORKSPACE_RUNNER_TOKEN` credential mechanics** → `credentials.md` § 9.
- **Field-by-field schema for `workspace.*`** → `values-yaml.md`.
- **Discovery questionnaire for workspace at install time** → `values-authoring.md`.
- **Operator dependencies (no operator required for workspace itself; depends on MySQL, Redis, and the chart's standard backing services)** → `services-operators.md`.
- **HPA / metrics-server config** → `autoscaling.md` (planned).
- **TLS / certs for the internal workspace API** → `tls-and-certs.md`.
- **Backup / disaster-recovery for workspace records in MySQL** → `groundx-architecture/references/disaster-recovery.md`.
