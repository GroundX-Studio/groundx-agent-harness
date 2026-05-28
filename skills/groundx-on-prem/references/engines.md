# Summary Engine Selection

This file documents **the LLM-engine decision a deployer makes once during install** — self-hosted vs external (three chart-recognized service types plus a custom-URL escape hatch), the cost / trust / latency / quality trade-offs, the values.yaml field shape per option, and the cross-field implications.

The summary engine is the single largest cost lever in a GroundX deployment. The decision interacts with cluster sizing (GPU vs no-GPU), trust boundaries (does document content leave the cluster?), and ongoing operational cost (GPU hours vs API tokens).

For the discovery-question framing that surfaces this decision at install time, route to `values-authoring.md` § 3.4. For the architectural picture of the summary stack, route to `groundx-architecture/references/summary-service.md`. For the credential pattern that protects the outbound API key, route to `credentials.md` § 9 (workload identity does **not** cover LLM API keys).

**Mode guard:** this file is on-prem only. Do not use Gemma 3, vLLM, or
`eyelevel-gpu-summary` as the answer to a hosted cloud sandbox model question.
For cloud sandbox defaults, verify the current cloud default from a cloud-mode
source before naming a model.

## 1. The engine options

The chart's `groundx.summary.create` helper (in `src/groundx/templates/_helpers/app/summary.tpl`) decides whether to deploy the in-cluster summary stack. The decision boils down to:

```
self-hosted ← (summary.existing.url is empty) AND
              (summary.existing.serviceType is NOT one of {openai, openai-base64, azure})
```

So a deployer disables self-hosted by either (a) setting `summary.existing.url` to a non-empty endpoint, or (b) setting `summary.existing.serviceType` to one of three values the chart's helper recognizes without needing a URL.

| Option | `summary.existing.serviceType` | URL required? | What it is |
| --- | --- | --- | --- |
| **Self-hosted Gemma 3** | unset (or any non-recognized value) AND no URL | n/a (self-hosted) | Bundled vLLM-served Gemma 3 model running on the cluster's GPU node group. Default. No external network egress from the summary path. |
| **External OpenAI** | `openai` | optional (default OpenAI endpoint applied) | OpenAI public endpoint (`api.openai.com/v1/chat/completions`). |
| **External OpenAI base64** | `openai-base64` | optional | OpenAI public endpoint with image data base64-encoded in-request (vs URL-passed). Use when the OpenAI endpoint can't reach the cluster's object store for image fetches. |
| **External Azure OpenAI** | `azure` | recommended | Azure-hosted OpenAI deployment. URL points at the specific Azure deployment id. |
| **External via custom URL** | any value (typically the engine name, e.g. `deep-infra`) | **required** | Any OpenAI-compatible endpoint the chart helper doesn't special-case. The chart passes `serviceType` through to the runtime config as the engine `service:` field, but skip-self-hosted depends on `url` being set, not on the chart recognizing the name. |

**Gotchas:**

- `eyelevel` is the chart's *default* `summary.existing.serviceType` (when omitted entirely). That default means the chart still deploys self-hosted — `eyelevel` is **not** an external engine selector. Don't write `serviceType: eyelevel` expecting it to point at an EyeLevel-hosted endpoint without a URL — that combination leaves self-hosted enabled.
- Setting `serviceType: deep-infra` without a URL leaves self-hosted enabled too. Always pair non-recognized engine names with `summary.existing.url`.
- The application code may support more engine routings via `engines.default.type` at the runtime layer; the chart's `summary.create` skip logic only checks the three special-cased names.

## 2. Decision matrix — five dimensions

The summary engine choice trades off five dimensions. No engine wins on all five.

| Dimension | Self-hosted | External (OpenAI / Azure OpenAI / any OpenAI-compatible URL) |
| --- | --- | --- |
| **GPU cost** | High — needs ≥24 GB GPU (e.g. NVIDIA L4 / A10G / A100). At ~$0.50–$1/hr per GPU on AWS g5, this is the deployment's dominant cost line. | None. Pure pass-through to the external API. |
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
    enabled: true                # required; ~24 GB GPU
    deviceUtilize: 0.48          # default; raise to ~0.95 for max throughput
    model:
      name: google/gemma-3-4b-it
      # dataType, maxInputTokens, maxOutputTokens, maxRequests, swapSpace tunable
```

**Cluster prerequisites:**
- A node in the `eyelevel-gpu-summary` node group with ≥24 GB GPU memory (NVIDIA L4 16 GB is not enough at default model sizing).
- NVIDIA GPU Operator installed.

**Sizing:** chart default `summary.inference.replicas.desired: 1`. Scale up for higher throughput. Each replica needs its own 24 GB GPU.

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
    url: https://api.deepinfra.com/v1/openai   # REQUIRED — chart helper doesn't special-case deep-infra
    apiKey: <deepinfra-api-key>
```

**Important caveat:** the chart's `summary.create` helper does NOT recognize `deep-infra` (or any other non-special-cased value) as an automatic "skip self-hosted" trigger. The chart only skips self-hosted when `serviceType` is `openai` / `openai-base64` / `azure` **OR** when `url` is non-empty. So `deep-infra` requires `url` to be set; otherwise self-hosted stays enabled.

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
| `summary.existing.serviceType: openai` (or `openai-base64`, `azure`) | the chart's `groundx.summary.create` helper returns false — chart skips deploying `summary-api` + `summary-inference`. `eyelevel-gpu-summary` node group not needed. URL optional for OpenAI / OpenAI-base64; recommended for Azure. |
| `summary.existing.url: <some-url>` (regardless of `serviceType`) | the chart's `groundx.summary.create` helper returns false — same effect. Use this path for any non-special-cased engine (`deep-infra`, custom OpenAI-compatible endpoint, EyeLevel-hosted). |
| `summary.existing.serviceType` set to a non-recognized value (`deep-infra`, `eyelevel`, etc.) WITHOUT `summary.existing.url` | Self-hosted **stays enabled**. This is a common footgun — the chart's helper only special-cases 3 names. |
| `summary.existing.apiKey` set inline | Treat as credential — move to `cluster.secrets`-referenced Secret or ESO. See `credentials.md` § 5–§ 6. |
| External engine selected | Document content leaves the cluster on every summary call. Audit NetworkPolicy egress for the chosen endpoint. Update `groundx-architecture/references/data-residency.md` posture. |
| No GPU available in the cluster | Forces external engine. Self-hosted Gemma 3 is not viable. (CPU fallback for the summary inference path is not architecturally supported.) |
| Self-hosted + want HPA | `summary.inference.replicas.{max, hpa, threshold, throughput}` tuned. Each replica needs its own GPU. |

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

## 8. What this file does not cover

- **Field-by-field schema for `summary.*` fields** → `values-yaml.md` § 5.5.
- **Discovery questionnaire that surfaces this decision at install time** → `values-authoring.md` § 3.4.
- **Architectural picture of the summary stack (in-cluster microservices, trust-boundary diagrams, callback pattern)** → `groundx-architecture/references/summary-service.md`.
- **Credential management for `summary.existing.apiKey`** → `credentials.md` § 5–§ 9.
- **Architectural rationale for why workload identity doesn't cover LLM keys** → `groundx-architecture/references/identity-and-trust.md`.
- **GPU sizing for self-hosted (memory, worker / thread tuning)** → `cluster-requirements.md` § 2.2 + `values-yaml.md` § 5.5.
- **Per-engine quality benchmarks** → out of scope; benchmark against the deployer's specific documents.
