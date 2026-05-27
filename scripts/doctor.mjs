#!/usr/bin/env node
/**
 * doctor.mjs — print install and verification help for GroundX Agent Harness.
 *
 * This helper is copied into the public repository. It does not install anything
 * automatically and never asks for API keys.
 *
 * Usage:
 *   node scripts/doctor.mjs
 *   node scripts/doctor.mjs claude
 *   node scripts/doctor.mjs codex
 *   node scripts/doctor.mjs vscode-claude
 *   node scripts/doctor.mjs mcp
 */

import { existsSync } from "node:fs";
import { spawnSync } from "node:child_process";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const HERE = dirname(fileURLToPath(import.meta.url));
const ROOT = resolve(HERE, "..");
const client = process.argv[2] ?? "all";
const validClients = new Set(["all", "claude", "codex", "vscode-claude", "mcp"]);

if (!validClients.has(client)) {
  console.error(`Unknown client "${client}". Use one of: ${[...validClients].join(", ")}`);
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

function claude() {
  section("Claude Code");
  console.log("From inside Claude Code, add the GroundX marketplace and install the plugin:");
  code(`
/plugin marketplace add GroundX-Studio/groundx-agent-harness
/plugin install groundx-agent-harness@groundx-agent-harness
`);
  console.log("CLI equivalent:");
  code(`
claude plugin marketplace add GroundX-Studio/groundx-agent-harness
claude plugin install groundx-agent-harness@groundx-agent-harness
`);
  console.log("Start a new Claude Code session after installing.");
}

function vscodeClaude() {
  section("VS Code + Claude");
  console.log("If you use Claude Code inside VS Code, run the same plugin commands in the Claude Code session:");
  code(`
/plugin marketplace add GroundX-Studio/groundx-agent-harness
/plugin install groundx-agent-harness@groundx-agent-harness
`);
  console.log("Restart the Claude Code session inside VS Code after installing.");
}

function codex() {
  section("Codex App");
  console.log("In Codex, open Plugins, then Manage or Manage marketplaces. Add a marketplace from this repository:");
  code(`
Repository URL: https://github.com/GroundX-Studio/groundx-agent-harness
Ref: main
Sparse paths: leave empty
`);
  console.log("Then install GroundX Agent Harness from that marketplace and start a new Codex session.");
  console.log("To add authenticated GroundX API tools, add the hosted MCP app in Codex:");
  code(`
Settings -> Apps -> Advanced -> New App
Name: GroundX Studio
MCP Server URL: https://api.groundx.ai/mcp
Authentication: OAuth
`);
  console.log("Leave advanced OAuth fields empty unless Codex asks you to review discovered settings. Create the app, authorize with a GroundX API key, then refresh the app if the action list is empty.");
}

function mcp() {
  section("Remote MCP / Connector Fallback");
  console.log("For clients that support remote MCP/connectors but not plugins, connect the hosted GroundX API MCP endpoint:");
  code("https://api.groundx.ai/mcp");
  console.log("Do not paste API keys into prompts. Use the deployment-managed OAuth flow or connector install flow.");
}

function verify() {
  section("Non-secret Verification Prompts");
  code(`
List the GroundX Agent Harness skills you have available.

Use the GroundX Agent Harness references to explain the safest document ingest -> status polling -> search flow. Do not ask me for an API key.

If GroundX API tools are visible, show my GroundX account context using the connector. Do not include raw credentials.
`);
}

validateLocalBundle();
if (client === "all" || client === "claude") claude();
if (client === "all" || client === "codex") codex();
if (client === "all" || client === "vscode-claude") vscodeClaude();
if (client === "all" || client === "mcp") mcp();
verify();
