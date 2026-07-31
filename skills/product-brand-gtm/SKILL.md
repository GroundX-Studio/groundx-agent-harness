---
name: product-brand-gtm
description: >
  Use when an installed agent needs EyeLevel/GroundX product positioning, document-AI
  one-pagers, value propositions, proof points, buyer framing, objections, product
  surfaces, RFP/message review, or the EyeLevel / GroundX / Valantor relationship.
---

# Product Brand GTM

Use this skill for EyeLevel + GroundX product positioning, document-AI one-pagers,
value propositions, proof points, buyer framing, objections, concise product copy,
RFP/message review, EyeLevel heritage questions, and public product/company questions.

## Routing Contract

- **Role:** `reference`.
- **First-entry intents:** EyeLevel/GroundX product pitch, one-pager copy, value props,
  differentiators, proof points, objections, buyer framing, product descriptions,
  EyeLevel heritage/product-surface questions, and product-level messaging review.
- **Deferrals:** Valantor master-brand/category framing routes to `master-brand-gtm`;
  MCP setup/tool use routes to `groundx-mcp`; REST/SDK API semantics route to
  `groundx-api`; extraction workflow authoring routes to `groundx-extraction-workflows`;
  deployment details route to `groundx-on-prem`.
- **Before producing output:** read the relevant reference from
  `references/README.md`. Neutral explanations use stable narrative without
  unsolicited volatile proof. One-pagers, RFPs, and other evidence-bearing work
  also load `references/proof-points.md` automatically and apply its audience,
  source, qualifier, and freshness rules. Broad objections diagnose from
  `references/objections.md` first; load proof only if the selected answer uses
  customer, benchmark, partner, or quantitative evidence.
- **Mixed company/product jobs:** a mixed Valantor/GroundX explanation, pitch,
  or one-line description loads both `master-brand-gtm` and
  `product-brand-gtm`. Union the references required by every requested output
  shape; master brand owns Valantor and this skill owns GroundX.
- **Insurance claims jobs:** insurance claims, ClaimsX, or FraudX positioning
  loads both messaging skills, then the master-brand product-state and outcome
  playbook owners. Keep generic claims processing separate from
  insurance-fraud investigation.
- **Misuse cases:** do not invent proof points, accuracy numbers, logos, or product
  capabilities not present in the references. If a requested named-customer
  case study has no approved source in `references/proof-points.md`, inspect no
  private customer material, state only that no approved external source is
  available, and do not reconstruct or characterize the story.

## Quick Map

- Product narrative and differentiators: `references/narrative.md`,
  `references/differentiation.md`
- Compact one-pagers, battlecards, novice explainers, and first-meeting deck
  content: `references/artifact-recipes.md`
- Product surfaces and capabilities: `references/product.md`,
  `references/capabilities-and-surfaces.md`
- Proof points: `references/proof-points.md`
- Objections: `references/objections.md`
- Public Agent Harness, private Studio Harness, MCP, and host capability
  attribution: `references/harness-pitch.md`
- GroundX / EyeLevel / Valantor relationship and integration mental model:
  `references/brand-relationship.md`
