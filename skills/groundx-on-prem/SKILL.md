---
name: groundx-on-prem
description: >
  Deployment operator's reference for GroundX: how to deploy, configure, scale,
  and run GroundX on Kubernetes, including AWS EKS, Azure AKS, generic Kubernetes,
  OpenShift, private cloud, minikube, and air-gapped on-prem deployments.
  Also triggers on GroundX Redis TLS and certificate troubleshooting:
  `certificate verify failed` from layout, ranker or summary pods, `rediss`
  URLs, a Redis CA for a GroundX install, or a request to turn certificate
  checks off.
  Use this for deployment operations. A buyer or prospect response, objection,
  comparison, or why-on-prem positioning request starts in `product-brand-gtm`,
  which returns here only for deployment facts.
---

# GroundX On-Prem

Before returning prose to a human, read `../RESPONSE_STYLE.md`. Its base rules apply to
everything you write. Add its external-writing section on top for Valantor or GroundX
collateral.

When a buyer asks about residency, use this order: state that GroundX can run fully
inside the customer's environment as a supported configuration; state that self-hosted
processing keeps those paths inside that environment; then state that optional external
OCR or model services change the boundary. Do not describe one configuration as the
default for every deployment or claim that every backing service must run in-cluster.

Use this skill for deployment planning, values.yaml authoring, cluster sizing,
air-gapped operation, OpenShift, upgrades, monitoring, troubleshooting, OCR mode,
summary engine selection, and Kubernetes operational questions.

For protected-file gateways, private upload, local MCP and storage acceptance, read `references/file-access.md` before writing deployment guidance.

## Redis and operator-run endpoint TLS

For a `certificate verify failed` error, or a question about the CA for a Redis or another endpoint the operator runs, open `references/tls-and-certs.md` § 3.3 and § 4.3 before answering. Never offer to turn certificate verification off, skip it, or change an endpoint's `ssl` setting to get past a certificate error; no GroundX setting turns it off. Never generate a CA or a server certificate. Ask whether the certificate comes from a public or a private CA, ask the operator for the CA certificate file, and route it through `fileAccess.caSecretName` by appending to the existing bundle, never replacing it. From the 0.2.8 chart line the `ai-server` layout, ranker and summary Redis clients verify the certificate and read `SSL_CERT_FILE`, so no other chart field is needed; do not call the connection verified end to end. Show each command that changes the cluster and run it only after the operator approves. If the operator must be back up before the CA is sorted out, offer `helm rollback` to the previous revision (`references/upgrades.md` § 6) and say that the previous images do not check the Redis certificate.

## Routing Contract

- **Role:** `reference`.
- **First-entry intents:** install, deploy, run, configure, scale, monitor, upgrade,
  troubleshoot, author values.yaml, plan clusters, choose OCR/summary engines, or
  prepare air-gapped/on-prem GroundX.
- **Deferrals:** architecture-shaped facts route to `groundx-architecture`; API behavior
  after install routes to `groundx-api`; schema-first extraction routes to
  `groundx-extraction-workflows`; getting or installing the GroundX Agent Harness plugin itself routes to `groundx-mcp`; product/company messaging routes to the GTM skills.
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
