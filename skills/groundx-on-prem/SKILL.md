---
name: groundx-on-prem
description: >
  Deployment operator's reference for GroundX: how to deploy, configure, scale,
  and run GroundX on Kubernetes, including AWS EKS, Azure AKS, generic Kubernetes,
  OpenShift, private cloud, minikube, and air-gapped on-prem deployments.
  Use this for deployment operations. A buyer or prospect response, objection,
  comparison, or why-on-prem positioning request starts in `product-brand-gtm`,
  which returns here only for deployment facts.
---

# GroundX On-Prem

Before returning prose to a human, read `../RESPONSE_STYLE.md`. Use its external-writing
section for Valantor or GroundX collateral and its default rules for technical answers.

When a buyer asks about residency, use this order: state that GroundX can run fully
inside the customer's environment as a supported configuration; state that self-hosted
processing keeps those paths inside that environment; then state that optional external
OCR or model services change the boundary. Do not describe one configuration as the
default for every deployment or claim that every backing service must run in-cluster.

Use this skill for deployment planning, values.yaml authoring, cluster sizing,
air-gapped operation, OpenShift, upgrades, monitoring, troubleshooting, OCR mode,
summary engine selection, and Kubernetes operational questions.

## Routing Contract

- **Role:** `reference`.
- **First-entry intents:** install, deploy, run, configure, scale, monitor, upgrade,
  troubleshoot, author values.yaml, plan clusters, choose OCR/summary engines, or
  prepare air-gapped/on-prem GroundX.
- **Deferrals:** architecture-shaped facts route to `groundx-architecture`; API behavior
  after install routes to `groundx-api`; schema-first extraction routes to
  `groundx-extraction-workflows`; product/company messaging routes to the GTM skills.
- **Before producing output:** read `../RESPONSE_STYLE.md`, open `references/README.md`, and the relevant reference.
  For values.yaml authoring, run the discovery questionnaire in
  `references/values-authoring.md` before emitting config.
- **Misuse cases:** do not generate a values.yaml blindly; do not invent deployment
  support beyond the references; do not commit customer credentials or private values.

## Pre-return Checklist

- [ ] The answer is deployment-operational, not a guessed architecture answer.
- [ ] Values guidance follows `references/values-authoring.md`.
- [ ] Secrets are placeholders only.
- [ ] Air-gapped and on-prem constraints are called out when relevant.
