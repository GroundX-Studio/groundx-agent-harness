# Summary Service

The summary service is the **LLM-calling tier** of GroundX — the pods that execute the agentic pipeline's document / section / chunk agents. It is the **summary triple**: `summary-client` (always present when summary is enabled), and the optional bundled self-hosted stack `summary-api` + `summary-inference` (when `summary.create=true`). The agentic-pipeline-altitude framing (what agents do, what they produce) lives in `agentic-pipeline.md`; this file documents the pods, the engine taxonomy, and the operating modes.

## 1. Marketing altitude

Not the canonical place — see `agentic-pipeline.md` § 1.

## 2. Product altitude

The summary service is what runs the LLM calls during ingest. Deployments choose where those calls go: a bundled self-hosted LLM (the convenience option for customers who don't already operate one), a third-party LLM service (OpenAI, Azure, DeepInfra, and others), or a customer's existing self-hosted LLM endpoint. The choice is a `values.yaml` decision; the agentic pipeline does not change behavior depending on which path is selected.

## 3. Conceptual / algorithmic altitude

Two architectural ideas drive the design:

**`summary-client` is engine-agnostic.** Every LLM target looks like a 3rd-party API from `summary-client`'s perspective — including the bundled self-hosted stack, which exposes the same call shape through `summary-api`. This lets the agentic pipeline run against any of the supported engines without per-engine branching in the orchestration layer.

**Engine selection is mostly an accounting / routing decision, with two protocol exceptions.** Most engine IDs (`hosted`, `openai`, `azure`, `eyelevel`) differ primarily in which credentials and which endpoint receive the call — i.e., they route the same logical LLM call shape to different accounts. Two engine IDs (`openai-base64`, `deep-infra`) are protocol-distinct rather than account-distinct. Because most LLM providers ignore the model name embedded in the payload anyway, choosing an engine is closer to "which account does this call hit" than "which model architecture answers."

## 4. System altitude

The summary path traverses three pods in the bundled-self-hosted case and one pod in the 3rd-party / customer-hosted cases:

```
pre-process → (queue, file-summary) → summary-client → summary-api → (Celery) → summary-inference   (bundled self-hosted)
                                                    └─ API → 3rd-party LLM                          (OpenAI / Azure / DeepInfra / EyeLevel-hosted)
                                                    └─ API → customer LLM endpoint                  (engine ID pointed at customer URL)
summary-client → (queue) → pre-process (callback)
```

`summary-client` always speaks something that looks like a 3rd-party API; `summary-api → summary-inference` is Celery (intra-stack). For the full topology see `overview.md` § 4.5.

## 5. Implementation altitude

### 5.1 Pods

| Pod | Runtime | CPU/GPU | Conditional | Role |
| --- | --- | --- | --- | --- |
| `summary-client` | Python | CPU | Present when summary is enabled (`summary.create=true` or `summary.serviceType` set) | API client; orchestrates the LLM calls; receives work over queue `file-summary` from `pre-process`; sends callback over queue when done |
| `summary-api` | Python | CPU | Only when `summary.create=true` (bundled self-hosted) | Fronts `summary-inference`; presents the same shape to `summary-client` that a 3rd-party LLM endpoint would |
| `summary-inference` | Python | **GPU** (no reliable CPU fallback; some models support CPU but it cannot be counted on architecturally) | Only when `summary.create=true` | The self-hosted LLM |

### 5.2 Engine taxonomy

`summary.serviceType` (or equivalent in `values.yaml`) selects the engine. The supported engine IDs:

| Engine ID | Distinction | Notes |
| --- | --- | --- |
| `hosted` | Routing | Bundled self-hosted (`summary-api` + `summary-inference`) — same call shape as a 3rd-party endpoint |
| `openai` | Routing | OpenAI's hosted API |
| `azure` | Routing | Azure OpenAI |
| `eyelevel` | Routing | EyeLevel-hosted endpoint |
| `openai-base64` | Protocol-distinct | Payload-shape variant of the OpenAI path |
| `deep-infra` | Protocol-distinct | DeepInfra-specific protocol shape |

Four of the six engine IDs (`hosted`, `openai`, `azure`, `eyelevel`) are best thought of as **routing / accounting labels** — they configure which account and endpoint the call goes to. The other two (`openai-base64`, `deep-infra`) reflect actual protocol-shape differences. Most LLM providers ignore the `model` field included in the payload, so the engine ID does more routing than model-selection work in practice.

### 5.3 Enable / disable behavior

Summary execution is governed by two related settings:

- `summary.create=true` — explicit bundled-self-hosted enable; brings up `summary-api` + `summary-inference`.
- Setting a 3rd-party `summary.serviceType` — implicitly disables the bundled self-hosted stack (the 3rd-party path is exclusive of `summary.create=true`).
- Setting `processLevel = none` on an ingest request — skips the summary pass entirely for that document (per `agentic-pipeline.md` § 3).

The **customer-hosted-LLM mode** is not a distinct engine ID — it's configured by pointing one of the existing engine IDs at a customer's URL. The deployment ends up looking like a 3rd-party call from `summary-client`'s perspective.

## 6. Security / compliance altitude

The trust-boundary shape differs by operating mode (per `agentic-pipeline.md` § 6):

1. **3rd-party LLM** (`openai` / `azure` / `openai-base64` / `deep-infra` / `eyelevel` pointed at a hosted endpoint) — document content leaves the GroundX deployment's trust boundary on every LLM call.
2. **Bundled self-hosted** (`summary.create=true`, engine `hosted`) — content stays inside the deployment.
3. **Customer-hosted LLM** (an engine ID pointed at a customer URL) — content stays inside the customer's trust boundary.

For the full identity / trust model see `identity-and-trust.md`. For data-residency implications see `data-residency.md`.

## 7. Operations / SRE altitude

`summary-inference`, `summary-api`, and `summary-client` (in external-LLM mode) are metered as **inference-class** tokens-per-minute in the `metrics` pod (per `overview.md` § 4.7). When self-hosted, `summary-inference` is the GPU pod that scales against the inference TPM signal; when running against a 3rd-party or customer LLM, the queue back-pressure on `summary-client` is the autoscaling lever. For the broader observability framing see `observability.md`.

## 8. Data architecture altitude

**Inputs:** the typed elements from the layout pipeline (per `vision-model.md` + `layout-ocr.md`) — tables, paragraphs, figures with their constituent words.

**Outputs:** the agentic-pipeline output that becomes the X-Ray (file storage) + JSONL chunks (OpenSearch) at the terminal `process` step (per `agentic-pipeline.md` § 8 + `store.md` § 8). `summary-client` also writes summary intermediate artifacts to file storage during the run.

## 9. Cost / FinOps altitude

`summary-inference` is the **largest GPU cost driver** in default deployments (per `data-flow.md` § 9 + `agentic-pipeline.md` § 9). The dominant cost-shape decision at this altitude is **bundled self-hosted vs 3rd-party** — opting into a 3rd-party engine shifts GPU cost to per-call API fees; opting into a customer-hosted endpoint shifts it onto the customer's infrastructure. The element-level architecture (per `vision-model.md` § 3 + `agentic-pipeline.md` § 3) is what makes smaller-context-window LLMs sufficient for each agent, which keeps `summary-inference` cost competitive against pure pure-frontier-LLM approaches. Deployment-level cost framing is owned by `groundx-on-prem`.

## 10. What this topic does not cover

- **What the agents do** (document / section / chunk-level work, chunk instruction step for tables and figures): `agentic-pipeline.md`.
- **The X-Ray output shape** and the JSONL chunks: `agentic-pipeline.md` § 5 + § 8.
- **The layout pipeline** that produces the typed elements the agents work on: `vision-model.md`, `layout-ocr.md`.
- **The hybrid-search path** that reads the JSONL chunks: `hybrid-search.md`.
- **Per-deployment engine selection guidance** and the `values.yaml` selector specifics: `groundx-on-prem`.
- **The exact payload shape per engine ID**: implementation detail; not architecturally meaningful at this altitude.
