# Sales Motion

The sales process from initial meeting to working deployment. Three phases: immediate, discovery, commit. This is the public-facing version sourced from the 2026 sales deck; the team may run a sharper internal version. When agent-generated content describes the process, it should match this shape.

For who the buyer is, see `buyer.md`. For audience-specific adaptations of the conversation in each phase, see `audiences.md`. For the objection responses that come up along the way, see `objections.md`.

## 1. Phase 1 — Immediate (this meeting forward)

- **Execute MNDA.** Mutual non-disclosure that lets the buyer share real documents and the team share architecture details that aren't public.
- **Share docs + intent.** The buyer points at the actual documents they want to work with — the visually complex, high-volume, regulated material that defeated their previous attempts. They also share *intent*: what they want the system to do (extraction? full RAG? both?), against what corpus, for which users.

**Why this phase exists:** the demo and the deep dive are dramatically sharper when they happen on the buyer's real material. Generic demos do not close.

## 2. Phase 2 — Discovery

Two parallel tracks:

- **Live demo, or clean dataset.** Either we run a live demo against the documents the buyer shared, or — if the documents need cleanup or are too sensitive for a live session — they hand off a clean dataset and we return with results. The point is to see the system work on *their* material before the conversation continues.
- **Collaborative deep dive.** Architecture, integration shape, deployment posture (cloud, on-prem, air-gapped), security model, model selection, expected accuracy targets, success criteria. This is where the buyer's VP Eng or Data Lead joins the conversation and where `technical-architecture.md` and `differentiation.md` get cited heavily.

**Time signature:** days to weeks. Air France/KLM's full engagement to production was three months from kickoff (see `proof-points.md` § 1.2); the discovery sub-phase is usually a smaller fraction of that.

## 3. Phase 3 — Commit

- **Scoped proposal.** Specific deliverables, success criteria, deployment shape (hosted, on-prem, air-gapped), engagement length, pricing. Built around what the discovery phase actually surfaced — not a generic SKU.
- **Contract → deliver.** Once signed, the team executes against the scoped proposal with the customer's experts in the loop validating outputs and tuning the system to their accuracy bar.

## 4. What good looks like inside the motion

- The buyer brings real documents to phase 2, not synthetic ones.
- The technical deep dive happens with the right buyer-side technical lead in the room (VP Eng, Data Lead, head of ML/AI).
- The buyer's success criteria are measurable (e.g. *"96.2% accuracy beating the 60% target"* from Air France/KLM, not *"better than what we had"*).
- The deployment shape is decided before contract — cloud, on-prem, air-gapped — so the contract reflects the right operational scope.
- The first deployment lands on a real use case, not a sandbox demo, so adoption signal is genuine.

## 5. Common failure modes inside the motion

| Failure mode | What to do |
| --- | --- |
| Buyer wants to skip MNDA and demo on a public dataset | Push back politely; demos on the buyer's material are dramatically more compelling and accelerate the rest of the process. |
| Buyer's documents aren't cleanly accessible | Offer the clean-dataset path: they hand off a sample under MNDA, the team returns with results. |
| Wrong buyer-side audience in the deep dive | Reschedule with the right technical lead. Demos to non-technical audiences usually don't survive a follow-up technical review. |
| Buyer signals on-prem requirement late in the process | Re-shape the proposal — the on-prem story is a strength, not a delay. See `differentiation.md` § 1 and `objections.md` § 2. |
| Buyer compares against a free open-source alternative late in the cycle | Surface the integrated-architecture argument and the head-to-head testing. See `objections.md` § 3.1 and `differentiation.md` § 4. |

## 6. What the motion does not include

- Free indefinite proof-of-concept. The MNDA-and-real-docs phase is fast; the discovery phase is structured; commit is contract. Long open-ended POCs are not the model.
- Bespoke per-customer engineering as the default. Customizations happen, but the core product is what gets sold. Vertical Outcome Plug-ins (FraudX, ClaimsX, ComplianceX) are the productized pattern when a vertical needs more — see `brand-relationship.md` § 6 and route to `master-brand-gtm` when that altitude opens up.
- Pricing in agent-generated content. Pricing is set by the sales team in the context of the scoped proposal; do not quote numbers from this skill.

## 7. Hand-off to medium skills

When the user asks the agent to produce an artifact that supports the motion:

| Artifact | Route to | This skill supplies |
| --- | --- | --- |
| Sales deck | Available deck-production skill or presentation-producing agent | Narrative, differentiation, proof points, audience-appropriate emphasis. |
| Discovery one-pager | Available document- or deck-production skill | Same as above; compressed. |
| Outbound or follow-up email | The agent producing the email | Voice register from `../product-brand-design-standards/references/voice.md`; pitch shape from `buyer.md`; specific claims from `proof-points.md`. |
| Proposal | A future docs skill | Phase-3 scoped-proposal structure (this file § 3); deliverables and criteria from the discovery phase. |
| Demo-prep brief | The agent | Audience cut from `audiences.md`; objection prep from `objections.md`. |
