# Service Substitution — Existing-Infra vs Chart-Deployed Dependencies

This file documents **the chart's primary integration knob: each major dependency subsystem (cache/Redis, db/MySQL, file/MinIO-S3, search/OpenSearch, stream/Kafka, summary/LLM) can be either chart-deployed in-cluster or routed to a deployer-supplied existing instance**. The mechanism is the same shape across all six subsystems: an `existing:` sub-block whose discriminator field, when non-empty, flips the chart's `create` helper to false.

For the related question of *which operators* the chart provisions when chart-deploying (Strimzi, Percona, MinIO operator, NVIDIA), route to `services-operators.md` (planned). For per-subsystem credentials and how secrets are wired in either mode, route to `credentials.md`. For the architectural picture, route to `groundx-architecture/references/data-flow.md`.

## 1. The pattern

Five of the six subsystems (cache, db, file, search, stream) share a `create` helper of the same shape, in the per-subsystem helper files under `templates/_helpers/services/`. The canonical shape (`db.tpl:18–28`, `file.tpl:12–22`, `search.tpl:12–27`, `stream.tpl:12–22`) is:

<!-- illustrative -->
```go-template
{{- define "groundx.<svc>.create" -}}
{{- $in := .Values.<svc> | default dict -}}
{{- $ic := include "groundx.<svc>.existing" . | trim | lower -}}
{{- if eq $ic "true" -}}
false
{{- else if hasKey $in "enabled" -}}
  {{- if (dig "enabled" false $in) -}}true{{- else -}}false{{- end -}}
{{- else -}}
true
{{- end -}}
{{- end }}
```

`cache.create` (`cache.tpl:7–17`) is slightly different in form but equivalent in semantics — it checks `existing.addr` inline rather than via a separate `existing` helper. `summary.create` is **materially different** and is documented in § 4.6 separately.

In plain English (for the five uniform-shape subsystems):

1. **If the `existing:` discriminator field is non-empty → don't deploy in-cluster.** The chart routes all references for the subsystem to the deployer-supplied address.
2. Else if `enabled` is explicitly set, honor it.
3. Else default to deploying the subsystem alongside the chart install.

So the *only* values.yaml signal needed to substitute a deployer-managed service for the chart's bundled one is to set the discriminator field of `existing:`. No need to set `enabled: false`. No need to disable the operator. Just provide an address — the chart skips the install.

**A note on what "chart-deployed" really means.** The GroundX chart itself only renders Kubernetes resources for **cache** (`templates/services/cache.yaml`, `cache-metrics.yaml`) and for **summary inference** (`templates/app/inference.yaml`), plus per-pipeline Kafka topic CRDs (`templates/services/stream-topics.yaml`). For db, file, search, and the Kafka cluster, "chart-deployed" means the deployer separately installs an operator (Strimzi for Kafka, Percona for MySQL, MinIO operator for object store) or a standalone Helm chart (OpenSearch) using the values files shipped under `src/groundx/values/{percona, minio, opensearch, strimzi}/`. The GroundX chart only writes the connection strings into `config.yaml` — it does not render the StatefulSets / CRs / tenants itself. See § 9.

## 2. Substitution matrix

| Subsystem | values block | Discriminator field | Chart-deployed default | Typical substitution target |
| --- | --- | --- | --- | --- |
| **Cache** (Redis/Valkey) | `cache` | `cache.existing.addr` | Bundled Redis in `eyelevel-cpu-only` node group | AWS ElastiCache, GCP Memorystore, self-hosted Valkey cluster |
| **Database** (MySQL) | `db` | `db.existing.ro` AND `db.existing.rw` (both required) | Percona MySQL operator + StatefulSet | AWS RDS MySQL, GCP CloudSQL MySQL, Azure Database for MySQL, on-prem MySQL/MariaDB |
| **Object store** (S3 / MinIO) | `file` | `file.existing.url` | MinIO operator + tenant | AWS S3, GCP Cloud Storage, Azure Blob, self-hosted MinIO, NetApp / Pure Storage S3 |
| **Search** (OpenSearch) | `search` | `search.existing.url` | OpenSearch StatefulSet in `eyelevel-cpu-memory` node group | AWS OpenSearch Service, Aiven OpenSearch, self-hosted OpenSearch cluster |
| **Stream** (Kafka) | `stream` | `stream.existing.domain` | Strimzi-managed Kafka cluster | AWS MSK, Confluent Cloud, Aiven Kafka, AWS SQS *(per-topic — see § 6)* |
| **Summary** (LLM) | `summary` | EITHER `summary.existing.url` non-empty OR `summary.existing.serviceType` in `{openai, openai-base64, azure}` | Self-hosted gemma inference pod | OpenAI, Azure OpenAI, AWS Bedrock, any OpenAI-compatible endpoint |

All discriminator fields are strings. Setting one to an empty string is the same as omitting it — chart deploys in-cluster. Setting it to a non-empty value, the chart skips.

## 3. The three substitution modes

The chart's terminology for the modes a deployer is choosing between:

| Mode | What it means |
| --- | --- |
| **Chart-deployed** | The chart installs the subsystem in-cluster. Resource requests, replicas, and (where relevant) StatefulSets are rendered. The `enabled` field is true (or unset, defaulting to true). |
| **Existing in-cluster** | Subsystem runs in the same Kubernetes cluster but is owned by a different operator or release (often deployed by the platform team before the GroundX install). The chart routes to it via a `.svc.cluster.local` address in `existing:`. |
| **Cloud-managed** | Subsystem is a fully-managed cloud service (RDS, ElastiCache, MSK, OpenSearch Service, S3, GCS). The chart routes via the cloud-provider's regional endpoint. |

The chart cannot tell modes 2 and 3 apart — they're both "existing", just with different addresses. The distinction matters only to the deployer (compliance, networking, who carries operational responsibility).

## 4. Per-subsystem semantics

### 4.1 Cache (`cache`)

Discriminator: `cache.existing.addr`. Helper at `templates/_helpers/services/cache.tpl:7–17`.

```yaml
cache:
  existing:
    addr: cache.prod.example.internal
    port: 6379                # default 6379
    ssl: true                 # default false; chooses redis:// vs rediss://
    isCluster: true           # default true when existing; deployer asserts cluster vs standalone
    type: valkey              # optional; affects in-cluster celery behaviour, see `engines.md`
```

When `cache.existing.addr` is set:

- `groundx.cache.create` → false. No in-cluster Redis Deployment is rendered.
- Every reference to the cache in `config-yaml-map` routes to `<addr>:<port>` with the right scheme.
- `cache.metrics.*` is independent: there's a separate `cache.metrics.existing.addr` for the metrics-aggregation cache. They can be substituted independently.

### 4.2 Database (`db`)

Discriminator: **both** `db.existing.ro` AND `db.existing.rw` must be non-empty. Helper at `templates/_helpers/services/db.tpl:12–28`.

```yaml
db:
  dbName: groundx               # database name, required
  username: app_user
  password: <app-password>
  privilegedUsername: root      # only used during init/migration
  privilegedPassword: <root-password>

  existing:
    ro: groundx-rdo.cluster-ro.us-east-1.rds.amazonaws.com    # read replica endpoint
    rw: groundx-rdo.cluster.us-east-1.rds.amazonaws.com       # writer endpoint
    port: 3306                                                  # default 3306
    rootCerts: |                                               # optional TLS root certs
      -----BEGIN CERTIFICATE-----
      ...
      -----END CERTIFICATE-----
```

The dual-discriminator pattern (ro AND rw) is the only one in the chart. It exists because GroundX's data-access pattern splits read traffic to a replica for scalability. A deployer wanting to run a single-host MySQL can point both fields at the same address — the chart doesn't enforce that they differ.

`db.privilegedUsername` and `db.privilegedPassword` are only used by the init job that bootstraps the schema. After install, the application connects with `db.username` / `db.password`. For cloud-managed databases where the deployer already provisioned the schema (or doesn't grant the deployment a privileged role), set the privileged fields to empty strings — the init job will skip privileged operations and the chart will template the rendered `config.yaml` to omit the privileged credentials.

### 4.3 File / object store (`file`)

Discriminator: `file.existing.url`. Helper at `templates/_helpers/services/file.tpl:6–22`.

```yaml
file:
  bucketName: groundx-prod
  username: <s3-access-key-id>
  password: <s3-secret-access-key>

  existing:
    url: https://s3.us-east-1.amazonaws.com
    region: us-east-1
    serviceType: s3                          # "s3" for AWS; the chart's `serviceType` informs the SDK config
    port: 443                                # default 443
```

For non-AWS object stores:

- **GCS**: `existing.url: https://storage.googleapis.com`, `serviceType: gcs` (when supported by the application's SDK; verify with deployer contact).
- **Azure Blob**: configured via Azure-compatible S3 gateway or direct Azure SDK depending on the application's support matrix.
- **Self-hosted MinIO**: `existing.url: https://minio.platform.svc.cluster.local`, `serviceType: minio`.

The chart's `file.bucketName` is the same regardless of substitution — the bucket must exist (the chart doesn't create cloud buckets; it does create in-cluster MinIO buckets when chart-deploying).

### 4.4 Search (`search`)

Discriminator: `search.existing.url`. Helper at `templates/_helpers/services/search.tpl:12–27`.

```yaml
search:
  indexName: groundx-prod
  username: <opensearch-app-user>
  password: <opensearch-app-password>
  privilegedUsername: <opensearch-admin>     # used during init for index creation
  privilegedPassword: <opensearch-admin-pw>

  existing:
    url: https://opensearch.prod.us-east-1.es.amazonaws.com
```

Two notable behaviours:

- **In `mode: ingest`, `search.create` is forced to false** regardless of `existing.url`. The ingest-only deployment mode doesn't run the search service at all (`deployment-modes.md`). The deployer can still supply `existing.url` for the application to *read* search results from, but the chart won't run a search StatefulSet locally.
- **`search.privilegedUsername`, `search.privilegedPassword`, `search.username`, and `search.password` are schema-required** (`values.schema.json:309–311`). Unlike `db.privilegedUsername` (which has a skip-when-empty conditional in `config-yaml.yaml:212–220`), the search privileged credentials are rendered unconditionally into the `init.search` block (`config-yaml.yaml:221–224`) — passing empty strings still emits the keys with empty values, which the init job may not handle gracefully. Always supply real values.

### 4.5 Stream (`stream`)

Discriminator: `stream.existing.domain`. Helper at `templates/_helpers/services/stream.tpl:12–22`.

```yaml
stream:
  existing:
    domain: kafka.prod.us-east-1.amazonaws.com
    port: 9094                                  # chart default is 9092; deployers typically set 9094 for TLS-MSK

  # Top-level key/secret/region are fallback credentials for SQS-typed topics
  # (per-topic key/secret/region under stream.topics.<name> coalesces over these
  # via templates/_helpers/services/topics.tpl). They are NOT Kafka SASL credentials.
  # key: <aws-access-key-id>
  # secret: <aws-secret-access-key>
  # region: us-east-1
```

When `stream.existing.domain` is set, the chart skips rendering the Strimzi-managed Kafka resources. Per-topic configuration (broker, groupId, type, plus optional AWS credentials for SQS-typed topics) lives under `stream.topics.<topic-name>.*`. See `credentials.md` § 6 and `values-yaml.md` § 7 for the per-topic surface. Kafka SASL/PLAIN authentication, if needed, is configured against the chart-deployed Strimzi `Kafka` CR or the existing Kafka cluster — not via these top-level stream fields.

The chart supports SQS as a per-topic alternative — see § 6 below.

### 4.6 Summary (`summary` — LLM)

The summary subsystem has a slightly different shape because the substitution decision is *also* a "use external API" decision, not just "use existing infra". See `engines.md` for the full picture; this section covers only the chart-level substitution mechanics.

Discriminator (from `groundx.summary.create` in `templates/_helpers/app/summary.tpl:6–13`):

```go-template
{{- $urlEmpty := eq (dig "url" "" $ex) "" -}}
{{- $stype := lower (coalesce (dig "serviceType" "" $ex) "eyelevel") | trim -}}
{{- $svcAllowed := or (eq $stype "openai") (eq $stype "openai-base64") (eq $stype "azure") -}}
{{- and $urlEmpty (not $svcAllowed) -}}
```

`groundx.summary.create` returns `true` (chart deploys internal) only when **both** url is empty AND serviceType is *not* in the allowed-set. In practical terms: setting **either** `existing.url` to a non-empty value **or** `existing.serviceType` to one of `{openai, openai-base64, azure}` flips the chart to "use external" — the chart skips the self-hosted inference deployment.

```yaml
summary:
  existing:
    apiKey: sk-...
    serviceType: openai                # one of: openai | openai-base64 | azure (when external)
    # url is OPTIONAL for these serviceTypes — the chart's own example
    # at src/groundx/values/values.openai.yaml notes:
    #   "for serviceType == openai, openai-base64, or azure, url is not needed"
    # url: https://api.openai.com/v1   # only needed for non-standard endpoints / custom routing
```

For the three allowed serviceTypes (`openai`, `openai-base64`, `azure`), `url` can be omitted — the application has built-in URL handling for these well-known service shapes. Setting `url` is still valid (for custom routing, on-prem OpenAI-compatible gateways, or Azure deployment paths) but isn't required by the chart or the application.

`summary.existing.apiKey` falls back to `admin.apiKey` via `groundx.summary.apiKey` (`summary.tpl:15–19`), so for OpenAI-compatible deployments where the deployer already set `admin.apiKey` to the OpenAI key, the existing.apiKey can be omitted. This is the kind of overlap that's easy to miss — see `engines.md` § 2 for the full picture.

When `summary.existing.*` triggers external mode, the chart skips deploying the self-hosted inference pod. When the chart deploys internally, the inference deployment lands in the `eyelevel-gpu-summary` node group.

## 5. Independence — substituting one without the others

Every `create` helper is independent. A common substitution shape is:

| Subsystem | Mode for this deployment |
| --- | --- |
| Cache | Chart-deployed (in-cluster Redis) |
| DB | Cloud-managed (RDS) |
| File | Cloud-managed (S3) |
| Search | Chart-deployed (in-cluster OpenSearch) |
| Stream | Chart-deployed (Strimzi Kafka) |
| Summary | Chart-deployed (self-hosted gemma) |

Or for a maximally-externalized deployment:

| Subsystem | Mode |
| --- | --- |
| Cache | Cloud-managed (ElastiCache) |
| DB | Cloud-managed (RDS) |
| File | Cloud-managed (S3) |
| Search | Cloud-managed (AWS OpenSearch Service) |
| Stream | Cloud-managed (MSK or SQS per-topic) |
| Summary | External LLM (OpenAI / Azure) |

The chart deploys *nothing stateful* in this configuration — only the stateless application pods. This is the common pattern for cloud-tier enterprises adopting GroundX as a managed application layer over their existing cloud-data estate.

## 6. Stream-substitution at the topic level (per-topic `type`)

The stream subsystem has one additional substitution path the others lack: **per-topic `type`**. Each topic block inside `stream.topics.<topic-name>` accepts a `type:` field that defaults to `kafka`. The helper at `templates/_helpers/services/topics.tpl:23–34` branches on this — when `type: kafka`, the broker, groupId, and topic-name fields are populated for the Kafka client; when set to anything else (typically `sqs` for AWS SQS), the broker/groupId/topic-name fields are omitted and the topic config carries only `key/region/secret/token/url`, which the application's runtime consumes as cloud-queue credentials.

So a deployer wanting Kafka for most pipeline topics but a cloud-queue alternative for a low-volume control-plane topic can set `type` on just that one topic. The rest of stream stays on Kafka (chart-deployed or existing). The chart itself doesn't validate the non-Kafka type value — it's a free string passed through to the application's runtime.

### 6.1 Mixed Kafka + SQS — per-topic override pattern

`src/groundx/values/values.existing.yaml` is the canonical chart example for mixing transports: `stream.existing.domain` points at a Kafka cluster, and per-topic `type` is set to `kafka` for most (`preProcess`, `process`, `summary`, `upload`) but `sqs` for `update`. The chart routes each topic independently:

```yaml
stream:
  existing:
    domain: kafka.existing.com
    port: 9001
  topics:
    update:
      key: awsKey
      region: us-east-2
      secret: awsSecret
      type: sqs
      url: https://sqs.us-east-2.amazonaws.com/X/file-update
    # ...other topics stay on Kafka
```

### 6.2 All-SQS — fully Kafka-less deployment

When every topic ships to SQS, the chart-recommended shape (per `src/groundx/values/values.aws.services.yaml`) is to set `stream.enabled: false` and supply `type: sqs` on every topic. With Kafka fully disabled, no Strimzi operator is needed and no `stream.existing.domain` is set:

```yaml
stream:
  enabled: false
  topics:
    preProcess:
      type: sqs
      url: https://sqs.us-east-2.amazonaws.com/X/file-pre-process
    process:
      type: sqs
      url: https://sqs.us-east-2.amazonaws.com/X/file-process
    summary:
      type: sqs
      url: https://sqs.us-east-2.amazonaws.com/X/file-summary
    update:
      type: sqs
      url: https://sqs.us-east-2.amazonaws.com/X/file-update
    upload:
      type: sqs
      url: https://sqs.us-east-2.amazonaws.com/X/file-upload
```

Note this example uses **only `url`** per topic — no `key`/`secret`/`region`. That's the IRSA pattern: the cluster's `serviceAccount.name` is annotated with an AWS IAM role that grants SQS access, and the AWS SDK picks up credentials via instance metadata. For non-IRSA clusters, supply `key`/`secret`/`region` per topic (as in § 6.1).

A practical note from the same file: "visibility timeout must be 10+ min for all SQS queues."

See `values-yaml.md` § 7 for the per-topic field surface.

## 7. Operational implications of substitution choices

| Choice | Tradeoffs |
| --- | --- |
| **All chart-deployed** | Maximum portability, single Helm release covers everything. Cluster resource footprint highest. Recovery and backup responsibility entirely on the deployer. Best for proofs of concept and air-gapped deployments. |
| **Selective substitution** | Externalize stateful subsystems (db, file, stream) to cloud-managed services for backup/recovery/durability; keep chart-deployed for low-state subsystems (cache, search if low scale). Most common production shape. |
| **All externalized** | Chart deploys only application pods. Lowest cluster resource footprint. Deployer takes full operational responsibility for every dependency. Best fit for enterprises with mature cloud-data estates. Highest install-time setup cost (every connection string and credential must be sourced and threaded through). |

The chart imposes no preference. Most production deployments end up at "selective" once they account for compliance, disaster-recovery posture, and which stateful systems the platform team already operates.

## 8. Cross-field implications

| Set this... | …and this is implied or required |
| --- | --- |
| `<svc>.existing.<discriminator>` non-empty | The chart skips chart-deploying that subsystem. Subsystem-specific replicas, resources, persistence, and node-selector fields under `<svc>` are ignored. Operator dependencies (Strimzi for stream, Percona for db, MinIO operator for file) are no longer required. |
| `<svc>.existing.<discriminator>` empty + `enabled: false` | The chart neither deploys the subsystem nor routes to an existing one. The application's runtime config will lack the service. **For most subsystems this breaks the pipeline.** Only valid when the deployment mode actively skips the subsystem (e.g., `mode: ingest` legitimately removes search). |
| `db.existing.ro` set but `db.existing.rw` empty (or vice versa) | The chart's `groundx.db.existing` helper returns false (both must be set). The chart will then chart-deploy MySQL — and the application will probably fail to connect to the half-configured "existing" endpoint. **Set both or neither.** |
| `summary.existing.serviceType` to an unsupported value (e.g., `bedrock`) | The chart does **not** fail the install. `groundx.summary.create` simply ignores the value (the allowed-set check is only used to flip create=false; an unsupported value leaves create=true unless `existing.url` is also set). Setting only an unsupported serviceType yields a deployment with both a chart-deployed inference pod AND a bogus serviceType written into config. Allowed-set is `openai | openai-base64 | azure`. See `engines.md` § 2. |
| Chart-deployed mode + cluster lacks the required operator | Pods stay pending. For Kafka, Strimzi must be installed first. For MySQL via the Percona operator path, similar. The chart renders the StatefulSet but the operator-owned CRDs won't materialize without their operator. |

## 9. What gets rendered where — chart vs separate Helm releases

Despite the "chart-deployed" terminology, the GroundX Helm chart only renders Kubernetes resources for a subset of the subsystems. The rest are installed via separate Helm releases that the deployer applies *before* the GroundX chart. Values files seeding those releases ship under `src/groundx/values/`:

| Subsystem | What the GroundX chart renders | What the deployer installs separately |
| --- | --- | --- |
| **cache** | `cache.yaml` + `cache-metrics.yaml` — Redis StatefulSets, in-cluster. | Nothing. |
| **db** | Nothing. | Percona XtraDB operator + cluster CR. Values under `src/groundx/values/percona/`. |
| **file** | Nothing. | MinIO operator + tenant CR. Values under `src/groundx/values/minio/`. |
| **search** | Nothing. | OpenSearch via its own Helm chart. Values under `src/groundx/values/opensearch/`. |
| **stream** | `stream-topics.yaml` — `KafkaTopic` CRDs only. The cluster itself is not rendered. | Strimzi Kafka operator + `Kafka` CR. Values under `src/groundx/values/strimzi/`. (Kafka topics rendered by the GroundX chart require Strimzi to be running so the operator picks up the CRDs.) |
| **summary** | `inference.yaml` — self-hosted gemma inference pod. | NVIDIA GPU operator (cluster-wide). |

So the install ordering matters: **the prerequisite operator Helm releases must come first**, otherwise the GroundX chart's CRD references (e.g., `KafkaTopic`) and connection-string assumptions will fail. See `install-flow.md` for the recommended sequence and `services-prereqs.md` for the operator inventory.

See `services-operators.md` (planned) for per-operator installation specifics.

## 10. Authoring discipline

When designing a values.yaml for a new deployment:

1. **Decide per-subsystem before writing config.** The substitution choice for each of cache, db, file, search, stream, summary is independent. Make all six decisions explicitly before writing any values.
2. **For each substituted subsystem, gather the connection details first.** Discriminator field plus credentials. Don't write half-substituted values blocks.
3. **Run `helm template` before `helm install`.** The chart's helpers fail-fast on a few obvious shape issues (`db.existing.ro` without `db.existing.rw`, `summary.existing.serviceType` outside the allowed set). Catch these locally before the cluster does.
4. **Network reachability is your problem.** The chart writes connection strings into `config.yaml`. It does not provision NetworkPolicies, VPC peering, or DNS. For each substituted subsystem, verify the cluster can reach the endpoint before installing.
5. **Backup posture shifts.** Chart-deployed subsystems are backed up by your in-cluster tooling. Substituted subsystems are backed up by the deployer's existing infra. Don't assume the chart-substitution decision is purely operational; it changes who's responsible for data durability.

## 11. What this file does not cover

- **Operator installation specifics (Strimzi, Percona, MinIO operator, NVIDIA operator)** → `services-operators.md` (planned).
- **Per-subsystem credential mechanics** → `credentials.md`.
- **Field-by-field schema for `<svc>` blocks** → `values-yaml.md`.
- **Discovery questionnaire for substitution decisions at install time** → `values-authoring.md`.
- **Summary engine semantics (allowed serviceTypes, vision flag, reasoningEffort)** → `engines.md`.
- **TLS / certificate handling for substituted services** → `tls-and-certs.md`.
- **Deployment-mode interactions (`mode: ingest` forcing search.create to false)** → `deployment-modes.md`.
- **Cost implications of chart-deployed vs cloud-managed** → `cost-estimation.md` (planned).
