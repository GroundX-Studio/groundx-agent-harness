---
name: groundx-architecture
description: >
  Customer-facing source of truth for GroundX architecture facts: pipeline,
  components, trust model, data flow, search, extraction architecture, observability,
  residency, and deployment-invariant system behavior.
---

# GroundX Architecture

Use this skill for architecture-shaped questions about GroundX: how the system works,
pipeline shape, trust model, data residency, observability, data flow, extraction QA,
search, and technical due diligence facts.

## Routing Contract

- **Role:** `reference`.
- **First-entry intents:** "how does GroundX work?", "explain the pipeline", "what is
  the trust model?", "where does data live?", "how does search work?", architecture
  diagrams, technical due diligence, vendor-risk reviews, and data-governance reviews.
- **Deferrals:** deployment runbooks and values.yaml route to `groundx-on-prem`; API
  endpoint behavior routes to `groundx-api`; extraction YAML authoring routes to
  `groundx-extraction-workflows`; pitch language routes to GTM skills.
- **Before producing output:** open the relevant reference for the topic and audience.
- **Misuse cases:** do not invent facts not present in references; do not produce
  deployment runbooks or API docs from this skill.

## Reference Map

Start with `references/README.md`. For end-to-end pipeline questions, read
`references/data-flow.md`. For trust and compliance, read
`references/identity-and-trust.md` and `references/data-residency.md`. For extraction,
read `references/extraction-architecture.md`.
