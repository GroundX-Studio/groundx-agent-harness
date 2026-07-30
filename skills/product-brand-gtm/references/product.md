# Product: Current State And Promise Boundaries

This product-state inventory is the local source of truth for product-altitude
promise boundaries. It records lifecycle state, what may be promised, the
technical source when one exists, the reviewable verification basis, and the
condition that forces a recheck. Customer outcomes and benchmarks live in
`proof-points.md`; API, deployment, and bundle details remain with their
technical sources.

If new collateral conflicts with this inventory, use the recorded state for the
runtime answer and request a reviewable approved product-state update. Narrative,
objections, and collateral do not become parallel state registries. If an agent
cannot access such an approval, it must preserve the state below, flag the
recheck, and avoid claiming that reconciliation is complete.

Repository-backed skills and specs listed below control technical semantics or
bundle boundaries, not business lifecycle decisions.

`Tracked source` identifies the reviewable repository record from which a
lifecycle state was carried forward. It is an audit anchor, not a fresh
product-owner confirmation. A newer approved product-state update replaces the
tracked state.

## 1. Product map

| Layer | Product | State | Promise boundary | Technical source / review instruction | Verification basis | Recheck trigger |
| --- | --- | --- | --- | --- | --- | --- |
| Hosted platform | **Hosted GroundX** | GA | May be described as the available hosted GroundX platform. Do not promise current UI quality, signup behavior, or conversion performance from GTM guidance. | `groundx-api` for supported behavior; approved product-state update required for lifecycle changes | Tracked source: canonical inventory at `4ca915b` (2026-05-15); no newer approved lifecycle update supplied | Product lifecycle change, customer-facing launch, or quarterly review |
| Self-hosted platform | **GroundX On-Prem** | GA | May be sold as the self-hosted and air-gapped GroundX distribution. Deployment facts, including the available workspace service, come from `groundx-on-prem` and architecture guidance. | `groundx-on-prem` for deployment truth; approved product-state update required for lifecycle changes | Tracked source: canonical inventory at `4ca915b` (2026-05-15); no newer approved lifecycle update supplied | Chart lifecycle change, support-policy change, or quarterly review |
| No-code UI | **GroundX Studio** | In development | Describe the intended business-user surface and named use cases. Do not promise general customer availability. | Approved product-state update required for lifecycle changes | Tracked source: canonical inventory at `4ca915b` (2026-05-15); no newer approved lifecycle update supplied | Release milestone, availability announcement, or quarterly review |
| Public agentic adoption | **GroundX Agent Harness** | Available public bundle | Promise public GroundX knowledge and workflows only. Do not attribute Studio-only, MCP, or host-client capabilities to it. | `public-harness` spec | Current public-harness spec and generated manifest | Public release-scope change or quarterly review |
| Private agentic adoption | **GroundX Studio Harness** | Alpha, private expanded bundle | Describe the prebuilt Studio production, authoring, publishing, administration, and operational workflows only for the private bundle. Do not imply that it exclusively owns the underlying On-Prem workspace service. | `private-harness` spec for bundle boundary; approved product-state update required for lifecycle changes | Tracked source: canonical inventory at `00fab9d` (2026-05-22) for lifecycle; current private-harness spec for bundle boundary | Product lifecycle change, bundle-scope change, or quarterly review |
| Outcome Plug-in | **FraudX** | GA | May be described as a shipping insurance-fraud Outcome Plug-in within the current capability boundary. | Approved product-state update required for lifecycle changes | Tracked source: canonical inventory at `4ca915b` (2026-05-15); no newer approved lifecycle update supplied | Capability, vertical, or lifecycle change; quarterly review |
| Outcome Plug-in | **ExtractX** | GA | May be described as a shipping document-operations Outcome Plug-in. Self-service delivery remains roadmap. | Approved product-state update required for lifecycle changes | Tracked source: canonical inventory at `4ca915b` (2026-05-15); no newer approved lifecycle update supplied | Delivery-model or lifecycle change; quarterly review |
| Outcome Plug-in | **ClaimsX, ComplianceX, OpsX, FinanceX, GridX** | Illustrative concepts | Use only to illustrate the productization pattern. Do not claim availability, pilots, or customer outcomes. | Approved product-state update required before changing availability | Tracked source: canonical inventory at `4ca915b` (2026-05-15); no newer approved lifecycle update supplied | Productization approval or quarterly review |
| Service layer | **Operational Layer** | Concept | Describe strategic outcomes-as-a-service posture only. Do not claim a shipping, customer-deployed, or available-on-request product. | Approved product-state update required before changing availability | Tracked source: canonical inventory at `4ca915b` (2026-05-15); no newer approved lifecycle update supplied | Approved customer offering, lifecycle decision, or quarterly review |

## 2. Hosted GroundX

- **Buyer.** Teams evaluating or integrating the hosted GroundX platform.
- **Current promise.** Hosted GroundX provides the managed platform path for
  document ingest, understanding, extraction, search, and grounded answers.
  Retrieve supported behavior from `groundx-api`.
- **Stable value.** Low-friction evaluation and managed operation without
  requiring a customer-run deployment.
- **Do not include.** Signup volume, conversion, dashboard quality, internal
  implementation problems, or replacement plans.

## 3. GroundX On-Prem

- **Buyer.** Engineering, security, platform, and operations teams that require
  customer-controlled deployment.
- **Current promise.** GA self-hosted GroundX for Kubernetes, including
  private-cloud and air-gapped postures where supported by the deployment
  owner.
- **Stable value.** Data control, deployment flexibility, and a path for
  regulated or sovereignty-sensitive workloads.
- **Technical boundary.** Use `groundx-on-prem` for Helm, infrastructure,
  architecture, workspace-service availability, runtime support, configuration,
  and operational claims.

## 4. GroundX Studio

- **Buyer.** Business users who need a guided GroundX experience without
  beginning from API integration.
- **State.** In development. Do not claim general customer availability.
- **Intended use cases.** **Extract**, **Interact**, and **Report**. Preserve
  these names.
- **Stable value.** A focused business-user surface for seeing and using
  GroundX outputs.
- **Do not include.** Prototype history, implementation quality, rebuild plans,
  or internal design debate.

## 5. GroundX Harnesses

### GroundX Agent Harness

- **Availability.** Public bundle.
- **Current promise.** Portable GroundX knowledge and workflows for compatible
  skills-capable agents.
- **Boundary.** Does not include private prebuilt Studio production, publishing,
  administration, partner-lifecycle, or internal workflow skills. This does not
  remove the On-Prem customer's ability to enable and operate the workspace
  service using public guidance. It also does not own capabilities supplied
  independently by the host client.

### GroundX Studio Harness

- **State.** Alpha, private expanded bundle.
- **Current promise.** Shared GroundX knowledge plus prebuilt Studio production,
  authoring, publishing, administration, and operational workflows.
- **Boundary.** Do not imply public availability or treat it as the same bundle
  as GroundX Agent Harness. Do not imply that the private bundle is required to
  deploy or operate the On-Prem workspace service.

GroundX MCP is optional connected execution, separate from installed knowledge.
REST and SDKs remain direct integration paths. Use `harness-pitch.md` for
buyer-facing capability attribution and bundle policy/generated manifests for
exact membership.

## 6. FraudX

- **State.** GA.
- **Buyer.** Insurance-fraud investigation teams, claims organizations, SIU,
  and legal review teams within the currently approved vertical boundary.
- **Current promise.** A GroundX-powered investigation product that applies the
  current investigator-defined checks and produces source-linked signals,
  answers, evidence, and network analysis.
- **Boundary.** Require an approved product-state update before expanding the
  supported lines of business or capabilities. Use `proof-points.md` for
  customer voice, ROI, benchmarks, or other substantiation.
- **Stable value.** Faster, more reviewable investigation with evidence tied
  back to source material.

## 7. ExtractX

- **State.** GA.
- **Buyer.** Companies and BPOs modernizing document extraction and review
  workflows.
- **Current promise.** A productized extraction outcome delivered through the
  currently approved managed or partnership deployment path.
- **Boundary.** Harness-and-Studio self-service remains roadmap until the owner
  changes the lifecycle record.
- **Stable value.** Replace brittle OCR-and-template workflows with structured,
  reviewable GroundX outputs.

## 8. Illustrative Outcome Plug-ins

ClaimsX, ComplianceX, OpsX, FinanceX, and GridX are illustrative marketing
concepts, not shipping products.

- Use them only to explain the broader *[Outcome]X* productization pattern.
- Do not invent availability, customers, accuracy, pilots, deployment counts,
  or dates.
- Route master-brand strategy to `master-brand-gtm`; use FraudX and ExtractX as
  the current shipping examples.

## 9. Operational Layer

- **State.** Concept. No shipping customer product.
- **Buyer idea.** Organizations that would rather buy a governed business
  outcome than assemble and operate the underlying toolchain.
- **Promise boundary.** Describe the outcomes-as-a-service strategy and AI plus
  human accountability model only. Do not claim availability, deployment,
  staffing readiness, or a live customer offering.
- **Reconciliation rule.** A real customer offer requires an approved,
  reviewable product-state update before GTM language changes.

## 10. How to use this file

- Use the table for lifecycle and promise questions.
- Use the relevant product section for stable buyer/value framing.
- Use `proof-points.md` for eligible customer, benchmark, partner, technical
  corpus, or performance proof.
- Use `harness-pitch.md` to distinguish public Agent Harness, private Studio
  Harness, MCP, and host-agent capabilities.
- If collateral is stronger than the current state, keep the current answer and
  request a reviewable approved product-state update.

## 11. What this file does not own

- Pricing or contract terms.
- Customer outcomes, benchmarks, or performance values.
- API, SDK, MCP, deployment, or exact bundle-membership semantics.
- Master-brand Valantor category positioning.
- Visual or voice-register decisions.
