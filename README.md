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
- One of: VS Code + Claude, Claude Desktop, or Codex Desktop.
- Enter API keys only in the GroundX OAuth screen. Do not paste keys into prompts.

Use a regular GroundX user API key unless you specifically need partner/admin
operations.

## Installation

### VS Code + Claude

1. Open the VS Code integrated terminal and confirm the Claude Code CLI supports
   plugins:

   ```sh
   claude plugin --help
   ```

   If this command is missing, update Claude Code first. The `/plugin` slash
   command is not available in every VS Code chat surface.

2. Add the GroundX marketplace and install the plugin from the terminal:

   ```sh
   claude plugin marketplace add GroundX-Studio/groundx-agent-harness
   claude plugin install groundx-agent-harness@groundx-agent-harness
   ```

   If you use the **Manage Plugins** UI instead, enter
   `GroundX-Studio/groundx-agent-harness` as the marketplace source. Do not use
   the full GitHub URL in that field.

3. Add the hosted GroundX MCP server:

   ```sh
   claude mcp add --transport http groundx https://api.groundx.ai/mcp
   ```

4. Restart or reload Claude Code, run `/mcp`, connect `groundx`, complete OAuth,
   and start a new Claude Code session.

### Claude Desktop

Claude Desktop connects GroundX API tools through MCP.

1. Open **Claude Desktop -> Settings -> Connectors**.
2. Click **Add custom connector**.
3. Enter:

   ```text
   Name: GroundX Studio
   Remote MCP Server URL: https://api.groundx.ai/mcp
   ```

4. Leave advanced OAuth fields empty unless Claude asks you to review discovered
   settings.
5. Click **Connect**, complete OAuth, and enable the connector in a conversation.

### Codex Desktop

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
8. Open **Settings -> Apps -> Advanced -> New App** and enter:

   ```text
   Name: GroundX Studio
   MCP Server URL: https://api.groundx.ai/mcp
   Authentication: OAuth
   ```

9. Leave advanced OAuth fields empty unless Codex asks you to review discovered
   settings.
10. Create the app, complete OAuth, and click **Refresh** if the action list is empty.

### Claude Code CLI

Outside VS Code, use the same Claude plugin and MCP commands:

```sh
claude plugin marketplace add GroundX-Studio/groundx-agent-harness
claude plugin install groundx-agent-harness@groundx-agent-harness
```

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
