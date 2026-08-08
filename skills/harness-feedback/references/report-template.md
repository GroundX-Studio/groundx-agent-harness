# Issue Report Template

Use this when reporting a defect in the harness, whether you file it with the
`report_issue` tool or write it into the conversation for the user to file.

The sections below are guidance, not a form. Nothing rejects a report for
missing one, and a thin report is worth more than one nobody filed. Cover what
you can and say so where you cannot.

One field is not optional.

## Always send the harness version

**`harness: {name, version, observed}` is the single most useful fact in a
report.** Without it a maintainer cannot tell whether the defect is already
fixed, which build to reproduce against, or whether the report is about a version
still in use. A report missing it often cannot be actioned at all, however good
the narrative is.

Nothing else fills the gap. A hosted server runs nowhere near the user's machine
and cannot read the installed version, so it prints "version not supplied" when
you leave it out. That line in a ticket means the evidence is gone, not that
nobody needed it.

Read the version from the installed plugin's manifest and send
`observed: true`. If you can only infer it, send what you have with
`observed: false`. Sending an uncertain version beats sending none.

## When to offer a report

The harness is the company's shared knowledge. A report is how something one
person learned gets into it. Three things are worth reporting: it broke, it was
slower than it should have been, or it did not know something it should.

Two tests. The first catches failures, the second catches gaps.

**1. Would a change to the harness have prevented this?** A change to a skill, a
reference, a scaffold default, a tool contract, an error message, or a missing
validation gate. If yes, offer to report it, even when the harness was not
literally wrong. If the only honest answer is that you should have been more
careful, do not. Without that line the tracker fills with "the AI made a mistake"
and stops being read.

An agent mistake can still be reportable. Guidance scoped to one repository while
the work spans three produces wrong claims from an agent following it correctly;
the guidance scope is the defect.

**2. Did the user supply something the harness should already know?** Nothing has
to break for this one. If the user corrected a fact, supplied context you could
not find, or explained how something works that no reference states, the harness
was missing that knowledge and the next agent will be missing it too. This is the
most valuable kind of report and the easiest to walk past, because the session
felt like a success.

Both tests carry the same filter: **would adding this help everyone using the
harness, or only this user on this task?** A fact about how one customer's data
is shaped is theirs. A fact about how GroundX behaves is everyone's. Report the
second, not the first.

### Offer when

**A diagnostic path is exhausted and the problem stands.** You have run the steps
the skill prescribes and have nothing left to try.

**Something the harness asserts is contradicted by what you observe.** These are
the ones worth naming, because they are easy to miss:

- a documented endpoint that returns not-found
- a field a reference describes that the API rejects
- a documented path that does not exist
- a tool the skill lists that is absent from the tool list
- a documented default that does not match observed behavior

**The user corrects a claim you made from a skill or reference.** The harness told
you something and reality did not agree. A correction of your own reasoning is
not reportable unless guidance made the wrong reasoning look right, which is the
same test again.

**The same tool fails three times in one session.** Repetition means the
workaround is not working.

**The user tells you something the harness does not contain.** They correct a
fact, explain a behavior no reference describes, or hand you context you searched
for and could not find. Nothing failed. Report it anyway, as long as it passes
the everyone-or-one-user filter.

**The user asks.** Draft it against the template without further qualification.

### Do not offer when

**One offer per defect per session.** If the user declines, that is the end of it
for that defect. Do not ask again.

**Nothing resolved on its own.** A request that failed once and succeeded on
retry, with no harness change involved, is not a defect.

**Not in the middle of working.** Offer at a stopping point, or when the task is
abandoned. Never interrupt something that is still making progress.

**Not for something true only here.** A customer's schema, one repository's
layout, a one-off preference. If adding it to the harness would help nobody but
this user on this task, it is not a report.

**Not for a user's own input mistake** — with one exception. If the harness's own
error message is what made the mistake hard to diagnose, the message is the
defect. Report it against the message, not against the user.

## What the tool does with it

You write the narrative. The platform attaches the reporter from the credential,
and the client and session tool failures when a local harness server is running.
Never ask the user for those.

The whole report is capped at 60000 characters. That is the only hard limit;
nothing else here is a size rule.

`report_issue` requires `confirm: true` and refuses without it. Show the drafted
report to the user first, in full, and set it only after they agree. If the
submission fails, the response carries the draft back so the user still has the
text.

## The narrative

Write it as one markdown document. These are its sections, not separate fields.

### Context

**Title.** One line naming the defect, not the symptom.

**Classification.** `bug`, `improvement`, or `limitation`:

- `bug` — the harness stated something false, or something broke.
- `improvement` — the harness was missing knowledge, or it works but cost time
  it should not have.
- `limitation` — the harness cannot do the thing, and that is a known boundary
  rather than a defect.

**What was being attempted.** The user's goal and the steps up to the failure,
including which skills, tools, and repositories were in play. A defect is only
judgeable against what someone was trying to do.

**Issue as the user described it.** Their own words, quoted. Not your paraphrase.
"Publish did nothing" and "publish returned success but the deployment did not
change" are different reports, and a maintainer needs to see which one was said.

**Relevant conversation excerpts.** Optional. Verbatim exchanges that carry
information a summary cannot, such as guidance you followed to the wrong outcome.
Include them only where they change what a maintainer would do. Quote the
exchange that misled you and summarise the rest: a pasted session buries the
diagnosis instead of supporting it.

### Diagnosis

**What happened.** The observable symptom and the steps that reproduce it.

**Root cause.** Cite it: a file path and line, a tool name, an endpoint, or a
skill and reference section. If you could not establish one, write
`not determined`. A guess presented as a cause is worse than no cause.

Cite against the pushed branch, not your local checkout. A line number from a
stale branch sends the maintainer to the wrong place, or to nothing at all.

**Why the harness allowed it.** Which skill, reference, scaffold default, tool
contract, error message, or missing validation gate made the wrong behavior look
correct. This is the section a maintainer acts on. A stack trace never contains
it and neither does the user's description; only an agent that has just read the
guidance can say it, and only while the session is open. `unknown` is a useful
answer when you cannot tell.

### Outcome

**What was done in session.** A local fix, a workaround, or nothing.

**Recommended change and its home.** What should change, and which file should
own it. Prefer the smallest change that fixes the cause, not the most thorough
one you can think of.

Say what it costs, not only what it fixes. What else reads or writes the thing
you are proposing to change, what depends on it, and what breaks if it moves. A
recommendation that accounts only for the file you happened to read is a guess,
and a maintainer has to redo the work to find out.

**Other observations.** Optional. Smaller shortcomings noticed along the way that
are not this defect. Keep them separate from the root cause and the
recommendation so a maintainer can promote one without confusing it for the
reported problem.

**Evidence.** What you ran and observed, stated separately from what you
inferred. Mark anything you did not verify as unverified.

## Writing rules

**Stand alone.** A maintainer reads this with no access to the session. What was
attempted, what the user said, and any quoted exchange are content and belong in
the report. Framing that only makes sense to a participant does not: no "as you
asked", no "per my earlier review", and no reference to an earlier turn without
reproducing what it said. Do not answer questions the reader never asked, and do
not frame anything as a correction to something you said earlier, because they
never saw it.

**Separate fact from inference.** State what you observed. Mark what you assumed.
If you did not verify something, say so plainly rather than asserting it.

**Be short.** Use the fewest words that carry the information. This is a density
rule, not a length limit: never drop a fact or a caveat to make it shorter, but
cut anything that would not change what the maintainer does. No restating the
title, no narrating how you investigated, no options you rejected, no hedging.

**No em dashes, en dashes, or arrow glyphs.** Commas, periods, colons, or
parentheses.

**One report per defect.** If a session surfaced two unrelated problems, file two
reports so each can be triaged and closed on its own.

**No credentials.** Never quote a key, token, or password. The platform scrubs
what it recognises, and that is a backstop, not permission.

## Worked example

```markdown
# search_content returns nothing for a document that finished ingesting

Classification: bug

## What was being attempted
Ingesting a PDF into a new bucket and then searching it, following the
ingest-to-search workflow in references/05-workflows.md.

## Issue as the user described it
"the upload worked but searching finds nothing"

## What happened
`document_ingestremote` returned a processId. `document_getprocessingstatusbyid`
reported `complete`. `search_content` against the bucket returned zero results
for text visible on page 1. Repeated after ten minutes with the same result.

## Root cause
not determined. The document reports complete and is listed by `document_list`,
so ingest and indexing disagree somewhere the tools do not expose.

## Why the harness allowed it
The workflow reference treats a `complete` processing status as the signal that
the document is searchable, and nothing tells the agent to verify with a search
before reporting success. An agent following it will say the upload worked.

## What was done in session
Nothing that fixed it. Re-ingesting into a second bucket reproduced it.

## Recommended change and its home
references/05-workflows.md should say that `complete` means processing finished,
not that the content is searchable, and should end the workflow with a search
that confirms it. Cost: one reference edit and one eval expectation. Anything
citing that workflow as the definition of done would need rechecking; the setup
and auth references do not.

## Other observations
`document_getprocessingstatusbyid` returns `complete` with no timestamp, so
there is no way to tell a fresh completion from an old one.

## Evidence
Ran the ingest, status poll, and search three times across two buckets; status
was complete every time and search returned zero every time. Not verified:
whether the document is present in the index at all, which the exposed tools
cannot show.
```
