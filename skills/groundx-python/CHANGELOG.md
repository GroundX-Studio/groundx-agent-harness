# Changelog

All notable changes to the `groundx-python` harness skill are documented here.
The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this skill adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## 0.x — initial development

This skill is in **initial development (0.x)**. Per semver, anything may change
between minor versions in this phase. Each `0.N.0` bump captures a coherent
iteration milestone. The `1.0.0` release will mark the first stable contract.

The skill itself is intentionally thin — it routes agents to the
`eyelevelai/groundx-python` repo's own `AGENTS.md` as the canonical contribution
guide rather than restating contribution rules here. Its job is to discriminate
SDK-repo contribution work from consumer-side SDK usage (`groundx-api`),
extraction-workflow methodology (`groundx-extraction-workflows`), and runtime
architecture questions (`groundx-architecture`).

## 0.1.0 — initial skill (Phase 2 of AGE-65)

**Added**

- `SKILL.md` — frontmatter trigger description for SDK-repo contribution intents
  (file paths under `src/groundx/`, `.fernignore`, `.fern/metadata.json`, extract
  submodule work, Fern boundary), with explicit anti-triggers for consumer-side
  SDK usage (defer to `groundx-api`)
- `references/README.md` — fast-path index with "when not to use this skill"
  table routing to other skills
- `references/01-orientation.md` — three-shapes-of-work disambiguation
  (contributing here vs. using the SDK vs. schema-first extraction), with a
  decision tree and common-confusion examples
- `references/02-core-sdk.md` — Fern boundary summary, `.fernignore` semantics,
  how to coordinate an upstream Fern API-shape change, validation gates →
  routes to repo `AGENTS.md` §1–§3 for canonical rules
- `references/03-extract.md` — extract submodule specifics: hand-written
  surface, optional-dep governance via `.fern/metadata.json`, test layout under
  `tests/extract/` (post-AGE-67), public-API helpers in
  `src/groundx/extract/classes/testing.py` with `__test__ = False` →
  routes to repo `AGENTS.md` §4–§5
- private maintenance reference — source-of-truth boundary (repo wins; skill
  summarizes and routes), cross-skill refactor coordination notes, reusable
  template patterns for the runner-repo AGENTS.md ticket (AGE-63)
- `evals/evals.json` — 6 routing tests: generic SDK-contribution trigger,
  add-an-optional-dep, .fernignore boundary, AGENTS.md-as-canonical, plus
  misuse-prevention tests (consumer-side → `groundx-api`; extraction YAML →
  `groundx-extraction-workflows`)
- Permission Boundaries section in `SKILL.md` (3-tier emoji block) mirroring
  the pattern adopted in the repo's own `AGENTS.md` §10

**Skill registry**

- Added to `skills/routing.manifest.json` (role: `reference`) + new
  `groundx-python-contribution` intent route
- Added to `skills/ROUTING.md` ("Contributing To The GroundX Python SDK Repo"
  section)
- Added to `.claude-plugin/marketplace.json` bundle list
- Added to `scripts/scans/scan-skill-routing.mjs` expected skills
- Added to `scripts/scans/scan-skill-coverage.mjs` coverage map
- Added to `scripts/generate-readme-skills.mjs` summaries (regenerates the
  README skill table)

**Refactor**

- `groundx-api/SKILL.md` — Routing Contract `Deferrals` extended to defer
  SDK-repo contribution work here
- `groundx-api/references/12-python-sdk-objects.md` — scope note added at top
  distinguishing CONTRIBUTORS (→ this skill) from USERS (stay in groundx-api)

**Removed**

- An empty stub skill directory from a deprecated naming (predecessor of
  `groundx-extraction-workflows`) — contained only compiled Python cache
  files, no `SKILL.md`, never registered in the routing manifest, and was
  failing the discoverability scanner. Schema-first extraction methodology
  lives in `groundx-extraction-workflows`.

**Plugin version**

- Bumped harness plugin version `2.0.3` → `2.1.0` (additive feature — new
  skill in the bundle)

## When to bump

This skill follows the harness plugin's overall versioning, but the skill-local
changes that should be reflected here:

- **Patch (`0.N.M+1`)** — wording fixes, broken-link fixes, polish that doesn't
  change routing or content surface
- **Minor (`0.N+1.0`)** — new references, new routing rules, new eval tests,
  retired references, changed deferrals
- **Major (`N+1.0.0`)** — only when this skill becomes stable (`1.0.0`)
  and beyond, for genuinely breaking changes to the routing contract
