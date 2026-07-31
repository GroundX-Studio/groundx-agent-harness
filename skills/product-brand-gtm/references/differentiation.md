# Differentiation: The Five Pillars

GroundX has five differentiator pillars. General pitch order matters, but it
does not override objection diagnosis. For an objection, use
`objections.md`'s buyer-signal map and select only the one or two relevant
lenses. In a broader pitch, pillars 1 and 2 lead for most buyers; pillars 3 and
4 reinforce; pillar 5 addresses implementation-scale pain.

For the master pain context that frames all five pillars, see `buyer.md` § 1.

## 1. Customer-controlled deployment

**The argument.** Customers can run GroundX in their own environment. Supported
options include on-prem, air-gapped, and cloud deployments. Load
`groundx-on-prem` before using these details.

**Why it matters.** Self-hosting is full architecture and operations scope:
Kubernetes packaging, backing services, model serving, storage, upgrades,
observability, and supported air-gap behavior. Compare that scope, using
current facts from `groundx-on-prem`, rather than asserting a universal build
duration or how many competitors can deliver it.

**Proof anchors.** Use `groundx-on-prem` for current deployment facts. For
evidence-bearing work, retrieve any eligible partner or third-party validation
from `proof-points.md`; do not maintain its status here.

## 2. High accuracy on complex documents

**The argument.** GroundX is built for high-accuracy understanding of complex
enterprise documents that break general-purpose AI. For an evidence-bearing
artifact, select the current eligible accuracy, customer, or benchmark claim
from `proof-points.md`.

**Why it is defensible.** GroundX reads page structure before it extracts
information. Tables, forms, diagrams, and text keep their context. Use
`technical-architecture.md` only when the buyer asks for the deeper mechanism.

**Use current approved proof, not comparative-only claims.** Retrieve the
headline and supporting result from `proof-points.md`, including qualifiers and
freshness metadata. Do not maintain the values here.

RAG is one consumption pattern, not the default external label. Use it when the buyer asks about RAG, search, retrieval, grounding, or failed internal RAG projects. Otherwise lead with accurate document understanding, structured extraction, grounded answers, and source-backed workflows.

## 3. Experienced team

**The argument.** The team came out of IBM Research, helped lead IBM Watson's
strategy and formation, did consumer-scale AI at the Weather Company, and built
GroundX from first principles around the documents-for-AI problem.

**Why it matters.** The history supports the team's ability to build and operate
the underlying system. Use the full arc from `narrative.md` § 4 only in longer
formats.

## 4. One integrated system

**The argument.** GroundX combines document reading, storage, and search in one
platform. The buyer has fewer tools and integrations to run.

**Why it matters.** Every separate tool adds another handoff to test, monitor,
and support. One platform reduces that work.

## 5. Faster implementation with the Harness

**The argument.** Buyers can accumulate more AI use cases than their teams can
implement one by one. The Harness is the direct answer for GroundX-touching use
cases: portable GroundX knowledge and workflows help compatible agents stand up
new integrations without rebuilding the same implementation context each time.
Use `harness-pitch.md` to attribute public Agent Harness, private Studio
Harness, MCP, and host-agent capabilities correctly.

**Why it matters.** Teams can reuse GroundX-specific knowledge and workflows
instead of rebuilding the same implementation context for each use case. Do not
present this as an architectural moat.

## 6. How to argue the pillars together

Lead order varies by buyer:

| Buyer signal | Pillar order |
| --- | --- |
| LOB owner / outcome-buyer asking about business metrics | 2, 5, 1, 4, 3. Lead with proof; route to `product.md` § 9 if outcome-paying is in scope. |
| Buyer explicitly raises displacement, job-security, control, or internal-program ownership concerns | Acknowledge the concern. Explain how the Harness can shorten implementation work. Involve the outcome owner without bypassing the technical buyer. Use 5, 1, 4, 2, 3. |
| Regulated industry, on-prem requirement, data sovereignty | 1, 2, 4, 3, 5 |
| Tried RAG and failed, accuracy pain | 2, 4, 3, 1, 5 |
| Large use-case backlog, limited implementation capacity | 5, 2, 1, 4, 3 |
| Long sales cycle, technical due diligence | 3, 2, 4, 1, 5 |
| Generic / no specific signal | 2, 1, 4, 3, 5 |

The pillars do not change. Their order does. Apply the conditional
organizational-risk guidance from `buyer.md` § 1 only when the buyer supplies
that signal. Otherwise treat technical stakeholders as ordinary collaborators
and order the pillars around the stated problem.

## 7. What this differentiation does not claim

- **Price:** this reference makes no cheapest-price claim.
- **Scope:** GroundX is for document-heavy AI work. Other AI work may need a
  different product.
- **Category:** document understanding and RAG already exist. Do not invent a
  new category claim at product altitude.
