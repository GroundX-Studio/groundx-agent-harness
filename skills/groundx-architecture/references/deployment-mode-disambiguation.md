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
| Summary engine identity | Verify the current cloud default before answering. Do not infer it from on-prem Helm values. | Self-hosted summary can use Gemma through vLLM when the bundled summary stack is enabled. |
| GPU node groups | Not described by Helm node-group labels in customer cloud answers. | `eyelevel-gpu-summary` is an on-prem only node group for the self-hosted summary stack. |
| Helm values | Not the right source for hosted cloud behavior. | Source of truth for install-time deployment behavior. |
| Residency and egress | Answer from the cloud contract/source for the customer's environment. | Answer from values, cluster topology, and on-prem trust-boundary docs. |

## Common Mistake

Do not answer a cloud sandbox model question with Gemma, vLLM, or
`eyelevel-gpu-summary` unless the user is explicitly asking about on-prem. Those
are on-prem deployment details. For cloud, verify the current cloud default or
say that the current default must be checked before naming a model.
