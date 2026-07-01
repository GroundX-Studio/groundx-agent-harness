# Workspace Runner

The workspace runner is the **agent-facing project-workspace API** — the subsystem that backs short-lived git sessions, scaffold provisioning, in-workspace command execution, publish, and cleanup for managed customer projects. It is **6 pods** (1 API + 5 workers) reachable only through `groundx` as Workspace facade API calls. It is **not** part of the ingest pipeline. This is the subsystem Workspace-aware Harness publishing flows call into.

## 1. Marketing altitude

Workspace runners stay out of marketing content. The Studio Harness scaffold pattern is the marketing surface above this subsystem; workspace internals should not appear in marketing copy.

## 2. Product altitude

The workspace runner is what makes managed Studio Harness projects work. When a workspace-capable caller creates a new managed project, clones an existing one, runs a command inside it, publishes it, or cleans it up, the request enters through `groundx` as a Workspace facade API call and is routed to the workspace runner subsystem. The subsystem handles git operations on behalf of the caller — managing credentials, branches, commits, and pushes — so callers don't manage git themselves.

## 3. Conceptual / algorithmic altitude

Three architectural choices shape the workspace runner:

**Single ingress through `groundx`.** There is no direct external path to the workspace runner. Every workspace operation is a Workspace facade API call to `groundx`, which authenticates the workspace-capable key and forwards internally to `workspace-api`. This is an architectural invariant — the workspace runner is not exposed as its own external endpoint.

**The service manages git, not the caller.** Git credentials are owned by the service. Callers ask "publish this workspace" without holding git credentials themselves — that's the whole point of the subsystem. Customer-facing managed projects don't expose underlying git plumbing to the agents or end users.

**Stateless with shared persistence.** Every workspace runner pod is stateless. Workspace state — running sessions, cloned repos, pending commits — lives in **file storage** (Kubernetes PVC) for the file system and in **MySQL/RDS** (the shared Process Metadata DB, in dedicated workspace tables) for the structured state. Storage backings are configurable in Helm. No pod-local state is required for correctness.

## 4. System altitude

The workspace runner is **6 pods** + two stores:

```
agent caller (Studio Harness workflow, etc.) → Workspace facade API → groundx → API → workspace-api → Celery → workspace workers (5)
                                                                                                                         → file storage (PVC)
                                                                                                                         → Process Metadata DB (dedicated tables)
```

- **1 API pod** (`workspace-api`) — the internal-only ingress; receives forwarded Workspace facade calls from `groundx`.
- **5 worker pods** (`workspace-workspace`, `workspace-provision`, `workspace-command`, `workspace-publish`, `workspace-cleanup`) — Celery-coordinated workers.

For the full system topology see `overview.md` § 4.5.

## 5. Implementation altitude

### 5.1 Pods

| Pod | Runtime | Inferred role |
| --- | --- | --- |
| `workspace-api` | Python | Entry point — receives forwarded Workspace facade calls from `groundx`; spawns worker tasks |
| `workspace-workspace` | Python | Per-managed-project workspace worker |
| `workspace-provision` | Python | Provisioner |
| `workspace-command` | Python | Command execution |
| `workspace-publish` | Python | Publish (commit, push, trigger downstream CI/CD where wired) |
| `workspace-cleanup` | Python | Cleanup |

**Per-worker responsibilities here are inferred from pod names** — they have not been authoritatively confirmed against source-of-truth. Updates should be back-ported when the workspace runner is documented in source-of-truth elsewhere.

### 5.2 State

| State | Where | Notes |
| --- | --- | --- |
| File system (cloned repos, scaffold contents, working copies) | File storage — Kubernetes PVC | Storage backing is configurable in Helm |
| Workspace records, session state, project metadata | Process Metadata DB (MySQL/RDS) | Dedicated workspace tables alongside the document-pipeline tables |
| Pod-local state | None (stateless pods) | All state externalized to the stores above |

### 5.3 Git credential management

Git credentials are managed by the workspace runner service itself. Callers do not provide git credentials per-request — the subsystem is the credential boundary. This is the architectural feature that makes managed projects feel like a hosted service rather than a CI-driven git workflow.

### 5.4 Routing invariant

The workspace runner is **reachable only through `groundx`** (see `identity-and-trust.md` § 5.5 + `overview.md` § 2). There is no external ingress to `workspace-api`; all calls enter as Workspace facade requests to `groundx` and are forwarded internally. This is an architectural invariant, not a default routing.

## 6. Security / compliance altitude

The workspace runner has **no external trust-boundary crossings** beyond the Workspace facade authentication on the `groundx` ingress. Git operations against configured remotes run from inside the cluster; git credentials are held by the service. For Workspace endpoint semantics and auth see the GroundX API skill's Workspace endpoint guidance; for the broader identity / trust model see `identity-and-trust.md`.

## 7. Operations / SRE altitude

`workspace-api` is metered as **API response time** in the `metrics` pod; the 5 worker pods are metered as **Celery task back-pressure** thresholds (per `overview.md` § 4.7). Workspace operations are independent of ingest pipeline load — the workspace runner has its own scaling profile driven by managed-project session count rather than document throughput. No hosted workspace pod alert route is sourced here; do not claim one unless the GroundX partner/workspace route proves it, and do not claim the `layoutWebhook` path for workspace alerts. For the broader observability framing see `observability.md`.

## 8. Data architecture altitude

**Inputs:** Workspace facade API requests (project creation, clone, command, publish, cleanup).

**State:**

- File storage (PVC) for workspace contents — cloned repos, working copies, intermediate scaffold output.
- Process Metadata DB (MySQL/RDS, dedicated tables) for workspace records, session state, project metadata.

**Outputs:** git operations against the configured remotes (commits, pushes); responses to the Workspace facade API caller.

For canonical artifact placement see `store.md`. The workspace runner shares the underlying Process Metadata DB with the ingest pipeline but uses dedicated tables — there is no row-level overlap with document / workflow / bucket tables.

## 9. Cost / FinOps altitude

The workspace runner is CPU-only and comparatively cheap. Cost drivers:

- **Worker pod replica count** — scales with concurrent workspace sessions, not document volume.
- **File storage (PVC)** — grows with the number of active managed workspaces and their working-copy sizes; configurable in Helm. The retention policy on workspace cleanup is the main lever.
- **Outbound git network egress** — depends on remote-hosting choices and traffic patterns, not architecturally significant at this altitude.

Deployment-level cost framing is owned by `groundx-on-prem`.

## 10. What this topic does not cover

- **Workspace endpoint surface and auth model** (route shapes, deploy-config payloads, diagnostics, publish): the GroundX API skill's Workspace endpoint guidance.
- **Partner account lifecycle and credential issuance** (how partner credentials are issued, validated, scoped): outside this public architecture topic.
- **The agent-facing workflows** (clone, edit, publish, cleanup) that consume this subsystem: Studio Harness managed-project workflow guidance.
- **The Studio Harness scaffold pattern** that managed projects are built from: Harness web UI and publish guidance.
- **Per-pod-worker responsibilities, source-of-truth** — to be back-ported when documented in the source.
- **Per-deployment PVC sizing, Helm storage backing selection**: `groundx-on-prem`.
