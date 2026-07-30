# Buyer: Sweet Spot vs. Broader Universe

The buyer universe is broad — anyone with substantial document understanding or RAG needs is in scope. Inside that universe there is a distinct ideal-customer profile (ICP) where the pitch lands sharpest and conversion is highest.

Do not write language that excludes the broader buyer base. *"This is for [archetype]"* and *"Not X, specifically Y"* phrasings collapse ICP into buyer universe. Use *"the sweet spot is..."*, *"we win obviously when..."*, *"most interested are..."* instead.

## 1. Conditional organizational-risk signal

Do not assume that an IT or engineering buyer fears job loss, protects an
internal program for political reasons, or is hostile to an outside vendor.
Default to treating technical teams as legitimate collaborators and buyers.

Apply organizational-risk framing only when the buyer explicitly signals one
or more of these concerns:

- a vendor may replace the team or reduce its role;
- an internal program's ownership or standing is at risk;
- job security, control, or organizational politics will affect the decision.

When a signal is present, acknowledge it without diagnosing motives. Position
GroundX and the Harness as force multipliers, clarify decision ownership, and
connect the technical buyer with the line-of-business sponsor when that sponsor
owns the business outcome or budget. Do not bypass a technical stakeholder
merely because of their role.

Separately, many buyers are tired of generic AI claims. Ground the pitch in the
specific document problem, desired outcome, and evidence appropriate to the
communication job.

## 2. The implementation-scale pain (master context)

A recurring buyer concern frames why every differentiator matters at enterprise scale:

> *"I have a growing AI use-case backlog. How am I going to implement it?"*

At scale, anything less than enterprise-grade accuracy, deployment flexibility,
integrated architecture, and a productive implementation pattern fails the
math. The Harness adoption pattern addresses implementation velocity; use
`harness-pitch.md` to distinguish the public Agent Harness from the private
Studio Harness, optional MCP execution, and host-client capabilities. The other
pillars address the per-use-case quality and deployment bar.

### 2.1 The two volume problems

Do not flatten every buyer pain into "too many documents." GroundX answers two
related but different volume problems:

- **Knowledge volume:** the enterprise has too much visually complex knowledge
  for people or general-purpose AI to reliably find, understand, and cite. This
  maps to grounded answers, source-backed reports, RAG, technical support,
  policy lookup, and customer-service assistants.
- **Transactional document volume:** the enterprise has too many recurring
  document-driven tasks to review one by one. This maps to extraction,
  classification, claim-file review, evidence packages, and operational
  workflows where consistency and throughput matter.

For short copy, pick the one the buyer is actually describing. For broader
strategy or investor context, show both: GroundX turns visually complex knowledge
into reliable intelligence and turns high-volume document transactions into
repeatable operational workflows.

## 3. The ideal-customer profile

The ICP is teams that have already tried RAG or LLM use cases on unstructured documents and run into the limits. They tend to have:

- **Volume** — a corpus large enough that manual review or fragile
  per-document handling no longer scales.
- **Visual complexity** — graphics, tables, schematics, decision trees, scanned content, handwritten notes, multi-column layouts.
- **A regulated context, a data-sensitivity concern, or both** — they cannot or will not feed their corpus to a vendor that trains on or could leak it.

ICP pitch shape: *"You tried, it didn't work, here's why, here's the system actually built for this."*

## 4. The broader buyer universe

Anyone with substantial document understanding or RAG needs — including teams who haven't tried yet, teams in less-regulated industries, teams with simpler document mixes. The product still serves them; the pitch shape just softens.

Broader-universe pitch shape: lead with capability, accuracy, and on-prem optionality. Failure-recovery framing is too sharp for buyers who haven't experienced the failure.

## 5. Pitch shape selector

| Signal in the conversation | Use this pitch shape |
| --- | --- |
| User is an LOB owner asking about business outcomes (cost, resolution rate, margin) | **Outcome-buyer** / lead with proof points and the Operational Layer concept (see `product.md` § 9) |
| User explicitly raises displacement, job-security, control, or internal-program ownership concerns | Acknowledge the stated concern, position GroundX as a force multiplier, and involve the LOB sponsor when that person owns the outcome or budget |
| User mentions tried-and-failed RAG, hallucinations, brittle parsing, frustrating accuracy | ICP / sharp |
| User mentions on-prem requirement, air-gapped, data sovereignty, regulated industry | ICP-adjacent / lead with on-prem |
| User mentions hundreds of AI use cases, agent fatigue, can't keep up with use case backlog | Master-context pain / lead with Harness |
| User is exploring AI capabilities generally, no specific failure named, no buyer signal yet | Broader universe / lead with capability and accuracy |
| User is at master-brand altitude (category, investor, board, AI+humans accountability) | Defer to `master-brand-gtm` |

## 6. Audience-cut overlay

Within any pitch shape, the buyer persona shifts emphasis. See `audiences.md`
for the LOB / CIO / VP Eng / Data Lead / Procurement / Investor cuts. Prefer
the person who owns the outcome and budget; do not rank an LOB buyer above a
technical buyer based on assumed motives. Persona-axis is secondary to
message-axis (this file and the differentiator/proof files), but the right
persona makes or breaks the pitch.
