# License Key and Admin Credentials

This file documents **the small but load-bearing surface at the top of values.yaml that bootstraps a GroundX deployment** — the license key, the admin block, the relationship between admin values and the in-cluster API key, and how the `admin.imageRepository` field overrides the chart-wide image-repo prefix.

For the broader credentials story (database, search, file, summary, stream, workspace tokens) route to `credentials.md`. For how these values land in pods, route to `values-yaml.md` § 2 and § 3. For image-variant choices, route to `image-variants.md`.

## 1. The two fields

| values key | Type | Default | Required? | What it does |
| --- | --- | --- | --- | --- |
| `licenseKey` | string | `""` | No (chart renders fine without it) | Written into the in-cluster `config-yaml-map` Secret as `admin.licenseKey`. Consumed by the in-cluster golang application and metrics services at startup (both mount `config-yaml-map` per `templates/app/golang.yaml:168–170` and `templates/app/metrics.yaml:206–208`). |
| `admin` | object | `{}` | No, but supplying any field surfaces an `admin:` section in the rendered config | Bundles the bootstrap administrator identity. Five optional fields. |

Both live at the top level of values.yaml — not under any subsystem.

```yaml
licenseKey: "00000000-0000-0000-0000-000000000000"

admin:
  apiKey: "00000000-0000-0000-0000-000000000000"
  email: "admin@example.com"
  password: "<bootstrap-password>"
  username: "00000000-0000-0000-0000-000000000000"
  imageRepository: "my-registry.example.com/groundx"   # optional, see § 4
```

## 2. The admin block — field-by-field

The chart treats every admin field as optional. The schema (`values.schema.json:27–37`) lists them as string-typed with no required, and the helpers in `templates/_helpers/main.tpl:5–23` default each to the empty string.

| Field | What the chart does with it | Notes |
| --- | --- | --- |
| `admin.apiKey` | Written to the rendered `config.yaml` as `admin.apiKey` and **also appended to the Python services' valid-API-keys list** alongside `admin.username` and `cluster.validApiKeys` (see § 5). Consumed by the in-cluster services at startup. | UUID format conventional. If omitted, the chart simply omits the `admin.apiKey` line from `config.yaml` (`config-yaml.yaml:106–108`). |
| `admin.email` | Stored on the bootstrap administrator record. | Free-form string. Not validated at template time. |
| `admin.password` | Setting it does **not** produce a working login under any mode. The value is loaded but not written to the seeded admin account record and not used by the login path, which depends on the deployment's selected `cognito.mode` (`apiKeyOnly`, `cognito`, or `local`), not this field. | Do not rely on this field for admin access. See `identity-model.md` § 1 and § 6. |
| `admin.username` | Doubles as the **internal API key used by in-cluster services** to call each other. Referenced via `groundx.admin.username` in `extract.client.apiKey`, `eyelevelSearch.apiKey`, `layout.client.apiKey`, and `owner.username` blocks in `config-yaml-map` (`templates/resources/config-yaml.yaml:154–170`, `:573–575`). | This is the non-obvious one — `admin.username` is not just a display name; it is the key in-cluster service calls authenticate with. Set it to a stable UUID. |
| `admin.imageRepository` | Overrides the chart-wide image-repo prefix (default `public.ecr.aws/c9r4x6y5`). Every chart-rendered image path (`{prefix}/eyelevel/<service>:<tag>`) keys off this. | See § 4. |

The fields land in the `config-yaml-map` Secret (`templates/resources/config-yaml.yaml:103–121`) inside an `admin:` block — but only when *at least one* of `admin.apiKey`, `admin.email`, `admin.password`, `admin.username`, or `licenseKey` is non-empty. If you set none of them, the rendered config simply has no `admin:` block at all, and the application uses its built-in defaults.

## 3. The license key — what it does

`licenseKey` is the key associated with the customer's GroundX subscription. It is consumed inside `config-yaml-map` (`templates/resources/config-yaml.yaml:112–114`). The chart treats it as a free-form string and writes it through verbatim under `admin.licenseKey` in the rendered `config.yaml`. Note that the application does not currently enforce the key at runtime; setting it correctly is still good practice for forward compatibility and audit trail.

Behaviour when `licenseKey` is unset:

- The chart renders successfully.
- All Kubernetes resources install.
- No `admin.licenseKey` field appears in the rendered config.

Behaviour when `licenseKey` is set:

- The string is written into `admin.licenseKey` of the rendered `config.yaml`.
- The application reads it at startup.

For sanitized example values, the upstream chart uses `00000000-0000-0000-0000-000000000000` as a placeholder. This is the *shape* of a real key, not a working one.

## 4. `admin.imageRepository` — the hidden override

The chart constructs every default image path through `groundx.imageRepository` (`templates/_helpers/main.tpl:109–117`):

```go-template
{{- define "groundx.imageRepository" -}}
{{- $in := .Values.admin | default dict -}}
{{- $repo := dig "imageRepository" "" $in -}}
{{- if ne $repo "" -}}
{{ $repo }}
{{- else -}}
public.ecr.aws/c9r4x6y5
{{- end -}}
{{- end }}
```

So `admin.imageRepository` is **the single field that re-points every default image to a private mirror**. When the field is empty (the chart default), images come from the EyeLevel-published public ECR registry at `public.ecr.aws/c9r4x6y5`. When set, every default `image:` field in the chart's helpers (`groundx.cache.image`, `groundx.layout.ocr.image`, `groundx.process.image`, etc.) prefixes the new value instead.

This is the field to set when:

- The cluster is air-gapped and reaches a private registry, not the public internet.
- Compliance requires the deployer maintain control of every image used.
- The deployer wants Chainguard or other hardened variants from a private mirror.

Note that per-pod `image:` values (e.g., `layout.ocr.image: my-registry/custom-ocr:latest`) still take precedence over `admin.imageRepository`. The repository field is the *default* prefix, applied only where the deployer hasn't supplied an explicit image path.

## 5. The admin → in-cluster API key relationship

The single most useful thing to know about this surface: **`admin.username` is the in-cluster API key**.

The chart writes the value of `admin.username` into three `apiKey:` fields inside the golang services' `config.yaml` — the slots used by in-cluster HTTP clients that call extract, eyelevel-search (the ranker), and layout:

- `ai.extract.client.apiKey` (rendered at `config-yaml.yaml:156–158`)
- `ai.eyelevelSearch.apiKey` (rendered at `config-yaml.yaml:162–164`, note: this is `apiKey` directly under `eyelevelSearch`, not `eyelevelSearch.client.apiKey`)
- `ai.layout.client.apiKey` (rendered at `config-yaml.yaml:168–170`)

Each is guarded by `if ne (include "groundx.admin.username" .) ""` — if `admin.username` is empty, the `apiKey:` line is simply omitted and the calling pod issues unauthenticated in-cluster HTTP. The namespace boundary is still the trust enclosure (`groundx-architecture/references/identity-and-trust.md` § 6), so this remains functional, just less auditable.

The Python services (ranker, layout, extract, summary) build a **list** of accepted API keys at startup that includes `admin.apiKey`, `admin.username`, and the entries in `cluster.validApiKeys`. The list is constructed inline in each Python service's `config.py` Secret — see `ranker-config-py.yaml:32–43`, `layout-config-py.yaml`, `extract-config-py.yaml`, `summary-config-py.yaml` for the same pattern. So **`admin.apiKey` and `admin.username` are *both* valid in-cluster API keys** for the Python services — and the deployer can add more via `cluster.validApiKeys: [<key>, <key>, ...]`.

`groundx.admin.username` is read directly in:

- `ranker-config-py.yaml:37`
- `layout-config-py.yaml:60`
- `extract-config-py.yaml:116`
- `summary-config-py.yaml:30`

There are also **indirect** references (via `callbackApiKey`-style helpers that default to `admin.username` when an explicit override isn't supplied):

- `layout-config-py.yaml:30` (via `groundx.layout.callbackApiKey`, defined at `_helpers/app/layout.tpl:6–9`)
- `extract-config-py.yaml:92, 127–128` (via `groundx.extract.callbackApiKey`, defined at `_helpers/app/extract.tpl:11–14`)

A deployer can override the callback paths by setting `layout.callbackApiKey` / `extract.callbackApiKey` explicitly. Left unset, both inherit `admin.username`. So a single change to `admin.username` propagates broadly across the in-cluster mesh, and `cluster.validApiKeys` is the escape hatch for adding additional valid keys without rotating either admin field.

In addition, `admin.username` is written into `owner.username` (`config-yaml.yaml:573–575`). That field is the deployment's identity record, not an API key — but it shares the same source value, so rotating `admin.username` rotates the identity record too.

Set `admin.username` to a stable, opaque value. UUID format is conventional. Treat it as a credential — anyone with cluster admin, or a Role granting `get`/`list` on `secrets` in the target namespace, can extract it from the `config-yaml-map` Secret. **Version caveat:** this holds on chart `0.2.7+` (GX-17), where `config-yaml-map` renders as a Secret. On `0.2.6` and earlier the same value sits in a plain **ConfigMap**, so the attack surface is wider there — any `get`/`list` on `configmaps` (not `secrets`) reads it. Scope the Role to the resource kind the deployed chart version actually renders.

## 6. Bootstrap recipe — minimal setup

For a first install:

```yaml
licenseKey: "<your-license-key-or-leave-unset>"

admin:
  apiKey: "<uuid-1>"
  email: "admin@yourcompany.example"
  password: "<bootstrap-password>"
  username: "<uuid-2>"
```

Two UUIDs, one bootstrap password, one optional license, one email. Everything else (database, file storage, summary, etc.) is covered by `credentials.md` and the per-subsystem files.

## 7. Operator handoff

When transitioning the deployment from install to operations:

1. **Do not rely on `admin.password` for login.** It has no effect on the on-prem login path today, under any selected `cognito.mode` (see § 2 and `identity-model.md` § 1 and § 6); there is no working admin-password login to rotate.
2. **`admin.apiKey` and `admin.username` are not rotated through Helm.** They're set once and remain stable. If a rotation is needed (e.g., after a credential leak), the deployer must coordinate with the application's admin API to issue a new key, then `helm upgrade` the chart to match.
3. **`licenseKey` tracks the customer's subscription.** Long-lived deployments should update it when the subscription is renewed — re-run `helm upgrade --install` after editing values.yaml. Enforcement is not currently active, but keeping the value accurate avoids future surprises.

## 8. Where to put these in production

- **Don't check values.yaml with real `admin.password`, `admin.apiKey`, or `licenseKey` into git.** Use a separate, gitignored secrets file passed as a second `-f` argument to `helm install`/`helm upgrade`. See `credentials.md` § 4 for the layered values pattern.
- **For CI/CD pipelines**, source these values from the pipeline's secret store (Vault, AWS Secrets Manager, GCP Secret Manager) and assemble the secrets-only values file at install time.
- **For air-gapped clusters**, the same pattern applies — the secrets file lives on the operator's workstation or in a sealed-secret-encoded git repo.

## 9. What this file does not cover

- **The runtime identity model — admin vs. ordinary keys, provisioning more keys, rotation, and its known caching limitation** → `identity-model.md`.
- **Database / search / summary / stream / workspace credentials** → `credentials.md`.
- **Field-by-field schema for the rest of values.yaml** → `values-yaml.md`.
- **How `admin.imageRepository` interacts with image-variant choices (Chainguard, distroless)** → `image-variants.md`.
- **The runtime application's password-hashing, login, or session model** → out of scope for this skill; application docs only.
- **License-key entitlement model or what a key authorizes** → out of scope; coordinate with the GroundX point of contact.
