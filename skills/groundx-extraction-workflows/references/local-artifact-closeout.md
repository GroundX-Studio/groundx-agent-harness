# Local Artifact Closeout

Use this procedure whenever an extraction instruction creates local outputs: run
directories, `--out` trees, X-Ray files, prompt captures, trace copies, scoring output, or
comparison bundles. Git ignore rules keep data out of commits; they do not remove it.

## Planned Harness Work

For an OpenSpec change owned by the GroundX Studio Harness, initialize before the first
producer creates a directory:

```bash
RUN_ROOT="$(node scripts/init-openspec-work.mjs \
  --change <change-id> --run <run-id> --owner <owner> \
  --reason <reason> --expires <future-ISO-8601>)"
```

Run this from the Harness Git checkout. The helper finds that checkout from its own script,
registers planned work, and prints an absolute path. Pass only that path or a child of it to
each artifact-producing `--out`, run-directory, prompt-capture, trace-copy, or evidence
argument. These Node helpers exist only in the Harness source checkout; when they are absent
or another repository owns the change, use the manual linked-repository sequence below. Do
not use a caller-relative path or a shared directory.

Before cleanup, move only reviewed deliverables to an approved destination and record the
handoff while settling the run:

```bash
node scripts/update-openspec-work.mjs --change <change-id> --run <run-id> \
  --state <accepted|rejected|superseded> --disposition <final-decision>
```

If work is still active, resumable, failed without a decision, or pending review, keep the
plan open and record its owner, reason, and future expiry. Do not delete evidence needed for
that decision.

Then preview, apply, and verify exact cleanup:

```bash
node scripts/close-openspec-work.mjs --change <change-id>
node scripts/close-openspec-work.mjs --change <change-id> --apply
node scripts/close-openspec-work.mjs --change <change-id> --check
```

The retained local form is a bounded lifecycle-only summary under ignored
`openspec/runs/<change-id>/`, plus a small tracked closeout receipt. Raw evidence is not
copied into either. Free-form lifecycle values are retained only as opaque semantic
SHA-256 digests, and validated state history prevents a hand-edited final state from
bypassing transition rules. Archive through `node scripts/archive-openspec-change.mjs --change
<change-id>` only after the check passes.

## Artifact Disposition

| Artifact class | Final disposition |
| --- | --- |
| User-owned source or credential outside the run root | Never delete |
| Run-owned source or credential copy inside the run root | Exclude from summaries; delete with the run root |
| Reviewed YAML, user-requested final JSON, accepted accuracy decision, promoted fixture, or review record | Hand off to a named approved location and record its digest/proof |
| Raw output, X-Ray, prompt, model response, trace, log, timeout history, intermediate output, or comparison bundle | Delete with the run root unless the user explicitly requested that raw deliverable and selected its destination |
| Bounded outcomes, provenance, first failing stage, cleanup counts, and aggregate content digest | Retain in the local summary |
| Hosted evidence or service staging | Follow the owning service lifecycle; do not count local cleanup as hosted cleanup |

Approved handoffs are a sanitized nonignored tracked repo file, the bounded closeout
summary, hosted storage with lifecycle or deletion proof, or an external local path the
user explicitly selected. Another ignored repo directory—including `openspec/private/` or
`openspec/artifacts/`—is not a durable handoff.

## Ad-Hoc Or Linked-Repository Work

The Harness helpers above are root-locked. Do not call them for work owned by another repo
or for an ad-hoc directory. Use this manual sequence in the owning Git repository:

1. Choose one dedicated `<owning-git-root>/openspec/work/<change-id>/<run-id>/` root before
   writing and record its owner, reason, and future expiry.
2. Confirm that exact work root and `openspec/runs/<change-id>/` are ignored with
   `git check-ignore --no-index`, while the tracked change and receipt paths are not.
3. Pass the absolute run root to every producer. Keep user-owned inputs outside it.
4. Record a final accepted, rejected, or superseded disposition. Hand off reviewed outputs
   only to one of the approved destinations above.
5. Create a lifecycle-only summary no larger than 256 KiB per file or 10 MiB per change.
   Exclude source content, prompts, responses, X-Ray content, raw traces/logs, credentials,
   signed URLs, and copied reports.
6. Preview the exact removal target and file/byte totals. Remove only the settled run root,
   verify it is absent, and preserve unrelated work.
7. Write a bounded tracked receipt containing only change ID, closeout time, cleanup state,
   counts, absence proof, and the summary digest. Gate archive on that receipt.
8. Keep archived summaries for at least 90 days. Prune only when one canonical archive date
   is older than 90 days and its tracked receipt digest matches the local summary.

For a non-plan ad-hoc run, use the same dedicated-root, inventory, handoff, exact removal,
absence-check, and final-report sequence, but do not invent OpenSpec metadata or route the
arbitrary directory to a plan cleanup helper.

## Final Report

Before returning, report:

- the exact local root removed and its file/byte count;
- each durable handoff retained and its owner;
- the summary/receipt state; and
- every local root intentionally left in place, with owner, reason, and expiry.
