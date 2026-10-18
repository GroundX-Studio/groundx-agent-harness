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
the MCP authorize page uses browser-based email/password authentication instead of API-key authentication. `local` makes no
outbound network call to authenticate, so it is air-gapped-safe the way `cognito` is not.

**Version requirement — this behavior is not on every published build.** The three-mode selection
ships in the on-prem chart from **0.2.7** (the release that added the `cognito.*` values block)
paired with a server image built from **GX-20** or later. An older published chart (0.2.6) rejects
`cognito.*` at render, and a pre-GX-20 server image still issues a `test-token` and does not return
the `apiKeyOnly` 501s — so on those builds this document's mode behavior does not yet apply. `local`
additionally requires a server image built from **GX-53** or later; on an image without it,
`cognito.mode: local` is rejected. Confirm the deployed chart and image versions before relying on a
mode's behavior.

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
