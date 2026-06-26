# AI / ML Lifecycle

The AI/ML lifecycle in GroundX covers two fine-tuned models: the **vision model** (`layout-inference`, per `vision-model.md`) and the **re-ranker** (`ranker-inference`, per `hybrid-search.md`). Both are produced by an out-of-cluster training pipeline (the `ml-models-training` repo), distributed as versioned S3 blobs, and pulled at pod startup. A Label-Studio-fronted annotation queue captures every file that flows through GroundX for use as future fine-tuning data — that's how the models continuously improve. This file documents the lifecycle as background context for understanding GroundX; the field-level training pipeline lives outside this skill.

## 1. Marketing altitude

Model-lifecycle stays out of marketing content. The accuracy-improving-over-time story is owned by `master-brand-gtm` / `product-brand-gtm`; the engineering substrate behind it lives here.

## 2. Product altitude

GroundX's accuracy improves over time because **documents from customers who have opted in are queued for human annotation** in a Label-Studio-based pipeline. Annotators correct the vision model's output where it's wrong; the corrected annotations feed the next round of fine-tuning. The opt-in is governed by the GroundX Terms of Service — annotation is not default-on. New model versions ship to all deployments via a config-controlled S3-blob distribution; existing documents stay on whatever version processed them.

There is **no customer-facing model selection** — model versions are not exposed in the API. Customers cannot opt into a specific version or A/B-test versions themselves. The model version a customer's documents get is the cluster default at ingest time.

## 3. Conceptual / algorithmic altitude

Three architectural ideas shape the AI/ML lifecycle:

**Models are versioned S3 blobs, not container images.** The vision-model and re-ranker weights are distributed through file storage with explicit version names. A `config.py` in the inference pod identifies the current target version. On every inference request the pod checks the local copy against the target; if missing or stale, it pulls from S3 before serving. This means a model upgrade is a config change + an S3 upload — not a container image rebuild. (Bundling the model into the container is supported but not the default.)

**Continuous-learning annotation is opt-in per customer.** Customers must opt in (governed by Terms of Service) for their documents to enter the annotation pipeline. For opted-in customers, a microservice in front of Label Studio consumes the annotation queue, creates per-bucket Label Studio projects, pre-loads each document with the current vision model's annotations, and waits for a human to correct them. The corrected annotations become the next round's fine-tuning data. This is a **background path** — it doesn't block ingest; the document proceeds through the pipeline while the annotation work happens out-of-band. Historically only opted-in customers have flowed through this pipeline.

**Optional pause-for-manual-annotation flow exists for high-priority cases.** A separate flow lets a caller pause processing at the layout entry point so a human can annotate the document exactly before the vision model runs. The flow is controlled by an ingest-request-body parameter that **exists in the API but is not documented in the customer-facing SDKs or REST surface** today (it's exposed through EyeLevel SSP). In this flow, manual annotations replace `layout-inference` output — the document continues through the layout pipeline with `layout-inference` skipped, using the human annotations instead. Re-entry happens at `pre-process → layout-api`. A script can also export the annotations back to GroundX for processing.

**Eval is done against a held-out test set, not live traffic.** No live-traffic A/B testing of model versions happens. The fine-tuning dataset is split ~90/10 (train/test) with an exception list that pins certain files to one side or the other; the test set is the pre-release evaluation surface. Customer-facing eval tooling — how-to guides, sample code, and per-bucket Chat + SEARCH buttons in the GroundX Dashboard — is separate from this internal eval and lets customers evaluate retrieval quality against their own corpus.

## 4. System altitude

```
groundx ingest (opted-in customer) → document enters Label Studio queue (microservice in front of Label Studio)
              ├── default flow: document continues through pipeline; annotation work runs out-of-band
              └── pause-for-annotation flow (ingest-request-body parameter, undocumented in customer SDKs / REST):
                  document pauses at pre-process → layout-api; manual annotations replace layout-inference;
                  processing resumes through layout pods with layout-inference skipped

ml-models-training repo → eval against held-out test set → S3 (versioned blob)
                                                              ↓
                                                       config.py target version
                                                              ↓
                                              layout-inference / ranker-inference pod
                                                              ↓
                                              check local copy → pull from S3 if missing/stale
                                                              ↓
                                                       serve inference request
```

The training pipeline (`ml-models-training`) and the annotation pipeline (Label Studio + microservice) are **separate from the GroundX production cluster** — they're support infrastructure for the lifecycle, not part of ingest / search / extraction.

## 5. Implementation altitude

### 5.1 Model distribution

| Component | Mechanism |
| --- | --- |
| Model storage | S3, versioned by name |
| Target version | `config.py` in each inference pod (`layout-inference`, `ranker-inference`) |
| Distribution at startup | Pod init checks shared disk space for the target version; pulls from S3 if missing |
| Distribution at runtime | On every inference request, the pod re-checks local vs target; pulls if updated |
| Concurrent-download handling | Not explicitly hardened today — if multiple pods discover a new version simultaneously, all may attempt the download in parallel. **Potential performance enhancement.** |
| Container bundling | Supported but not the default; default containers expect the S3 + shared-disk pattern |

### 5.2 Annotation pipeline (continuous learning)

Two flows feed annotation. **Both require customer opt-in** (per the GroundX Terms of Service); documents from non-opted-in customers do not enter the annotation pipeline.

*Source: opt-in posture and the pause-for-annotation parameter — scoped internal-review finding, 2026-05-17. Verify with the cloud-service operational owner before external claim. The `ml-models-training` repo is the upstream source for the pipeline structure.*

**Default flow (background path):**

1. Documents from opted-in customers are queued for annotation at ingest.
2. A microservice in front of Label Studio consumes the queue, creates per-bucket Label Studio projects, and pre-loads each document with the current vision model's output.
3. Humans correct annotations in Label Studio as needed.
4. Corrected annotations become fine-tuning data for the next training round.
5. **This does not impact document processing** — the document proceeds through the GroundX pipeline normally. The annotation work runs out-of-band.

**Pause-for-annotation flow:**

1. Caller sets the ingest-request-body parameter that activates the pause flow.
2. Document enters Label Studio at the same queue entry point, but processing **pauses** at `pre-process → layout-api`.
3. Annotators correct the document in Label Studio.
4. Corrected annotations are pushed back to GroundX (or exported via a manual re-export script).
5. Document resumes processing — re-enters at `pre-process → layout-api`, then proceeds through the layout pods with `layout-inference` skipped (manual annotations are used in place of inference output).

The pause-for-annotation parameter exists in the ingest-request body but is **not documented in the customer-facing SDKs or REST surface** today. It is exposed through EyeLevel SSP. The mechanism is fully implemented; the surfacing decision is what's missing.

### 5.3 Training pipeline

Lives in the **`ml-models-training`** repo, separate from the harness. The pipeline is Label-Studio-driven (the same Label Studio instance that fronts the annotation queue). Fine-tuning uses the human-corrected annotations as ground truth. Training output is a new versioned model blob uploaded to S3.

### 5.4 Eval methodology

| Surface | What it covers | Where |
| --- | --- | --- |
| Pre-release eval (internal) | Fine-tuning train/test split, ~90/10, random with exception list pinning certain documents to train or test | `ml-models-training` repo |
| Customer-facing eval (how-to + sample code) | Documentation + code samples teaching customers how to evaluate retrieval against their own corpus | `groundx-api` skill (sample projects) |
| Customer-facing eval (interactive) | Per-bucket Chat + SEARCH buttons in the GroundX Dashboard for superficial bucket-level inspection (Chat opens chat-with-files; SEARCH shows API retrievals) | the private GroundX Dashboard frontend reference |

No live-traffic A/B testing of model versions exists. All comparison work is against the held-out test set pre-release.

### 5.5 Rollout

A model upgrade is:

1. New version trained → uploaded to S3 with a new version name.
2. `config.py` in the inference pods updated to point at the new version.
3. Pods pick up the new version on the next inference request (per § 5.1).

Customers don't pin to specific versions — the cluster runs whatever the current `config.py` target is. Existing customer documents stay on whatever version processed them at ingest time; new documents get the new version.

### 5.6 No per-document version tracking — known gap

**GroundX does not currently track which model version processed which document.** When a deployment upgrades, existing documents retain their (old-model) outputs but the system has no record of which version they came from. This is a known gap — meaningful for reproducibility, drift analysis, and selective re-processing.

## 6. Security / compliance altitude

**Training-data path is opt-in and crosses an internal trust boundary for opted-in customers.** Documents from customers who have opted in (per Terms of Service) move from GroundX to Label Studio, where human annotators see and correct them. This is an internal-to-deployment path in the cloud service; for on-prem deployments wanting the same continuous-learning pattern, the Label Studio instance would need to live inside the same trust enclosure. **The annotation pipeline does not run for customers who have not opted in** — their documents do not enter the annotation queue at all. The opt-in mechanism is governed by the Terms of Service, not architectural code; historically only opted-in customers have flowed through this pipeline.

For the trust-boundary inventory and the no-3rd-party-LLM-on-search invariant see `identity-and-trust.md` § 6.2.

## 7. Operations / SRE altitude

The inference pods are responsible for their own model bootstrap (check local, pull from S3 on miss/stale). Concurrent-download contention is not specifically hardened today; multiple pods discovering a new version simultaneously may all attempt the download. For the broader observability framing see `observability.md`. For the metrics pod and per-inference-pod TPM signals see `overview.md` § 4.7.

## 8. Data architecture altitude

**Training data** flows from the annotation queue into Label Studio into the `ml-models-training` repo's processing. Production models live in S3 with explicit version names. The GroundX production cluster does not store training data, eval data, or training outputs — those are all in the training-pipeline ecosystem.

**Per-document model version is not currently tracked** (per § 5.6). Document records (per `groundx-api/references/02-documents.md`) do not carry a model-version field; X-Ray output (per `agentic-pipeline.md` § 5) does not include the vision model version. The architectural implication: re-ingest of an existing document is the only way to get its output from a different model version, and there's no automated detection of "this document is on an old version, re-process it."

## 9. Cost / FinOps altitude

Training infrastructure cost is separate from production. Training runs on its own compute (in the `ml-models-training` ecosystem, not the GroundX production cluster) and doesn't impact production GPU spend. The dominant production GPU costs (per `data-flow.md` § 9) — `summary-inference`, `ranker-inference`, `layout-inference` — are independent of the training pipeline.

The annotation pipeline (Label Studio + the microservice + human annotator time) is a separate operational cost. Architecturally, it's a continuous-investment story; the cost is the long-term accuracy improvement.

Deployment-level cost framing is owned by `groundx-on-prem`.

## 10. What this topic does not cover

- **The fine-tuned vision model itself** (what it detects, training data scale): `vision-model.md`.
- **The fine-tuned re-ranker model itself** (what it scores, why it can't be replaced by a 3rd-party): `hybrid-search.md`.
- **The exact training pipeline implementation** (Label Studio project structure, annotation schema, fine-tuning hyperparameters, train/test split mechanics): `ml-models-training` repo (out of scope for this skill).
- **The customer-facing eval tooling** (how-to guides, sample code, chat / SEARCH buttons): `groundx-api` (samples) + the private GroundX Dashboard frontend reference (Dashboard widgets).
- **The opt-in API parameter for pause-for-annotation**: implementation lives in EyeLevel SSP today; documented at the architectural altitude here, not at the API-call altitude.
- **Compliance posture for training-data handling**: `data-residency.md`.
- **Concurrent-download hardening for the model-pull-on-miss pattern**: known gap; `observability.md` may pick it up as a future fitness-gate target.
