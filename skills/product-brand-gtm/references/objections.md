# Objections

Common objections, the reframe that opens the conversation back up, and the proof anchor that closes it. Structure each entry as **Objection → Reframe → Proof**.

For the differentiator pillars these anchors live in, see `differentiation.md`. For the proof citations, see `proof-points.md`.

## 1. Capability and accuracy

### 1.1 "We'll just use OpenAI / Claude / Gemini directly."

- **Reframe:** General-purpose AI fails on the documents that actually matter — visually complex policies, claims, contracts, technical diagrams, tables, decision trees. The failure rate is not a feature gap; it is structural. General-purpose models don't see document structure before they reason about it.
- **Proof:** Select the current eligible customer and benchmark claims from
  `proof-points.md` § 1; preserve their source, qualifier, and freshness rules.

### 1.2 "We can build this ourselves."

- **Reframe:** Probably — eventually. The question is the math. The team that
  built GroundX has been at this since IBM Research, helped lead Watson, did
  consumer-scale AI at the Weather Company, and spent years on this exact
  problem. The architecture combines specialized document understanding,
  focused processing, and hybrid retrieval. Compare the internal build against
  that full system, not against a single API call.
- **Read the room.** Treat the internal effort as legitimate. If the buyer
  explicitly raises displacement, job-security, control, or internal-program
  ownership concerns, acknowledge the stated concern and position GroundX as a
  force multiplier. Involve an LOB sponsor when that person owns the business
  outcome or budget; do not bypass the technical buyer based on role alone.
- **Proof:** Use the heritage arc from `narrative.md`, the mechanism from
  `technical-architecture.md`, and any current training-corpus or benchmark
  claims from `proof-points.md`.

### 1.3 "Our internal AI team is already building this."

- **Reframe.** Start by asking what the internal program is intended to deliver,
  where it is working, and where capacity or document complexity creates a gap.
  Do not assume the program exists to protect jobs or justify headcount. Two
  responses, by decision ownership:
  - If the buyer is the LOB owner whose outcomes the internal team is supposed to deliver: ask whether the internal program is hitting the business metrics that matter. If not, the conversation pivots to outcomes the internal program is not yet delivering, and GroundX (or the Operational Layer for outcome-buyers, `product.md` § 9) becomes the path to those outcomes.
  - If the buyer is IT or engineering: do not argue the internal program is
    wasted. Position the Harness as a force multiplier that makes their team
    more productive across a large use-case backlog. Apply job-security framing
    only if the buyer explicitly supplies that signal (`buyer.md` § 1).
- **Proof:** The implementation-scale pain framing in `buyer.md` § 2; the Harness positioning in `differentiation.md` § 5.

### 1.4 "Our documents aren't that complex; basic RAG works fine."

- **Reframe:** Two scenarios. If that is true and the corpus is small, you may
  not need GroundX yet. If the corpus is large or spans many document variants,
  basic RAG can fail quietly through degraded retrieval, omissions, and
  hard-to-detect edge cases.
- **Proof:** The eyelevel.ai head-to-head on vector-DB-loses-accuracy-at-scale; AskVet's data trove was unlocked only after specialized document handling.

## 2. Deployment and security

### 2.1 "We can't send our data to a vendor."

- **Reframe:** Then deploy GroundX inside your own environment. For buyer and
  trust conversations, lead with on-prem, private-cloud, residency-control, or
  supported air-gapped operation. Route platform engineers to
  `groundx-on-prem` for current Kubernetes, Helm, and runtime requirements.
- **Proof:** Retrieve eligible third-party validation from `proof-points.md` § 4.

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

- **Reframe:** Free open-source tools become expensive at scale — vendor stitching, accuracy degradation, hallucination cleanup, multiple tools to maintain. GroundX's agentic pipeline was designed around focused element-level tasks, so many steps can use smaller, easier-to-self-host models instead of sending whole documents to one frontier model. The premium pays back on accuracy that reduces manual review and on an integrated deployment that avoids a multi-vendor stitching project. Do not promise total cost stops scaling; deployment-level cost still depends on volume, storage, retained artifacts, and model choices.
- **Proof:** Select a current eligible business-outcome claim from
  `proof-points.md`; pair it with the architecture-level cost argument in
  `technical-architecture.md` § 3.

### 3.2 "We have a large use-case backlog — how do we afford the integration cost?"

- **Reframe:** This is the implementation-scale pain. GroundX Agent Harness
  supplies public portable GroundX knowledge and workflows to compatible
  agents. When private Studio production or operations are actually in scope,
  GroundX Studio Harness adds the expanded internal capability set. Keep MCP
  execution and host-client capabilities separately attributed.
- **Proof:** See `differentiation.md` § 5 and `buyer.md` § 1. The Harness is the operational answer for GroundX-touching use cases.

## 4. Architecture and technical

### 4.1 "Why not just use a vector database?"

- **Reframe:** Pure similarity matching loses relevance at scale. GroundX's hybrid search uses a weighted relevance pre-filter (OpenSearch on rich metadata chunks) plus semantic similarity scoring, then blends both. The integrated design — ingest that produces objects the search was built for — is the moat.
- **Proof:** `eyelevel.ai/post/do-vector-databases-lose-accuracy-at-scale`. Technical detail in `technical-architecture.md` § 4.

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
