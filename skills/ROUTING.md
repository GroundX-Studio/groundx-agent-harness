# GroundX Agent Harness Skill Routing

Use this file as the public installed-agent routing tree. Pick the first-entry skill
here, then open that skill's `SKILL.md` and follow its reference map.

For any answer, ticket, install guide, RFP response, or technical handoff written to a
human engineer, apply [`RESPONSE_STYLE.md`](./RESPONSE_STYLE.md): lead with the answer,
keep it brief by default, use plain English, and omit internal harness logistics unless
they are the work.

## GroundX MCP Setup And Tools

Start with `groundx-mcp` for connecting an AI assistant or MCP client to the GroundX MCP
server: per-client setup (Claude Code CLI, Claude Desktop, Codex CLI, Codex Desktop,
Cursor, Replit), the default tool reference, advanced operation discovery, auth and scope
troubleshooting, and migration from old tool names. It is standalone; use `groundx-api`
for REST endpoint semantics and SDK setup once MCP is connected.

## GroundX API Work

Start with `groundx-api` for customer-scoped GroundX API behavior: authentication,
document ingest, search, grounded answers, buckets, groups, workflows, status polling,
source retrieval, extraction retrieval, and SDK or REST fallback. For MCP client setup
and the MCP tool reference, see `groundx-mcp`.

## Structured Extraction Work

Start with `groundx-extraction-workflows` for schema-first extraction: drafting or
iterating extraction YAML, compiling workflow JSON, comparing output to ground truth,
debugging fields, or planning a serious extraction pilot. It delegates platform API
execution back to `groundx-api`.

## GroundX Deployment

Start with `groundx-on-prem` for deployment planning, values.yaml authoring, cluster
sizing, air-gapped operation, OpenShift, upgrades, monitoring, troubleshooting, OCR mode,
summary engine selection, and Kubernetes operational questions.

## Architecture Questions

Start with `groundx-architecture` for how GroundX works, pipeline shape, trust model,
data residency, observability, system components, and technical due diligence facts.
Use `groundx-on-prem` for deployment-specific runbooks and `groundx-api` for endpoint
behavior.

## Product And Company Messaging

Start with `product-brand-gtm` for GroundX product positioning, value propositions,
proof points, buyer framing, objections, and product-level copy. Start with
`master-brand-gtm` for Valantor company/category framing, Visual Intelligence,
AI-plus-humans accountability, and master-brand value props.
