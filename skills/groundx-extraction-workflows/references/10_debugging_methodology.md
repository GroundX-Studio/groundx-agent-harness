# 10. Debugging methodology

How to investigate failures in `groundx-extraction-workflows` skill output or
customer extractions. Complements `references/9_testing_methodology.md`,
which covers verifying that changes work in the first place — debugging
is what you reach for when a test reveals a problem.

## 10.1 Diff-before-debug discipline

When a new customer onboarding or a regression produces unexpected
behavior **and** a known-working reference exists (production code,
prior customer, working notebook), the cheapest test is **artifact
diff**, not behavioral hypothesis.

### 10.1.1 The principle

When something works in a known reference but fails in your
implementation, **compare the artifact the system actually consumes**
(workflow JSON, request body, serialized config) **before forming
behavioral hypotheses**. Behavior is downstream of artifacts; mysterious
behavior usually has a boring artifact cause.

### 10.1.2 When this applies

- Onboarding a new customer with an existing production reference
- Diagnosing why a skill change regressed extraction
- Investigating "works for them, doesn't for us" reports

### 10.1.3 When it doesn't apply

- Brand-new domain with no reference — must reason from the SDK + docs
- Behavioral differences with no shared artifact format

## 10.2 Worked example — the v0.1.2 bug

invoice-001 testing produced `account_charges: []` despite per-chunk
X-Ray extractions being correct. The actual cause was a wire-format
issue: Pydantic v1's `.dict()` silently dropped unset fields, so the
compiled workflow JSON was missing 5 of 7 `WorkflowSteps` slot keys
and 3 of 6 `WorkflowStep` variant keys per populated step. The
platform's aggregator silently skipped the chunk_keys → account_charges
step.

Debugging path actually taken (≈3 hours, 6 ingests across v3–v7):

- v3: rewrote prompt wrappers to match a reference manager (wrong direction)
- v4: removed schema fields without checking the compiled workflow diff (wrong direction)
- v5: changed `section_strategy="page"` two-step flow (wrong direction)
- v6: added `workflows.add_to_account()` (wrong direction)
- v7: ran the reference manager directly — worked. Bug isolated to our path.
- v8: diffed workflow JSON — caught it.

Debugging path the discipline would have taken (≈5 minutes, 0 ingests):

- Capture the known-working workflow JSON via SDK introspection
- Compile our YAML through our compiler
- `diff` the two
- 11 structural differences visible immediately

## 10.3 Useful diagnostic artifacts

- **X-Ray** (`gx.documents.get_xray(document_id)`) — per-chunk LLM
  output; shows what each chunk produced before platform aggregation.
  Use `templates/xray_to_extract.py` for local aggregation that
  reproduces what `get_extract()` should return — divergence between
  the two is a strong signal of platform-side aggregation issues.
- **Workflow JSON** (compiled output of `compile_workflow.py`) — what
  was actually submitted to the platform. Use
  `templates/validate_workflow_json.py` for structural shape checks.
- **`run.log`** — JSONL event timeline from a `run_extraction.py`
  invocation. Useful for reconstructing the timing and ordering of
  the run after a sub-agent terminates.
- **`compare-report.txt`** — per-field PASS/FAIL diff against the
  answer key. Identifies which fields regressed.

## 10.4 Relationship failures

When a meter, charge, line item, or other related record is missing,
duplicated, or attached to the wrong parent, debug the relationship before
rewriting prompts:

1. Inspect the source document and find the printed values that should link the
   records.
2. Inspect X-Ray to see whether those values were parsed and extracted.
3. Check whether the answer key uses the printed value or a normalized system
   value.
4. Check the final JSON shape and the final-group metadata that drives dedupe,
   matching, conflict surfacing, and passthrough.
5. Check any custom manager code that passes metadata into reconcile, QA, or
   post-extraction logic.

Common evidence problems include OCR or model ambiguity (`I` vs `1`, `O` vs
`0`), a value appearing on one page but not the page that contains the related
record, and an answer key that stores a customer system value instead of the
printed document value.

## 10.5 Prompt-manager debug loop

For quickstart-style projects that use `manager.py`, `simple.yaml`, and
extract/reconcile/QA prompt modules, debug the run before rewriting prompts:

1. Check processing status and confirm the document completed.
2. Retrieve `get_extract` and inspect the structured result.
3. Retrieve `get_xray` and inspect the source chunk evidence.
4. Compare the initial extraction result shape against the expected output shape.
5. Use section summary, suggested text, and chunk evidence to decide whether the
   YAML field prompt, extract wrapper, reconcile prompt, or QA prompt needs the
   change.

This keeps the today-path manager executable while preserving the future goal:
one YAML-driven `groundx-python/extract` abstraction.

## 10.6 Cross-references

- `references/9_testing_methodology.md` — verifying changes work
  proactively; this reference is for investigating why they don't
- `references/6_known_limitations.md` — platform-locked field names
  (AGE-6) and convention ambiguities (AGE-7); escalation playbook
- `templates/validate_workflow_json.py` — structural validator
  codified from the v0.1.2 bug
- `references/prompt-manager.md` — minimal today-path manager for
  quickstart-style prompt modules
- `CHANGELOG.md` `[0.1.2]` entry — full bug narrative
