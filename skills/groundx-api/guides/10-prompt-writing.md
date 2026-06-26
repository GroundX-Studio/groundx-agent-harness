# Workflow Prompt Writing

Use this when you write or review GroundX workflow prompts, including full
`prompt` overrides, `additionalContext`, search-query rewrites, document
processing prompts, and retrieval metadata prompts.

## 1. Good Prompt Standard

A good prompt is short, direct, and easy to test. It tells the model exactly:

1. **What to do.**
2. **What input to trust.**
3. **What output to return.**
4. **What to do when evidence is missing.**
5. **What not to add.**

Use plain English. Remove any sentence that does not change the model's behavior.

## 2. Write The Prompt In This Order

1. Start with the output: "Return JSON with these keys", "Rewrite the search
   query", or "Summarize this chunk for retrieval".
2. Name the current input: document, page, section, chunk, field list, or user
   query.
3. Give a short process in numbered steps.
4. Define the exact output shape.
5. Add one small example in the same shape as the desired answer.
6. End with hard rules: no unsupported values, no extra keys, no prose outside
   the requested output.

## 3. Workflow Prompt Parts

Use the smallest prompt surface that fits the change.

| Part | Use it for |
| --- | --- |
| `task` | Stable rules: goal, evidence rules, output shape, and what not to do. |
| `request` | The per-item work: current chunk, page, field list, query, or document text. |
| `additionalContext` | A small add-on when the default prompt is right but needs customer, domain, or workflow-specific terms. |
| Full `prompt` | A complete replacement. Use this only when the default prompt is not close enough. |

additionalContext is not a second full prompt. Keep it small. Do not repeat the default prompt. Put only the terms or rules that are specific to this workflow.

## 4. Retrieval And Search Prompts

For search-query or retrieval prompts:

1. Keep exact source or user words first: company, product, document, date, metric, visual title,
   value, and unit words first.
2. Add aliases only when the query includes that term or clearly asks for the same
   specific thing.
3. Add the date and name forms in §5 when they help matching.
4. Do not expand broad words like "performance", "value", "business", "trend",
   or "change" into long synonym lists.
5. Return only the rewritten query text when the prompt is a query rewriter.

Example:

```text
User query: Acme Q3 2026 outage report search latency
Good rewrite: Acme Q3 2026 2026 Q3 3Q26 outage report search latency
Bad rewrite: Acme performance value business growth platform advantage search scalability
```

## 5. Dates And Names

Use these forms when a workflow asks for date or name expansion. Do not add every
form if the prompt has a strict length limit; keep exact user words first.

**Calendar date**
- June 20, 2026 -> June 20 2026, Jun 20 2026, 2026-06-20, June 2026, 2026.

**Calendar year**
- 2026 -> 2026, calendar 2026.

**Calendar quarter**
- Q3 2026 -> Q3 2026, 2026 Q3, 3Q26, 2026.

**Year range**
- 2024-2026 -> 2024, 2025, 2026.

**Acronyms and product names**
- Exact name first, then common acronym or common expanded name when high-confidence:
  Data Loss Prevention -> Data Loss Prevention, DLP; Kubernetes -> Kubernetes, K8s.

Do not invent legal names, acronyms, product families, or dates. Add them only when
they are visible, provided by metadata, or high-confidence common knowledge.

## 6. Document Processing Prompts

For document, section, chunk, table, or figure prompts:

1. Keep names, dates, titles, metrics, values, and units exactly as they appear.
2. Add aliases for important names, dates, and common domain abbreviations when
   the alias is obvious.
3. Keep page or chunk details local to that page or chunk.
4. Do not make a footnote, page footer, or neighboring page carry the main chart's
   meaning unless that content is visible there.
5. Do not invent page numbers, values, conclusions, or document titles.

Example:

```text
Good: Summarize this chart with the company, chart title, period, metric, units,
visible categories, and visible values.
Bad: Summarize the page and include likely financial themes from the whole report.
```

## 7. Extraction Prompts

For schema-first extraction prompt writing, including `prompt.yaml`, field
prompts, group prompts, and custom extraction wrapper prompts, use
`../../groundx-extraction-workflows/references/16_prompt_writing.md` after loading
the `groundx-extraction-workflows` skill.

This guide covers general workflow prompt wording. The extraction skill owns
`prompt.yaml`, field prompts, group prompts, and extraction wrapper prompts.

## 8. Anti-Patterns

- Long introductions about the workflow, agent, model, or implementation.
- Labels that sound precise but do not say what to do.
- Broad synonym bags.
- Examples copied from known test answers.
- Rules that solve one customer page instead of the document family.
- Repeating the same instruction three times with different words.
- Asking for evidence and then allowing unsupported guesses.

## 9. Before Shipping

Check the prompt with this list:

- [ ] A busy human can tell what output is expected.
- [ ] The output shape is explicit.
- [ ] The prompt uses source words before aliases.
- [ ] Domain terms are added only when the input supports them.
- [ ] Missing evidence has a clear result, usually `null` or omission.
- [ ] There is one small example, not an answer key.
- [ ] Every sentence changes behavior.
