# GroundX Agent Harness

GroundX Agent Harness gives Claude, Codex, and other coding agents GroundX-specific
working knowledge. Install it when you want an agent to understand how to use GroundX
well enough to help with:

- ingesting documents, checking processing status, and searching GroundX content
- using GroundX buckets, groups, workflows, APIs, and SDKs correctly
- designing schema-first extraction workflows and comparing results
- planning GroundX on-prem deployments and configuration values
- answering GroundX architecture, product, and company questions with approved context

The harness gives the agent instructions and reference material. To let the agent make
authenticated GroundX API calls, also connect the hosted GroundX API MCP app at
`https://api.groundx.ai/mcp`.

## Easy Mode Install

Choose the client you use. Use a regular GroundX user API key during OAuth unless
you specifically need partner/admin operations.

### VS Code + Claude

Use this path when you want Claude to edit code in VS Code and use GroundX
references while it works.

1. In the Claude Code panel inside VS Code, install the plugin:

   ```text
   /plugin marketplace add GroundX-Studio/groundx-agent-harness
   /plugin install groundx-agent-harness@groundx-agent-harness
   /reload-plugins
   ```

2. In the VS Code integrated terminal, add the hosted GroundX MCP server:

   ```sh
   claude mcp add --transport http groundx https://api.groundx.ai/mcp
   ```

3. In Claude, run `/mcp`, connect `groundx`, and complete the browser OAuth flow
   with your GroundX API key.

4. Start a new Claude Code session in VS Code.

### Claude Desktop

Use this path when you want Claude Desktop to call GroundX API tools. Claude Desktop
uses the hosted MCP connector; it does not install the repository skill package.

1. Open **Claude Desktop -> Settings -> Connectors**.
2. Click **Add custom connector**.
3. Enter:

   ```text
   Name: GroundX Studio
   Remote MCP Server URL: https://api.groundx.ai/mcp
   ```

4. Leave advanced OAuth fields empty unless Claude asks you to review discovered
   settings.
5. Add the connector, click **Connect**, and complete OAuth with your GroundX API
   key.
6. Enable the GroundX connector in a conversation from the connector picker.

### Codex Desktop

Use this path when you want Codex to use the GroundX reference package and call
GroundX API tools.

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
8. Open **Settings -> Apps -> Advanced -> New App**.
9. Enter:

   ```text
   Name: GroundX Studio
   MCP Server URL: https://api.groundx.ai/mcp
   Authentication: OAuth
   ```

10. Leave advanced OAuth fields empty unless Codex asks you to review discovered
    settings.
11. Create the app and complete OAuth with your GroundX API key.
12. Return to **Settings -> Apps**, open **GroundX Studio**, and click **Refresh** if
    the action list is empty.

Expected result: the app information shows URL `https://api.groundx.ai/mcp`,
authorization supported/used as `OAuth`, and actions such as `bucket_list`,
`document_ingestlocal`, `search_content`, or `groundx_account_context`.

### Claude Code CLI

If you use Claude Code outside VS Code, install the same plugin and MCP server:

```text
/plugin marketplace add GroundX-Studio/groundx-agent-harness
/plugin install groundx-agent-harness@groundx-agent-harness
/reload-plugins
```

```sh
claude mcp add --transport http groundx https://api.groundx.ai/mcp
```

Then run `/mcp`, connect `groundx`, complete OAuth, and start a new session.

## Verify Installation

Use non-secret checks first.

### Skill Package Check

For VS Code + Claude, Claude Code CLI, or Codex Desktop:

```text
List the GroundX Agent Harness skills you have available.
```

```text
Use the GroundX Agent Harness references to explain the safest document ingest -> status polling -> search flow. Do not ask me for an API key.
```

### MCP Connector Check

For all three easy-mode clients:

```text
Show my GroundX account context using the connector. Do not include raw credentials.
```

With a regular user key, normal GroundX API tools should be available and partner/admin
tools should not be visible.

### Data Extraction Smoke Test

Use a sanitized sample document and expected fields. Ask:

```text
Use the GroundX Agent Harness extraction workflow guidance to design a schema for this document. If GroundX API tools are connected, ingest the file, check processing status, search or retrieve the processed content, compare the result to these expected fields, and suggest schema or prompt fixes. Do not ask me to paste an API key.
```

You can also run the local helper from a checkout of this repository:

```sh
node scripts/doctor.mjs
```

## Keep Customer Data Private

Do not commit customer documents, answer keys, private pilot notes, comparison outputs,
credentials, or local run artifacts to this repository.
