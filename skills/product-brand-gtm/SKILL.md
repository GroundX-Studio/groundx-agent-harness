---
name: product-brand-gtm
description: >
  Use when an installed agent needs EyeLevel/GroundX product positioning, document-AI
  one-pagers, value propositions, proof points, buyer framing, a buyer or prospect response,
  objections, bare named-customer case studies, customer stories, customer outcomes,
  product surfaces, RFP/message review, or the EyeLevel / GroundX / Valantor relationship.
  A bare battlecard, one-pager, intro deck, or similar sales artifact defaults
  here unless the request explicitly signals Valantor company/category,
  investor, board, analyst, or Outcome Plug-in work.
---

# Product Brand GTM

First action after this skill loads: use Read to open `../RESPONSE_STYLE.md`, resolved
from the skill base directory. Do this before opening any messaging reference.

For a buyer or prospect response to an objection, comparison, alternative, or stated
constraint, read `references/objections.md` before any other product reference. Let the
buyer's stated signal choose every additional owner.

For every buyer objection, use this sequence:

1. Read `../RESPONSE_STYLE.md`.
2. Read `references/objections.md` and select no more than two lenses from the
   buyer's explicit signals.
3. Invoke only the factual owners required by those lenses.
4. Draft only from the selected lenses. Delete every claim that belongs to an
   unselected lens.

Before returning prose to a human, read `../RESPONSE_STYLE.md`. Its base rules apply to
everything you write. Add its external-writing section on top for Valantor or GroundX
collateral.

Immediately before sending, search the complete output for `—`, `–`, and `→`. Replace
every match, including punctuation copied with a quote or source attribution.
If the response will mention on-premises, air-gapped operation, a customer-controlled
environment, residency, egress, or a data boundary, also invoke `groundx-on-prem` before
drafting and preserve its configuration qualifiers. Do not replace that skill handoff by
opening one of its reference files directly. The entrypoint owns reference selection and
the complete deployment boundary. Do not draft until the `groundx-on-prem` skill invocation
is recorded. If the invocation is unavailable, state only that deployment details need the
deployment owner. Do not improvise the boundary.
Treat speed, time saved, throughput, "in production," and customer adoption as evidence
claims even when they contain no number. Omit them unless an eligible proof record supports
the exact statement and scope.

For an external artifact, use tools silently. The final answer starts with the
artifact title. Never open with "Here is," "Below is," "All references loaded,"
or another setup/status sentence.

Use this skill for EyeLevel + GroundX product positioning, document-AI one-pagers,
value propositions, proof points, buyer framing, objections, concise product copy,
RFP/message review, EyeLevel heritage questions, and public product/company questions.
A bare commercial artifact with no master-brand signal also starts here.

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
  `references/README.md`. For every external Valantor or GroundX artifact, also
  read `../RESPONSE_STYLE.md`. Neutral explanations use stable narrative without
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
  capabilities not present in the references. A requested named-customer case
  study starts with `references/customer-disclosure.md`, then searches only the
  exact name in `references/proof-points.md`. If no approved source exists,
  inspect no private customer material, state only that no approved external
  source is available, and do not reconstruct or characterize the story.

## Quick Map

- Product narrative and differentiators: `references/narrative.md`,
  `references/differentiation.md`
- Compact one-pagers, battlecards, novice explainers, and first-meeting deck
  content: `references/artifact-recipes.md`
- Product surfaces and capabilities: `references/product.md`,
  `references/capabilities-and-surfaces.md`
- Proof points: `references/proof-points.md`
- Named-customer external-use gate: `references/customer-disclosure.md`
- Objections: `references/objections.md`
- Public Agent Harness, private Studio Harness, MCP, and host capability
  attribution: `references/harness-pitch.md`
- GroundX / EyeLevel / Valantor relationship and integration mental model:
  `references/brand-relationship.md`
