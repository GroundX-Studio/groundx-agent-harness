# Brand Relationship: EyeLevel ↔ GroundX ↔ Valantor

How EyeLevel, GroundX, GroundX Studio, and Valantor relate as brands and what to say (and not say) about each. The authoritative source for master-brand altitude rules is now `../../master-brand-gtm/references/brand-hierarchy.md`. This file restates the rules at product-altitude framing for `product-brand-gtm` use; when rules disagree, the `master-brand-gtm` version wins.

For visual logo and lockup rules, see `../product-brand-design-standards/references/logos.md`.

## 1. The hierarchy in one line

> **Valantor** (the company) → **GroundX** (the platform) → **GroundX Studio** (the extensibility platform) → **Outcome Plug-ins** (the productized verticals) → **Operational Layer** (Valantor agents + human orchestration).

## 2. Valantor (master brand)

- **Role:** the enterprise Visual Intelligence operating company. The master brand. What investors value and what enterprises sign multi-year contracts with.
- **Tagline:** *Valantor is the Visual Intelligence Company.*
- **What to say externally:** Valantor when the conversation is at master-brand altitude (category, investor, board, AI+humans accountability, Outcome Plug-in strategy). Defer to `master-brand-gtm` for full master-brand messaging.
- **What not to say:** *"EyeLevel by Valantor."* That construction is wrong. See § 3.

## 3. GroundX (platform layer)

- **Role:** the Visual Intelligence platform that converts raw visual data into trusted, structured, model-ready intelligence. The technical legitimacy behind the master-brand claims.
- **External rendering:** *"GroundX by Valantor."*
- **Internal/product framing:** *"GroundX is the platform, not the company."*
- **Hard rule:** **GroundX is never optional.** Every Valantor module, agent, workflow, and Outcome Plug-in runs on GroundX.
- **What to say externally:** *"GroundX is the platform layer for Visual Intelligence."* *"GroundX by Valantor."*
- **What not to say:** *"GroundX, the company."* *"EyeLevel by Valantor."* *"Valantor uses GroundX-like technology."*

## 4. EyeLevel (acquired company / technology heritage)

- **Role:** the company that built GroundX before Valantor acquired the work. Now the heritage / origin-story brand and the lockup co-sign.
- **Where EyeLevel appears:** on the lockup as the visible mark, with *"A VALANTOR COMPANY"* baked into the PNG asset. This is governed by `../product-brand-design-standards/references/logos.md`.
- **What to say externally:** *"EyeLevel — A Valantor Company."* Use when describing the team's heritage (Watson, Weather Company, 2019 spinout — see `narrative.md` § 4).
- **What not to say:** *"EyeLevel by Valantor"* (wrong construction — see § 3). Do not re-typeset the "A VALANTOR COMPANY" co-sign as separate text; it is part of the lockup asset.

## 5. GroundX Studio (extensibility platform)

- **Role:** the native toolset that works inside Claude Cowork, ChatGPT Enterprise, Gemini, and other agent surfaces. Lets teams build, share, and deploy custom plug-ins that extend GroundX with new skills, agents, and hooks.
- **Plug-in categories:**
  - **Document Plug-ins** — extend GroundX with document-archetype-specific intelligence (invoice, policy, claim form, medical record). Built from skills, agents, and hooks tuned to the archetype.
  - **Function Plug-ins** — extend GroundX with capability-specific operations (extract, classify, summarize, report, compare, validate). Modular and composable.
- **Plug-in types** (apply across both categories): **Skills** (discrete reusable capabilities), **Agents** (autonomous multi-step operators), **Hooks** (event-driven triggers at defined workflow points). Every Studio plug-in is shareable across projects, teams, and other plug-ins.
- **Key discipline:** Studio plug-ins are **building blocks**, never outcomes. Outcome Plug-ins (§ 6) are how blocks compose into productized outcomes.
- **GroundX Studio as a single UI** (separate concept — same brand): the no-code product surface with Extract, Interact, and Report use cases. See `capabilities-and-surfaces.md` § 2.2 for the consumption-surface framing.

## 6. Outcome Plug-ins

- **Role:** Valantor-operated, GroundX-powered vertical solutions. The industrialization layer where Studio plug-ins compose into repeatable, enterprise-grade outcomes.
- **Naming convention:** **[Outcome]X**.
- **State as of 2026-05-14:**
  - **Shipping (GA):** **FraudX**, **ExtractX**.
  - **Illustrative marketing concepts (not shipping):** ClaimsX, ComplianceX, OpsX, FinanceX, GridX. These names appear in master-brand materials to demonstrate the *[Outcome]X* productization pattern; they do not have current customer-facing implementations. **Do not claim them as products in external content.** Do not invent customer outcomes for them.
- **Key discipline:**
  - Outcome Plug-ins are **not** companies.
  - Outcome Plug-ins are **not** bespoke projects — they are repeatable products with defined inputs, outputs, and SLAs.
  - Every Outcome Plug-in is powered by GroundX.
- **Positioning examples (shipping products only):**
  - *FraudX is an insurance-specific Outcome Plug-in built on GroundX that automates fraud detection with speed, accuracy, and auditability enterprises can trust.* Buyer: fraud investigation teams (notably construction workers' compensation claims investigation). Current sales framing: four product surfaces (FraudX Score, Chat with Claims, Evidence Package, Network Analysis) and 20+ investigator-defined fraud checks with source-linked dossiers. Older smart-report implementation notes belong in architecture context, not external sales headlines.
  - *ExtractX is the GA Outcome Plug-in for companies and BPOs replacing legacy OCR / templating systems for invoice and other document processing.* Buyer: organizations with human teams paired to legacy OCR/templating stacks. MVP today is delivered either as a service (Valantor team runs the tool on behalf of the client) or as a partnership deployment integrating GroundX into existing document-processing workflows. Roadmap: expose entirely via Harness and Studio for rapid customer-led implementation.
- **Master-brand altitude:** Outcome Plug-in marketing and vertical-thesis articulation (including the illustrative-concept plug-ins as category demonstrations) defers to `master-brand-gtm`. This skill mentions Outcome Plug-ins only when product context demands it; when it does, the shipping/illustrative distinction is preserved.

## 7. Operational Layer (Valantor agents + human orchestration)

- **State as of 2026-05-14: concept — no shipping customer product yet.** Valantor has the offshore infrastructure (shops in India and Macedonia) capable of scaling once a customer is landed. The Operational Layer is the intended productization of *outcomes-as-a-service* sold against business metrics rather than against AI tooling.
- **Intended role:** where Valantor converts Visual Intelligence into real enterprise outcomes. Agents orchestrated on top of GroundX, Studio plug-ins, and Outcome Plug-ins, paired with human-in-the-loop oversight.
- **Three roles humans are intended to play:** enterprise industrialization, outcome accountability, enterprise-wide AI adoption.
- **Master-brand altitude:** the "AI + humans accountability" investor narrative defers to `master-brand-gtm`. This file mentions the operational layer only to keep the hierarchy complete.
- **Do not claim shipping status externally.** Operational Layer messaging stays aspirational until the first customer is landed.

## 8. Naming rule summary

| Say externally | Do not say |
| --- | --- |
| GroundX by Valantor | EyeLevel by Valantor |
| GroundX is the platform | GroundX is the company |
| Valantor is the Visual Intelligence Company | Valantor uses GroundX-like technology |
| EyeLevel — A Valantor Company (on lockup) | A separately-typed "A VALANTOR COMPANY" tagline next to the logo |
| Extract / Interact / Report (Studio use cases) | Other invented names for the three use cases |
| Fine-tuned vision model trained on 1M+ pages of enterprise documents | The underlying open-source architecture name |
| Outcome Plug-ins are repeatable products | Outcome Plug-ins are services / consulting engagements |
| FraudX and ExtractX (the GA Outcome Plug-ins) | ClaimsX / ComplianceX / OpsX / FinanceX / GridX as if they ship today (they are illustrative concepts) |

## 9. Altitude routing

| The conversation is at... | Owner |
| --- | --- |
| GroundX product, GroundX Studio extensibility, Studio UI, customer outcomes, sales pitch | `product-brand-gtm` (this skill) |
| Visual Intelligence as a category, AI+humans accountability, Outcome Plug-in vertical strategy, investor narrative, Valantor brand promise | `master-brand-gtm` |
| Visual design, logos, palette, typography, voice register | `product-brand-design-standards` (product altitude) or `master-brand-design-standards` (master-brand altitude) |

## 10. What this file does not own

- The visual lockup and logo rules — see `../product-brand-design-standards/references/logos.md`.
- The master-brand category narrative — defer to `master-brand-gtm`.
- The Valantor visual system (Jim Anderson's brand) — lives in `master-brand-design-standards`.
