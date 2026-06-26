# Public Extraction Docs

Use this reference when writing customer-facing docs about GroundX extraction.
Public docs should teach the workflow a customer performs, not the harness
implementation or the compiler internals.

## Plain-Language Flow

Teach the path in this order:

1. Show the JSON the application should receive.
2. Create one YAML file that names the top-level JSON objects and values.
3. Create or update the GroundX workflow directly from the YAML path with
   `client.create_extraction_workflow(...)` or
   `client.update_extraction_workflow(...)`.
4. To inspect, reuse, or copy settings, use
   `client.load_extraction_definition(...)` with `path=...` or
   `workflow_id=...`.
5. Assign the workflow where documents will be uploaded.
6. Upload documents with `client.ingest(...)` and `Document(...)`.
7. Poll until ingest completes.
8. Read extracted JSON with `client.documents.get_extract(...)`.
9. Improve the smallest YAML prompt that explains a missing or wrong value.

The public guide can mention that GroundX uses the YAML names in the returned
JSON. It does not need to describe how the SDK prepares workflow steps.

If custom workflow steps are public-facing in the guide, keep the explanation at
the SDK/workflow-settings level: `template`, `customSteps`, `outputRoutes`, and
`leafFields` are workflow settings that let engineers route custom extraction
outputs back to the JSON they want. Do not describe harness compiler internals,
local plugin mirrors, or private reassembly scripts.

## SDK Ingest Example

Public Python SDK docs should use the SDK-level ingest method:

```python
from groundx import Document, GroundX

client = GroundX(api_key="YOUR_API_KEY")

client.ingest(
    documents=[
        Document(
            bucket_id=1234,
            file_name="statement.pdf",
            file_type="pdf",
            file_path="https://example.com/statement.pdf",
            process_level="full",
        )
    ],
)
```

Do not teach `client.documents.ingest_remote(...)` or
`client.documents.ingest_local(...)` in public Python docs. Those are lower-level
surfaces; the public SDK path is `client.ingest(...)`.

## Keep Internal Details Out

Do not expose authoring or reassembly internals in public docs unless the user is
explicitly asking for SDK internals:

- `_defs`
- `_pseudo_groups`
- `slot:`
- JSON Pointer route maps
- reassembly metadata
- harness script names
- local compile/deploy scripts
- platform slot names
- manual `prepare_extraction_yaml(...)` calls

When those details matter, describe the visible outcome instead: the YAML names
become the JSON names the application reads.

Do not use `workflow-how-to.md` as public-docs copy. It is an internal workflow
reference. Use it to verify behavior, then rewrite the public doc around the
customer-visible flow and JSON result.

When borrowing API details from `groundx-api`, translate MCP and REST operation
names into SDK-level public examples. Public Python docs use `client.ingest(...)`
with `Document(...)`; operation names such as `document_ingestremote` belong in
API operation references, not public walkthroughs.

## Language

Use customer-readable words before implementation words:

- Prefer "JSON you want back" over "final data object" or "contract".
- Prefer "value" over "field" except when pointing at the YAML `fields:` key.
- Prefer "workflow settings" over "workflow JSON" in public walkthrough steps.
- Avoid "boundary" and "extraction definition".
- Prefer "top-level JSON object" over "section" when describing the result.

Do not add a generic `What To Avoid` section. If there is a real risk, turn it
into a direct instruction where the reader needs it.
