# Red Hat OpenShift — Quickstart

This file documents **the OpenShift-specific behaviour the chart exposes** — the `cluster.type: openshift` flag, what changes when it's set (security contexts, ingress vs Route, the chart's `isOpenshift` and `createSymlink` helpers), the OpenShift-specific seed values file, and the install sequence for OpenShift AI clusters.

For NVIDIA GPU Operator on OpenShift (which uses the Red Hat OperatorHub, not Helm), route to `gpu-operator.md` § 4. For general install ordering, route to `install-flow.md`. For the security-context implications on Chainguard, route to `image-variants.md` § 10.

## 1. The flag

```yaml
cluster:
  type: openshift     # default is "eks"; valid values include "eks", "aks", "gke", "openshift", "minikube"
```

The chart's `groundx.clusterType` helper (`_helpers/main.tpl:51–54`) reads `cluster.type` (defaulting to `eks`) and lowercases it. Several behaviours branch on `clusterType == openshift`.

## 2. What changes when `cluster.type: openshift`

### 2.1 Security contexts skip `runAsUser`

The chart's `renderSecurityContext` helper (`_helpers/elements/securitycontext.tpl:9–26`) deliberately omits `runAsUser` / `runAsGroup` / `fsGroup` when `clusterType == openshift`:

```go-template
{{- if $isOS -}}
  {{- $ctx = dict
      "runAsNonRoot" true
      "seccompProfile" (dict "type" "RuntimeDefault")
    -}}
{{- else -}}
  {{- $ctx = dict
      "runAsNonRoot" true
      "seccompProfile" (dict "type" "RuntimeDefault")
      "runAsUser" $user
      "runAsGroup" $user
      "fsGroup" $user
      "fsGroupChangePolicy" "OnRootMismatch"
    -}}
{{- end }}
```

OpenShift's Security Context Constraints (SCC) assign UIDs from a per-namespace range and reject hardcoded `runAsUser`. The chart respects this by leaving the UID unset and letting SCC do its thing.

**Implication for Chainguard.** On OpenShift, the chart's `imageType: chainguard` flag (which would normally flip the UID to 65532 — see `image-variants.md` § 2) has *no effect on UID*. The UID is set by the SCC. Verify the actual running container UID with `kubectl exec ... id` (or `oc exec`) rather than reading the chart's spec.

### 2.2 Ingress vs Route

The chart's interface helper supports OpenShift `Route` (apiVersion `route.openshift.io/v1`) in addition to standard Kubernetes `Ingress`. From `_helpers/elements/interface.tpl:48`:

```go-template
apiVersion: route.openshift.io/v1
```

The Route resource type is rendered when the deployment's ingress shape calls for it. Standard non-OpenShift clusters use `networking.k8s.io/v1 Ingress` exclusively.

### 2.3 Skip filesystem symlinks

The chart's `groundx.createSymlink` helper (`_helpers/main.tpl:56–59`) returns `false` on OpenShift (and Minikube):

```go-template
{{- define "groundx.createSymlink" -}}
{{- $t := include "groundx.clusterType" . -}}
{{- and (ne $t "openshift") (ne $t "minikube") -}}
{{- end }}
```

This affects init-container behaviour in inference pods that would normally create symlinks for model caches. OpenShift's PVC permission model doesn't reliably allow the symlink creation step, so the chart skips it. Inference pods still work; they just don't materialize the convenience symlinks.

### 2.4 The `isOpenshift` helper

`_helpers/main.tpl:108–111` exposes `groundx.isOpenshift` as a boolean for downstream conditionals:

```go-template
{{- define "groundx.isOpenshift" -}}
{{- $t := include "groundx.clusterType" . -}}
{{- eq $t "openshift" -}}
{{- end }}
```

Other helpers and templates can branch on this. The pattern is `{{- if eq (include "groundx.isOpenshift" .) "true" -}}`.

## 3. The OpenShift seed values file

The chart ships `src/groundx/values/openshift/values.yaml`:

```yaml
licenseKey: "00000000-0000-0000-0000-000000000000"

admin:
  apiKey: "00000000-0000-0000-0000-000000000000"
  email: "support@mycorp.net"
  password: "password"
  username: "00000000-0000-0000-0000-000000000000"

cluster:
  pvClass: eyelevel-pv
  type: openshift
# ... (continues with OpenShift-tuned defaults)
```

Use this as the starting point for an OpenShift deployment. Layer it under your own overrides:

```sh
helm install groundx ./src/groundx \
  -n eyelevel \
  -f helm/values/openshift/values.yaml \
  -f my-overrides.yaml
```

## 4. Install sequence — OpenShift AI

The canonical OpenShift install sequence is materially different from EKS / AKS / GKE because operator installs go through OLM, not Helm:

1. **Cluster prep.** Install OpenShift cluster. For GPU workloads, ensure GPU-capable Machine Sets exist.

2. **Node Feature Discovery (NFD) operator.** Via OperatorHub. NFD tags nodes with hardware capability labels (GPU presence, CPU features). Required before GPU Operator.

3. **NVIDIA GPU Operator.** Via OperatorHub (not Helm). The operator detects GPU nodes (via NFD labels) and installs driver + device plugin. See `gpu-operator.md` § 4.

4. **OpenShift AI operator.** Via OperatorHub. Provides higher-level managed AI workflows; not strictly required for GroundX but often installed alongside.

5. **Backing-service operators** (Strimzi, Percona, OpenSearch). Strimzi and OpenSearch are available via OperatorHub; Percona usually via its own Helm chart. See `services-operators.md`.

6. **GroundX chart install** with `cluster.type: openshift` set.

This ordering matters — GPU Operator before GroundX (so `nvidia.com/gpu` resources are registered before inference pods schedule); backing-service operators before GroundX (so CRDs exist when the chart renders KafkaTopic / pxc CRs).

## 5. SCC and ServiceAccount

OpenShift SCCs are the equivalent of PodSecurityPolicy. The chart pods need to be allowed under an appropriate SCC (typically `restricted-v2` works because the chart pods specify `runAsNonRoot: true`, `seccompProfile: RuntimeDefault`, `allowPrivilegeEscalation: false`, and `capabilities.drop: [ALL]`).

If a pod needs a custom SCC (e.g., for hostPath access — uncommon in GroundX), the deployer creates the SCC and binds it to the namespace's default ServiceAccount or to a per-pod ServiceAccount referenced via `<pod>.serviceAccount.name`.

For per-pod ServiceAccount override, see the corresponding subsystem's `serviceAccount.name` field. Example for workspace:

```yaml
workspace:
  api:
    serviceAccount:
      name: workspace-api-sa
```

The chart doesn't render the ServiceAccount itself (or the SCC binding) — those are deployer-managed.

## 6. Persistent volumes on OpenShift

OpenShift's storage layer typically uses:

- **`ocs-storagecluster-ceph-rbd`** (Ceph RBD) for `ReadWriteOnce` block storage.
- **`ocs-storagecluster-cephfs`** (CephFS) for `ReadWriteMany` filesystem storage.

Or vendor-specific classes (NetApp Trident, Pure Storage Portworx).

Set `cluster.pvClass` to the appropriate storage class for the deployment:

```yaml
cluster:
  pvClass: ocs-storagecluster-cephfs    # for RWX needs (workspace PVC, shared model cache)
  pvAccessMode: ReadWriteMany
```

When a stateful subsystem (Percona PXC, MinIO, OpenSearch) needs RWO storage, override the per-subsystem PVC class. See the operator-specific docs.

## 7. Route exposure

To expose GroundX externally on OpenShift, use a Route instead of an Ingress:

```yaml
groundx:
  ingress:
    enabled: false      # don't render the Ingress
    # The chart's interface helper renders the Route resource type
    # when groundx.isOpenshift is true and an external entrypoint is needed.
```

Verify with `oc get route -n eyelevel`. OpenShift's Router (HAProxy) handles TLS termination and routing to the GroundX service.

## 8. Cross-field implications

| Set this... | …and this is implied or required |
| --- | --- |
| `cluster.type: openshift` | `runAsUser` omitted from pod specs; OpenShift SCC controls UID. Chainguard-flavor images may still need image-pull secrets but the UID story is OpenShift-managed. |
| `cluster.type: openshift` + `imageType: chainguard` | Container images come from Chainguard, but UID comes from SCC, not from the chart's `groundx.container.username` (which returns 65532). Verify actual UID via `oc exec`. |
| GPU Operator installed via Helm on OpenShift | OperatorHub path is canonical; Helm install may work but isn't the supported path. |
| `groundx.ingress.enabled: true` on OpenShift | Renders a Kubernetes Ingress, which OpenShift's Router may or may not honor depending on cluster config. Prefer Route via the chart's interface helper (which switches when `cluster.type: openshift`). |
| Custom SCC required | Deployer creates the SCC and binds to a per-pod ServiceAccount. Chart doesn't render SCC resources. |

## 9. Verification

After install on OpenShift:

```sh
# Pods running
oc get pods -n eyelevel

# Each pod's UID is set by SCC (not 1001 or 65532 from the chart)
oc exec -n eyelevel <pod> -- id

# Routes (if any)
oc get route -n eyelevel

# SCC assignment
oc get pod <pod> -n eyelevel -o jsonpath='{.metadata.annotations.openshift\.io/scc}'
```

If `openshift.io/scc` is `restricted-v2`, the pods are running under the standard restricted SCC — that's typical and correct.

## 10. What this file does not cover

- **OperatorHub navigation and OLM mechanics** → Red Hat OpenShift documentation.
- **GPU Operator install via OperatorHub** → `gpu-operator.md` § 4 + Red Hat docs.
- **OpenShift AI operator deep-dive** → Red Hat OpenShift AI documentation; the GroundX chart consumes whatever the operator provides.
- **Custom SCC authoring** → Red Hat security docs.
- **Routes vs Ingress trade-offs (TLS, ACME, ingress controllers)** → OpenShift networking docs.
- **OpenShift-specific image-pull secret patterns** → see `credentials.md` § 5 (mostly cross-platform).
- **OpenShift-specific storage tuning** → consult the cluster's storage operator docs (OCS, Trident, Portworx).
