# 9. Testing methodology

How to validate that a `groundx-extraction-workflows` skill change works — for both
customers authoring new YAMLs and maintainers of the skill itself.

Complements `references/10_debugging_methodology.md`, which covers
investigating failures when a test reveals one.

## 9.1 Two audiences

Skill changes affect two distinct populations:

- **Customers using the skill via Claude Code** — author a YAML, run
  extraction, iterate to accuracy. No Python expertise required. The
  test is end-to-end through Claude.
- **Developers maintaining the skill** — change `templates/`,
  `references/`, or repo-level scripts. Need direct Python access plus
  the customer-flow validation.

Every skill change must be validated for both. Skipping the customer
flow is the most common drift mode: a refactor that "still works for
me as a developer" can silently break the Claude-driven onboarding.

## 9.2 Audience A — clean-room sub-agent test (pre-PR gate)

The strict gate before any skill version flips draft → ready-for-review.

### 9.2.1 Setup

Spawn a fresh general-purpose sub-agent with explicit constraints:

- DO NOT read prior debug artifacts (`notes/extractx-runs/`,
  `/tmp/clean-room-*/`, prior session run dirs)
- DO NOT read reference implementations outside the skill
  (customer-owned reference managers, customer-specific notebooks)
- DO NOT modify any file inside `skills/groundx-extraction-workflows/`
- DO write run artifacts to a fresh temp dir (e.g. `/tmp/clean-room-vX/`)
- DO use `templates/run_extraction.py` (not a custom runner)

### 9.2.2 Inputs

- The Linear ticket for the customer (e.g. AGE-1)
- The skill at HEAD
- The customer's PDF + answer key
- `GROUNDX_API_KEY` available in env or a `.env` file in the
  work directory

### 9.2.3 Success criteria

- Zero local patches required to complete the run
- Accuracy target met for the customer (e.g. ≥95% statement + 3/3
  charges for the invoice example)
- `run.log` shows the expected event sequence (compile → validate →
  workflow.create → bucket.create → workflow.add_to_bucket → ingest →
  poll → xray.captured → extract.captured → run.done)

### 9.2.4 Why this catches bugs

A normal development cycle accumulates implicit context — knowledge of
where files live, which arguments are required, which env vars work.
Clean-room runs strip that context and surface anything the skill
doesn't explicitly teach. During AGE-15 development, two real bugs
surfaced this way that normal use missed:

1. A `RunLog.event(name, **kwargs)` collision with a `name=` data
   kwarg. Normal dev workflow never hit the broken path because the
   developer didn't pass `name=` as data.
2. A `dotenv.load_dotenv()` cwd-resolution bug. The developer ran
   from inside the harness; the sub-agent ran from `/tmp` and silently
   couldn't find the `.env`.

Each bug took the sub-agent a single iteration to surface and was
trivially fixable. Without clean-room testing both would have shipped.

## 9.3 Audience B — developer-side validation

For routine maintainer changes:

1. **`node scripts/validate.mjs`** from repo root — all 13 must pass.
2. **Smoke the iteration aids** if any was touched:
   - `compile_workflow.py` → `validate_workflow_json.py` on output
   - `run_extraction.py` → end-to-end against a known fixture
   - `xray_to_extract.py` → on a captured X-Ray
   - `cleanup_orphans.py --dry-run`
3. **For meaningful changes** — repeat the §9.2 clean-room test.

## 9.4 What to record in the PR

A skill-change PR should include, in the top-level body or comment:

- **Audience A test recipe** — how a customer would validate the
  change. Reference the relevant Linear ticket + fixture (e.g. AGE-1
  + an invoice + answer key).
- **Audience B test recipe** — concrete validate + smoke commands the
  reviewer can run locally.
- **What was verified** — a snapshot of accuracy numbers achieved,
  pointer to the `run.log` location, any orphan-resource cleanup done
  on the platform.
- **AC + DoD audit tables** — declarative completion-state snapshot
  for the relevant Linear ticket.

The AGE-15 PR (PR #3) is the worked example of this convention.

## 9.5 Cross-references

- `references/10_debugging_methodology.md` — what to do when a test
  reveals failure
- `references/8_iteration_and_feedback.md` — iteration budget, journey
  storage, X-Ray-first iteration loop
- `references/1_extraction_loop.md` §3 — the loop the clean-room test
  exercises end-to-end
