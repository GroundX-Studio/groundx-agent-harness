# Disaster Recovery

GroundX's disaster-recovery posture is **inherited from the chosen backing services** — RDS, OpenSearch, S3 in the cloud service, or whichever equivalents `values.yaml` selects on-prem — plus a single in-cluster recovery mechanism (`MonitorPipeline` Lambda) for restarting ingest documents that get stuck at a pipeline step. There are **no documented RPO / RTO targets** beyond what's committed in customer contracts; **no cross-region replication** in the cloud service today; **no restore drills**; and DR responsibility on-prem is the deployer's. This file documents the actual posture, names the known gaps explicitly, and routes to the harness skills + `data-residency.md` for adjacent depth.

## 1. Marketing altitude

DR posture stays out of marketing content. The high-reliability story for marketing surfaces is owned by `master-brand-gtm` / `product-brand-gtm`; the architectural facts those claims rest on are here and in `data-residency.md`.

## 2. Product altitude

The cloud service relies on managed AWS services (RDS, OpenSearch, S3) for backup and durability — whatever AWS provides as the default for each service is what GroundX has. Within-region (multi-AZ) failover is transparent for the managed services; pods reschedule via Kubernetes when an AZ fails. **Cross-region failover is not a current capability** — the production cloud service runs in us-west-2 with no replica anywhere else.

A `MonitorPipeline` Lambda detects documents stuck at a pipeline step (layout or extract) past a cutoff and re-queues them. This is the in-cluster recovery mechanism for the most common operational failure: a document that started processing but stalled.

On-prem deployments inherit whatever the chosen backings provide; backup posture, cross-region recovery, and restore drilling are the deployer's responsibility.

## 3. Conceptual / algorithmic altitude

Three architectural ideas shape DR:

**Stateless pods + state-tier-owned durability.** Every pod in GroundX is stateless (per `overview.md` § 4.4); state lives in the three stores. Pod loss is recovery-by-restart with no per-pod state migration. The hard problem of DR — preserving state across failures — is delegated entirely to the store tier, which is delegated entirely to backing-service defaults.

**No replication beyond what backings provide.** The cloud service does not maintain its own backup layer on top of the managed services. RDS automated snapshots, OpenSearch automated snapshots, and S3's default durability are the entire backup posture. This is honest and operationally lean; the trade-off is that the recovery story matches AWS-managed-service defaults exactly, no better and no worse.

**Pipeline-level recovery via `MonitorPipeline`.** A Lambda runs on a CloudWatch schedule (cloud-service only), checks the process-metadata DB for documents whose `updated` timestamp is older than the cutoff for their current processor stage, and re-queues those documents to `pre-process` for retry. This recovers from a specific failure mode (a pod crashing mid-step or a Celery task silently dropping) without requiring per-document operator intervention.

## 4. System altitude

```
Cloud service (us-west-2):
  RDS              Automated snapshots + point-in-time recovery (AWS managed-service defaults)
  OpenSearch       Automated snapshots (default)
  S3               No versioning, no lifecycle policy beyond AWS defaults
  Multi-AZ         Default behavior of each managed service
  Cross-region     None (no replica in another region)

In-cluster recovery:
  MonitorPipeline (CloudWatch-triggered Lambda; cloud-service only)
    Scans process metadata DB for documents stuck past cutoff
      - extractCutoff = 30 minutes
      - layoutCutoff  = 60 minutes
    Resets processor status to Queued; bumps document's updated timestamp
    Re-enqueues to pre-process queue (file-pre-process)
    Repair limit: 10 documents per invocation
    Critical errors → Slack

On-prem:
  Backup posture, multi-AZ, restore drills, equivalent of MonitorPipeline:
  all deployer's responsibility
```

For the topology these mechanisms operate on see `overview.md`. For the stores being protected see `store.md`. For the residency posture and deletion mechanics see `data-residency.md`.

## 5. Implementation altitude

### 5.1 Backup posture (cloud service)

| Store | Backing | Backup mechanism | Notes |
| --- | --- | --- | --- |
| Process Metadata DB | RDS | RDS automated snapshots + point-in-time recovery (AWS managed-service defaults for the chosen RDS configuration) | Snapshot frequency / retention follow AWS defaults; specifics depend on the RDS instance class and configuration |
| Retrieval DB | OpenSearch | OpenSearch automated snapshots (AWS default) | Same — inherits managed-service default |
| File storage | S3 | No versioning enabled; no lifecycle policy beyond AWS defaults; relies on S3's 11-nines durability for retention | Source files + intermediate artifacts + X-Rays all live here |

There is no GroundX-managed backup layer on top of these. What AWS gives is what GroundX has.

### 5.2 RPO / RTO

| Target | Posture |
| --- | --- |
| RPO | Roughly bounded by RDS snapshot interval (~hourly) and S3 durability (immediate). **Committed in customer contracts; not publicly published.** |
| RTO | Bounded by RDS restore-from-snapshot time and Kubernetes pod restart time. **Committed in customer contracts; not publicly published.** |

GroundX does not publish public SLA / RPO / RTO targets. Customer-contract-specific commitments live in the operational agreements, not at this skill's altitude.

*Source: scoped internal-review finding, 2026-05-17. Customer-contract specifics are owned by the sales / compliance team, not this skill.*

### 5.3 Multi-AZ within-region

| Component | Multi-AZ behavior |
| --- | --- |
| RDS | AWS-managed multi-AZ failover (default behavior of the chosen RDS instance class) |
| OpenSearch | AWS-managed multi-AZ behavior (default) |
| S3 | S3 is multi-AZ by default within a region |
| GroundX pods | Kubernetes reschedules pods to surviving AZs on AZ failure; no GroundX-specific AZ-pinning logic |

Failover is transparent to GroundX application code — pods reconnect to managed services after AZ events and resume work.

### 5.4 Cross-region recovery

The cloud service has **no replica in any other region**. In the event of a catastrophic us-west-2 outage, recovery would require restoring from RDS / OpenSearch snapshots into another region — the architecture supports it, but there is **no documented runbook today**. This is a known posture, not a designed-in capability.

### 5.5 Restore drills

GroundX does **not run periodic restore drills** today. Backup integrity is assumed from the managed-service contracts; restore success is not exercised on a documented cadence. This is a known gap in the operational posture.

### 5.6 `MonitorPipeline` Lambda

The cloud-service-only Lambda that recovers stuck-document scenarios. Source: `cashbot-go/lambda/MonitorPipeline/main.go`.

**Trigger:** CloudWatch scheduled event (Lambda invocation on a fixed interval).

**Detection:** queries the process-metadata DB for documents whose `updated` timestamp is older than the cutoff for their current processor stage:

| Processor stage | Cutoff | Effect on detection |
| --- | --- | --- |
| Layout | 60 minutes | Documents stuck in layout past 60 min are candidates for restart |
| Extract | 30 minutes | Documents stuck in extract past 30 min are candidates for restart |

(Other processor stages — convert, map, summarize — are diagnostic-only in the current Lambda; recovery is implemented for layout and extract.)

**Recovery action per stuck document:**

1. Reset the document's processor status (Layout or Extract) to `Queued`.
2. Bump the document's `updated` timestamp to NOW().
3. Re-enqueue to the pre-process queue (`file-pre-process`) with an `AIFilePreProcessRequest` stream message.

**Safety:**

- Repair limit: **10 documents per invocation** — prevents the Lambda from overwhelming the queue if many documents are stuck.
- Hardcoded ignore lists (model IDs, customer usernames) skip known-broken cases.
- Critical errors emit to the configured Slack webhook.

**On-prem equivalent:** none. On-prem deployments need their own pipeline-recovery mechanism.

For more detail see `groundx-cloud-utilities.md`.

## 6. Security / compliance altitude

The 1-year SOC2 audit-log retention (per `data-residency.md` § 6.2) is enforced by the **CloudWatch log-group retention configuration** (cloud service) — not by the RDS / OpenSearch snapshot posture. The audit log is therefore on a different durability path from the state stores; a CloudWatch loss event would impact audit-log recoverability independently of RDS / OpenSearch / S3 recovery.

Customer data deletion (per `data-residency.md` § 5.4) does not roll back across DR restore — restored RDS / OpenSearch / S3 state may include previously-deleted customer artifacts, which is operationally significant for GDPR / right-to-be-forgotten claims. The deployment's compliance contract is what governs how DR restores are reconciled against deletion history.

## 7. Operations / SRE altitude

DR operational responsibilities split clearly:

- **Cloud service** — GroundX SRE owns the cloud deployment's DR posture, including snapshot review, AZ-failover monitoring, and Slack-alerted `MonitorPipeline` outputs. No customer action is needed; customers experience whatever the posture provides.
- **On-prem** — deployer owns everything: backup configuration on the chosen backings, multi-AZ / multi-region decisions, restore testing, an equivalent of `MonitorPipeline` for pipeline-level recovery, and any RPO / RTO commitments.

For broader observability framing see `observability.md`. For the failure scenarios DR helps recover from see `failure-modes.md`. For the runbook depth on-prem deployers need to build see `groundx-on-prem`.

## 8. Data architecture altitude

What gets recovered varies by failure:

| Failure | Recovery |
| --- | --- |
| AZ outage | RDS, OpenSearch, S3 fail over automatically; pods reschedule via Kubernetes; service resumes |
| Pod crash | Kubernetes restarts the pod; in-flight work may be lost (see `failure-modes.md`); `MonitorPipeline` recovers stuck documents on the next invocation |
| Stuck document at layout / extract step | `MonitorPipeline` resets state, re-enqueues to `pre-process`; document re-processes from its current step |
| Regional outage | No automatic recovery; manual restore from snapshots into another region required; no documented runbook |
| Backing-service data corruption | Restore from snapshot (RDS / OpenSearch); S3 has no versioning so prior versions of artifacts aren't recoverable |

The store-level cascading deletes (per `data-residency.md` § 5.4) are also recovery-relevant — restoring from a snapshot taken before a customer-delete will re-materialize the deleted data, which the operational contract must reconcile.

## 9. Cost / FinOps altitude

DR cost in the cloud service is built into the managed-service line items: RDS multi-AZ + snapshots are billed as part of the RDS instance cost; OpenSearch snapshots are part of the cluster cost; S3 durability is part of the per-GB cost. There is no separate DR cost line. Cross-region replication, if added, would roughly double per-store cost — it is not done today (per `data-residency.md` § 9). Deployment-level cost framing is owned by `groundx-on-prem`.

## 10. What this topic does not cover

- **The compliance posture (SOC2 Type 1 + HIPAA + SOC2 Type 2 in progress)** that constrains DR retention: `data-residency.md` § 5.3.
- **The audit log retention (1 year cloud) and the right-to-be-forgotten interaction**: `data-residency.md` § 6.2.
- **What the metrics pod + Slack alerts look like in practice**: `observability.md`.
- **The specific failure scenarios DR helps recover from + behavior per pod**: `failure-modes.md`.
- **The cloud-service Lambda inventory** beyond `MonitorPipeline`: `groundx-cloud-utilities.md`.
- **Public SLA / RPO / RTO commitments**: not a current capability; customer-contract specifics live in operational agreements, not at this skill's altitude.
- **Cross-region runbook for catastrophic us-west-2 outage**: not documented today; named here as a known gap.
- **On-prem DR-tooling guidance (pipeline-recovery equivalent, backup automation)**: `groundx-on-prem` when authored.
