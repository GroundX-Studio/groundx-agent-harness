# Troubleshooting — Common Failure Modes

This file documents **the failure modes a deployer hits during install, upgrade, and runtime**, organized by *where in the deployment lifecycle the failure surfaces*. Each entry has a symptom, the chart-side or cluster-side cause, and the fix.

For the canonical install sequence, route to `install-flow.md`. For the per-subsystem ownership map (which file owns what), route to `references/README.md`. For the maintenance discipline used when this file's diagnoses go stale, route to the private maintenance reference.

## 1. `helm install` / `helm template` failures

### 1.1 `workspace requires workspace.token or workspace.existingSecret when enabled`

**Symptom.** `helm install` fails immediately with that exact message.

**Cause.** `workspace.enabled: true` was set, but neither `workspace.token` nor `workspace.existingSecret` was supplied. The chart hard-fails at template-render time via `_helpers/app/workspace.tpl:15`:

```go-template
{{- if and (eq (dig "token" "" $in) "") (eq (dig "existingSecret" "" $in) "") -}}
  {{- fail "workspace requires workspace.token or workspace.existingSecret when enabled" -}}
{{- end -}}
```

This is the only `fail` call in the chart's helpers.

**Fix.** Supply one of:

```yaml
workspace:
  enabled: true
  token: "<long-random-shared-secret>"
```

or

```yaml
workspace:
  enabled: true
  existingSecret: "my-workspace-secret"   # must contain WORKSPACE_RUNNER_TOKEN
```

See `workspace-service.md` § 3 for the bootstrap minimum and `credentials.md` § 9 for the credential mechanics.

### 1.2 `layout.ocr.credentials file not found at path: <path>`

**Symptom.** `helm install` fails with this message when GCV OCR is configured.

**Cause.** `layout.ocr.credentials` points at a file path that doesn't exist inside the chart directory at template-render time. The chart's `.Files.Glob` check at `templates/resources/layout-ocr-credentials.yaml:16` fails fast.

**Fix.** Copy the GCP service-account JSON into the chart at the configured path before installing:

```sh
cp /path/to/gcp-service-account.json src/groundx/files/ocr/credentials.json
```

And confirm `layout.ocr.credentials: files/ocr/credentials.json` matches. See `ocr-mode.md` § 4.1.

### 1.3 Schema validation rejected an `additionalProperties` field

**Symptom.** `helm install` fails with `error converting YAML to JSON: ... values don't meet the specifications of the schema(s) in the following chart(s): groundx: - additional property X is not allowed`.

**Cause.** A values block has `additionalProperties: false` in `values.schema.json`. Many subsystem blocks (`workspace.pvc`, `cache.existing`, `db.existing`, etc.) reject unknown fields. Common offenders: `workspace.pvc.enabled` (doesn't exist — the chart `omit`s it explicitly), legacy environment-style `environment:` at the top level, mistyped field names.

**Fix.** Grep the schema (`values.schema.json`) for the parent block and use only the listed `properties`. The scanner sub-check 5 (`scripts/scans/scan-on-prem.mjs`) flags this category in docs; the chart itself rejects at install time.

### 1.4 `KafkaTopic` CRD not registered

**Symptom.** `helm install` succeeds but `kubectl -n eyelevel get kafkatopic` returns `error: the server doesn't have a resource type "kafkatopic"`. Or the GroundX chart's KafkaTopic CRDs render but the Strimzi operator never reconciles them into real topics.

**Cause.** Strimzi operator wasn't installed (or wasn't installed in the right namespace) before the GroundX chart. The chart renders `KafkaTopic` resources but Strimzi must be running to interpret them.

**Fix.** Install Strimzi first (see `services-operators.md` § 6), then `helm install` GroundX.

### 1.5 Missing image pull secret

**Symptom.** Pods stuck in `ImagePullBackOff` with `ErrImagePull` and the imagepull error mentions auth failure or unauthorized.

**Cause.** `cluster.imagePullSecrets` references a secret that doesn't exist in the namespace, or the secret doesn't have valid credentials for the registry.

**Fix.** Create the secret in the install namespace before `helm install`:

```sh
kubectl -n eyelevel create secret docker-registry chainguard-pull-secret \
  --docker-server=cgr.dev \
  --docker-username=<token-id> \
  --docker-password=<token-secret>
```

See `image-variants.md` § 6.

## 2. Pod scheduling failures

### 2.1 Pods stuck `Pending` with `nodeSelector` not matching any node

**Symptom.** `kubectl describe pod` shows `0/N nodes are available: N node(s) didn't match Pod's node affinity/selector`.

**Cause.** GroundX pods target node-label values like `eyelevel-cpu-only`, `eyelevel-cpu-memory`, `eyelevel-gpu-layout`, `eyelevel-gpu-ranker`, `eyelevel-gpu-summary` under the **`eyelevel_node` label key** (not the bare `node` key). If the cluster's nodes are labeled with a different scheme, scheduling fails.

**Fix.** Apply the labels:

```sh
kubectl label node my-cpu-node-1 eyelevel_node=eyelevel-cpu-only
```

Or override the chart's expected values via `cluster.nodeLabels.*` (`node-groups.md` § 1.1). For GPU node groups, the corresponding `eyelevel-gpu-layout` / `eyelevel-gpu-ranker` / `eyelevel-gpu-summary` labels must also be applied to GPU nodes.

### 2.2 GPU pods scheduled but failing to acquire GPU

**Symptom.** `layout-inference`, `ranker-inference`, or `summary-inference` pods schedule but fail with `CUDA error: no CUDA-capable device is detected` or similar.

**Cause.** NVIDIA GPU Operator isn't installed (or isn't running). The pods request `nvidia.com/gpu: 1` and the cluster has no device plugin registering that resource.

**Fix.** Install the NVIDIA GPU Operator before GroundX (`services-operators.md` § 2). On AKS, use the `runtimeClass: nvidia-container-runtime` variant. See `gpu-operator.md` (planned) for deep-dive.

### 2.3 PVC stuck in `Pending`

**Symptom.** `kubectl get pvc -n eyelevel` shows the workspace-data PVC (or a Percona PXC PVC) in `Pending` with `waiting for first consumer to be created before binding` or `no persistent volumes available for this claim`.

**Cause.** The cluster's default StorageClass is missing or not in the right access mode. The chart requests `cluster.pvClass` and `cluster.pvAccessMode`; if those don't match an available StorageClass, PVCs don't bind.

**Fix.** Set a default StorageClass that supports the access mode requested. On AKS use `managed-csi-premium` or `azurefile`; on EKS use `gp3` or `efs-sc`; on GKE use `standard-rwo` or `filestore`. Override `cluster.pvClass` and `cluster.pvAccessMode` to match.

## 3. Init-container `wait-for-*` looping

The chart's app pods (`api.yaml`, `golang.yaml`, `celery.yaml`, etc.) ship init containers that block startup until backing services are reachable. From `templates/app/api.yaml:85–115`:

- `wait-for-cache` — `nc -z <cache.addr> <cache.port>`. Loops with `sleep 2` until reachable.
- `wait-for-metrics` — `wget -T 5 -qO- <metrics.serviceUrl>/health`. Rendered when `metrics` is in `dpnd`.
- `wait-for-callback` — `wget -T 5 -qO- <callback.url>/health`. Rendered for some service flavors.
- `wait-for-database` — `nc -z <db.rw> <db.port>`.

### 3.1 `wait-for-cache` loops forever

**Cause.** Cache (Redis) isn't reachable at `cache.addr:cache.port`. Common causes: NetworkPolicy blocking egress to the in-cluster cache, `cache.existing.addr` pointing at a non-resolvable host, the cache StatefulSet not yet ready.

**Fix.** `kubectl -n eyelevel logs <pod> -c wait-for-cache` confirms the loop. Check `kubectl get statefulset cache` is ready; verify NetworkPolicy allows pod-to-cache traffic; for existing-cache mode, confirm `cache.existing.addr` resolves from inside the cluster.

### 3.2 `wait-for-database` loops forever

**Cause.** MySQL HAProxy service at `<db.serviceName>-cluster-haproxy.<ns>.svc.cluster.local` not resolvable. Common causes: Percona PXC cluster not deployed (or named differently than `db-cluster`), `db.existing.rw` pointing at a non-resolvable host, NetworkPolicy egress block.

**Fix.** Verify the Percona PXC cluster service exists: `kubectl -n eyelevel get svc | grep haproxy`. For cloud-managed MySQL, verify the RDS endpoint resolves and security groups allow the cluster's outbound IPs.

## 4. Runtime / pipeline failures

### 4.1 Documents stuck in pre-process or process queue

**Symptom.** Documents ingested via the API never complete. `kubectl logs -n eyelevel pre-process-xxx` shows the file pulled from the queue but no progress.

**Cause.** Most common: the layout pipeline (`layout-api`, `layout-process`, `layout-inference`) isn't responding. Either GPU pods aren't healthy or callback URLs are misconfigured.

**Fix.** Check `layout-inference` pod logs for CUDA errors; check `layout-api` pod logs for connection errors; verify `layoutWebhook` service is reachable from the layout pipeline (the chart auto-wires this, but custom node-label overrides can disrupt it).

### 4.2 Search returns no results despite successful ingest

**Symptom.** `POST /search` returns empty results for documents that show as fully ingested.

**Cause.** OpenSearch index isn't populated. Either the `layout-save` worker hit a permission error against OpenSearch, the OpenSearch privileged credentials weren't supplied, or `mode: ingest` was set (which disables search-side rendering).

**Fix.** Check `layout-save` pod logs for OpenSearch auth errors. Verify `search.privilegedUsername` and `search.privilegedPassword` match the OpenSearch admin credentials. If `mode: ingest` is intentional, the deployment is ingest-only and search isn't a feature — see `deployment-modes.md` § 2.

### 4.3 Summary requests timing out

**Symptom.** Summary requests hang or return 504 / "model timeout."

**Cause.** Most common: external LLM endpoint slow or rate-limited; or self-hosted `summary-inference` pod underprovisioned / not GPU-scheduled.

**Fix.** For external LLM, check `summary.existing.url` reachable from cluster; verify `summary.existing.apiKey` is correct; check the LLM provider's rate-limit / quota status. For self-hosted, check `summary-inference` pod CUDA status (see § 2.2).

## 5. Upgrade failures

### 5.1 `helm upgrade` rejected by schema after chart bump

**Symptom.** `helm upgrade` fails with new `values.schema.json` rejections that didn't exist in the prior version.

**Cause.** Chart-side schema strictening — new `additionalProperties: false` or `required` constraints, or a renamed field.

**Fix.** Diff `helm/values.schema.json` between the old and new chart versions. Update values.yaml to match. The chart's CHANGELOG (when present) flags breaking changes. See `upgrades.md` (planned) for the canonical upgrade flow.

### 5.2 ConfigMap roll-out didn't restart pods

**Symptom.** After `helm upgrade`, ConfigMap contents changed but pods didn't restart.

**Cause.** Most chart-rendered Deployments include a `config-hash` annotation (e.g., `celery.yaml:62`) tied to the ConfigMap's contents — this forces a rollout when the ConfigMap changes. But ConfigMap-only changes that don't touch the hashed file won't trigger rollouts.

**Fix.** `kubectl -n eyelevel rollout restart deployment <name>` forces a restart. For sweeping changes, rolling-restart all of the relevant subsystem's deployments.

## 6. Where to look when none of these match

When the failure doesn't match a category above:

1. **`helm template -f your-values.yaml ./src/groundx > rendered.yaml`** — render the chart locally without installing. Inspect the rendered output for the resource you expect to find.

2. **`kubectl get events -n eyelevel --sort-by='.lastTimestamp' | tail -40`** — Kubernetes-level events surface scheduling, image-pull, and resource-limit failures.

3. **`kubectl -n eyelevel logs -f <pod> --all-containers`** — pod-level logs including init containers.

4. **`kubectl -n eyelevel describe pod <pod>`** — full event history for that pod (image-pull retries, OOM, eviction).

5. **Re-survey the chart helpers** for the failing subsystem — the per-subsystem helper files under `templates/_helpers/app/` (`workspace.tpl`, `layout-ocr.tpl`, `summary.tpl`, etc.) — to confirm the chart is doing what your doc says it is. The same drift patterns that bite docs bite mental models.

## 7. What this file does not cover

- **Chart-rendered config.yaml structure** → `groundx-architecture/references/data-flow.md`.
- **Application-layer errors** (specific API response codes, RAG quality issues, embedding errors) → application docs; out of chart scope.
- **Kubernetes / Helm fundamentals** (RBAC, pod disruption budgets, taints/tolerations) → upstream Kubernetes docs.
- **Per-cloud provider tuning** → `deployment-options.md` (planned) and `terraform-aws.md` (planned).
- **GPU Operator deep-dive** → `gpu-operator.md` (planned).
- **OpenShift-specific issues** → `openshift.md` (planned).
- **Air-gapped failures** → `air-gapped.md` (planned).
- **Upgrade-specific procedures** → `upgrades.md` (planned).
