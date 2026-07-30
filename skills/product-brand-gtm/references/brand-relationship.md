# Brand Relationship: EyeLevel ↔ GroundX ↔ Valantor

How EyeLevel, GroundX, GroundX Studio, and Valantor relate as brands and what to say (and not say) about each. The authoritative source for master-brand altitude rules is now `../../master-brand-gtm/references/brand-hierarchy.md`. This file restates the rules at product-altitude framing for `product-brand-gtm` use; when rules disagree, the `master-brand-gtm` version wins.

For visual logo and lockup rules, see `../product-brand-design-standards/references/logos.md`.

## 1. The hierarchy in one line

> **Valantor** (the company) → **GroundX** (the platform) → **GroundX Studio** (the extensibility platform) → **Outcome Plug-ins** (the productized verticals) → **Operational Layer** (Valantor agents + human orchestration).

## 1.1 Plain-English mental model for agents

Use this when a user is trying to make sense of the names or decide which
GroundX path an agent should use:

| Name | Plain meaning | Use it when... | Do not confuse it with... |
| --- | --- | --- | --- |
| **Valantor** | The company and master brand. | The topic is company, category, investor, Visual Intelligence, AI + humans, or Outcome Plug-in strategy. | GroundX the platform, or EyeLevel the heritage brand. |
| **GroundX** | The platform layer. | The topic is document understanding, ingest, search, RAG, workflows, extraction substrate, buckets, groups, API, SDK, MCP, or on-prem deployment. | The company. Say "GroundX by Valantor" externally. |
| **EyeLevel** | The acquired-company / heritage brand that built GroundX before Valantor acquired the work. | The topic is the team's history, origin story, logo lockup, or EyeLevel-pack product surfaces. | The platform. Never say "EyeLevel by Valantor." |
| **GroundX MCP** | The preferred connected-agent path for using GroundX tools. | An installed agent has MCP tools connected and needs to ingest, poll, search, list, or discover operations. | REST/SDK endpoint semantics, which belong to `groundx-api`. |
| **REST APIs / SDKs** | Direct integration surfaces for application code and fallback. | The topic is backend integration, dev environment behavior, endpoint shapes, SDK objects, local-file upload gaps, or MCP fallback. | MCP setup and tool-use instructions. |
| **GroundX Agent Harness** | The public GroundX knowledge and workflow bundle. | A public or customer agent needs portable GroundX guidance. | GroundX Studio Harness, MCP execution, or capabilities supplied by the host client. |
| **GroundX Studio Harness** | The private expanded GroundX knowledge and workflow bundle with prebuilt Studio workflows. | Ready-made Studio production, authoring, publishing, administration, or operational workflows are in scope. | The public Agent Harness, the underlying On-Prem workspace service, or the only way to integrate GroundX. |
| **GroundX On-Prem** | A deployment distribution of GroundX for customer-controlled infrastructure, including the workspace service where configured. | The topic is deployment mode, Kubernetes, Helm, values.yaml, workspace-service operation, private cloud, air-gapped, residency, or operations. | Private Studio Harness workflow skills or runtime workflow model assignment, which belongs to `groundx-api`. |

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
- **Current state:** use `product.md` as the sole lifecycle and promise owner.
  It distinguishes shipping Outcome Plug-ins from illustrative concepts and
  records when that decision must be rechecked.
- **Key discipline:**
  - Outcome Plug-ins are **not** companies.
  - Outcome Plug-ins are **not** bespoke projects — they are repeatable products with defined inputs, outputs, and SLAs.
  - Every Outcome Plug-in is powered by GroundX.
- **Positioning examples:** use only when `product.md` currently permits the
  named product claim.
  - *FraudX is an insurance-specific Outcome Plug-in built on GroundX that helps investigation teams detect, examine, and document fraud with source-linked evidence.* Use `product.md` for the current capability boundary and `proof-points.md` for eligible quantitative proof.
  - *ExtractX is a document-operations Outcome Plug-in for organizations replacing legacy OCR and templating workflows.* Use `product.md` for current lifecycle and delivery boundaries.
- **Master-brand altitude:** Outcome Plug-in marketing and vertical-thesis
  articulation defers to `master-brand-gtm`. `product.md` remains the lifecycle
  and promise owner.

## 7. Operational Layer (Valantor agents + human orchestration)

- **State:** use `product.md` for lifecycle, promise boundary, freshness, and
  recheck trigger. The Operational Layer is the intended productization of
  *outcomes-as-a-service* sold against business metrics rather than AI tooling.
- **Intended role:** where Valantor converts Visual Intelligence into real enterprise outcomes. Agents orchestrated on top of GroundX, Studio plug-ins, and Outcome Plug-ins, paired with human-in-the-loop oversight.
- **Three roles humans are intended to play:** enterprise industrialization, outcome accountability, enterprise-wide AI adoption.
- **Master-brand altitude:** the "AI + humans accountability" investor narrative defers to `master-brand-gtm`. This file mentions the operational layer only to keep the hierarchy complete.
- **Do not infer availability from strategy language.** Apply the current
  promise boundary in `product.md`.

## 8. Naming rule summary

| Say externally | Do not say |
| --- | --- |
| GroundX by Valantor | EyeLevel by Valantor |
| GroundX is the platform | GroundX is the company |
| Valantor is the Visual Intelligence Company | Valantor uses GroundX-like technology |
| EyeLevel — A Valantor Company (on lockup) | A separately-typed "A VALANTOR COMPANY" tagline next to the logo |
| Extract / Interact / Report (Studio use cases) | Other invented names for the three use cases |
| Approved external vision-model description from `technical-architecture.md`; current training-corpus value only from `proof-points.md` | The underlying open-source architecture name |
| Outcome Plug-ins are repeatable products | Outcome Plug-ins are services / consulting engagements |
| Outcome Plug-ins whose current state in `product.md` permits external use | An illustrative name as if it were an available product |

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
