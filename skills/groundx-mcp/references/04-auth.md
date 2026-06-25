# Auth and Troubleshooting

Auth for the GroundX MCP server runs at the transport layer — never inside a tool argument.
This file covers obtaining a key, the two supported auth paths (OAuth and `X-API-Key`), the
MCP server URL, and how to diagnose the three most common failures.

---

## 1. Obtaining a GroundX API Key

1. Create or sign in to your account at `https://dashboard.groundx.ai`.
2. Navigate to **API Keys** in the left sidebar.
3. Generate a new key and copy it immediately — the dashboard does not display it again.
4. Store the key in an environment variable. The conventional name is `GROUNDX_API_KEY`.

```sh
export GROUNDX_API_KEY="YOUR_API_KEY"
```

Rules that apply everywhere:

- Never hardcode the raw key in source, config files, notebooks, memory, or any artifact.
- Never paste the raw key into an MCP tool argument (`call_operation`, `search_content`, etc.).
  Examples in this skill always use the placeholder `YOUR_API_KEY` or `${GROUNDX_API_KEY}`.
- Auth is transport-layer only. The key travels in the HTTP `X-API-Key` header or is
  exchanged once during the OAuth flow — the resulting MCP tokens carry access from that point on.

---

## 2. MCP Server URL

The hosted GroundX MCP endpoint has two equivalent forms:

```
https://api.groundx.ai/mcp
https://api.groundx.ai/api/v1/mcp
```

Either URL works; use whichever a per-client config block requires. For on-prem deployments,
replace `api.groundx.ai` with the deployer-controlled public GroundX API hostname. No path
changes are needed — the `/mcp` and `/api/v1/mcp` suffixes are the same.

---

## 3. OAuth Path (Interactive Clients)

Use this path for clients that open a browser during connection: **Claude Desktop**,
**Codex Desktop**, and any other interactive MCP client that supports OAuth 2.0.

### 3.1 Discovery

The client fetches metadata from two well-known endpoints before starting the flow:

```
GET https://api.groundx.ai/.well-known/oauth-protected-resource
GET https://api.groundx.ai/.well-known/oauth-authorization-server
```

These responses tell the client where to redirect the user and which grant types are supported.

### 3.2 Authorization-Code Flow

1. The client redirects the user to the GroundX-hosted authorization page.
2. The page prompts for a GroundX API key and validates it inside the deployment.
3. On success the server issues short-lived MCP tokens and returns them to the client via the
   redirect URI.
4. The raw API key is not transmitted after this step — the client holds only the MCP tokens.

### 3.3 Token Expiry

MCP tokens are short-lived. If a previously working session returns 401, re-authorize through
the client UI. The raw API key is not re-entered unless the token has been fully revoked.

---

## 4. X-API-Key Transport (Headless / CI / Non-Interactive Agents)

Use this path for agents, pipelines, and CLI-based clients that cannot open a browser:
**Claude Code CLI**, **Codex CLI**, **Cursor**, **Replit**, and any CI runner.

Pass the key in the `X-API-Key` HTTP header of the MCP transport connection. The key never
appears inside a tool call.

Illustrative server config block (the exact field names vary by client — see
`references/01-setup.md` for per-client forms):

```json
{
  "mcpServers": {
    "groundx": {
      "url": "https://api.groundx.ai/mcp",
      "headers": {
        "X-API-Key": "${GROUNDX_API_KEY}"
      }
    }
  }
}
```

The `${GROUNDX_API_KEY}` placeholder is expanded from the environment at runtime by the client.
Do not substitute the literal key value into the config file.

---

## 5. Troubleshooting

### 5.1 401 Unauthorized

**Symptoms:** the MCP client fails to connect; a tool call returns HTTP 401 or an
"unauthorized" error message.

**Causes and fixes:**

| Cause | Fix |
|---|---|
| `GROUNDX_API_KEY` not set in the environment | Run `export GROUNDX_API_KEY="YOUR_API_KEY"` before starting the client |
| `X-API-Key` header missing from the server config | Add the `headers.X-API-Key` field to the server config block (see §4); confirm the client reads headers from that config |
| Key placed in a tool argument instead of the transport header | Remove the key from the tool argument; place it only in the transport config |
| OAuth token expired | Re-authorize through the client UI (see §3.3) |
| Wrong or revoked key | Generate a new key at `https://dashboard.groundx.ai` → API Keys |

**Quick REST sanity-check** — confirm the key is valid before debugging the MCP layer:

```sh
curl -H "X-API-Key: YOUR_API_KEY" https://api.groundx.ai/api/v1/health/api
```

A `200` response confirms the key is accepted. A `401` confirms the key itself is the problem.

### 5.2 Scope Mismatch

**Symptoms:** a tool is not visible in the client's tool list, or a `call_operation` call is
rejected even though the operation exists.

**How scope is derived** (see `references/02-default-tools.md` for the full rule and table):

1. Path contains `/ingest` → requires `groundx:ingest`
2. Otherwise a write verb (POST / PUT / PATCH / DELETE) → requires `groundx:write`
3. Otherwise → requires `groundx:read`

**What a read-only session sees** from the 12 default tools — only the three tools that need
only `groundx:read`:

- `bucket_list`
- `group_list`
- `health_get`

Plus the 4 always-present tools (`groundx_account_context`, `list_operations`,
`describe_operation`, `call_operation`) regardless of scope.

Note: `search_content` and `search_documents` use POST, so they are `groundx:write` — they are
**not** visible in a read-only session. This is intentional.

**Fix:** upgrade the API key's grant level in the GroundX dashboard to include `groundx:write`
or `groundx:ingest` as needed. A key with broader scope unlocks the corresponding tools
immediately on reconnect.

For the full default tool list with per-tool scope assignments, see
`references/02-default-tools.md`.

### 5.3 Tool Not Found

**Symptoms:** the client reports the tool name is unknown, or a call fails with "tool not
found" or "unknown tool".

**Checklist:**

1. **Verify the normalized name.** Tool names are lowercase with underscores (e.g.
   `document_ingestremote`, `bucket_create`). The `operationId` values in the raw OpenAPI spec
   use PascalCase (`Document_ingestRemote`, `Bucket_create`) — those are not valid MCP tool
   names. For the authoritative list, see `references/02-default-tools.md`.

2. **Check scope.** The tool may exist but be hidden because the current session's scope is
   insufficient. Use `list_operations` (always present) to see advanced operations exposed
   through MCP, then compare to the expected visibility in §5.2 above.

3. **Use `call_operation` for advanced ops.** Only the 12 default tools appear by name in the
   tool list. Registered advanced operations are reached through the discovery path:
   `list_operations` → `describe_operation({operationId})` → `call_operation({operationId, args})`.
   Some operations are intentionally unavailable through MCP, including `APIKey_create`. See
   `references/03-discovery.md` for the full pattern.

4. **Check for a tool list reduction.** If the client previously worked with more tools visible
   by name, the server may have been updated to the 12-tool default set. There is no
   restore/opt-in flag — advanced ops move permanently to the `call_operation` path. Migration
   guidance is in `references/06-migration.md`.
