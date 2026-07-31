# Objections

Common objections, the reframe that opens the conversation back up, and the proof anchor that closes it. Structure each entry as **Objection → Reframe → Proof**.

For the differentiator pillars these anchors live in, see `differentiation.md`. For the proof citations, see `proof-points.md`.

## 0. Diagnose before answering

A broad alternative such as "we will use a general-purpose model directly" is
not enough evidence for one hardcoded rebuttal. Select one or two lenses closest
to the buyer's stated signal:

| Buyer signal | Lead lens | Card |
| --- | --- | --- |
| No signal beyond direct-model sufficiency | Concede possible fit; ask one useful question | § 1.1 |
| Simple text, small corpus, current quality bar met | Honest no-current-fit | § 1.4 |
| Tables, decision trees, layouts, or observed document failures | Document comprehension | § 1.1 |
| Large corpus, document selection, retrieval, grounding, or search failure | Retrieval | § 4.1 |
| Stated residency, sensitivity, or customer-controlled deployment | Deployment control | § 2.1 |
| Stated internal-build plan | Full-system scope and collaboration | §§ 1.2–1.3 |
| Stated model-usage or processing-cost pain | Focused processing and model choice | § 3.1 |
| Two or more explicit signals | The one or two closest lenses | The corresponding cards only |

Read this file first. Then load only the selected mechanism, deployment, buyer,
or differentiation owner. Load `proof-points.md` only when the answer will
actually use customer, benchmark, partner, or quantitative evidence. No-signal
and confirmed-simple-fit answers do not preload proof.

Return only the objection response. Do not append a next step, meeting request,
demo offer, or offer to add more unless the user asks for one.

Hard stop: when the response would mention on-premises, air-gapped operation,
customer-controlled deployment, residency, egress, or a data boundary, invoke
the installed plugin's `groundx-on-prem` skill before drafting. Reading this
objection card is not a substitute for that skill invocation.

## 1. Capability and accuracy

### 1.1 "We'll just use OpenAI / Claude / Gemini directly."

- **Use when:** start here for the broad objection. Use the comprehension lens
  only when the buyer names visual structure or an observed document failure.
- **Lead:** Direct model use can be enough for simple documents and small
  corpora. GroundX becomes relevant when visual document structure, corpus
  retrieval, deployment control, repeatability, or operating scale creates a
  problem.
- **Ask or verify:** "Where does the current approach break: understanding a
  page, finding the right document, deployment control, repeatability, or
  model usage?"
- **Required owner:** before stating the visual-comprehension mechanism, read
  `technical-architecture.md` §§ 2–3. Load eligible proof only if it will be cited.
- **If deflected:** follow the new explicit signal. If the buyer says page
  answers are good but file selection is hard, move to retrieval (§ 4.1).
- **Avoid:** assuming every document is visually complex, reciting every
  differentiator, claiming a model vendor trains on or leaks the buyer's
  documents, or volunteering proof before fit is known.

When the buyer supplies no failure signal, keep the answer to two sentences:
concede that direct model use can fit simple documents or a small corpus, then
ask where the current approach breaks across page understanding, retrieval,
deployment control, repeatability, or model usage. Do not predict that the
buyer's approach will break or describe a failure they have not reported.

### 1.2 "We can build this ourselves."

- **Use when:** the buyer states an internal-build plan.
- **Lead:** The buyer can build it. The real comparison includes document
  reading, search quality, testing, deployment, and ongoing support. In spoken
  copy, follow with: "Which parts does your team want to build and maintain?"
- **Ask or verify:** "Which parts does the team plan to own, and where would a
  proven component accelerate the roadmap?"
- **Support:** `technical-architecture.md`, `buyer.md` §§ 1–2, and
  `differentiation.md` §§ 4–5. Use the exact heritage language from
  `narrative.md` only when relevant.
- **If deflected:** if the team already covers the full scope, ask where
  backlog or document complexity remains rather than predicting failure.
- **Avoid:** "probably, eventually," staffing guesses, build-duration promises,
  challenging competence, or changing "helped lead Watson's strategy and
  formation" into "built Watson."

### 1.3 "Our internal AI team is already building this."

- **Use when:** an internal AI program already exists.
- **Lead:** Start by asking what the internal program is intended to deliver,
  where it is working, and where capacity or document complexity creates a gap.
  Do not assume the program exists to protect jobs or justify headcount. Two
  responses, by decision ownership:
  - If the buyer is the LOB owner whose outcomes the internal team is supposed to deliver: ask whether the internal program is hitting the business metrics that matter. If not, the conversation pivots to outcomes the internal program is not yet delivering, and GroundX (or the Operational Layer for outcome-buyers, `product.md` § 9) becomes the path to those outcomes.
  - If the buyer is IT or engineering: do not argue the internal program is
    wasted. Explain how the Harness can shorten implementation work and help
    the team handle more use cases. Apply job-security framing
    only if the buyer explicitly supplies that signal (`buyer.md` § 1).
- **Ask or verify:** "Which outcomes is the program accountable for, and where
  is the current backlog or quality gap?"
- **Support:** `buyer.md` § 2 and `differentiation.md` § 5.
- **If deflected:** if there is no gap, do not manufacture one. If the signal is
  backlog, explain how GroundX can shorten the work.
- **Avoid:** assuming job protection, bypassing the technical owner, or saying
  the internal program is wasted.

### 1.4 "Our documents aren't that complex; basic RAG works fine."

- **Use when:** the buyer says the current simple-document path works.
- **Lead:** If the current approach works, keep it. Ask whether the same quality
  holds as the number and variety of documents grow.
- **Ask or verify:** "Does the current quality bar hold as the corpus and format
  diversity grow?"
- **Support:** stop without proof when the simple fit is confirmed. If the buyer
  supplies retrieval or scale pain, use § 4.1 and eligible proof.
- **If deflected:** keep the honest no-current-fit answer and offer a future
  trigger, not a manufactured present problem.
- **Avoid:** attaching unrelated customer stories or claiming hidden failure
  without evidence.

## 2. Deployment and security

### 2.1 "We can't send our data to a vendor."

- **Use when:** the buyer explicitly requires residency, sensitivity, or
  customer-controlled deployment.
- **Lead:** GroundX supports deployment in customer-controlled environments.
  For buyer and
  trust conversations, lead with on-prem, private-cloud, residency-control, or
  supported air-gapped operation. Route platform engineers to
  `groundx-on-prem` for current Kubernetes, Helm, and runtime requirements.
- **Ask or verify:** "Which deployment mode and data boundary does the security
  team require?"
- **Support:** load `groundx-on-prem`; retrieve eligible third-party validation
  only if it will be used.
- **If deflected:** if data control is not the problem, return to the buyer's
  stated comprehension, retrieval, build, or cost signal.
- **Avoid:** unconditional "your data never leaves," unsupported vendor-risk
  claims, or implying every deployment mode has the same boundary. Never say
  data or documents "never have to leave." Say GroundX supports
  customer-controlled deployment, then preserve the exact configuration and
  optional-external-service qualifiers from `groundx-on-prem`.

### 2.2 "We need full data sovereignty."

- **Reframe:** GroundX supports air-gapped or private deployment without an
  external runtime dependency. For technical readers, name the Helm deployment,
  optional AWS Terraform path, and supported backing-service choices.
- **Proof:** Helm chart README documents air-gapped operation explicitly.

### 2.3 "Our security team won't allow another vendor."

- **Reframe:** The on-prem deployment runs in customer-controlled
  infrastructure, while the hosted version is a separate option. Use current
  deployment facts from `groundx-on-prem`.
- **Proof:** Retrieve eligible partner validation from `proof-points.md`; do not
  assert a current partner status from this objection.

## 3. Cost and operational

### 3.1 "This is expensive vs free open-source tools."

- **Use when:** the buyer explicitly raises model usage, processing cost, or the
  operating scope of a stitched stack.
- **Lead:** Open source can remove license cost. The buyer still owns document
  reading, search quality, testing, deployment, and support. Compare those
  costs too.
- **Ask or verify:** "Is the cost pressure model usage, manual review, vendor
  integration, or ongoing operations?"
- **Required owner:** before stating the focused-processing mechanism, read
  `technical-architecture.md` § 3. Load a business-outcome proof only when it is
  eligible and directly relevant.
- **If deflected:** follow the named cost driver; do not substitute a different
  objection.
- **Avoid:** saying free tools inevitably become expensive, promising payback,
  quoting price, or claiming total cost stops scaling.

When the buyer says acceptable answers are becoming expensive because the same
documents are processed repeatedly, answer that signal directly. Before
drafting, read `technical-architecture.md` §§ 3–4 for the current ingest and
query-time mechanism. Do not draft from this card alone; it intentionally does
not restate the mechanism. Ask whether the integration is re-ingesting unchanged
documents. Do not turn ingest into a one-time-only claim, diagnose the buyer's
implementation without evidence, describe re-ingestion as likely or usual, or
promise savings.

### 3.2 "We have a large use-case backlog — how do we afford the integration cost?"

- **Reframe:** This is the implementation-scale pain. GroundX Agent Harness
  supplies public portable GroundX knowledge and workflows to compatible
  agents. When private Studio production or operations are actually in scope,
  GroundX Studio Harness adds the expanded internal capability set. Keep MCP
  execution and host-client capabilities separately attributed.
- **Proof:** See `differentiation.md` § 5 and `buyer.md` § 1. The Harness is the operational answer for GroundX-touching use cases.

## 4. Architecture and technical

### 4.1 "Why not just use a vector database?"

- **Use when:** the buyer has a large corpus, cannot reliably select the right
  document, or reports search, grounding, or retrieval failures. Do not use this
  merely because a vector database appears in the architecture.
- **Lead:** Uploading one known PDF hides the retrieval problem because the user
  has already selected the document. At corpus scale, GroundX combines weighted
  relevance over rich document metadata with semantic scoring so the model
  receives the right evidence, not merely similar text.
- **Ask or verify:** "How is the current system choosing which documents and
  sections reach the model when the answer could be anywhere in the corpus?"
- **Support:** use `technical-architecture.md` § 4 for the mechanism. Load the
  eligible retrieval proof from `proof-points.md` only when the response will
  cite it.
- **If deflected:** if the buyer says retrieval already meets its quality bar,
  follow the next explicit signal or keep the honest fit answer. If the buyer
  says it will add a vector database, compare the required ingest metadata,
  ranking, grounding, and evaluation scope rather than dismissing that plan.
- **Avoid:** treating a small hand-selected pilot as corpus-scale evidence,
  claiming every vector database fails, saying hybrid search alone is the moat,
  or attaching an unrelated accuracy story.

### 4.2 "Why OpenSearch and not [vector DB X]?"

- **Reframe:** GroundX chunks include document summaries, section keywords,
  chunk keywords, and three versions of the text. Weighted text search narrows
  the candidates before semantic scoring. Each step has a clear job.
- **Proof:** Architecture explanation in `technical-architecture.md` § 4. Head-to-head testing in `proof-points.md` § 1.4.

### 4.3 "Are you locked to a specific LLM vendor?"

- **Reframe:** No. GroundX is model-agnostic. Its pipeline can use smaller,
  focused models for specific tasks. The buyer can choose the foundation model
  that consumes the result.
- **Proof:** `technical-architecture.md` § 3 (agentic pipeline) and the on-prem deployment optionality.

## 5. Brand and category

### 5.1 "Is this EyeLevel or Valantor? Which company am I buying from?"

- **Reframe:** Valantor is the company. GroundX is the platform. External copy
  says *GroundX by Valantor*. EyeLevel is the technology heritage behind
  GroundX. See `brand-relationship.md` for the full hierarchy.
- **Proof:** Valantor brand architecture document.

### 5.2 "Why should I trust a 2019 company?"

- **Reframe:** The team's experience predates the company. It includes IBM
  Research, work on IBM Watson's strategy and formation, and consumer AI at The
  Weather Company. Use exact history from `narrative.md`.
- **Proof:** `narrative.md` § 4.

## 6. Discovery and timing

### 6.1 "We're not ready yet; we're still exploring."

- **Reframe:** That is fine. Start with an MNDA, representative documents, and
  the intended use. Then scope a live demo and decide whether a deeper working
  session is useful. See `sales-motion.md`.
- **Proof:** The sales process.

### 6.2 "We need to see it work on our documents."

- **Reframe:** Share representative documents under an MNDA. We will run a live
  demo on them so the buyer can judge the result directly. See
  `sales-motion.md`.
- **Proof:** Select the current eligible real-document engagement claim from
  `proof-points.md`.

## 7. What this file does not handle

- Master-brand altitude objections (Visual Intelligence category skepticism, AI+humans accountability pushback). Those defer to `master-brand-gtm/references/objections.md`.
- Pricing objections requiring a specific number. If price comes up, route to
  the sales team. Do not quote one in agent-generated content.
- Legal / contract objections. Those route to the legal and contracts owners; messaging here is product-positioning only.
