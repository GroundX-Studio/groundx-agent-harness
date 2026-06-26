# Setup — Per-Client MCP Configuration

Connect an MCP client to the GroundX MCP server. This reference covers server URL, where the
API key goes, and configuration blocks for each supported client.

For key acquisition, OAuth detail, and troubleshooting, see `references/04-auth.md`.

---

## 1. Before you start

**Server URL.** The GroundX MCP server is at:

```
https://api.groundx.ai/mcp
```

Both of the following URLs are equivalent — the server accepts requests at either path:

```
https://api.groundx.ai/mcp
https://api.groundx.ai/api/v1/mcp
```

On-prem deployments replace `https://api.groundx.ai` with the deployer-controlled public
GroundX API hostname. The path (`/mcp` or `/api/v1/mcp`) stays the same.

**Where the API key goes.** The key travels in the `X-API-Key` HTTP request header. It is
never placed in a tool argument. The alternative to a header key is the OAuth flow, where
you authorize in a browser and no header is needed. See `references/04-auth.md` for how to
obtain a key from `https://dashboard.groundx.ai` (API Keys section).

**Confirm tools are visible.** After connecting, ask your client to list available tools.
You should see 12 default tools (scoped by your API key's permissions) plus 4 always-present
tools (`groundx_account_context`, `list_operations`, `describe_operation`, `call_operation`).
If you see fewer default tools, check the scope on your key — a read-only key shows only
`bucket_list`, `group_list`, and `health_get` from the default set. For a full tool reference,
see `references/02-default-tools.md`.

---

## 2. Claude Code CLI

### 2.1 Add via command line

The fastest path is the `claude mcp add` command. Run it from the project root so the server
is registered in the project `.mcp.json`:

```sh
claude mcp add --transport http groundx https://api.groundx.ai/mcp \
  --header "X-API-Key: ${GROUNDX_API_KEY}"
```

This writes the `groundx` entry to your project `.mcp.json`. The `GROUNDX_API_KEY` environment
variable must be set in the shell where Claude Code runs.

### 2.2 Add via .mcp.json

Alternatively, create or edit `.mcp.json` at the project root:

```json
{
  "mcpServers": {
    "groundx": {
      "type": "http",
      "url": "https://api.groundx.ai/mcp",
      "headers": {
        "X-API-Key": "${GROUNDX_API_KEY}"
      }
    }
  }
}
```

Set `GROUNDX_API_KEY` in your environment. Do not commit a real key — use the variable
reference shown above.

### 2.3 OAuth alternative

If you prefer OAuth, omit the `headers` block and do not pass `--header` in the CLI command.
Claude Code will prompt you to authorize in a browser on first use. No key is stored in the
config file.

### 2.4 Restart and verify

Restart or reload Claude Code after editing `.mcp.json`. Run `/tools` or ask the model to list
available tools to confirm the `groundx` MCP server appears.

---

## 3. Claude Desktop

### 3.1 Config file location

| OS | Path |
|---|---|
| macOS | `~/Library/Application Support/Claude/claude_desktop_config.json` |
| Windows | `%APPDATA%\Claude\claude_desktop_config.json` |

### 3.2 Add the mcpServers entry

Open the config file and add (or merge) the `mcpServers` block:

```json
{
  "mcpServers": {
    "groundx": {
      "type": "http",
      "url": "https://api.groundx.ai/mcp",
      "headers": {
        "X-API-Key": "${GROUNDX_API_KEY}"
      }
    }
  }
}
```

Set `GROUNDX_API_KEY` in the environment where Claude Desktop starts, or use the client's
supported secret-reference syntax. Do not paste a raw key into this config file, and do not
commit or share a config profile that contains credentials.

### 3.3 Restart and verify

Fully quit and relaunch Claude Desktop. The GroundX tools should appear in the tools panel.

---

## 4. Codex CLI

### 4.1 Config block

Add a `groundx` entry under `mcpServers` in the Codex CLI MCP config file. The exact config
file path depends on your Codex CLI version — check the Codex CLI documentation for the
current location (typically a `codex.json` or `.codex/config.json` in your project or home
directory):

```json
{
  "mcpServers": {
    "groundx": {
      "type": "http",
      "url": "https://api.groundx.ai/mcp",
      "headers": {
        "X-API-Key": "${GROUNDX_API_KEY}"
      }
    }
  }
}
```

### 4.2 Environment variable

Set `GROUNDX_API_KEY` in the environment where Codex CLI runs:

```sh
export GROUNDX_API_KEY=YOUR_GROUNDX_API_KEY
```

Add this to your shell profile or `.env` file so it persists across sessions. Never paste a
raw key into the config file — use the variable reference.

### 4.3 Verify

After restarting Codex CLI, list available tools to confirm the `groundx` server and its
default tools appear.

---

## 5. Codex Desktop

### 5.1 Add via Settings

1. Open **Settings** in Codex Desktop.
2. Navigate to **MCP Servers** (or **Integrations → MCP Servers**).
3. Click **Add Server**.
4. Set the URL to `https://api.groundx.ai/mcp`.
5. Add a header: key `X-API-Key`, value `${GROUNDX_API_KEY}` or the client's supported
   secret-reference syntax.
6. Save.

### 5.2 OAuth alternative

If Codex Desktop supports OAuth for remote MCP servers, select the OAuth option when adding
the server. Authorize in the browser when prompted. No key is entered manually.

### 5.3 Verify

After saving, the GroundX tools should appear in the tool list for new conversations.

---

## 6. Cursor

Cursor's MCP support is available but subject to change — check the Cursor documentation
for the current state before configuring.

### 6.1 If MCP is supported

Follow the same pattern: configure a remote HTTP MCP server pointing at
`https://api.groundx.ai/mcp` with the `X-API-Key` header supplied from an environment
variable or client secret. The exact UI path or config file location depends on the Cursor
version — consult Cursor's MCP integration documentation for the current steps.

### 6.2 If MCP is not yet available in your Cursor version

Use the REST API directly via the `groundx-api` skill, which documents the base URL,
`X-API-Key` REST header setup, SDK setup, and endpoint operation semantics. The `groundx-api`
skill is an optional
cross-link — it is not required to use this skill.

---

## 7. Replit

### 7.1 Store the key as a Secret

In your Replit project, open **Secrets** (the lock icon in the sidebar) and add:

- Key: `GROUNDX_API_KEY`
- Value: your API key

Never paste the raw key into source files or config blocks in your project — use the Replit
Secret and reference it by name.

### 7.2 MCP server config

If your Replit environment supports MCP server configuration, reference the secret in the
header config:

```json
{
  "mcpServers": {
    "groundx": {
      "type": "http",
      "url": "https://api.groundx.ai/mcp",
      "headers": {
        "X-API-Key": "${GROUNDX_API_KEY}"
      }
    }
  }
}
```

Replit automatically resolves `${GROUNDX_API_KEY}` from your project Secrets at runtime.

### 7.3 REST fallback

If MCP server support is not available in your Replit environment, use the REST API directly.
The `groundx-api` skill documents the base URL and SDK setup. This is an optional cross-link;
this skill does not require `groundx-api` to be installed.

---

## 8. MCP server URL

Both URLs below point at the same server:

| URL | Notes |
|---|---|
| `https://api.groundx.ai/mcp` | Preferred short form |
| `https://api.groundx.ai/api/v1/mcp` | Equivalent; some client docs or older references may use this form |

**On-prem deployments.** If GroundX is deployed on-premises, replace `https://api.groundx.ai`
with the deployer-controlled public GroundX API hostname. The path segment (`/mcp` or
`/api/v1/mcp`) is the same as the cloud endpoint. Contact your deployment operator for the
exact hostname.

For auth detail (OAuth metadata discovery, key scopes, 401 troubleshooting), see
`references/04-auth.md`.
