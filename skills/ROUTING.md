# GroundX Agent Harness Skill Routing

Use this file as the public installed-agent routing tree. Pick the first-entry skill
here, then open that skill's `SKILL.md` and follow its reference map.

## GroundX API Work

Start with `groundx-api` for customer-scoped GroundX API behavior: authentication,
document ingest, search, grounded answers, buckets, groups, workflows, status polling,
source retrieval, extraction retrieval, and SDK or REST fallback.

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

## Not Included

This public bundle does not include internal managed-project publishing, web UI scaffold
implementation, slide production, Partner-only API lifecycle operations, or local Studio
MCP lifecycle tools.
