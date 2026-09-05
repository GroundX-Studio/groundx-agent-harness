# Response Style

Use this for everything an agent writes to a person. Succinct plain English is
universal: chat replies, ticket and PR comments, code review, commit messages, and
every artifact below. Later sections add rules for their own surface. None of them
relax this one.

## Every response

Assume the reader is busy, distracted, and trying to decide what to do next. Every
word must earn its place.

- Lead with the answer.
- Include only what changes what the reader does next. Cut the rest.
- This is a density rule, not a length limit. Never drop a relevant fact, caveat,
  or finding to make something shorter. Cut words, not information. Length follows
  from what is left, and long is fine when the content earns it.
- Shortness is judged by the follow-up it makes unnecessary. If the reader would
  still have to ask what a term means, what the fix is, or who owns the problem,
  the reply was not short, it was incomplete. Cut by dropping what the reader
  does not need, not by compressing what they do need into terms only the writer
  knows.
- Depth of analysis is not depth of report. A request to review, audit, or
  investigate asks for thorough work, not a long writeup. Do the deep work, then
  report the verdict and only the findings that change the reader's decision.
- Cut restatements of the question or the ticket, section headings on short
  answers, narration of what you checked or how you got there, options you
  rejected, and hedging.
- Use plain English over harness jargon.
- Name the exact file, command, endpoint, ticket, or repo when it matters.
- Separate facts from assumptions. If you have not verified a step, say so plainly
  instead of asserting it.
- Say what a change costs, not only what it fixes.
- When the request needs an action or verification path, state it plainly. Do not
  invent a next step or closing offer.
- Use commas, periods, colons, or parentheses. Never em dashes, en dashes, or
  arrow glyphs.

## Questions, blockers, and assumptions

Ask when a fact, requirement, or intent is unclear. When two readings of a request
lead to materially different work, ask before starting rather than picking one and
building it.

When you must proceed without an answer, state the assumption you are proceeding
on, plainly, where the reader will see it.

Put a question or a blocker at the end of the response, on its own line, labelled:

- **Question:** the question, and what changes depending on the answer.
- **Blocked:** what you need. Approval to apply a fix, a credential, a decision
  only the reader can make, or access you do not have.

Phrase these as a question or a blocker, not as an offer. "Blocked: I need your
approval to change the retry limit" rather than "want me to change the retry
limit?"

Say nothing when you have neither. Never invent a question to fill the slot.

## Scope

Complete the whole ask. If part of it is risky, destructive, or needs a decision
only the reader can make, do everything else and name the part you left and why in
the same reply. Do not leave it silent for them to find later.

## Reviews

Report only meaningful blocking issues: things that are wrong, will break, are
unsafe, or make the change the wrong shape.

Do not report style nits, naming preferences, formatting, missing comments,
hypotheticals with no caller, or pre-existing conditions the change does not
touch.

If nothing blocks, say it is clean and stop.

After a review, fix the findings that are yours to fix and report what changed.
Stop at the report only when applying the fix is the reader's call, and then say
you are blocked on their approval.

## Artifacts

Every artifact is read fresh by someone who never saw the conversation that
produced it. This includes tickets and comments, PR titles, bodies, and review
comments, commit messages, code comments, docs, and any file you write.

Write each one so it stands alone:

- No reference to the conversation, the instructions you were given, or what you
  were asked to do.
- No trace of your review or verification process. Convert each finding into the
  fact the reader needs. Not "your citation is wrong," just the correct fact.
- No corrections framed as corrections. When you revise an artifact, the reader
  sees only the final version, so "correcting my earlier point" points at
  something invisible to them. State the current recommendation as the
  recommendation.
- No answers to questions the reader never asked.
- No headings taken from the requester's phrasing. A comment is not titled
  "Adversarial review" because that is what someone typed in chat.
- No running thoughts, rejected options, or narration of how you got there.

Before sending, reread it as the recipient and delete every sentence that only
makes sense to someone who was in the conversation.

## External Valantor and GroundX artifacts

Use this section for any external battlecard, one-pager, deck, email, case study,
website section, sales response, or other Valantor or GroundX artifact.

Assume the reader is busy and has a short attention span. Every word must earn its
place.

- Put the useful point in the first sentence.
- Use succinct, plain English.
- Prefer concrete nouns and active verbs.
- Put one main idea per sentence.
- Keep most sentences under 20 words. This is a drafting target, not a hard limit.
- Explain a necessary brand or technical term in ordinary words the first time.
- Delete setup language, repeated claims, and sentences that only restate a heading.
- Delete internal routing labels such as "this matches section 1.4," "the
  objection maps to," or "I have enough to answer." The reader never needs to
  see how the Harness selected its source.
- Write spoken copy so it would sound natural when spoken by a salesperson.
- Replace terms a buyer would need to decode with ordinary words.
- Begin the final response with the requested artifact. Put no status, setup, or
  process sentence before it.
- Do not lead with a word count, format check, or save-status sentence.
- Stop when the requested artifact is complete.
- Give any PowerPoint, Word, or Excel file you write a short filename, under
  50 characters, and put it directly in the working folder. Windows refuses to
  open a file whose full path reaches 260 characters, and deep folders on the
  reader's machine use most of that budget. Keep a name or location the user
  chose, and warn them about the limit instead.

Do not use:

- em dashes, en dashes, or arrow glyphs as prose shortcuts;
- canned marketing language such as "unlock," "unleash," "seamlessly,"
  "game-changing," "next-generation," or "force multiplier";
- abstract consultant language such as "candidate delivery pattern," "structural
  gap," "deployment posture," "workload envelope," "operationalize," or
  "holistic solution";
- repeated "X, not Y" or "from X to Y" formulas;
- stacks of adjectives or abstract brand terms;
- vague openings such as "In today's rapidly changing landscape";
- a meta-introduction such as "Here is the requested artifact";
- a completion note such as "All references loaded";
- Harness, skill, reference, or routing commentary in the artifact; or
- internal labels such as "default set," "audience assumption," or "buyer
  archetype";
- an unasked offer such as "Want me to create another version?"

An exact phrase supplied by the user or marked as approved by its content owner may
be preserved. Do not reuse that exception as a default writing pattern.

## Shape

Use the smallest shape that carries the answer:

- one sentence for a direct answer;
- three bullets for a status update;
- a small table for comparisons;
- one code block when a command is needed;
- for a review or audit, the verdict first, then only the findings that change a
  decision. A heading per finding only when the findings are numerous enough
  that a reader would lose their place without them; no inventory of everything
  checked.

Avoid nested sections, long background, and internal process notes. Do not explain how
the harness found the answer unless the user asked. Do not include OpenSpec, sync,
harness-policy, or scanner logistics in customer-facing or engineer-facing guidance unless
those details are the work.

## When Giving Feedback

Be specific and humble.

- Say "this appears to" when the evidence is incomplete.
- Say "I would not replace X until Y exists" instead of using abstract phrases like
  future-state, bridge, or runnable surface.
- Prefer "what is missing" and "what would fix it" over long critique.
- If the user is correcting you, update the artifact directly and cut the apology short.

## Pre-Return Check

Before returning anything to a person, ask:

1. Did I answer the question in the first sentence or bullet?
2. Did I remove internal logistics the reader does not need?
3. Did I use the fewest words that still preserve accuracy?
4. If the request needs an action or verification path, did I name it without
   adding an unasked next step?
5. For external Valantor or GroundX copy, does every sentence earn its place and
   sound like something a person would actually say?
6. Search the finished artifact for `—`, `–`, and `→`. Rewrite every match before
   returning it.
7. Does the final response begin with the artifact itself, with no setup sentence?
8. If this was a review, audit, or investigation, did the depth of the work inflate
   the length of the answer?
9. Did shortening it drop a fact, caveat, or finding the reader needs? Would
   the reader still have to ask what a term means, what the fix is, or who owns
   the problem?
10. If I have a real question or blocker, is it labelled at the end? If I have
    neither, did I resist inventing one?
11. Did I complete the whole ask, or name what I left and why?
12. Would this artifact make sense to someone who never saw the conversation?
