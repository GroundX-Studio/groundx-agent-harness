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

## Install

Choose the client you use.

### Claude Code

From inside Claude Code, add the GroundX marketplace and install the plugin:

```text
/plugin marketplace add GroundX-Studio/groundx-agent-harness
/plugin install groundx-agent-harness@groundx-agent-harness
```

Then start a new Claude Code session.

CLI equivalent:

```sh
claude plugin marketplace add GroundX-Studio/groundx-agent-harness
claude plugin install groundx-agent-harness@groundx-agent-harness
```

### VS Code + Claude

If you use Claude Code inside VS Code, run the same Claude plugin commands in the
Claude Code session:

```text
/plugin marketplace add GroundX-Studio/groundx-agent-harness
/plugin install groundx-agent-harness@groundx-agent-harness
```

Restart the Claude Code session inside VS Code after installing.

### Codex App

In Codex:

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

## Connect GroundX API Tools In Codex

The plugin gives Codex the GroundX agent instructions. The hosted MCP app gives Codex
authenticated GroundX API tools.

1. Open **Settings -> Apps** in Codex.
2. Click **Advanced**.
3. Click **New App**.
4. Enter:

   ```text
   Name: GroundX Studio
   MCP Server URL: https://api.groundx.ai/mcp
   Authentication: OAuth
   ```

5. Leave advanced OAuth fields empty unless Codex asks you to review discovered
   settings. Codex should discover the OAuth metadata from the MCP server.
6. Accept the custom MCP server warning.
7. Click **Create**.
8. Complete the GroundX authorization screen with a GroundX API key.
9. Return to **Settings -> Apps**, open **GroundX Studio**, and click **Refresh** if
   the action list is empty.

Expected result: the app information shows URL `https://api.groundx.ai/mcp`,
authorization supported/used as `OAuth`, and actions such as `bucket_list`,
`document_ingestlocal`, `search_content`, or `groundx_account_context`.

## Remote MCP / Connector Fallback

For clients that support remote MCP or hosted connectors but not plugins, connect the
hosted GroundX API MCP endpoint:

```text
https://api.groundx.ai/mcp
```

Use the deployment-managed OAuth/connector flow. Do not put API keys, refresh tokens,
client secrets, or user auth state in prompts or checked-in files.

## Verify Installation

Use non-secret checks first:

```text
List the GroundX Agent Harness skills you have available.
```

```text
Use the GroundX Agent Harness references to explain the safest document ingest -> status polling -> search flow. Do not ask me for an API key.
```

If the GroundX API connector is connected:

```text
Show my GroundX account context using the connector. Do not include raw credentials.
```

You can also run the local helper from a checkout of this repository:

```sh
node scripts/doctor.mjs
```

## Keep Customer Data Private

Do not commit customer documents, answer keys, private pilot notes, comparison outputs,
credentials, or local run artifacts to this repository.
