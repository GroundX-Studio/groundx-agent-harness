---
name: harness-feedback
description: >
  Use when the harness itself was wrong, missing, or slower than it should have
  been: a documented endpoint returns not-found, a reference describes a field the
  API rejects, a listed tool is absent, a documented default does not match what
  you observe, the same tool fails repeatedly, the user corrects a claim you made
  from a skill, or the user tells you something no reference contains. Also use
  when a skill claims a subject and had nothing to give on it, so you had to
  answer from outside the harness. Also use when the user asks to file a bug,
  report a problem, or flag missing knowledge. This skill files the report; it
  does not fix the harness.
---

# Harness Feedback

When the GroundX Agent Harness plugin is installed, anything wrong with the
harness itself starts here. Other skills own their subject; this one owns the
harness being wrong about that subject.

The harness is the company's shared knowledge. A report is how something one
person learned gets into it, so the next agent starts where this session ended.

Do not use this skill for problems in the systems the harness describes. A stuck
document, an empty search, a failing deployment, or a broken build belongs to the
skill that owns that surface. Come here when the harness told you something that
was not true, or should have told you something and did not.

## The two tests

**1. Would a change to the harness have prevented this?** A change to a skill, a
reference, a scaffold default, a tool contract, an error message, or a missing
validation gate. If the only honest answer is that you should have been more
careful, there is nothing to file.

**2. Did the user supply something the harness should already know?** Nothing has
to break for this one. This is the most valuable kind of report and the easiest to
walk past, because the session felt like a success.

Both carry the same filter: **would adding this help everyone using the harness,
or only this user on this task?** A fact about how one customer's data is shaped
is theirs. A fact about how GroundX behaves is everyone's.

## Silence counts, inside a claim

A skill's own description states the subjects it owns. When a skill claims a
subject and no reference in it answers a question inside that subject, the harness
has a gap, and test 2 applies even though nothing failed.

The bound is the claim. The harness not covering a subject is not a defect,
because covering everything was never the contract. Only a subject some skill said
it owns counts.

Establish the silence before reporting it. Open the skill's `references/README.md`
index and look where it sends you. Not finding something is not the same as the
harness not holding it, and a gap report that turns out to be a search failure
costs a maintainer the search you skipped.

**Worked through:** a user asks for a company executive's biography for an
investor deck. `master-brand-gtm` names investor material, board decks, and
company positioning in its own description, so the subject is claimed. Its
reference index has no entry for a person and no reference carries one, so the
silence is real and not a missed lookup. Answering required going outside the
harness. That is reportable, and it passes the everyone-or-one-user filter,
because every future investor or analyst request needs the same facts.

Compare a question about Python asyncio semantics. Nothing claims it, so the
harness having nothing is not a gap and there is nothing to file.

## Filing

Read `references/report-template.md` before drafting. It carries what a report
covers, the writing rules, and a worked example.

**Always send `harness: {name, version, observed}`.** The version is the most
useful fact in a report and the one the platform cannot supply: a hosted server
cannot read the version installed on the user's machine. Without it a maintainer
cannot tell whether the defect is already fixed. Read it from the installed
plugin's manifest, or send what you can infer with `observed: false`.

**With `report_issue` in your tool list:** draft the narrative, show it to the user
in full, and set `confirm: true` only after they agree. The platform attaches the
reporter, and the client and session tool failures when a local harness server is
running. Never ask the user for those.

**Without it:** a bug or an improvement files with a credential-free POST to the
report endpoint; `references/report-template.md` carries the request. Show the
draft to the user first, exactly as with the tool. A knowledge report cannot go
that way: write it into the conversation so the finding survives, and tell the
user that filing it needs a connected GroundX MCP client. See the `groundx-mcp`
skill for connecting one.

## Routing Contract

- **Role:** `reference`.
- **First-entry intents:** a harness assertion contradicted by observation; a
  skill silent on a subject it claims; the user correcting a skill-derived claim;
  the same tool failing repeatedly; an exhausted diagnostic path; an explicit
  request to file a bug or report missing knowledge.
- **Deferrals:** a broken document, search, deployment, build, or API call goes to
  the skill that owns that surface first. Return here only if the harness's own
  guidance is what made it wrong or hard to diagnose.
- **Required handoffs:** none. This skill files a report and does not fix the
  harness or the surface.
- **Before producing output:** read `references/README.md`, then
  `references/report-template.md`, then `../RESPONSE_STYLE.md`. A report is an
  artifact for a reader who never saw the session.
- **Misuse cases:** do not file for an agent mistake with no harness cause, a
  failure that resolved on retry, a fact true only for this user, or a defect you
  already offered and the user declined. Do not interrupt work that is still
  making progress.

## Installed-skill retrieval contract

Do not rely on memory for what a report covers or when to offer one. Read
`references/README.md` and open the template before drafting. The rules about
what is reportable change, and a remembered version files noise.

## Pre-return Checklist

- [ ] The finding passes one of the two tests, and the everyone-or-one-user filter.
- [ ] For a gap, the skill's reference index was consulted before calling it
      silent.
- [ ] `harness.version` was sent. A report without it is usually not actionable.
- [ ] The draft was shown to the user in full before `confirm` was set.
- [ ] The report stands alone for a reader who never saw the session.
- [ ] No credential, key, or token appears in the narrative.
