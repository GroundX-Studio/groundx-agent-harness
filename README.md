# GroundX Agent Harness

GroundX Agent Harness gives Claude and Codex the GroundX context they need to help
with:

- document ingest, status checks, and search
- buckets, groups, workflows, APIs, and SDKs
- schema-first extraction workflows
- GroundX on-prem planning
- GroundX product, company, and architecture questions

For authenticated GroundX API calls, connect the hosted MCP server:

```text
https://api.groundx.ai/mcp
```

## Requirements

- A GroundX API key.
- One of: VS Code + Claude, Claude Desktop, Codex Desktop, or Codex CLI.
- Enter API keys only in the GroundX OAuth screen. Do not paste keys into prompts.

Use a regular GroundX user API key unless GroundX has issued you Partner-tier access.

The harness plugin and the MCP server are separate pieces:

- The plugin gives the agent GroundX instructions and workflows.
- MCP gives the agent authenticated GroundX API tools.
- Install both where the client supports both.

Client support:

| Client | Plugin / skills | MCP API tools |
| --- | --- | --- |
| VS Code + Claude | Yes | Yes |
| Claude Desktop | Yes, through Claude organization plugin sync | Yes |
| Codex Desktop | Yes | Yes |
| Codex CLI | Yes | Yes |
| Claude Code CLI | Yes | Yes |

## Installation

### VS Code + Claude

Install the plugin with either method.

**Method 1 — Claude Code slash commands**

Run these commands inside Claude Code:

```text
/plugin marketplace add GroundX-Studio/groundx-agent-harness
/plugin install groundx-agent-harness@groundx-agent-harness
/reload-plugins
```

If `/plugin` is not available in your VS Code chat surface, run the terminal
commands instead:

```sh
claude plugin marketplace add GroundX-Studio/groundx-agent-harness
claude plugin install groundx-agent-harness@groundx-agent-harness
```

Then run `/reload-plugins` inside Claude Code, or start a new Claude Code session.

**Method 2 — Claude Code Desktop (local or SSH sessions)**

Claude Code Desktop supports plugins for local and SSH sessions, but not remote
sessions.

1. Click **Customize** in the left sidebar.
2. Next to **Personal plugins**, click **+**, then select
   **Create plugin -> Add marketplace**.
3. In **Add marketplace**, enter `GroundX-Studio/groundx-agent-harness` and click
   **Sync**.
4. Click **+** next to **Personal plugins** again, then select **Browse plugins**.
5. Open the **Personal** tab, find **GroundX Agent Harness**, and click **+** to
   install it.
6. Run `/reload-plugins`, or start a new Claude Code session.

Connect MCP:

1. Add the hosted GroundX MCP server:

   ```sh
   claude mcp add --transport http groundx https://api.groundx.ai/mcp
   ```

2. Run `/mcp`, connect `groundx`, complete OAuth,
   and start a new Claude Code session.

### Claude Desktop

Install the plugin:

1. An organization admin opens **Claude**.
2. Go to **Organization settings -> Plugins**.
3. Click **Add plugins**.
4. Choose **Sync from GitHub**.
5. Select:

   ```text
   GroundX-Studio/groundx-agent-harness
   ```

6. Complete the sync flow so **GroundX Agent Harness** appears in the organization's
   plugin list.
7. Individual users can then install it from Claude **Cowork** or **Code**:
   - Click the **+** symbol.
   - Choose **Add plugin**.
   - Select **GroundX Agent Harness** from the organization plugins.
8. Start a new Claude Cowork or Code session after installing.

Connect MCP:

9. Open **Claude Desktop -> Settings -> Connectors**.
10. Click **Add custom connector**.
11. Enter:

   ```text
   Name: GroundX Studio
   Remote MCP Server URL: https://api.groundx.ai/mcp
   ```

12. Leave advanced OAuth fields empty unless Claude asks you to review discovered
   settings.
13. Click **Connect**, complete OAuth, and enable the connector in a conversation.

### Codex Desktop

Codex Desktop supports both the plugin and the MCP connector. Install the plugin first,
then add the MCP app.

Install the plugin:

1. Open **Plugins**.
2. Open **Manage** or **Manage marketplaces**.
3. Add a marketplace from this repository:

   ```text
   https://github.com/GroundX-Studio/groundx-agent-harness
   ```

4. Use ref `main`.
5. Leave sparse paths empty.
6. Install **GroundX Agent Harness**.
7. Start a new Codex session.

Connect MCP:

8. Open **Settings -> MCP servers**.
9. Toggle the server type to **Streamable HTTP**.
10. Enter:

    ```text
    https://api.groundx.ai/mcp
    ```

11. Click **Save**.
12. The MCP server should appear in the **From plugins** list with an
    **Authenticate** button.
13. Click **Authenticate** and complete OAuth.

### Codex CLI

Install the plugin:

```sh
codex plugin marketplace add GroundX-Studio/groundx-agent-harness --ref main
codex plugin add groundx-agent-harness@groundx-agent-harness
```

Connect MCP:

```sh
codex mcp add groundx --url https://api.groundx.ai/mcp
codex mcp login groundx
```

Verify:

```sh
codex plugin list
codex mcp list
```

Start a new Codex session after installing.

### Claude Code CLI

Outside VS Code, use the same Claude plugin and MCP commands:

Install the plugin:

```sh
claude plugin marketplace add GroundX-Studio/groundx-agent-harness
claude plugin install groundx-agent-harness@groundx-agent-harness
```

Then run `/reload-plugins` inside Claude Code, or start a new session.

Connect MCP:

```sh
claude mcp add --transport http groundx https://api.groundx.ai/mcp
```

Then run `/mcp`, connect `groundx`, complete OAuth, and start a new session.

## Verification

Run these checks without pasting secrets into chat.

```text
List the GroundX Agent Harness skills you have available.
```

```text
Use the GroundX Agent Harness references to explain the safest document ingest -> status polling -> search flow. Do not ask me for an API key.
```

```text
Show my GroundX account context using the connector. Do not include raw credentials.
```

With a regular user key, normal GroundX API tools should be visible and partner/admin
tools should not be visible.

With a Partner-tier key, connect the same MCP URL once. Partner resource tools should ask
for `customerUsername` when they need to operate on a specific customer account. Do not
paste API keys into prompts.

```text
Use the GroundX Agent Harness extraction workflow guidance to design a schema for this document. If GroundX API tools are connected, ingest the file, check processing status, search or retrieve the processed content, compare the result to these expected fields, and suggest schema or prompt fixes. Do not ask me to paste an API key.
```

You can also run the local helper from a checkout of this repository:

```sh
node scripts/doctor.mjs
```

## Data Handling

Do not commit customer documents, answer keys, private pilot notes, comparison outputs,
credentials, or local run artifacts to this repository.
