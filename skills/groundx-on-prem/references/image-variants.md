# Image Variants — Default vs Chainguard Hardened

This file documents **what `imageType` does, which image variants the chart supports, and the full set of side-effects of switching to Chainguard hardened images** (container UIDs, pull secrets, per-pod image overrides, dependency operator images, busybox helper image).

For the related admin field that overrides the chart-wide image-repo prefix, route to `license-and-admin.md` § 4. For image-pull-secret credential mechanics, route to `credentials.md` § 5.

## 1. The flag

```yaml
imageType: chainguard   # default is "" (unset → standard images)
```

Top-level string field at the root of values.yaml. The chart's schema (`values.schema.json:7`) declares it as a free-form string. Only one value other than empty has chart-level effects: `chainguard`.

## 2. What `imageType: chainguard` actually does

Surprisingly little is conditional on this flag. The chart branches on `imageType == "chainguard"` in three places:

| Location | Effect when `imageType: chainguard` |
| --- | --- |
| `groundx.container.username` (`templates/_helpers/main.tpl:38–44`) | Container user UID becomes `65532` (Chainguard's `nonroot` convention). Otherwise `1001`. |
| `groundx.golang.home` (`templates/_helpers/app/golang.tpl:1–8`) | The home-directory token used to build app config mount paths becomes `nonroot`. Otherwise `golang`. Consumed in `templates/app/golang.yaml:156` and `templates/app/metrics.yaml:197`. |
| `templates/resources/layout-supervisord-conf.yaml:36–38` | The supervisord config for every layout-* celery worker gains an extra env var: `PROTOCOL_BUFFERS_PYTHON_IMPLEMENTATION=python`. This avoids the C++ protobuf binding (which the Chainguard distroless image doesn't ship). |

Everything else — image paths, pull secrets, dependency images, other runtime arguments — is **not auto-flipped** by the flag. To actually run Chainguard variants you must also:

1. Override each pod's `image:` field to a Chainguard-tagged image.
2. Add `chainguard-pull-secret` (or your equivalent) to `cluster.imagePullSecrets`.
3. Optionally override `busybox.image` and dependency-operator images.

The upstream chart ships a complete reference set under `src/groundx/values/chainguard/` — six files that together flip the entire deployment to Chainguard variants. Treat that directory as the canonical recipe.

## 3. The reference set — `src/groundx/values/chainguard/`

| File | What it covers |
| --- | --- |
| `values.yaml` | Core chart: `imageType: chainguard`, `cluster.imagePullSecrets: [chainguard-pull-secret]`, `busybox.image: cgr.dev/eyelevel.ai/busybox-fips:latest` (the cgr.dev busybox is the *canonical* Chainguard choice; the standard `public.ecr.aws/c9r4x6y5/eyelevel/busybox:latest` also works with `imageType: chainguard` and is what `values.aks.yaml` uses), `cache.image: cgr.dev/eyelevel.ai/redis-fips:v8.2.3`, plus per-pod `image:` overrides for `groundx`, `layout.{api,correct,inference,map,ocr,process,save}`, `layoutWebhook`, `preProcess`, `process`, `queue`, `summaryClient`, `upload`. |
| `values.nvidia.yaml` | NVIDIA GPU operator: `operator.runtimeClass: nvidia-container-runtime`. |
| `values.minio.operator.yaml` | MinIO **operator** image substitution. Pull secret `chainguard-pull-secret`. |
| `values.minio.tenant.yaml` | MinIO **tenant** image substitution. Pull secret. |
| `values.strimzi.operator.yaml` | Strimzi (Kafka) operator image substitution. Pull secret. |
| `values.strimzi.cluster.yaml` | Strimzi Kafka cluster image substitution. |

The split between operator and tenant/cluster files for MinIO and Strimzi exists because those subsystems are deployed as separate Helm releases — see `services-prereqs.md` and (when shipped) `services-operators.md`.

For a full Chainguard install you layer them:

```sh
helm install groundx ./chart \
  -f src/groundx/values/chainguard/values.yaml \
  -f src/groundx/values/chainguard/values.nvidia.yaml \
  -f my-overrides.yaml

# MinIO operator/tenant installs separately:
helm install minio-operator minio/operator \
  -f src/groundx/values/chainguard/values.minio.operator.yaml
helm install minio-tenant minio/tenant \
  -f src/groundx/values/chainguard/values.minio.tenant.yaml

# Strimzi (Kafka) similarly:
helm install strimzi strimzi/strimzi-kafka-operator \
  -f src/groundx/values/chainguard/values.strimzi.operator.yaml
# Then the chart-rendered Kafka cluster references the cluster values file.
```

## 4. Per-pod image override pattern

Every pod helper that produces an image path follows the same shape (`coalesce` over an explicit override, then a chart-built fallback):

```go-template
{{- define "groundx.layout.ocr.image" -}}
{{- $b := .Values.layout | default dict -}}
{{- $in := dig "ocr" dict $b -}}
{{- $repoPrefix := include "groundx.imageRepository" . | trim -}}
{{- $ver := coalesce .Chart.AppVersion .Chart.Version -}}
{{- $fallback := printf "%s/eyelevel/layout-process:%s" $repoPrefix $ver -}}
{{- coalesce (dig "image" "" $in) $fallback -}}
{{- end }}
```

So per-pod `image:` always wins. If the deployer wants Chainguard variants for some pods and standard for others — for example, hardened images for the externally-reachable surfaces and standard images for the internal pipeline — they only override the pods that need it.

## 5. The image-repo prefix

The chart-wide image-repo prefix (`groundx.imageRepository`) lives under `admin.imageRepository` (default `public.ecr.aws/c9r4x6y5`). When set, it changes the *fallback* prefix used by every pod's image-path helper, but pod-level `image:` overrides ignore the prefix entirely (they're full paths).

For air-gapped clusters using Chainguard images:

```yaml
admin:
  imageRepository: my-mirror.internal/c9r4x6y5

imageType: chainguard
# Per-pod image overrides become my-mirror.internal/... or cgr.dev/... as needed
```

See `license-and-admin.md` § 4 for the prefix mechanics.

## 6. Pull secrets

Chainguard's registry (`cgr.dev`) requires authentication for the FIPS variants and for some operator images. The pull secret reference is added to `cluster.imagePullSecrets`:

```yaml
cluster:
  imagePullSecrets:
    - chainguard-pull-secret
```

The chart consumes this list via `groundx.imagePullSecrets` (`templates/_helpers/main.tpl:79–87`) and attaches the secret references to every Pod spec. The secret itself must exist in the namespace before install — the chart does not create it. Provision pattern:

```sh
kubectl create namespace eyelevel
kubectl -n eyelevel create secret docker-registry chainguard-pull-secret \
  --docker-server=cgr.dev \
  --docker-username=<token-id> \
  --docker-password=<token-secret>
```

See `credentials.md` § 5 for the broader image-pull-secret pattern.

## 7. Busybox helper image

The chart uses a busybox image for **`wait-for-<dependency>` init containers** — small `until nc -z` / `until wget` loops that block pod startup until cache, metrics, database, and callback services are reachable (`templates/app/api.yaml:85–115`, similar patterns elsewhere). It's overridable independently:

```yaml
busybox:
  image: cgr.dev/eyelevel.ai/busybox-fips:latest
```

Helper at `_helpers/main.tpl:25–31`. Default fallback is `{prefix}/eyelevel/busybox:1.0.0`.

## 8. Cross-field implications

| Set this... | …and this is implied or required |
| --- | --- |
| `imageType: chainguard` only | Container UIDs flip to `65532`, golang home flips to `nonroot`. But pod images still resolve to the default (non-Chainguard) tags unless you also override per-pod `image:` fields. Pods will pull non-Chainguard images running as UID 65532 — likely to fail on filesystem-permission checks. **Don't set `imageType: chainguard` without the matching image overrides.** |
| Per-pod `image:` overrides without `imageType: chainguard` | Pods pull the override images but run as UID `1001`. Chainguard nonroot images expect UID `65532`. Likely permission failures inside the container. **Pair the override with the flag.** |
| Chainguard images + air-gapped cluster | Mirror the Chainguard images to a private registry first, then set `admin.imageRepository` plus per-pod `image:` to that mirror. `cgr.dev` is not reachable from air-gapped clusters. |
| Chainguard pull secret missing | Pods fail to pull with `ImagePullBackOff`. Provision the secret in-namespace before `helm install`. |
| `cluster.imagePullSecrets` set globally | The list applies to **every** Pod the chart renders. Per-pod overrides aren't needed for pull secrets; per-cluster scope is the right altitude. |

## 9. FedRAMP / compliance posture

Chainguard's hardened images are typically a load-bearing piece of FedRAMP-track deployments because they ship with verified provenance, near-zero-CVE base layers, and FIPS-validated cryptography. **Switching `imageType` alone is insufficient** — the deployment also needs:

- All pod images on Chainguard variants (not just the chart pods — also MinIO, Strimzi, NVIDIA operator, Redis, MySQL/Percona, OpenSearch).
- All pull secrets and registry credentials managed under the deployer's compliance-scope credentials store.
- Egress to `cgr.dev` either allowed (regulated cluster) or proxied through a private mirror (air-gapped).
- Audit trail recording every image-digest the cluster pulls.

The chart enables FedRAMP-compatible deployments but does not enforce them. The compliance audit work lives outside the chart.

## 10. Verification — confirming Chainguard is actually in effect

After install:

```sh
kubectl -n eyelevel get pods -o jsonpath='{range .items[*]}{.metadata.name}{"\t"}{.spec.containers[*].image}{"\n"}{end}'
```

Every line should show a Chainguard-tagged image (typically `cgr.dev/...` or your mirror's path with `:chainguard` tags). Cross-check the UID:

```sh
kubectl -n eyelevel get pod <name> -o jsonpath='{.spec.securityContext.runAsUser}'
# expected: 65532
```

If any pod shows UID `1001` or pulls a non-Chainguard tag, the flag-plus-override pairing is incomplete.

**OpenShift caveat.** The chart's `renderSecurityContext` helper (`_helpers/elements/securitycontext.tpl:9–26`) deliberately omits `runAsUser` when `cluster.type: openshift` — OpenShift's SCC assigns the UID independently. On OpenShift the UID check above will return empty regardless of `imageType`. Validate Chainguard adoption on OpenShift via the image-tag check alone, or by inspecting the running container's actual UID with `kubectl exec ... id`.

## 11. What this file does not cover

- **`admin.imageRepository` mechanics** → `license-and-admin.md` § 4.
- **Pull-secret credential lifecycle** → `credentials.md` § 5.
- **MinIO / Strimzi / NVIDIA operator deployment specifics** → `services-prereqs.md` and `services-operators.md` (when it ships).
- **Air-gapped image-mirroring procedure** → `air-gapped.md` (planned).
- **FedRAMP attestation checklists** → out of scope; consult the deployer's compliance org and `groundx-architecture/references/data-residency.md`.
- **Chainguard product details, pricing, or tag-lifecycle policy** → consult Chainguard's documentation.
