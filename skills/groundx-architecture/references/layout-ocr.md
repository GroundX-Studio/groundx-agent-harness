# Layout + OCR (Layout Microservice)

The layout microservice is the **document-reading tier** of GroundX — the Celery-orchestrated pipeline that takes a source file and produces a typed, structured layout for downstream agents. It pairs the fine-tuned vision model (`layout-inference`, GPU; canonical depth in `vision-model.md`) with OCR (`layout-ocr`, CPU — Tesseract default, Google Cloud Vision optional) and fuses their outputs by spatial containment. This file documents the subsystem as a whole; vision-model depth is in `vision-model.md`.

## 1. Marketing altitude

Not the canonical place — see `vision-model.md` § 1.

## 2. Product altitude

The layout microservice is the first compute stage after a document enters the pipeline. It converts a source file (typically a PDF) into a typed, structured layout — every page becomes a sequence of detected elements (tables, paragraphs, figures), each carrying its constituent words and bounding-box coordinates. This is what the agentic pipeline consumes downstream.

## 3. Conceptual / algorithmic altitude

The layout microservice is built on three architectural ideas:

**Vision and OCR are independent passes.** The fine-tuned vision model (`layout-inference`) operates on the page image and produces element types + element bounding boxes. OCR (`layout-ocr`) operates on the same page image, independently, and produces words + word bounding boxes. Neither pass consumes the other's output. Fusion happens after, in `layout-map`, by spatial containment: words whose bounding boxes fall inside an element's bounding box are merged into a typed object of that element's type. The architectural value of this separation: the vision model can focus purely on reading the document as a human would (visual structure) without OCR errors propagating into element detection; OCR can be backed by either an in-cluster or 3rd-party engine without affecting the vision model. (See `vision-model.md` § 3 for the meaning-second framing.)

**OCR is pluggable.** Tesseract is the default (in-cluster, no external dependency). Google Cloud Vision is the optional alternative (activated when a `gcv.json` GCP service account file is provided). These are the two supported backends — there are no others. Tesseract attempts to install as many language packs as it can find at deployment time; GCV's language support is inherited from the GCV service.

**The pipeline is Celery-orchestrated.** Each layout step is a Celery task. Per-page steps (layout-correct, layout-inference, layout-ocr) run in parallel across pages; per-document steps (layout-process at the start, layout-map at the end, layout-save) gate the fan-out and fan-in. `layoutWebhook` (golang) is the API-callback target that closes the loop back to `pre-process`.

## 4. System altitude

The layout microservice is entered via API from `pre-process` and exits via API callback to `layoutWebhook`:

```
pre-process → API → layout-api → Celery: layout-process → layout-correct (per-page) → [layout-inference + layout-ocr (per-page, in parallel)] → layout-map (per-document) → layout-save → API callback → layoutWebhook → (queue) → pre-process
```

`layout-api` is the entry point; all internal handoff is Celery. The intermediate artifacts (per-page images, OCR text, detection results, mapped layouts) are written to file storage as the pipeline progresses (per `store.md` § 5.1). For the full topology see `overview.md` § 4.5.

## 5. Implementation altitude

### 5.1 Pods

| Pod | Runtime | CPU/GPU | Granularity | Role |
| --- | --- | --- | --- | --- |
| `layout-api` | Python | CPU | — | Entry point from `pre-process`; spawns the Celery task chain |
| `layout-process` | Python | CPU | Per-document | Initial file manipulation (PDF→images), resolution normalization; generates per-page processing requests |
| `layout-correct` | Python | CPU | Per-page | Page rotation correction |
| `layout-inference` | Python | **GPU** (CPU fallback available; default GPU for speed — per `vision-model.md` § 5) | Per-page | The fine-tuned vision model — element detection (tables, paragraphs, figures); runs in parallel with `layout-ocr` |
| `layout-ocr` | Python | CPU | Per-page | OCR — Tesseract default, Google Cloud Vision when `gcv.json` is provided; runs in parallel with `layout-inference` |
| `layout-map` | Python | CPU | Per-document | Fuses `layout-inference` element output with `layout-ocr` word output by **spatial containment** (per `vision-model.md` § 3) |
| `layout-save` | Python | CPU | Per-document | Final save step; triggers API callback |
| `layoutWebhook` | Golang | CPU | — | API callback target; also receives extract pipeline callbacks; enqueues to `pre-process` |

### 5.2 OCR backends

| Backend | When | Notes |
| --- | --- | --- |
| **Tesseract** (default) | Always, unless GCV is configured | In-cluster; no external dependency. At install time the deployment attempts to install as many Tesseract language packs as it can find — language coverage depends on what's available at build time. |
| **Google Cloud Vision** | When a `gcv.json` GCP service account file is provided | OCR calls go to GCV's hosted API. Language coverage is whatever GCV supports. |

These are the only two supported OCR backends.

### 5.3 Fusion (the role of `layout-map`)

The `layout-map` pod is what makes the independent-passes architecture work. After per-page parallel work completes, `layout-map` runs per-document and combines the per-page results: for every element box from `layout-inference`, the OCR words from `layout-ocr` whose bounding boxes fall inside that element box are merged into a typed object (table / paragraph / figure) carrying its constituent words. The output is a unified document-level layout — the input to the agentic pipeline.

## 6. Security / compliance altitude

The layout microservice is **in-cluster** in the default (Tesseract) configuration. When `gcv.json` is configured, OCR calls cross the trust boundary to Google Cloud Vision — document page images leave the deployment on each OCR call. This is the only external trust-boundary crossing in the layout microservice. For the full identity / trust model see `identity-and-trust.md`.

## 7. Operations / SRE altitude

`layout-api` and `layoutWebhook` are metered as **API response time** thresholds in the `metrics` pod; the layout sub-pods are metered as **Celery task back-pressure** thresholds; `layout-inference` is additionally metered as **inference-class** TPM (per `overview.md` § 4.7). The per-page parallelism means HPA scaling on layout sub-pods is the dominant lever for layout throughput at high ingest volume. For the broader observability framing see `observability.md`.

## 8. Data architecture altitude

**Inputs:** source file (from file storage; written there by `upload` for URL-shared ingest or by `groundx` for binary uploads).

**Intermediate artifacts** (all written to file storage during processing):

- Per-page rendered images (from `layout-process`).
- Per-page rotation-corrected images (from `layout-correct`).
- Per-page element detection results (from `layout-inference`).
- Per-page OCR text + word bounding boxes (from `layout-ocr`).
- Per-document mapped layout (from `layout-map`).

**Output:** the document-level mapped layout — the input to the agentic pipeline. For canonical artifact placement see `store.md` § 5.1.

## 9. Cost / FinOps altitude

`layout-inference` is the **third-largest GPU cost driver** in default deployments (after `summary-inference` and `ranker-inference` — per `data-flow.md` § 9). The CPU layout pods are cheap by comparison; their cost lever is replica count under HPA for ingest throughput. The OCR backend choice has a cost shape difference: Tesseract is in-cluster (CPU only; no per-call cost beyond replica count); Google Cloud Vision is per-call billing against the GCV API. Deployment-level cost framing is owned by `groundx-on-prem`.

## 10. What this topic does not cover

- **The fine-tuned vision model itself** (what it detects, what it's trained on, the meaning-second framing): `vision-model.md`.
- **The agentic pipeline** that consumes the mapped layout: `agentic-pipeline.md`.
- **The end-to-end document journey through the pipeline**: `data-flow.md` § 5.1.
- **The X-Ray and JSONL chunks** produced downstream: `agentic-pipeline.md` § 8 + `store.md` § 8.
- **Per-deployment Tesseract language-pack selection and `gcv.json` provisioning**: `groundx-on-prem`.
- **The `extraction-architecture.md` callback path** through `layoutWebhook`: `extraction-architecture.md`.
