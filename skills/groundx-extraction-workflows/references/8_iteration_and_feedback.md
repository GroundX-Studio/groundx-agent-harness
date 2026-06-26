# 8. Iteration lifecycle and compounding feedback

How to manage the YAML through iteration, where to store the journey,
and how lessons from each customer feed back into the skill so future
customers benefit. This reference is the operational layer on top of
the basic loop in `1_extraction_loop.md`.

## 1. Overview

A typical customer onboarding has three phases:

1. **Author** — agent drafts an initial YAML from the customer's inputs
   (document + expected answers) and the skill's references.
2. **Iterate** — run compile → register workflow → ingest → extract →
   compare. Use `prompt-improvement-loop.md` to source-adjudicate, classify the
   miss, change one prompt or group rule, and check for regressions. Repeat.
3. **Finalize** — once accuracy meets the bar, the YAML is locked.
   Decide what feeds back into the skill so the next customer's run
   starts from a stronger position.

This document covers phase 2 (iteration journey) and the hand-off
into phase 3 (compounding feedback).

## 1.1 Expected-answer uncertainty

Treat expected answers as evidence, not as unquestionable truth. They may arrive
as JSON, spreadsheets, documents, text files, PDFs, or human-review notes. If
the extracted value is visible in the source document but the expected answer
has a normalized, blank, sentinel, or database-derived value, pause before
changing YAML prompts.

Record the mismatch in the run notes with:

- the source page or X-Ray chunk where the value appears
- the extracted value
- the expected-answer value and source location
- the source-support decision and scoreability decision
- the question that needs human confirmation

Do not tune prompts to reproduce a suspected expected-answer artifact. After the
expected value is confirmed, make the smallest change: comparison normalization
or mapping when the customer's expected format is valid, YAML prompt wording
when the model picked the wrong source value, or business logic when the output
shape needs a dedupe/link/passthrough rule. Use `5_validation.md` §1.2 for the
minimal mapping record.

## 2. Iteration budget

### 2.1 Default: 2 iterations max per working session

Cost discipline matters because each iteration re-ingests the
document, consuming time and platform budget. Patterns that resist
2 rounds of prompt tightening usually need more than another prompt
tweak — they may indicate platform limitations, ambiguous ground
truth, or a structural rethink of the schema.

Forcing a stop after 2 iterations creates time to analyze what's going
wrong, which is more productive than another quick tweak.

### 2.2 When to override the budget

- A specific iteration takes <2 minutes end-to-end (e.g., a single
  prompt edit with cached chunks already inspected via X-Ray). Cheap
  iterations don't count against the budget.
- The user explicitly asks to continue past the budget for a specific
  field or reason.

### 2.3 What to do if the budget is exhausted without hitting the bar

- Capture the failing field(s) and observed behavior in the run's
  `run.md`.
- Consult `6_known_limitations.md` §3 (X-Ray inspection, escalation
  playbook).
- Either schedule another session (after analysis) or escalate to the
  platform team — do not push more iterations in the current session.

### 2.4 Stop on non-convergence within the budget

Budget exhaustion (§2.3) is the *hard* stop. There's also a *soft* stop:
if iteration N regresses or fails to improve over iteration N-1, stop
even when budget remains. Continuing to tighten prompts past this signal
is the most common way to waste the remaining budget.

Recognize non-convergence when any of these is true:

- A field that PASSed in iteration N-1 now FAILs in iteration N
  (regression — usually collateral damage from tightening another field)
- The FAIL count is the same or higher, with the failing set shifting
  rather than shrinking (oscillation)
- Same YAML run twice produces different FAIL sets (stochastic — a
  platform/model issue, not a prompt issue)

When you hit any of these, do not run another tighten-and-retry
iteration. Instead:

1. Open X-Ray for the failing iteration and inspect the raw per-chunk
   output for the failing fields. See
   `references/10_debugging_methodology.md` §10.3 for the diagnostic
   artifact inventory.
2. Identify the root cause from the X-Ray evidence and act:
   - **Schema coupling** (fields fighting each other across iterations):
     restructure the schema — move disambiguation to the group-level
     `prompt.instructions` block, or split coupled fields across groups.
     Do not keep tightening individual fields.
   - **Signal not in the document**: accept the FAIL with a documented
     rationale in `run.md`. Do not tighten prompts.
   - **Platform-side issue** (aggregator behavior, AGE-6 platform-locked
     names, AGE-7 convention ambiguity): escalate per
     `references/6_known_limitations.md` §3.
3. If the diagnosis isn't clear from X-Ray, escalate rather than guess.
   Repeated prompt tightening on an unclear root cause burns quota and
   corrupts the journey record.

## 3. Journey storage

Each customer's iteration history lives **outside the skill
directory**, in a location the team picks. The skill does not
prescribe an absolute path because storage location is a team
operational decision (privacy, retention, access control).

### 3.1 Recommended structure per run

```
<storage-root>/extractx-runs/<customer>-<run-number>/
├── run.md                         summary, hypothesis, iteration log, verdict, lessons
├── inputs/
│   ├── <document>.pdf             customer-supplied document (subject to customer permissions)
│   └── <expected-answers>.*       customer-supplied expected answers or reviewer notes
├── v1/
│   ├── prompt.yaml                first-draft schema
│   ├── workflow.json              compiled workflow JSON
│   ├── output.json                raw GroundX get_extract, when available
│   ├── xray.json                  raw X-Ray evidence
│   ├── xray_diagnostic.json       local X-Ray reconstruction, when needed
│   ├── final_output.json          local diagnostic/business-logic output, when needed
│   ├── expected-answer-mapping.json  source-backed mapping/adjudication record, when needed
│   ├── compare-report.txt         score_extraction.py output
│   └── notes.md                   rationale for v1, observed failures
└── v2/                            second iteration (same shape) — only if needed
```

A team using `notes/extractx-runs/` adjacent to their repo is one
example. Cloud storage with appropriate access control is another.
The skill cares about the structure, not the location.

### 3.2 What `run.md` contains

A single durable record per run with these sections:

- **Inputs** — customer name, document type, expected-answer format, field
  count, run date.
- **Hypothesis** — what the agent expected before starting (schema
  shape, likely hard fields).
- **Iteration log** — for each iteration: what changed, what passed
  before vs. after, accuracy delta.
- **Verdict** — final accuracy, what shipped to `examples/<customer>/`,
  what stayed in journey storage.
- **Lessons** — see §5 for what gets promoted.

### 3.3 Customer permissions

Documents and expected answers are typically customer-confidential. Before
storing inputs anywhere persistent:

- Confirm the customer permits storage in the team's chosen location.
- Default to journey-storage-only (not committed to a public-facing
  repo) unless the customer has explicitly granted broader rights.
- Finalized YAMLs are generally derivative artifacts (the schema is
  the team's IP), but the document content is the customer's. Store
  documents separately from the YAML where possible.

## 4. Finalization criteria

A YAML is finalized when:

- Per-field accuracy meets the customer's bar (typical default: ≥95%
  on per-document fields, 100% on repeating records).
- Remaining non-PASS rows are documented (known platform issues per
  `6_known_limitations.md`, or convention ambiguities the customer
  has explicitly accepted).
- The customer or skill maintainer signs off.

If the YAML hasn't met the bar after the iteration budget is exhausted,
**do NOT finalize.** Capture the gap and either schedule another
session (after analysis) or escalate. Premature finalization corrupts
the compounding feedback loop because the example will mislead the
next customer's onboarding.

## 5. Compounding feedback

After finalization, three things can land back into the skill so
future customers benefit. Each has a different bar.

### 5.1 Finalized YAML → `examples/<customer>/`

The lowest bar. After every successful finalization:

```
skills/groundx-extraction-workflows/examples/<customer>/
├── prompt.yaml                the finalized YAML
├── data/
│   ├── <document>.pdf         (only if customer permits; otherwise reference an external location)
│   └── <expected-answers>.*   (same caveat; map to runner-shaped JSON before scoring)
└── README.md                  one paragraph: domain, document shape, accuracy results
```

The sub-agent for any future customer reads all `examples/*/prompt.yaml`
as reference patterns. More finalized customers → more patterns →
shorter authoring time for new customers.

If customer permissions don't allow the document to be committed,
include the YAML and a `README.md` that explains the document shape
without including the actual document.

### 5.2 Per-customer lessons → `examples/<customer>/LESSONS.md`

The middle bar. For each finalized customer, capture what was hard in
a single file:

```markdown
# Lessons from <customer>

## Schema shape
[How fields were decomposed; what worked, what didn't]

## Hardest fields
- field_x: required two iterations because the model kept confusing it
  with field_y. Resolved by adding a negative example to instructions.
- field_z: convention ambiguity — see `references/6_known_limitations.md`.

## Platform constraints surfaced
- [Specific limitations discovered during this run, with Linear ticket
  references where applicable]

## Generalizable patterns
[Anything worth promoting to references/ — see §5.3 for the bar]
```

`LESSONS.md` is concise — half a page, not an essay. Future agents
read it alongside `examples/<customer>/prompt.yaml` when working on a
similar customer.

### 5.3 Generalizable lessons → updates to `references/`

The highest bar. When a lesson applies across customers (not just one
domain or document type), update the skill's references:

| Lesson shape | Lands in |
|---|---|
| New platform constraint observed across 2+ customers | `references/6_known_limitations.md` |
| New schema design pattern that generalizes | `references/2_schema_design.md` |
| New iteration technique (e.g., a specific X-Ray inspection idiom) | `references/1_extraction_loop.md` |
| New mode of compile-time validation | `references/4_sdk_integration.md` |

The bar for updating references is **"this would help the next
customer regardless of domain."** Customer-specific tactics stay in
`LESSONS.md` even if they're clever — clever tactics that work for one
domain often misfire in another.

A rough rule: wait until 2 customers have hit the same issue before
promoting to references. A single observation is anecdote; the second
is a pattern.

### 5.4 What does NOT feed back

- Customer-specific prompts (already in `examples/<customer>/`)
- Iteration intermediates — `v1/`, `v2/` artifacts (already in journey
  storage)
- Speculative patterns ("this might generalize") — wait until you see
  it twice
- Failures from a single run unless the failure is a hard platform
  constraint (then it belongs in `6_known_limitations.md`)

## 6. X-Ray as a first-class iteration artifact

X-Ray is the raw output of GroundX's parsing + chunking step. It
contains each chunk's text, content type (`paragraph` / `figure` /
`table_figure` / etc.), page numbers, and any custom workflow extraction
outputs already produced. Reading X-Ray is the most direct way to
answer **"why didn't this field extract"** — was the value in the
chunk at all? Was the chunk routed to the right extraction step? Did
the LLM just miss it?

### 6.1 When to capture

After ingest completes — that is, after polling shows status
`complete` — and before the iteration ends. Capture in parallel with
`get_extract`; both are reads of state the platform already produced.

```python
xray = gx.documents.get_xray(document_id=doc_id)
with open('v1/xray.json', 'w') as f:
    json.dump(xray.dict(), f, indent=2, default=str)
```

Saving the full payload to `v1/xray.json` (or `v2/xray.json` on a later
iteration) makes it durable for the sub-agent's next-round authoring.

### 6.2 How the sub-agent uses it on the next iteration

When iterating from v1 to v2, the sub-agent reads three artifacts
together:

- `v1/compare-report.txt` — which fields passed/failed
- `v1/output.json` — raw GroundX `get_extract`, when available
- `v1/final_output.json` — local diagnostic/business-logic output, when used
- `v1/xray.json` — what GroundX parsed per chunk (diagnostic source evidence)

The combination lets the sub-agent diagnose at the right layer:

- **Field is wrong AND value is visible in some chunk** → prompt issue.
  Tighten `instructions` or `identifiers`.
- **Field is wrong AND value is in NO chunk** → parsing/chunking
  issue. See `references/6_known_limitations.md` §3 for the platform
  escalation path. Do not waste an iteration tightening prompts that
  can't fix this.
- **Field is right in some chunks but wrong after reconciliation** →
  identity/dedup issue. This points at a v0.2+ concern (mode-key +
  entity identity) and is out of scope for basic-tier iteration.

### 6.3 Cost

X-Ray retrieval is a single API call per document, returning a
potentially large JSON payload (chunks + page image URLs). It does
not consume file-token quota — it's a read of state already produced
by the prior ingest. Always capture it; the marginal cost is zero
and the diagnostic value is high.

---

## 7. Quota tracking

Each ingest consumes file-token quota. Tracking consumption per
iteration gives two benefits: the team avoids surprise quota
exhaustion mid-iteration, and future customers benefit by seeing
typical consumption ranges for similar document types.

### 7.1 What to capture

GroundX exposes quota state via the customer endpoint:

```python
c = gx.customer.get().customer
meters = c.subscription.meters
# meters.file_tokens.value, meters.file_tokens.max
# meters.searches.value, meters.searches.max
```

Save the meters dict before and after each iteration:

```python
with open('v1/quota-before.json', 'w') as f:
    json.dump(meters.dict(), f, indent=2)
# ... run iteration ...
with open('v1/quota-after.json', 'w') as f:
    json.dump(meters.dict(), f, indent=2)
```

### 7.2 What to record in run.md

For each iteration:
- file_tokens consumed (`after.value` − `before.value`)
- searches consumed (usually 0 for extraction-only runs, but capture
  for completeness)

At the end of the run:
- Total file_tokens consumed across all iterations
- Remaining headroom (`max` − final `value`)

### 7.3 Why this matters for future customers

When the next customer is onboarded with a document of similar size
and field count, the team can look at this run's `run.md` and
estimate quota consumption before starting. Iterations consume more
than one-shot extractions because each iteration re-ingests — a
customer doing 2 iterations on a 1MB PDF roughly doubles consumption
vs. a single run.

If consumption is unexpectedly high during a run (e.g., a much larger
document than budgeted), surface it to the user before continuing to
the next iteration — they may want to pause and re-plan.

---

## 8. When to invoke this lifecycle vs. when to skip

### 8.1 Invoke when

- A new customer needs extraction for a document shape not yet covered
  by an existing example.
- An existing customer's schema needs major revision (>20% of fields
  change, or the document type has materially shifted).
- A new domain is being onboarded (cross-domain learning is the whole
  point of the compounding feedback layer).

### 8.2 Skip when

- A small fix to an existing customer's YAML (one or two fields). Edit
  the YAML in place, run the runner, commit if it works. The journey
  storage overhead isn't worth it.
- Exploratory work that won't be productionized.
- Re-running an existing successful YAML against a new instance of
  the same document type (no schema change).

## 9. Decision flow

A condensed map for an agent invoking this skill on a new customer:

1. **Inputs available?** Confirm document + expected answers in hand. If
   not, surface to the user.
2. **Storage location agreed?** Confirm where journey storage lives
   for this customer. Default to a team `notes/extractx-runs/`
   location if not specified.
3. **Existing examples to learn from?** Read `examples/*/prompt.yaml`
   and `examples/*/LESSONS.md`. Adjacent-domain patterns help.
4. **Author v1.** Use `2_schema_design.md` + `3_prompt_pipeline.md`.
5. **Run iteration 1.** Compile → register → ingest → extract →
   compare. Save artifacts to journey storage.
6. **Decide: budget remaining?** If yes and accuracy is below bar,
   tighten and iterate. If budget exhausted or bar met, go to step 7.
7. **Decide: finalize or escalate?** Per §4. If finalizing, run the
   compounding feedback flow (§5).
8. **Write `run.md`.** Always. Even runs that didn't finalize need
   the journey record.
