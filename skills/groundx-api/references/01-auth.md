# Authentication and Connection

## 1. Authentication

GroundX REST requests authenticate with an API key passed in the `X-API-Key` header.

```http
X-API-Key: YOUR_API_KEY
```

**Obtaining an API key:** Create an account at
`https://dashboard.groundx.ai/auth/register`, then navigate to **API Keys** in the
dashboard. Copy the key and store it in an environment variable —
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

## 2. MCP connection

Use the first-party GroundX MCP server before direct REST. First check whether GroundX
MCP tools are visible in the current agent runtime. If they are not visible, instruct the
user to connect the GroundX MCP connector to GroundX and retry tool discovery before
using REST fallback. When the connector is available, configure the MCP client with the
server URL and let the client follow the OAuth metadata and authorization-code flow. The
hosted GroundX authorization page asks the user for a GroundX API key, validates it
inside the GroundX deployment, and returns short-lived MCP tokens to the client.

For non-interactive API agents or MCP clients that cannot complete OAuth, authenticate
the MCP HTTP transport with the standard `X-API-Key` header. That is transport
authentication only; do not put the raw API key in MCP tool arguments, redirect URLs,
logs, transcripts, generated examples, or frontend/browser code.

```json
{
  "url": "https://api.groundx.ai/mcp"
}
```

MCP clients discover the protected resource and authorization server metadata at:

```text
GET https://api.groundx.ai/.well-known/oauth-protected-resource
GET https://api.groundx.ai/.well-known/oauth-authorization-server
```

On on-prem deployments, use the deployer-controlled public GroundX API hostname instead
of `https://api.groundx.ai`. The same endpoints are served by that deployment.

Once connected, call `groundx_account_context` before choosing behavior. It returns the
resolved account type, mode (`customer`, `partner`, or `admin`), granted scopes, base URL,
and enabled tool groups. Customer accounts expose customer GroundX tools. Partner accounts
also expose Partner and Workspace tools when enabled. Admin accounts expose all enabled
tool groups. If connector attachment/auth fails, or a needed tool remains missing after
discovery, use the REST references below as the fallback path and keep the API key
server-side.

`https://api.groundx.ai/mcp` and `https://api.groundx.ai/api/v1/mcp` are
equivalent — either may be used.

Interactive clients should use OAuth. Non-interactive agents may use `X-API-Key` MCP
transport auth when they cannot complete the browser authorization flow. In both modes,
never place the API key in MCP tool arguments or generated artifacts.

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

## 4. SDK setup

GroundX provides official SDKs for Python and TypeScript. Both SDKs wrap the REST
API and expose the same operations as method calls. Direct HTTP (cURL or any HTTP
client) is also supported for all languages.

### 4.1 Python SDK

Install:

```bash
pip install groundx
```

Initialize:

```python
import os
from groundx import GroundX

client = GroundX(
    api_key=os.environ.get("GROUNDX_API_KEY"),
)
```

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
