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

When the local `groundx-studio` server files the report, it reads and attaches
the version, reporter, client, and session tool events itself. Do not restate
any of them in the narrative: the attached header is authoritative, and a
narrative copy goes stale and contradicts it.

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
Never ask the user for those, and never copy them into the narrative.

The whole report is capped at 60000 characters. That is the only hard limit;
nothing else here is a size rule.

`report_issue` requires `confirm: true` and refuses without it. Show the drafted
report to the user first, in full, and set it only after they agree. If the
submission fails, the response carries the draft back so the user still has the
text.

## Filing without a connected client

When `report_issue` is absent from the tool list, a `bug` or an `improvement`
files with a credential-free request. Everything above still applies: the same
narrative, the same confirmation shown to the user first, the same 60000
character cap.

Write the payload to a file, the same shape the tool takes, wrapped in `report`:

```json
{"report": {"title": "...", "narrative": "...", "confirm": true,
 "classification": "bug",
 "harness": {"name": "groundx-agent-harness", "version": "x.y.z", "observed": true}}}
```

```bash
curl -sS -X POST https://api.groundx.ai/api/v1/report -H 'Content-Type: application/json' -d @report.json
```

No key header. The ticket is labelled as anonymous, so send the harness version:
it is the only identifying evidence the report will carry.

Two rejections mean stop, not retry. A `403` means this deployment has reporting
turned off. A `406` naming `report.classification` means the report needs the
authenticated path.

A `knowledge` report cannot be filed this way. Write it into the conversation so
the finding survives, and tell the user that filing it needs a connected GroundX
MCP client; see the `groundx-mcp` skill for connecting one. A rejected
credential-free submission naming `report.classification` means the report needs
that authenticated path.

## The narrative

Write it as one markdown document. These are its sections, not separate fields.

### Context

**Title.** One line stating the observed behavior, specific enough to find
again. Mechanism words ("silently discards", "overwrites", "race") appear only
when the mechanism was directly observed. When the cause is unknown, the title
says what happened, not why.

**Classification.** `bug`, `improvement`, `knowledge`, or `limitation`:

- `bug` — the harness stated something false, or something broke.
- `improvement` — it works, but it cost time it should not have.
- `knowledge` — the harness was missing knowledge, or states something
  incorrect. This is the second reportability test's category.
- `limitation` — the harness cannot do the thing, and that is a known boundary
  rather than a defect.

Classification decides what can be filed without an account: `bug` and
`improvement` can go credential-free, `knowledge` and everything else cannot,
because an unattributable claim about product behavior cannot be followed up.

**Summary.** Two or three plain sentences: what broke, who is affected, and
what below is verified fact versus still unknown. A triager reads this and
nothing else before deciding who owns the ticket.

**Correlation facts.** For every failing call: the UTC timestamp, the endpoint
and verb (or tool name), the response status, the verbatim error, and every
identifier in play (account or customer, bucket, workflow, document, process,
deploy or workflow run, environment). One list, near the top, nothing buried in
prose. This is how a maintainer finds the matching events in logs and the
database; a platform-behavior report without timestamps usually cannot be
actioned, for the same reason a report without a version cannot.

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

Where the defect sits decides the rest of the diagnosis. One question: is the
suspected surface something you can read (a skill, a reference, a scaffold
default, a tool contract, the project's own code)? Or does the behavior sit
behind the GroundX API, where you can see only what crosses the boundary?

**For a surface you can read:**

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

**For behavior behind the GroundX API:**

Do not write a root cause. You cannot see one, and a wrong guess anchors the
investigation: the maintainer starts by disproving your theory instead of
reading your evidence. The record of past reports shows the observations hold
up and the mechanism guesses do not.

**Observed at the boundary.** What went in, what came back, what that proves.
Observed only, nothing inferred.

**Discriminating checks.** Your hypotheses, each written as a testable
prediction paired with the observation that would confirm or refute it, and
labelled as unverifiable from the client side. "If X, then the index will hold
no entries for this documentId; if Y, entries will exist under a different
key." A hypothesis you cannot pair with a deciding observation does not go in
the report. Never assert a backend mechanism (a cache, a race, a token budget)
as the cause; phrase it as a check or drop it.

**What would make this report wrong.** For a `bug` about platform behavior:
the strongest alternative explanation, including your own measurement being
wrong, and what you did to rule it out. If you could not rule it out, present
it alongside the finding rather than presenting the finding as established.

**Both branches end the diagnosis the same way:**

**Suspected layer.** One line: project code, harness guidance, harness tooling,
GroundX platform, or undetermined, with the evidence class that puts it there.
This is the first question triage asks; answer it so nobody has to.

### Outcome

**What was done in session.** A local fix, a workaround, or nothing.

**Recommended change and its home.** What should change, and which file should
own it. Prefer the smallest change that fixes the cause, not the most thorough
one you can think of.

Say what it costs, not only what it fixes. What else reads or writes the thing
you are proposing to change, what depends on it, and what breaks if it moves. A
recommendation that accounts only for the file you happened to read is a guess,
and a maintainer has to redo the work to find out.

**Other observations.** Optional, and context notes only: something a maintainer
should know while reading this report that is not itself actionable. Anything
independently actionable is its own defect and files as its own report, however
small. A second defect parked here has no id, no status, and no owner, and it
will be found by accident or not at all.

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

A platform-behavior report. For a harness-surface defect, the same report
carries Root cause and Why the harness allowed it in place of the boundary
sections.

```markdown
# search_content returns nothing for a document that reports complete

Classification: bug

## Summary
A document finished ingesting but searching its bucket finds nothing, on every
retry across two fresh buckets. Everything below Correlation facts is verified;
the cause is not established, and no client-visible surface shows index state.

## Correlation facts
All times UTC. Environment prod. Buckets 31007 and 31022 (retry).
- 2026-08-30 14:02:11  document_ingestremote: 200, processId 7d1f0c2e
- 2026-08-30 14:06:40  document_getprocessingstatusbyid: 200, status complete
- 2026-08-30 14:07:02  search_content bucket 31007: 200, zero results for a
  phrase quoted verbatim from page 1
- 2026-08-30 14:17 and 14:31: same two calls, same results
- 2026-08-30 14:40: re-ingest into bucket 31022 reproduced all of the above
  (processId 9b21d7aa, documentId 65ac5d92)

## What was being attempted
Ingesting a PDF into a new bucket and then searching it, following the
ingest-to-search workflow in references/05-workflows.md.

## Issue as the user described it
"the upload worked but searching finds nothing"

## Observed at the boundary
Ingest returned a processId, the status poll reported complete, and
document_list shows the document present in the bucket. Search returns zero
results for text visible on page 1. Ten minutes and a fresh bucket changed
nothing, so this is not settling delay or a one-off.

## Discriminating checks
Unverifiable from the client side; each names the observation that decides it.
- If the document was never indexed, the search index holds nothing for
  documentId 65ac5d92 while ingest storage holds its processed output.
- If it was indexed under a different identifier, index entries exist for this
  content under some other key.
- If complete is written before indexing finishes, the status write will
  predate the index writes for documents where search does work.

## What would make this report wrong
A query that misses for query reasons rather than index reasons. Ruled out as
far as the client can see: the phrase is copied verbatim from page 1, and the
same phrasing matches a control document ingested the same way into the same
bucket.

## Suspected layer
GroundX platform, undetermined between ingest and indexing. Client inputs are
verified correct and no exposed tool shows whether the index holds the
document.

## What was done in session
Nothing fixed it. Re-ingesting into a second bucket reproduced it.

## Recommended change and its home
references/05-workflows.md should say that complete means processing finished,
not that the content is searchable, and should end the workflow with a search
that confirms it. Cost: one reference edit and one eval expectation; anything
citing that workflow as the definition of done needs rechecking.

## Other observations
document_getprocessingstatusbyid returns complete with no timestamp, so a
fresh completion cannot be told from an old one. Filed separately.

## Evidence
Observed: the calls listed in Correlation facts, run three times across two
buckets; status complete every time, search empty every time, control document
matched. Not verified: whether the document is present in the index at all,
which the exposed tools cannot show.
```
