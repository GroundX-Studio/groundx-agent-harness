# Identity Model — On-Prem Authentication

This file states what authenticates requests against a self-hosted GroundX deployment and how an
operator gives access to more than one person, across all three selectable identity modes. For
the values.yaml fields that bootstrap the first key, see `license-and-admin.md`. For the full
`cognito.*` field reference, see `values-yaml.md` § 2.

## 1. What authenticates today — three identity modes

Every request is authenticated with a single header, `X-API-Key`, checked against the database, in
every mode. A deployment additionally selects one of three password/human-identity modes through
`cognito.mode` in `values.yaml`; the selection governs only whether — and how — a password-based
login path exists alongside the always-on API-key path.

**`apiKeyOnly`** — the default, active when the `cognito` block is omitted from values.yaml
entirely, or `mode` is set to `apiKeyOnly` explicitly. Identity is limited to the seeded admin API
key (`admin.apiKey`, see `license-and-admin.md`) plus durable, DB-backed customer/API-key rows the
admin creates. Every human-identity route — login, register, password reset/confirm, and every
Basic-Auth route — returns HTTP 501. No route on an `apiKeyOnly` install issues a mock or
`test-token`.

**`cognito`** — set `cognito.mode: cognito` plus `clientId`, `clientSecret`, `poolId`, and
`region` (all four required; missing any one is a startup-fatal error, not a silent fallback to
`apiKeyOnly` or a mock client). Wires a real Cognito client against the configured `poolId` and
`region`, and additionally requires AWS credentials reaching the pod — standard AWS environment
variables or an IRSA-bound service account — for the Cognito API calls to succeed. `cognito` calls
out to `cognito-idp.<region>.amazonaws.com`, so it is not a valid choice for an air-gapped cluster.

**`local`** — set `cognito.mode: local`; no other `cognito.*` key is required. Password login is
verified against a bcrypt hash stored in MySQL (`partner_users.password`); a successful login
returns the customer body with no `token` field at all (the field is omitted, not emptied).
Password reset under `local` is performed through the existing superaccess-gated
`customer/password/reset` route: the owning partner or an admin can reset that customer's
password, while another partner is denied. There is no self-service password-change route. A password
is first set when the admin creates the customer through `customer/register` (with a password) or
resets one through `customer/password/reset` — `admin.password` sets nothing, and a customer that
existed before the switch to `local` has no password until an admin resets it. The always-on
API-key path above continues to work unchanged alongside `local` password login, and under `local`
the MCP authorize page offers browser-based email/password sign-in plus an `Or use a GroundX API key`
field below the email and password fields, for customers who have no password. `local` makes no
outbound network call to authenticate, so it is air-gapped-safe the way `cognito` is not: it is the
password-login option for air-gapped installs, from chart 0.2.8, the release that adds
`cognito.mode: local` (GX-53, groundx-on-prem#123; not published yet).

The `local` behavior below applies only to a server image that includes **GX-83**; an older image
does not have it.

**`local` login lock.**
Three failed password attempts within 15 minutes lock that account for 15 minutes, counted from the third failure.
Every spelling of the account's email that the database treats as equal, and the account's username, share one count.
A locked account and a wrong password get the same generic error. The response does not reveal whether an email exists.
A successful login or an admin password reset clears the failure count.
A Redis restart or failover can reset the count; this only gives an attacker a fresh set of attempts and is not a security boundary change.

**Sustained lockout.** Anyone who knows a customer's email can keep that account locked by repeatedly
failing logins. A per-source-IP rate limit at the ingress slows brute-force guessing and bcrypt load:
set the limit annotations for your ingress controller under `groundx.ingress.annotations`, which
apply to every route of the API Ingress. The chart has no defence against a targeted lockout of a
known email; this is an accepted residual.
Recovery for a locked customer is an admin password reset, which clears the lock.

**MCP sign-in prerequisite.** MCP sign-in on chart installs needs GX-112, which exposes the MCP token
secret and the sign-up URL in the chart; the chart does not expose them yet, so the sign-up link is
hidden on chart installs.

**Reset scope.** An admin password reset ends that customer's MCP sessions only. Their API keys and
app sessions are not touched. After a suspected compromise, disable the account and reset its password; the reset
ends its MCP sessions at once. Disabling can take up to an hour to reach cached credentials, because
the server caches API-key lookups for up to 60 minutes. Deleting API keys alone does not help, because
the username itself still works as a credential (GX-113).

**Redis.** MCP session revocation relies on Redis. A Redis failover right after a reset can revive
the MCP sessions that reset ended. Set the Redis `maxmemory-policy` to `noeviction` or a `volatile-*`
policy; under an `allkeys-*` policy the reset marker can be evicted, which revives earlier-ended MCP
sessions (future resets still work). The chart has no setting for the eviction policy. Check it on
the running Redis with `redis-cli CONFIG GET maxmemory-policy`; this also applies to
customer-managed Redis.

**Version requirement — this behavior is not on every published build.** The `apiKeyOnly` and
`cognito` modes ship in the on-prem chart from **0.2.7** (the release that added the `cognito.*`
values block) paired with a server image built from **GX-20** or later. An older published chart
(0.2.6) rejects `cognito.*` at render, and a pre-GX-20 server image still issues a `test-token` and
does not return the `apiKeyOnly` 501s — so on those builds this document's mode behavior does not
yet apply. `local` is not in the published 0.2.7 chart: its schema accepts only `apiKeyOnly` and
`cognito`, so `cognito.mode: local` fails at render. `local` needs chart 0.2.8, the release that adds it
(GX-53, groundx-on-prem#123; not published yet), and a server image built from **GX-53** or
later; on an image without it, `cognito.mode: local` is rejected. The `local` login lock and MCP
behavior above need an image built from **GX-83** or later; after upgrading to one, existing
local-mode MCP sessions must re-authorize once (sessions issued before GX-83 have no owning customer
and are rejected). Confirm the deployed chart and image versions before relying on a mode's
behavior.

A valid key is authenticated as whoever owns it; what that identity can then do is governed by the
partner-boundary check in § 2, not by anything stored on the key itself.

## 2. Admin key vs. ordinary customer key — they are not interchangeable

There is no "admin" flag on the API key itself. The `apikeys` table stores only the key string, a name, the owning username, and a creation timestamp, nothing else. Admin status lives on a separate record, the owning user's account row, marked `status='admin'`, and the two are joined only by username.

`admin.apiKey` and `admin.username` are not interchangeable either, even though both get seeded together. The authentication code treats them differently: authenticating with the seeded `admin.apiKey` value resolves to an ordinary, account-scoped key, it does not retain elevated privileges for delegated requests acting on another account. Do not assume "the admin key" is a universal all-access credential for every kind of request; check the specific operation's own auth requirements.

Practically: treat the bootstrap admin key as a privileged credential for your own account, not a key that can freely act on other accounts. Issue ordinary customer keys (§ 4) for everyday per-person or per-application access instead of sharing the admin key around.

## 3. Where the first key comes from

The admin key is seeded at install time from your `values.yaml` (`admin.apiKey`, `admin.username`). See `license-and-admin.md` for the full field reference. This section only covers what happens after that: issuing keys for other people.

## 4. Provisioning additional keys, using your own deployment

Separate keys for teammates or applications do not require separate accounts. Any valid key on your account can create more keys for that same account, no account registration step needed.

Find your deployment's own API address:

```bash
kubectl -n eyelevel get svc groundx
# use the external IP / hostname shown for the LoadBalancer
```

Then create a key against your own endpoint, using your existing key:

```bash
curl -X POST http://<your-groundx-external-ip>/api/v1/apikey \
  -H "X-API-Key: <your existing key>" \
  -H "Content-Type: application/json" \
  -d '{"apiKey": {"name": "jane-doe"}}'
```

Give the new key a name that identifies who or what it's for, then hand that key to the teammate or application. Deleting, renaming, and listing keys follow the same pattern, same header, same base URL, only the HTTP method and path change. The full request/response contract for create, list, rename, and delete is documented in `groundx-api/references/07-customer-and-keys.md`, same endpoints, just pointed at your own deployment's address instead of the hosted API.

## 5. Rotating a key

There is no regenerate-in-place. Rotation is three steps: create a new key, move whoever used the old key over to it, then delete the old one.

**Known limitation:** deleting a key does not immediately revoke it. Validated keys are cached for up to 60 minutes, and deletion does not force-expire that cache entry, so a deleted key can keep working for up to an hour afterward. Plan key rotations (especially after a suspected leak) with that window in mind. The caching behavior itself is a backend fix candidate; this doc does not attempt to work around it.

## 6. What this does not give you

- SSO, OIDC, or SAML on-prem, under any `cognito.mode`. `cognito.mode: cognito` wires
  Cognito-backed password login; it does not add SSO/OIDC/SAML federation on top of Cognito.
- Interactive dashboard login when `cognito.mode: apiKeyOnly` (the default) — every
  human-identity route returns HTTP 501 under this mode. Set `cognito.mode: cognito` or
  `cognito.mode: local` in `values.yaml` (see `values-yaml.md` § 2) to enable a password-based
  login path instead.
- A working login from setting `admin.password` in `values.yaml`, under any mode. It is not used
  by the login path; see the correction in `license-and-admin.md` § 2.

## 7. What this file does not cover

- **values.yaml fields for the admin block and license key** → `license-and-admin.md`.
- **The full `cognito.*` field reference (`mode`, `clientId`, `clientSecret`, `poolId`, `region`)**
  → `values-yaml.md` § 2.
- **Full API key-endpoint request/response contract** → `groundx-api/references/07-customer-and-keys.md`.
- **Database/search/file/summary credentials unrelated to identity** → `credentials.md`.
