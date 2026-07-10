# Coverage Checklist

Track documentation status for every MCP tool and REST endpoint.
Update the ☐→✓ column as each reference doc is written.
Each phase starts by reading this file and ends by updating it.

## 01-auth.md

_No individual operations — cross-cutting content._

| Done | Notes |
|---|---|
| ✓ | Written |

## 02-documents.md

| Done | MCP Tool | REST |
|---|---|---|
| ✓ | `document_cancelprocess` | `DELETE /v1/ingest/{processId}` |
| ✓ | `document_crawlwebsite` | `POST /v1/ingest/documents/website` |
| ✓ | `document_delete1` | `DELETE /v1/ingest/document/{documentId}` |
| ✓ | `document_get` | `GET /v1/ingest/document/{documentId}` |
| ✓ | `document_getextract` | `GET /v1/ingest/document/extract/{documentId}` |
| ✓ | `document_getprocesses` | `GET /v1/ingest` |
| ✓ | `document_getprocessingstatusbyid` | `GET /v1/ingest/{processId}` |
| ✓ | `document_getxray` | `GET /v1/ingest/document/xray/{documentId}` |
| ✓ | `document_ingestlocal` | `POST /v1/ingest/documents/local` |
| ✓ | `document_ingestremote` | `POST /v1/ingest/documents/remote` |
| ✓ | `document_list` | `GET /v1/ingest/documents` |
| ✓ | `document_lookup` | `GET /v1/ingest/documents/{id}` |
| ✓ | `document_update` | `PUT /v1/ingest/documents` |
| ✓ | `documents_copy` | `POST /v1/ingest/copy` |
| ✓ | `documents_delete` | `DELETE /v1/ingest/documents` |

## 03-search.md

| Done | MCP Tool | REST |
|---|---|---|
| ✓ | `search_content` | `POST /v1/search/{id}` |
| ✓ | `search_documents` | `POST /v1/search/documents` |

## 04-buckets.md

| Done | MCP Tool | REST |
|---|---|---|
| ✓ | `bucket_create` | `POST /v1/bucket` |
| ✓ | `bucket_delete` | `DELETE /v1/bucket/{bucketId}` |
| ✓ | `bucket_get` | `GET /v1/bucket/{bucketId}` |
| ✓ | `bucket_list` | `GET /v1/bucket` |
| ✓ | `bucket_update` | `PUT /v1/bucket/{bucketId}` |

## 05-groups.md

| Done | MCP Tool | REST |
|---|---|---|
| ✓ | `group_addbucket` | `POST /v1/group/{groupId}/bucket/{bucketId}` |
| ✓ | `group_create` | `POST /v1/group` |
| ✓ | `group_delete` | `DELETE /v1/group/{groupId}` |
| ✓ | `group_get` | `GET /v1/group/{groupId}` |
| ✓ | `group_list` | `GET /v1/group` |
| ✓ | `group_removebucket` | `DELETE /v1/group/{groupId}/bucket/{bucketId}` |
| ✓ | `group_update` | `PUT /v1/group/{groupId}` |

## 06-workflows.md

| Done | MCP Tool | REST |
|---|---|---|
| ✓ | `workflow_add_to_account` | `POST /v1/workflow/relationship` |
| ✓ | `workflow_add_to_id` | `POST /v1/workflow/relationship/{id}` |
| ✓ | `workflow_create` | `POST /v1/workflow` |
| ✓ | `workflow_delete` | `DELETE /v1/workflow/{id}` |
| ✓ | `workflow_get` | `GET /v1/workflow/{id}` |
| ✓ | `workflow_get_account` | `GET /v1/workflow/relationship` |
| ✓ | `workflow_list` | `GET /v1/workflow` |
| ✓ | `workflow_remove_from_account` | `DELETE /v1/workflow/relationship` |
| ✓ | `workflow_remove_from_id` | `DELETE /v1/workflow/relationship/{id}` |
| ✓ | `workflow_update` | `PUT /v1/workflow/{id}` |
| ✓ | `workflow_validate` | `POST /v1/workflow/validate` |

## 07-customer-and-keys.md

| Done | MCP Tool | REST |
|---|---|---|
| ✓ | `apikey_create` | `POST /v1/apikey` |
| ✓ | `apikey_delete` | `DELETE /v1/apikey/{apiKey}` |
| ✓ | `apikey_list` | `GET /v1/apikey` |
| ✓ | `apikey_update` | `PUT /v1/apikey/{apiKey}` |
| ✓ | `customer_get` | `GET /v1/customer` |
| ✓ | `health_list` | `GET /v1/health` |
| ✓ | `health_get` | `GET /v1/health/{service}` |

## 08-errors-and-limits.md

_No individual operations — cross-cutting content._

| Done | Notes |
|---|---|
| ✓ | Written |
