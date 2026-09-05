# Monitoring — Prometheus + Grafana + ServiceMonitor

This file documents **how to wire GroundX metrics into a Prometheus + Grafana stack** — what the chart exposes, the upstream `monitoring/` directory's reference setup (`values.prometheus.yaml`, `service-monitor.yaml`, `groundx-dashboard.json`), and what to scrape vs ignore.

For the autoscaling that consumes these metrics, route to `autoscaling.md`. For per-pod resource sizing visible in metrics, route to `node-groups.md` and `cluster-requirements.md`. For end-to-end observability architecture, route to `groundx-architecture/references/observability.md`.

## 1. What the chart exposes

When `metrics.enabled: true`, the chart deploys a single metrics service pod that exposes a `/metrics` endpoint on the service `metrics.<namespace>.svc.cluster.local`. The endpoint surfaces:

- **Pipeline throughput** — total estimated throughput for files moving through GroundX.
- **API latency** — request-response latency per API pod.
- **Queue backlog** — message count per queue.
- **Task backlog** — Celery task count per worker.
- **Inference request throughput** — model request rate per inference pod.

These are the same metrics the HPA consumes for autoscaling (`autoscaling.md` § 5). With monitoring enabled, the metrics are also available for dashboards.

## 2. Apply the separate ServiceMonitor manifest

The GroundX chart **does not render** a `ServiceMonitor`. For Prometheus Operator users, first enable the chart's metrics endpoint:

```yaml
metrics:
  enabled: true
```

Then inspect and apply the separate manifest shipped by the upstream repository:

```sh
kubectl apply -f monitoring/service-monitor.yaml
```

That manifest creates `groundx-metrics` in the `monitoring` namespace, selects the `app: metrics` Service in `eyelevel`, and scrapes its HTTPS target on port 8443. Adjust its namespaces, release label, selector, and TLS policy before applying it when the deployment differs from those defaults.

The similarly named `metrics.serviceMonitor.enabled` values flag only controls whether the metrics chart template may create a missing metrics `ServiceAccount`: `true` permits creation and `false` suppresses it. It does not register anything with Prometheus. The account name resolves from `metrics.serviceAccount.name`, then the global `serviceAccount.name`, then the default `metrics`. The canonical prerequisite chart creates `s3-sqs-worker`, not `metrics`. Unless the resolved name points to an account that already exists, set this flag to `true` so the chart can create it; otherwise the Deployment references an account that does not exist. This flag is still not a substitute for applying the external ServiceMonitor manifest.

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
kubectl apply -f monitoring/service-monitor.yaml

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
| Apply `monitoring/service-monitor.yaml` | Prometheus Operator and the `monitoring.coreos.com/v1` ServiceMonitor CRD must exist. Check the manifest's `monitoring` / `eyelevel` namespaces, `release: monitoring` label, selector, and TLS policy before applying it. |
| `metrics.serviceMonitor.enabled: true` | Allows the metrics template to create its `ServiceAccount` when absent. It does **not** render a ServiceMonitor or replace the separate manifest step. |
| `metrics.enabled: false` | No `/metrics` endpoint; HPAs (if any) have no signal; monitoring stack has nothing to scrape. Set both to `true` together for autoscaling-grade observability. |
| Custom queue names (e.g., `workspace.command.queue: my-q`) | Make sure the metrics service is wired to scrape from your new queue. The chart's metrics-config-rendering aligns this automatically; manual queue renames outside the chart break the link. |
| Multi-cluster monitoring | The chart doesn't multiplex across clusters. Run a separate Prometheus per cluster, or aggregate via Thanos / Cortex / Mimir at the upper layer. |

## 11. Following one document through the pipeline

Fleet metrics (§ 5) say whether the system is healthy. This section answers the other question — **"where is my document right now?"** — during the post-install smoke test (`install-flow.md` § 7.4) or whenever one specific document is stuck while the fleet looks fine.

**Get the identifiers right first.** Ingest returns an **ingest-job process ID** — poll the ingest-status endpoint with it (call shape → `groundx-api/`). The status response reports coarse states only (`queued`, `processing`, `complete`, …) — it never names an internal stage — and it identifies each **document ID** in the batch. Downstream worker logs key on the document (and its task), **not** the ingest-job ID, and a document also carries its own distinct lineage `processId` — see `groundx-api/references/02-documents.md` § 10.1 for the two-`processId` contract. Poll with the job ID; correlate everything below by **document ID**.

A document moves through pipeline stages; each stage has a transport you can measure and workloads you can log-tail:

| Stage | Transport | Workloads to log-tail (`-n eyelevel`, by label) |
| --- | --- | --- |
| Intake | `stream.topics.upload` and `stream.topics.preProcess` → default topics `file-upload`, `file-pre-process` | `app=upload`, `app=pre-process` |
| Dispatch | `stream.topics.process` → default topic `file-process` | `app=process` |
| Layout (correct → OCR ∥ layout → map → save, per page) | Celery over the `cache` Redis | `app=layout-process`, `app=layout-correct`, `app=layout-ocr`, `app=layout-map`, `app=layout-save`; GPU inference: `app=layout-inference` |
| Summary | `stream.topics.summary` → default topic `file-summary` | `app=summary-client`, `app=summary-api`; GPU inference: `app=summary-inference` |
| Finalize | `stream.topics.update` → default topic `file-update` | `app=queue` (status writer), served by the API (`app=groundx`) |

(Workload names and `file-*` topic names are the default render's; per-topic `topic`/`groupId` overrides and service-name overrides change them — read the deployed values first. The layout step order is the `ai-server` per-page chain: `correctImage` → `detectOCR` ∥ `detectLayout` → `detectMap` → save. `ranker-*` is search-time, not part of ingest.)

Diagnostic order — authoritative answer, then the systemic signal, then logs:

```bash
# 1) Poll ingest status with the JOB process ID; note the coarse state and
#    collect the affected DOCUMENT ID(s)  (shape → groundx-api/)

# 2) Is a stage's queue backing up (systemic), or is this one document stuck?
#    Start with groundx_queue_backlog (§ 5) from the metrics pod where it reports
#    your queues (its implementation ships in the metrics image — confirm coverage
#    on non-default transports); otherwise use the transport-specific checks:
#    Transport-specific (topics can be Kafka, SQS, or mixed per topic —
#    values-authoring.md § 3.5.5):
#      bundled Strimzi Kafka  — consumer-group lag (group IDs default to topic names):
kubectl get pods -n eyelevel -l strimzi.io/cluster=stream-cluster   # find a broker pod
kubectl exec -n eyelevel <kafka-broker-pod> -- \
  bin/kafka-consumer-groups.sh --bootstrap-server localhost:9092 \
  --describe --group file-process
#      external Kafka         — same query via your broker's approved client tooling
#      AWS SQS                — queue depth / in-flight / oldest-message age via
#                               CloudWatch or `aws sqs get-queue-attributes`

# 3) Log-tail the stages for this DOCUMENT. Derive the lookback from the
#    document's age (ingest start time, step 1) — a fixed 30m window on a
#    45m-old document misses the pickup event and fakes a "lost" diagnosis:
kubectl logs -n eyelevel -l app=layout-process --since=<document-age> --tail=5000 | grep -i <document-id>
# repeat across the stage labels in table order (intake → finalize) until the
# LAST event for this document is found; check the GPU inference pod for the
# layout/summary stages too
```

How to read the combination:

- **Status parked + stage queue backlog growing** → the stage is under-provisioned or its workers are failing; check the stage pods' restarts and route to `troubleshooting.md` § 4.
- **Status parked + queue drained** → locate the document's **last** logged event across the stage labels (lookback ≥ the document's age). Classify the task as lost mid-flight (worker OOM/crash after take) **only when a log line shows it was dequeued or started and nothing follows it**. On the layout stage's default Redis/Valkey Celery broker — late acknowledgement, no `visibility_timeout` override — a lost task redelivers only after the visibility timeout expires (~1 hour), so a long park followed by a spontaneous retry is this signature; SQS-backed topics redeliver per the queue's own visibility timeout instead (10+ minutes, values-authoring.md § 3.5.5), and deployments that override broker transport options differ. **If no stage ever logged the document**, it was never dispatched — step back to the previous stage's queue and workloads instead. Route to `troubleshooting.md` § 4.
- **Log lines show repeated re-processing of the same page/task** → a poison document or a task that dies at the same point each attempt; capture the log window before routing.

## 12. Monitoring on AWS CloudWatch / Container Insights

The chart's first-class monitoring path is Prometheus + Grafana (above). The chart ships no CloudWatch integration, but an AWS operator who runs observability on CloudWatch / Container Insights instead of Prometheus can bridge to it — the chart exposes the same signals, only the collection layer differs. Nothing in the chart changes; you add AWS-side collectors:

- **Metrics** — the metrics pod exposes a Prometheus-format `/metrics` endpoint (§ 1). Point a Prometheus-compatible CloudWatch collector at it: the **CloudWatch agent in Prometheus mode** or an **ADOT (AWS Distro for OpenTelemetry) collector** scraping `metrics.<namespace>.svc.cluster.local:443/metrics` and writing to a CloudWatch metrics namespace (the metrics Service exposes port `443`, forwarding to the pod's `8443`; a collector that reaches the Service by its DNS name must use `443`, not the pod port — the § 1 ServiceMonitor targets the pod's `8443` directly, which is why it differs). This is the same out-of-band scrape path noted in § 2 for non-operator Prometheus. The endpoint is HTTPS with a self-signed CA, so the collector needs the chart's `metrics-tls` CA (or `insecureSkipVerify`).
- **Logs** — GroundX pods log to stdout; the chart ships no log-shipping layer (deployer responsibility, `groundx-architecture/references/observability.md`). Ship container logs to CloudWatch Logs with **Fluent Bit** — the standard EKS log path; Container Insights installs a Fluent Bit DaemonSet that covers this. (FireLens is an ECS-only log router and does not apply to EKS; FluentD is deprecated for Container Insights.)
- **Alarms** — define **CloudWatch alarms** on the metrics you land (mirroring the starter conditions in § 9) plus the pod/queue signals Container Insights collects. The chart ships no alarm definitions (§ 9).

This is a bridge, not a chart feature: you own the collector install, the IAM (the agents need CloudWatch Logs + metrics permissions, grantable via IRSA like the roles in `terraform-aws.md` § 6), and the alarm definitions. If you run both Prometheus and CloudWatch, scrape the one `/metrics` endpoint from whichever collector you standardize on.

## 13. What this file does not cover

- **Autoscaling that consumes these metrics** → `autoscaling.md`.
- **GPU metrics via DCGM** → `gpu-operator.md` § 1 (the DCGM exporter is an operator feature, not GroundX-side).
- **Application-layer logs / tracing** (OpenTelemetry, structured logging) → out of chart scope; application-side.
- **Per-cluster alerting rules** → deployer responsibility; out of chart scope.
- **Multi-cluster aggregation** (Thanos, Cortex, Mimir) → upstream Prometheus ecosystem.
- **Architectural framing of GroundX observability** → `groundx-architecture/references/observability.md`.
- **Detailed Prometheus / Grafana setup** → `monitoring/README.md` in the upstream `groundx-on-prem` repo.
- **Full CloudWatch / Container Insights setup** (collector install, IAM policy authoring, log-group retention, dashboards) → deployer responsibility; § 12 gives the endpoint-and-logs bridge, not a full AWS runbook.
