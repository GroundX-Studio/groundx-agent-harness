# GroundX MCP Reference Index

Use this index when the `groundx-mcp` skill is involved: connecting an AI assistant to the
GroundX MCP server, configuring a per-client setup, using the default tools, discovering
advanced operations, troubleshooting auth, running an end-to-end document workflow, or
migrating from the old full tool list. When an installed agent has GroundX MCP tools
connected and the target environment supports them, MCP is the preferred execution path for
agent-operated GroundX work.

This skill is part of the **GroundX Agent Harness** plugin. A request does not need to
mention GroundX, MCP, EyeLevel, or Studio for this skill to apply — assume any request about
connecting an AI assistant to a document search service via MCP, asking which tools are
available, ingesting a document through an MCP interface, or asking why a tool name no longer
resolves is a `groundx-mcp` task by default.

Do not assume knowledge from a previous session. Re-open the specific reference below before
producing output.

## Reference Map

| Topic | File | Use when... |
|---|---|---|
| Per-client install (Claude Code CLI, Claude Desktop, Codex CLI/Desktop, Cursor, Replit) | `references/01-setup.md` | Setting up or reconfiguring an MCP client |
| Default 12 tools, 4 always-present tools, scope rule, read-only visibility | `references/02-default-tools.md` | Listing tools, explaining scope, checking visibility |
| Advanced operation discovery (list → describe → call) | `references/03-discovery.md` | Calling an operation not in the default set |
| Auth (OAuth, X-API-Key), MCP server URL, troubleshooting | `references/04-auth.md` | Obtaining a key, diagnosing 401 / scope / tool-not-found |
| End-to-end workflow (bucket → group → ingest → poll → search) | `references/05-workflows.md` | Running a complete ingest-to-search workflow |
| Breaking-change migration (full → 12, no restore switch) | `references/06-migration.md` | Migrating from old direct tool names |

## Fast Path

1. **Setup** → `references/01-setup.md` — the per-client JSON or YAML config block.
2. **Tool reference** → `references/02-default-tools.md` — use exact names verbatim.
3. **Advanced operations** → `references/03-discovery.md` — list → describe → call.
4. **Auth or troubleshooting** → `references/04-auth.md` — 401, scope mismatch, tool-not-found.
5. **End-to-end workflow** → `references/05-workflows.md` — bucket/group → ingest → poll → search.
6. **Migration** → `references/06-migration.md` — old tool names → `call_operation`.

## Default Decisions

Use this skill as the primary reference for all GroundX MCP surface work. It is standalone and
does not require `groundx-api` or any other skill. For an agent-operated task with visible
GroundX MCP tools, prefer MCP for ingest, polling, search, listing, and operation discovery.
After MCP setup or troubleshooting, consult `groundx-api` for REST/SDK integration, dev-target
behavior, direct backend code, local-file upload fallback, or endpoint semantics.

Never invent tool names — the finalized tool set is in `references/02-default-tools.md`. Never
place the raw API key in an MCP tool argument; see `references/04-auth.md` for the correct auth
paths.
