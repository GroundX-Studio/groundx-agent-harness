---
name: master-brand-gtm
description: >
  Customer-facing Valantor company and category messaging reference: Visual
  Intelligence, AI plus humans accountability, company value props, category
  framing, and brand hierarchy.
---

# Master Brand GTM

Use this skill for Valantor company/category framing, Visual Intelligence, AI plus
humans accountability, master-brand value props, executive descriptors, and brand
hierarchy questions.

## Routing Contract

- **Role:** `reference`.
- **First-entry intents:** Valantor company positioning, category narrative, Visual
  Intelligence, executive/company descriptors, AI plus humans accountability, brand
  hierarchy, and master-brand questions.
- **Deferrals:** GroundX product-level positioning routes to `product-brand-gtm`; API
  semantics route to `groundx-api`; deployment routes to `groundx-on-prem`.
- **Before producing output:** read the relevant reference from `references/README.md`.
- **Misuse cases:** do not claim illustrative products are shipping; do not invent
  customer outcomes or proof points.

## Quick Map

- Short company descriptor: `references/elevator.md`
- Category narrative: `references/narrative.md`,
  `references/visual-intelligence.md`
- AI plus humans: `references/ai-and-humans.md`
- Brand hierarchy: `references/brand-hierarchy.md`
- Proof points: `references/proof-points.md`
