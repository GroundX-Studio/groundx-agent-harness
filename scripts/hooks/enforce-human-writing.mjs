#!/usr/bin/env node

let input = "";
for await (const chunk of process.stdin) input += chunk;

let event;
try {
  event = JSON.parse(input);
} catch {
  process.exit(0);
}

if (event?.hook_event_name !== "Stop") process.exit(0);

const response = typeof event.last_assistant_message === "string"
  ? event.last_assistant_message
  : "";

const reasons = [];

if (/[—–→]/u.test(response)) {
  reasons.push("Remove every em dash, en dash, and arrow glyph. Use commas, periods, colons, or parentheses.");
}

if (/(?:\blet me know if\b|\bask if you want\b|\bwant me to\b|\bwant to (?:bring|test|share|see|walk)\b|\bwould you like(?: me)? to\b|\bhappy to (?:help|walk|share|draft|create|discuss|talk|show)\b|\bworth a (?:call|meeting)\b|\bwhich do you want(?: me)? to do\b|\bnext (?:step|action):)/iu.test(response)) {
  reasons.push("Remove the unasked follow-up offer. End when the requested answer is complete.");
}

if (reasons.length > 0) {
  process.stdout.write(JSON.stringify({
    decision: "block",
    reason: `Rewrite the final response. ${reasons.join(" ")} Return only the corrected answer with no explanation.`,
  }));
}
