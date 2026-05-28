# GroundX Architecture Reference Index

Use this index when the public GroundX Agent Harness is installed and the work is
about GroundX architecture: pipeline shape, components, trust model, data flow,
search, extraction architecture, observability, residency, and deployment-invariant
system behavior.

## Fast Path

1. Start in `../SKILL.md` for the public routing contract.
2. Pick the smallest reference below.
3. Use product GTM skills for pitch language and `groundx-on-prem` for deployment
   runbooks or values.yaml.
4. Do not invent facts not present in the references.

## Reference Map

| Need | Read |
| --- | --- |
| End-to-end document flow | `data-flow.md` |
| Vision model and document understanding | `vision-model.md`, `layout-ocr.md` |
| Agentic enrichment | `agentic-pipeline.md` |
| Hybrid search and ranker behavior | `hybrid-search.md`, `search-service.md` |
| Ingest services and component responsibilities | `ingest-service.md` |
| Storage and artifacts | `store.md` |
| Summary service | `summary-service.md` |
| Extraction architecture | `extraction-architecture.md` |
| Cloud vs on-prem model, GPU, Helm, networking, or residency disambiguation | `deployment-mode-disambiguation.md` |
| Trust and credentials | `identity-and-trust.md` |
| Multi-tenancy | `multi-tenancy.md` |
| Data residency | `data-residency.md` |
| Observability | `observability.md` |
| Failure modes and recovery patterns | `failure-modes.md`, `disaster-recovery.md` |

## Deferrals

| Intent | Start with |
| --- | --- |
| Customer API endpoint behavior | `groundx-api` |
| Schema-first extraction workflow authoring | `groundx-extraction-workflows` |
| Kubernetes deployment and operations | `groundx-on-prem` |
| Product/company messaging | `product-brand-gtm` or `master-brand-gtm` |

This public bundle intentionally omits internal scaffold publishing, web UI
implementation, slide-production, and partner-lifecycle skills. If a user asks for
those internal workflows, say the public harness does not include them.
