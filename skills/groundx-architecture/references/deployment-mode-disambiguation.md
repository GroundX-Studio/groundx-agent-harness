# Deployment Mode Disambiguation

Use this whenever an answer touches model identity, GPU resources, Helm values,
networking, residency, or deployment mechanics.

## Rule

Establish whether the answer is about **cloud**, **on-prem**, or a future
evaluation path before naming mode-specific components.

If context is clear, state the assumption:

> Assuming this is the hosted cloud sandbox...

If context is ambiguous, ask one short clarification before citing mode-specific
details:

> Are you asking about the hosted cloud sandbox or an on-prem deployment?

## Mode-Specific Facts

| Topic | Cloud | On-prem |
| --- | --- | --- |
| Regions | Dev is in `us-east-1`; prod is in `us-west-2`. | Deployer-selected. |
| Runtime placement | Hosted cloud is mixed: most hosted API/event paths are Lambda, hosted file processing is dedicated EC2, extraction and managed workspace run in Kubernetes, and layout/search-ranker run on dedicated EC2 hosts. | Canonical Helm chart on Kubernetes; `values.yaml` selects backing services. |
| API and dashboard | Prod API defaults to `https://api.groundx.ai/api`; dev uses `https://devapi.groundx.ai/api`. Prod dashboard is `https://dashboard.groundx.ai`; dev dashboard is `https://devdashboard.groundx.ai`. The dashboards share Cognito login credentials but not buckets, API keys, documents, or account data. | Deployment-specific. |
| Dev/prod data | Dev has its own SQS, RDS, Redis, Lambda set, dedicated file-processing host, and OpenSearch index. Dev shares layout/search-ranker hosts, S3 buckets, Cognito, and OpenSearch cluster with prod. Extraction does not work in dev. | Deployment-specific. |
| Summary engine identity | Verify the current cloud default before answering. Do not infer it from on-prem Helm values. | Self-hosted summary can use Gemma through vLLM when the bundled summary stack is enabled. |
| GPU node groups | Not described by Helm node-group labels in customer cloud answers. | `eyelevel-gpu-summary` is an on-prem only node group for the self-hosted summary stack. |
| Helm values | Not the right source for hosted cloud behavior. | Source of truth for install-time deployment behavior. |
| Residency and egress | Answer from the cloud contract/source for the customer's environment. | Answer from values, cluster topology, and on-prem trust-boundary docs. |

## Common Mistake

Do not answer a cloud sandbox model question with Gemma, vLLM, or
`eyelevel-gpu-summary` unless the user is explicitly asking about on-prem. Those
are on-prem deployment details. For cloud, verify the current cloud default or
say that the current default must be checked before naming a model.
