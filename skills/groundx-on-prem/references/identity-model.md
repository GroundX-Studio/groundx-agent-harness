# Identity Model — On-Prem Authentication

This file states what actually authenticates requests against a self-hosted GroundX deployment today, and how an operator gives access to more than one person. For the values.yaml fields that bootstrap the first key, see `license-and-admin.md`. For the open gap in interactive login, see GX-20 (tracked separately, not fixed by this file).

## 1. What authenticates today

On-prem GroundX, as currently configured, authenticates every request with a single header: `X-API-Key`, checked against the database. There is no SSO, OIDC, SAML, or interactive dashboard login wired up on-prem today, and no per-key scopes or permissions table. This is a current-configuration gap, not a product-wide limitation: GroundX Cloud already authenticates through Cognito, and GX-20 is extending configurable Cognito support to on-prem. A valid key is authenticated as whoever owns it; what that identity can then do is governed by the partner-boundary check in § 2, not by anything stored on the key itself.

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

**Known limitation:** deleting a key does not immediately revoke it. Validated keys are cached for up to 60 minutes, and deletion does not force-expire that cache entry, so a deleted key can keep working for up to an hour afterward. Plan key rotations (especially after a suspected leak) with that window in mind. The caching behavior itself is a backend fix candidate, tracked separately, not something this doc can work around.

## 6. What this does not give you

- No SSO, OIDC, SAML, or interactive dashboard login on-prem, as currently configured. GX-20 is extending configurable Cognito support to on-prem; until that lands, this is what's true here.
- Setting `admin.password` in `values.yaml` does **not** produce a working login. It is not used by the login path today; see the correction in `license-and-admin.md` § 2.

## 7. What this file does not cover

- **values.yaml fields for the admin block and license key** → `license-and-admin.md`.
- **Full API key-endpoint request/response contract** → `groundx-api/references/07-customer-and-keys.md`.
- **Interactive login, SSO/OIDC decision, Cognito wiring** → GX-20; not fixed or worked around here.
- **Database/search/file/summary credentials unrelated to identity** → `credentials.md`.
