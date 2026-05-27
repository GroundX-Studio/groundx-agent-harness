# Product: What Is Built, MVP, and Capabilities

Authoritative product-state inventory for every shipping (or named) product entity in the EyeLevel / GroundX / Valantor stack. Each entity has State, Buyer, MVP today, Roadmap next, and a short Why. Treat this file as the source of truth for product claims — `proof-points.md` cites customer outcomes; `brand-relationship.md` covers the brand hierarchy; this file covers *what each product actually is right now.*

**Do not invent state.** If an entity below is marked *concept* or *illustrative*, do not write external content as if it ships. This product-state inventory is the local source of truth for product-altitude claims and is authoritative as of 2026-05-14. For master-brand framing, cross-check `../../master-brand-gtm/references/product.md`.

## 1. The product map at a glance

| Layer | Product | State |
| --- | --- | --- |
| Hosted SaaS | **Hosted GroundX** | GA |
| Self-hosted | **GroundX On-Prem** (Helm distribution) | GA |
| No-code single UI | **GroundX Studio** | In development |
| AI Agent Harness | **GroundX Studio Harness** | Alpha |
| Outcome Plug-in | **FraudX** | GA |
| Outcome Plug-in | **ExtractX** | GA |
| Outcome Plug-in | **ClaimsX** | Illustrative concept |
| Outcome Plug-in | **ComplianceX** | Illustrative concept |
| Outcome Plug-in | **OpsX**, **FinanceX**, **GridX** | Illustrative concepts |
| Service layer | **Operational Layer** (Valantor agents + human orchestration) | Concept |

Hosted GroundX and GroundX On-Prem are sibling distributions of the same engine; everything else either sits on top of them, packages them differently, or productizes Valantor's services around them.

## 2. Hosted GroundX

- **State.** GA.
- **Buyer.** Self-service inbound user. Typically arrives via SEO or content (influencer-promoted blog post, YouTube, podcast). Runs the gamut of verticals. **Volume:** ~30 signups per day. **Conversion:** very low.
- **MVP today.** A small allowance of ingestion tokens (the metering unit for files ingested) and search requests, accessed through an end-user dashboard. The dashboard experience is currently broken and clearly is not fulfilling the user's interest.
- **Roadmap next.** Replace the dashboard with GroundX Studio as soon as possible, building Studio via the GroundX Studio Harness.
- **Why this exists.** Inbound discovery channel — a low-friction way for individual technical users to evaluate the GroundX engine before a managed sale starts. Today it converts poorly; the Studio rebuild is the lever to fix that.

## 3. GroundX On-Prem

- **State.** GA. The public Helm chart repository at `github.com/eyelevelai/groundx-on-prem` carries an "Open Beta" tag that is stale — treat the public repo as authoritative for capabilities and dependencies, not lifecycle state.
- **Buyer.** SRE, VP of Engineering, the person who owns product or the person who owns deployment. Usually an **influencer in the buying decision, not the decision maker.** Their job is to evaluate the level of effort to integrate and install.
- **MVP today.** Helm chart-based installation deployable to cloud, on-prem, or fully air-gapped Kubernetes. No external runtime dependencies. Includes Ingest service (fine-tuned vision model + agentic pipeline at document/section/chunk levels), Store (encrypted storage for source files, semantic objects, vectors), Search (OpenSearch + fine-tuned re-ranker + hybrid retrieval), SDK access (Python, TypeScript), REST API parity with hosted, HPA autoscaling + custom metrics server, optional Prometheus integration, optional AWS Terraform path, Red Hat OpenShift AI partner quickstart, x86_64 publicly (arm64 on customer request). The `values.yaml` is **very confusing** today given poor documentation and the wealth of configurable options.
- **Roadmap next.** Properly educate on all of the configuration options — the values-file UX is the active gap.
- **Why this exists.** The only viable path for regulated and data-sovereignty buyers. Differentiator pillar 1; almost no competition in document understanding or RAG when deploying on-prem. The buyer's job is to land confidence that the install is tractable — so docs quality directly drives win rate.

## 4. GroundX Studio (no-code single UI)

- **State.** In development.
- **Buyer.** The **business user** who wants to see the value of GroundX without needing IT or a formal deployment. Potentially a major decision maker in the purchase. Strategically, this is a buyer we want to see the value early and become a champion who can go fight IT for the product.
- **MVP today.** A Replit-built buggy implementation that has most of the desired features but is buggy. **This was the inspiration for building the Harness** — it showed what was possible with coding tools given the proper direction, which is the proof of concept the Harness systematizes.
- **Roadmap next.** Develop consensus on the final design, rebuild via the GroundX Studio Harness within days, replace the existing GroundX dashboard experience with this.
- **Why this exists.** The hosted GroundX dashboard is broken. Studio is the productized fix — and the *champion-enabler* for the LOB pitch path. A business user who plays with Studio and gets value becomes the internal advocate when IT pushes back.
- **Use cases packaged in the UI.** **Extract** (data extraction), **Interact** (chat / RAG), **Report** (smart pre-compiled RAG queries assembled into a report with follow-up chat). These names are coined by the sales team and should be used verbatim.

## 5. GroundX Studio Harness

- **State.** Alpha. This is the product we are inside right now.
- **Buyer.** The executive team. The IT team. The Harness is *the how* for scaling GroundX deployments and dropping implementation time from months to days. It is the operational answer to the *"I have 500 AI agent use cases, how am I going to implement them all?"* pain (see `buyer.md` § 1).
- **MVP today.** GroundX Studio Harness is an **AI Agent Harness**. Install the plugin via Claude or OpenAI Codex; interact via the existing Claude or OpenAI experience. The Harness packages skills, connectors, references, templates, and design patterns that an installed agent loads automatically to become fluent in GroundX.
- **Roadmap next.** Iteratively expand integration points to other agent surfaces (Cursor, Replit, Gemini — at minimum confirm functionality there; some may already be compatible). Build a no-code GUI on top of the harness, mirroring how Cursor and Replit expose coding agents. GA to customers as an enabling tool.
- **Why this exists.** Two reasons. (1) Scaling GroundX adoption — the customer is doing many AI use cases, and the harness lets agents stand them up without a one-by-one engineering build. (2) Reducing the cost of building the *other* GroundX products (Studio especially) — the Replit-built Studio prototype proved coding agents could do it; the Harness gives them the right substrate.
- **Treat as messaging pillar, not technical moat.** Easy to copy. Pillar holds because every AI winner so far has won by being the easiest path into a capability for a buyer who was underserved by what existed before — see `differentiation.md` § 5.

## 6. FraudX (Outcome Plug-in)

- **State.** GA.
- **Buyer.** Four cuts across the insurance-fraud value chain (canonical detail in `audiences.md` § FraudX buyer cuts): **Carriers & TPAs claims teams** (triage suspicious claims at intake, justify reserves), **SIU investigators** (skip the file slog, land on the leads that matter), **legal teams / defense counsel** (build cross-examination off the record, surface contradictions before deposition), **GCs & law firms** (scale file review without scaling headcount). Today the production deployment is focused on construction workers' compensation claims fraud investigation.
- **MVP today — four capability surfaces:**
  - **FraudX Score** — AI-generated fraud probability per claim with ranked red flags, severity tiers (HIGH / MED / LOW), and the evidence behind each finding. Re-runs automatically as new documents arrive. 20+ investigator-defined red flags configured to the line of business.
  - **Chat with Claims** — plain-language Q&A over the full case file with source-linked answers. *"Like a research assistant who never misses a detail."*
  - **Evidence Package** — source-cited dossier for SIU referral, reservation of rights, or trial prep. Every red flag links to the exact page, line, and timestamp in the source document.
  - **Network Analysis** — pattern-matching across claimants, providers, attorneys, and locations; surfaces organized fraud rings by connecting actors across unrelated claims.
- **How it works (3 steps).** (1) Ingest the entire claim file — any format, any length (medical records, bills, ISO reports, depositions, photos, site reports, recorded statements). (2) Run 20+ fraud checks scoring each claim against an extensible investigator-defined indicator library. (3) Deliver a cited, source-linked dossier defensible from day one.
- **ROI claims.** *EyeLevel internal benchmark; "Actual results vary":* 40× faster claim file review, 10× more files reviewed per day, directional reduction in loss ratio.
- **Customer voice.** Three named customer quotes — Kirk Willis (Willis Law Group), Andriana Vamvakas (Andromeda Advantage), Dan Hickey (Tradesman/Roosevelt Road). Cited at master-brand altitude in `../../master-brand-gtm/references/proof-points.md` § 7 quote bank.
- **Why this exists.** Vertical Outcome Plug-in pattern proof point. Demonstrates the *[Outcome]X* productized productization — repeatable, defined SLA, GroundX-powered.

## 7. ExtractX (Outcome Plug-in)

- **State.** GA.
- **Buyer.** Companies or BPOs (business process outsourcers) who have human teams paired with legacy OCR / templating systems to process invoices and other documents. The pitch is *modernize the OCR-and-human-review pipeline.*
- **MVP today.** Either (a) provide the extracted data **as a service** — Valantor team uses the tool internally on behalf of the client — or (b) **partner to deploy and integrate** GroundX into the customer's existing document-processing workflows.
- **Roadmap next.** Expose ExtractX entirely via the Harness and Studio for rapid implementation, either internally by Valantor or by the customer directly.
- **Why this exists.** Productized data-extraction outcome. Different from `groundx-extraction-workflows` (the contributor-facing skill for authoring extraction workflows): ExtractX is the customer-facing vertical product; `groundx-extraction-workflows` is the developer toolkit.

## 8. ClaimsX, ComplianceX, OpsX, FinanceX, GridX (Outcome Plug-ins — illustrative concepts only)

- **State.** Illustrative marketing concepts. Not shipping.
- **Why named.** They appear in Valantor master-brand materials to demonstrate the *[Outcome]X* productization pattern (claims processing, compliance workflows, operations, finance, energy/grid). They do not have customer-facing implementations today.
- **Do not.** Do not write external content as if these ship. Do not invent customer outcomes for them. Do not claim accuracy numbers, deployments, or pilots. If asked about them, route the conversation to master-brand-altitude framing (Valantor's *vertical-Outcome-Plug-in strategy*) and acknowledge they are illustrative until productized.

## 9. Operational Layer (Valantor agents + human orchestration)

- **State.** Concept. No shipping customer product yet.
- **Buyer.** Companies that just want the outcome (e.g. extracted data) and will pay for the outcome rather than for the tool that produces it. This is the *outcomes-vs-tools* sales path (see `buyer.md` § 2).
- **MVP today.** None today. Valantor has the infrastructure to scale this rapidly when a customer is landed (offshore shops in India and Macedonia capable of doing the human-in-the-loop work).
- **Roadmap next.** Land a customer. Sell against outcomes vs. tools. Ramp up capability as the first engagement defines the operating playbook.
- **Why this exists.** Strategic positioning at the master-brand altitude — the productization of *outcomes-as-a-service* sold against business metrics. Reframes services from low-multiple consulting into managed AI infrastructure with SLAs and long-term contracts. **Do not claim shipping status externally.**

## 10. How to use this file

The catalog above is the answer when a buyer asks:

- *"What is GroundX?"* — § 2 + § 3 (hosted + on-prem are the engine; everything else sits on top).
- *"What is the Studio?"* — § 4 (no-code UI) and § 5 (Harness). Note these are distinct things even though they share the *Studio* name.
- *"What is FraudX / ExtractX?"* — § 6 / § 7.
- *"What other vertical solutions do you offer?"* — § 8 with the explicit illustrative-concept caveat. Do not list them as if they ship.
- *"Can we just pay you to do this for us?"* — § 9 (Operational Layer is the answer in concept; flag that it is not GA and a real engagement is the way to make it real).

For positioning *why* each product exists in a buyer-specific way, see `audiences.md`. For *what to say when a buyer objects*, see `objections.md`. For *which differentiator pillar to lead with per buyer*, see `differentiation.md` § 6.

## 11. What this file does not cover

- **Pricing or contract terms.** Agent-generated content does not quote prices; route to sales.
- **Master-brand-altitude positioning** of Valantor as the Visual Intelligence Company. That defers to `master-brand-gtm` when it exists.
- **Customer outcome citations.** Those live in `proof-points.md`. This file states what products exist; `proof-points.md` cites what customers got from them.
- **Visual or voice register.** `../product-brand-design-standards/` owns those.
