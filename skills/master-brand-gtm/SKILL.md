---
name: master-brand-gtm
description: >
  Use when a request names Valantor and asks for company or category messaging,
  positioning, collateral, a company overview, one-pager, pitch, one-line description,
  investor or board one-pagers,
  Visual Intelligence framing, AI plus
  humans accountability, Outcome Plug-in positioning, executive descriptors, or
  the EyeLevel / GroundX / Valantor brand hierarchy.
---

# Master Brand GTM

First action after this skill loads: use Read to open `../RESPONSE_STYLE.md`, resolved
from the skill base directory. Do this before opening any messaging reference.

Before returning prose to a human, read `../RESPONSE_STYLE.md`. Its base rules apply to
everything you write. Add its external-writing section on top for Valantor or GroundX
collateral.

Immediately before sending, search the complete output for `—`, `–`, and `→`. Replace
every match, including punctuation copied with a quote or source attribution.

For an external artifact, use tools silently. The final answer starts with the
artifact title. Never open with "Here is," "Below is," "All references loaded,"
or another setup/status sentence.

For requests about current customers, partner targets, pipeline, quarterly
goals, contract targets, or internal business strategy, do not infer an answer
from public positioning. State only that the public Harness has no approved
current operating-strategy source and request a current owner-approved source.
Do not discuss connected systems, suggest where the data might live, reconstruct
target classes, or offer to continue. Return exactly two sentences and nothing
before or after them:

> The public Harness has no approved current operating-strategy source for those details.
> Provide a current owner-approved source if you need them.

Use this skill for Valantor company/category framing, investor one-pagers, board
materials, enterprise platform category narrative, Visual Intelligence, AI plus
humans accountability, Outcome Plug-in positioning, master-brand value props,
executive descriptors, and EyeLevel/GroundX/Valantor brand hierarchy questions.
Do not use it for a bare battlecard, one-pager, intro deck, or generic sales
artifact with no master-brand signal. Those default to `product-brand-gtm`.

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
  `references/README.md`. For every external Valantor or GroundX artifact, also
  read `../RESPONSE_STYLE.md`. Neutral explanations use stable narrative without
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
