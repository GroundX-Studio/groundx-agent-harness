# GroundX Agent Harness

GroundX Agent Harness is the customer-facing plugin bundle for agents working with
GroundX. It includes public-safe guidance for:

- GroundX API authentication, ingest, search, buckets, groups, workflows, and SDK use
- schema-first extraction workflow authoring and comparison
- GroundX on-prem deployment planning and values authoring
- GroundX architecture facts for technical due diligence
- approved GroundX and Valantor product/company messaging references

This public bundle intentionally excludes internal managed-project lifecycle tools,
Partner-only APIs, web UI scaffold production, slide production, and the local
Studio lifecycle MCP server. Use the hosted GroundX API connector for API operations.

## Quick Start

Use this public repository target:

```text
GroundX-Studio/groundx-agent-harness
```

After installation, start a new agent session so the plugin and skills are loaded.
If GroundX API tools are not visible, connect the hosted GroundX API connector and
retry tool discovery. Do not paste API keys into prompts.

## Claude Code

In Claude Code, add the public repository as a plugin marketplace and install the
plugin:

```text
/plugin marketplace add GroundX-Studio/groundx-agent-harness
/plugin install groundx-agent-harness@groundx-agent-harness
```

Then start a new Claude Code session.

## VS Code + Claude

If you are using the Claude Code extension for VS Code, use the same Claude Code
plugin commands inside that VS Code Claude session:

```text
/plugin marketplace add GroundX-Studio/groundx-agent-harness
/plugin install groundx-agent-harness@groundx-agent-harness
```

This path assumes the Claude Code plugin flow is available inside VS Code. If the
extension cannot see the plugin after install, restart the Claude Code session inside
VS Code.

## Codex

In Codex:

1. Open **Plugins -> Manage -> Marketplace -> Add marketplace**.
2. Enter:

   ```text
   https://github.com/GroundX-Studio/groundx-agent-harness
   ```

3. Use ref:

   ```text
   main
   ```

4. Leave sparse paths empty.
5. Install **GroundX Agent Harness** from the added marketplace.
6. Start a new Codex session.

### Add the hosted GroundX MCP app in Codex

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

## Public Bundle Validation

This repository is generated from the internal `groundx-studio-harness` source repo.
Public CI runs:

```sh
node scripts/validate-public-bundle.mjs
```

That check verifies public manifests, skill paths, absence of local lifecycle MCP,
absence of excluded internal skill surfaces, provenance, and secret hygiene.

## Private Work

Do not commit customer documents, answer keys, private pilot notes, comparison outputs,
credentials, or local run artifacts to this repository. Keep private work outside the
repo or in ignored local work directories when using OpenSpec in an implementation repo.

## Generated Source

Skill content in this repository is generated from `groundx-studio-harness`. Do not
hand-edit generated skill content here. Make source changes in the internal harness and
sync them into this repository through the public release process.
