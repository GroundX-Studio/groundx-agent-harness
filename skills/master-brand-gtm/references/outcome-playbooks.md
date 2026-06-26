# Outcome Plug-in Playbooks

Per-Outcome-Plug-in positioning. Two shipping (FraudX, ExtractX); five illustrative-only (ClaimsX, ComplianceX, OpsX, FinanceX, GridX). For the canonical shipping/illustrative distinction, see `product.md` § 6–8 and `brand-hierarchy.md` § 6. This file owns the messaging detail.

**Hard rule for this file:** illustrative concepts do not get playbooks the way shipping products do. Their entries below are *category-pattern demonstrations*, not market-ready positioning.

## 1. FraudX (shipping — GA)

### Buyer

Four buyer cuts across the insurance-fraud value chain (see `../../product-brand-gtm/references/audiences.md` § FraudX buyer cuts for the product-altitude detail):

- **Carriers & TPAs / Claims teams** — triage suspicious claims at intake; justify reserves; stop paying inflated demands.
- **SIU investigators** — skip the file slog; land on the leads that matter with citations and evidence pre-built.
- **Legal teams / Defense counsel** — build cross-examination off the record; surface contradictions before deposition.
- **General Contractors / GC & law firms** — scale file review across thousands of claims without scaling headcount.

Today's production focus: construction workers' compensation claims fraud investigation.

### Problem statement

Insurance fraud costs the US **$308B annually** (Coalition Against Insurance Fraud, 2023); **10% of every premium dollar** is lost to fraudulent and inflated claims (FBI Insurance Fraud estimate). Modern claim files run to thousands of pages — too many to read manually. SIU headcount doesn't scale with fraud volume, and general-purpose AI tools hallucinate citations that don't hold up in court. FraudX closes the bandwidth gap with an AI investigator that reads every page and links every finding to its source.

### What it is

A productized four-surface AI investigator:

- **FraudX Score** — AI-generated fraud probability for every claim, with ranked red flags, severity tiers (HIGH / MED / LOW), and the evidence behind each finding. Re-runs automatically when new documents arrive. 20+ investigator-defined red flags configured to the line of business.
- **Chat with Claims** — ask the case file anything in plain English; get source-linked answers with no hallucinations. *"Like a research assistant who never misses a detail."*
- **Evidence Package** — source-cited dossier built for SIU referral, reservation of rights, or trial prep. Every red flag links to the exact page, line, and timestamp in the source document. Saves dozens of hours per claim.
- **Network Analysis** — cross-references every actor in the claim (claimants, providers, attorneys, locations) against a network of flagged actors; surfaces organized rings by connecting actors across unrelated claims.

### How it works

Three steps from a stack of unstructured documents to a defensible, source-cited fraud assessment:

1. **Ingest the entire claim file** — medical records, bills, ISO reports, depositions, photos, site reports, recorded statements. Any format, any length.
2. **Run 20+ fraud checks** — FraudX scores each claim against an extensible library of indicators tuned by SIU investigators and defense counsel.
3. **Deliver a cited, source-linked dossier** — every red flag links back to the exact page, line, and timestamp. Defensible from day one.

### Positioning (master-brand altitude)

> *FraudX is the first shipping Outcome Plug-in — Valantor-operated, GroundX-powered insurance fraud detection delivered as a productized solution. An AI investigator that never blinks: it reads every page of every claim, surfaces the red flags, and builds the file investigators need to deny, defend, or recover — in minutes, not months. Built on GroundX, productized for repeatable enterprise deployment with the speed, accuracy, and auditability fraud teams need.*

### Use in master-brand materials

- Lead proof point for the *[Outcome]X* productization pattern.
- Vertical-thesis anchor for insurance and regulated-financial-services framing.
- AI+humans accountability proof: investigators stay in the loop; the system encodes their expertise rather than replacing it.
- Investor-narrative anchor for *"vertical Outcome Plug-ins are a real product line, not just a roadmap."*
- Tagline-ready: *"An AI investigator that never blinks"* / *"Find source-linked fraud signals faster"* / *"Show every flagged network with evidence."*

### Proof (see `proof-points.md` for full citations)

- 3 named customer quotes — Kirk Willis (Willis Law Group), Andriana Vamvakas (Andromeda Advantage), Dan Hickey (Tradesman/Roosevelt Road). See `proof-points.md` § 7 quote bank.
- ROI snapshot (EyeLevel internal benchmark; *"Actual results vary."*) — 40× faster review, 10× more files reviewed per day, directional reduction in loss ratio. See `proof-points.md` § 2.4.
- Team credentials — built by the AI engineers behind IBM Watson, 20+ patents in AI / digital security / enterprise systems, co-developed with elite SIU teams. See `proof-points.md` § 4.2.

### Do not

- Invent accuracy numbers or claim-volume figures beyond what's in `proof-points.md`. Specific customer numbers route through sales.
- Claim FraudX runs across all insurance lines today. Construction workers' comp is the production focus; other lines are forward-looking.
- Conflate FraudX with general claims processing (that is the illustrative ClaimsX concept — see § 3).
- Quote 40× or 10× without the *EyeLevel internal benchmark* attribution and *"Actual results vary"* qualifier.
- Use judgmental labels for people, doctors, providers, firms, or claim participants in reusable copy. Avoid phrases like "bad guys," "bad actors," and "bad doctors." Use neutral terms such as flagged entities, watch list, data list, claim participants, providers, networks, or source-linked fraud signals.

## 2. ExtractX (shipping — GA)

### Buyer

Companies or BPOs (business process outsourcers) with human teams paired to legacy OCR / templating systems for invoice and document processing. Common buyer types: shared-services finance teams, BPO operations leaders, document-ops directors at financial-services and insurance companies, healthcare back-office teams.

### What it is

A productized data-extraction outcome. Today, delivered in two operational modes:

- **As a service.** Valantor team uses GroundX internally on behalf of the client to deliver extracted data; the client consumes the output without operating the platform.
- **As a partner deployment.** Valantor integrates GroundX into the customer's existing document-processing workflows; the customer operates with Valantor's support.

Roadmap: expose ExtractX entirely via the Harness and Studio for rapid customer-led implementation — moving from *service / partner deployment* mode toward *customer self-service via the platform*.

### Positioning (master-brand altitude)

> *ExtractX modernizes the document-extraction pipelines that BPOs and operations teams run today on legacy OCR plus human review. Delivered as a managed outcome — Valantor operates the platform; the customer consumes extracted, structured data — or as a partner deployment integrating GroundX into the customer's existing workflows. Replaces OCR templates with GroundX's reasoning-driven extraction at scale.*

### Use in master-brand materials

- Second shipping Outcome Plug-in proof — demonstrates the vertical breadth of the productization pattern (insurance fraud + document operations, two distinct industries).
- Best lead for the outcomes-vs-tools narrative in `ai-and-humans.md` — ExtractX literally is *the outcome (extracted data) sold as a service*. It is the most concrete operationalization of the Operational Layer concept (§ 5 of `ai-and-humans.md`) that exists today.
- Anchor for the *legacy-OCR-replacement* messaging — competitive against the in-place stack of OCR templates plus human review, not against vector-DB stacks.

### Do not

- Claim ExtractX is fully self-service via Studio today. Self-service via the Harness and Studio is the roadmap; current MVP is service-mode or partner-deployment.
- Quote pricing or per-document rates.
- Frame ExtractX as a replacement for FraudX or vice versa — they target distinct verticals.

## 3. ClaimsX (illustrative concept only — not shipping)

### State

Illustrative marketing concept. **No customer-facing implementation.** Used in master-brand materials and the brand-architecture document to demonstrate the *[Outcome]X* pattern extension into claims processing as a vertical adjacent to fraud investigation.

### Use when

- Articulating the vertical extension pattern: *"the Outcome Plug-in family extends from FraudX (fraud investigation) into adjacent claims-processing outcomes — ClaimsX is the named roadmap concept for that extension."*
- Demonstrating naming consistency in the [Outcome]X pattern.

### Do not

- Write external content as if ClaimsX ships.
- Invent customer outcomes, accuracy numbers, deployment counts, or pilot details.
- Position ClaimsX in proof-point sections — there are no proofs yet.

## 4. ComplianceX (illustrative concept only — not shipping)

### State

Illustrative marketing concept. **No customer-facing implementation.** Demonstrates the pattern extension into compliance workflows — regulatory reporting, audit-trail generation, policy-compliance validation.

### Use when

- Articulating vertical extension into regulated workflows where the Visual Intelligence claim (trusted, auditable, governed) maps directly onto a compliance-officer buyer.

### Do not

- Claim ComplianceX is in pilot, in development, or otherwise productized. It is a category-pattern demonstration only.

## 5. OpsX, FinanceX, GridX (illustrative concepts only — not shipping)

### State

Illustrative marketing concepts named in the Valantor brand-architecture document. Demonstrate the pattern extension into operations (OpsX), finance functions (FinanceX), and energy/grid (GridX) verticals.

### Use when

- Establishing breadth in category-creation white papers and investor narratives — *"the [Outcome]X family is the productization pattern Valantor extends across regulated, asset-heavy verticals over time."*

### Do not

- Write any content as if they ship.
- Invent customer outcomes.
- Promise dates.

## 6. The composite messaging pattern

When writing a master-brand piece (white paper, investor narrative, analyst briefing) that needs to cover the Outcome Plug-in family:

1. Lead with the shipping pair: **FraudX (insurance fraud, GA)** + **ExtractX (document operations, GA)**.
2. Position them as the live proofs of the *[Outcome]X* productization pattern — the pattern is real, not theoretical.
3. Reference the roadmap-of-the-pattern: *"The same pattern extends into adjacent regulated verticals — claims processing (ClaimsX), compliance workflows (ComplianceX), operations (OpsX), finance functions (FinanceX), energy/grid (GridX)."* — explicitly framed as roadmap, never as shipping.
4. Tie back to the strategic frame: Outcome Plug-ins are how Valantor industrializes Visual Intelligence into repeatable vertical products with SLAs.

A clean composite phrasing:

> *Valantor's Outcome Plug-in family today includes two shipping vertical solutions — FraudX for insurance fraud investigation and ExtractX for document-operations extraction. Both are Valantor-operated, GroundX-powered, productized for repeatable enterprise deployment. The same pattern extends across the Outcome Plug-in roadmap into claims processing, compliance workflows, operations, finance, and energy/grid verticals (ClaimsX, ComplianceX, OpsX, FinanceX, GridX).*

## 7. Cross-references

- `product.md` § 6–8 — the canonical state matrix for every Outcome Plug-in.
- `brand-hierarchy.md` § 6 — the hard rules on Outcome Plug-in framing (not companies, not bespoke, every Outcome powered by GroundX).
- `verticals.md` — the why-these-verticals thesis (regulated, asset-heavy, compliance-intensive).
- `proof-points.md` — customer outcomes that anchor the FraudX and ExtractX positioning.
