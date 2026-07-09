# Brand Hierarchy (authoritative)

This file is the **authoritative source** for the Valantor / GroundX / GroundX Studio / Outcome Plug-ins / Operational Layer relationship rules. Other files in this skill, and `../../product-brand-gtm/references/brand-relationship.md`, reference this file rather than restating — to prevent two copies from drifting.

If a rule below disagrees with a statement elsewhere in the harness, this file wins.

## 1. The hierarchy in one line

> **Valantor** (the company) → **GroundX** (the platform) → **GroundX Studio** (the extensibility platform) → **Outcome Plug-ins** (the productized verticals) → **Operational Layer** (Valantor agents + human orchestration).

Plus a parallel: **GroundX Studio Harness** is the agentic adoption layer for any of the above — not a hierarchical layer, but a delivery channel for the GroundX-touching surfaces.

## 1.1 Plain-English mental model

Use this when the user is not asking for investor/category depth and only needs
to understand the names:

| Name | Plain meaning | Use it when... | Do not confuse it with... |
| --- | --- | --- | --- |
| **Valantor** | The company and master brand. | Company, category, investor, Visual Intelligence, AI + humans accountability, or Outcome Plug-in strategy. | GroundX the platform or EyeLevel the heritage brand. |
| **GroundX** | The platform layer. | Product mechanism, document intelligence, ingest, search, RAG, workflows, extraction substrate, APIs, SDKs, MCP, or deployment. | The company. Externally, introduce it as GroundX by Valantor. |
| **EyeLevel** | The acquired-company / heritage brand that built GroundX before Valantor acquired the work. | Origin story, team heritage, or EyeLevel-pack product surfaces. | The platform. Never say EyeLevel by Valantor. |
| **GroundX MCP** | The preferred connected-agent path for using GroundX tools. | An installed agent has MCP tools connected and needs to operate GroundX. | REST/SDK endpoint semantics, which belong to `groundx-api`. |
| **GroundX Studio Harness** | The agent knowledge and workflow layer. | Agents need GroundX-specific skills, references, patterns, and medium guidance. | The only way to integrate GroundX. |

Keep simple relationship answers simple. Do not expand into a full investor,
category, or Outcome Plug-in narrative unless the user asks for that altitude.

## 2. Valantor — master brand

- **Role:** the enterprise Visual Intelligence operating company.
- **Tagline:** *Valantor is the Visual Intelligence Company.*
- **What Valantor means** (master-brand attributes):
  - Assured intelligence, not probabilistic AI.
  - Safe, operational AI inside real enterprises.
  - AI + human accountability.
  - Long-term infrastructure partner, not a tool vendor.
- **Brand promise:** Valantor makes Visual Intelligence trusted, operational, and outcome-driven inside the world's most complex enterprises.
- **External rendering:** simply *Valantor* when referring to the company. Use *Valantor's GroundX*, *Valantor's Outcome Plug-ins*, etc. when describing what Valantor offers — never *Valantor by [other]*.
- **Do not say:** *"Valantor uses GroundX-like technology"* (Valantor *operates* GroundX; it is not technology-adjacent). *"EyeLevel by Valantor"* (wrong construction — see § 3 and § 4).

## 3. GroundX — platform layer

- **Role:** the Visual Intelligence platform that converts raw visual data into trusted, structured, model-ready intelligence. The technical legitimacy behind Valantor's master-brand claims.
- **External rendering:** *GroundX by Valantor* when introducing the platform externally.
- **Internal / product framing:** *GroundX is the platform, not the company.*
- **Hard rule:** **GroundX is never optional.** Every Valantor module, agent, workflow, plug-in, and Outcome runs on GroundX.
- **State:** GA. Two sibling distributions — Hosted GroundX (SaaS) and GroundX On-Prem (Helm-deployable self-hostable, air-gapped capable). See `product.md` for state detail.
- **Do not say:** *"GroundX is the company"*; *"Valantor's GroundX product"* (slightly awkward — prefer *"the GroundX platform"* or *"GroundX by Valantor"*).

## 4. EyeLevel — heritage / acquired company

- **Role:** the company that built GroundX before Valantor acquired the work. Now the heritage / origin-story brand and the lockup co-sign on EyeLevel-pack product surfaces.
- **External rendering:** *EyeLevel — A Valantor Company* (matches the EyeLevel logo lockup PNG, which bakes the co-sign in). Use when describing the team's heritage (IBM Research, Watson, Weather Company, 2019 spinout).
- **Do not say:** *"EyeLevel by Valantor"* (wrong construction). Do not re-typeset the *A VALANTOR COMPANY* co-sign as separate text adjacent to the EyeLevel mark; it is part of the lockup asset (see `../../product-brand-design-standards/references/logos.md`).

## 5. GroundX Studio — extensibility platform

- **Role:** the native toolset for building, sharing, and deploying custom plug-ins that extend GroundX with new skills, agents, and hooks. Works inside Claude Cowork, ChatGPT Enterprise, Gemini, and other agent surfaces.
- **Plug-in categories:**
  - **Document Plug-ins** — extend GroundX with document-archetype-specific intelligence (invoice, policy, claim form, medical record).
  - **Function Plug-ins** — extend GroundX with capability-specific operations (extract, classify, summarize, report, compare, validate). Modular and composable.
- **Plug-in types** (apply across both categories): **Skills** (discrete reusable capabilities), **Agents** (autonomous multi-step operators), **Hooks** (event-driven triggers at defined workflow points).
- **Sharing rule:** every Studio plug-in is shareable across projects, teams, and other plug-ins, including Outcome Plug-ins.
- **Key discipline:** Studio plug-ins are **building blocks**, never outcomes. Outcome Plug-ins (§ 6) are how blocks compose into productized outcomes.
- **State:** the no-code single UI is in development (Replit-built prototype today; rebuild via the Harness is the path forward). The plug-in / extensibility model is the product description.
- **Note on naming overlap:** *GroundX Studio* names both the no-code single UI (the product surface) and the extensibility platform (the plug-in model). Context disambiguates. When distinguishing matters, use *the GroundX Studio UI* vs. *GroundX Studio's plug-in model* explicitly.

## 6. Outcome Plug-ins — productized verticals

- **Role:** Valantor-operated, GroundX-powered vertical solutions. The industrialization layer where Studio plug-ins compose into repeatable, enterprise-grade outcomes.
- **Naming convention:** **[Outcome]X**.
- **State as of 2026-05-14:**
  - **Shipping (GA):** **FraudX**, **ExtractX**. See `product.md` § 6–7 and `outcome-playbooks.md` for buyer / MVP / roadmap detail.
  - **Illustrative marketing concepts (not shipping):** ClaimsX, ComplianceX, OpsX, FinanceX, GridX. They demonstrate the *[Outcome]X* productization pattern in master-brand materials and analyst briefings. **Do not claim them as products in external content.** Do not invent customer outcomes for them.
- **Key discipline:**
  - Outcome Plug-ins are **not** companies.
  - Outcome Plug-ins are **not** bespoke projects — they are repeatable products with defined inputs, outputs, and SLAs.
  - Every Outcome Plug-in is powered by GroundX.
- **Positioning examples (shipping products only):**
  - *FraudX is an insurance-specific Outcome Plug-in built on GroundX that automates fraud detection with speed, accuracy, and auditability enterprises can trust.*
  - *ExtractX is the GA Outcome Plug-in for companies and BPOs replacing legacy OCR / templating systems for invoice and document processing.*

## 7. Operational Layer — Valantor agents + human-in-the-loop

- **State as of 2026-05-14: concept — no shipping customer product yet.** Valantor has offshore infrastructure (shops in India and Macedonia) capable of scaling once a customer is landed.
- **Intended role:** convert Visual Intelligence into real enterprise outcomes. Agents orchestrated on top of GroundX, Studio plug-ins, and Outcome Plug-ins, paired with human-in-the-loop oversight.
- **Three intended human roles:** enterprise industrialization, outcome accountability, enterprise-wide AI adoption.
- **Strategic frame:** *AI + humans accountability* — reframes services from low-multiple consulting into managed AI infrastructure with SLAs and long-term contracts. See `ai-and-humans.md`.
- **Do not claim shipping status externally.** Investor narrative can articulate the strategic posture; customer-facing surfaces cannot claim the Operational Layer is GA.

## 8. GroundX Studio Harness — agentic adoption channel

- **State:** alpha. The skill substrate (this harness) is currently the most modern way to consume GroundX into agent-led workflows.
- **Role:** drops GroundX-implementation time from months to days for any agent (Claude, Gemini, ChatGPT, Cursor, Replit, openclaw, smolagents, or any agent framework) by giving the agent deep, structured knowledge of GroundX, the brand, and the operating rules.
- **Not a hierarchical layer.** The Harness sits alongside the stack as a delivery channel — applicable to GroundX, Studio, Outcome Plug-ins, and (in time) Operational Layer surfaces. It is the productization of the *implementation-scale pain* answer (see `../../product-brand-gtm/references/differentiation.md` § 5).

## 9. Naming rule summary

| Say externally | Do not say |
| --- | --- |
| Valantor is the Visual Intelligence Company | Valantor uses GroundX-like technology |
| GroundX by Valantor | EyeLevel by Valantor |
| GroundX is the platform | GroundX is the company |
| EyeLevel — A Valantor Company (lockup) | A separately-typed "A VALANTOR COMPANY" tagline next to the logo |
| FraudX, ExtractX (the GA Outcome Plug-ins) | ClaimsX / ComplianceX / OpsX / FinanceX / GridX as if they ship today |
| Operational Layer (strategic posture) | Operational Layer as a GA product |
| Document Plug-ins, Function Plug-ins | Studio plug-ins as outcomes |
| The GroundX Studio Harness | A custom integration framework (the Harness is the productized version) |

## 10. Altitude routing

| The conversation is at... | Owner |
| --- | --- |
| Master-brand altitude (Valantor company, category, investor, board, AI+humans, Outcome Plug-in strategy) | This skill |
| Product altitude (GroundX product pitch, customer outcomes at product level, sales motion) | `../../product-brand-gtm/` |
| Visual decisions (palette, type, logo, layout) — Valantor pack | `../../master-brand-design-standards/` |
| Visual decisions — EyeLevel pack | `../../product-brand-design-standards/` |
| Implementation (web UI, slides, code, API) | The relevant medium skill |
