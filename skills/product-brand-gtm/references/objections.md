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
- **Support:** for confirmed visual complexity, use
  `technical-architecture.md` §§ 2–3. Load eligible proof only if it will be
  cited.
- **If deflected:** follow the new explicit signal. If the buyer says page
  answers are good but file selection is hard, move to retrieval (§ 4.1).
- **Avoid:** assuming every document is visually complex, reciting every
  differentiator, claiming a model vendor trains on or leaks the buyer's
  documents, or volunteering proof before fit is known.

### 1.2 "We can build this ourselves."

- **Use when:** the buyer states an internal-build plan.
- **Lead:** Treat the build as legitimate. Compare its intended scope with the
  full document-understanding, focused-processing, retrieval, deployment, and
  operating system—not with one API call.
- **Ask or verify:** "Which parts does the team plan to own, and where would a
  proven component accelerate the roadmap?"
- **Support:** `technical-architecture.md`, `buyer.md` §§ 1–2, and
  `differentiation.md` §§ 4–5. Use the exact heritage language from
  `narrative.md` only when relevant.
- **If deflected:** if the team already covers the full scope, ask where
  backlog or document complexity remains rather than predicting failure.
- **Avoid:** "probably—eventually," staffing guesses, build-duration promises,
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
    wasted. Position the Harness as a force multiplier that makes their team
    more productive across a large use-case backlog. Apply job-security framing
    only if the buyer explicitly supplies that signal (`buyer.md` § 1).
- **Ask or verify:** "Which outcomes is the program accountable for, and where
  is the current backlog or quality gap?"
- **Support:** `buyer.md` § 2 and `differentiation.md` § 5.
- **If deflected:** if there is no gap, do not manufacture one. If the signal is
  backlog, position GroundX as a force multiplier.
- **Avoid:** assuming job protection, bypassing the technical owner, or saying
  the internal program is wasted.

### 1.4 "Our documents aren't that complex; basic RAG works fine."

- **Use when:** the buyer says the current simple-document path works.
- **Lead:** Two scenarios. If that is true and the corpus is small, you may
  not need GroundX yet. If the corpus is large or spans many document variants,
  basic RAG can fail quietly through degraded retrieval, omissions, and
  hard-to-detect edge cases.
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
  claims, or implying every deployment mode has the same boundary.

### 2.2 "We need full data sovereignty."

- **Reframe:** Same answer — air-gapped or private deployment with no external runtime dependency. When the audience is technical, name the Helm deployment, optional AWS Terraform path, and backing-service choices: AWS SQS or Kafka, S3 or MinIO, existing OpenSearch or a dedicated cluster.
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
- **Lead:** GroundX's focused processing lets the deployment choose an
  appropriate model per task instead of sending every whole document to one
  frontier model. Compare the full operating scope, not license price alone.
- **Ask or verify:** "Is the cost pressure model usage, manual review, vendor
  integration, or ongoing operations?"
- **Support:** `technical-architecture.md` § 3. Load a business-outcome proof
  only when it is eligible and directly relevant.
- **If deflected:** follow the named cost driver; do not substitute a different
  objection.
- **Avoid:** saying free tools inevitably become expensive, promising payback,
  quoting price, or claiming total cost stops scaling.

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

- **Reframe:** The chunks GroundX produces have rich attributes — document summaries, section keywords, chunk keywords, three versions of the text. A weighted text query on those attributes is a stronger pre-filter than a pure vector query. The semantic similarity step still runs on candidates — it just runs on the right candidates. The result is better than either pure approach.
- **Proof:** Architecture explanation in `technical-architecture.md` § 4. Head-to-head testing in `proof-points.md` § 1.4.

### 4.3 "Are you locked to a specific LLM vendor?"

- **Reframe:** No. GroundX is model-agnostic. The agentic pipeline uses small focused models — older, cheaper, easier to self-host — and the output is consumed by whatever foundation model the buyer chooses downstream. Route best-fit model per task.
- **Proof:** `technical-architecture.md` § 3 (agentic pipeline) and the on-prem deployment optionality.

## 5. Brand and category

### 5.1 "Is this EyeLevel or Valantor? Which company am I buying from?"

- **Reframe:** Valantor is the company. GroundX is the platform. *GroundX by Valantor* is how it reads externally. EyeLevel is the technology heritage — the team that built GroundX before Valantor acquired the work. The EyeLevel mark appears on the lockup with "A VALANTOR COMPANY" baked in. See `brand-relationship.md` for the full hierarchy.
- **Proof:** Valantor brand architecture document.

### 5.2 "Why should I trust a 2019 company?"

- **Reframe:** The team has been at this since IBM Research — helped lead the strategy and formation of IBM Watson, did consumer-scale AI at Weather Company. They left in 2019 to solve this specific problem. The company is younger than the team's expertise in this space, which is over a decade.
- **Proof:** `narrative.md` § 4.

## 6. Discovery and timing

### 6.1 "We're not ready yet — still exploring."

- **Reframe:** That is fine. The first ask is light — MNDA, share documents and intent. We can scope a live demo against your material, then use the result to guide a deeper working session. See `sales-motion.md`.
- **Proof:** The sales process.

### 6.2 "We need to see it work on our documents."

- **Reframe:** Best signal we can give. Share a clean dataset under MNDA; we can run a live demo against it. This is part of the standard process. See `sales-motion.md`.
- **Proof:** Select the current eligible real-document engagement claim from
  `proof-points.md`.

## 7. What this file does not handle

- Master-brand altitude objections (Visual Intelligence category skepticism, AI+humans accountability pushback). Those defer to `master-brand-gtm/references/objections.md`.
- Pricing objections requiring a specific number. If a price comes up in a sales conversation, route to the sales team — do not quote one in agent-generated content.
- Legal / contract objections. Those route to the legal and contracts owners; messaging here is product-positioning only.
