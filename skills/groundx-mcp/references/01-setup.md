# Setup — Per-Client MCP Configuration

Connect an MCP client to the GroundX MCP server. This reference covers server URL, where the
API key goes, and configuration blocks for each supported client.

For key acquisition, OAuth detail, and troubleshooting, see `references/04-auth.md`.

---

## 1. Before you start

**Check first: the harness plugin may already have connected this server.** Skipping this
check is the most common cause of attaching the same server twice, which shows up as
duplicated tools and repeated approval prompts.

The harness plugin declares the hosted `groundx` server in its bundled MCP config, so
current Claude Code and Codex plugin installs register it on install. List the client's MCP
servers before following any per-client setup below:

- **Claude Code** — run `/mcp` or `claude mcp list`. A plugin-provided server is **not**
  named bare `groundx`; it appears as `plugin:<plugin-name>:groundx` (for example
  `plugin:groundx-agent-harness:groundx`), and its tools are named
  `mcp__plugin_<plugin_name>_groundx__<tool>` rather than `mcp__groundx__<tool>`. Match on
  the `groundx` suffix, not an exact string.
- **Codex** — run `codex mcp list`. The entry is named `groundx`.

If the server is already present, do not add it again. Go straight to authentication
(`references/04-auth.md`). Only follow the per-client setup below when the server is absent —
for example on an agent without plugin MCP support, or an older client that does not read
plugin MCP config.

**How the key reaches an already-registered server differs by client.** Both clients read
the same `GROUNDX_API_KEY` environment variable, but through different config fields, so
what you can tell a user to do differs:

- **Claude Code** reads the config's `headers`. An exported `GROUNDX_API_KEY` is sent as
  `X-API-Key`. If unset, an empty value is sent, the server answers
  `401 authorization_required`, and the client offers the OAuth sign-in.
- **Codex ignores `headers` entirely** and reads `env_http_headers`, which names the
  environment variable to resolve at connect time. An exported `GROUNDX_API_KEY` works; an
  unset one means the header is omitted and `codex mcp login groundx` is the way in. Do not
  tell a Codex user that a `headers` entry or a `${GROUNDX_API_KEY}` placeholder will work —
  Codex does not expand `${...}` in header values and would transmit the literal text.

OAuth is the only path that prompts the user interactively and stores the credential in the
OS keychain on both clients, so prefer it when the user has no key exported. Claude Code
plugins can also prompt once for a keychain-stored key via plugin `userConfig`; Codex has no
equivalent, so treat that as a Claude-only convenience rather than shared guidance.

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
You should see 12 default tools (scoped by your API key's permissions), plus 4 always-present
tools (`groundx_account_context`, `list_operations`, `describe_operation`, `call_operation`),
plus `report_issue`.
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

### 3.1 Add the connector

1. Open **Settings -> Connectors -> + -> Add custom connector**. From the Code tab the
   route is **Customize -> Connectors**.
2. Enter `Name: GroundX API`.
3. Enter the MCP server URL `https://api.groundx.ai/mcp`.
4. Leave the advanced OAuth fields empty unless Claude asks you to review discovered
   settings.
5. Click **Add**, then **Connect** on the next screen.
6. Enter your key on the GroundX sign-in page.

Connector tool calls may default to per-tool approval prompts. Choose **Always allow**
only after accepting the broader connector permission.

### 3.2 Verify

Enable the connector in a conversation and ask the client to list its tools.

If GroundX tools appear twice in a later Claude Code session, keep the plugin entry and
disable the connector under `/mcp`.

---

## 4. Codex CLI

### 4.1 Sign in

Confirm `groundx` is listed with `codex mcp list`, then sign in once:

```sh
codex mcp login groundx
```

Prefer this: the credential goes to the OS keychain, not a config file.

### 4.2 Environment variable

Exporting the key authenticates without signing in:

```sh
export GROUNDX_API_KEY=YOUR_GROUNDX_API_KEY
```

Add this to your shell profile so it persists across sessions.

### 4.3 Config block, when `groundx` is absent from `codex mcp list`

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
      "env_http_headers": {
        "X-API-Key": "GROUNDX_API_KEY"
      }
    }
  }
}
```

Codex reads `env_http_headers`, which names the environment variable to resolve at connect
time. A `headers` entry does not authenticate on Codex. Never paste a raw key into the
config file.

### 4.4 Verify

After restarting Codex CLI, list available tools to confirm the `groundx` server and its
default tools appear.

---

## 5. Codex Desktop

Codex Desktop setup needs no terminal commands.

### 5.1 Authenticate the registered server

1. Open **Settings -> Plugins** in Codex Desktop.
2. Find `groundx` in the list.
3. Click **Authenticate**.
4. Enter your key on the GroundX sign-in page.

### 5.2 Add it by hand, when `groundx` is not in the list

1. Go to **Settings -> Plugins -> Add -> Add MCP server**.
2. Set the type to **Streamable HTTP**.
3. Set the URL to `https://api.groundx.ai/mcp`.
4. Click **Save**, then **Authenticate** on the new entry.

A second entry alongside the plugin's attaches the same server twice.

### 5.3 Verify

The GroundX tools should appear in the tool list for new conversations.

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
