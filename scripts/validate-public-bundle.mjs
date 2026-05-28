#!/usr/bin/env node
/**
 * validate-public-bundle.mjs — standalone validation for GroundX Agent Harness.
 *
 * This script is copied into the generated public repository. It must not depend on
 * private groundx-studio-harness source files.
 *
 * Usage:
 *   node scripts/validate-public-bundle.mjs
 *   node scripts/validate-public-bundle.mjs --allow-missing-provenance
 */

import { existsSync, readFileSync, readdirSync } from "node:fs";
import { dirname, extname, join, relative, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const HERE = dirname(fileURLToPath(import.meta.url));
const ROOT = resolve(HERE, "..");
const EXPECTED_NAME = "groundx-agent-harness";
const args = new Set(process.argv.slice(2));
const ALLOW_MISSING_PROVENANCE = args.has("--allow-missing-provenance");
const VALID_ARGS = new Set(["--allow-missing-provenance"]);

const FORBIDDEN_TEXT = [
  "harness-publish",
  "harness-web-ui",
  "harness-slides",
  "groundx-partner-api",
  "servers/groundx-studio",
  "groundx-studio/server",
  "WORKSPACE_API_KEY",
  "PARTNER_API_KEY",
  "git_session",
  "project_create",
  "customer-facing plugin bundle",
  "public-safe guidance",
  "intentionally excludes",
  "managed-project lifecycle",
  "Partner-only APIs",
  "web UI scaffold production",
  "slide production",
  "Use this public repository target",
];
const SECRET_PATTERNS = [
  { label: "GitHub access token URL", pattern: /x-access-token:[^@\s]{8,}@/ },
  { label: "GitHub app token", pattern: /ghs_[A-Za-z0-9_]{20,}/ },
  { label: "GitHub personal access token", pattern: /ghp_[A-Za-z0-9_]{20,}/ },
  { label: "GitHub fine-grained personal access token", pattern: /github_pat_[A-Za-z0-9_]{20,}/ },
];
const TEXT_SCAN_SKIP = new Set([
  "scripts/validate-public-bundle.mjs",
]);
const TEXT_EXTENSIONS = new Set([
  "",
  ".json",
  ".md",
  ".mjs",
  ".js",
  ".ts",
  ".tsx",
  ".yaml",
  ".yml",
  ".txt",
]);

const violations = [];

for (const arg of args) {
  if (!VALID_ARGS.has(arg)) {
    violations.push({ file: ".", message: `unknown argument ${arg}` });
  }
}

function rel(file) {
  return relative(ROOT, file).split("\\").join("/");
}

function flag(file, message) {
  violations.push({ file: rel(file), message });
}

function readJson(path) {
  try {
    return JSON.parse(readFileSync(path, "utf8"));
  } catch (error) {
    flag(path, `invalid JSON: ${error instanceof Error ? error.message : String(error)}`);
    return null;
  }
}

function requireFile(path, message = "required file is missing") {
  if (!existsSync(path)) flag(path, message);
}

function walkFiles(root = ROOT) {
  const files = [];
  function walk(dir) {
    for (const entry of readdirSync(dir, { withFileTypes: true })) {
      if (entry.name === ".git" || entry.name === "node_modules") continue;
      const absolute = join(dir, entry.name);
      if (entry.isDirectory()) {
        walk(absolute);
      } else if (entry.isFile()) {
        files.push(rel(absolute));
      }
    }
  }
  walk(root);
  return files.sort((a, b) => a.localeCompare(b));
}

function ensureNoPath(prefixOrFile, message) {
  if (existsSync(join(ROOT, prefixOrFile))) {
    flag(join(ROOT, prefixOrFile), message);
  }
}

for (const required of [
  ".agents/plugins/marketplace.json",
  ".claude-plugin/marketplace.json",
  ".codex-plugin/plugin.json",
  ".github/workflows/validate.yml",
  ".gitignore",
  "LICENSE",
  "README.md",
  "scripts/doctor.mjs",
  "scripts/validate-public-bundle.mjs",
  "skills/ROUTING.md",
]) {
  requireFile(join(ROOT, required));
}

if (!ALLOW_MISSING_PROVENANCE) {
  requireFile(join(ROOT, ".groundx-generated.json"), "public release provenance is missing");
}

ensureNoPath(".mcp.json", "public bundle must not include local MCP config");
ensureNoPath(".app.json", "public bundle must not include placeholder Codex app bindings; use custom MCP setup docs");
ensureNoPath("servers/groundx-studio", "public bundle must not include local groundx-studio MCP server");
ensureNoPath("openspec/work", "public bundle must not include OpenSpec work products");
ensureNoPath("openspec/private", "public bundle must not include private OpenSpec content");
ensureNoPath("openspec/runs", "public bundle must not include OpenSpec run outputs");
ensureNoPath("openspec/artifacts", "public bundle must not include OpenSpec artifacts");

const codex = readJson(join(ROOT, ".codex-plugin/plugin.json"));
if (codex) {
  if (codex.name !== EXPECTED_NAME) flag(join(ROOT, ".codex-plugin/plugin.json"), `expected name ${EXPECTED_NAME}`);
  if (codex.skills !== "./skills/") flag(join(ROOT, ".codex-plugin/plugin.json"), 'skills must be "./skills/"');
  if (codex.mcpServers !== undefined) flag(join(ROOT, ".codex-plugin/plugin.json"), "public Codex manifest must not expose mcpServers");
  if (codex.apps !== undefined) flag(join(ROOT, ".codex-plugin/plugin.json"), "public Codex manifest must not expose placeholder app bindings");
}

const claude = readJson(join(ROOT, ".claude-plugin/marketplace.json"));
if (claude) {
  if (claude.name !== EXPECTED_NAME) flag(join(ROOT, ".claude-plugin/marketplace.json"), `expected name ${EXPECTED_NAME}`);
  const bundle = Array.isArray(claude.plugins) ? claude.plugins[0] : null;
  if (!bundle) {
    flag(join(ROOT, ".claude-plugin/marketplace.json"), "plugins[0] is required");
  } else {
    if (bundle.name !== EXPECTED_NAME) flag(join(ROOT, ".claude-plugin/marketplace.json"), `expected plugin name ${EXPECTED_NAME}`);
    if (bundle.mcpServers !== undefined) flag(join(ROOT, ".claude-plugin/marketplace.json"), "public Claude manifest must not expose mcpServers");
    for (const skillPath of bundle.skills ?? []) {
      const normalized = String(skillPath).replace(/^\.\//, "");
      requireFile(join(ROOT, normalized, "SKILL.md"), `Claude-listed skill ${skillPath} is missing SKILL.md`);
      requireFile(join(ROOT, normalized, "references/README.md"), `Claude-listed skill ${skillPath} is missing references/README.md`);
    }
  }
}

const marketplace = readJson(join(ROOT, ".agents/plugins/marketplace.json"));
if (marketplace) {
  if (marketplace.name !== EXPECTED_NAME) flag(join(ROOT, ".agents/plugins/marketplace.json"), `expected marketplace name ${EXPECTED_NAME}`);
  const plugin = Array.isArray(marketplace.plugins) ? marketplace.plugins[0] : null;
  if (!plugin || plugin.name !== EXPECTED_NAME) {
    flag(join(ROOT, ".agents/plugins/marketplace.json"), `expected plugin entry ${EXPECTED_NAME}`);
  }
}

const readmePath = join(ROOT, "README.md");
if (existsSync(readmePath)) {
  const readme = readFileSync(readmePath, "utf8");
  for (const expected of [
    "/reload-plugins",
    "Claude Code Desktop (local or SSH sessions)",
    "Personal plugins",
    "GroundX-Studio/groundx-agent-harness",
  ]) {
    if (!readme.includes(expected)) {
      flag(readmePath, `README install guide must include ${expected}`);
    }
  }
}

const provenance = existsSync(join(ROOT, ".groundx-generated.json"))
  ? readJson(join(ROOT, ".groundx-generated.json"))
  : null;
if (provenance) {
  for (const field of ["sourceRepository", "sourceCommit", "generatedBundlePath", "generator", "bundlePolicy", "generatedAt"]) {
    if (typeof provenance[field] !== "string" || provenance[field].length === 0) {
      flag(join(ROOT, ".groundx-generated.json"), `${field} must be present`);
    }
  }
  if (typeof provenance.sourceRepository === "string") {
    try {
      const sourceUrl = new URL(provenance.sourceRepository);
      if (sourceUrl.username || sourceUrl.password) {
        flag(join(ROOT, ".groundx-generated.json"), "sourceRepository must not include credentials");
      }
    } catch {
      // Non-URL repository identifiers are allowed, but token-shaped strings are scanned below.
    }
  }
}

for (const file of walkFiles()) {
  if (file.includes("/evals/") || file.startsWith("evals/")) {
    flag(join(ROOT, file), "public bundle must not include internal eval files");
  }
  if (TEXT_SCAN_SKIP.has(file)) continue;
  if (!TEXT_EXTENSIONS.has(extname(file))) continue;
  const content = readFileSync(join(ROOT, file), "utf8");
  for (const forbidden of FORBIDDEN_TEXT) {
    if (content.includes(forbidden)) {
      flag(join(ROOT, file), `public bundle references excluded internal surface "${forbidden}"`);
    }
  }
  for (const { label, pattern } of SECRET_PATTERNS) {
    if (pattern.test(content)) {
      flag(join(ROOT, file), `public bundle contains credential-shaped value: ${label}`);
    }
  }
}

if (violations.length === 0) {
  console.log("✓ GroundX Agent Harness public bundle is valid");
  process.exit(0);
}

for (const violation of violations) {
  console.error(`✗ ${violation.file}: ${violation.message}`);
}
console.error(`\n${violations.length} public bundle violation${violations.length === 1 ? "" : "s"} found.`);
process.exit(1);
