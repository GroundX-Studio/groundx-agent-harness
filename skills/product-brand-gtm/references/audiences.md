# Audiences

Persona-axis overlay on the message-axis. Use this file to adapt the pitch shape — defined in `buyer.md` — to a specific buyer persona without changing the underlying claims.

For the master market context (the AI-existential-crisis dynamic) that shapes every audience, see `buyer.md` § 1. For the implementation-scale pain, see `buyer.md` § 2. For the differentiator pillars used to construct each persona pitch, see `differentiation.md`.

**Audience ordering note.** Line-of-Business owners (§ 1 below) are listed first because the existential-crisis dynamic makes them the preferred buyer wherever a choice exists. CIO / VP Eng / Data Lead audiences (§§ 2–4) are framed as **potentially hostile gatekeepers with competing internal AI projects** rather than as straightforward technical buyers.

## 1. Line-of-Business owner (Customer Service, Claims, Compliance, Operations, Fraud Investigation, BPO ops)

**Why this audience comes first.** LOB owners measure their world in outcomes the business already understands — cost per case, resolution rate, fraud-detect rate, margin, FTE displacement, time-to-revenue. They are not threatened by AI in the same way IT and engineering are; they are looking for tools that help them hit business metrics. They are the buyer the existential-crisis dynamic in `buyer.md` § 1 directs us toward.

**What they care about.** Business outcomes. Cost reduction. Time-to-value. Whether the system actually answers the customer's question or pulls the right field from the document without hallucinating. Champion-readiness — can they walk it into IT and defend the choice.

**Pitch shape.**
- Lead with **customer outcomes** — Air France/KLM 96.2% beating a 60% target, AskVet's 40% → 80% margin shift and 70–85% autonomous resolution, FraudX in production with four product surfaces and 20+ investigator-defined fraud checks.
- Lead second with **the Operational Layer concept** if the buyer would rather pay for the outcome than for a tool — see `product.md` § 9.
- Pillar order: 2 (accuracy proof) → 5 (Harness as adoption velocity) → 1 (on-prem if compliance comes up) → 4 (integrated architecture) → 3 (heritage).
- Reference `proof-points.md` § 1 and § 2, and `product.md` § 6 (FraudX) or § 7 (ExtractX) when there's a vertical fit.
- Emphasize: real, defensible customer numbers; time-to-value (Studio live in days; FraudX as a production GUI today; three-month Air France/KLM engagement to production); the *we will deliver the outcome, not just the tool* framing.
- De-emphasize: architecture details, the routing and skill mechanics of the Harness as infrastructure.

## 2. CIO / CTO

**Audience context.** Often facing the AI existential crisis personally — they are accountable for AI strategy at the same time they may have an internal team building AI projects defensively. They may quietly want the vendor solution to succeed, or may quietly want it to fail to protect their internal program.

**What they care about (stated).** AI-native transformation across the enterprise. Hundreds of AI use cases at varying maturity. Standardization that keeps switching costs down and platform debt manageable.

**What they often care about (unstated).** Whether bringing in this vendor will be seen as undermining their internal team's relevance. Whether they can position the adoption as their own initiative.

**Pitch shape.**
- Lead with the implementation-scale pain — it frames the conversation as *how do we scale AI across 500 use cases* rather than *here's another AI vendor*.
- **Find an LOB champion in parallel** — even when the CIO is the convening buyer, the LOB voice de-risks the pitch by showing demand is from business operations, not from IT being sold to.
- Pillar order: 5 (Harness as the operational answer) → 2 (accuracy bar that scales) → 1 (on-prem for compliance breadth) → 4 (integrated architecture) → 3 (heritage).
- Emphasize: standardization, multi-use-case economics, model-agnostic posture, **the Harness as a force-multiplier that makes the internal team more productive, not redundant.**
- De-emphasize: low-level technical mechanism (defer to VP Eng).

## 3. VP / Director of Engineering

**Audience context.** Closest to the existential crisis. Their team often *is* the internal AI project the CIO is protecting. Pitching here without acknowledging that dynamic is the fastest way to lose the room.

**What they care about (stated).** Can their team actually build with this. Integration complexity. Operational burden. Whether the system can be self-hosted, governed, and observed.

**What they often care about (unstated).** Whether adopting this vendor solution means their team gets smaller, or whether it lets their team take on more ambitious work. The Harness pitch lands much better when framed as the second.

**Pitch shape.**
- Lead with on-prem / Helm / Red Hat partnership (pillar 1) and integrated architecture (pillar 4) — these are *engineering excellence* messages that earn respect without threatening.
- Pillar order: 1 → 4 → 2 → 5 → 3.
- Open the technical-architecture conversation. Reference `technical-architecture.md`.
- Emphasize: Helm chart deployability, SDKs in Python and TypeScript, MCP wrapper, autoscaling, no external dependencies in air-gapped mode, **the Harness as a tool that makes their team's work tractable across the 500-use-case backlog rather than replaceable.**
- De-emphasize: business outcomes (defer to LOB); the *we will do it for you* Operational Layer framing — that reads as threatening to this audience.

## 4. Data Lead / Head of ML / Head of AI

**Audience context.** Often running the defensive internal AI project. Often a vector-database believer or a build-from-foundation-models believer. Cynical about new AI vendors.

**What they care about (stated).** Accuracy at scale on the actual document corpus. Whether RAG will work. Whether extraction will hold up across document variants. Vector DB tradeoffs.

**What they often care about (unstated).** Whether GroundX's approach validates or invalidates the architectural bets they have made internally. A pitch that argues *vector-DB-only loses accuracy at scale* (one of our head-to-head posts) can read as a personal attack.

**Pitch shape.**
- Lead with the **accuracy pillar (pillar 2)** and the technical "why" behind it — let the architecture earn the credibility rather than asserting it.
- Pillar order: 2 → 4 → 3 → 1 → 5.
- Open the head-to-head testing references and DocBench. Reference `proof-points.md` § 1 and `technical-architecture.md`.
- Emphasize: vision model + agentic pipeline + hybrid search; OpenSearch-not-vector-DB design *as a complementary approach to their internal stack rather than a replacement*; why this beats stitched-together stacks at scale.
- De-emphasize: the no-code Studio UI; framing that implies their internal AI program was wasted effort.

## 5. Procurement / Vendor management

**What they care about:** vendor risk, security posture, deployment options, terms, references.

**Pitch shape:**
- Lead with on-prem / air-gapped optionality (pillar 1) — *we can deploy inside your perimeter; you do not have to send data anywhere.*
- Pillar order: 1 → 3 (heritage as trust signal) → 4 → 2 → 5.
- Reference the Red Hat OpenShift AI partner quickstart.
- Emphasize: deployment options (cloud, on-prem, air-gapped), Red Hat partnership, model-agnostic posture, decade-plus team heritage.
- De-emphasize: forward-looking features.

## 6. Investor (founder / executive briefing)

**What they care about:** category, defensibility, valuation profile. Premium-multiple positioning. TAM and expansion.

**Pitch shape:**
- This audience is typically a `master-brand-gtm` audience. Defer when the conversation is at master-brand altitude (category creation, AI+humans accountability, vertical Outcome Plug-in strategy, infrastructure-grade economics).
- If GroundX product narrative is needed: lead with the heritage (pillar 3) → architecture defensibility (pillar 4) → on-prem moat (pillar 1) → accuracy proof (pillar 2) → Harness adoption pattern (pillar 5).
- Emphasize: years of pre-AI-boom development, the technical pedigree from Watson, the on-prem deployment moat.
- De-emphasize: tactical sales process.

## 7. FraudX buyer cuts (vertical-specific overlay on § 1 LOB owner)

FraudX is the first shipping Outcome Plug-in (see `product.md` § 6 for product detail). Its buyers cut across the insurance-fraud value chain — same Outcome Plug-in, configured to how each team works the file. Treat these as vertical-specific instances of § 1 (Line-of-Business owner) — each has its own outcome the business already measures.

### 7.1 Carriers & TPAs / Claims teams

**Outcome they measure.** Loss ratio, inflated-demand spend, time to reserve.

**Pitch hook.** *"Triage suspicious claims at intake. Justify reserves. Stop paying inflated demands before they become losses."*

**What they want.** Early signal at intake — before a claim ages into a paid loss. The Score surface is the lead value; Network Analysis matters when ring exposure is part of the loss-ratio conversation.

### 7.2 SIU / Investigators

**Outcome they measure.** Cases worked per investigator, fraud-detect rate, referral quality.

**Pitch hook.** *"Skip the file slog. Land on the leads that actually matter — with citations attached and evidence pre-built."*

**What they want.** Time back on the cases worth investigating. The Chat with Claims and Evidence Package surfaces are the lead value; the system encodes their expertise rather than replacing it.

### 7.3 Legal teams / Defense counsel

**Outcome they measure.** Win rate, settlement leverage, billable efficiency.

**Pitch hook.** *"Build your cross-examination off the record. Surface contradictions before deposition. Win on facts."*

**What they want.** Defensible evidence with citations that hold up in court. The Evidence Package surface is the lead value; *"no hallucinations, every finding linked to page, line, timestamp"* is the unlock.

### 7.4 General Contractors & GC / law firms

**Outcome they measure.** Margin per case, throughput, headcount discipline.

**Pitch hook.** *"Scale file review across thousands of claims without scaling headcount. Win on margin, not hours."*

**What they want.** Operational leverage on a volume business. The Score + Evidence Package surfaces together — automated first-pass triage with cited dossiers ready for the cases that warrant deeper work.

### Cross-cut rules

- All four buyers can be the LOB champion; the pitch order varies by which outcome they measure first.
- Carriers/TPAs and SIU usually live inside the same buying organization (carrier with in-house SIU); the conversation flows between them but the budget often sits with the carrier's claims operations leader.
- Legal / GC + law firm buyers are typically external to the carrier and buy on their own contract — *don't conflate them with carrier SIU in the same deal motion*.
- For the master-brand-altitude reframe of these four cuts, see `../../master-brand-gtm/references/outcome-playbooks.md` § 1 (FraudX buyer).
- For the customer voice on the record, see `../../master-brand-gtm/references/proof-points.md` § 7 quote bank (Kirk Willis / Andriana Vamvakas / Dan Hickey).

## 8. Persona cross-pitch rules

- **Do not pitch every pillar to every audience.** Three or four pillars in a meeting is plenty; saving one for follow-up creates a reason to meet again.
- **Do not let a technical audience lead with business outcomes, or vice versa.** Match the altitude first; expand outward.
- **Do not collapse personas into "the buyer."** A pitch reads as off-target the moment a CIO gets the Data Lead pitch or vice versa. Use this file to keep the persona axis explicit.

## 9. When the persona is not yet known

Default to the broader-universe pitch shape from `buyer.md` § 3 — lead with capability, accuracy, and on-prem optionality. Ask discovery questions early ("which AI use cases have you tried?" "what does your deployment posture look like?") to identify the persona, then shift the pitch shape accordingly.
