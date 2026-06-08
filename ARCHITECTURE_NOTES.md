# Architecture Notes — groundx-agent-harness

> Onboarding notes. Last updated: 2026-06-07. Lens: mapping this repo as a **node in a cross-repo dependency graph** and assessing its AI-first conversion. Priorities: (a) the bundle's exposed contract, (b) the bundle's gate/rules, (c) cross-repo dependencies & duplication, (d) external endpoints it points at.

## What this system does
This is **not a runnable application** — it's a *knowledge/skills plugin* that teaches Claude and Codex how to help users work with the GroundX platform (a document-ingest / RAG / schema-first-extraction product by EyeLevel/Valantor). The deliverable is Markdown content: 7 "skills," each a folder of `SKILL.md` + reference docs that an agent loads on demand. Live authenticated API calls happen through a **separate hosted MCP server** (`https://api.groundx.ai/mcp`); this repo only supplies the agent's instructions, workflows, and reference knowledge.

## Stack
- **Languages:** Markdown (the product); JavaScript (ES modules, `.mjs`) for 2 helper scripts only.
- **Frameworks / runtimes:** Node.js ≥20 (CI + scripts; stdlib only, **no `package.json`, no deps**). Consumed at runtime by Claude Code / Codex plugin loaders + MCP.
- **Datastores / infra:** None in-repo. (GroundX platform itself uses OpenSearch, MinIO/S3, Percona, Kafka/Strimzi, SQS — referenced only in on-prem docs.)
- **Notable dependencies:** External, by reference — the published `groundx` PyPI SDK and the `eyelevelai/groundx-python` repo (see Cross-repo section).

## Directory map
| Path | Responsibility |
|------|----------------|
| `skills/` | ★ The product. 7 skill folders + `ROUTING.md` dispatch tree. All knowledge lives here. |
| `scripts/` | `doctor.mjs` (prints install help, no side effects) + `validate-public-bundle.mjs` (the CI gate). |
| `.claude-plugin/marketplace.json` | Claude install contract: bundle name, version, ordered skill list. |
| `.codex-plugin/plugin.json` | Codex install contract: same bundle, Codex manifest format + UI interface metadata. |
| `.agents/plugins/marketplace.json` | Agent-platform marketplace variant (install/auth policy: `AVAILABLE` / `ON_INSTALL`). |
| `.github/workflows/validate.yml` | CI: Node 20 → runs `validate-public-bundle.mjs` on push/PR/dispatch. |
| `.groundx-generated.json` | Provenance: marks repo as a **generated mirror** of a private upstream (see below). |
| `README.md` | Per-client install + MCP-connect + verification guide. |
| `LICENSE` | MIT. |

## Entry points
There is no `main()`. "Entry points" are dispatch/install surfaces:
- `skills/ROUTING.md` — the agent's router: pick first-matching skill → open its `SKILL.md` → follow its reference map.
- `skills/*/SKILL.md` — per-skill entry; YAML frontmatter (`name` + `description`) drives when the agent invokes it.
- The 3 manifests — entry points for the *installer* (which skills ship, version, policy).
- `scripts/doctor.mjs` — the only human-runnable CLI entry.

## Running it locally
```bash
# the only two executable commands in the repo:
node scripts/doctor.mjs                  # print install / verification help (optionally pass a client name)
node scripts/validate-public-bundle.mjs  # the "test" — bundle integrity gate (exit 1 on any violation)
#   --allow-missing-provenance           # skips the .groundx-generated.json requirement
```
"Running for real" = install as a plugin in Claude/Codex (per README) + connect the MCP server. No build step, no env vars needed to validate.

---

## (a) Bundle contract — what this repo exposes
Bundle name (constant across all manifests): **`groundx-agent-harness`**, version **2.1.3**.
Three parallel manifests describe the same bundle to three loaders:
- **Claude** (`.claude-plugin/marketplace.json`): `plugins[0]` with `source: "./"`, `strict: false`, and an **explicit ordered `skills` array** (7 paths).
- **Codex** (`.codex-plugin/plugin.json`): `skills: "./skills/"` (directory, not list) + rich `interface` block (displayName, capabilities, defaultPrompt, brandColor `#29335c`).
- **Agents marketplace** (`.agents/plugins/marketplace.json`): `source.local ./`, `policy {installation: AVAILABLE, authentication: ON_INSTALL}`.

**Shipped skills (the public surface — 7):**
1. `groundx-api` — customer-scoped API: ingest, search, RAG, buckets, groups, workflows, status, source/extraction retrieval, SDK+REST fallback. *Central skill; others delegate execution here.*
2. `groundx-extraction-workflows` — schema-first extraction (YAML→compiled workflow JSON); largest skill (37 files); has templates + CHANGELOG.
3. `groundx-on-prem` — deployment/Helm/values.yaml/cluster sizing/air-gapped/OpenShift.
4. `groundx-architecture` — how GroundX works; pipeline shape, trust model, due-diligence facts.
5. `product-brand-gtm` — GroundX product positioning/messaging.
6. `master-brand-gtm` — Valantor master-brand / category framing.
7. `groundx-python` — guidance for *contributing to* the `eyelevelai/groundx-python` SDK repo.

MCP is **intentionally NOT bundled** — connected separately by the user. The gate actively forbids manifests from declaring `mcpServers`/`apps` (keeps plugin and MCP as separate pieces).

## (b) Bundle rules / the gate — `scripts/validate-public-bundle.mjs`
This is the repo's **agent boundary / publication gate**. It enforces that the public mirror leaks nothing private. Key rules:
- **Required files present:** the 3 manifests, `validate.yml`, `.gitignore`, `LICENSE`, `README.md`, both scripts, `skills/ROUTING.md`. Each Claude-listed skill must have `SKILL.md` **and** `references/README.md`.
- **Required provenance:** `.groundx-generated.json` must exist (unless `--allow-missing-provenance`) with non-empty `sourceRepository`, `sourceCommit`, `generatedBundlePath`, `generator`, `bundlePolicy`, `generatedAt`. `sourceRepository` must NOT embed credentials.
- **Manifest invariants:** Codex/Claude/agents names must all equal `groundx-agent-harness`; Codex `skills` must be `"./skills/"`; manifests must NOT expose `mcpServers` or `apps`.
- **README invariants:** must contain `/reload-plugins`, `### Claude Code Desktop`, `Organization plugin sync`, `Personal plugins`, `GroundX-Studio/groundx-agent-harness`.
- **Forbidden paths (must be absent):** `.mcp.json`, `.app.json`, `servers/groundx-studio`, `openspec/{work,private,runs,artifacts}`, anything under `evals/`.
- **Forbidden text scan** (over `.json/.md/.mjs/.js/.ts/.tsx/.yaml/.yml/.txt` + extensionless): blocks 18 internal-surface strings — e.g. `harness-publish`, `harness-web-ui`, `harness-slides`, `groundx-partner-api`, `WORKSPACE_API_KEY`, `PARTNER_API_KEY`, `git_session`, `project_create`, `Partner-only APIs`, `managed-project lifecycle`, etc. → reveals the **private superset** this is carved out of.
- **Secret scan:** rejects GitHub token shapes (`ghs_`, `ghp_`, `github_pat_`, `x-access-token:…@`).
- Exits 0 with `✓` or 1 listing every violation. This script is **self-excluded** from the text scan.

## (c) Cross-repo dependencies & duplication
This repo is a **generated leaf** in the GroundX graph — it points at others, is generated from another, and does NOT vendor their code (refers, doesn't duplicate):
- **Upstream (generator source):** `.groundx-generated.json` → generated from **private** `github.com/EyeLevel-ai/groundx-studio-harness` via `scripts/sync-plugin.mjs`, bundle path `plugins/groundx-agent-harness`. Editing here likely gets **overwritten on next sync** — change upstream, not here. ⚠️ verify before editing.
- **groundx-python SDK (runtime dependency, by reference):** `groundx-extraction-workflows` templates deploy via the GroundX Python SDK; install paths `pip install groundx` and `pip install groundx[extract]` (two SDK layers: core + extract submodule). The `groundx-python` skill is explicitly *about contributing to* `eyelevelai/groundx-python` and repeatedly defers to that repo's own `AGENTS.md` (`github.com/eyelevelai/groundx-python/blob/main/AGENTS.md`, 6 refs) as canonical — so it **links, does not copy**. Mentions Fern generator boundary + `.fernignore` (SDK is partly codegen'd).
- **API surface:** `groundx-api` documents endpoints under `api.groundx.ai/api/v1` but treats the **MCP connector as source of truth**, with REST as fallback — so it mirrors API *behavior/shape*, not a vendored OpenAPI spec.
- **on-prem:** references external Helm charts/registries (`registry.groundx.ai/helm`, NVIDIA NGC, OpenSearch, Percona, MinIO operator, Strimzi/Kafka, helm-secrets/sops) — infra dependencies described, not contained.
- **Duplication risk to watch:** API endpoint docs (`groundx-api`) and SDK behavior (`groundx-python`/extraction templates) can drift from the real `groundx-python` SDK and live API — this repo has no automated check that they stay in sync with upstream.

## (d) External endpoints it points at
- **`https://api.groundx.ai/mcp`** — the hosted MCP server (primary integration; 16 refs). Also seen: `api.groundx.ai/api`, `api.groundx.ai/api/v1`, `api.groundx.ai/api/v1/mcp`.
- **REST fallback:** `https://api.groundx.ai/api/v1` with `X-API-Key` header (keys kept out of tool args/logs/examples by policy).
- **EyeLevel upload pipeline (in API/architecture docs):** `upload.eyelevel.ai/layout/...`, `api.eyelevel.ai/upload/file`.
- **on-prem infra registries:** `registry.groundx.ai/helm`, `helm.ngc.nvidia.com/nvidia`, OpenSearch/Percona/MinIO/Strimzi chart repos.
- **Third-party referenced in examples:** `api.openai.com/v1`, `api.deepinfra.com/v1/openai` (summary/extraction engine options); AWS SQS/S3, GCS (pipeline internals in architecture docs). `example.com` URLs are illustrative placeholders.
- **Repo self-reference / install:** `github.com/GroundX-Studio/groundx-agent-harness` (the public mirror).

## Key abstractions / patterns
1. **Skill = folder of Markdown** (`SKILL.md` frontmatter + `references/`). Frontmatter `description` is the trigger contract; `references/README.md` is a required map. Progressive disclosure: agent reads SKILL.md, then drills into references on demand.
2. **Routing tree** (`skills/ROUTING.md`) — deterministic "start with skill X" dispatch; `groundx-api` is the hub others delegate execution to.
3. **Plugin ⟂ MCP separation** — knowledge (this repo) and authenticated tools (MCP) are deliberately decoupled; the gate enforces the boundary.
4. **Generated-mirror + publication gate** — repo is a sanitized projection of a private superset; `validate-public-bundle.mjs` is the enforcement of that projection.

## Where state lives
- No application state in this repo. Build/release state lives upstream (private generator). Runtime auth/data state lives in the GroundX platform behind the MCP/REST endpoints.

## Core data flow — bundle lifecycle (Phase 2, verified)
No request/response runtime in-repo; the representative path is the bundle lifecycle:
```
upstream source → generate/sync → GATE → CI → install (manifest) → runtime route → MCP/REST → GroundX
```
1. **Source (off-repo):** private `EyeLevel-ai/groundx-studio-harness` projected by `scripts/sync-plugin.mjs` (per `.groundx-generated.json`). This repo is the *output*.
2. **Gate:** `scripts/validate-public-bundle.mjs` — `requireFile` loop (118–131), manifest invariants (145–177), `walkFiles()` forbidden-text + secret scan (216–233). **Two callers, different strictness:** CI runs it bare → provenance **required**; `doctor.mjs:validateLocalBundle()` runs it with `--allow-missing-provenance` → tolerant for dev checkouts.
3. **CI:** `.github/workflows/validate.yml` (push/PR/dispatch, Node 20) → the gate. Only automated check in the repo.
4. **Install:** a manifest is the loader's entry; `doctor.mjs` only *prints* per-client install commands (`vscodeClaude()`, `claudeCodeDesktop()`, …) — installs nothing.
5. **Runtime route:** agent loads `ROUTING.md` → picks skill → reads `SKILL.md` → drills into `references/`. `groundx-api` is the execution hub.
6. **Egress:** `groundx-api/SKILL.md` enforces MCP-connector-first → REST fallback via `X-API-Key` only (never `Authorization: Bearer`; keys never in tool args). (verified lines 6–10, 76–78)
7. **GroundX platform:** all real work happens behind the endpoints; nothing executes here.

**Boundaries / seams:** generator boundary (edit upstream, not the mirror) · gate boundary (single chokepoint for "what may be public") · plugin⟂MCP (knowledge here, auth/tools separate; manifests forbidden to declare `mcpServers`) · skill⟂skill (`ROUTING.md` dispatch, `groundx-api` hub).

## Module notes
<To be filled by Phase 3 deep dives. Candidates: `validate-public-bundle.mjs` (line-level gate semantics), `skills/groundx-api/` (egress hub), `skills/groundx-extraction-workflows/` (SDK-coupled templates).>

## Open questions / things I don't understand yet
- [ ] What exactly does the upstream `scripts/sync-plugin.mjs` strip/transform when generating this mirror? (Not in this repo — lives in private `groundx-studio-harness`.)
- [ ] Is there any automated drift check between `groundx-api` endpoint docs / extraction templates and the real `groundx-python` SDK + live API? (None found in-repo — appears manual.)
- [ ] How is the bundle version (2.1.3) bumped — by the upstream generator, or hand-edited across all 3 manifests? Three copies risk skew.
- [ ] `bundlePolicy` references `scripts/plugin/bundle-policy.json` in provenance, but that path is NOT in this public bundle — what rules does it encode upstream?
- [ ] What is the full private superset implied by the 18 forbidden strings (publish/web-ui/slides/partner-api/managed-project)? Useful for the dependency graph — these are sibling capabilities carved out.

## Verified vs. inferred
- **Verified (read directly):** all 3 manifests, full `validate-public-bundle.mjs`, `ROUTING.md`, `.groundx-generated.json`, README; URL/cross-repo greps across `skills/`; file counts per skill.
- **Inferred (not run/seen):** behavior of the upstream generator & `bundle-policy.json` (not in repo); that edits here are overwritten on sync (strongly implied by provenance, not confirmed); that endpoint docs can drift (no sync mechanism found, but absence ≠ proof).
- Not executed: `node scripts/validate-public-bundle.mjs` / `doctor.mjs` (read-only pass; can run on request).
