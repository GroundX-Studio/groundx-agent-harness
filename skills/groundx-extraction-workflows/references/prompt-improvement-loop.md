# Prompt Improvement Loop

Before any command here creates local output, read [`local-artifact-closeout.md`](./local-artifact-closeout.md). Planned work must initialize and use its exact absolute run root. Ad-hoc work uses one dedicated root. Settle or hand off useful results, delete raw evidence, verify absence, and report what remains.

Use this guide when extraction output is missing, wrong, or weaker than the expected
quality bar.

For current live runs, score the raw GroundX `get_extract` response captured as
`output.json`. Treat X-Ray as diagnostic evidence, not as a second output or an input
for local reconstruction.

## What Looping Means

Looping is the repeated process of diagnosing one problem, making one change, compiling,
running or rescoring, and checking whether the change improved the result without a
regression.

One loop is:

1. Pick one field or one group rule.
2. Locate the source evidence in the document and X-Ray.
3. Compare source evidence, expected answer, raw `get_extract` output, and X-Ray evidence.
4. Source-adjudicate disagreements before changing YAML.
5. Classify the miss.
6. Change one prompt or one group rule.
7. Compile and inspect the prompt diff.
8. Run or rescore.
9. Score the result.
10. Record artifacts, accuracy delta, and the next decision.

## Classify the miss

Use the smallest category that explains the failure:

- **Prompt quality**: the source has the value, but the prompt did not explain how to
  identify or choose it.
- **Group prompt**: record selection or shared group rules are wrong.
- **Expected-answer issue**: the expected value is unsupported, normalized differently,
  or mapped to the wrong field.
- **X-Ray issue**: the source evidence is missing or OCR/layout did not capture it.
- **Hosted identity or relationship behavior**: raw extraction does not reflect
  supported YAML identity or relationship intent.
- **Platform behavior**: workflow execution, image evidence, or runtime behavior blocked
  the right result.

## Debug Decision Tree

Use this before changing YAML:

1. If the expected answer and extraction disagree, inspect the source document first.
   Expected-answer issues include unsupported values, wrong field mapping, or different
   normalization. If the expected answer is not source-supported, fix the expected answer
   or mark the field unscoreable. Do not change the prompt.
2. If the source document does not contain the value, return or expect null. Do not
   prompt around a value that is not there.
3. If X-Ray is missing the source evidence, classify this as X-Ray issues or platform
   behavior. Do not keep tightening prompts until the source evidence is available.
4. If X-Ray has the source evidence and raw extract is wrong, fix one field prompt or
   one group prompt rule.
5. If raw extract omits supported identity or relationship behavior, preserve
   the raw artifact and file a product defect in the owning repository. Do not
   add a Harness mutation fallback.
6. If raw extract is missing, `progress.errors` is populated, or the run never reaches
   extract retrieval, debug runtime processing failures before scoring or changing
   prompts.
7. If captured rendered request evidence does not contain the YAML rule you changed,
   fix the server authoring path or stale workflow before running again.

## One change per loop

Make one meaningful change per loop. Examples:

- tighten one field's exclusion rule
- add one representative identifier
- move one shared rule to group-level `prompt.instructions`
- adjust one expected-answer mapping after source-adjudication

Do not rewrite a whole group because one field failed. If several fields fail for the
same reason, fix the shared group rule and record that decision.

## Run or rescore

Choose the cheapest valid verification:

- If only expected-answer mapping changed, rescore existing output.
- If YAML prompts changed, run server validation, register, and run the workflow again.
- If raw X-Ray already proves the platform missed source evidence, do not keep
  rewriting prompts.

Inspect captured rendered request evidence before judging prompt propagation. A YAML
edit that does not reach the model request cannot improve extraction.

## Source-adjudicate before scoring

When expected answers and extraction disagree, inspect the source document before calling
it a miss. Record:

- field path
- source location
- expected value
- extracted value
- source-supported value
- scoreability decision
- rationale

Only count true source-supported misses against prompt quality.

## Stop Conditions

Stop looping and escalate or hand off when:

- the same field does not improve after a clear prompt fix
- a new run causes a regression in fields that previously passed
- the miss is caused by missing source evidence in X-Ray
- the expected answer is not source-supported
- the prompt would need sample-specific wording to pass
- the workflow shape or hosted identity/relationship behavior is the real problem

## Artifacts

Keep enough artifacts that another agent can continue without guessing:

- source PDF or source reference
- prompt.yaml diff
- server workflow readback and captured rendered request excerpt
- raw GroundX `get_extract` output (`output.json`)
- X-Ray or diagnostic output
- score report
- source-adjudicated discrepancy list
- loop notes with hypothesis, change, result, regression check, and next step

## Good loop note

```text
Field: effective_date
Problem: raw `get_extract` output used a signature date.
Source evidence: page with selected effective-date option.
Change: field instructions now exclude signature/revision dates and require selected option evidence.
Result: field passed; no regression in related date fields.
Next: continue to next true miss.
```

## Weak loop note

```text
Improved dates.
```

This is not enough. It does not say what changed, why, what was verified, or whether
anything regressed.
