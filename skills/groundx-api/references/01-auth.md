# Authentication and Connection

## 1. Authentication

GroundX REST requests authenticate with an API key passed in the `X-API-Key` header.

```http
X-API-Key: YOUR_API_KEY
```

**Obtaining an API key:** Use the dashboard for the target environment, then
navigate to **API Keys**. Prod uses `https://dashboard.groundx.ai`; dev uses
`https://devdashboard.groundx.ai`. The dashboards share Cognito login
credentials, so the same email/password works in both, but they do not share
backend data: buckets, API keys, documents, and account resources are
environment-specific. Copy the key and store it in an environment variable —
`GROUNDX_API_KEY` is the conventional name.

Never hardcode the key in source code or commit it to version control. All examples
in this skill use `YOUR_API_KEY` or `process.env.GROUNDX_API_KEY` as placeholders.

If an installed agent needs to call the GroundX API and no key is available in the
current environment, it should ask the user to paste or otherwise provide the key. The
agent may reuse that key for subsequent requests in the current working session, but must
not save it to long-lived model memory, source files, docs, logs, tests, or generated
examples. For cross-session persistence, ask the user for explicit approval and store the
key only in a user-approved environment variable, ignored `.env` file, or secret manager.

**Key rotation:** Use `apikey_list`, `apikey_create`, and `apikey_delete` to rotate
keys without service interruption. See `references/07-customer-and-keys.md` for the
full rotation pattern.

## 2. Environment and connection choice

For direct API work, use `GROUNDX_API_KEY` with the Python SDK or REST. Choose the
environment first:

| Environment | Base URL | Key |
| --- | --- | --- |
| Prod | SDK default, or `https://api.groundx.ai/api` | prod `GROUNDX_API_KEY` from `https://dashboard.groundx.ai` |
| Dev | `https://devapi.groundx.ai/api` | dev `GROUNDX_API_KEY` from `https://devdashboard.groundx.ai` |

The hosted GroundX MCP connector is optional and currently production-only. If MCP tools
are already visible and the target is prod, call `groundx_account_context` before
choosing customer, partner, workspace, or admin behavior. If the target is dev, use the
Python SDK or REST instead of asking the user to connect MCP.

MCP auth is handled at the transport layer — never put the raw API key in MCP tool
arguments, redirect URLs, browser code, logs, transcripts, generated examples, or
frontend bundles.
Raw keys must never appear in MCP tool arguments, browser code, or logs.

For MCP client setup — per-client configuration (Claude Code CLI, Claude Desktop, Codex,
Cursor, Replit), the OAuth metadata and authorization-code flow, the `X-API-Key` HTTP transport
for non-interactive agents, and the MCP server URL — use the dedicated `groundx-mcp` skill. This
skill does not duplicate that setup detail; it cross-links to `groundx-mcp` and owns REST/SDK.

Once connected in prod, `groundx_account_context` returns the resolved account type,
mode (`customer`, `partner`, or `admin`), granted scopes, base URL, and enabled tool
groups. Customer accounts expose customer GroundX tools. Partner accounts also expose
Partner and Workspace tools when enabled. Admin accounts expose all enabled tool groups.
If connector attachment/auth fails, or a needed tool remains missing after discovery,
use the Python SDK or REST references below and keep the API key server-side.

For Partner MCP sessions, do not pass raw API keys as tool arguments. Partner resource tools use
`customerUsername` as a per-call target-customer selector; the server maps it to the Partner API
`X-Customer-Key` header. If the session is authorized with a regular user key, Partner tools
should not be visible.

## 3. REST base URL and headers

The OpenAPI and MCP source files use operation paths that start with `/v1`, such as
`POST /v1/search/{id}`. Compose full public URLs in one of two equivalent ways:

| HTTP client setup | Request path to pass |
|---|---|
| Base URL `https://api.groundx.ai/api` | `/v1/search/{id}` |
| Base URL `https://api.groundx.ai/api/v1` | `/search/{id}` |

Both produce the same full URL:

```
https://api.groundx.ai/api/v1
```

For dev, use the same path rules with base URL `https://devapi.groundx.ai/api`.
Do not use a prod API key against dev, or a dev API key against prod.

Do not combine a `/api/v1` base with a `/v1/...` operation path; that creates the
invalid double-version path `/api/v1/v1/...`.

Every request requires two headers:

| Header | Value |
|---|---|
| `X-API-Key` | `YOUR_API_KEY` |
| `Content-Type` | `application/json` (required for POST/PUT with a JSON body; omit for GET/DELETE) |

Example bare REST request:

```http
GET /api/v1/bucket HTTP/1.1
Host: api.groundx.ai
X-API-Key: YOUR_API_KEY
```

Do not use `Authorization: Bearer` for direct REST calls. Bearer tokens are for the MCP
OAuth transport only.

Security posture note: GroundX REST API authentication is `X-API-Key`; do not describe
the REST API as OAuth 2.0/JWT-authenticated. OAuth applies to the hosted MCP connector
flow, and any customer-required OAuth/JWT front door should be implemented by a gateway
or identity proxy in front of GroundX.

## 4. SDK setup

GroundX provides official SDKs for Python and TypeScript. Both SDKs wrap the REST
API and expose the same operations as method calls. Direct HTTP (cURL or any HTTP
client) is also supported for all languages.

### 4.1 Python SDK

Install:

```bash
pip install "groundx[extract]"
```

Initialize:

```python
import os
from groundx import GroundX

client = GroundX(
    api_key=os.environ.get("GROUNDX_API_KEY"),
    base_url=os.environ.get("GROUNDX_BASE_URL", "https://api.groundx.ai/api"),
)
```

For prod, leave `GROUNDX_BASE_URL` unset or set it to `https://api.groundx.ai/api`.
For dev, set `GROUNDX_BASE_URL=https://devapi.groundx.ai/api`.

### 4.2 TypeScript SDK

Install:

```bash
npm install -s groundx
```

Initialize:

```typescript
import { GroundXClient } from "groundx";

const client = new GroundXClient({
    apiKey: process.env.GROUNDX_API_KEY,
});
```

### 4.3 Direct HTTP

No SDK is required. Use cURL or any HTTP client. All examples in this skill include
both an MCP tool call variant and a REST/cURL variant.
