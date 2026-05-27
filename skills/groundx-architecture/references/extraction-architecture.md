# Extraction Microservice

The extraction microservice is the **schema-driven QA tier** of GroundX — the optional cluster of pods that produces structured extraction outputs from documents that have already been ingested through layout + the agentic pipeline. It is **opt-in twice**: enabled at the deployment level via `values.yaml` and engaged per-document via the extraction YAML in the workflow API request. QA in this context means **Quality Assurance** — every extracted category passes through a reconciliation step followed by a QA agent before being saved. The authoring side of extraction (YAML schema design, ground-truth comparison, running an extraction workflow against a PDF) lives in the **`groundx-extraction-workflows`** skill; this file documents the runtime microservice.

## 1. Marketing altitude

Extraction stays out of marketing content. The customer-facing framing of structured extraction is owned by `master-brand-gtm` / `product-brand-gtm`; the schema-first authoring story is owned by `groundx-extraction-workflows`.

## 2. Product altitude

The extraction microservice runs after the agentic pipeline produces the X-Ray. When a workflow has an extraction YAML attached, the microservice ingests the X-Ray, walks the schema, runs per-category reconciliation + QA agents, and writes structured extraction output to file storage. Customers retrieve the output through the GroundX API.

## 3. Conceptual / algorithmic altitude

Three architectural ideas shape the extraction microservice:

**Extraction runs against the X-Ray, not the raw layout.** The agentic pipeline must complete first. The X-Ray (the aggregated, enriched JSON for the document — per `agentic-pipeline.md` § 5 + `store.md` § 8) is the single substrate every extraction agent reads from. Running against the X-Ray rather than the raw layout output means extraction agents inherit all the agentic enrichment (summaries, keywords, chunk versions, page URLs) without having to re-derive them.

**Schema-driven sequence.** The extraction YAML in the workflow defines the categories to extract, the reconciliation logic per category, and the QA checks. The microservice executes the sequence the YAML describes — different YAMLs produce different agent sequences (parallel where the schema allows, sequential where dependencies require it). The encoding of the schema, the authoring workflow, and the field-by-field YAML pattern live in the dedicated `groundx-extraction-workflows` skill.

**QA is a per-category step, not a global post-pass.** Every extracted category passes through its own reconcile + QA pair before save. The pattern is `reconcile-<category>` → `qa-<category>` → save (per `agentic-pipeline.md` § 5.1 step 6 + the invoice example in `overview.md` § 4.5). This is what makes extraction outputs trustable in a production pipeline — the QA is structural, not optional.

Use **category** for a functional grouping of fields, such as `statement`, `charges`,
or `meters`. Each category has a corresponding extraction agent that handles
extraction, reconciliation, and QA for that category; extraction agents are **not one
agent per field**. Keep each category's extraction load to about 20 fields or fewer
because higher field counts increase LLM cognitive load and reduce consistency. When a
field set gets larger or crosses a natural document boundary, add another coherent
category instead of adding one agent per field.

## 4. System altitude

The extraction microservice is **4 pods** + the file-storage substrate, entered via API from `pre-process` and exiting via API callback to `layoutWebhook`:

```
pre-process → API → extract-api → Celery: extract-download → parallel agents (reconcile + QA per category) → extract-save → ... → API callback → layoutWebhook → (queue) → pre-process
```

The exact sequence is **schema-driven** — the example invoice schema in `overview.md` § 4.5 fans out into parallel statement / meters reconciliation, then a sequential charges step. Other schemas produce other sequences. The final `extract-save` calls back to `layoutWebhook` (not to `groundx`); `layoutWebhook` enqueues to `pre-process`, which then proceeds to `process` for the terminal write.

## 5. Implementation altitude

### 5.1 Pods

| Pod | Runtime | Role |
| --- | --- | --- |
| `extract-api` | Python | Entry point from `pre-process`; spawns the Celery task chain per the extraction YAML |
| `extract-download` | Python | Fetches the **X-Ray** from file storage; makes it available to the agent pods |
| `extract-agent` | Python | Runs reconcile + QA work per category; same pod handles both stages (reconcile-`<category>` and qa-`<category>`); replica count is a throughput lever as multiple agents run in sequence and in parallel per document |
| `extract-save` | Python | Writes results to file storage; runs multiple times in the sequence; the **final** `extract-save` calls back to `layoutWebhook` (not to `groundx`) |

All 4 pods are Python.

### 5.2 Activation

Extraction is **opt-in at two levels**:

1. **Deployment level** — `values.yaml` enables the extraction microservice (the 4 pods).
2. **Per-workflow** — the workflow API request must include an extraction YAML. Workflows without an attached YAML skip extraction even when the microservice is enabled.

Deployments that don't enable extraction skip the 4 pods entirely.

### 5.3 Sequencing within ingest

Extraction runs **after summary completes** in the ingest pipeline (per `data-flow.md` § 5.1 step 6 + `ingest-service.md` § 5):

```
... → summary (callback to pre-process) → extract (when enabled) → callback via layoutWebhook → pre-process → process (terminal write)
```

The default path (extraction disabled or no extraction YAML attached) skips this stage and goes directly from summary to `process`.

## 6. Security / compliance altitude

The extraction microservice is **entirely in-cluster** — no external LLM provider, no external service calls. All work runs against the X-Ray and the agent pods inside the deployment's trust boundary. For the full identity / trust model see `identity-and-trust.md`.

## 7. Operations / SRE altitude

`extract-api` is metered as **API response time** in the `metrics` pod; the extract sub-pods (download / agent / save) are metered as **Celery task back-pressure** thresholds (per `overview.md` § 4.7). `extract-agent` replica count is the meaningful throughput lever — the pod runs multiple times per document per schema, and high-volume extraction workflows can require significant CPU. For the broader observability framing see `observability.md`.

## 8. Data architecture altitude

**Input:** the X-Ray from file storage (fetched by `extract-download`).

**Per-stage artifacts:** intermediate reconciliation + QA outputs (in file storage during processing).

**Output:** structured extraction output to **file storage**. The retrieval API for extraction output lives in the **`groundx-api`** skill; this skill does not name the endpoint at architecture altitude.

For canonical artifact placement see `store.md` § 5.1.

## 9. Cost / FinOps altitude

The extraction microservice is CPU-only and adds 4 pods to deployments that enable it. Cost drivers:

- **Whether extraction is enabled** — deployments that don't enable it skip the 4 pods entirely.
- **`extract-agent` replica count** — runs multiple times per document per schema; the dominant throughput / cost lever when extraction is heavy.
- **Schema complexity** — schemas with many categories or many sequential dependencies produce more agent invocations per document; the YAML is the source of this cost shape.

Deployment-level cost framing is owned by `groundx-on-prem`.

## 10. What this topic does not cover

- **Authoring the extraction YAML** (schema design, field-by-field encoding, ground-truth comparison, debugging a field that extracts wrong): `groundx-extraction-workflows`.
- **The X-Ray that extraction consumes**: `agentic-pipeline.md` § 5 + `store.md` § 5.1.
- **The agentic pipeline** that produces the X-Ray: `agentic-pipeline.md`.
- **The end-to-end ingest flow** including extraction as an optional branch: `data-flow.md` § 5.1.
- **The extraction output retrieval API** (endpoint paths, request/response shapes): `groundx-api`.
- **UI patterns that consume extraction output**: implementation guidance from the relevant UI harness or application docs.
