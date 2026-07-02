# GroundX Credential Handling

Use this reference before any skill asks for, stores, uses, or documents GroundX
credentials. This file is the canonical credential policy for installed agents.

## Credential Types

| Credential | Environment variable | Used for |
| --- | --- | --- |
| GroundX API key | `GROUNDX_API_KEY` | Customer-scoped SDK/REST requests and the optional hosted GroundX MCP authorization page |
| GroundX API base URL | `GROUNDX_BASE_URL` | Non-secret environment selector; unset or `https://api.groundx.ai/api` for prod, `https://devapi.groundx.ai/api` for dev |
| Workspace API key | `WORKSPACE_API_KEY` | Managed workspace projects; `PARTNER_API_KEY` and `GROUNDX_API_KEY` are accepted aliases by the harness/scaffold |
| Partner API key | `PARTNER_API_KEY` | Partner-only customer lifecycle, key minting, and cross-customer provisioning requests |
| LLM API key | `LLM_API_KEY` | Server-side middleware completions in scaffolded web UI projects |
| LLM service/provider | `LLM_SERVICE` | Provider/service for server-side completions, such as `openai`, `anthropic`, or a custom provider |
| LLM model ID | `LLM_MODEL_ID` | Exact completion model ID the scaffolded middleware should send to the LLM provider |
| Customer username | `CUSTOMER_USERNAME` | Partner resource endpoints that require `X-Customer-Key` |

## Required Agent Behavior

If a task requires `GROUNDX_API_KEY`, `WORKSPACE_API_KEY`, `PARTNER_API_KEY`, or
`LLM_API_KEY` and the key is not already available in the environment, current session,
or user-provided context, ask the user for the key before making any API request. When
asking for an LLM API key, also ask for the LLM service/provider and exact model ID; do
not assume defaults for real completions.

When the user provides a key:

- Use it only for the current working session unless the user explicitly approves
  persistence.
- Never print the full key back to the user.
- Never write the key into source files, skill files, docs, examples, evals, snapshots,
  logs, transcripts, generated code, commits, or long-lived model memory.
- Never include the key in browser-visible code or frontend bundles.
- Never place the key in MCP tool arguments, generated artifacts, browser code, logs, or
  transcripts. Interactive MCP clients should use the GroundX-hosted OAuth page, which
  exchanges the key inside the GroundX deployment for short-lived MCP tokens.
  Non-interactive API agents may use the key only as MCP HTTP transport auth with
  `X-API-Key`.
- Use placeholders such as `YOUR_API_KEY`, `$GROUNDX_API_KEY`, `$WORKSPACE_API_KEY`,
  `$PARTNER_API_KEY`, `$LLM_API_KEY`, or
  `process.env.*` in examples and generated code.
- Treat `LLM_SERVICE` and `LLM_MODEL_ID` as non-secret configuration. They may be
  written to ignored local env files with user approval, but must not be invented when
  the user has not chosen a provider/model.

## Persistence

Persistent storage is allowed only after explicit user approval. Approved locations are:

- a shell environment variable,
- an ignored local `.env` file,
- a user-approved secret manager.

Before persisting, name the destination and wait for confirmation. Do not invent a
storage location.

## Generated Apps

Generated web apps must keep secrets server-side:

- Browser code never receives `GROUNDX_API_KEY`, `WORKSPACE_API_KEY`,
  `PARTNER_API_KEY`, `LLM_API_KEY`, runner tokens, git session passwords, provider
  credentials, or LLM provider keys.
- Middleware owns server-side secrets and calls GroundX, Partner, runner, GitHub, GitLab,
  or LLM APIs on behalf of the browser.
- Frontend code calls same-origin middleware routes, not external secret-bearing APIs.

## Git Sessions

Managed workspace git-session passwords are short-lived credentials. Treat them like API
keys:

- use them only for clone/fetch/push against the returned managed repo;
- use noninteractive Git auth with `GIT_TERMINAL_PROMPT=0`, `GIT_ASKPASS`, and
  `git -c credential.helper=` so ambient keychains or cached credentials cannot override
  the session token;
- refresh them before expiry or after an auth failure;
- never print, persist, commit, or log them.

## API Header Reminders

- GroundX SDK/REST requests use `X-API-Key: $GROUNDX_API_KEY` under the hood.
- `GROUNDX_API_KEY` is environment-specific. Dev and prod need different keys.
- Prod keys are created in `https://dashboard.groundx.ai`; dev keys are created in
  `https://devdashboard.groundx.ai`. The dashboards share Cognito email/password
  login, but not backend data. Buckets, API keys, documents, and account resources are
  environment-specific.
- `GROUNDX_BASE_URL` is non-secret. For prod, leave it unset or set
  `https://api.groundx.ai/api`; for dev, set `https://devapi.groundx.ai/api`.
- GroundX MCP is optional and currently production-only. If prod MCP tools are already
  visible, call `groundx_account_context` before partner, workspace, or admin behavior.
  If MCP tools are missing, continue with SDK/REST unless the user specifically wants
  MCP setup help. Dev work should use SDK/REST.
- Managed workspace project requests use `X-API-Key: $WORKSPACE_API_KEY`; regular
  workspace-capable GroundX keys work for these endpoints, and `PARTNER_API_KEY` /
  `GROUNDX_API_KEY` are compatibility aliases in the harness/scaffold.
- Partner-only customer lifecycle, key minting, and cross-customer provisioning requests
  use `X-API-Key: $PARTNER_API_KEY`.
- Partner resource endpoints that operate for a customer also use
  `X-Customer-Key: $CUSTOMER_USERNAME` where documented.
- Do not use `Authorization: Bearer` for GroundX or Partner REST requests. Bearer tokens
  are the MCP OAuth transport result, not a REST auth pattern.
