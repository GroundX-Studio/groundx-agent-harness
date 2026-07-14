# GroundX Agent Harness

GroundX Agent Harness gives your AI agent the GroundX context it needs to help
with:

- document ingest, status checks, and search
- buckets, groups, workflows, APIs, and SDKs
- schema-first extraction workflows
- GroundX on-prem planning
- GroundX product, company, and architecture questions

It is built on the open Agent Skills (`SKILL.md`) standard. Claude and Codex
install it as a one-command plugin; any other skills-capable agent (Cursor,
Replit, Gemini, Windsurf, Copilot, and more) uses the same portable skills by
adding this repository's `skills/` folder. Installing the skills is the primary
step and is what "Agent Harness" is; the hosted MCP server (below) is a separate,
optional add-on.

This repository installs **GroundX Agent Harness**, the public runtime bundle for
agents. The internal **GroundX Agent Harness** is separate and includes
Studio-only web UI, publish, slides, and partner-admin production skills. Those
internal skills are intentionally not included in the public agent harness.

The hosted MCP server is optional and prod-only today. Connect it only when your
agent supports remote MCP and you are working against prod:

```text
https://api.groundx.ai/mcp
```

## Requirements

- A GroundX API key. Sign in or create an account at
  `https://dashboard.groundx.ai`, then create or copy an API key.
- One supported agent (see the client table below).

Wherever you enter your key, use the GroundX sign-in page, an environment
variable, or an approved local secret store. Never paste an API key into chat or
into a tool argument. For authenticated GroundX API calls, set `GROUNDX_API_KEY`
in the shell that starts your agent. Use a regular GroundX user API key unless
GroundX has issued you Partner-tier access.

The skills and the MCP server are separate pieces:

- The skills give the agent GroundX instructions and workflows.
- `GROUNDX_API_KEY` gives SDK/REST access.
- MCP gives the agent authenticated GroundX API tools when your agent supports
  it.
- Install the skills first. Add MCP only when you need its tools.
- Connector tool calls may default to per-tool approval prompts. That is
  expected. You may choose **Always allow** after accepting the broader security
  tradeoff.

Client support:

| Client | Plugin / skills | MCP API tools |
| --- | --- | --- |
| Claude Desktop | Yes | Yes |
| Claude Desktop with Connectors only | No plugin skills; use hosted connector for MCP tools | Yes |
| Codex Desktop | Yes | Yes |
| Claude CLI | Yes | Yes |
| Codex CLI | Yes | Yes |
| VS Code | Yes | Yes |
| Everything else (Cursor, Replit, Gemini, Windsurf, Copilot, and more) | Yes, via the portable `skills/` folder | If your agent supports remote MCP |

## Installation

### Claude Desktop

Most Claude app builds expose the **Plugins/Cowork** surface and install the
plugin from a marketplace. Builds that expose only **Connectors** use the hosted
MCP connector path at the end of this section.

**Install the plugin (personal marketplace).** Route: **Customize -> Plugins ->
Personal plugins + -> Add marketplace -> Add from a repository**.

1. Open **Customize -> Plugins -> Personal plugins + -> Add marketplace**.
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

**Organization distribution (Team/Enterprise admins).** Claude organization
GitHub sync uses a private or internal marketplace repository.
The public repo is not supported as the direct organization marketplace sync target.

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

4. In **Claude**, go to **Organization settings -> Plugins**, click **Add
   plugin**, select **GitHub**, and enter the private/internal organization
   marketplace repository (not `GroundX-Studio/groundx-agent-harness`).
5. Complete the sync so **GroundX Agent Harness** appears in the organization's
   plugin list. Users install it from Claude **Cowork** or **Code** (**+ -> Add
   plugin -> GroundX Agent Harness**), then run `/reload-plugins` or start a new
   session.

**Connect MCP (optional).**

```sh
claude mcp add --transport http groundx https://api.groundx.ai/mcp
```

Run `/mcp`, connect `groundx`, enter your key on the GroundX sign-in page, and
start a new Claude Code session.

**Connector-only builds.** If your Claude Desktop build exposes only
**Connectors** (no Plugins/Cowork surface), it has no plugin skills; the
connector provides MCP tools only:

1. Open **Claude Desktop -> Customize -> Connectors**.
2. Click **+**, then **Add custom connector**.
3. Enter:

   ```text
   Name: GroundX API
   Remote MCP Server URL: https://api.groundx.ai/mcp
   ```

4. Leave advanced OAuth fields empty unless Claude asks you to review discovered
   settings.
5. Click **Add** first, then **Connect** on the next screen.
6. Enter your key on the GroundX sign-in page.
7. Enable the connector in a conversation. Expect per-tool approval prompts by
   default; choose **Always allow** only after accepting the broader connector
   permission.

### Claude Code Desktop

Claude Code Desktop supports plugins for local and SSH sessions. Install with the
same commands as Claude CLI:

```sh
claude plugin marketplace add GroundX-Studio/groundx-agent-harness
claude plugin install groundx-agent-harness@groundx-agent-harness
```

Run `/reload-plugins` or start a new session. Connecting MCP is optional:

```sh
claude mcp add --transport http groundx https://api.groundx.ai/mcp
```

Run `/mcp`, connect `groundx`, enter your key on the GroundX sign-in page, and
start a new session.

### Codex Desktop

Install the plugin first, then add the MCP app.

Install the plugin:

1. Open **Plugins -> Manage** (or **Manage marketplaces**).
2. Add a marketplace from this repository, using ref `main` and leaving sparse
   paths empty:

   ```text
   https://github.com/GroundX-Studio/groundx-agent-harness
   ```

3. Install **GroundX Agent Harness** and start a new Codex session.

Connect MCP (optional):

4. Open **Settings -> MCP servers**, toggle the server type to **Streamable
   HTTP**, and enter:

   ```text
   https://api.groundx.ai/mcp
   ```

5. Click **Save**. The saved MCP server entry in the MCP server list should show
   an **Authenticate** button; click it and enter your key on the GroundX sign-in
   page.

### Claude CLI

Install the plugin:

```sh
claude plugin marketplace add GroundX-Studio/groundx-agent-harness
claude plugin install groundx-agent-harness@groundx-agent-harness
```

Then run `/reload-plugins` inside Claude Code, or start a new session. If
`claude plugin` is not found, update Claude Code first.

Connect MCP (optional):

```sh
claude mcp add --transport http groundx https://api.groundx.ai/mcp
```

Run `/mcp`, connect `groundx`, enter your key on the GroundX sign-in page, and
start a new session.

### Codex CLI

Install the plugin:

```sh
codex plugin marketplace add GroundX-Studio/groundx-agent-harness --ref main
codex plugin add groundx-agent-harness@groundx-agent-harness
```

Connect MCP (optional):

```sh
codex mcp add groundx --url https://api.groundx.ai/mcp
codex mcp login groundx
```

Verify and start a new Codex session:

```sh
codex plugin list
codex mcp list
```

### VS Code

Open the VS Code integrated terminal (Ctrl+` / Cmd+`) and run the install for
your agent.

Claude Code:

```sh
claude plugin marketplace add GroundX-Studio/groundx-agent-harness
claude plugin install groundx-agent-harness@groundx-agent-harness
```

Codex:

```sh
codex plugin marketplace add GroundX-Studio/groundx-agent-harness --ref main
codex plugin add groundx-agent-harness@groundx-agent-harness
```

Then reload plugins or start a new session. If `claude plugin` is not found,
update Claude Code first.

Connect MCP (optional), in the same terminal. Claude Code:

```sh
claude mcp add --transport http groundx https://api.groundx.ai/mcp
```

Codex:

```sh
codex mcp add groundx --url https://api.groundx.ai/mcp
codex mcp login groundx
```

Connect (`/mcp` for Claude Code), then enter your key on the GroundX sign-in
page.

### Everything else

The harness is built on the open Agent Skills (`SKILL.md`) standard, so agents
beyond Claude and Codex (Cursor, Replit, Gemini, Windsurf, Copilot, and more)
can use it too.

1. Clone the harness:

   ```sh
   git clone https://github.com/GroundX-Studio/groundx-agent-harness
   ```

2. Add its `skills/` folder to your agent's skills directory. See your agent's
   docs for where skills live.
3. Reload or restart your agent so it picks up the skills.

If your agent supports remote MCP, you can also add the optional tools: in your
agent's MCP settings, add a Streamable HTTP server with URL
`https://api.groundx.ai/mcp`, authenticate, and enter your key on the GroundX
sign-in page.
## Try GroundX Studio

See your agent put GroundX to work in about five minutes. The agent does the
work: it creates the bucket and ingests the sample itself, so there are no manual
dashboard steps. Your agent needs to reach GroundX for these, through the MCP
tools or your API key; a chat-only agent can explain the steps but cannot run
them.

1. **Hand it a document.** Have your agent set up a bucket and load a sample
   invoice, then tell you when it is ready to search.
2. **Ask about it.** For example: "What is the total due on that invoice, and
   which line does it come from?"
3. **Pull out the details.** For example: "Pull the invoice number, date, vendor,
   each line item, and the total into a table."
4. **Make extraction accurate at scale.** For real volume, have it build an
   extraction workflow that grades itself against an answer key and tunes the
   schema and prompts until it is at least 90% accurate.

Then point it at your own documents and go further: ask for a summary report, a
way to classify them, or a small app to search them.

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

With a regular user key, normal GroundX API tools should be visible and
partner/admin tools should not be visible.

With a Partner-tier key, connect the same MCP URL once. Partner resource tools
should ask for `customerUsername` when they need to operate on a specific
customer account. Do not paste API keys into prompts.

```text
Use the GroundX Agent Harness extraction workflow guidance to design a schema for this document. If GroundX API tools are connected, ingest the file, check processing status, search or retrieve the processed content, compare the result to these expected fields, and suggest schema or prompt fixes. Do not ask me to paste an API key.
```

You can also run the local helper from a checkout of this repository:

```sh
node scripts/doctor.mjs
```

## Data Handling

Do not commit customer documents, answer keys, private pilot notes, comparison
outputs, credentials, or local run artifacts to this repository.
