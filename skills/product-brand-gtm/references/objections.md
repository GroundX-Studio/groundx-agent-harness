# Objections

Common objections, the reframe that opens the conversation back up, and the proof anchor that closes it. Structure each entry as **Objection → Reframe → Proof**.

For the differentiator pillars these anchors live in, see `differentiation.md`. For the proof citations, see `proof-points.md`.

## 1. Capability and accuracy

### 1.1 "We'll just use OpenAI / Claude / Gemini directly."

- **Reframe:** General-purpose AI fails on the documents that actually matter — visually complex policies, claims, contracts, technical diagrams, tables, decision trees. The failure rate is not a feature gap; it is structural. General-purpose models don't see document structure before they reason about it.
- **Proof:** Air France/KLM's policy documents broke every general-purpose AI they tested before GroundX produced 96.2% accuracy against a 60% target. DocBench superhuman performance against general models. See `proof-points.md` § 1.

### 1.2 "We can build this ourselves."

- **Reframe:** Probably — eventually. The question is the math. The team that built GroundX has been at this since IBM Research, helped lead Watson, did consumer-scale AI at Weather Company, and spent years before the AI craze on this exact problem. The vision model is fine-tuned on 1 million+ pages of enterprise documents. The hybrid search architecture is the product of years of iteration. A six-engineer in-house project is not going to match that in twelve months.
- **Read the room.** This objection often arrives loaded — when it comes from an IT or engineering audience facing the AI existential crisis (see `buyer.md` § 1), it is sometimes *"we are already building this defensively to keep our team relevant."* In that frame, the pure math argument lands as a threat. The right move is often to acknowledge the internal effort, position GroundX as a force-multiplier that lets their team take on more ambitious work, and route the conversation toward an LOB champion who can speak to business outcomes the internal program is not yet delivering.
- **Proof:** The heritage arc (see `narrative.md` § 4); the 1M+ pages training corpus; the head-to-head benchmarks against popular RAG tools.

### 1.3 "Our internal AI team is already building this."

- **Reframe.** Many enterprises are running internal AI projects right now whose primary function is to keep the technical team relevant (see `buyer.md` § 1). Two responses, by audience:
  - If the buyer is the LOB owner whose outcomes the internal team is supposed to deliver: ask whether the internal program is hitting the business metrics that matter. If not, the conversation pivots to outcomes the internal program is not yet delivering, and GroundX (or the Operational Layer for outcome-buyers, `product.md` § 9) becomes the path to those outcomes.
  - If the buyer is IT or engineering themselves: do not argue the internal program is wasted. Position the Harness as a force-multiplier that makes their team more productive across the 500-use-case backlog, not as a replacement. Cite the implementation-scale pain (`buyer.md` § 2).
- **Proof:** The implementation-scale pain framing in `buyer.md` § 2; the Harness positioning in `differentiation.md` § 5.

### 1.4 "Our documents aren't that complex; basic RAG works fine."

- **Reframe:** Two scenarios. If that is true and scale is small, you may not need GroundX yet — buy it when the complexity or volume crosses the line. If you think it is true but scale is high (1000s of pages, 100s of document variants), basic RAG breaks quietly — accuracy degrades, hallucinations creep into corners, and the failure mode is hard to detect until a customer or a regulator finds it.
- **Proof:** The eyelevel.ai head-to-head on vector-DB-loses-accuracy-at-scale; AskVet's data trove was unlocked only after specialized document handling.

## 2. Deployment and security

### 2.1 "We can't send our data to a vendor."

- **Reframe:** Then deploy on-prem. GroundX runs on Kubernetes via Helm charts with no external dependencies — fully air-gapped if required. Red Hat shipped an OpenShift AI quickstart for it.
- **Proof:** GroundX On-Prem Helm chart repo at `registry.groundx.ai/helm`. The Red Hat AI quickstart `rh-ai-quickstart/Billing-extraction-with-GroundX`. See `proof-points.md` § 4.

### 2.2 "We need full data sovereignty."

- **Reframe:** Same answer — air-gapped Helm deployment, no external dependencies at runtime. Optional Terraform path on AWS, or run on any pre-existing Kubernetes cluster. Use AWS SQS or Kafka, S3 or MinIO, existing OpenSearch or a dedicated cluster — your choice of services.
- **Proof:** Helm chart README documents air-gapped operation explicitly.

### 2.3 "Our security team won't allow another vendor."

- **Reframe:** The on-prem deployment is your infrastructure. The hosted version is opt-in. The Red Hat partnership reduces vendor surface — you are buying a product Red Hat has validated.
- **Proof:** Red Hat AI quickstart partnership.

## 3. Cost and operational

### 3.1 "This is expensive vs free open-source tools."

- **Reframe:** Free open-source tools become expensive at scale — vendor stitching, accuracy degradation, hallucination cleanup, multiple tools to maintain. GroundX's agentic pipeline was designed to use older, cheaper, easier-to-self-host models, which reduces operating cost over time. The premium pays back on accuracy that doesn't require manual review and on a deployment that doesn't require a multi-vendor integration project.
- **Proof:** AskVet's 40% → 80% gross margin shift; the architecture-level cost argument in `technical-architecture.md` § 3.

### 3.2 "We need to deploy across hundreds of use cases — how do we afford the integration cost?"

- **Reframe:** This is the implementation-scale pain. The Studio Harness is the direct answer. Agents that know GroundX intimately stand up new integrations dramatically faster than a one-by-one engineering build — across Claude, Gemini, ChatGPT, Replit, Cursor, smolagents, openclaw, or any agent framework.
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

- **Reframe:** That is fine. The first ask is light — MNDA, share docs and intent. We can demo on your real documents in days, not weeks. The collaborative deep dive happens after you have seen it work on your material. See `sales-motion.md`.
- **Proof:** The sales process.

### 6.2 "We need to see it work on our documents."

- **Reframe:** Best signal we can give. Share a clean dataset under MNDA; we can run a live demo against it. This is part of the standard process. See `sales-motion.md`.
- **Proof:** Air France/KLM's three-month engagement proved out 96.2% accuracy on their actual policy documents.

## 7. What this file does not handle

- Master-brand altitude objections (Visual Intelligence category skepticism, AI+humans accountability pushback). Those defer to `master-brand-gtm/references/objections.md`.
- Pricing objections requiring a specific number. If a price comes up in a sales conversation, route to the sales team — do not quote one in agent-generated content.
- Legal / contract objections. Those route to the legal and contracts owners; messaging here is product-positioning only.
