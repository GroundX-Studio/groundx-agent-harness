# RAG Integration Patterns

How to wire GroundX into an LLM-powered system: three integration patterns
(traditional, conversational, agentic), system prompt structure, and MCP-specific
agent workflows.

## 1. Pattern overview

| Pattern | When to use |
|---|---|
| Traditional RAG | Single-turn Q&A — user asks one question, system answers |
| Conversational RAG | Multi-turn chat — conversation history must be maintained |
| Agentic RAG | Complex or multi-part queries — GroundX is one tool among several in an agent loop |

Start with traditional RAG. Move to conversational if you need session memory, or
agentic if single searches are insufficient for the query type.

**GroundX is LLM-agnostic.** It handles ingestion, storage, and semantic search;
it has no opinion about which language model you use. The integration point is
`search.text` — a pre-assembled context string you insert into your prompt. Any
LLM that accepts a prompt string works: OpenAI, Anthropic, Mistral, a locally-run
model, or anything else. Code examples in this guide use generic pseudocode; adapt
the LLM call to whichever client library your stack uses.

## 2. Traditional RAG

The standard pattern for single-turn question answering.

```
search_content(bucketId, userQuery)
   → result.search.text

LLM(systemPrompt + search.text + userQuery)
   → answer
```

**MCP:**
```json
{ "id": 1234, "query": "What is the cancellation policy?" }
```
Tool: `search_content` → `search.text`

Pass `search.text` to the LLM as context in the system prompt, separated from
instructions by a clear delimiter:

```
{your instructions}
===
{search.text}
===
```

Then send the user's query as the user message. Most modern LLMs produce accurate,
grounded responses from this structure without additional formatting.

**Why `search.text` over `search.results`:** GroundX has already applied semantic
search, re-ranking, and chunk rewriting optimized for LLM consumption. `search.text`
is the suggested context created for downstream answer generation. Build context from
`search.results` only when you intentionally want to control context assembly yourself.
The chunk metadata in `search.results` remains the right source for UI evidence such as
page images, document URLs, page numbers, bounding boxes, scores, and citation cards.
See §1.2 in 03-search.md for the response shape.

## 3. System prompt structure

A system prompt for GroundX-backed Q&A should tell the LLM three things: what role
it is playing, how to interpret the retrieved context, and what to do when context
is insufficient.

Minimal structure:

```
You are a knowledgeable assistant. Answer the user's question using only the
information provided below.

If the answer cannot be found in the provided information, say so clearly — do
not fabricate an answer.

===
{search.text}
===
```

For applications where document provenance matters, instruct the LLM to cite
`sourceUrl` or `fileName` values from `search.results[n]` when available —
these are top-level chunk fields, not inside `searchData`.

## 4. Conversational RAG

For multi-turn chat, the conversation history must be maintained across turns.
The question is how much GroundX context to carry.

**Recommended approach — retrieval per turn, no history accumulation:**

On each user turn, issue a fresh `search_content` call with the latest user message
as the query. Inject only the new `search.text` into the current prompt. Do not
carry forward previous GroundX retrievals.

```
Turn 1:
  search(query1) → text1
  messages: [system, user: text1 + query1] → answer1

Turn 2:
  search(query2) → text2
  messages: [system, user: query1, assistant: answer1, user: text2 + query2] → answer2
```

The conversation history preserves the thread of dialogue. Fresh retrieval ensures
each turn gets the most relevant context for its specific question. This is more
economical than accumulating all prior retrievals and works well for the large
majority of conversational applications.

**When to accumulate retrievals:** If users ask follow-up questions that depend on
specific retrieved passages ("you mentioned X earlier — can you expand?"), carry the
previous `search.text` in the system prompt rather than the user messages. Be aware
that this grows the context window on every turn and increases token cost.

## 5. Agentic RAG

In an agentic system, GroundX is exposed as a tool alongside other tools. The agent
(an LLM) decides when to call it based on the query.

**Tool definition pattern:**

The tool needs a query input and returns a text output:

```
function groundx_search(query: string) -> string:
  result = search_content(bucketId, query)
  return result.search.text
```

**Tool description for the agent:**

How you describe the tool shapes when the agent uses it. A description that works
well in practice:

```
groundx_search(query): Searches the knowledge base for information relevant to the
query. Returns a text passage containing relevant content from stored documents.
Use this tool when the user asks a question that may be answered by the stored
documents.
```

Keep the description specific about what is stored. If the bucket contains product
manuals, say that. Vague descriptions like "searches documents" produce inconsistent
tool-calling behavior.

**Agentic RAG is best for:**
- Exhaustive summarization — where the agent may need to issue multiple queries
  to cover all relevant sections
- Multi-part questions — where each sub-question needs its own targeted retrieval
- Tool-switching — where the agent must decide between GroundX retrieval and other
  tools (code execution, web search, calculation, etc.)

**Agentic RAG is not needed for most applications.** Start with traditional RAG and
only introduce the agentic layer when single-query retrieval demonstrably fails for
your use case.

## 6. MCP agent patterns

When connected via MCP, an agent can do more than just search — it can discover
available content, ingest new documents, and manage the knowledge base as part of a
workflow. The following patterns compose the basic MCP tools into useful sequences.

### 6.1 Discover-then-search

When the bucket or group ID is not known in advance, the agent discovers it first:

```
bucket_list  {}
  → buckets: [{ bucketId: 31, name: "product-docs", ... }, ...]

→ agent selects relevant bucket

search_content  { id: 31, query: "data retention policy", verbosity: 2 }
  → search.text, search.results
```

Use `bucket_list` (or `group_list`) at the start of a session to orient the agent
to available content. Once IDs are known, cache them for the session rather than
re-listing on every search.

### 6.2 Ingest-then-query

When the agent needs to add new content before answering:

```
bucket_list  {}  (or bucket_create if needed)
  → bucketId

document_ingestremote  { documents: [{ bucketId, sourceUrl, fileName, fileType }] }
  → processId

document_getprocessingstatusbyid  { processId }
  → status: "queued" … poll every 5s …

document_getprocessingstatusbyid  { processId }
  → status: "complete"

search_content  { id: bucketId, query: "..." }
  → search.text
```

Do not search immediately after ingest. Always wait for `status: complete` before
querying the ingested content. See §2 in 08-errors-and-limits.md for polling
guidance.

### 6.3 Search by specific documents

When the agent has already identified the relevant documents (e.g., from a prior
`document_list` or `document_lookup` call):

```
search_documents  { documentIds: ["doc-id-1", "doc-id-2"], query: "renewal terms" }
  → search.text
```

Use `search_documents` instead of `search_content` when the document scope is
known and the agent should not search the entire bucket.

## 7. MCP connection configuration

```json
{
  "url": "https://api.groundx.ai/api/v1/mcp"
}
```

Use the first-party GroundX OAuth flow for interactive MCP clients. The MCP client
discovers the authorization metadata from the GroundX deployment, opens the hosted
authorize page, and receives short-lived bearer tokens after the user enters a GroundX
API key there. Non-interactive API agents may authenticate MCP transport with
`X-API-Key`. Do not put `X-API-Key` or a raw API key in MCP tool arguments, generated
artifacts, browser code, logs, or transcripts. Tool discovery is automatic after
connection; the client receives the GroundX tool schemas. MCP is optional and prod-only;
when MCP is missing or the target is dev, use the SDK/REST path in `01-auth.md`.

## 8. Error handling

Wrap every search call in a try/except (Python) or try/catch (TypeScript). If the
search fails, use an empty string as the context — do not skip the LLM call.

```python
try:
    results = client.search.content(id=bucket_id, query=user_query, n=5)
    context = results.search.text
except Exception:
    context = ""

# Always call the LLM even when context is empty.
# An empty context string still lets the LLM respond with "NOT FOUND"
# rather than producing a silent failure.
```

**Why always call the LLM:** passing an empty context causes the LLM to answer
"I could not find relevant information" (or similar), which is a valid,
user-facing response. Skipping the call entirely produces a silent error that
is harder to diagnose and breaks the expected response contract.

For transient failures, apply the same exponential backoff strategy as for
HTTP 429 responses — see §4.3 in 08-errors-and-limits.md.
