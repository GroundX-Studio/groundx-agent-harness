---
name: product-brand-gtm
description: >
  Installed-agent GroundX product messaging reference: value propositions,
  differentiators, proof points, buyer framing, objections, product surfaces,
  and the GroundX by Valantor relationship.
---

# Product Brand GTM

Use this skill for GroundX product positioning, value propositions, proof points,
buyer framing, objections, concise product copy, RFP/message review, and public
product/company questions.

## Routing Contract

- **Role:** `reference`.
- **First-entry intents:** GroundX product pitch, one-pager copy, value props,
  differentiators, proof points, objections, buyer framing, product descriptions, and
  product-level messaging review.
- **Deferrals:** Valantor master-brand/category framing routes to `master-brand-gtm`;
  API semantics route to `groundx-api`; extraction workflow authoring routes to
  `groundx-extraction-workflows`; deployment details route to `groundx-on-prem`.
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
