# Vision Model

GroundX's fine-tuned vision model is a GPU-served, per-page **element-detection** model trained on 1M+ pages of enterprise documents. It identifies the visual elements on a page — **tables**, **paragraphs**, and **figures** — and outputs each as a type plus a bounding box. It is the structural reason GroundX is accurate: by detecting the page's elements before any LLM reasoning happens, downstream agents work on small focused pieces rather than entire pages or documents.

In implementation, it is the **`layout-inference`** pod inside the layout pipeline cluster. This file describes the model's responsibility and place in the pipeline; for the full layout pipeline progression see `overview.md` § 4.5 and `layout-ocr.md`.

## 1. Marketing altitude

GroundX reads enterprise documents the way a human does — visual layout first, then meaning. A **fine-tuned vision model trained on 1M+ pages of enterprise documents** identifies tables, paragraphs, and figures on every page *before* any LLM reasoning happens. That's the structural reason GroundX is accurate on the visually complex documents that defeat general-purpose AI.

## 2. Product altitude

The vision model identifies **elements** on a page — typed regions (table / paragraph / figure) with bounding boxes. It runs per-page, in parallel with an OCR pass that extracts words. The two outputs are fused in `layout-map`: words whose bounding boxes fall inside an element's box are merged into a typed object representing that element. Downstream agents then work on those typed elements — not on raw pages — which is what makes per-element reasoning accurate and tractable.

## 3. Conceptual / algorithmic altitude

Element-level detection before LLM reasoning is what makes GroundX's accuracy structurally different from page-level or document-level approaches. Two architectural properties follow.

**First, vision and meaning are separate passes.** The vision model operates **purely on the page image** — it does not consume OCR text. OCR runs concurrently as an independent pass (`layout-ocr`). The two outputs are joined later by spatial containment in `layout-map`, where words inside an element's bounding box become that element's content. Each pass has a narrow, specific responsibility: the vision model identifies *what kind of region this is* and where it is; OCR identifies *what words exist on the page* and where they are. Neither alone is sufficient — both are necessary to produce a typed, content-bearing element. The spatial-containment join is the mechanism that combines them.

**Second, element-level processing enables cognitive-load reduction downstream.** Because the document is split into typed elements before reasoning starts, each downstream agent in the agentic pipeline works on a single focused element rather than a whole page or document. Smaller, cheaper LLMs with smaller context windows can serve those agents reliably — the documents-per-element-per-agent structure is what makes that work. The cost-reduction benefit applies to the **agents downstream** of the vision model, not to the vision model itself; the vision model is a purpose-built fine-tuned model, not an LLM, so the cheaper-LLM substitution isn't applicable to it.

## 4. System altitude

The vision model runs as the **`layout-inference`** GPU service inside the layout pipeline cluster. The pipeline progression:

```
layout-api → layout-process → layout-correct → [layout-inference + layout-ocr] → layout-map → layout-save → layoutWebhook
```

`layout-inference` is **not** API-callable from outside the layout pipeline — it's a Celery worker dispatched by the layout pipeline. The initial entry into the pipeline is the API call from `pre-process` to `layout-api`. Within the pipeline:

- `layout-process` (per-document) does PDF→images and **resolution normalization**, then dispatches per-page work.
- `layout-correct` (per-page) does **page rotation correction**.
- `layout-inference` (per-page, **GPU**) runs the vision model: element detection only.
- `layout-ocr` (per-page) runs in parallel: word + word-bounding-box extraction.
- `layout-map` (per-document) fuses both passes by spatial containment.

For the rest of the layout pipeline see `overview.md` § 4.5 and `layout-ocr.md`.

## 5. Implementation altitude

| Aspect | Value |
| --- | --- |
| Pod name | `layout-inference` |
| Runtime | Python |
| CPU/GPU | Default GPU (`gpuLayout` node selector); **can run on CPU** — GPU is for speed, not a strict requirement |
| Granularity | Per-page (concurrent across pages via Celery) |
| Position in the layout pipeline | After `layout-correct`; concurrent with `layout-ocr`; results join at `layout-map` |
| Input | Rotation-corrected page image |
| Output | List of `(element type, bounding box)` pairs per page. Element types: `table`, `paragraph`, `figure`. |
| Training | Fine-tuned on 1M+ pages of enterprise documents |

The vision model is named externally as **"a fine-tuned vision model trained on 1M+ pages of enterprise documents"** — the underlying model architecture name is internal-only and is not used in external content.

## 6. Security / compliance altitude

The vision model processes document pages — customer data passes through. For the full identity / trust model and data-residency implications see `identity-and-trust.md` and `data-residency.md`. The vision model itself does not retain document content beyond its in-flight inference call.

## 7. Operations / SRE altitude

`layout-inference` is metered as an **inference-class** metric in the `metrics` pod (per `overview.md` § 4.7) — tokens-per-minute against the configured threshold drives the pod's HPA. As a GPU pod, scale-to-zero matters: when there's no layout load, `layout-inference` can ramp down to free GPU capacity. For the broader observability framing see `observability.md`.

## 8. Data architecture altitude

**Input:** page images written to file storage by `layout-process`. **Output:** per-page element lists that `layout-map` consumes alongside `layout-ocr`'s word lists. The fused document-level layout is what gets handed downstream to the agentic enrichment pipeline. For the file-storage backing services (MinIO / S3 / etc.) see `overview.md` § 4.4 and `store.md`.

## 9. Cost / FinOps altitude

`layout-inference` is the **third-largest GPU cost driver** in default deployments — behind `summary-inference` and `ranker-inference`. Unlike those two (fine-tuned LLM-class inference services with no practical CPU fallback), `layout-inference` **can run on CPU** — GPU is the default for speed, not a hard requirement. In cost-constrained or GPU-constrained deployments, `layout-inference` is a candidate for CPU fallback at the cost of throughput. The element-level cost-reduction story (smaller-context-window LLMs for downstream agents — per `agentic-pipeline.md` when authored) is separate from the vision model's own deployment posture. Deployment-level cost framing is owned by `groundx-on-prem`.

## 10. What this topic does not cover

- **The OCR pass** that runs concurrently with the vision model: `layout-ocr.md`.
- **Page rotation correction and resolution normalization**: handled by `layout-correct` and `layout-process` respectively, inside the layout pipeline cluster. See `overview.md` § 4.5.
- **The spatial-containment fusion algorithm** in `layout-map`: noted at the System altitude here; for depth see `layout-ocr.md` or the layout pipeline section of `overview.md` § 4.5.
- **What downstream agents do with the element output**: `agentic-pipeline.md`.
- **Hybrid search and the re-ranker** that operate on the eventual indexed chunks: `hybrid-search.md`.
- **The end-to-end document journey** through the pipeline: `data-flow.md`.
- **The underlying vision-model architecture name**: not used in external content; not named in this skill.
