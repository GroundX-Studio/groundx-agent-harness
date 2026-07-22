# Autoscaling — HPA, External Metrics, Per-Pod Control

This file documents **how the GroundX chart's HPA story works** — the cluster-wide enable flag, the per-pod hpa toggle, the external-metrics server, the per-service threshold / target / throughput defaults, and the two-axis scaling model (pipeline throughput plus pod-specific metric).

For the chart's per-pod resource defaults and node-group placement, route to `node-groups.md`. For the cost implications of HPA-on vs HPA-off, route to `cost-estimation.md`. For monitoring the metrics the autoscaler consumes, route to `monitoring.md`. For deployer-grade failure-mode diagnosis, route to `troubleshooting.md` § 3.

## 1. The three knobs

| Knob | Default | Effect |
| --- | --- | --- |
| `cluster.hpa` | `false` | Cluster-wide HPA toggle. When `true`, the chart renders HorizontalPodAutoscaler resources for pods that have `replicas.hpa: true` (or inherit it). |
| `<pod>.replicas.hpa` | inherits from `cluster.hpa` | Per-pod override. Set to `false` to disable HPA on a single pod even when `cluster.hpa: true`. |
| `metrics.enabled` | `false` | Enables the custom metrics server pod that exposes the GroundX metrics the HPAs scale on. **Required** for HPA-driven scaling to work — without it, the HPAs render but have no metrics source. |

To turn autoscaling on cluster-wide:

```yaml
cluster:
  hpa: true

metrics:
  enabled: true
```

After install, verify with `kubectl get hpa -n eyelevel` — every autoscaled pod gets an HPA resource.

## 2. The two-axis scaling model

Every autoscaled pod scales on **two metrics simultaneously**:

### 2.1 Pipeline throughput (all pods)

The metrics server estimates total pipeline throughput for files moving through GroundX. Each pod declares the throughput a single replica can support via the per-service `groundx.<svc>.throughput.default` helper. Replicas increase until total pod capacity meets estimated pipeline throughput.

This is a chart-wide signal — every pod with HPA participates in it.

### 2.2 Pod-specific metric (by pod type)

Different pod types scale on different secondary metrics:

| Pod type | Secondary metric | Default target |
| --- | --- | --- |
| **api** (`groundx`, `extract.api`, `layout.api`, `summary.api`, `workspace.api`, etc.) | Response latency / requests | threshold 4000 ms |
| **queue** (`preProcess`, `process`, `queue`, `upload`, `summaryClient`) | Message backlog | threshold 10 |
| **task** (`layout.{ocr, correct, map, process, save}`, `extract.{agent, download, save}`, `workspace.{cleanup, command, provision, publish, workspace}`) | Celery task backlog | threshold 10 |
| **inference** (`layout.inference`, `ranker.inference`, `summary.inference`) | Model request throughput | Per-replica capacity = throughput-default × workers × threads (tokens/min). Scales when requests exceed per-replica capacity. Default throughput-per-worker-per-thread is 60000 for layout.inference; see the per-helper `<svc>.inference.throughput.default` |

These come from the per-service `groundx.<svc>.threshold.default` helpers (e.g., `_helpers/app/groundx.tpl:45` for the `groundx` pod, `_helpers/app/workspace-api.tpl:58–60` for workspace-api).

## 3. Replicas — `desired` / `min` / `max`

The semantics of the three `replicas` fields differ by HPA mode:

**HPA disabled** (`<pod>.replicas.hpa: false` or inherits from `cluster.hpa: false`):

```yaml
<pod>:
  replicas:
    desired: 2     # the only field that matters; replica count is fixed at 2
```

**HPA enabled** (`<pod>.replicas.hpa: true`):

```yaml
<pod>:
  replicas:
    desired: 1     # initial value at install; autoscaler then adjusts
    min: 1         # lower bound
    max: 16        # upper bound
    hpa: true
```

When HPA is enabled, the chart sets `desired` as the initial replica count; `min` and `max` bound the autoscaler's adjustment range.

## 4. Per-service threshold / target / throughput defaults

Every autoscaled service ships with three default helpers:

| Helper suffix | Meaning |
| --- | --- |
| `<svc>.threshold.default` | The metric target the HPA tries to maintain (queue backlog count, API latency ms, etc.) |
| `<svc>.target.default` | Fraction of the threshold the HPA aims for (typically `1`) |
| `<svc>.throughput.default` | Per-replica throughput estimate (tokens/min or messages/min) for the pipeline-throughput axis |

Each is overridable via `<pod>.replicas.{threshold, target, throughput}` in values.yaml. For example, to halve the workspace command worker's queue threshold:

```yaml
workspace:
  command:
    replicas:
      hpa: true
      threshold: 5     # half the default 10 → scale earlier
```

For the documented defaults per workspace component, see `workspace-service.md` § 8.

## 5. The metrics server

The custom metrics server (`metrics.enabled: true`) exposes a `/metrics` endpoint that the chart-rendered HPAs scrape via an `External` metrics source. It exposes:

- Pipeline throughput
- API latency
- Queue backlog
- Task backlog
- Inference request throughput

For the namespace and listening port, see `templates/app/metrics.yaml`. The metrics server is a single chart-deployed pod (typically `replicas.desired: 1`); it doesn't itself autoscale because it's the source of truth for the autoscaler.

**Without the metrics server, HPAs render but have no signal.** Setting `cluster.hpa: true` without `metrics.enabled: true` produces HPAs in `<unknown>` state — they don't scale.

## 6. Prometheus integration (optional)

For Prometheus Operator users, enable ServiceMonitor:

```yaml
metrics:
  enabled: true
  serviceMonitor:
    enabled: true
```

This renders a `ServiceMonitor` resource that Prometheus discovers automatically. Prometheus then scrapes the GroundX `/metrics` endpoint and the metrics are available for dashboards in addition to the HPA. See `monitoring.md` for the full Prometheus + Grafana setup.

## 7. Cost implications of HPA-on

`cluster.hpa: true` multiplies the cluster's resource budget by the per-pod `replicas.max` values. The vanilla chart sets max values that are reasonable for moderate-to-high throughput; production deployments that need higher peaks can raise them but must scale node-group capacity to match.

The per-pod max footprint is computed by `Σ (replicas.max × resources.limits)` for each pod, summed per node group. See `cost-estimation.md` § 4 for the manual sizing pattern and § 8 for the cost-modelling discipline.

A common pattern: **HPA on for queue / task / api pods; HPA off (replicas fixed) for inference pods.** Inference pods consume GPU memory at a fixed multiple of GPU memory per pod, and the GPUs are expensive enough that overprovisioning at peak is rarely justified.

## 8. Per-pod HPA override pattern

To enable HPA cluster-wide but disable it on selected pods:

```yaml
cluster:
  hpa: true

metrics:
  enabled: true

summary:
  inference:
    replicas:
      hpa: false        # disable HPA on summary-inference specifically
      desired: 1

layout:
  inference:
    replicas:
      hpa: false        # disable HPA on layout-inference specifically
      desired: 1
```

The chart's per-pod `hpa` field, when set, overrides the cluster-wide default. This is the standard pattern for keeping inference pods at fixed replicas while letting the orchestration tier autoscale.

## 9. Cross-field implications

| Set this... | …and this is implied or required |
| --- | --- |
| `cluster.hpa: true` | `metrics.enabled: true` is effectively required. Without the metrics server, HPAs have no signal and don't scale. |
| `metrics.enabled: false` + `cluster.hpa: true` | HPAs render but show `<unknown>` for their target metric. Misleading state — not an outright failure, but the autoscaler does nothing. |
| `<pod>.replicas.hpa: true` + missing `replicas.max` | The HPA defaults `max` to a chart-sensible value; verify by inspecting the rendered HPA resource. Always pin `max` explicitly for production. |
| Custom worker queue names (e.g., `workspace.command.queue: my-command-queue`) | Keep them in values, not by editing templates — the metrics-server's queue config and the HPA's metric source must stay in sync. The chart wires both from the same value. |
| HPA on + node-group capacity not increased | Pods scale up to `replicas.max` but stay `Pending` because node capacity is exhausted. Plan node-group capacity for `replicas.max × resources.requests` per pod, summed per node group. See `cost-estimation.md` § 4. |

## 10. Verification

After enabling HPA:

```sh
# Every autoscaled pod has an HPA resource
kubectl -n eyelevel get hpa

# Targets should show real values, not <unknown>
kubectl -n eyelevel describe hpa <pod>-hpa

# Metrics server is up and responding
kubectl -n eyelevel logs <metrics-pod>
kubectl -n eyelevel get svc metrics
```

If `kubectl describe hpa` shows `<unknown>` for the metric, the metrics server is not exposing the expected metric — check `metrics.enabled: true` is set, the metrics pod is `READY 1/1`, and the chart's expected metric names match what the metrics server publishes.

## 11. What this file does not cover

- **Per-pod resource defaults and node-group placement** → `node-groups.md`.
- **Cost modelling around HPA min/max footprint** → `cost-estimation.md`.
- **Prometheus / Grafana setup beyond the ServiceMonitor toggle** → `monitoring.md`.
- **External metrics adapter installation** → `monitoring.md` — the chart's metrics server is the GroundX-side source; the cluster also needs a Kubernetes external-metrics adapter for HPAs to consume the metrics.
- **Workspace runner specific HPA defaults** → `workspace-service.md` § 8.
- **Architectural rationale for the two-axis model** → `groundx-architecture/references/observability.md`.
- **Troubleshooting HPA / metrics-server failures** → `troubleshooting.md` § 4.
