# Customer and API Keys

This reference covers account management: retrieving account information, managing API
keys, and checking service health.

## 1. customer_get / GET /v1/customer

Retrieve account information associated with the current API key.

**MCP discovery:** List operations and describe `Customer_get` first, then:
```json
{
  "operationId": "Customer_get",
  "args": {}
}
```
Tool: `call_operation`

**REST:**
```http
GET /v1/customer
X-API-Key: YOUR_API_KEY
```

**Response:**
```json
{
  "customer": {
    "email": "user@example.com",
    "first": "Jane",
    "last": "Smith",
    "subscription": {
      "meters": {
        "fileTokens": { "value": 12500, "max": 100000 },
        "searches":   { "value": 42,    "max": 1000   }
      }
    }
  }
}
```

`subscription` contains the current plan details and usage limits. The `meters`
object tracks consumption against account caps:

| Field | Description |
|---|---|
| `subscription.meters.fileTokens.value` | File tokens consumed in the current period |
| `subscription.meters.fileTokens.max` | File token cap for the current plan |
| `subscription.meters.searches.value` | Searches performed in the current period |
| `subscription.meters.searches.max` | Search cap for the current plan |

Use `fileTokens.value / fileTokens.max` and `searches.value / searches.max` to
render usage meters in account dashboards or to gate uploads when the account is
near its limit.

**Python SDK note:** The SDK auto-converts camelCase JSON fields to snake_case
attributes. Access meters as `customer.subscription.meters.file_tokens.value`,
`customer.subscription.meters.file_tokens.max`,
`customer.subscription.meters.searches.value`, and
`customer.subscription.meters.searches.max`.

## 2. apikey_list / GET /v1/apikey

List all API keys in the account.

**MCP discovery:** List operations and describe `APIKey_list` first, then:
```json
{
  "operationId": "APIKey_list",
  "args": {}
}
```
Tool: `call_operation`

**REST:**
```http
GET /v1/apikey
X-API-Key: YOUR_API_KEY
```

**Response:** `{ "apiKeys": [...] }` — each entry includes the key value, name, and
creation timestamp.

**Scope note:** GroundX customer-tier keys are not scoped per project, environment, or
purpose. Any key with access to `apikey_list` returns every key on the account, including
admin keys, in plaintext. Treat all customer-tier keys as account-level credentials, and
do not hand a "per-project" or "per-environment" key to a third party expecting it to be
limited in blast radius. The Partner API has its own separate key tier (see the
Partner API guidance, when available) for cases where per-customer isolation is required.

## 3. apikey_create / POST /v1/apikey

Create a new API key with a given display name. Use this during key rotation to generate
a replacement before deleting the old key.

**MCP:** Customer API-key creation is intentionally excluded, regardless of scope. Use the dashboard or authorized REST flow.

**REST:**
```http
POST /v1/apikey
X-API-Key: YOUR_API_KEY
Content-Type: application/json

{ "name": "production-key-2" }
```

The same `{ "name": "..." }` body shape works against both customer-tier
(`X-API-Key` only) and partner-tier (`X-API-Key` + `X-Customer-Key`) callers.
Partner-tier header construction is outside this customer-tier reference.

**Response:** `{ "apiKeys": [...] }` — the new key is included in the list.

**Key rotation pattern:** create the new key → update the consumer to use it → delete
the old key via §5. This order ensures no service interruption.

**Errors:** 400 — invalid body parameter.

## 4. apikey_update / PUT /v1/apikey/{apiKey}

Rename an existing API key. The `apiKey` path parameter is the key value (UUID).

**MCP discovery:** List operations and describe `APIKey_update` first, then:
```json
{
  "operationId": "APIKey_update",
  "args": {
    "apiKey": "key-uuid",
    "name": "production-key-renamed"
  }
}
```
Tool: `call_operation`

**REST:**
```http
PUT /v1/apikey/key-uuid
X-API-Key: YOUR_API_KEY
Content-Type: application/json

{ "name": "production-key-renamed" }
```

**Input parameters:**

| Parameter | Required | Description |
|---|---|---|
| `apiKey` | yes | Key value (UUID) of the API key to rename (path) |
| `name` | yes | New display name for the API key (body) |

**Response:** Updated list of API keys.

## 5. apikey_delete / DELETE /v1/apikey/{apiKey}

Delete the API key identified by `apiKey`. Revocation propagates through the auth cache;
allow up to several minutes before assuming the deleted key will reliably fail with 401.
Ensure all consumers have switched to a different key before deleting. For incident
response (suspected key compromise), rotate to a new key, switch consumers over, and
treat the old key as compromised regardless of when delete was called.

**MCP discovery:** List operations and describe `APIKey_delete` first, then:
```json
{
  "operationId": "APIKey_delete",
  "args": {
    "apiKey": "key-uuid"
  }
}
```
Tool: `call_operation`

**REST:**
```http
DELETE /v1/apikey/key-uuid
X-API-Key: YOUR_API_KEY
```

**Response:** `{ "message": "OK" }`

## 6. health_list / GET /v1/health

Get the current health status of all GroundX services. Statuses update every 5 minutes.
Use this for monitoring and pre-flight checks before submitting large ingestion workloads.
In the GroundX cloud service, this is service-level availability monitoring: it tells
callers whether the service is available / unavailable at the service level, not a
root-cause diagnostic report.

**MCP discovery:** List operations and describe `Health_list` first, then:
```json
{
  "operationId": "Health_list",
  "args": {}
}
```
Tool: `call_operation`

**REST:**
```http
GET /v1/health
X-API-Key: YOUR_API_KEY
```

**Response:**
```json
{
  "health": {
    "services": [
      {
        "service": "search",
        "status": "healthy",
        "lastUpdate": "2026-01-15T10:00:00.000Z"
      },
      {
        "service": "ingest",
        "status": "healthy",
        "lastUpdate": "2026-01-15T10:00:00.000Z"
      }
    ]
  }
}
```

Each entry in `health.services` contains:

| Field | Description |
|---|---|
| `service` | Service name (e.g. `"search"`, `"ingest"`) |
| `status` | `"healthy"` \| `"degraded"` \| `"down"` \| `"unknown"` |
| `lastUpdate` | RFC 3339 timestamp of the last status check |

**Pre-flight check pattern** — verify all services are healthy before a critical
ingest run:

```python
def groundx_is_healthy(client) -> bool:
    try:
        response = client.health.list()
        return all(
            s.status == "healthy"
            for s in response.health.services
        )
    except Exception:
        return False
```

For on-prem deployments, use the deployment's Prometheus and Grafana metrics for deeper
application-health diagnostics. The customer-tier health endpoint remains the API-facing
status surface; Prometheus/Grafana are the operator-facing detail surface.

## 7. health_get / GET /v1/health/{service}

Get the current health status of a specific service. The `service` path parameter
accepts a service name (e.g. `search`, `ingest`).

**MCP discovery:** List operations and describe `Health_get` first, then:
```json
{
  "operationId": "Health_get",
  "args": {
    "service": "search"
  }
}
```
Tool: `call_operation`

**REST:**
```http
GET /v1/health/search
X-API-Key: YOUR_API_KEY
```

**Response:** Same shape as §6 — `{ "health": { "services": [...] } }` — with a
single entry for the requested service.

**Errors:** 400 — invalid service name.

## Account file-access policy

Customer readback includes confirmed `fileAccess`, `fileAccessRevision` and
`effectiveFileAccess` where supported. `PUT /v1/customer` (`Customer_update`) changes only
the file-access policy with required `fileAccess` and `fileAccessRevision`; explicit null
clears the account override. MCP discovery requires `groundx:write`; customer readback
requires `groundx:read`. Read `13-file-access.md` before making a change.

## Aggregate usage

`GET /v1/customer/usage` (`Customer_getUsage`) returns aggregate usage for the current
account. Required query fields are `metric` (`searches` or `fileTokens`), `startTime`
(inclusive) and `endTime` (exclusive). RFC3339 timestamps must align to minute boundaries;
the server normalizes to UTC, rejects future ends and windows longer than 366 days.
The account subscription/meter is resolved server-side, not passed by the caller.

After list/describe, MCP (`groundx:read`) uses:

```json
{ "operationId": "Customer_getUsage", "args": { "metric": "searches", "startTime": "2026-07-15T00:00:00Z", "endTime": "2026-07-29T00:00:00Z" } }
```

Tool: `call_operation`. The response is
`{ customer: { usage: { metric, meterId, value, startTime, endTime, usageAsOf } } }`;
`meterId` is optional. `usageAsOf` reflects the latest available summary, not a claim of
instant billing completeness. 400 means invalid metric/window; 404 means no current
subscription or meter. Do not invent a generated SDK helper without checking its release.

Existing key list/update/delete operations require `groundx:admin` through discovery.
Credential creation is deliberately excluded from customer MCP, including advanced
discovery; use authorized REST/dashboard or separate Partner provisioning. Treat key
list output as credentials and never log or copy the raw values into artifacts.
