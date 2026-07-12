# GroundX Agent Harness

GroundX Agent Harness gives Claude and Codex the GroundX context they need to help
with:

- document ingest, status checks, and search
- buckets, groups, workflows, APIs, and SDKs
- schema-first extraction workflows
- GroundX on-prem planning
- GroundX product, company, and architecture questions

For authenticated GroundX API calls, set `GROUNDX_API_KEY` in the shell that starts
your agent. Use a regular GroundX user API key unless GroundX has issued you
Partner-tier access.

This repository installs **GroundX Agent Harness**, the public runtime bundle for
agents. The internal **GroundX Studio Harness** is separate and includes Studio-only
web UI, publish, slides, and partner-admin production skills. Those internal skills
are intentionally not included in the public agent harness.

The hosted MCP server is optional and currently production-only. Connect it only when
your client supports MCP and the target environment is prod:

```text
https://api.groundx.ai/mcp
```

## Requirements

- A GroundX API key. For prod, sign in or create an account at
  `https://dashboard.groundx.ai`, create or copy a prod API key, and keep it in
  local secret storage or the GroundX OAuth page. Never paste API keys into chat.
- One of: VS Code (with the Claude Code or Codex CLI), Claude Code Desktop, Claude
  Desktop, Codex Desktop, Codex CLI, or Claude Code CLI. Any other agent that supports
  the Agent Skills (`SKILL.md`) standard can also use the harness skills — see
  "Other skills-capable agents" below.
- Put API keys in environment variables or approved local secret stores. Do not paste
  keys into prompts.
- Dev and prod use different API keys. For prod, leave `GROUNDX_BASE_URL` unset. For
  dev, set `GROUNDX_BASE_URL=https://devapi.groundx.ai/api`.
- Prod keys are created in `https://dashboard.groundx.ai`; dev keys are created in
  `https://devdashboard.groundx.ai`. The dashboards use the same Cognito
  email/password, but buckets, API keys, documents, and account data are separate.

The harness plugin and the MCP server are separate pieces:

- The plugin gives the agent GroundX instructions and workflows.
- `GROUNDX_API_KEY` gives SDK/REST access.
- MCP gives the agent authenticated GroundX API tools for prod when supported.
- Install the plugin first. Add MCP only when you need prod MCP tools.
- Connector tool calls may default to per-tool approval prompts. That is expected.
  You may choose **Always allow** after accepting the broader security tradeoff.

Client support:

| Client | Plugin / skills | MCP API tools |
| --- | --- | --- |
| VS Code (Claude Code or Codex CLI) | Yes | Yes |
| Claude Code Desktop | Yes | Yes |
| Claude app with Plugins/Cowork | Yes | Yes |
| Claude Desktop with Connectors only | No plugin skills; use hosted connector for MCP tools | Yes |
| Codex Desktop | Yes | Yes |
| Codex CLI | Yes | Yes |
| Claude Code CLI | Yes | Yes |
| Other skills-capable agents (Cursor, Gemini, Windsurf, Copilot, …) | Yes — portable Agent Skills, added manually | Yes, when the agent supports MCP |

The one-command plugin install is available on Claude and Codex. The harness content
itself is standard Agent Skills (`SKILL.md`) under `skills/`, so any other
skills-capable agent (Cursor, Gemini, Windsurf, GitHub Copilot, and more) can use the
same skills by adding that folder to its skills directory. See "Other skills-capable
agents".

## Installation

### VS Code

In the VS Code integrated terminal, run the install commands for the agent you use.

Claude Code:

```sh
claude plugin --help
claude plugin marketplace add GroundX-Studio/groundx-agent-harness
claude plugin install groundx-agent-harness@groundx-agent-harness
```

If `claude plugin --help` does not work, update Claude Code first. The `/plugin`
slash command is not available in every VS Code chat surface.

Codex:

```sh
codex plugin marketplace add GroundX-Studio/groundx-agent-harness --ref main
codex plugin add groundx-agent-harness@groundx-agent-harness
```

Another agent? See "Other skills-capable agents".

Connect MCP, optional prod-only:

1. Add the hosted GroundX MCP server.

   Claude Code:

   ```sh
   claude mcp add --transport http groundx https://api.groundx.ai/mcp
   ```

   Codex:

   ```sh
   codex mcp add groundx --url https://api.groundx.ai/mcp
   codex mcp login groundx
   ```

2. Connect (`/mcp` in Claude Code), enter the prod API key on the GroundX OAuth
   page, and start a new session.

### Claude Code Desktop

Claude Code Desktop supports plugins for local and SSH sessions, but not remote
sessions.

Install the plugin with either method.

**Method 1 — Organization plugin sync**

Use this when a Team or Enterprise admin wants org-wide distribution. Claude
organization GitHub sync uses a private or internal marketplace repository; the
public repo is not supported as the direct organization marketplace sync target.

1. Create or choose a private/internal organization marketplace repository.
2. Vendor/copy this public bundle into that repository at:

   ```text
   plugins/groundx-agent-harness/
   ```

   The private marketplace repository should include:

   ```text
   .claude-plugin/marketplace.json
   plugins/groundx-agent-harness/.claude-plugin/marketplace.json
   plugins/groundx-agent-harness/README.md
   plugins/groundx-agent-harness/scripts/
   plugins/groundx-agent-harness/skills/
   ```

3. Create the private marketplace root `.claude-plugin/marketplace.json` with a
   complete marketplace manifest. Use your organization for the root `owner`,
   keep the public bundle plugin entry's `description`, `strict`, and `skills`
   fields, and change only the plugin `source` to this repo-relative path. You
   may replace `author` with your approved organization publisher value:

   ```json
   {
     "name": "groundx-agent-harness-marketplace",
     "owner": {
       "name": "Your Organization"
     },
     "plugins": [
       {
         "name": "groundx-agent-harness",
         "description": "GroundX agent runtime harness for API use, schema-first extraction, on-prem deployment, architecture, and supported GTM guidance.",
         "author": {
           "name": "GroundX"
         },
         "source": "./plugins/groundx-agent-harness",
         "strict": false,
         "skills": [
           "./skills/groundx-api",
           "./skills/groundx-mcp",
           "./skills/groundx-extraction-workflows",
           "./skills/groundx-on-prem",
           "./skills/groundx-architecture",
           "./skills/product-brand-gtm",
           "./skills/master-brand-gtm",
           "./skills/groundx-python"
         ]
       }
     ]
   }
   ```

4. In **Claude**, go to **Organization settings -> Plugins**.
5. Click **Add plugin** and select **GitHub** as the source.
6. Enter the private/internal organization marketplace repository, not:

   ```text
   GroundX-Studio/groundx-agent-harness
   ```

7. Complete the sync flow so **GroundX Agent Harness** appears in the organization's
   plugin list.
8. Individual users can then install it from Claude **Cowork** or **Code**:
   - Click the **+** symbol.
   - Choose **Add plugin**.
   - Select **GroundX Agent Harness** from the organization plugins.
9. Run `/reload-plugins`, or start a new Claude Code session.

**Method 2 — Personal marketplace**

Route: **Customize -> Plugins -> Personal plugins + -> Add marketplace -> Add
from a repository**.

1. In a Claude app build that shows the Plugins/Cowork surface, open
   **Customize -> Plugins -> Personal plugins + -> Add marketplace**.
2. Choose **Add from a repository**.
3. When prompted for a repository, enter:

   ```text
   GroundX-Studio/groundx-agent-harness
   ```

4. A GitHub account is not required for this public repository. If the repository
   list cannot load, type `GroundX-Studio/groundx-agent-harness` directly and
   continue.
5. Click **Sync**.
6. Open the personal directory or **GroundX Agent Harness** card and click
   **Install**.
7. Run `/reload-plugins`, or start a new Claude Code session.

Connect MCP, optional prod-only:

```sh
claude mcp add --transport http groundx https://api.groundx.ai/mcp
```

Run `/mcp`, connect `groundx`, enter the prod API key on the GroundX OAuth page,
and start a new Claude Code session.

### Claude Desktop

Some Claude app builds expose the Plugins/Cowork surface and can use the personal
marketplace plugin path above. Claude Desktop builds that only expose Connectors use
the hosted MCP connector path below.

Connect MCP, optional prod-only:

1. Open **Claude Desktop -> Customize -> Connectors**.
2. Click **+**, then click **Add custom connector**.
3. Enter:

   ```text
   Name: GroundX API
   Remote MCP Server URL: https://api.groundx.ai/mcp
   ```

4. Leave advanced OAuth fields empty unless Claude asks you to review discovered
   settings.
5. Click **Add first**, then click **Connect on the next screen**.
6. Enter the prod API key on the **GroundX OAuth page**.
7. Enable the connector in a conversation.
8. Expect per-tool approval prompts by default. Choose **Always allow** only after
   accepting the broader connector permission.

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

Connect MCP, optional prod-only:

8. Open **Settings -> MCP servers**.
9. Toggle the server type to **Streamable HTTP**.
10. Enter:

    ```text
    https://api.groundx.ai/mcp
    ```

11. Click **Save**.
12. The saved MCP server entry in the MCP server list should show an
    **Authenticate** button.
13. Click **Authenticate** and enter the prod API key on the **GroundX OAuth
    page**.

### Codex CLI

Install the plugin:

```sh
codex plugin marketplace add GroundX-Studio/groundx-agent-harness --ref main
codex plugin add groundx-agent-harness@groundx-agent-harness
```

Connect MCP, optional prod-only:

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

Connect MCP, optional prod-only:

```sh
claude mcp add --transport http groundx https://api.groundx.ai/mcp
```

Then run `/mcp`, connect `groundx`, enter the prod API key on the GroundX OAuth
page, and start a new session.

### Other skills-capable agents

Agents beyond Claude and Codex — Cursor, Gemini, Windsurf, GitHub Copilot, and more —
can use the harness through the open Agent Skills (`SKILL.md`) standard. There is no
one-command install; add the skills manually.

1. Clone this repository:

   ```sh
   git clone https://github.com/GroundX-Studio/groundx-agent-harness
   ```

2. Add the repository's `skills/` folder to your agent's skills directory. See your
   agent's documentation for where skills live and whether placement is automatic or
   manual.
3. Reload or restart the agent so it picks up the skills.

Connect MCP, optional prod-only: if your agent supports MCP, add a Streamable HTTP
server pointing at `https://api.groundx.ai/mcp`, authenticate, and enter the prod API
key on the GroundX OAuth page.

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
