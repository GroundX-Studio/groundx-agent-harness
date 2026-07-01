# Monitoring — Prometheus + Grafana + ServiceMonitor

This file documents **how to wire GroundX metrics into a Prometheus + Grafana stack** — what the chart exposes, the ServiceMonitor toggle, the upstream `monitoring/` directory's reference setup (`values.prometheus.yaml`, `service-monitor.yaml`, `groundx-dashboard.json`), and what to scrape vs ignore.

For the autoscaling that consumes these metrics, route to `autoscaling.md`. For per-pod resource sizing visible in metrics, route to `node-groups.md` and `cluster-requirements.md`. For end-to-end observability architecture, route to `groundx-architecture/references/observability.md`.

## 1. What the chart exposes

When `metrics.enabled: true`, the chart deploys a single metrics service pod that exposes a `/metrics` endpoint on the service `metrics.<namespace>.svc.cluster.local`. The endpoint surfaces:

- **Pipeline throughput** — total estimated throughput for files moving through GroundX.
- **API latency** — request-response latency per API pod.
- **Queue backlog** — message count per queue.
- **Task backlog** — Celery task count per worker.
- **Inference request throughput** — model request rate per inference pod.

These are the same metrics the HPA consumes for autoscaling (`autoscaling.md` § 5). With monitoring enabled, the metrics are also available for dashboards.

## 2. Enabling the ServiceMonitor

For Prometheus Operator users, the chart can render a `ServiceMonitor` resource that Prometheus discovers automatically:

```yaml
metrics:
  enabled: true
  serviceMonitor:
    enabled: true
```

When `metrics.serviceMonitor.enabled: true`, the chart renders a `ServiceMonitor` named `metrics` in the install namespace. Prometheus Operator picks it up and starts scraping.

Without ServiceMonitor support (legacy Prometheus, or non-operator deployments), the deployer configures scraping out-of-band against the `metrics.<namespace>.svc.cluster.local:<port>/metrics` endpoint.

## 3. The reference setup at `monitoring/`

The upstream `groundx-on-prem` repo ships a reference Prometheus + Grafana setup under `monitoring/`:

| File | Purpose |
| --- | --- |
| `monitoring/values.prometheus.yaml` | Helm values for `kube-prometheus-stack`. Configures `kube-state-metrics` to expose `eyelevel_node` and legacy `node` (node-side labels) plus `app` (pod label) via metric label allow-list. Pins all five `kube-prometheus-stack` components (Prometheus, Grafana, Alertmanager, prometheusOperator, kube-state-metrics) to `eyelevel-cpu-only` nodes. |
| `monitoring/service-monitor.yaml` | The `ServiceMonitor` resource that targets the GroundX metrics service. Define-once, applied via `kubectl apply`. |
| `monitoring/groundx-dashboard.json` | Pre-built Grafana dashboard JSON. Import into Grafana for an initial view of pipeline throughput, queue depths, API latency. |
| `monitoring/README.md` | Step-by-step setup against `kube-prometheus-stack`. The canonical install path. |

For full setup, follow `monitoring/README.md` upstream. Briefly:

```sh
# 1. Create monitoring namespace
kubectl create namespace monitoring

# 2. Install kube-prometheus-stack with GroundX-tuned values
helm repo add prometheus-community https://prometheus-community.github.io/helm-charts
helm repo update

helm upgrade --install monitoring prometheus-community/kube-prometheus-stack \
  -n monitoring \
  -f monitoring/values.prometheus.yaml

# 3. Apply the ServiceMonitor so Prometheus scrapes GroundX
kubectl -n monitoring apply -f monitoring/service-monitor.yaml

# 4. Import the dashboard into Grafana (via UI or grafana provisioning)
```

After install, Prometheus runs in `monitoring`, Grafana is deployed automatically, and `kube-state-metrics` exposes the GroundX-relevant labels.

## 4. What `kube-state-metrics` exposes

By default `kube-state-metrics` filters most pod / node labels. The reference `values.prometheus.yaml` allow-lists two:

- **`eyelevel_node`** on Kubernetes Nodes — via `kube_node_labels`. Lets dashboards group by node group (`eyelevel-cpu-only` / `eyelevel-gpu-layout` / etc.).
- **`app`** on Pods — via `kube_pod_labels`. Lets dashboards group by GroundX pod (e.g., `app=workspace-api`, `app=layout-inference`).

```yaml
# values.prometheus.yaml excerpt — actual file at monitoring/values.prometheus.yaml
kube-state-metrics:
  nodeSelector:
    eyelevel_node: eyelevel-cpu-only

  metricLabelsAllowlist:
    - nodes=[
        node,
        eyelevel_node,
      ]
    - pods=[
        app,
      ]
```

This exposes the following to Prometheus and Grafana:

- Both `node` (legacy chart label key) and `eyelevel_node` (canonical) on Kubernetes **nodes** via `kube_node_labels`. See `node-groups.md` § 1 for the canonical-vs-legacy story.
- `app` on Kubernetes **pods** via `kube_pod_labels` (set by the chart's `groundx.renderDefaultLabels` helper to each pod's service name).

These are the most-used groupings for GroundX dashboards. Adding more labels (e.g., `version`, `chart`, `heritage` from `_helpers/elements/labels.tpl`) requires extending this allow-list.

## 5. What to scrape

The GroundX metrics service exposes:

| Metric family | Sample names | Cardinality |
| --- | --- | --- |
| Pipeline | `groundx_pipeline_throughput_tpm` | 1 series |
| API latency | `groundx_api_latency_ms_<bucket>` | One series per API pod (extract-api, layout-api, summary-api, workspace-api, etc.) |
| Queue backlog | `groundx_queue_backlog{queue="<name>"}` | One per queue (5 pipeline topics + workspace worker queues) |
| Task backlog | `groundx_task_backlog{worker="<name>"}` | One per task worker (`layout.ocr`, `extract.agent`, `workspace.command`, etc.) |
| Inference throughput | `groundx_inference_throughput{model="<name>"}` | One per inference pod |

The chart-rendered metric names and cardinality are governed by the metrics service code (application-level), not the chart helpers. The chart's role is exposing the endpoint; the application defines the metrics.

For the canonical set scraped by the reference dashboard, see `monitoring/groundx-dashboard.json` and the underlying PromQL queries it uses.

## 6. What NOT to scrape

The chart's metrics endpoint is the **summary signal** — aggregated, low-cardinality. For per-pod observability:

- **Don't scrape every GroundX pod individually.** The metrics service does the aggregation. Per-pod scraping multiplies time-series count without adding diagnostic value.
- **Don't scrape the inference pods directly.** They expose CUDA-level metrics via DCGM (when DCGM exporter is enabled by the GPU Operator — see `gpu-operator.md` § 1). The metrics service handles inference-level summarization.
- **Don't scrape the backing services (Redis, MySQL, OpenSearch, Kafka) via the GroundX metrics service.** Use their own exporters: `redis_exporter`, `mysqld_exporter`, OpenSearch's built-in metrics endpoint, Strimzi's Kafka Exporter.

## 7. Per-cluster monitoring layout

A typical production layout:

```
┌─────────────────────────────────────┐
│  monitoring namespace               │
│  ├── kube-prometheus-stack          │
│  │   ├── prometheus                 │
│  │   ├── grafana                    │
│  │   └── alertmanager               │
│  └── ServiceMonitor → metrics svc   │
└─────────────────────────────────────┘
                  │
                  │ scrapes
                  ▼
┌─────────────────────────────────────┐
│  eyelevel namespace                 │
│  ├── metrics (chart-deployed)       │
│  ├── groundx, layout, ranker, ...   │
│  └── (backing services + exporters) │
└─────────────────────────────────────┘
```

Prometheus lives in `monitoring`, scrapes the GroundX `metrics` service in `eyelevel` via the ServiceMonitor. Grafana queries Prometheus. Alertmanager handles alert routing to the deployer's chosen incident tooling.

## 8. Dashboards

The reference `monitoring/groundx-dashboard.json` includes panels for:

- **Pipeline throughput** — tokens/min over time, by pod group.
- **Queue depths** — message counts per pipeline queue (`pre-process`, `process`, `summary`, `update`, `upload`).
- **API latency** — p50/p95/p99 by API pod.
- **Inference throughput** — requests/min per inference pod (layout, ranker, summary).
- **Resource utilization** — CPU/memory per pod, GPU memory per inference pod (when DCGM is exporting).

Import via Grafana UI: Dashboards → Import → Upload JSON. Or via Grafana provisioning ConfigMap if Grafana is managed declaratively.

## 9. Alerting

The chart does NOT ship Prometheus alerting rules. Deployers define alerts per their operational requirements. Common starters:

- Pipeline throughput drop > 50% from baseline (suggests pipeline stall).
- Any queue depth growing for > 5 minutes (suggests worker undercapacity).
- API latency p99 > 30s (suggests upstream issue).
- Inference throughput zero for > 1 minute (suggests GPU failure).
- HPA at `replicas.max` for > 10 minutes (suggests cluster capacity exhaustion).

For the architectural framing of alerting, route to `groundx-architecture/references/observability.md` § 5.

## 10. Cross-field implications

| Set this... | …and this is implied or required |
| --- | --- |
| `metrics.serviceMonitor.enabled: true` | Prometheus Operator must be installed (i.e., the `monitoring/.../prometheus.servicemonitor` CRD must exist). Otherwise the chart-rendered ServiceMonitor is orphan. |
| `metrics.enabled: false` | No `/metrics` endpoint; HPAs (if any) have no signal; monitoring stack has nothing to scrape. Set both to `true` together for autoscaling-grade observability. |
| Custom queue names (e.g., `workspace.command.queue: my-q`) | Make sure the metrics service is wired to scrape from your new queue. The chart's metrics-config-rendering aligns this automatically; manual queue renames outside the chart break the link. |
| Multi-cluster monitoring | The chart doesn't multiplex across clusters. Run a separate Prometheus per cluster, or aggregate via Thanos / Cortex / Mimir at the upper layer. |

## 11. What this file does not cover

- **Autoscaling that consumes these metrics** → `autoscaling.md`.
- **GPU metrics via DCGM** → `gpu-operator.md` § 1 (the DCGM exporter is an operator feature, not GroundX-side).
- **Application-layer logs / tracing** (OpenTelemetry, structured logging) → out of chart scope; application-side.
- **Per-cluster alerting rules** → deployer responsibility; out of chart scope.
- **Multi-cluster aggregation** (Thanos, Cortex, Mimir) → upstream Prometheus ecosystem.
- **Architectural framing of GroundX observability** → `groundx-architecture/references/observability.md`.
- **Detailed Prometheus / Grafana setup** → `monitoring/README.md` in the upstream `groundx-on-prem` repo.
