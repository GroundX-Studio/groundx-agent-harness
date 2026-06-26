# Cross-Region Disaster Recovery — Runbook

This file documents **the cross-region DR pattern for a chart-deployed GroundX cluster** — what an active-passive failover looks like, what data layers need replication, the RPO / RTO trade-offs, and the failover / failback procedures. The chart itself is single-region; multi-region is a deployer architecture pattern that consumes the chart twice.

For the architectural framing of disaster recovery, route to `groundx-architecture/references/disaster-recovery.md`. For the install flow that DR re-runs, route to `install-flow.md`. For backing-service substitution choices that affect DR scope, route to `service-substitution.md` § 5.

## 1. The chart's DR posture (single-region)

The GroundX chart deploys into a single Kubernetes cluster in a single region. The chart's helpers, templates, and resources have no built-in cross-region awareness. Cross-region DR is achieved by:

1. **Deploying the chart twice** — once in primary region, once in secondary region.
2. **Replicating the stateful layer** — MySQL, OpenSearch index, MinIO/S3 bucket, optionally Kafka. The replication mechanism depends on the backing-service choice (chart-deployed vs cloud-managed).
3. **Switching traffic** at the DNS / load-balancer layer when failover is triggered.

The chart-side knobs that matter for DR:

- `cluster.type` (probably the same in both regions, but can differ if migrating).
- `cluster.pvClass` / `cluster.pvAccessMode` (must align with each region's storage).
- All `<svc>.existing.*` blocks pointing at each region's local backing services.
- `admin.imageRepository` if using a regional mirror.

## 2. What needs replication

| Layer | Replication target | Mechanism | RPO |
| --- | --- | --- | --- |
| **MySQL data** | Schema + rows | RDS Multi-Region / Aurora Global / Percona Replication / native replication for self-hosted | Seconds (synchronous) to minutes (async) |
| **OpenSearch index** | Indices + documents | Cross-cluster replication (OpenSearch native), or snapshot+restore on schedule | Minutes (CCR) to hours (snapshot) |
| **MinIO / S3 bucket** | Object data | S3 Cross-Region Replication (CRR), MinIO active-active, or Restic snapshots | Seconds (S3 CRR) to hours (snapshot) |
| **Kafka topics** (when chart-deployed Strimzi) | Topic data | Strimzi MirrorMaker2; Confluent Cluster Linking; MSK MirrorMaker | Seconds (MM2) |
| **Application config** (values.yaml + secrets) | Helm release state | Git-tracked values.yaml + Secrets Manager + manual sync | Operator-driven |
| **Workspace cache PVC** | Cache contents | NOT replicated; cache is regenerable from Git | N/A |

The chart-deployed Redis cache is **not** typically replicated — caches are regenerable, and cross-region Redis replication adds complexity without much value.

## 3. The active-passive pattern

The most common DR pattern for GroundX:

```
┌────────────────────────────────────┐
│  Region A — ACTIVE                 │
│  ├── GroundX cluster (full)        │
│  ├── RDS primary                   │
│  ├── OpenSearch (writes)           │
│  ├── S3 bucket (primary)           │
│  └── Public DNS → A's load balancer│
└────────────────────────────────────┘
            │ replication
            ▼
┌────────────────────────────────────┐
│  Region B — PASSIVE                │
│  ├── GroundX cluster (cold/warm)   │
│  ├── RDS replica (read-only)       │
│  ├── OpenSearch (replicated)       │
│  ├── S3 bucket (replicated)        │
│  └── (DNS doesn't point here yet)  │
└────────────────────────────────────┘
```

Region B's GroundX cluster is either:

- **Cold** — chart not installed; install during failover. Faster MTTR (~30 minutes for chart install) but longer-RTO.
- **Warm** — chart installed but minimal replicas; scale up during failover. Lower-RTO (~5 minutes) but higher steady-state cost.
- **Hot** — chart installed at production scale, optionally also serving read traffic. Lowest-RTO but doubles steady-state cost.

Most production deployments choose warm — paid for, but at small scale until needed.

## 4. RPO / RTO targets

Define the deployment's RPO (recovery point objective) and RTO (recovery time objective) before designing replication:

| Pattern | RPO | RTO | Cost orientation |
| --- | --- | --- | --- |
| Synchronous DB replication (RDS Multi-AZ or Aurora Global) | < 1 minute | 1-5 minutes | High |
| Async DB replication + S3 CRR + OpenSearch CCR | 1-15 minutes | 10-30 minutes | Medium |
| Snapshot-based (hourly snapshots) | 1 hour | 1-4 hours | Lower |
| Daily backups, no replication | 24 hours | Hours-to-days | Lowest |

The right choice depends on the deployment's tolerance for data loss and service interruption.

## 5. Failover procedure (active to passive)

When primary region becomes unavailable:

### 5.1 Decide

The decision to fail over is a human judgment call. Factors:

- Is the primary region truly down (AWS region-wide outage) or just an AZ issue (multi-AZ within region handles)?
- Is the issue temporary (~15 minutes) or extended?
- What's the data-loss exposure of the secondary region's replication lag?

Premature failover causes data divergence; delayed failover extends downtime.

### 5.2 Promote the database

For RDS Aurora Global Database: `aws rds failover-global-cluster` promotes the secondary cluster to primary. ~1 minute.

For Percona PXC native replication: STOP REPLICATION on secondary; promote to writer. Manual steps documented per Percona's docs.

### 5.3 Stop replication writes

Source-region writes must stop (or the source must be unreachable). If the source comes back, configure reverse replication so the failed-back data syncs.

### 5.4 Verify and warm up the secondary

```sh
# Switch kubectl context to secondary cluster
kubectl config use-context groundx-region-b

# If chart was cold-installed, install now
helm install groundx ./src/groundx -n eyelevel -f my-region-b-values.yaml

# If warm, scale up
kubectl -n eyelevel scale deployment groundx --replicas=4
kubectl -n eyelevel scale deployment layout-api --replicas=4
# etc.

# Verify pods come up
kubectl -n eyelevel get pods
```

### 5.5 Switch DNS / load-balancer

Route 53 weighted records, AWS Global Accelerator, or external DNS provider (Cloudflare, Akamai) re-pointed at region B's load balancer.

### 5.6 Verify end-to-end

```sh
# API endpoint responding
curl https://api.groundx.example.com/health

# Test ingest works
curl -X POST https://api.groundx.example.com/v1/ingest -d @test-document.pdf

# Test search returns results
curl https://api.groundx.example.com/v1/search?q=test
```

## 6. Failback procedure (passive back to active)

After the primary region is restored:

### 6.1 Reverse replication

Configure region B → region A replication. Wait for it to catch up.

### 6.2 Plan failback window

Schedule a maintenance window. Failback is more disruptive than the failover because the deployer is intentionally moving traffic away from a healthy cluster.

### 6.3 Stop secondary writes

During the failback window, stop writes to region B.

### 6.4 Promote region A's database

Reverse the promote operation: region A becomes the writer again; region B reverts to replica.

### 6.5 Switch DNS back

Re-point DNS at region A.

### 6.6 Verify end-to-end

Same as § 5.6.

### 6.7 Restore replication direction

Resume replication from A → B.

## 7. Chart-side considerations

When deploying the chart in two regions:

### 7.1 Distinct namespace? Same name?

The chart conventionally installs into the `eyelevel` namespace. Both regions can use `eyelevel` — they're separate clusters with no namespace collision. The chart's namespace-scoped resources don't conflict.

### 7.2 Distinct DNS names?

If the deployer wants to address each region's cluster directly (e.g., for testing), use distinct DNS names for the LoadBalancer Services or Ingress hosts: `api-us-east-2.groundx.example.com` and `api-us-west-2.groundx.example.com`. The user-facing DNS (`api.groundx.example.com`) is a Route 53 alias to whichever region is active.

### 7.3 admin.* and licenseKey

Both regions need the same `admin.*` values and `licenseKey`. Otherwise the API keys won't match across regions and clients can't seamlessly switch.

### 7.4 Backing services in distinct accounts

For maximum isolation, each region runs in a distinct cloud account. This is overkill for most deployments but mandated for FedRAMP / DoD-track architectures.

## 8. What's NOT covered by chart-side DR

- **Application-level state machines**. The chart doesn't track in-flight document ingestions. Failovers during a document's pipeline progression may result in that document being re-processed in region B (idempotency is the application's problem to handle).
- **Authentication / authorization state**. JWT tokens issued by region A are typically valid against region B (assuming the same `admin.username` / API keys), but session state (if any) doesn't replicate by default.
- **Worker queue state**. Kafka topics replicated via MM2 *will* preserve in-flight pipeline messages; SQS queues don't typically replicate cross-region — design accordingly.
- **External LLM provider state**. If `summary.existing.url: https://api.openai.com/v1`, both regions hit the same OpenAI endpoint. No DR concerns there beyond OpenAI's own SLA.

## 9. Cross-region testing — quarterly fire drills

DR is only credible if tested. A quarterly fire drill:

1. **Plan a maintenance window**.
2. **Trigger failover** following § 5.
3. **Run end-to-end tests** against region B (ingest, search, summarize).
4. **Measure RTO actual vs target**. Document gaps.
5. **Fail back** following § 6.
6. **Post-mortem** any surprises. Update the runbook.

The first fire drill always reveals procedural gaps. Subsequent drills shrink them.

## 10. Cross-field implications

| Set this... | …and this is implied or required |
| --- | --- |
| Two-region deployment | Backing services in each region must be set up consistent with each region's chart values; replication wired separately per service. |
| `admin.*` differs between regions | API clients break when DNS flips — keys must match. Synchronize. |
| `licenseKey` differs between regions | License-key enforcement may flag the failover as a new install. Use the same license in both regions. |
| Chart-deployed Kafka with no MirrorMaker2 | Topic state doesn't replicate. In-flight pipeline messages lost during failover. Add MM2 or accept data loss. |
| Cloud-managed RDS with single-region | No automatic cross-region failover. Pair with Aurora Global Database or read-replica promotion procedure. |
| Cold passive cluster | Slowest RTO; chart install during failover. Test the install end-to-end at least quarterly. |
| Two clusters at full scale (hot-hot) | Highest cost, lowest RTO. Active-active read traffic distribution is possible but write traffic must converge to a single primary. |

## 11. What this file does not cover

- **Backing-service-specific replication setup** — RDS Multi-AZ, S3 CRR, OpenSearch CCR, Strimzi MM2 each have their own setup; consult vendor docs.
- **Architectural framing of disaster recovery** → `groundx-architecture/references/disaster-recovery.md`.
- **Within-region HA (multi-AZ deployment)** — this file focuses on cross-region; for HA see node-group placement in `node-groups.md`.
- **Data residency requirements that mandate single-region deployment** — air-gapped and FedRAMP deployments may forbid cross-region. See `air-gapped.md` and consult compliance.
- **Backup retention and restore-from-snapshot procedures** — see your backing-service docs.
- **Application-level idempotency for in-flight pipelines** — application docs; out of chart scope.
- **DNS provider specifics (Route 53, Cloudflare, NS1, etc.)** — vendor docs.
- **Cross-cloud DR (e.g., AWS primary, GCP secondary)** — possible but not standard; data-replication tooling is more complex.
