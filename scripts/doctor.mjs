#!/usr/bin/env node
/**
 * doctor.mjs — print install and verification help for GroundX Agent Harness.
 *
 * This helper is copied into the public repository. It does not install anything
 * automatically and never asks for API keys.
 *
 * Usage:
 *   node scripts/doctor.mjs
 *   node scripts/doctor.mjs vscode-claude
 *   node scripts/doctor.mjs claude-code-desktop
 *   node scripts/doctor.mjs claude-desktop
 *   node scripts/doctor.mjs codex-desktop
 *   node scripts/doctor.mjs codex-cli
 *   node scripts/doctor.mjs claude-code
 *   node scripts/doctor.mjs mcp
 *   node scripts/doctor.mjs skills
 */

import { existsSync, readFileSync } from "node:fs";
import { spawnSync } from "node:child_process";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const HERE = dirname(fileURLToPath(import.meta.url));
const ROOT = resolve(HERE, "..");
const requestedClient = process.argv[2] ?? "all";
const clientAliases = new Map([
  ["claude", "claude-code"],
  ["codex", "codex-desktop"],
]);
const client = clientAliases.get(requestedClient) ?? requestedClient;
const validClients = new Set([
  "all",
  "claude-code",
  "claude-code-desktop",
  "claude-desktop",
  "codex-cli",
  "codex-desktop",
  "vscode-claude",
  "mcp",
  "skills",
]);

if (!validClients.has(client)) {
  console.error(`Unknown client "${requestedClient}". Use one of: ${[...validClients].join(", ")}`);
  process.exit(2);
}

function section(title) {
  console.log(`\n## ${title}`);
}

function code(value) {
  console.log("");
  console.log(value.trim());
}

function validateLocalBundle() {
  section("Local Bundle Check");
  const validator = join(ROOT, "scripts/validate-public-bundle.mjs");
  if (!existsSync(validator)) {
    console.log("Missing scripts/validate-public-bundle.mjs. This checkout is incomplete.");
    return;
  }
  const result = spawnSync(process.execPath, [
    validator,
    "--allow-missing-provenance",
  ], {
    cwd: ROOT,
    encoding: "utf8",
  });
  if (result.status === 0) {
    console.log("Local public bundle shape looks valid.");
  } else {
    console.log("Local public bundle validation failed:");
    console.log(result.stdout.trim());
    console.log(result.stderr.trim());
  }
}

function readPublicPolicyMetadata() {
  const rulesPath = join(ROOT, "scripts/public-bundle-rules.json");
  if (!existsSync(rulesPath)) return null;
  try {
    return JSON.parse(readFileSync(rulesPath, "utf8"));
  } catch {
    return null;
  }
}

function skillsAndRuntime() {
  section("Skills And Runtime");
  const metadata = readPublicPolicyMetadata();
  if (!metadata?.skills) {
    console.log("Missing generated public policy metadata. Run scripts/validate-public-bundle.mjs.");
    return;
  }
  for (const [skillName, skillPolicy] of Object.entries(metadata.skills)) {
    const runtime = metadata.runtimeFamilies?.[skillPolicy.runtimeFamily];
    const tools = runtime?.tools?.length ? runtime.tools.join(", ") : "none";
    console.log(`- ${skillName}: runtime=${skillPolicy.runtimeFamily}; tools=${tools}`);
  }
}

function vscodeClaude() {
  section("VS Code + Claude");
  console.log("Install the plugin from the VS Code integrated terminal:");
  code(`
claude plugin --help
claude plugin marketplace add GroundX-Studio/groundx-agent-harness
claude plugin install groundx-agent-harness@groundx-agent-harness
`);
  console.log("If claude plugin --help does not work, update Claude Code first. The /plugin slash command is not available in every VS Code chat surface.");
  console.log("Add the hosted GroundX MCP server:");
  code(`
claude mcp add --transport http groundx https://api.groundx.ai/mcp
`);
  console.log("Run /mcp, connect groundx, complete OAuth with a GroundX API key, then start a new Claude Code session in VS Code.");
}

function claudeCodeDesktop() {
  section("Claude Code Desktop");
  console.log("Claude Code Desktop supports plugins for local and SSH sessions, but not remote sessions.");
  console.log("Method 1 — organization plugin sync:");
  code(`
Organization settings -> Plugins -> Add plugins -> Sync from GitHub
Repository: GroundX-Studio/groundx-agent-harness
`);
  console.log("After the organization sync completes, users can install GroundX Agent Harness from Claude Cowork or Code with + -> Add plugin. Then run /reload-plugins or start a new session.");
  console.log("Method 2 — personal marketplace:");
  code(`
Customize -> Personal plugins + -> Create plugin -> Add marketplace
Repository: GroundX-Studio/groundx-agent-harness
Sync -> Personal -> GroundX Agent Harness -> + install
`);
  console.log("Then run /reload-plugins or start a new session.");
  console.log("Add the hosted GroundX MCP server:");
  code(`
claude mcp add --transport http groundx https://api.groundx.ai/mcp
`);
  console.log("Run /mcp, connect groundx, complete OAuth with a GroundX API key, then start a new Claude Code session.");
}

function claudeDesktop() {
  section("Claude Desktop");
  console.log("Connect the hosted MCP connector:");
  code(`
Settings -> Connectors -> Add custom connector
Name: GroundX Studio
Remote MCP Server URL: https://api.groundx.ai/mcp
`);
  console.log("Leave advanced OAuth fields empty unless Claude asks you to review discovered settings. Add the connector, click Connect, authorize with a GroundX API key, then enable the connector in a conversation.");
}

function codexDesktop() {
  section("Codex Desktop");
  console.log("In Codex, open Plugins, then Manage or Manage marketplaces. Add a marketplace from this repository:");
  code(`
Repository URL: https://github.com/GroundX-Studio/groundx-agent-harness
Ref: main
Sparse paths: leave empty
`);
  console.log("Then install GroundX Agent Harness from that marketplace and start a new Codex session.");
  console.log("To add authenticated GroundX API tools, add the hosted MCP server in Codex:");
  code(`
Settings -> MCP servers
Toggle to Streamable HTTP
URL: https://api.groundx.ai/mcp
Save
`);
  console.log("The server should appear in the From plugins list with an Authenticate button. Click Authenticate and complete OAuth.");
}

function codexCli() {
  section("Codex CLI");
  console.log("Install the plugin from the terminal:");
  code(`
codex plugin marketplace add GroundX-Studio/groundx-agent-harness --ref main
codex plugin add groundx-agent-harness@groundx-agent-harness
`);
  console.log("Connect and authenticate the hosted GroundX MCP server:");
  code(`
codex mcp add groundx --url https://api.groundx.ai/mcp
codex mcp login groundx
`);
  console.log("Verify plugin and MCP registration:");
  code(`
codex plugin list
codex mcp list
`);
  console.log("Start a new Codex session after installing.");
}

function claudeCode() {
  section("Claude Code CLI");
  console.log("Install the plugin from the terminal, then add the hosted GroundX MCP server:");
  code(`
claude plugin marketplace add GroundX-Studio/groundx-agent-harness
claude plugin install groundx-agent-harness@groundx-agent-harness
`);
  console.log("Then run /reload-plugins inside Claude Code, or start a new session.");
  code(`
claude mcp add --transport http groundx https://api.groundx.ai/mcp
`);
  console.log("Run /mcp, connect groundx, complete OAuth, then start a new session.");
}

function mcp() {
  section("Hosted GroundX API MCP");
  console.log("For clients that support remote MCP/connectors, connect the hosted GroundX API MCP endpoint:");
  code("https://api.groundx.ai/mcp");
  console.log("Do not paste API keys into prompts. Use the deployment-managed OAuth flow or connector install flow.");
}

function verify() {
  section("Non-secret Verification Prompts");
  code(`
List the GroundX Agent Harness skills you have available.

Use the GroundX Agent Harness references to explain the safest document ingest -> status polling -> search flow. Do not ask me for an API key.

If GroundX API tools are visible, show my GroundX account context using the connector. Do not include raw credentials.

With a regular user key, confirm normal GroundX tools are available and partner/admin tools are not visible.

Use the GroundX Agent Harness extraction workflow guidance to design a schema for a sanitized sample financial document. If GroundX API tools are connected, ingest the file, check processing status, search or retrieve processed content, compare the result to expected fields, and suggest schema or prompt fixes. Do not ask me to paste an API key.
`);
}

validateLocalBundle();
if (client === "all" || client === "vscode-claude") vscodeClaude();
if (client === "all" || client === "claude-code-desktop") claudeCodeDesktop();
if (client === "all" || client === "claude-desktop") claudeDesktop();
if (client === "all" || client === "codex-desktop") codexDesktop();
if (client === "all" || client === "codex-cli") codexCli();
if (client === "all" || client === "claude-code") claudeCode();
if (client === "all" || client === "mcp") mcp();
if (client === "skills") skillsAndRuntime();
verify();
