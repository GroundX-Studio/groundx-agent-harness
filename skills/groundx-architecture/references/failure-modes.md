# Failure Modes

This file documents the failure scenarios GroundX is known to handle, the recovery pattern for each, and the customer-impact lens. It combines a **structural inventory** (what fails-open vs fails-closed by subsystem) with a **scenarios catalog** (what to do when X happens). The cloud stuck-document monitor (cloud-service only, per `disaster-recovery.md` § 5.6) recovers stuck-document scenarios at layout and extract steps; everything else is per-subsystem retry behavior plus Kubernetes pod-restart defaults.

## 1. Marketing altitude

Failure modes stay out of marketing content.

## 2. Product altitude

Most transient failures recover automatically: pod crashes restart, stuck documents get re-routed by the cloud stuck-document monitor after a cutoff, 3rd-party LLM errors trigger retries with backoff, OpenSearch read errors retry up to 3 times. Some failures cause the document to fail outright — file storage write failures during the terminal `process` step, MySQL/RDS unavailability at the API ingress, or Redis-cache-miss conditions that cascade through Celery. Customers experience failures as either delayed ingest (recoverable, transparent) or failed document ingests (visible in `GET /v1/ingest/{processId}` status).

## 3. Conceptual / algorithmic altitude

Three architectural ideas drive failure handling:

**Retry where retry helps; fail where retry doesn't.** External dependencies (3rd-party LLMs, OpenSearch reads) are retried because they have transient-failure characteristics. Store writes at the terminal step (`process` writing to file storage / OpenSearch / MySQL) fail the document because re-trying a partial write would leave an inconsistent terminal state. Auth-tier failures (MySQL/RDS unavailable, Redis unavailable for Celery state) fail closed because operating with broken auth or broken queue state is worse than failing.

**Stateless pods + queue handoff make Kubernetes-default recovery sufficient for pod-loss scenarios.** A pod that crashes loses any in-memory work; Kubernetes restarts the crashed container in place (same pod); the queue retries the message. Celery retry configuration governs how many times a task retries before giving up, but only for a raised exception the task explicitly retries through the retry API — a worker loss (its process killed mid-task, e.g. by OOM) does not by itself count toward that limit. Soft timeouts (~600s) catch stuck-but-not-crashed work. For `layout-process` specifically, on an image built from `ai-server` with the GX-61 change, a worker loss is bounded to three total attempts (the initial attempt plus two retries), after which the task attempts the existing terminal failure callback and acknowledges the message, so the document does not loop forever; the other five Celery layout pods (`layout-inference`, `layout-ocr`, `layout-map`, `layout-save`, `layout-correct`) redeliver a lost worker's task without that bound. `layout-api` is the layout pipeline's HTTP entry point — a gunicorn pod with no Celery queue of its own — so neither the bound nor the unbounded-redelivery description applies to it.

**The cloud stuck-document monitor covers the residual.** Some documents end up in a "started processing, never finished" state without a hard error (Celery task silently dropped, pod went away mid-step, etc.). The monitor is the recovery for this scenario — checks for documents whose `updated` timestamp is older than the per-stage cutoff and re-routes them.

## 4. System altitude

```
External dependencies (retried):
  3rd-party LLM enrichment call from summary-client
    → 3 retries with progressive backoff
    → no usable content after retries: document completes if still saveable/indexable;
      failed enrichment is recorded in statusMessage
    → hard provider or structural failures still fail the document
  OpenSearch read from groundx (search path)
    → 3 retries with sleep between (non-progressive)
    → after 3 retries, error returned to caller
  ranker-inference call from groundx (search path)
    → if cloud: fall back to OpenAI for the score
    → if on-prem: failure
  GCV API (when configured for OCR)
    → behavior governed by the GCV client library; not separately documented

Store writes:
  File storage write at process step  → failure (document fails)
  OpenSearch write at process step    → failure (document fails)
  MySQL/RDS write at process step     → failure (document fails)

Store dependencies for the auth path:
  MySQL/RDS unavailable              → fail closed (groundx cannot serve requests)
  Redis unavailable                  → Celery tasks fail (uses Redis as broker); document fails

Pipeline pod crashes mid-document:
  Celery retries via Celery configuration, but a worker loss (process killed mid-task) is not
    counted toward max_retries unless the task explicitly checks for it — the other five Celery
    layout pods (layout-inference, layout-ocr, layout-map, layout-save, layout-correct) redeliver
    a lost worker's task without a bound. layout-api has no Celery queue (HTTP entry point only).
  layout-process (on an image built from ai-server with the GX-61 change): bounded to three total
    attempts (initial attempt plus two retries), then one terminal failure callback attempt and
    message acknowledgement, so the document does not loop
  Celery soft timeouts: ~600 seconds
  Kubernetes restarts the crashed container in place (same pod, default backoff); a pool-worker
    child process killed alone is recovered by Celery respawning that worker, no container/pod
    restart

Stuck-document recovery:
  Cloud stuck-document monitor (cloud-service only)
    - layoutCutoff: 60 minutes
    - extractCutoff: 30 minutes
    - 10 documents per invocation
    - Routes documents through the normal processing path

Queue overflow (Kafka / SQS over-capacity):
  Not observed in production; behavior undocumented; presumed message loss
```

## 5. Implementation altitude

### 5.1 Failure-by-subsystem inventory

| Subsystem | Failure scenario | Recovery behavior | Customer impact |
| --- | --- | --- | --- |
| **`summary-client` → 3rd-party LLM enrichment** | No usable enrichment content after retries | **Progressive-backoff retry, up to 3 attempts.** After retry exhaustion, the document still completes if it can be saved and indexed; the failed enrichment request is recorded in `statusMessage`. | Document completes ingest on the content that succeeded; customers can inspect `statusMessage` for partial enrichment failures. |
| **`summary-client` → 3rd-party LLM hard failure** | Hard provider rejection / timeout / structural error | **Progressive-backoff retry, up to 3 attempts.** After retries, the document fails through the normal failure path. | Document does not complete ingest; customer sees failure via `/v1/ingest/{processId}` status (and via callback, if attached, per `integration-architecture.md` § 5.2). |
| **`groundx` → OpenSearch read** (search path) | OpenSearch read error / timeout | **3 retries with a sleep between** (non-progressive). After 3 retries, error returned to the caller. | Search request returns an error to the caller; no degraded fallback to keyword-only |
| **`groundx` → `ranker-api` → `ranker-inference`** (search path) | Ranker error / GPU OOM / timeout | **Cloud-service deployments fall back to calling OpenAI** for the score. **On-prem deployments fail** (no fallback). | Cloud: degraded result (still ranked, via different scoring); on-prem: search request fails |
| **`process` → file storage write** (terminal step) | S3/MinIO write fails | **Document fails.** No inline retry; the terminal write is treated as a hard fail. | Document ingest marked failed |
| **`process` → OpenSearch write** (terminal step) | OpenSearch write fails | **Document fails.** | Document ingest marked failed; chunks not indexed |
| **`process` → MySQL/RDS write** (terminal step) | RDS write fails | **Document fails.** | Document ingest marked failed |
| **`groundx` ingress → MySQL/RDS auth lookup** | RDS unavailable on cache miss | **Fails closed.** `groundx` cannot serve requests requiring auth. | API requests return errors; service-level outage from the customer's perspective |
| **Redis unavailable** (Celery broker; auth cache) | Redis down | **Celery tasks fail because the broker is unavailable; documents fail.** Auth cache misses cascade to MySQL/RDS (degraded latency, not failure, on the auth path alone). | Ingest and document-processing fail; search may still serve if the request hits a path that doesn't touch Celery |
| **`layout-process` pod crash mid-document** (worker OOM-killed or otherwise lost, on an image built from `ai-server` with the GX-61 change) | Pod goes down | **Bounded to three total attempts** (initial attempt plus two retries), then one terminal failure callback attempt and message acknowledgement, so the document does not loop. On nodes that kill the whole container on OOM, every process in the container (the wrapping shell and its children, including the Celery worker) is killed together, so Kubernetes restarts the crashed container in place, same pod, between attempts. On nodes where only the worker process is killed, the container's other processes survive, so Celery respawns that worker inside the still-running container, with no container or pod restart, and the next attempt starts immediately rather than waiting on the broker's visibility timeout. | Document proceeds if a retry succeeds; after three attempts, document fails via the terminal callback. GroundX cloud's stuck-document monitor may resubmit a document still active 60 minutes after its last update, starting a fresh three-attempt budget as a new Celery message; on-prem has no stuck-document monitor, so the document stays in its last-reported failed state until a human or a future ticket acts on it |
| **Other layout pipeline pod crash mid-document** (the other 5 Celery layout pods: `layout-inference`, `layout-ocr`, `layout-map`, `layout-save`, `layout-correct`; `layout-api` is the layout pipeline's HTTP entry point — a gunicorn pod with no Celery queue of its own — and is not part of this row) | Pod goes down | **Celery retries the task** per Celery configuration, but only for a raised exception the task explicitly retries through the retry API — a worker loss (its process killed mid-task, e.g. OOM) does not count toward `max_retries` for these five pods, so the broker redelivers a lost worker's task without a bound. Soft timeouts ~600 seconds catch stuck-but-not-crashed work. On nodes that kill the whole container on OOM, Kubernetes restarts the crashed container in place, same pod; on nodes where only the worker process is killed, Celery respawns that worker within the still-running container, with no container or pod restart. | Document may proceed after retry; if the worker loss keeps recurring, the document keeps looping (no bound), or if a raised, explicitly-retried error exhausts its retries, the document fails. The cloud stuck-document monitor covers stuck cases |
| **Pod CrashLoopBackOff** | Pod can't start | **Kubernetes default backoff.** Operator intervention typically required to diagnose. | In-flight work may be lost; re-ingest may be required depending on which step crashed |
| **Queue overflow** (Kafka / SQS over-capacity) | Queue rejects new messages | **Not observed in production; behavior undocumented;** presumed message loss for new ingests. | Speculative: new ingests may fail to enqueue; existing in-flight work continues |
| **AZ outage** (cloud service) | One AZ goes offline | RDS / OpenSearch / S3 fail over automatically per managed-service defaults; Kubernetes reschedules pods to surviving AZs | Transparent to customers in most cases; transient pod restarts may cause brief delays |
| **Regional outage** (cloud service us-west-2) | Whole region offline | No automatic recovery (no cross-region replica per `data-residency.md`); manual restore from snapshots into another region required | Complete service outage until manual recovery |
| **Stuck document at layout or extract** | Document's `updated` timestamp goes stale | A cloud-service monitor detects past the cutoff (60 min layout, 30 min extract), resets processor state to Queued, and routes the document through the normal processing pipeline. 10 docs per invocation. | Document eventually re-processes; user-visible delay equals cutoff + queue depth |

*Sources: per-subsystem retry behavior (LLM 3 progressive, OpenSearch 3 with sleep, terminal-write failures, ranker fallback) — scoped internal-review finding, 2026-05-17. Cloud stuck-document monitor cutoffs and re-route mechanics — scoped internal-review finding, 2026-05-17. Queue-overflow behavior is genuinely unobserved in production; framing is explicit as such.*

### 5.2 Fails-open vs fails-closed by boundary

| Boundary | Behavior |
| --- | --- |
| `groundx` auth check (RDS down) | Fails closed |
| `groundx` auth check (Redis down) | Falls through to RDS — fails open at the cache layer (degraded latency) |
| Celery broker (Redis down) | Fails closed for queued work |
| 3rd-party LLM no-content enrichment exhaustion (summary path) | Fails open to completed ingest with `statusMessage` partial-failure detail |
| 3rd-party LLM hard failure (summary path) | Fails closed after retries |
| 3rd-party LLM (ranker fallback, cloud only) | Fails open — used as fallback when self-hosted ranker fails |
| OpenSearch read (search path) | Fails closed after 3 retries |
| OpenSearch write (`process` terminal step) | Fails closed — document fails |
| File storage write (`process` terminal step) | Fails closed — document fails |
| Pod crash mid-document (layout / extract steps) | Fails to a retry (Celery) — fails open transiently, may fail closed after retries exhausted. For `layout-process` specifically, the fail-closed terminal callback fires once a fixed three-attempt budget (initial attempt plus two retries) is exhausted, not an open-ended retry; the extract steps and the other five Celery layout pods (`layout-inference`, `layout-ocr`, `layout-map`, `layout-save`, `layout-correct`) retain the generic Celery-retry description. `layout-api` has no Celery queue and is not part of this row |
| AZ outage | Fails open — managed-service defaults handle it |
| Regional outage | Fails closed — no automatic recovery |

### 5.3 Customer-visible signals

When a document fails, the customer sees:

- `GET /v1/ingest/{processId}` returns the failure status with a status message (per `groundx-api`).
- If a `callbackUrl` was attached, the callback POST fires once with the failure outcome (per `integration-architecture.md` § 5.2). **No retries** on the callback — if the customer's endpoint is down, the customer must poll.

When a document completes with partial summary enrichment failure, the customer sees completed
ingest plus `statusMessage` detail identifying the failed enrichment request. The document remains
searchable on the content that was successfully saved and indexed.

When the search path fails (OpenSearch read or ranker), the customer sees an error response from `groundx`. There is no degraded-mode fallback for search beyond the ranker → OpenAI fallback in the cloud service.

### 5.4 Operator-visible signals

| Failure shape | Where operators see it |
| --- | --- |
| Stuck-document detection + re-route | Hosted-cloud operator alerting via the stuck-document monitor critical-error path |
| Layout or extract callback-handler failure | Hosted-cloud operator alerting via the GroundX-side `layoutWebhook` critical alert path, plus callback-handler logs |
| Hosted workspace pod alert | No sourced route in this reference; do not claim one unless the GroundX partner/workspace route proves it |
| Pod CrashLoopBackOff | Kubernetes events; metrics pod via queue back-pressure (eventually) |
| 3rd-party LLM summary enrichment retry exhaustion or hard failure | Logs in CloudWatch (cloud) / stdout (on-prem) on the `summary-client` pod |
| Queue back-pressure exceeding threshold | The metrics pod's queue-back-pressure signal — drives HPA scale-out |
| AZ outage | CloudWatch (cloud) — managed-service alarms |
| Audit-log queries (compliance investigation) | The same logging stack as ops logs (per `observability.md` § 5.3) |

## 6. Security / compliance altitude

Failures that lose data (queue overflow with presumed message loss; regional outage with no replica) are operationally significant for compliance — they undermine implicit-availability claims in customer contracts. The architecture skill does not commit to availability targets at this altitude; customer contracts carry the specifics. The audit log retains evidence of failed API calls (per `identity-and-trust.md` § 6.1); operators investigating compliance-relevant failures use the audit log as the source of record.

## 7. Operations / SRE altitude

The operational triage tree for a customer-reported failed document:

1. Check `GET /v1/ingest/{processId}` for the error status message.
2. Check stuck-document monitor operator notifications — was the document detected as stuck and re-routed?
3. Check `summary-client` logs for 3rd-party LLM errors.
4. Check `process` pod logs for terminal-write failures.
5. Check the metrics pod for queue depth and inference TPM anomalies.

For broader observability framing see `observability.md`. For cloud stuck-document monitor behavior see `disaster-recovery.md` § 5.6.

## 8. Data architecture altitude

Failures that touch state:

- **Terminal `process` failures** leave the document in a failed state in the process-metadata DB but do not leave inconsistent state across the stores — `process` writes are gated; the document doesn't appear in OpenSearch unless all three writes succeed.
- **Cloud stuck-document monitor re-route** preserves the document's identity (same `documentId` / `taskId`); processing restarts from the failing step, re-using intermediate artifacts already in file storage where they exist.
- **Customer / bucket / document delete during in-flight processing** — interaction not documented. The deletion endpoints (per `data-residency.md` § 5.4) and the in-flight ingest paths could in principle race; whether the architecture handles this gracefully is not specified. Flagged as a known-unknown.

## 9. Cost / FinOps altitude

Retry storms (e.g., a sustained 3rd-party LLM outage producing thousands of retried calls) can drive transient cost spikes on the LLM provider's billing surface. The 3-retry cap on the summary path bounds this. OpenSearch read retries (3 with sleep) don't materially affect cost — OpenSearch capacity is provisioned per-node, not per-call. For broader cost-shape framing see `data-flow.md` § 9; deployment-level cost is owned by `groundx-on-prem`.

## 10. What this topic does not cover

- **The cloud stuck-document monitor behavior + cutoffs**: `disaster-recovery.md` § 5.6.
- **The metrics-pod-driven HPA signal flow**: `observability.md` § 5.1.
- **The audit log as a failure-investigation source**: `identity-and-trust.md` § 6.1 + `observability.md` § 5.3.
- **The callback delivery contract** (one POST per document, no retries): `integration-architecture.md` § 5.2 + § 7.
- **The X-Ray + JSONL terminal-write contract** (what `process` is writing when it fails): `agentic-pipeline.md` § 8 + `store.md` § 5.
- **The cascade-delete contract that interacts with in-flight processing**: `data-residency.md` § 5.4.
- **Per-pod operator runbooks** (specific logs to check, specific commands to run): `groundx-on-prem`.
- **Customer-contract availability commitments**: not at this skill's altitude; operational-agreement specifics.
- **Backup-restore behavior in detail**: `disaster-recovery.md`.
