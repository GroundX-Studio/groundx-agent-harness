---
name: master-brand-gtm
description: >
  Use when an installed agent needs Valantor master-brand or company/category
  messaging, investor or board one-pagers, Visual Intelligence framing, AI plus
  humans accountability, Outcome Plug-in positioning, executive descriptors, or
  the EyeLevel / GroundX / Valantor brand hierarchy.
---

# Master Brand GTM

Use this skill for Valantor company/category framing, investor one-pagers, board
materials, enterprise platform category narrative, Visual Intelligence, AI plus
humans accountability, Outcome Plug-in positioning, master-brand value props,
executive descriptors, and EyeLevel/GroundX/Valantor brand hierarchy questions.

## Routing Contract

- **Role:** `reference`.
- **First-entry intents:** Valantor company positioning, investor or board
  one-pagers, enterprise platform category narrative, Visual Intelligence,
  executive/company descriptors, AI plus humans accountability, Outcome Plug-in
  positioning, EyeLevel/GroundX/Valantor brand hierarchy, and master-brand questions.
- **Deferrals:** GroundX product-level positioning routes to `product-brand-gtm`;
  connected-agent MCP setup/tool use routes to `groundx-mcp`; REST/SDK API semantics
  route to `groundx-api`; deployment routes to `groundx-on-prem`.
- **Before producing output:** read the relevant reference from
  `references/README.md`. Neutral explanations use stable narrative without
  unsolicited volatile proof. Investor, board, RFP, one-pager, objection, and
  other evidence-bearing work also loads `references/proof-points.md`
  automatically and applies its audience, source, qualifier, and freshness
  rules.
- **Mixed company/product jobs:** a mixed Valantor/GroundX explanation, pitch,
  or one-line description loads both `master-brand-gtm` and
  `product-brand-gtm`. This skill owns Valantor/company meaning; product brand
  owns GroundX/platform meaning.
- **Insurance claims jobs:** insurance claims, ClaimsX, or FraudX positioning
  loads both messaging owners plus this skill's product-state and outcome
  playbook references. Never present FraudX evidence as generic
  claims-processing proof.
- **Misuse cases:** do not claim illustrative products are shipping; do not invent
  customer outcomes or proof points.

## Quick Map

- Short company descriptor: `references/elevator.md`
- Category narrative: `references/narrative.md`,
  `references/visual-intelligence.md`
- Investor or board narrative: `references/investor-narrative.md`,
  `references/ai-and-humans.md`
- AI plus humans: `references/ai-and-humans.md`
- Outcome Plug-in positioning: `references/outcome-playbooks.md`,
  `references/product.md`
- Brand hierarchy and GroundX / EyeLevel / Valantor mental model:
  `references/brand-hierarchy.md`
- Proof points: `references/proof-points.md`
