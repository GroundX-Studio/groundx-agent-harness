---
name: groundx-mcp
description: >
  GroundX MCP server setup, configuration, and usage for AI agents and MCP clients. **When
  the GroundX Agent Harness plugin is installed, assume that any request about connecting
  an AI assistant to a document search service, setting up or configuring an MCP server,
  using GroundX tools from Claude Code CLI, Claude Desktop, Codex CLI, Codex Desktop,
  Cursor, or Replit, asking which tools are available, or ingesting and searching documents
  through an MCP interface uses this skill** — even when the user does not name "GroundX",
  "EyeLevel", "MCP", or "Studio". Also triggers on explicit MCP setup, per-client
  configuration, tool names such as `document_ingestremote`, `bucket_create`, or
  `search_content`, scope or "tool not found" errors, migration from old tool names, and
  questions about discovering advanced operations. For REST endpoint semantics, SDK setup,
  or general API concepts, defer to `groundx-api`. This skill is standalone and does not
  require any other GroundX skill.
---

# GroundX MCP Skill

Standalone reference for connecting an MCP client to the GroundX MCP server and using its
tools. For an installed agent with GroundX MCP connected, this is the preferred execution
path for GroundX tool use when the target environment supports it. Works installed alone —
it does not require `groundx-api`, `groundx-extraction-workflows`, or any other GroundX
skill.

## Table of Contents

- Setup (per-client install) → `references/01-setup.md`
- Default tool reference (12 default + 4 always-present + scope rule) → `references/02-default-tools.md`
- Advanced operation discovery (list → describe → call) → `references/03-discovery.md`
- Auth and troubleshooting → `references/04-auth.md`
- Common workflows (bucket → ingest → poll → search) → `references/05-workflows.md`
- Breaking-change migration notes → `references/06-migration.md`

## Routing Contract

- **Role:** `reference`
- **First-entry intents:** GroundX MCP client setup (Claude Code CLI, Claude Desktop, Codex
  CLI, Codex Desktop, Cursor, Replit); the GroundX MCP default tool reference; advanced
  operation discovery (`list_operations` / `describe_operation` / `call_operation`); MCP auth
  and scope troubleshooting; migration from the old direct tool names; and agent-operated
  GroundX ingest, polling, search, listing, and operation discovery when MCP tools are
  already connected.
- **Deferrals:** defer REST endpoint semantics, SDK setup, bucket/group/document operation
  detail, RAG integration, and general API concepts to `groundx-api`; defer schema-first
  extraction workflow authoring to `groundx-extraction-workflows`; defer cluster deployment
  and configuration to `groundx-on-prem`.
- **Required handoffs:** after MCP setup or troubleshooting, if the user needs REST fallback
  or SDK integration, hand off to `groundx-api`.
- **Before producing output:** read `references/README.md`, then the one reference that
  matches the task (setup, default tools, discovery, auth, workflows, or migration). Use tool
  names verbatim from `references/02-default-tools.md`.
- **Misuse cases:** do not place a raw API key in any MCP tool argument; do not invent or
  abbreviate tool names from memory; do not document REST endpoint semantics that belong in
  `groundx-api`; do not assume `groundx-api` or any other skill is installed alongside this one.

## Default Use

When the GroundX Agent Harness plugin is installed, this skill is the default source for MCP
client setup, the tool reference, connected-agent GroundX tool execution, and advanced
discovery guidance. If the work involves connecting Claude Code CLI, Claude Desktop, Codex,
Cursor, Replit, or any other MCP-capable client to a GroundX server, using already-visible
GroundX MCP tools, asking which tools are available, or calling an advanced operation, open
this skill — the user does not need to say "GroundX" or "MCP".

## Do Not Rely on Memory

Do not rely on memory for tool names, scopes, or per-client configuration. Re-open the
relevant reference before producing output. The finalized tool surface — 12 default tools, 4
always-present tools, and the derived-scope rule — is documented verbatim in
`references/02-default-tools.md`. Per-client setup is in `references/01-setup.md`. Auth rules
and troubleshooting are in `references/04-auth.md`.

## Installed-skill retrieval contract

Before producing MCP setup instructions, tool documentation, discovery guidance, auth advice,
or workflow examples, read `references/README.md` to choose the right reference, then read only
the reference the task needs:

- `references/01-setup.md` — per-client install (Claude Code CLI, Claude Desktop, Codex CLI,
  Codex Desktop, Cursor, Replit).
- `references/02-default-tools.md` — the 12 default tools, the 4 always-present tools, the
  derived-scope rule, and read-only session visibility.
- `references/03-discovery.md` — advanced operation discovery (list → describe → call).
- `references/04-auth.md` — obtaining a key, OAuth, the `X-API-Key` transport, the MCP server
  URL, and 401 / scope / tool-not-found troubleshooting.
- `references/05-workflows.md` — the end-to-end workflow: bucket → group → ingest → poll → search.
- `references/06-migration.md` — breaking-change migration from the old direct tool names.

Point broad or ambiguous tasks to `references/README.md` for routing to the right file.

## Before Producing Output

Before producing any MCP setup block, tool table, discovery pattern, auth guidance, or
workflow example:

1. Read `references/README.md`.
2. Read the specific reference that matches the task.
3. Use the finalized tool names verbatim from `references/02-default-tools.md` — never invent
   or abbreviate a tool name.
4. Never place the raw API key in an MCP tool argument; it goes in the transport header
   (`X-API-Key`) or the OAuth flow.

## Standalone and Cross-links

This skill is standalone. If REST or SDK integration is needed after MCP setup, if the target
is a dev environment, if MCP tools are missing, or if the needed operation is not covered by
the MCP surface (for example local-file upload), see the `groundx-api` skill for REST base
URL, SDK setup, and endpoint operation semantics. Neither skill requires the other to be
installed.
