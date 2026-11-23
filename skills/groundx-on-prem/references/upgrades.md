# Upgrades — Version-to-Version Helm Upgrade

This file documents **the `helm upgrade` workflow for the GroundX chart** — pre-upgrade checks, schema migrations, hash-annotation-driven rollouts, backing-service version coordination, and the rollback path. The chart's general upgrade philosophy is *forward-only* with explicit deployer review at each schema bump.

For chart-deployed operator and release versions (Percona, MinIO AIStor, Strimzi, NVIDIA GPU Operator, and the OpenSearch Helm release), route to `services-operators.md`. For the install-time flow that upgrades build on, route to `install-flow.md`. For air-gapped upgrades, route to `air-gapped.md` § 10.

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

    **Do not reach for a line-oriented filter here.** `grep -v -A20 'name: "metrics-tls"'` looks like it drops the match and the twenty lines after it; it removes nothing at all. `-v` selects every *non*-matching line, and `-A20` then prints twenty lines of trailing *context* after those selected lines — which re-admits the Secret, `tls.key` included. `-A` only ever adds lines to output. The filter published above is verified against a fixture render: the Secret document and `tls.key` are removed while every unrelated document survives.

    The second way is to set **`metrics.useExisting: true`** in the values used for both renders — client-side this suppresses the generated key material (the `metrics-tls` Secret renders with an empty `data:` block, identically every time), making the diff deterministic.

    Use `metrics.useExisting: true` only when an existing `metrics-tls` Secret is actually present in the target namespace. It does **not** switch to an external collector or skip the metrics microservice: the Deployment, Service, and APIService still render. For an offline diff, it makes the Secret data empty because `lookup` cannot see the cluster; prefer the exclusion filter above so the diff does not depend on that cluster-only lookup behavior.

4. **Confirm backing-service compatibility.** If the new chart version expects a newer Percona / MinIO / OpenSearch / Strimzi version, upgrade those *first* (or simultaneously) — the chart doesn't strictly enforce backing-service versions, but mismatches surface as runtime errors.

5. **Snapshot the cluster state.** Export current `values.yaml`, current MySQL data (via `kubectl exec` and `mysqldump`), OpenSearch indices (via snapshot API). Air-gapped: ensure new chart + new images are mirrored *before* the upgrade.

6. **Upgrading to chart 0.2.8: rename object keys that start with `/`.** This applies only to a store connected as `file.existing.serviceType: minio` that is not MinIO or AIStor and keeps a leading `/` in object keys. MinIO and AIStor drop the leading `/` when they store an object, and AWS S3 (`serviceType: s3`) is not affected. In chart 0.2.8, the `groundx`, `upload`, `pre-process`, `process`, `queue`, and `summary-client` services remove the leading `/` from every key and prefix, so they no longer find objects stored with it. Follow the on-prem migration guide section [Object Keys That Start with a Slash](https://github.com/eyelevelai/groundx-on-prem/blob/53cf055e5437b8e619b0f4a2f2e27459a922eee2/docs/storage/minio-migration.md#object-keys-that-start-with-a-slash), which holds the commands, in its order: stop uploads and wait until no documents are still processing, so that 0.2.7 services write no new keys; rename the keys; upgrade GroundX straight after the rename; then, before resuming uploads, list the keys again and rename any new ones the same way. An object over 5 GB stops the guide's rename loop and needs the guide's copy-in-parts step, for the rename and for a rollback. Keep every list of renamed keys for a rollback (§ 6). GroundX ran these commands against S4 on 2026-10-15 and 2026-10-16, including an object over 5 GB copied with `aws s3 cp` and the rollback's reverse rename; every object kept its content.

7. **Plan the database migration Job.** On published charts 0.2.7 to 0.2.9 every upgrade runs a migration Job with a fixed deadline, and Argo CD never runs it. Follow § 2.2 before the upgrade window, and § 2.3 on a later chart.

### 2.1 Certificate verification and private CAs (0.2.8 chart line)

GroundX Go service images that include the GX-130 change verify the TLS certificate of every HTTPS and Redis TLS endpoint they call. Before upgrading to a chart that runs those images, check each endpoint:

| Endpoint | Action |
| --- | --- |
| Bundled in-chart Redis and MinIO | None. The chart connects to them without TLS inside the cluster. |
| External Redis without TLS (`cache.existing.ssl` false or unset) | None. No TLS options are applied to a plain `redis://` connection. |
| External Redis with TLS (`cache.existing.ssl: true`) signed by a private or self-signed CA | The `ai-server` layout, ranker and summary services, and the `workspace-*` pods when the selected workspace runner image verifies Redis certificates, fail to connect with `certificate verify failed` until you supply the CA (steps below). A certificate that does not cover the configured hostname fails the same way, and a CA does not fix it: the endpoint owner must reissue the certificate. No setting skips the check. |
| Ranker-only Redis with TLS (`ranker.cache.ssl: true`) signed by a private or self-signed CA | The `ai-server` ranker services fail to connect with `certificate verify failed` until you supply the CA (steps below), and a certificate that does not cover the configured hostname fails the same way. No setting skips the check. |
| Separate metrics Redis with TLS (`cache.metrics.existing.ssl: true`) signed by a private or self-signed CA | The `ai-server` status client fails with `certificate verify failed` and the layout, ranker and summary inference pods go unready until you supply the CA (steps below). |
| External services with public-CA certificates (S3 and public LLM APIs) | None. The image's CA bundle already trusts them. |
| External Redis on ElastiCache without cluster mode (`cache.existing.isCluster: false`) | Verification against ElastiCache was not tested in either mode. Run a connection test before upgrading (`tls-and-certs.md` § 4.3). |
| External Redis in cluster mode (any `cache.existing` without `isCluster: false`), including ElastiCache | The cluster must announce node endpoints its certificate covers (`tls-and-certs.md` § 4.3). Test the connection before upgrading. |
| Bundled OpenSearch | Use only a chart release that also carries the GX-90 OpenSearch certificate fix. Do not run certificate-verifying GroundX Go images on a chart without it. |
| External Redis, OpenSearch, MinIO, self-hosted LLM or intranet URLs signed by a private or self-signed CA | Connections from the GroundX Go services fail until you supply the CA. Follow the steps below and test each connection before upgrading. |
| Customer ingest, crawl or callback URLs with an expired, wrong-hostname or self-signed certificate | These requests fail. A CA does not fix an expired or wrong-hostname certificate; the endpoint owner must replace it. |

To supply a private CA:

1. Confirm the target chart has the behavior with the render probe in `tls-and-certs.md` § 3.2.
2. Create a Secret in the chart namespace whose key `ca.crt` holds a complete PEM bundle: the public root CAs plus the private CA. It must be the complete bundle: the chart also sets `SSL_CERT_FILE` in the GroundX Python services, and some of their clients then trust only that file, so a private-CA-only bundle breaks LLM calls (httpx 0.28.1) and public S3 uploads (minio 7.2.20). That behavior was observed in the extract image, not in a chart deployment (GX-130 ticket comment, 2026-10-26). If the install already sets `fileAccess.caSecretName`, append the new CA to the existing bundle and never replace it (`tls-and-certs.md` § 3.3).
3. Set `fileAccess.caSecretName` to that Secret's name and upgrade.
4. Confirm every pod is Ready (§ 11). A missing Secret or `ca.crt` key makes the upgrade fail: the pre-upgrade schema-migration Job mounts the Secret first, so its pod is expected not to start, and the running pods stay on the previous revision.
5. Check the layout, ranker and summary logs, and the `workspace-*` pod logs when the selected workspace runner image verifies Redis certificates, for `certificate verify failed`: the `ai-server` API and Celery worker pods stay Ready even when they cannot connect to Redis.

To roll back, run `helm rollback` to the previous revision (§ 6), which restores the previous chart and images. Clearing `fileAccess.caSecretName` while the certificate-verifying images still run is not a rollback: endpoints signed by the private CA fail again. Never disable certificate verification. Details: `tls-and-certs.md` § 3.2 and § 4.

### 2.2 Database migration Job (published charts 0.2.7 to 0.2.9)

On published charts 0.2.7, 0.2.8 and 0.2.9, `helm upgrade` first runs a Job named `<release>-schema-migration`, which runs `groundx -migrate-only`. Helm changes no Deployment until the Job finishes. On these charts the Job has a fixed 900-second deadline and no retry, and no value changes either: the chart schema rejects `groundx.migration.*` keys. `helm install` does not run the Job.

The first upgrade to a 0.2.8 or later GroundX image builds a new file-access history table from every past ingest task, even when file access is off. On a large database this can take longer than 900 seconds. A build that stops keeps the rows it copied, but on 0.2.8 and 0.2.9 images the next attempt reads every task again from the first one. Once a build finishes, later upgrades skip it.

Three related behaviors matter during the upgrade:

- The `groundx` API pod runs the migration each time it starts, before it reports healthy. Its liveness probe restarts the pod after about 90 seconds, so on a large database the pod never finishes the build and starts it again after each restart.
- Only one migration runs at a time. A migration that cannot get the database lock within 30 seconds fails with `GroundX migration lock is busy; retry after the active migration finishes`.
- Until the build finishes, the new version's Go workers exit with `missing index file_access_source_history.file_access_history_path_idx; run GroundX -migrate-only before starting this version`. Pods of the previous version keep serving.

**Measure first.** Time the migration on a restored copy of the database before the upgrade window. The row count is context only; plan from the measured time. Use the values files your release or Argo CD Application uses. `<namespace>` below is the chart's `namespace` value (default `eyelevel`).

1. Restore a recent snapshot of the GroundX database to a separate MySQL server. A dump of one database does not include MySQL accounts, so create the GroundX database user from your values on that server, with the same password.
2. Render the target chart's migration Job pointed at that copy, with a long deadline for the test (4 hours here). For a local chart path, use the path instead of `groundx/groundx --version <target-version>`.

    ```sh
    helm template groundx-timing groundx/groundx --version <target-version> \
      -f my-values.yaml -f my-secrets.yaml \
      --set db.existing.rw=<restored-host> --set db.existing.ro=<restored-host> \
      --is-upgrade --show-only templates/app/schema-migration.yaml \
      | sed 's/activeDeadlineSeconds: 900/activeDeadlineSeconds: 14400/' > migration-timing.yaml
    ```

    `migration-timing.yaml` is secret-bearing: its Secret holds the database password and the other credentials from your values. That is true whether or not `metrics.enabled` is set; this render does not include the `metrics-tls` key. Write the file outside any repository or gitignore it, treat the file as secret, and delete it after the Job is removed. Never paste it into chat, logs or a PR.

3. Apply it and wait for it:

    ```sh
    kubectl apply -f migration-timing.yaml
    kubectl wait -n <namespace> --for=condition=complete job/groundx-timing-schema-migration --timeout=4h
    ```

    `kubectl wait` does not return when the Job fails; it keeps waiting until its timeout. To check for a failure, run `kubectl get job <name> -n <namespace> -o jsonpath='{.status.conditions[?(@.type=="Failed")].reason}'`. `BackoffLimitExceeded` means the migration exited with an error: read `kubectl logs job/<name> -n <namespace>` before you delete anything. `DeadlineExceeded` means the Job ran out of time and its pod was stopped, so there may be no logs: raise the deadline. Fix the cause and run the Job again. Do not upgrade or sync until a run has completed.

    When the Job has completed, read its start and finish times, then remove it:

    ```sh
    kubectl get job groundx-timing-schema-migration -n <namespace> -o jsonpath='{.status.startTime} {.status.completionTime}{"\n"}'
    kubectl delete -f migration-timing.yaml
    rm -f migration-timing.yaml
    ```

**Run the migration first when it does not fit.** Under Helm, do this when the measured time is close to or above 900 seconds. Under Argo CD, do it before a sync to a new chart version whenever the measured time is above about 60 seconds, because the API pod is then the only thing that runs the migration (see Argo CD below). Render the Job as in step 2, but with the release name `groundx-premigrate`, without the two `db.existing` settings, with `activeDeadlineSeconds` well above the measured time (for example twice it), and into `migration-premigrate.yaml`, which is secret-bearing in the same way. Apply it, wait for `job/groundx-premigrate-schema-migration` with the `kubectl wait` command from step 3 and a `--timeout` above the new deadline, then delete the Job, its Secret and `migration-premigrate.yaml` as in step 3. Do not restart GroundX pods while it runs: a restarting API pod waits for the same lock and fails after 30 seconds. The chart's own Job then finds the build done and finishes quickly.

These commands create and delete a Secret and a Job in the cluster. Show them to the operator and wait for approval before running them, and confirm each delete separately.

**Helm.** Set `--timeout` above the Job deadline, for example `--timeout 20m`. Helm applies `--timeout` to each operation it waits for, including the migration Job; it is not a limit on the whole upgrade, and its default is 5 minutes. If `helm upgrade` stops with a timeout, the Job can still be running. Check it before you run the upgrade again:

```sh
kubectl get job <release>-schema-migration -n <namespace> -o jsonpath='{.status.active} {.status.conditions[?(@.status=="True")].type} {.status.conditions[?(@.type=="Failed")].reason}{"\n"}'
```

`Complete` means it finished after Helm stopped waiting. `Failed` and a reason mean it failed: handle it as in step 3 above. Only a number, such as `1`, means it is still running: wait for it. `NotFound` means Helm saw it finish and removed it. Running the upgrade again deletes the previous migration Job, even one that is still running, and starts a new one. Wait until the Job has finished first.

**Argo CD.** Argo CD renders the chart with `helm template`, which never sets the upgrade flag, so on these charts Argo CD never creates the migration Job. The new `groundx` API pod is then the only thing that runs the migration. Run the separate Job above with `kubectl`, outside the Application, before you sync to the new chart version. Argo CD neither tracks nor prunes a Job and Secret applied this way, because they carry neither its tracking annotation nor the `app.kubernetes.io/instance` label.

If you already synced, and the new API pods keep restarting while the new workers exit:

1. Turn off automated sync for the Application. Argo CD refuses a rollback while automated sync is on.
2. Roll the Application back to the previous chart version, for example with `argocd app rollback <app-name>`, so that no API pod of the new version runs and holds the lock. Confirm with `kubectl rollout status deployment/groundx -n <namespace>`, then wait until `kubectl get pods -n <namespace>` shows no `groundx` pod of the new version, including one that is still terminating. A terminating pod can still hold the lock, and the separate Job then fails after 30 seconds.
3. Run the separate Job above, wait for it to complete, and delete it, its Secret and the file. If it fails, do not sync: read its logs, fix the cause and run it again.
4. Sync to the new chart version again, and turn automated sync back on if you use it.

Raising `--timeout` or rerunning `helm upgrade` does not help here: under Argo CD there is no Helm release and no chart Job to wait for.

### 2.3 Migration Job values (first chart release after 0.2.9)

The first chart release after 0.2.9 adds three values for the migration Job. Published charts 0.2.7 to 0.2.9 reject them. Before you set them, check that the target chart accepts them:

```sh
helm template probe groundx/groundx --version <target-version> --set groundx.migration.activeDeadlineSeconds=3600 >/dev/null
```

A schema error that names `migration` means the chart does not have the values. The probe discards its output; without `>/dev/null` the render would include the `metrics-tls` private key when `metrics.enabled` is true, so never paste it.

- `groundx.migration.activeDeadlineSeconds` (integer, at least 1, default `3600`): the time limit for the whole Job, in seconds.
- `groundx.migration.backoffLimit` (integer, at least 0, default `2`): how many times Kubernetes starts a new pod after a failed one. Retries share the deadline: when it passes, Kubernetes stops the Job even if retries remain. Each attempt still waits only 30 seconds for the migration lock.
- `groundx.migration.gitOps` (boolean, default `false`): when `true`, the chart renders the migration Secret and Job in every render that enables at least one Go workload, so Argo CD runs them as PreSync hooks before it updates any Deployment, on every full sync including the first. Argo CD does not run hooks when you sync only selected resources, so the Job does not run and the new pods start before the database is migrated: upgrade with a full sync. The database, its credentials, the service account and the image pull Secrets must exist before PreSync, so do not use it for a first sync with the bundled MySQL. It does not change `helm install` or `helm upgrade`. With it on and a deadline above the measured time, the separate Job in § 2.2 is not needed.

On that release the Job renders `activeDeadlineSeconds: 3600`, so the `sed` in § 2.2 no longer matches: raise the deadline of the timing and run-first Jobs with `--set groundx.migration.activeDeadlineSeconds=<seconds>` instead.

Upgrading to that release with unchanged values gives the Job a 3600-second deadline and 2 retries instead of 900 seconds and none. Set `--timeout` above the Job deadline, for example `--timeout 70m`. When Helm stops waiting, it deletes the migration Secret, so the Job cannot start a retry: a retry pod that stays in `ContainerCreating` with a `secret ... not found` event will never start, and the upgrade must be run again with a longer `--timeout`. With that release's default GroundX image, a retried history build starts after the last task it recorded instead of the first one, though some tasks can still be read again.

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

### 3.5 A resource changed kind (ConfigMap to Secret)

Upgrading **`0.2.6` to `0.2.7`** (GX-17) flips seven same-named resources from `ConfigMap` to `Secret`: `config-yaml-map`, each `<svc>-config-py-map`, and `layout-ocr-credentials-map`. The names do not change, only the kind. This is invisible to values.yaml but breaks anything that references these resources **by kind** from outside the chart: GitOps pins that select `kind: ConfigMap`, External Secrets Operator mappings, audit or backup scripts running `kubectl get configmap <name>`, and any RBAC `Role` scoped to `configmaps` rather than `secrets`. The chart carries **no `helm.sh/hook` migration** for this flip (verified) — Helm simply deletes the old ConfigMap and creates the new Secret on upgrade. Before upgrading: retarget every external reference and RBAC grant to `kind: Secret` (and add base64 decode where a consumer read the resource's `data` field as plain text), then upgrade. `helm rollback` flips them back to ConfigMap (see § 6), so external references must tolerate whichever kind matches the deployed revision.

## 4. Hash-annotation-driven rollouts

Many of the chart's Deployments include a hash annotation (`config-hash`, `gunicorn-conf-hash`, `supervisord-hash`, or a sibling) on the Pod template, tying the rollout to the contents of the corresponding rendered resource — ConfigMap or Secret, depending on which annotation:

```go-template
annotations:
  config-hash: {{ include (print $.Template.BasePath "/resources/" $mapPrefix "-config-py.yaml") $ | sha256sum }}
```

When the rendered resource's contents change (because `values.yaml` change re-rendered the config), the annotation changes, triggering a rolling restart of the Deployment.

This means: **most `helm upgrade` operations that change runtime config automatically restart the affected pods**. No manual `kubectl rollout restart` needed.

Exceptions: changes to the `Service` resource (port, type), changes to the PVC (capacity, storageClass), changes to the StatefulSet's volumeClaimTemplates — these may not restart pods automatically. For sweeping config changes, an explicit `kubectl -n eyelevel rollout restart deployment` is the safe pattern.

## 5. Backing-service version coordination

The GroundX chart doesn't strictly couple to specific backing-service versions, but mismatches surface as runtime errors:

| Backing service | Coupling | When to upgrade |
| --- | --- | --- |
| **Cache** (Redis 7.x / Valkey) | Loose — protocol-compatible | Independently when ready |
| **MySQL** (Percona PXC 8.x) | Loose — SQL-compatible | Independently when ready; pay attention to major-version jumps (5.7 → 8.x) requiring data migration |
| **Object store** (MinIO AIStor operator + object store) | Loose — S3-protocol-compatible | Independently. A community MinIO install from an earlier guide moves to AIStor through a one-way upgrade that starts with a disk snapshot — see `services-operators.md` § 4.4 |
| **Search** (OpenSearch 2.x) | Tight on the index version when migrating; loose otherwise | Coordinate with GroundX upgrades, especially across major OpenSearch versions |
| **Stream** (Strimzi-managed Kafka) | Loose for minor Strimzi/Kafka bumps; **tight for the `groundx-strimzi-kafka-cluster` 0.1.x -> 0.2.x jump** (v1beta2 -> v1 CRD conversion) | Minor Strimzi/Kafka: independently, rolling. The 0.1.x -> 0.2.x subchart jump is NOT a plain rolling upgrade; follow the conversion runbook (note below) |
| **NVIDIA GPU Operator** (driver + device plugin) | Tight on the kernel / runtime combo | Coordinate with K8s upgrades, not GroundX upgrades |

> **0.1.x `groundx-strimzi-kafka-cluster` -> 0.2.x is a CRD-API migration, not a rolling upgrade.** The 0.2.x subchart emits `kafka.strimzi.io/v1` resources; a 0.1.x cluster runs `v1beta2`. Before any `0.2.7` install or `helm upgrade`, convert the existing resources with the chart's own runbook (`prereqs/kafka-cluster/README.md` in groundx-on-prem): upgrade the Strimzi operator to 0.50.1 (dual-serving), run `strimzi-v1-api-conversion` + the CRD upgrade so stored CRs become `v1`, then `helm upgrade` to 0.2.7. `helm rollback` does not revert a CRD conversion. This gap (a brownfield 0.1.x Kafka release routed here as a plain rolling upgrade) is the specific case the conversion runbook covers.

> **The first chart release after 0.2.7 requires operator-supplied OpenSearch passwords.** Published chart 0.2.7 and earlier (including 0.2.6) still ship the public OpenSearch default and have no check against it, so on those versions set both `search.password` and `search.privilegedPassword` yourself. From the first chart release after 0.2.7, both `search.password` and `search.privilegedPassword` must be supplied unless `mode` is `ingest` (in `mode: ingest`, from that release, none is needed), by values or by `SEARCH_PASSWORD` / `SEARCH_INIT_PASSWORD` in the cluster credentials Secret (the Secret route needs the `groundx` and `process` images that the same chart release deploys by default (both log in to OpenSearch: the API to search, the indexing worker to write the index); if you override either with `groundx.image` or `process.image`, override both with images built from that chart release or later, and for a tag that is not a version number (such as `chainguard` or a mirrored tag) confirm with the image provider that both images read `SEARCH_PASSWORD` / `SEARCH_INIT_PASSWORD`, or set `search.password` and `search.privilegedPassword` in values instead). From that release the render also rejects a published default value for either key given as a value (matched by hash; a Secret-delivered password is not render-validated), so an upgrade that silently keeps the old default (for example `helm upgrade --reuse-values`) fails to render. For an existing OpenSearch (chart-deployed or customer-managed), set `search.privilegedPassword` (or `SEARCH_INIT_PASSWORD`) to the current admin password and `search.password` (or `SEARCH_PASSWORD`) to the current application password before upgrading, because a new admin value does not change an already-initialized OpenSearch; if either current value is a published default, that chart release rejects it, so rotate the admin password off the default first with the backup-based route below and choose a new application password, then set the new values. When you upgrade the OpenSearch release itself, keep `-f opensearch-admin.values.yaml` on `helm upgrade opensearch`: the image requires `OPENSEARCH_INITIAL_ADMIN_PASSWORD` at every start and a restart without it exits with `No custom admin password found`. Then rotate: Rotate the application password by changing `search.password` and upgrading (or, for `SEARCH_PASSWORD`, by updating the Secret and restarting `groundx` and then `process`); the GroundX API re-creates its user. The OpenSearch `admin` user is reserved, so the security REST API refuses to change it (403 "Resource 'admin' is reserved", checked 2026-09-30 on the seed image); rotate the admin password with the backup-based route (verified 2026-09-30 on the seed image: the backup keeps REST-created users, the new admin password returns 200 and the old one 401, and this persists after a restart). Inside the OpenSearch pod, take `securityadmin.sh -backup` first, set the new `hash.sh` hash as the `admin` hash in the backed-up `internal_users.yml`, and upload that file with `securityadmin.sh -t internalusers`; existing users, including the GroundX application user, are kept. Then set `search.privilegedPassword` to the new value and upgrade, and confirm by logging in as `admin`: the new password must succeed and the old one must be rejected. See the chart README "Upgrading an Existing Install". See `values-authoring.md` section 3.5.4.

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
- **Config-resource rollback IS supported** — the previous ConfigMap or Secret content is reinstated, and the corresponding hash annotation triggers a fresh rollout. Rolling `0.2.7` back to `0.2.6` also reverts the § 3.5 kind flip (the seven resources return to `ConfigMap`); external references and RBAC grants scoped by kind must tolerate whichever kind matches the revision now deployed.
- **Object keys renamed for chart 0.2.8 are not renamed back.** If § 2 step 6 renamed keys that started with `/`, reverse that rename before rolling back to chart 0.2.7, as the same migration guide section describes. Objects written on chart 0.2.8 are stored without the slash and are not in the renamed-key lists, so 0.2.7 services may not find them.

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
- **Worker tier** (celery workers and Go queue services): On the 0.2.8 chart line and later, a celery worker rollout drain waits for in-flight tasks, bounded by the longest running task, up to the grace period; earlier charts can still cut off in-flight tasks. The chart's `terminationGracePeriodSeconds` is set through `replicas.gracePeriod` on the services whose schema lists it, including the `extract.*` sub-microservices, the workspace-runner sub-microservices, the six layout workloads (0.2.7 chart and later), and `ranker.inference` and `summary.inference` (0.2.8 chart line and later). `preProcess`, `process`, `queue`, `summaryClient` and `upload` have a planned shutdown default of 900 seconds. This default is unreleased; the first carrying chart version is unconfirmed. Chart 0.2.8 renders no default; for any other version, verify its published render before relying on a default and set `replicas.gracePeriod` explicitly when needed. The drain needs queue-service images that read `drainSeconds` (the 0.2.7 and later images do; an older pinned image ignores it). Upgrading to a chart confirmed to carry the default restarts the seven `golang.yaml` Deployments once through the `config-hash` annotation, plus the metrics, large-file-delivery, post-process and file-access Deployments when those are enabled; any other service whose schema does not list the key keeps the Kubernetes default. On Kafka installs a draining pod can keep its partition until a rebalance or its reader closes, so on a one-partition topic a new message can wait behind the drain (derived from the queue service source, not measured). If a rebalance moves the partition, the new owner re-runs the message while the old pod is still working (seen in the validation of this change, GX-138).
- **Inference tier** (layout-inference, ranker-inference): GPU pods. Rolling updates work but require enough GPU capacity to schedule the new pod while the old still runs. With one GPU per inference pod, you need a spare GPU during the rollout, OR set `maxUnavailable: 1, maxSurge: 0` to drain-then-create (with downtime). On the 0.2.8 chart line and later, a ranker-inference pod drains its in-flight tasks before it stops, so a rollout waits up to its grace period; earlier charts can still cut off in-flight tasks (see `references/values-yaml.md` § 5.2).
- **Summary inference** (summary-inference): requests no GPU by default, so the default rolling update schedules a new copy beside the old one on the same GPU. When the running copies already fill that GPU, the new copy fails to load with `less than desired GPU memory utilization`, never becomes Ready, and the rollout stalls; it is not `Pending` on `Insufficient nvidia.com/gpu`. Set `summary.inference.updateStrategy: Recreate`, which stops the old copies before the new one starts, so summary is down for the drain time plus model load on each upgrade that changes the summary pod (the drain applies on the 0.2.8 chart line and later; earlier charts can still cut off in-flight tasks; see `references/values-yaml.md` § 5.2). Observed with the 24 GB values in `cluster-requirements.md` § 2.3; for the 48 GB defaults the same recommendation is derived from the rolling-update behavior, not tested on a 48 GB card.
- **Backing services**: each backing service has its own zero-downtime story. Percona PXC supports rolling restarts. Strimzi supports rolling Kafka broker upgrades. OpenSearch single-node deployments have downtime; multi-node deployments support rolling restart.

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

## 12. Secure-by-default StorageClass encryption (groundx-storageclass chart >=0.1.2)

**Not yet safe to rely on.** This section describes `groundx-storageclass` chart
`>=0.1.2`'s behavior. The chart source carries the bump, but publishing it to the public
Helm repo is a separate, not-yet-completed human hand-off (`src/build.sh`, PRIVILEGED,
never automated). Confirm the published chart version before assuming any of the
following applies to your install — on a chart still pinned to `<0.1.2`, there is no
`lookup` guard, so an EBS-backed StorageClass renders whatever the values file supplies
for `parameters.encrypted` (including nothing, if the values file omits it) rather than
defaulting to `encrypted: "true"`. Setting that key explicitly on an **existing** install
on this chart range adds a parameter the live StorageClass didn't have and breaks the
upgrade (StorageClass parameters are immutable) — see `values-yaml.md`'s
`groundx-storageclass` example for the existing-install vs new-install guidance.

Once `>=0.1.2` is actually in use:

- **New installs:** an EBS-backed StorageClass (provisioner `ebs.csi.aws.com`) renders
  `parameters.encrypted: "true"` by default. Every opt-out spelling
  (`"false"`, `false`, `null`, `""`) normalizes to omitting the `encrypted` key, for all
  three EBS-only parameter keys (`type`, `encrypted`, `kmsKeyId`). Non-EBS provisioners
  (`efs.csi.aws.com`, Azure Files (`provisioner file.csi.azure.com`), `filestore.csi.storage.gke.io`) never render
  `encrypted` or `kmsKeyId`, regardless of chart defaults — this section does not apply to
  them.
- **Existing installs (the common upgrade case):** `helm upgrade --install` against a
  live cluster where the named StorageClass already exists reads that class via
  `lookup "storage.k8s.io/v1" "StorageClass" "" <name>` and re-renders its live
  parameters verbatim. StorageClass parameters are immutable in Kubernetes, so the chart
  never changes an existing class's `encrypted` value — **no action is needed** on
  upgrade for a live cluster.
- **No-live-cluster render flows (`helm template`, client-side dry-run, most GitOps
  renderers):** the `lookup` call always resolves empty in these flows (a documented Helm
  limitation), so they always render new-install defaults regardless of what is actually
  deployed. An operator on one of these flows managing an existing class that `0.1.1`
  created *without* an explicit `encrypted` value must set `parameters.encrypted: "false"`
  explicitly in their values file, or the rendered manifest will disagree with the live
  class (which Kubernetes will then reject as an immutable-field change, not silently
  apply). This does not work for a class that `0.1.1` created *with* an explicit
  `encrypted: "false"`: `0.1.2` never renders an explicit `false`, so the key is omitted and
  the render still disagrees with the live class. For that class, use a live-cluster
  `helm upgrade --install` (the `lookup` keeps the live value), stay on `0.1.1` in that
  flow, or create a new StorageClass.
- **Drift warning:** the chart's `templates/NOTES.txt` prints one line only when a `lookup`
  hit finds any supplied (normalized) parameter, such as `encrypted`, `kmsKeyId` or `type`,
  differing from the live class's `parameters`, and it names each one that was not applied.
  Silent on a lookup miss (no existing class) or on agreement. Read that NOTES.txt output after every `helm upgrade --install` against this
  chart.

Existing backing stores (MySQL, OpenSearch, or any store reached without the chart's own
TLS termination) are **not** covered by this StorageClass default. There is no `ssl: true`
chart value for MySQL or OpenSearch connections — that key exists only for the Redis
cache (`cache.existing.ssl: true`). For the real per-store TLS settings
(`db.existing.rootCerts` for MySQL/RDS/Azure Database, OpenSearch's own TLS trust
options), read `references/tls-and-certs.md` §4.

## 13. What this file does not cover

- **The initial install flow** → `install-flow.md`.
- **Air-gapped image staging** → `air-gapped.md` § 10.
- **Backing-service operator upgrades** → respective operator docs; see `services-operators.md` for install pointers.
- **Chart CHANGELOG / breaking-change log** → consult the chart's own `CHANGELOG.md` (when present).
- **GroundX MySQL schema migrations** → not a separate step: the chart's pre-upgrade migration Job and the `groundx` API pod run them; see § 2.2.
- **Major-version Kubernetes upgrades** → upstream Kubernetes docs; the chart works across recent K8s versions but coordinate carefully.
- **Cross-region DR-driven upgrades (active-passive failover patterns)** → `dr-cross-region-runbook.md`.
- **Specific chart-version migration steps** → consult the chart's release notes.
