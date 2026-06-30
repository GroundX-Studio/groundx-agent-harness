# Observability

GroundX's observability surface has four layers: **metrics** (via the `metrics` pod, with each pod reporting to Redis and the `metrics` pod producing the exposed Prometheus output), **logs** (CloudWatch in the cloud service; stdout on-prem; partially-migrated JSON structured format), **traces** (OpenTelemetry, partially implemented), and **customer-facing health surfaces** (`GET /v1/health` exposing two services — search and ingest — with a status that updates every 5 minutes from active pre-flight probes). In cloud, the customer-facing health endpoint is service-level availability monitoring, not a root-cause diagnostic surface; on-prem operators use Prometheus / Grafana metrics for deeper application-health diagnosis. There are **no published SLOs** and cloud alerts route to **Slack**. This file documents the observability shape; depth on individual signals lives with the producing subsystem.

## 1. Marketing altitude

Observability is an operator concern, not a marketing surface. Customer-facing observability is small (the `/v1/health` endpoint + per-customer quota meters); marketing claims about reliability defer to customer SLAs and deployment-level operational contracts, which are outside this skill.

## 2. Product altitude

Customers see observability in two places: the `GET /v1/health` endpoint (service-level status of `search` and `ingest`, refreshed every 5 minutes by active probes) and the per-customer quota meters exposed on `GET /v1/customer` (token usage, search counts; per `multi-tenancy.md`). Operators see the rest — pod-level metrics on the `metrics` pod's Prometheus surface, logs in CloudWatch (cloud) or whatever the deployer wires (on-prem), partial OpenTelemetry traces, and Slack alerts wired to the cloud service. In cloud, `/v1/health` should be treated as available / unavailable service health; in on-prem deployments, Prometheus and Grafana are the application-health diagnostic surface.

## 3. Conceptual / algorithmic altitude

Three architectural ideas shape observability:

**Metrics flow through Redis, exposed by a single pod.** Each pod reports its own metrics to Redis; the `metrics` pod reads from Redis and produces the Prometheus-compatible exposed surface. This avoids each pod exposing its own Prometheus scrape endpoint (a coordination cost at HPA-scaled pod counts) and centralizes the metric-shape decisions in one place. The trade-off: the `metrics` pod is a single point of metric-availability failure; if it's down, autoscaling and dashboards lose their signal.

**Logs and traces are partially migrated.** The format and stack story is **transitional**: log format is migrating from plain text to JSON structured (partial today); tracing is migrating to full OpenTelemetry coverage (partial today). At this skill's altitude, both surfaces should be described as "partial — migration in progress" rather than as committed contracts.

**Health endpoints are externally verified by active probing.** `UpdateHealthStatus` (cloud-service Lambda) runs every 5 minutes — submits a test search query and verifies the `summary-client` service's health. The output drives the `GET /v1/health` endpoint. This is an external-perspective probe (does a real search work? does the summary path respond?) rather than an internal-state aggregation (are pods running?). For on-prem deployments this Lambda doesn't exist; the deployer would need an equivalent.

## 4. System altitude

```
Metrics:
  Per-pod metrics  → Redis  → metrics pod  → Prometheus-compatible /metrics
                                          → Grafana dashboards (cloud service)
                                          → Prometheus Operator + ServiceMonitor (optional, on-prem)

Logs:
  Per-pod stdout
    Cloud service  → CloudWatch
    On-prem        → stdout (deployer wires the collection layer)
  Format: partial JSON structured (migration in progress); plain text otherwise
  Log levels in use

Traces:
  OpenTelemetry, partially implemented (migration in progress)

Health (customer-facing):
  GET /v1/health            (all services)
  GET /v1/health/{service}  (specific service)
  Statuses refreshed every 5 min by UpdateHealthStatus Lambda (cloud)
    - Submits test search query
    - Checks summary-client service health
  Services surfaced: search, ingest

Alerts:
  Cloud: Slack (stuck-document monitor critical errors; alert webhooks)
  On-prem: deployer's choice (AlertManager via Prometheus Operator typical)

Audit log:
  groundx pod emits API-request audit log entries as log messages
  Lands in same logging stack as ops logs
  Retention: 1 year cloud (SOC2 contract); on-prem operator's choice
```

For the metrics signals' canonical categories see `overview.md` § 4.7. For health endpoint shape see `groundx-api` § customer-and-keys.

## 5. Implementation altitude

### 5.1 Metrics

| Layer | Mechanism |
| --- | --- |
| Emission (per pod) | Each pod writes metric data points to Redis |
| Aggregation | The `metrics` pod reads from Redis, computes the exposed series, and serves the Prometheus-compatible endpoint |
| HPA signal | The `metrics` pod's series drive HPA on every other pod |
| Scrape (cloud service) | Grafana / Prometheus consumes the `metrics` pod's surface |
| Scrape (on-prem) | Prometheus Operator + ServiceMonitor (optional, configured in Helm) |

**Metric categories (per `overview.md` § 4.7):**

| Category | Measured | Pods covered |
| --- | --- | --- |
| API | Response time threshold | `groundx`, `layout-api`, `layoutWebhook`, `extract-api`, `workspace-api` |
| Queue | Back-pressure threshold | `pre-process`, `process`, `queue`, `upload`, `summary-client` (external-LLM mode) |
| Task | Celery task back-pressure threshold | All layout sub-pods, all extract sub-pods, all workspace sub-pods |
| Inference | Tokens per minute | `layout-inference`, `summary-inference`, `summary-api`, `summary-client` (external-LLM mode) |
| System-overall | Estimated TPM (autoscaling signal) | `document`, `page`, `extractRequest`, `summaryRequest` — every pod scales against these |

### 5.2 Logs

| Aspect | Cloud service | On-prem |
| --- | --- | --- |
| Destination | CloudWatch | stdout (collected by whatever the deployer wires) |
| Format | Partial JSON structured (migration in progress); plain text where unmigrated | Same migration state |
| Log levels | In use (debug / info / warn / error etc.) | Same |
| Retention | Per the CloudWatch log-group retention policy + SOC2 (1 year for audit) | Deployer's choice |

### 5.3 Audit log

The `groundx` pod emits an entry for every authenticated API request to the standard log stream — same destination as ops logs (per § 5.2). This is the comprehensive audit log (per `identity-and-trust.md` § 6.1). Retention is **1 year in the cloud service per SOC2**; on-prem retention is the deployer's choice (per `data-residency.md` § 6.2). There is no separate audit-log bucket or audit-log database.

### 5.4 Distributed tracing

OpenTelemetry is the chosen tracing stack. **Coverage is partial today** — migration to full coverage is in progress. The architecture skill should not claim a specific trace shape or coverage promise at this altitude. The migration target is per-request distributed traces across the ingest pipeline and search path.

### 5.5 Health endpoints

| Endpoint | Returns |
| --- | --- |
| `GET /v1/health` | Status of both services (`search`, `ingest`) with `lastUpdate` timestamps |
| `GET /v1/health/{service}` | Status of the named service only |

Status values: `healthy` / `degraded` / `down` / `unknown`. Statuses refresh every 5 minutes (cloud service) driven by `UpdateHealthStatus`. For the response schema and pre-flight-check example pattern see `groundx-api/references/07-customer-and-keys.md` § 6–7.

### 5.6 `UpdateHealthStatus` Lambda (cloud-service only)

Runs every 5 minutes. Two probes per invocation:

1. **Search probe** — submits a test search query against a fixed bucket; verifies the search path (groundx → OpenSearch → ranker pair → groundx → response) is functional end-to-end.
2. **Summary probe** — checks the health status of the `summary-client` service.

Output drives the `/v1/health` endpoint's `services` array. On-prem deployments need their own equivalent (or accept that `/v1/health` won't be populated).

### 5.7 Alerting

| Surface | Mechanism |
| --- | --- |
| Cloud service | Slack — stuck-document monitor critical errors (per `disaster-recovery.md` § 5.6) emit to a configured Slack webhook; other cloud-side alerting flows through Slack |
| On-prem | Deployer's choice — Prometheus Operator's AlertManager is a common path with the optional ServiceMonitor integration |

### 5.8 SLOs

**No published or internal SLO commitments today.** The architecture has the signals required to define SLOs (search p99 latency, ingest-to-retrievable time, uptime %), but no commitments are published, nor are they committed in this skill. Customer-contract-specific commitments live in the operational agreements, not at this skill's altitude.

## 6. Security / compliance altitude

The audit log is the only authoritative record of customer-tier and partner-tier API actions (per `identity-and-trust.md` § 6.1). Retention is bound to SOC2 in the cloud service (1 year, per `data-residency.md` § 6.2). Logging stack access — who can read CloudWatch log groups, who can query — is part of the deployment's operational contract (cloud: GroundX SRE controls; on-prem: deployer's controls), not architectural.

## 7. Operations / SRE altitude

The metric signals + the cloud stuck-document monitor + Slack alerting form the in-production operability surface today. Tracing coverage is partial and growing. Logging is structurally complete (every pod logs) but format-wise transitional (JSON migration in progress).

**Known operational gaps:**

- The `metrics` pod is a single point of metric-availability failure; if it's down, HPA loses its signal and autoscaling stalls.
- No published SLOs; customer expectations of latency / uptime live in customer contracts only.
- On-prem deployments don't get `UpdateHealthStatus` or the Slack alerts wired by default.

## 8. Data architecture altitude

The metric data points flow through Redis (per § 5.1) — Redis carries the in-flight metric state until the `metrics` pod aggregates. This is the largest non-cache use of Redis in the architecture (alongside the cached auth records and frequently-used API query results, per `store.md` § 5.2). The audit log lives in the same logging stack as ops logs (CloudWatch / stdout); it is not a separate data store. Trace data, when emitted, follows the OpenTelemetry stack configured at the deployment level.

## 9. Cost / FinOps altitude

Observability cost is mostly in the logging stack — CloudWatch log ingestion + storage at scale can become a material line item, particularly under the SOC2 1-year retention. Metrics infrastructure cost (Redis ↔ `metrics` pod ↔ Prometheus / Grafana) is comparatively small at default deployment scale. Tracing cost depends on OpenTelemetry sampling rate, which is not specified at this skill's altitude.

Deployment-level cost framing is owned by `groundx-on-prem`.

## 10. What this topic does not cover

- **The auth surfaces emitting the audit-log entries**: `identity-and-trust.md` § 5–6.
- **The audit-log retention policy and right-to-be-forgotten interaction**: `data-residency.md` § 6.2.
- **The cloud stuck-document monitor behavior + cutoffs**: `disaster-recovery.md` § 5.6.
- **The full cloud function inventory**: cloud-service operator guidance.
- **The customer-tier `/v1/health` response shape and pre-flight check pattern**: `groundx-api` § customer-and-keys.
- **Per-pod HPA tuning, replica defaults, autoscaling specifics**: `groundx-on-prem`.
- **What fails how + per-failure customer-impact lens**: `failure-modes.md`.
- **OpenTelemetry trace shape and coverage commitments**: not committed at this skill's altitude; migration in progress.
- **Public SLO commitments**: not made; customer-contract specifics live in operational agreements.
