# Vendor-Risk Trust Review

Use this reference for vendor-risk, CISO, procurement, subprocessor, and security
questionnaires that ask about the hosted GroundX service. It is a routing map and
claim-status table, not a substitute for legal, compliance, or contract approval.

## 1. Status Labels

Use these labels in answers:

| Label | Meaning |
| --- | --- |
| Held | Confirmed current posture in the architecture references. |
| In progress | Confirmed as underway, not complete. |
| Not held | Confirmed not currently held by the hosted cloud service. |
| Deployer-attested | Available only when the on-prem deployer certifies or operates it. |
| Customer-contract-specific | Not a public/default architecture commitment. |
| Source-pending | A likely questionnaire field, but this skill has no approved source. |
| Unknown | The available sources do not answer the question. |

Do not turn source-pending or unknown into a confident claim.

## 2. Approval And Freshness

Compliance and certification status is owned by the Security / Compliance / Legal
owner or a named delegate, not by this architecture skill. This reference may route
agents to approved architecture facts, but it is not itself an external-use approval.

Before using compliance claims in a vendor-risk, procurement, security review, or other
external answer, confirm these fields with the owning team:

| Field | Required meaning |
| --- | --- |
| Owner | Security / Compliance / Legal owner or named delegate responsible for the claim. |
| Approval scope | Internal architecture, customer-facing, vendor-risk approved, or contract-specific. |
| Last verified | Exact date the owner confirmed the status. |
| Source artifact | Approved compliance artifact, attestation, control statement, or owner-approved source. |
| Review cadence | When the claim must be refreshed, including after certification or deployment changes. |

If those fields are missing, say the architecture reference has an internal source for
the platform fact but external use requires owner confirmation.

## 3. Read Order

1. `identity-and-trust.md` for auth, trust boundaries, missing native controls, audit log,
   and API security posture.
2. `observability.md` for logs, metrics, traces, health checks, alerts, and SLO posture.
3. `data-residency.md` for region, deletion, audit retention, and compliance status.
4. `multi-tenancy.md` for tenant isolation and partner blast radius.
5. `disaster-recovery.md` for cloud-service recovery utilities and what on-prem deployers
   must provide themselves.

## 4. Hosted-Service Operator Facts

| Question | Answer status | Current answer |
| --- | --- | --- |
| Who operates the hosted cloud deployment? | Source-pending | Existing references say GroundX SRE owns the cloud deployment's DR posture and cloud alerts route through the GroundX cloud-service stack. They do not provide an approved legal/operator entity label for questionnaire use. |
| Change categories / change classification | Source-pending | Do not invent categories such as standard, emergency, major, or minor. |
| Issue tracker or ticketing system | Source-pending | Do not name Jira, Linear, GitHub Issues, or another tool without an approved source. |
| Source control / CI ownership | Source-pending | Do not name a provider or access model from memory. |
| Employee vs contractor control parity | Source-pending | Do not claim parity, background checks, training, or access review cadence without source approval. |
| Deployment access posture | Source-pending | Do not claim who can deploy, approve, break glass, or access production without source approval. |
| Vulnerability management / pen testing | Source-pending | Do not invent scanner, cadence, SLA, pen-test, or remediation commitments. |

When asked for any source-pending operator fact, answer plainly: "This architecture
reference does not currently source that fact; confirm with the cloud-service compliance
or operations owner before external use."

## 5. Hosted-Cloud Operations Stack

| Area | Status | Sourced answer |
| --- | --- | --- |
| Logs | Held | Cloud service logs land in CloudWatch; on-prem logs are stdout collected by the deployer. Log format is partially migrated to JSON structured. Source: `observability.md`. |
| Metrics | Held | Pods write metric data to Redis; the `metrics` pod exposes Prometheus-compatible metrics. Cloud consumes that surface through Prometheus/Grafana; on-prem uses deployer wiring. Source: `observability.md`. |
| Traces | In progress | OpenTelemetry is the chosen tracing stack, but coverage is partial and migration is in progress. Source: `observability.md`. |
| Health checks | Held | `GET /v1/health` reports search and ingest status, refreshed every 5 minutes by `UpdateHealthStatus` in the cloud service. Source: `observability.md`. |
| Alerts | Held, limited | Hosted-cloud alerts route through internal operator alerting, including stuck-document monitor critical errors. Source: `observability.md` and `disaster-recovery.md`. |
| Pipeline self-healing | Held for cloud service | A cloud stuck-document monitor re-routes stuck ingest documents past layout/extract cutoffs. On-prem deployers need an equivalent. Source: `disaster-recovery.md`. |
| Paging / on-call tool | Source-pending | Do not name PagerDuty, Opsgenie, chat-only paging, or an on-call process without an approved source. |
| SIEM / threat detection | Source-pending | Do not claim a SIEM, EDR, or threat-detection stack without an approved source. |
| Public SLOs | Not held | No public SLOs are committed in this skill; customer-contract specifics live in operational agreements. Source: `observability.md`. |

## 6. Compliance Posture

| Claim | Status | Scope | Freshness / approval |
| --- | --- | --- | --- |
| SOC2 Type 1 | Held | GroundX cloud-service production. Source: `data-residency.md`. | Architecture-source backed; no external-use owner/date is recorded in this harness. Confirm with Security / Compliance / Legal before vendor-risk use. |
| HIPAA | Held | GroundX cloud-service production. Source: `data-residency.md`. | Architecture-source backed; no external-use owner/date is recorded in this harness. Confirm with Security / Compliance / Legal before vendor-risk use. |
| SOC2 Type 2 | In progress | GroundX cloud-service production. Source: `data-residency.md`. | Architecture-source backed; no external-use owner/date is recorded in this harness. Confirm with Security / Compliance / Legal before vendor-risk use. |
| FedRAMP / IL6 | Not held by hosted cloud | On-prem / air-gapped deployments can be deployer-attested. Source: `data-residency.md`. | Architecture-source backed; no external-use owner/date is recorded in this harness. Confirm with Security / Compliance / Legal before vendor-risk use. |
| GDPR attestation | Not held by hosted cloud | Delete-on-request supports the deletion-rights piece; formal attestation is not held. Source: `data-residency.md`. | Architecture-source backed; no external-use owner/date is recorded in this harness. Confirm with Security / Compliance / Legal before vendor-risk use. |
| RPO / RTO | Customer-contract-specific | Do not quote public numbers. Source: `disaster-recovery.md`. | Contract owner must confirm any customer-specific numbers or commitments. |

External compliance answers need Security / Compliance / Legal approval before use
outside an architecture review.

## 7. Subprocessors And Trust-Boundary Crossings

| Category | Customer data? | Status | Notes |
| --- | --- | --- | --- |
| Hosted cloud infrastructure/backing services | Yes | Held | The hosted cloud service runs in AWS us-west-2 for production. File storage, process metadata, retrieval data, and logs use deployment-selected backing services such as S3, RDS/MySQL, OpenSearch, Redis, and CloudWatch. Source: `data-residency.md`, `store.md`, and `observability.md`. |
| Third-party LLM | Yes, only when configured | Optional | Document content leaves the deployment when `summary.serviceType` points to a hosted engine such as OpenAI, Azure, DeepInfra, or another hosted endpoint. Bundled self-hosted and customer-hosted modes keep content inside the deployment. Source: `identity-and-trust.md` and `summary-service.md`. |
| Google Cloud Vision OCR | Yes, only when configured | Optional | Page images leave the deployment only when `gcv.json` is configured. Tesseract is the default OCR path. Source: `identity-and-trust.md` and `layout-ocr.md`. |
| On-prem backing services and monitoring | Deployer-owned | Deployer-attested | In on-prem deployments, the customer/deployer chooses and operates the backing stores, monitoring, alerting, and region. |
| Internal alerting channel | Source-pending customer-data status | Held as an internal alert channel, not approved as subprocessor table entry | The architecture references source hosted-cloud operator alerting, but does not approve alert-payload contents for customer-data processing classification. |
| Engineering SaaS such as issue tracker, source control, CI, docs, or chat | Source-pending | Unknown | Do not list as non-customer-data engineering SaaS without an approved source and data-processing classification. |

Keep optional trust-boundary crossings optional. Do not describe third-party LLM or
Google Cloud Vision as always-on subprocessors.

## 8. Negative-Space Controls

| Expected control | Native status | Actual model or compensating control |
| --- | --- | --- |
| Customer-tier SSO / OIDC / SAML | Not native | Partners can implement SSO in their own middleware and translate authenticated sessions into partner-tier calls. Source: `integration-architecture.md`. |
| Customer-tier RBAC | Not native | A customer API key is the customer-tier identity; scope narrowing is through request filters. Source: `identity-and-trust.md`. |
| Customer API key rotation | Not native | Customer keys are issue-once; leaked keys require partner-side revocation/re-issue. Source: `identity-and-trust.md`. |
| Native OAuth/JWT for REST API | Not native | REST API auth uses `X-API-Key`; OAuth applies to hosted MCP connector flows where supported. Source: `identity-and-trust.md`. |
| Native public API mTLS | Not native | Cloud API uses HTTPS/TLS through AWS API Gateway; customer ingress, service mesh, or API gateway can enforce mTLS for on-prem or fronted deployments. Source: `identity-and-trust.md`. |
| GroundX-managed KMS / per-customer KMS | Not native | Encryption at rest is delegated to backing services such as RDS, OpenSearch, S3, or MinIO. Source: `identity-and-trust.md`. |
| Per-customer database/schema/index isolation | Not native | One shared cluster uses API-layer ownership checks plus store-level owner validation and search pre-filters. Source: `multi-tenancy.md`. |
| Public SLO commitments | Not held | The architecture exposes signals, but commitments are customer-contract-specific. Source: `observability.md`. |

## 9. Answer Rules

- Use short status-labeled answers.
- Cite the reference file that owns each claim.
- For compliance or certification claims, include owner/freshness fields when present;
  otherwise say external use requires Security / Compliance / Legal confirmation.
- Say "source pending" instead of guessing for operator process questions.
- Keep cloud and on-prem separate.
- Keep optional external calls optional.
- Do not upgrade deployment-layer options into native GroundX controls.
