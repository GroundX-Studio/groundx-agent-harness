# Upgrades — Version-to-Version Helm Upgrade

This file documents **the `helm upgrade` workflow for the GroundX chart** — pre-upgrade checks, schema migrations, ConfigMap-driven rollouts, backing-service version coordination, and the rollback path. The chart's general upgrade philosophy is *forward-only* with explicit deployer review at each schema bump.

For chart-deployed operator versions (Percona, MinIO, Strimzi, OpenSearch, NVIDIA GPU Operator), route to `services-operators.md`. For the install-time flow that upgrades build on, route to `install-flow.md`. For air-gapped upgrades, route to `air-gapped.md` § 10.

## 1. The basic upgrade command

```sh
helm upgrade groundx ./src/groundx \
  -n eyelevel \
  -f my-values.yaml \
  -f my-secrets.yaml
```

Or in air-gapped / offline mode:

```sh
helm upgrade groundx /path/to/groundx-X.Y.Z.tgz \
  -n eyelevel \
  -f my-values.yaml \
  -f my-secrets.yaml
```

The upgrade is idempotent — Helm compares the existing release to the new chart + values, and only renders / applies the diff.

## 2. Pre-upgrade checklist

Before running `helm upgrade`:

1. **Diff the schema.** Compare `helm/values.schema.json` between the current and target chart versions:

    ```sh
    diff <(cat ./current/values.schema.json) <(cat ./target/values.schema.json)
    ```

    Look for: new `required` constraints, removed `properties`, renamed fields, tightened `additionalProperties: false` blocks. Any of these may reject your current values.yaml.

2. **Diff the per-microservice defaults.** Compare `src/groundx/values.yaml` between versions. Default replica counts, resource requests, and image tags drive the cluster's resource footprint.

3. **Render the target locally.**

    ```sh
    helm template groundx ./target/src/groundx -f my-values.yaml > rendered.target.yaml
    helm template groundx ./current/src/groundx -f my-values.yaml > rendered.current.yaml
    diff rendered.current.yaml rendered.target.yaml | less
    ```

    The diff shows every resource change the upgrade will produce. Review it.

4. **Confirm backing-service compatibility.** If the new chart version expects a newer Percona / MinIO / OpenSearch / Strimzi version, upgrade those *first* (or simultaneously) — the chart doesn't strictly enforce backing-service versions, but mismatches surface as runtime errors.

5. **Snapshot the cluster state.** Export current `values.yaml`, current MySQL data (via `kubectl exec` and `mysqldump`), OpenSearch indices (via snapshot API). Air-gapped: ensure new chart + new images are mirrored *before* the upgrade.

## 3. Schema migration patterns

The chart's schema may tighten or rename fields across versions. Common patterns:

### 3.1 A field was renamed

The chart adds a helper that reads both names with a coalesce, then removes the old name in a later version. Pattern:

- **Version N**: new field `foo` added; old field `bar` still works; helper does `dig "foo" (dig "bar" "" $in) $in`.
- **Version N+1**: `bar` schema removed (`additionalProperties: false` now rejects it). Deployers using `bar` must migrate to `foo` before upgrade.

When the schema rejects `bar`, the upgrade fails with `additional property "bar" is not allowed`. Migrate values.yaml first.

### 3.2 A field changed semantics

A field that used to default to `false` may now default to `true` (or vice versa). The chart's CHANGELOG flags these — read it before upgrade. Update values.yaml to explicitly set the field if the new default would change behaviour.

### 3.3 A new field is now required

The schema added `required: [<new-field>]` to a previously-optional block. Existing values.yaml that omits the block entirely still works (the block doesn't exist), but any partial population of the block must include the new required field.

### 3.4 An additionalProperties block is now strict

A previously-permissive block (`additionalProperties: true`) flipped to `false`. All keys must now match the declared `properties`. Often catches typos and renamed-but-not-removed fields.

The fix for all four: read the CHANGELOG, update values.yaml, render locally, then upgrade.

## 4. ConfigMap-driven rollouts

Many of the chart's Deployments include a `config-hash` annotation on the Pod template, tying the rollout to the contents of the corresponding ConfigMap:

```go-template
annotations:
  config-hash: {{ include (print $.Template.BasePath "/resources/" $mapPrefix "-config-py.yaml") $ | sha256sum }}
```

When the ConfigMap's contents change (because `values.yaml` change re-rendered the config), the annotation changes, triggering a rolling restart of the Deployment.

This means: **most `helm upgrade` operations that change runtime config automatically restart the affected pods**. No manual `kubectl rollout restart` needed.

Exceptions: changes to the `Service` resource (port, type), changes to the PVC (capacity, storageClass), changes to the StatefulSet's volumeClaimTemplates — these may not restart pods automatically. For sweeping config changes, an explicit `kubectl -n eyelevel rollout restart deployment` is the safe pattern.

## 5. Backing-service version coordination

The GroundX chart doesn't strictly couple to specific backing-service versions, but mismatches surface as runtime errors:

| Backing service | Coupling | When to upgrade |
| --- | --- | --- |
| **Cache** (Redis 7.x / Valkey) | Loose — protocol-compatible | Independently when ready |
| **MySQL** (Percona PXC 8.x) | Loose — SQL-compatible | Independently when ready; pay attention to major-version jumps (5.7 → 8.x) requiring data migration |
| **Object store** (MinIO operator + tenant) | Loose — S3-protocol-compatible | Independently |
| **Search** (OpenSearch 2.x) | Tight on the index version when migrating; loose otherwise | Coordinate with GroundX upgrades, especially across major OpenSearch versions |
| **Stream** (Strimzi-managed Kafka) | Loose — Kafka protocol-compatible | Independently; rolling upgrades supported by Strimzi |
| **NVIDIA GPU Operator** (driver + device plugin) | Tight on the kernel / runtime combo | Coordinate with K8s upgrades, not GroundX upgrades |

For canonical install commands per backing service, see `services-operators.md`.

## 6. The rollback path

If an upgrade goes wrong:

```sh
# List release history
helm history groundx -n eyelevel

# Roll back to the previous revision
helm rollback groundx <revision-number> -n eyelevel
```

Helm's rollback replays the previous chart + values + release-state. Caveats:

- **PVCs are not rolled back.** Data written during the failed upgrade stays. If schema migrations ran on MySQL or OpenSearch, those are not reverted by `helm rollback`.
- **External backing services are not rolled back.** Cloud-managed services and existing-infra databases follow their own rollback procedures.
- **ConfigMap rollback IS supported** — the previous ConfigMap content is reinstated, and the `config-hash` annotation triggers a fresh rollout.

For data-side rollback, restore from snapshots taken pre-upgrade (§ 2 step 5).

## 7. Helm dry-run before commit

To preview an upgrade without applying:

```sh
helm upgrade --dry-run groundx ./src/groundx \
  -n eyelevel \
  -f my-values.yaml
```

Helm renders the chart and runs the same client-side validation as `helm install`, but doesn't talk to the cluster. Useful for catching schema-rejection errors before the real upgrade window.

`helm template` is similar but skips even Helm-server-side validation. Use `--dry-run` for upgrade verification; use `helm template` for static rendering / diff workflows.

## 8. Zero-downtime upgrade considerations

The chart's Deployments use rolling updates by default — old pods serve while new pods come up. For zero-downtime upgrades:

- **API tier** (groundx, layout-api, summary-api, extract-api, workspace-api): handled by rolling updates. Set `replicas.desired: 2` or higher so at least one pod always serves.
- **Worker tier** (celery workers): inflight tasks may be interrupted. The chart's `terminationGracePeriodSeconds` (configurable via `<pod>.replicas.gracePeriod`) gives workers time to finish in-flight tasks.
- **Inference tier** (layout-inference, ranker-inference, summary-inference): GPU pods. Rolling updates work but require enough GPU capacity to schedule the new pod while the old still runs. With one GPU per inference pod, you need a spare GPU during the rollout, OR set `maxUnavailable: 1, maxSurge: 0` to drain-then-create (with downtime).
- **Backing services**: each operator has its own zero-downtime story. Percona PXC supports rolling restarts. Strimzi supports rolling Kafka broker upgrades. OpenSearch single-node deployments have downtime; multi-node deployments support rolling restart.

## 9. Major-version chart upgrades

When the chart version jumps (e.g., `1.x` → `2.x`), expect:

- **Breaking schema changes**. Always diff schema and update values.yaml first.
- **New required backing-service versions**. Coordinate operator upgrades.
- **Image-tag changes**. The chart's `appVersion` / `Chart.Version` drives the default image tag. Custom per-pod `image:` overrides must be updated.
- **Possibly: new CRDs the chart depends on**. Check `templates/services/` and `templates/resources/` for new CRD references.

Major-version upgrades benefit from a staged rollout: dev → staging → prod, with snapshot-based rollback at each stage.

## 10. Cross-field implications

| Set this... | …and this is implied or required |
| --- | --- |
| Skipping the schema diff before upgrade | High risk of upgrade-time rejection. Always diff. |
| Skipping the dry-run | Same risk. Always dry-run major upgrades. |
| Backing-service operators left at older versions | May produce runtime errors when the new chart version uses CRD features the operator doesn't support. Coordinate. |
| PVC-resizing during upgrade (`pvc.capacity: 50Gi` → `100Gi`) | Some storage classes support volume expansion; some don't. Verify the storage class's `allowVolumeExpansion: true` first. |
| Renaming a service (`db.serviceName: my-db`) during upgrade | Old service name is dropped; new one is created. Pods restart against the new name. Verify the operator-side cluster CR is renamed simultaneously (`services-operators.md` § 8). |
| GPU-pod inference pod count increase (`max: 1` → `max: 4`) | Need 4× the GPU node capacity. Increase node pool before the upgrade. |
| Air-gapped + upgrade | Add the mirror-and-transfer step before the helm upgrade. See `air-gapped.md` § 10. |

## 11. Verification post-upgrade

```sh
# All deployments rolled out
kubectl -n eyelevel get deployment -o wide

# All pods running and ready
kubectl -n eyelevel get pods

# No CrashLoopBackOff or ImagePullBackOff
kubectl -n eyelevel get pods | grep -E 'Crash|Image'

# Helm shows the new release as deployed
helm history groundx -n eyelevel

# Test a representative workflow end-to-end
# (e.g., POST a document via the API, confirm it ingests and is searchable)
```

If any pod is stuck `Pending` or `CrashLoopBackOff`, the standard troubleshooting flow (see `troubleshooting.md`) applies — same diagnostics, just post-upgrade context.

## 12. What this file does not cover

- **The initial install flow** → `install-flow.md`.
- **Air-gapped image staging** → `air-gapped.md` § 10.
- **Backing-service operator upgrades** → respective operator docs; see `services-operators.md` for install pointers.
- **Chart CHANGELOG / breaking-change log** → consult the chart's own `CHANGELOG.md` (when present).
- **Data-side schema migrations within MySQL or OpenSearch** → handled by the application's init job; not chart-side.
- **Major-version Kubernetes upgrades** → upstream Kubernetes docs; the chart works across recent K8s versions but coordinate carefully.
- **Cross-region DR-driven upgrades (active-passive failover patterns)** → `dr-cross-region-runbook.md` (planned).
- **Specific chart-version migration steps** → consult the chart's release notes.
