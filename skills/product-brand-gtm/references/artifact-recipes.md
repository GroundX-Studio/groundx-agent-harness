# Compact Buyer Artifact Recipes

Use these recipes after selecting the audience, message axis, and eligible
proof. They constrain shape and source discipline; they do not supply new
claims.

Before drafting any external artifact, read `../../RESPONSE_STYLE.md`. Write for
a busy reader. Use succinct, plain English. Make every word count.

## 1. Retrieval rule for mixed jobs

Treat every requested output shape as part of one job and **union** its required
references. A prompt that asks for an explanation, a pitch, and a one-line
description therefore loads the neutral narrative and relationship owners plus
the differentiation and proof owners required by the pitch. Loading proof is a
grounding step; a novice answer may omit the proof when it would add noise.

For a mixed Valantor/GroundX request, load both `master-brand-gtm` and
`product-brand-gtm`:

- master brand owns Valantor as the company;
- product brand owns GroundX as the platform; and
- external product naming is *GroundX by Valantor*.

Do not let either owner summarize the other from memory.

## 2. Novice explainer

Use this order:

1. **Valantor:** what the company does, in one plain sentence.
2. **GroundX:** what the platform does, in one plain sentence.
3. **Relationship:** Valantor is the company; GroundX is the platform it uses
   to power products and customer outcomes.
4. **60-second pitch:** problem, GroundX approach, buyer value, and next step.
5. **One line:** include both company and platform when the user asked about
   both.

Novice mode:

- use plain analogies before mechanism names;
- define any necessary technical term in the same sentence;
- omit Helm, hybrid search, model architecture, RAG, and brand heritage unless
  they answer the question; and
- preserve approved uncertainty. Do not replace "designed to" with "always" or
  "reads like a human";
- never translate "assured," "accountable for," or "outcome-oriented" into a
  guarantee; and
- use ordinary words first: company, software, difficult documents, and usable
  information. Introduce one branded category term only after the plain
  explanation.

## 3. One-pager copy

Target **at most 500 visible words**:

- one audience and one stated audience assumption when the user did not name
  one;
- one problem and one outcome-oriented proposition;
- three compact value/differentiator blocks;
- one proof block using only eligible records;
- one CTA.

Each block should make one point. Remove any sentence that repeats the heading or
the prior block. Do not append a second CTA, a process note, or an unasked offer.

Visible-word count includes headings, body copy, proof qualifiers, source notes,
and the CTA. Report the count during validation. Load `sales-motion.md` for a
persona-appropriate CTA.

Keep source and last-verified metadata in a compact source note when adjacent
metadata would make the buyer copy unreadable. A one-pager without an output
medium is a copy-ready Markdown artifact, not a rendered PDF. If the user asks
for a designed or send-ready PDF, route to the slide/PDF producer available in
the installed environment.

Do not volunteer financial, traction, adoption, usage, or customer-count figures
in a generic external artifact. These figures rot quickly. Use one only when the
user explicitly asks for that class of evidence and provides a current approved
source for the communication job.

## 4. Battlecard

The explicit artifact noun controls the recipe: in "one-page battlecard,"
"battlecard" selects this structure and "one-page" sets the size limit.

Target **at most 500 visible words**:

- top value proposition in two or three short bullets;
- exactly three differentiators;
- four or five objections;
- each spoken objection response at most **35 words**; and
- discovery cues only when the user asks for them.

Write value propositions as direct buyer outcomes. Write each differentiator as
one claim and one short explanation. Write objection responses so they sound
natural when spoken. Answer the objection before naming the mechanism. Do not
append a generic CTA, process note, or unasked offer.
Write the exact words the salesperson should say. Do not leave directions such
as "ask the buyer," "verify," or "route to" inside the spoken response.

The final response must start with the artifact title. Put no status, reference,
or process sentence before it. Do not announce that the artifact follows.
Do not print internal selection notes such as "default cross-enterprise set" or
"audience assumption." The artifact should contain only material the salesperson
or buyer will use.

If a selected value proposition, differentiator, or objection mentions on-prem,
air-gapped, residency, data location, Kubernetes, or customer-controlled
deployment, load `groundx-on-prem` before drafting. Keep the statement
conditional on the supported deployment mode. Do not say "your data stays" or
"your data never leaves" without an owner-backed boundary for that mode.
This is a hard gate. If `groundx-on-prem` has not been loaded, omit deployment
details from the artifact.

For the real-document demo objection, describe the approved MNDA and sample-data
process from `sales-motion.md`. Do not attach a named customer unless that
customer's proof record explicitly says it followed that process.

When no buyer signal is available, select four or five objections from this
default pool. It spans common enterprise concerns without claiming a ranking.
Do not call them "the most common" or "top objections":

- "We can build this ourselves."
- "Our documents aren't that complex; basic RAG works fine."
- "We can't send our data to a vendor."
- "This is expensive vs free open-source tools."
- "We need to see it work on our documents."

Order the selected objections by the audience's stated pain, deployment
constraints, build posture, sales stage, and likely decision owner. Swap in
technical, regulated, build, cost, or outcome objections only when the context
supplies those signals. With no signal, do not claim the pool is
frequency-ranked. Use `objections.md` to diagnose before
selecting proof. Define value propositions as buyer outcomes and differentiators
as reasons GroundX can deliver them; remove duplicated phrasing before returning.

Before returning the battlecard, run a literal final pass:

1. Remove every `—`, `–`, and `→` character.
2. Remove internal labels, process notes, and audience assumptions.
3. Replace jargon a non-technical buyer would need explained.
4. Remove any sentence that repeats the heading above it.
5. Remove instructions to the salesperson. Turn any useful discovery cue into a
   direct question.
6. Read each objection answer aloud. If it sounds scripted, rewrite it.
7. Remove discovery cues unless the user requested them.

## 5. First non-technical buyer meeting

Use this recipe for a first non-technical buyer meeting.

For a ten-slide intro deck, use this buyer arc:

1. title and buyer outcome;
2. the document/business problem;
3. why current approaches struggle;
4. what GroundX does in plain English;
5. how the workflow changes for the buyer;
6. two or three relevant use cases;
7. eligible proof with scope and qualifiers;
8. deployment/trust options only at buyer altitude;
9. discovery questions or a working-session proposal;
10. one CTA.

Lead with the business problem, not RAG or architecture. Keep vision models,
hybrid search, vector search, Kubernetes details, and training-corpus claims
out of the main arc unless the buyer asks; move technical depth to a follow-up
or appendix. The cover is not a proof slide; do not repeat quantitative proof
there. A source/freshness note accompanies **every slide instance** of a proof,
not merely the first occurrence.

Write each title as a point a human presenter would say aloud. Use short,
audience-facing sentences. Do not use slogans to fill space.

Load `product.md` or `capabilities-and-surfaces.md` before asserting product
workflow behavior. Load `groundx-api` before naming connectors, interfaces, or
ingestion sources. Otherwise use a neutral placeholder rather than plausible
capability copy.

## 6. Source-preservation pass

Before returning any recipe:

- compare each factual sentence with its owner;
- preserve evidence scope, required qualifier, source, and freshness;
- do not change "helped lead the strategy and formation of IBM Watson" into
  "built Watson";
- do not turn a deployment option into an unconditional data-egress promise;
- do not use a narrow customer result as proof of a broader industry outcome;
  and
- omit adjacent claims whose owner was not loaded; and
- preserve "assured," "accountable," and "designed to" without rewriting them
  as "guaranteed," "always," or a completed buyer outcome.
