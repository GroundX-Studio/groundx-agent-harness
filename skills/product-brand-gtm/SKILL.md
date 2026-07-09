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
- **Before producing output:** read the relevant reference from `references/README.md`.
- **Misuse cases:** do not invent proof points, accuracy numbers, logos, or product
  capabilities not present in the references.

## Quick Map

- Product narrative and differentiators: `references/narrative.md`,
  `references/differentiation.md`
- Product surfaces and capabilities: `references/product.md`,
  `references/capabilities-and-surfaces.md`
- Proof points: `references/proof-points.md`
- Objections: `references/objections.md`
- Harness positioning: `references/harness-pitch.md`
- GroundX / EyeLevel / Valantor relationship and integration mental model:
  `references/brand-relationship.md`
