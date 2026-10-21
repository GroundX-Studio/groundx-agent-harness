# Summary Engine Selection

This file documents **the LLM-engine decision a deployer makes once during install** — self-hosted vs external (the well-known `openai` / `openai-base64` / `azure` shapes plus any custom OpenAI-compatible URL), the cost / trust / latency / quality trade-offs, the values.yaml field shape per option, and the cross-field implications.

The summary engine is the single largest cost lever in a GroundX deployment. The decision interacts with cluster sizing (GPU vs no-GPU), trust boundaries (does document content leave the cluster?), and ongoing operational cost (GPU hours vs API tokens).

For the discovery-question framing that surfaces this decision at install time, route to `values-authoring.md` § 3.4. For the architectural picture of the summary stack, route to `groundx-architecture/references/summary-service.md`. For the credential pattern that protects the outbound API key, route to `credentials.md` § 9 (workload identity does **not** cover LLM API keys).

**Runtime boundary:** this is install-time deployment configuration. It decides how the
on-prem summary service is wired when the Helm chart renders. It is not the runtime API
surface for assigning workflows or changing a single workflow step's model endpoint. For
runtime workflow assignment and workflow-step `engine` configuration, route to
`groundx-api/references/06-workflows.md` and `groundx-api/guides/09-workflows.md`.

**Mode guard:** this file is on-prem only. Do not use Gemma 3, vLLM, or
`eyelevel-gpu-summary` as the answer to a hosted cloud sandbox model question.
For cloud sandbox defaults, verify the current cloud default from a cloud-mode
source before naming a model.

## 1. The engine options

The chart's `groundx.summary.create` helper (in `src/groundx/templates/_helpers/app/summary.tpl`) decides whether to deploy the in-cluster summary stack. On chart 0.2.7 this is **engine-based** (it replaced the 0.2.6 rule that keyed on a fixed `{openai, openai-base64, azure}` serviceType set):

```
self-hosted ← at least one resolved summary engine is LOCAL
              (engine service == "eyelevel" AND engine baseUrl == the in-cluster summary API URL)
```

The chart resolves `engines` (via `groundx.engine.settings`) and deploys self-hosted if any engine resolves local. With no `summary.existing` and no `engines` map — the default — the chart builds one `default` engine that resolves local, so self-hosted runs. A deployer disables self-hosted by configuring `engines` so no engine resolves local: set the engine's `service`/`serviceType` to anything other than `eyelevel`, or point its `baseUrl` (or `summary.existing.url`) off-cluster. **0.2.7 also requires an engine id once summary is configured explicitly:** setting `summary.existing` with no `engines` map fails the render with `explicit summary configuration requires engines.default.engineId`, and every `engines.<name>` must carry a non-empty `engineId`. The schema also requires an `engines.default` entry whenever `engines` is set (`values.schema.json:121–146`).

| Option | `summary.existing.serviceType` | URL required? | What it is |
| --- | --- | --- | --- |
| **Self-hosted Gemma 3** | unset, or `eyelevel` with no off-cluster URL | n/a (self-hosted) | Bundled vLLM-served Gemma 3 model running on the cluster's GPU node group. Default. No external network egress from the summary path. |
| **External OpenAI** | `openai` | optional (default OpenAI endpoint applied) | OpenAI public endpoint (`api.openai.com/v1/chat/completions`). |
| **External OpenAI base64** | `openai-base64` | optional | OpenAI public endpoint with image data base64-encoded in-request (vs URL-passed). Use when the OpenAI endpoint can't reach the cluster's object store for image fetches. |
| **External Azure OpenAI** | `azure` | recommended | Azure-hosted OpenAI deployment. URL points at the specific Azure deployment id. |
| **External via custom URL** | any other value (typically the engine name, e.g. `deep-infra`) | **required** | Any OpenAI-compatible endpoint without a built-in shape. The chart passes `serviceType` through to the runtime config as the engine `service:` field. On 0.2.7 any non-`eyelevel` value resolves the engine external; the URL is where the runtime sends requests. |

**Gotchas:**

- `eyelevel` is the chart's *default* `summary.existing.serviceType` (when omitted entirely), and it is the one value that resolves **local**. That default is why an unconfigured chart still deploys self-hosted — `eyelevel` is **not** an external engine selector. Writing `serviceType: eyelevel` with no off-cluster `url`/`baseUrl` leaves the engine local and self-hosted enabled.
- Any non-`eyelevel` `service`/`serviceType` resolves external (self-hosted skipped); an `eyelevel` engine pointed at an off-cluster `baseUrl`/`summary.existing.url` also resolves external. There is no fixed recognized-name set on 0.2.7.
- Once you set `summary.existing` or any `engines.<name>`, each engine needs a non-empty `engineId`, or the render fails.

## 2. Decision matrix — five dimensions

The summary engine choice trades off five dimensions. No engine wins on all five.

| Dimension | Self-hosted | External (OpenAI / Azure OpenAI / any OpenAI-compatible URL) |
| --- | --- | --- |
| **GPU cost** | High — the default summary values need a 48 GB GPU (e.g. NVIDIA L40S on `g6e.xlarge`); a 24 GB card runs one copy with the `cluster-requirements.md` § 2.3 values. This GPU is usually the deployment's dominant cost line. | None. Pure pass-through to the external API. |
| **Per-call cost** | Free (after GPU is provisioned). | Pay-per-token. At OpenAI gpt-5-mini rates: ~$1 per million input tokens, ~$3 per million output tokens. Per-document costs scale linearly with document size. |
| **Trust boundary** | Closed — document content stays inside the cluster. The summary pipeline reads from in-cluster object store and writes back to in-cluster OpenSearch. **Critical for FedRAMP, regulated verticals, and air-gapped deployments.** | Open — document content (preprocessed chunks) leaves the cluster on every summary call. Trust-boundary crossing. See `groundx-architecture/references/summary-service.md` § 6 + `groundx-architecture/references/identity-and-trust.md` § 6.2. |
| **Latency floor** | Low — GPU inference is in-cluster, sub-second per call after model warm-up. | Network-bound — adds 200–800 ms per call depending on geo + LLM provider load. Cold-start jitter on the LLM side. |
| **Output quality** | Gemma 3 4B — strong for the summary use case, but a smaller open model than GPT-5 / Claude. | OpenAI / Azure / Anthropic models often outperform Gemma 3 on edge cases. Quality vs cost trade-off, not a winner-take-all. |

**Two general patterns:**

1. **Regulated / air-gapped → self-hosted.** Trust boundary is non-negotiable. GPU cost is the price of compliance.
2. **Public-cloud non-regulated → external.** Avoids GPU operational burden, pays per-call. For most non-regulated deployments this is cheaper than running a 24/7 GPU just to serve summaries.

## 3. Field shape per option

### 3.1 Self-hosted Gemma 3 (default)

No `summary.existing` block. Self-hosted is enabled by default:

```yaml
summary:
  api:
    enabled: true
  inference:
    enabled: true                # required; defaults sized for a 48 GB GPU
    deviceUtilize: 0.48          # default; per copy, 2 copies share one GPU
    model:
      name: google/gemma-3-4b-it
      # dataType, maxInputTokens, maxOutputTokens, maxRequests, swapSpace tunable
```

**Cluster prerequisites:**
- A node in the `eyelevel-gpu-summary` node group with a 48 GB GPU for the default summary values, or a 24 GB GPU with the single-copy values in `cluster-requirements.md` § 2.3 (tested on an NVIDIA A10G only).
- NVIDIA GPU Operator installed.

**Sizing:** the chart default is `summary.inference.replicas.desired: 2`, two copies at `summary.inference.deviceUtilize: 0.48`. The copies share the summary GPU unless `summary.inference.resources` requests `nvidia.com/gpu`, so keep copies × `summary.inference.workers` × `summary.inference.deviceUtilize` at or below 1 per summary GPU node. To scale out, add summary GPU nodes and give each copy its own GPU through `summary.inference.resources`; see `autoscaling.md` § 8.

For the per-microservice fields, see `values-yaml.md` § 5.5.

### 3.2 External — OpenAI

```yaml
summary:
  api:
    enabled: false
  inference:
    enabled: false
  existing:
    serviceType: openai
    # url: optional; defaults to api.openai.com/v1/chat/completions
    apiKey: <openai-api-key>     # treat as credential — see credentials.md
engines:
  default:
    engineId: <model-id>         # required on chart 0.2.7
```

**Cluster impact:** `eyelevel-gpu-summary` node group no longer needed. The summary microservices don't render at all.

**Egress:** outbound HTTPS to `api.openai.com`. Allow this in NetworkPolicy if the cluster has a default-deny posture.

**Cost model:** per-token. Estimate ~10× cheaper than running a 24/7 GPU for low-volume deployments (< 100k summaries/month). The break-even crosses around 100k–1M summaries/month depending on GPU SKU and document size.

### 3.3 External — OpenAI base64

```yaml
summary:
  existing:
    serviceType: openai-base64
    # url: optional (OpenAI default)
    apiKey: <openai-api-key>
engines:
  default:
    engineId: <model-id>         # required on chart 0.2.7
```

Same as OpenAI, but **image data is base64-encoded in-request** instead of URL-fetched by OpenAI. Use this when:

- The cluster's object store isn't reachable from the public internet (private VPC).
- Compliance forbids cross-internet URL fetch by a third-party service.
- Latency optimization (avoid the round-trip OpenAI → S3).

**Cost impact:** larger request payloads (image bytes inline). Modest per-call latency increase. Cost-per-summary is comparable to plain `openai`.

### 3.4 External — Azure OpenAI

```yaml
summary:
  existing:
    serviceType: azure
    url: https://<resource-name>.openai.azure.com/openai/deployments/<deployment-name>
    apiKey: <azure-openai-key>
engines:
  default:
    engineId: <model-id>         # required on chart 0.2.7
```

**When to choose:**
- AKS deployment where the LLM call should stay inside the Azure cloud boundary (no traffic across Microsoft ↔ OpenAI infrastructure).
- Procurement-mandated Microsoft-first stack.
- Azure-specific rate-limit guarantees.

**Cost model:** Azure passes through OpenAI's per-token pricing with Azure's own markup. Comparable to direct OpenAI within 5–15%.

**URL is required** (unlike `openai` which defaults). The URL must include the specific deployment ID.

### 3.5 External — DeepInfra (or any custom OpenAI-compatible endpoint)

```yaml
summary:
  existing:
    serviceType: deep-infra           # passed through to runtime config as engine `service:`
    url: https://api.deepinfra.com/v1/openai   # required: the runtime has no built-in endpoint for deep-infra
    apiKey: <deepinfra-api-key>
engines:
  default:
    engineId: <model-id>              # required on chart 0.2.7
```

**Important caveat:** on chart 0.2.7 a `serviceType` of `deep-infra` (any non-`eyelevel` value) resolves the engine external on its own, so the chart skips self-hosted regardless of `url`. The `url` is still **required for the application to reach DeepInfra at runtime** (DeepInfra has no built-in endpoint the way the well-known shapes do) — omitting it points the engine at no reachable endpoint, not back at self-hosted. (On 0.2.6 the chart's skip decision keyed on a fixed `{openai, openai-base64, azure}` set OR a non-empty `url`, so `deep-infra` without a `url` left self-hosted enabled; 0.2.7 removed that set.)

**When to choose:**
- Cost optimization. DeepInfra is often 2–5× cheaper than OpenAI for equivalent open-source models.
- Open-model alignment (DeepInfra hosts Llama 3, Mixtral, etc. via OpenAI-compatible endpoints).
- Any OpenAI-compatible endpoint the chart doesn't natively recognize.

### 3.6 The `eyelevel` default is *not* an external engine

`eyelevel` is the chart's **default** `summary.existing.serviceType` when the deployer omits it entirely. It is NOT an external-engine selector — the chart's `summary.create` helper does not treat `eyelevel` as "skip self-hosted." A deployer cannot route summary calls to an EyeLevel-hosted endpoint by writing `serviceType: eyelevel` alone.

If EyeLevel-hosted summary is part of the procurement bundle, the procurement materials should specify the endpoint URL and API key; use Pattern § 3.5 (custom URL) to point at it.

## 4. Cross-field implications

| Set this... | …and this is implied or required |
| --- | --- |
| `summary.existing.serviceType: openai` (or `openai-base64`, `azure`, or any non-`eyelevel` value) + `engines.default.engineId` | the engine resolves external, so `groundx.summary.create` returns false — chart skips deploying `summary-api` + `summary-inference`. `eyelevel-gpu-summary` node group not needed. URL optional for OpenAI / OpenAI-base64; recommended for Azure; required for any endpoint without a built-in shape. |
| `summary.existing.url: <off-cluster-url>` with an `eyelevel`/default engine + `engines.default.engineId` | the engine's `baseUrl` resolves off-cluster, so `groundx.summary.create` returns false — same effect. Use this path for a custom OpenAI-compatible endpoint or EyeLevel-hosted summary. |
| `summary.existing` set with **no** `engines` map | **Render fails** (`explicit summary configuration requires engines.default.engineId`). 0.2.7 requires a declared engine with an id once summary is configured explicitly, and the schema requires that `engines` include a `default` entry. |
| `summary.existing.serviceType: eyelevel` with no off-cluster `url`/`baseUrl` | Engine resolves **local** — self-hosted **stays enabled**. `eyelevel` is the local default, not an external selector. |
| `summary.existing.apiKey` set inline | Treat as credential — move to `cluster.secrets`-referenced Secret or ESO. See `credentials.md` § 5–§ 6. |
| External engine selected | Document content leaves the cluster on every summary call. Audit NetworkPolicy egress for the chosen endpoint. Update `groundx-architecture/references/data-residency.md` posture. |
| No GPU available in the cluster | Forces external engine. Self-hosted Gemma 3 is not viable. (CPU fallback for the summary inference path is not architecturally supported.) |
| Self-hosted + want HPA | Enable `cluster.hpa` and `metrics.enabled`, then tune `summary.inference.replicas.{min,max}` and `throughput.services.summary.{api,inference}`. Copies share a GPU by default, so cap `summary.inference.replicas.max` at the copies the summary GPUs hold and give each copy its own GPU through `summary.inference.resources` (`autoscaling.md` § 8). |

## 5. Workload identity does NOT cover this

A common assumption: "we're using IRSA on EKS, so we don't need to manage the LLM API key separately."

That assumption is wrong. Workload identity (IRSA / Workload Identity / WIF) binds the cluster's Kubernetes ServiceAccount to a *cloud* IAM role. It covers AWS / Azure / GCP cloud services — S3, RDS, SQS, ElastiCache, etc.

OpenAI, Azure OpenAI, DeepInfra, EyeLevel are **third-party API services outside the cloud IAM perimeter**. They authenticate via their own API key, not the cluster's IAM role. Even with workload identity configured, the LLM API key (`summary.existing.apiKey`) must be supplied via Pattern 3 (Kubernetes Secret reference) or higher. See `credentials.md` § 9 for the full list of what workload identity does and doesn't cover.

## 6. Switching engines after install

Switching is supported but not instant:

1. Update `summary.*` values.
2. `helm upgrade --install groundx ./src/groundx -f values.<env>.yaml -f values.<env>.secret.yaml`.
3. The chart re-renders the summary microservices. If switching from self-hosted to external:
   - `summary-api` and `summary-inference` pods are deleted.
   - `summary-client` (which orchestrates calls) is restarted with new env.
4. If switching from external to self-hosted:
   - `summary-api` and `summary-inference` pods are created.
   - GPU node group must already have a GPU available.
   - Wait for inference pods to be `Ready` before traffic flows reliably.

In-flight summary requests during a switch fail. Drain documents before switching in production, or accept some failed jobs that will need re-ingestion.

## 7. Cost-vs-trust quick guide

The two-axis decision most deployments face:

```
                       Trust boundary closed
                              │
   self-hosted Gemma 3        │
   (regulated, air-gapped)    │
                              │
   ───────────────────────────┼───────────────────────────────
   high GPU cost              │              high API-token cost
                              │
   ─                          │     OpenAI / Azure / DeepInfra
   (no good option)           │     (public cloud, non-regulated)
                              │
                       Trust boundary open
```

- **Top-left (self-hosted):** regulated / air-gapped. GPU is the cost of trust. Don't fight it.
- **Bottom-right (external):** public cloud, non-regulated. API tokens are the cost. Don't run a 24/7 GPU unless throughput warrants.
- The middle area (mixed regulated workload, partially open trust boundary): unusual. Most deployments cleanly belong to one quadrant.

## 8. External Bedrock extraction

Bedrock is a per-workflow extraction provider, separate from the install-time summary engine. Configure the extract runtime and AWS S3 storage once, then select `service: bedrock` only in workflows that should use it:

```yaml
file:
  enabled: false
  bucketName: <bucket-name>
  existing:
    serviceType: s3
    url: https://s3.us-west-2.amazonaws.com
    region: us-west-2

extract:
  enabled: true
  agent:
    enabled: true
    serviceType: bedrock
    apiBaseUrl: https://bedrock-mantle.us-west-2.api.aws/openai/v1
    modelId: google.gemma-4-31b
    existingSecret: true
    secretName: <extract-agent-secret>
```

The chart validates that Bedrock has an endpoint, model, API-key source, and S3 file storage. At runtime, the extract agent uses S3 references when the effective request service is Bedrock. Non-Bedrock requests keep their configured image transport. Internal page-image URLs are converted to references in the effective S3 bucket. Existing valid `s3://` references pass through, including references to another bucket.

Allow outbound HTTPS to the configured Bedrock endpoint. The AWS identity behind the Bedrock request must be able to read every referenced object. For a Bedrock API key, grant that access to the IAM principal behind the key. A cross-account bucket also needs a bucket policy. A customer-managed KMS key also needs decrypt permission.

This does not change the default. Extraction remains opt-in, and non-Bedrock workflows keep their current provider and image transport.

## 9. What this file does not cover

- **Field-by-field schema for `summary.*` fields** → `values-yaml.md` § 5.5.
- **Discovery questionnaire that surfaces this decision at install time** → `values-authoring.md` § 3.4.
- **Architectural picture of the summary stack (in-cluster microservices, trust-boundary diagrams, callback pattern)** → `groundx-architecture/references/summary-service.md`.
- **Credential management for `summary.existing.apiKey`** → `credentials.md` § 5–§ 9.
- **Architectural rationale for why workload identity doesn't cover LLM keys** → `groundx-architecture/references/identity-and-trust.md`.
- **GPU sizing for self-hosted (memory, worker / thread tuning)** → `cluster-requirements.md` § 2.2 + `values-yaml.md` § 5.5.
- **Per-engine quality benchmarks** → out of scope; benchmark against the deployer's specific documents.
