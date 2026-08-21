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

0. **Confirm this is not a downgrade — do this first.** This is the only path with a deployed version to compare against; `install-flow.md` § 3.5.1 routes every brownfield cluster here, so the check belongs at the top of this list rather than in the fresh-install flow. Using the release and namespace discovered in § 3.5.1:

    The deployed release, its namespace and its chart version all come from the cluster-wide, all-status, paginated, chart-matched `helm list -A --all` search in `install-flow.md` § 3.5.1 — reuse its complete output rather than re-querying here. (It deliberately avoids `helm get metadata`, which needs Helm 3.13 while this skill supports v3.8+.)

    Compare that `Version:` against the version you are about to install — the explicit `--version` pin when upgrading from the `groundx` repo, or `src/groundx/Chart.yaml`'s `version:` (plus the checkout's branch/commit) when upgrading from a local path, where `--version` is silently ignored. See `install-flow.md` § 4.2 for the source-dependent pin rule.

    If the target version is **older** than the deployed version, **stop** — this is a downgrade. The chart provides no downgrade path: schema changes, ConfigMap-driven rollouts and backing-service expectations are all forward-only, and `helm rollback` (§ 6) does not restore PVCs or external backing services. Do not proceed without explicit operator confirmation naming the two versions.

1. **Diff the schema.** Compare `helm/values.schema.json` between the current and target chart versions:

    ```sh
    diff <(cat ./current/values.schema.json) <(cat ./target/values.schema.json)
    ```

    Look for: new `required` constraints, removed `properties`, renamed fields, tightened `additionalProperties: false` blocks. Any of these may reject your current values.yaml.

2. **Diff the per-microservice defaults.** Compare `src/groundx/values.yaml` between versions. Default replica counts, resource requests, and image tags drive the cluster's resource footprint.

3. **Render the target locally.** **When `metrics.enabled: true` (not the chart default), both renders below write a chart-generated `metrics-tls` RSA private key to disk** — `rendered.target.yaml` and `rendered.current.yaml` are secret-bearing files, not scratch output. Before running them: gitignore both paths (or work outside the repo), treat them as secret, and delete them once the diff is reviewed. Never paste the render — or the raw diff — into chat, logs, or a PR; see `references/credentials.md` for render-output secret handling.

    ```sh
    helm template groundx ./target/src/groundx -f my-values.yaml > rendered.target.yaml
    helm template groundx ./current/src/groundx -f my-values.yaml > rendered.current.yaml
    diff rendered.current.yaml rendered.target.yaml | less
    ```

    The diff shows every resource change the upgrade will produce. Review it, then remove both files:

    ```sh
    rm -f rendered.current.yaml rendered.target.yaml
    ```

    **Make the diff deterministic first.** When `metrics.enabled: true`, the chart calls `genCA`/`genSignedCert` on every *local* render (`helm template` is client-side, so its `lookup` of an existing Secret always misses), producing fresh key material each time. Two renders of an identical chart therefore differ, and the `metrics-tls` Secret shows as changed on every upgrade diff — noise that can hide a real change. With `metrics.enabled: false` — the default — no `metrics-tls` Secret is rendered at all and the diff is already deterministic.

    Two ways to make it deterministic when metrics *is* enabled. The first is to exclude the Secret's whole YAML document before comparing:

    ```sh
    # Drop the "metrics-tls" Secret document — and only that document — from a rendered stream.
    # Must be document-level: the Deployment references metrics-tls by name in its volumes, and
    # a line-oriented filter either leaves the key behind or deletes documents you need.
    drop_metrics_tls() {
      awk '
        function flush() {
          if (n > 0 && !(isSecret && hasName)) for (i = 1; i <= n; i++) print buf[i]
          n = 0; isSecret = 0; hasName = 0
        }
        /^---[[:space:]]*$/                                           { flush(); buf[++n] = $0; next }
        /^kind:[[:space:]]*Secret[[:space:]]*$/                       { isSecret = 1 }
        /^[[:space:]]+name:[[:space:]]*"?metrics-tls"?[[:space:]]*$/  { hasName = 1 }
                                                                      { buf[++n] = $0 }
        END { flush() }
      ' "$1"
    }

    drop_metrics_tls rendered.current.yaml
    ```

    Then compare the filtered streams: `diff <(drop_metrics_tls rendered.current.yaml) <(drop_metrics_tls rendered.target.yaml)`. Only `awk` is required, so this works on an air-gapped host with no extra tooling.

    **Do not reach for a line-oriented filter here.** `grep -v -A20 'name: "metrics-tls"'` looks like it drops the match and the twenty lines after it; it removes nothing at all. `-v` selects every *non*-matching line, and `-A20` then prints twenty lines of trailing *context* after those selected lines — which re-admits the Secret, `tls.key` included. `-A` only ever adds lines to output. `scripts/tests/test-doc-shell-commands.mjs` executes the filter published above against a fixture render and asserts the Secret document and `tls.key` are gone while every unrelated document survives.

    The second way is to set **`metrics.useExisting: true`** in the values used for both renders — client-side this suppresses the generated key material (the `metrics-tls` Secret renders with an empty `data:` block, identically every time), making the diff deterministic.

    Use `metrics.useExisting: true` only when an existing `metrics-tls` Secret is actually present in the target namespace. It does **not** switch to an external collector or skip the metrics microservice: the Deployment, Service, and APIService still render. For an offline diff, it makes the Secret data empty because `lookup` cannot see the cluster; prefer the exclusion filter above so the diff does not depend on that cluster-only lookup behavior.

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

**The rendered output can be secret-bearing.** When `metrics.enabled: true` (not the chart default), both `helm upgrade --dry-run` and `helm template` render the chart's generated `metrics-tls` RSA private key in cleartext, regardless of which credential pattern the input values use. Never paste raw render output into chat, logs, or a PR — redact the Secret `data`/`stringData` fields or save the full render to a local gitignored file treated as secret; see `references/credentials.md` for the same handling applied to the secret companion file.

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
- **Cross-region DR-driven upgrades (active-passive failover patterns)** → `dr-cross-region-runbook.md`.
- **Specific chart-version migration steps** → consult the chart's release notes.
