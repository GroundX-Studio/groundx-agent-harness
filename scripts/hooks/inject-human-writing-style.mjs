#!/usr/bin/env node

import { readFileSync } from "node:fs";

let input = "";
for await (const chunk of process.stdin) input += chunk;

let event;
try {
  event = JSON.parse(input);
} catch {
  process.exit(0);
}

if (event?.hook_event_name !== "SessionStart") process.exit(0);

const stylePath = process.argv[2];
if (!stylePath) process.exit(0);

let style;
try {
  style = readFileSync(stylePath, "utf8").trim();
} catch {
  process.exit(0);
}

process.stdout.write(JSON.stringify({
  hookSpecificOutput: {
    hookEventName: "SessionStart",
    additionalContext: `<GROUNDX_RESPONSE_STYLE>\n${style}\n</GROUNDX_RESPONSE_STYLE>`,
  },
}));
