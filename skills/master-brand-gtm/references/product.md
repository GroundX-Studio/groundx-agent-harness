# Product: Master-Brand Altitude

Per-entity product-state inventory at **master-brand altitude**. Mirrors `../../product-brand-gtm/references/product.md` but reframes each entity for Valantor / category / investor framing rather than for product-pitch framing. The product-state matrix is the same matrix; the language is different.

**Do not invent state.** If an entity below is marked *concept* or *illustrative*, do not write external content as if it ships. This master-brand product-state matrix is the local source for Valantor altitude and is authoritative as of 2026-05-14. Cross-check `../../product-brand-gtm/references/product.md` for product-altitude detail.

## 1. The product map at a glance

| Layer | Product | State |
| --- | --- | --- |
| Hosted platform | **Hosted GroundX** | GA |
| Self-hosted platform | **GroundX On-Prem** (Helm) | GA |
| No-code single UI | **GroundX Studio** (UI) | In development |
| Agentic adoption | **GroundX Studio Harness** | Alpha |
| Outcome Plug-in | **FraudX** | GA |
| Outcome Plug-in | **ExtractX** | GA |
| Outcome Plug-in | **ClaimsX, ComplianceX, OpsX, FinanceX, GridX** | Illustrative marketing concepts only |
| Service layer | **Operational Layer** (Valantor agents + human orchestration) | Concept |

## 2. Hosted GroundX (master-brand framing)

The hosted SaaS distribution of Valantor's Visual Intelligence platform. Today, the master-brand framing positions Hosted GroundX as the inbound discovery channel — the way individual technical users evaluate Visual Intelligence before enterprise procurement begins. The broken dashboard and Studio-rebuild path (see `../../product-brand-gtm/references/product.md` § 2) are product-altitude details; at master-brand altitude, the talking point is *Valantor's platform is freely accessible for evaluation; enterprise engagement begins when an organization moves from individual-user testing to multi-stakeholder deployment.*

## 3. GroundX On-Prem (master-brand framing)

The self-hostable, air-gapped, Helm-deployable distribution. **GA.** The master-brand talking point: *Valantor is the only Visual Intelligence platform that deploys inside the customer's perimeter at infrastructure-grade scale, including fully air-gapped environments.* The Red Hat OpenShift AI partnership is the third-party validation. For regulated industries and data-sovereignty buyers — the Valantor ICP — On-Prem is often the only acceptable deployment posture.

The public Helm chart README's "Open Beta" tag is stale; treat GroundX On-Prem as GA in all master-brand-altitude materials.

## 4. GroundX Studio — the UI (master-brand framing)

The no-code single UI consumption surface. **In development.** Three use cases: Extract (data extraction), Interact (chat / RAG), Report (smart pre-compiled RAG with follow-up chat). The master-brand framing avoids the product-altitude detail (Replit-built prototype, rebuild via Harness) and positions Studio as *the demonstration surface where business users see Visual Intelligence value without IT or formal deployment* — the champion-enablement path for the LOB / outcome-buyer audience routing in `buyer.md`.

## 5. GroundX Studio Harness (master-brand framing)

The agentic adoption layer. **Alpha.** The master-brand framing: *the Harness is how Valantor industrializes Visual Intelligence across hundreds of enterprise AI use cases.* It is the operational answer to the implementation-scale pain (*"I have 500 AI agent use cases, how am I going to implement them all?"*). At master-brand altitude, the Harness is a productivity-multiplier story for the platform; product-altitude detail (Claude/Codex install, Cursor/Replit roadmap) lives in `../../product-brand-gtm/references/product.md` § 5.

## 6. FraudX (Outcome Plug-in — GA)

Vertical Outcome Plug-in for insurance fraud investigation. **GA.** Currently focused on construction workers' compensation claims fraud. Current external sales framing presents FraudX as a four-surface AI investigator: **FraudX Score**, **Chat with Claims**, **Evidence Package**, and **Network Analysis**. The deck-level product story is: ingest the entire claim file, run **20+ investigator-defined fraud checks**, and deliver a cited, source-linked dossier defensible from day one.

Master-brand talking point: *FraudX is the first shipping Outcome Plug-in — a productized vertical solution where Valantor operates the platform on behalf of the customer to deliver fraud-detection outcomes with speed, accuracy, and auditability. Built on GroundX, productized for repeatable enterprise deployment.*

Use FraudX as the lead proof point when articulating the Outcome Plug-in pattern in category-creation, investor, or analyst materials.

## 7. ExtractX (Outcome Plug-in — GA)

Vertical Outcome Plug-in for document extraction at BPO and operations scale. **GA.** Replaces legacy OCR + human-review pipelines for invoice and document processing. Delivered today either as a service (Valantor team runs the tool on behalf of the client) or as a partnership deployment integrating GroundX into the customer's existing document-processing workflows. Roadmap: expose entirely via the Harness and Studio for rapid customer-led implementation.

Master-brand talking point: *ExtractX productizes the document-extraction outcome for organizations replacing OCR-and-human-review pipelines — particularly BPOs and operations teams in financial services, insurance, and shared-services functions.*

Use ExtractX as the second shipping Outcome Plug-in proof when articulating vertical breadth (insurance fraud + document operations are working today; the pattern extends from there).

## 8. ClaimsX, ComplianceX, OpsX, FinanceX, GridX — illustrative concepts

**Not shipping.** These names appear in Valantor master-brand materials and the brand-architecture document to demonstrate the *[Outcome]X* productization pattern across verticals (claims processing, compliance workflows, operations, finance, energy/grid). They do not have customer-facing implementations today.

**Do not:**
- Write external content as if any of them ships.
- Invent customer outcomes, accuracy numbers, deployment counts, or pilot details for them.
- List them in proof-point sections.

**Do (carefully):**
- Use them as illustrations of the *[Outcome]X* pattern in category-creation materials, white papers, and investor narratives — explicitly framed as the productization pattern Valantor extends into new verticals over time, not as shipping products.
- Cite FraudX and ExtractX as the live proofs of the pattern, with the named concepts as the *roadmap of where the pattern goes*.

A clean external phrasing: *"The Outcome Plug-in family today includes the shipping FraudX (insurance fraud) and ExtractX (document operations), with ClaimsX, ComplianceX, and additional verticals (operations, finance, energy/grid) on the productization roadmap."*

## 9. Operational Layer (concept)

**State: concept — no shipping customer product yet.** Valantor has the offshore infrastructure (shops in India and Macedonia) to scale this rapidly when a customer is landed.

Master-brand talking point: *the Operational Layer is the productized expression of outcomes-as-a-service — companies pay for the business outcome (extracted data delivered, fraud claims investigated, compliance reports completed) rather than for the AI tool that produces it. Valantor operates the platform, the agents, and the human-in-the-loop oversight; the customer consumes the outcome on an SLA.*

**Do not claim shipping status externally.** Investor narrative articulates the strategic posture; customer-facing surfaces stay at *"available on request"* or *"engagement-based"* until the first customer is landed.

The Operational Layer is the single largest piece of the *AI + humans accountability* story (see `ai-and-humans.md`). It reframes services from low-multiple consulting into managed AI infrastructure with SLAs and long-term contracts — a premium-multiple valuation lever.

## 10. How to use this file

The matrix above is the answer when a master-brand-altitude audience asks:

- *"What is Valantor's platform?"* — § 2 + § 3 (Hosted + On-Prem are the platform; one is SaaS, one is self-hosted, same engine).
- *"What does Valantor offer beyond the platform?"* — § 4 (Studio UI), § 5 (Harness), § 6–8 (Outcome Plug-ins), § 9 (Operational Layer).
- *"What is FraudX / ExtractX / ClaimsX?"* — § 6 / § 7 / § 8. Surface the shipping/illustrative distinction every time.
- *"Can we just pay you to deliver the outcome?"* — § 9 (Operational Layer is the answer in concept; flag that it is not GA and a real engagement is the way to make it real).

For positioning *why* each product exists in a buyer-specific way, see `audiences.md`. For *what to say when an Outcome Plug-in audience pushes on a specific vertical*, see `outcome-playbooks.md`. For the technical *how*, defer to `../../product-brand-gtm/`.

## 11. What this file does not cover

- Pricing, terms, contract shapes. Master-brand work does not quote prices; route to sales.
- Customer-specific outcomes. Those live in `proof-points.md`. This file states what products exist; `proof-points.md` cites what customers got from them.
- Product mechanism. Vision model, agentic pipeline, hybrid search — those belong to `../../product-brand-gtm/references/technical-architecture.md` (product altitude).
- Visual brand decisions. Those belong to `../../master-brand-design-standards/`.
