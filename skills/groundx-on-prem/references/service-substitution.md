# Service Substitution — Existing-Infra vs Chart-Deployed Dependencies

This file documents **the chart's primary integration knob: each major dependency subsystem (cache/Redis, db/MySQL, file/MinIO-S3, search/OpenSearch, stream/Kafka, summary/LLM) can be either chart-deployed in-cluster or routed to a deployer-supplied existing instance**. The mechanism is the same shape across all six subsystems: an `existing:` sub-block whose discriminator field, when non-empty, flips the chart's `create` helper to false.

For the related question of *which operators* the chart provisions when chart-deploying (Strimzi, Percona, MinIO AIStor operator, NVIDIA), route to `services-operators.md`. For per-subsystem credentials and how secrets are wired in either mode, route to `credentials.md`. For the architectural picture, route to `groundx-architecture/references/data-flow.md`.

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

**A note on what "chart-deployed" really means.** The GroundX chart itself only renders Kubernetes resources for **cache** (`templates/services/cache.yaml`, `cache-metrics.yaml`) and for **summary inference** (`templates/app/inference.yaml`), plus per-pipeline Kafka topic CRDs (`templates/services/stream-topics.yaml`). For db, file, search, and the Kafka cluster, "chart-deployed" means the deployer separately installs an operator (Strimzi for Kafka, Percona for MySQL, the MinIO AIStor operator for object store) or a standalone Helm chart (OpenSearch) using the values files shipped under `src/groundx/values/{percona, aistor, opensearch, strimzi}/`. The GroundX chart only writes the connection strings into `config.yaml` — it does not render the StatefulSets / CRs / object stores itself. See § 9.

## 2. Substitution matrix

| Subsystem | values block | Discriminator field | Chart-deployed default | Typical substitution target |
| --- | --- | --- | --- | --- |
| **Cache** (Redis/Valkey) | `cache` | `cache.existing.addr` | Bundled Redis in `eyelevel-cpu-only` node group | AWS ElastiCache, GCP Memorystore, self-hosted Valkey cluster |
| **Database** (MySQL) | `db` | `db.existing.ro` AND `db.existing.rw` (both required) | Percona MySQL operator + StatefulSet | AWS RDS MySQL, GCP CloudSQL MySQL, Azure Database for MySQL, on-prem MySQL/MariaDB |
| **Object store** (S3 / MinIO) | `file` | `file.existing.url` | MinIO AIStor operator + object store (customer's license) | AWS S3, GCP Cloud Storage, Azure Blob, self-hosted MinIO or AIStor, S4, NetApp / Pure Storage S3 |
| **Search** (OpenSearch) | `search` | `search.existing.url` | OpenSearch StatefulSet in `eyelevel-cpu-memory` node group | AWS OpenSearch Service, Aiven OpenSearch, self-hosted OpenSearch cluster |
| **Stream** (Kafka) | `stream` | `stream.existing.domain` | Strimzi-managed Kafka cluster | AWS MSK, Confluent Cloud, Aiven Kafka, AWS SQS *(per-topic — see § 6)* |
| **Summary** (LLM) | `summary` | A `summary.existing` engine whose `serviceType` is not `eyelevel` or whose `url` is off-cluster, plus `engines.default.engineId` (chart 0.2.7, § 4.6) | Self-hosted gemma inference pod | OpenAI, Azure OpenAI, AWS Bedrock, any OpenAI-compatible endpoint |

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
  metrics:
    enabled: false            # metrics server shares this Redis (see below)
  existing:
    addr: cache.prod.example.internal
    port: 6379                # default 6379
    ssl: true                 # default false; chooses redis:// vs rediss://
    isCluster: true           # default true when existing; deployer asserts cluster vs standalone
    type: valkey              # optional; affects in-cluster celery behaviour, see `engines.md`
```

When `cache.existing.addr` is set:

- `groundx.cache.create` → false. No in-cluster Redis Deployment is rendered.
- The main cache session in `config-yaml-map` routes to `<addr>:<port>` with the right scheme, and uses `cache.password` / `cache.username` when set.
- The metrics server's Redis session follows `cache.metrics.enabled`, which defaults to `true`. While it is `true`, the metrics address, port, cluster mode, TLS setting and credentials come from the `cache.metrics.*` settings, such as `cache.metrics.existing` and `cache.metrics.password` / `cache.metrics.username`, not from `cache.existing` or `cache.password`; without `cache.metrics.existing.addr` the address is the `cache-metrics` in-cluster host, which the chart does not deploy when `cache.existing.addr` is set. With `cache.metrics.enabled: false`, the metrics session inherits the `cache.existing` address, port, cluster mode and TLS setting, and `cache.password` / `cache.username`. Set `cache.metrics.enabled: false` for one shared Redis, or set `cache.metrics.existing` plus `cache.metrics.password` for a separate metrics Redis (`tls-and-certs.md` § 4.3).

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

For AWS RDS and RDS Proxy (endpoints, the proxy CA, pool sizing, and Error 9501), see `services-prereqs.md` § 3.2.

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
- **Self-hosted MinIO or MinIO AIStor**: `existing.url: https://minio.platform.svc.cluster.local`, `serviceType: minio`.
- **S4**: `serviceType: s4` with the S4 Service URL on port 7480 for a new install; when S4 replaces an existing MinIO store, GroundX keeps the URL it uses today — see § 4.3.1.

The chart's `file.bucketName` is the same regardless of substitution. The chart doesn't create cloud buckets, so a cloud bucket must exist before install.

With `fileAccess.enabled` false (the chart default), on an in-cluster MinIO, MinIO AIStor, or S4 store, GroundX creates the bucket when it does not exist and then sets a public-read policy on it, which GroundX's unsigned file, X-Ray, and page-image links rely on. If the bucket already exists on such a store, because it was copied from another store or an operator created it, GroundX does not set the policy. Apply the anonymous `s3:GetObject` policy step in the on-prem S4 migration guide ([Migrating from MinIO or AIStor](https://github.com/eyelevelai/groundx-on-prem/blob/53cf055e5437b8e619b0f4a2f2e27459a922eee2/docs/storage/s4.md#migrating-from-minio-or-aistor), step 3), with the store's own URL, credentials, and region in place of the S4 ones. The policy lets anyone who can reach the store read every object in the bucket, not only those links. With `fileAccess.enabled` true, GroundX does not set this policy and the bucket must stay private: do not apply it, and remove any anonymous grant, because GroundX serves files through the file-access gateway instead (`file-access.md`). On S4 0.3.2, `DeleteBucketPolicy` reports success but keeps the policy ([rh-aiservices-bu/s4#34](https://github.com/rh-aiservices-bu/s4/issues/34)): replace the policy instead, with one that grants `s3:GetObject` only to the S4 service user (`arn:aws:iam:::user/s4admin`), then confirm that an anonymous GET of an object in the bucket is refused.

#### 4.3.1 S4

[S4](https://github.com/rh-aiservices-bu/s4) is a license-free, S3-compatible store that runs in one container on Ceph's experimental standalone gateway. GroundX connects to it with storage type `s4`, which needs GroundX chart 0.2.8 or later with its default image tags: older service images do not know `s4` and send files to AWS S3 or fail extraction at start. S4 suits small installs; for production, use MinIO AIStor (`services-operators.md` § 4).

Limits of S4 0.3.2, as the on-prem [S4 guide](https://github.com/eyelevelai/groundx-on-prem/blob/53cf055e5437b8e619b0f4a2f2e27459a922eee2/docs/storage/s4.md#limits) lists them:

- One replica, so no high availability ([chart values](https://github.com/rh-aiservices-bu/s4/blob/797911cbaa1b44fcaecfdfe69145a6a904ef7463/charts/s4/values.yaml#L4)).
- Thousands to tens of thousands of objects per bucket ([S4 FAQ](https://github.com/rh-aiservices-bu/s4/blob/797911cbaa1b44fcaecfdfe69145a6a904ef7463/docs/operations/faq.md#how-many-objects-can-s4-handle)).
- The image is built for `linux/amd64` only.
- Kubernetes health checks cover only the web UI port (5000), not the S3 port (7480) that GroundX uses.
- In S4 mode, large-file import and review (large-file delivery, off by default) refuse files larger than 5 GiB, the largest single upload S4 accepts, before uploading them. They also spool each upload to a temporary file in the pod's `TMPDIR` on top of the importer's own copy, so they need temporary pod disk of about twice the largest file for each upload in flight.
- Long object keys fail. S4 limits the whole key, path included, as sent URL-encoded: in GroundX's tests on S4 0.3.2 it stored keys of up to 246 bytes in a single upload and 210 bytes in a multipart upload, and refused longer ones. Each `/` counts as 3 bytes, and each non-ASCII character counts as its URL-encoded length (9 bytes for a 3-byte UTF-8 character, as in Chinese or Japanese), so such file names fail much sooner. A file name fails below those figures by the length of the path GroundX puts in front of it. Extraction trace capture saves on S4 from chart 0.2.8.
- The access key and secret key are fixed when S4 first starts on its volume. In GroundX's tests, after a restart with new credentials, S4 refused the new keys (`InvalidAccessKeyId`) and kept accepting the first ones.
- Bucket creation outside region `us-east-1` fails. GroundX services always use `us-east-1` for `s4` and ignore a configured region.
- Write-once (creating an object only if its key is absent) holds only for writers that do not overlap in time. In GroundX's tests, when eight writers created the same new key at once, two of them both succeeded in 3 of 40 rounds: both were told they had created the object, and only one writer's content was kept.

Connect a new GroundX install to S4 with the S4 access key and secret key as `file.username` and `file.password`. The URL is `http://<s4-service>.<namespace>.svc.cluster.local:7480`; leave `file.existing.region` unset, because S4 always uses `us-east-1`. When S4 replaces an existing MinIO store, use the migration rule below instead: it keeps the store's URL.

```yaml
file:
  username: <s4-access-key>
  password: <s4-secret-key>
  existing:
    serviceType: s4
    url: http://s4.eyelevel.svc.cluster.local:7480
```

The [S4 install](https://github.com/eyelevelai/groundx-on-prem/blob/53cf055e5437b8e619b0f4a2f2e27459a922eee2/README.md#using-s4) uses S4's git tag with `helm/values/s4/values.yaml`. To copy an existing store, follow [Migrating from MinIO or AIStor](https://github.com/eyelevelai/groundx-on-prem/blob/53cf055e5437b8e619b0f4a2f2e27459a922eee2/docs/storage/s4.md#migrating-from-minio-or-aistor). With `fileAccess.enabled` false, after a copy or on a bucket the deployer created, apply the guide's public-read policy step: GroundX sets the policy only on a bucket it creates itself, and the copy does not carry it. With file access on, skip that step and keep the bucket private (`file-access.md`). GroundX saves each file's full URL, including the store's host and any port, and reads and copies only files whose URL starts with its storage URL. So when S4 replaces an existing MinIO store, GroundX keeps the URL it uses today, with `serviceType: s4`. The guide's migration steps cover a MinIO or AIStor store installed by the on-prem README in namespace `eyelevel`, with `file.existing.url`, `file.customDomain`, `file.serviceName`, and `file.bucketName` unset: they hand Service `minio` to S4 and set `url: http://minio.eyelevel.svc.cluster.local`, without a port. If any of them is set, S4 must answer at exactly the scheme, host, and port GroundX uses today instead; GroundX has not tested that. Uploads stay stopped, with no document still processing, from before the copy until, after the GroundX upgrade, a file link stored before the move loads and a small test document finishes processing. If you cannot confirm that nothing is processing, do not migrate. GroundX has not tested this wait.

A store connected as `serviceType: minio` that keeps a leading `/` in object keys — an S3-compatible store other than MinIO or AIStor — must rename those keys before upgrading GroundX to chart 0.2.8: [Object Keys That Start with a Slash](https://github.com/eyelevelai/groundx-on-prem/blob/53cf055e5437b8e619b0f4a2f2e27459a922eee2/docs/storage/minio-migration.md#object-keys-that-start-with-a-slash).

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
- **`search.password` and `search.privilegedPassword` are required from the first chart release after 0.2.7 whenever `mode` is not `ingest`, with no chart default from that release (published 0.2.7 and earlier still ship the public default, so set both yourself there).** This includes `search.enabled: false` with `search.existing.url` (customer-managed or cloud-managed OpenSearch): the credentials are still needed, supplied by values or by `SEARCH_PASSWORD` / `SEARCH_INIT_PASSWORD` in the cluster credentials Secret (`cluster.secrets`; values win, so leave the values key empty for the Secret route, which applies only from that release, and a Secret-delivered password is not render-validated). In `mode: ingest`, from the first chart release after 0.2.7, neither needs to be set and neither is rendered (published 0.2.7 and earlier still render the defaults). The Secret route needs the `groundx` and `process` images that the same chart release deploys by default (both log in to OpenSearch: the API to search, the indexing worker to write the index); if you override either with `groundx.image` or `process.image`, override both with images built from that chart release or later, and for a tag that is not a version number (such as `chainguard` or a mirrored tag) confirm with the image provider that both images read `SEARCH_PASSWORD` / `SEARCH_INIT_PASSWORD`, or set `search.password` and `search.privilegedPassword` in values instead. The GroundX API provisions `search.username` with `search.password` at startup, authenticating with `search.privilegedUsername` / `search.privilegedPassword`. See `values-authoring.md` section 3.5.4.

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

Discriminator (chart 0.2.7 — `groundx.summary.create` in `templates/_helpers/app/summary.tpl:14–23`, which resolves `groundx.engines` and tests each engine with `groundx.engine.create` in `templates/_helpers/engines.tpl:68–72`):

```go-template
{{- $engines := include "groundx.engines" . | fromYaml -}}
{{- $localNeeded := false -}}
{{- range $engine := $engines -}}
  {{- if eq (include "groundx.engine.create" (dict "root" $ "engine" $engine)) "true" -}}
    {{- $localNeeded = true -}}
  {{- end -}}
{{- end -}}
{{- $localNeeded -}}
```

0.2.7 made this **engine-based**, replacing the 0.2.6 discriminator (which returned internal only when `existing.url` was empty **and** `existing.serviceType` was outside `{openai, openai-base64, azure}`; that fixed allowed-set no longer exists). `groundx.summary.create` now returns `true` (chart deploys the self-hosted summary inference) when **at least one resolved summary engine is local**: `groundx.engine.create` is true for an engine whose resolved `service` is `eyelevel` and whose `baseUrl` is the in-cluster summary API URL. With no `summary.existing` and no `engines` map (the default), the chart builds a single `default` engine that resolves local, so summary runs internally. Setting `summary.existing.*` and declaring engines flips it: any engine whose `service`/`serviceType` is not `eyelevel`, or whose `baseUrl`/`existing.url` points off-cluster, resolves external, and when no engine resolves local the chart skips the self-hosted inference pod.

**On 0.2.7, configuring summary explicitly requires an engine id.** Setting `summary.existing` with no `engines` map fails the render with `explicit summary configuration requires engines.default.engineId`, and every `engines.<name>` must carry a non-empty `engineId`. The schema also requires an `engines.default` entry whenever `engines` is set (`values.schema.json:121–146`), so declare the external engine as `default`:

```yaml
summary:
  existing:
    apiKey: sk-...
    serviceType: openai                # external service identifier (0.2.7 has no fixed allowed-set)
    # url is OPTIONAL for well-known service shapes; set it for custom/Azure/on-prem endpoints
    # url: https://api.openai.com/v1
engines:
  default:
    engineId: <external-model-or-deployment-id>   # REQUIRED on 0.2.7 when summary is configured
```

`url` can be omitted for well-known service shapes (the application has built-in URL handling); set it for custom routing, on-prem OpenAI-compatible gateways, or Azure deployment paths.

Credential resolution runs through the engine, not a single `existing.apiKey` field: `groundx.summary.apiKey` (`summary.tpl:34–38`) reads the resolved `default` engine's `apiKey`, and `groundx.engine.settings` (`engines.tpl:22–30`) falls back to `admin.apiKey` only for a **local** engine — an external engine inherits `summary.existing.apiKey` (or an explicit `engines.default.apiKey`). See `engines.md` § 2 for the full picture.

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

The stream subsystem has one additional substitution path the others lack: **per-topic `type`**. Each topic block inside `stream.topics.<topic-name>` accepts a `type:` field that defaults to `kafka`. The helper at `templates/_helpers/services/topics.tpl:27–38` branches on this — when `type: kafka`, the broker, groupId, and topic-name fields are populated for the Kafka client; when set to anything else (typically `sqs` for AWS SQS), the broker/groupId/topic-name fields are omitted and the topic config carries only `key/region/secret/token/url`, which the application's runtime consumes as cloud-queue credentials.

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

### 6.3 SQS vs MSK for production EKS — which to choose

Both Amazon SQS and Amazon MSK (managed Kafka) are valid AWS-managed queues for the stream subsystem, but they differ sharply in chart support and semantics. For a **production EKS deployment the recommended default is SQS**, which is also the shape the chart's AWS-EKS example pre-selects (§ 6.2, `src/groundx/values/values.aws.services.yaml`). The rationale:

| | SQS (recommended default) | MSK (managed Kafka) |
| --- | --- | --- |
| **Chart wiring** | First-class: per-topic `type: sqs` + `url`, with labeled recipes in § 6.1 / § 6.2. | Generic existing-Kafka path only (`stream.existing.domain`, § 4.5); no MSK-specific recipe beyond that. |
| **Auth from the chart** | Fully wirable from values: IRSA (url-only per topic) or per-topic `key`/`secret`/`region`. | **Not wirable from the chart.** Chart 0.2.7 has no Kafka keystore/truststore or SASL-SCRAM mount, so MSK TLS/SASL/IAM auth needs an out-of-chart path (`tls-and-certs.md` § 4.4). |
| **Operational model** | Fully managed, no brokers to size or run. Changes queue semantics: ordering, batching, and a 10+ minute visibility timeout per queue (§ 6.2). | Managed brokers you still size, patch-window, and pay for. Preserves Kafka semantics (ordering, replay, consumer groups). |
| **Cross-region DR** | SQS is regional and does not replicate cross-region; rebuild queues per region. | Kafka topics replicate via MirrorMaker2 / MSK replication (`dr-cross-region-runbook.md` § 2). |

**Choose SQS** unless you specifically need Kafka semantics (strict per-partition ordering, message replay, or existing Kafka consumer tooling). **Choose MSK only if** you need those *and* can supply broker auth outside the chart, because the chart cannot render MSK TLS/SASL/IAM credentials today.

**Wiring MSK (the labeled path).** MSK is configured through the generic existing-Kafka block in § 4.5: set `stream.existing.domain` to the MSK bootstrap-broker endpoint and `port: 9094` (TLS). The chart connects its Kafka client to that broker, but it does **not** render MSK authentication material — `stream.{key,secret,region}` are SQS fallback credentials, **not** Kafka SASL credentials (§ 4.5). MSK IAM authentication and SASL/SCRAM therefore require an application-supported environment contract verified separately, a service mesh or proxy, or a reviewed chart change (`tls-and-certs.md` § 4.4). Settle that auth path before committing to MSK.

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
| `<svc>.existing.<discriminator>` non-empty | The chart skips chart-deploying that subsystem. Subsystem-specific replicas, resources, persistence, and node-selector fields under `<svc>` are ignored. Operator dependencies (Strimzi for stream, Percona for db, the MinIO AIStor operator for file) are no longer required. |
| `<svc>.existing.<discriminator>` empty + `enabled: false` | The chart neither deploys the subsystem nor routes to an existing one. The application's runtime config will lack the service. **For most subsystems this breaks the pipeline.** Only valid when the deployment mode actively skips the subsystem (e.g., `mode: ingest` legitimately removes search). |
| `db.existing.ro` set but `db.existing.rw` empty (or vice versa) | The chart's `groundx.db.existing` helper returns false (both must be set). The chart then ignores both values and points every service at the in-cluster Percona hostnames; with no in-cluster Percona, pods wait at wait-for-database or fail to connect. **Set both or neither.** |
| `summary.existing.serviceType` to any non-`eyelevel` value (e.g., `openai`, `bedrock`) | On 0.2.7 you must also declare `engines.default.engineId` or the render fails. With engines declared, any non-`eyelevel` service resolves the engine external, so `groundx.summary.create` returns false and no self-hosted inference pod is rendered. There is no fixed allowed-set on 0.2.7; whether the runtime can actually reach the named service is a separate application concern (set `existing.url` for any endpoint without a built-in shape). See `engines.md` § 2. |
| Chart-deployed mode + cluster lacks the required operator | Pods stay pending. For Kafka, Strimzi must be installed first. For MySQL via the Percona operator path, similar. The chart renders the StatefulSet but the operator-owned CRDs won't materialize without their operator. |

## 9. What gets rendered where — chart vs separate Helm releases

Despite the "chart-deployed" terminology, the GroundX Helm chart only renders Kubernetes resources for a subset of the subsystems. The rest are installed via separate Helm releases that the deployer applies *before* the GroundX chart. Values files seeding those releases ship under `src/groundx/values/`:

| Subsystem | What the GroundX chart renders | What the deployer installs separately |
| --- | --- | --- |
| **cache** | `cache.yaml` + `cache-metrics.yaml` — Redis StatefulSets, in-cluster. | Nothing. |
| **db** | Nothing. | Percona XtraDB operator + cluster CR. Values under `src/groundx/values/percona/`. |
| **file** | Nothing. | MinIO AIStor operator + object store. Values under `src/groundx/values/aistor/`. Or S4, values under `src/groundx/values/s4/`, connected through `file.existing` with `file.existing.serviceType: s4` (§ 4.3). |
| **search** | Nothing. | OpenSearch via its own Helm chart. Values under `src/groundx/values/opensearch/`. |
| **stream** | `stream-topics.yaml` — `KafkaTopic` CRDs only. The cluster itself is not rendered. | Strimzi Kafka operator + `Kafka` CR. Values under `src/groundx/values/strimzi/`. (Kafka topics rendered by the GroundX chart require Strimzi to be running so the operator picks up the CRDs.) |
| **summary** | `inference.yaml` — self-hosted gemma inference pod. | NVIDIA GPU operator (cluster-wide). |

So the install ordering matters: **the prerequisite operator Helm releases must come first**, otherwise the GroundX chart's CRD references (e.g., `KafkaTopic`) and connection-string assumptions will fail. See `install-flow.md` for the recommended sequence and `services-prereqs.md` for the operator inventory.

See `services-operators.md` for per-operator installation specifics.

## 10. Authoring discipline

When designing a values.yaml for a new deployment:

1. **Decide per-subsystem before writing config.** The substitution choice for each of cache, db, file, search, stream, summary is independent. Make all six decisions explicitly before writing any values.
2. **For each substituted subsystem, gather the connection details first.** Discriminator field plus credentials. Don't write half-substituted values blocks.
3. **Run `helm template` before `helm install`.** The chart's helpers fail the render on a few shape issues, for example an explicit summary configuration without `engines.default.engineId`. Catch these locally before the cluster does. A database block with only one of its two endpoints set does not fail the render (see § 8).
4. **Network reachability is your problem.** The chart writes connection strings into `config.yaml`. It does not provision NetworkPolicies, VPC peering, or DNS. For each substituted subsystem, verify the cluster can reach the endpoint before installing.
5. **Backup posture shifts.** Chart-deployed subsystems are backed up by your in-cluster tooling. Substituted subsystems are backed up by the deployer's existing infra. Don't assume the chart-substitution decision is purely operational; it changes who's responsible for data durability.

## 11. What this file does not cover

- **Operator installation specifics (Strimzi, Percona, MinIO AIStor operator, NVIDIA operator)** → `services-operators.md`.
- **Per-subsystem credential mechanics** → `credentials.md`.
- **Field-by-field schema for `<svc>` blocks** → `values-yaml.md`.
- **Discovery questionnaire for substitution decisions at install time** → `values-authoring.md`.
- **Summary engine semantics (allowed serviceTypes, vision flag, reasoningEffort)** → `engines.md`.
- **TLS / certificate handling for substituted services** → `tls-and-certs.md`.
- **Deployment-mode interactions (`mode: ingest` forcing search.create to false)** → `deployment-modes.md`.
- **Cost implications of chart-deployed vs cloud-managed** → `cost-estimation.md`.
