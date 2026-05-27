# Credentials and Secret Handling

This file owns the deeper secret-handling depth deferred from `values-yaml.md` § 8 and `values-authoring.md` § 3.8: every credential the chart consumes, the six patterns for managing them, the workload-identity deep dive that replaces several patterns entirely on cloud platforms, rotation strategies, CI/CD injection, multi-environment isolation, common mistakes, and the placeholder-discipline contract this skill (and every other skill in the harness) follows for example credentials.

For the field-level shapes credentials populate, route to `values-yaml.md` § 8. For the discovery questionnaire that selects a credential pattern at deployment time, route to `values-authoring.md` § 3.8.

## 1. Credential surface inventory

Every credential the chart consumes, grouped by where the application uses it:

| Credential | Field path | Used for |
| --- | --- | --- |
| License key | `licenseKey` | GroundX license validation. |
| Bootstrap admin API key | `admin.apiKey` | First admin user's API key. |
| Bootstrap admin email / username / password | `admin.{email, username, password}` | First admin user's identity. |
| MySQL app user / password | `db.{username, password}` | Application's DB connection. |
| MySQL privileged user / password | `db.{privilegedUsername, privilegedPassword}` | Chart-install-time bootstrap (creates the app user / database / tables). |
| MySQL TLS root CA | `db.existing.rootCerts` or `db.rootCerts` | Verifies the DB's TLS cert. Multi-line PEM. |
| Object store credentials | `file.{username, password}` (bundled MinIO and external S3) | Reads / writes uploaded documents, intermediate artifacts, X-Rays. |
| Cache credentials | `cache.existing.{addr, port, ssl, isCluster}` + Redis AUTH (out-of-band) | Bundled Redis is auth-less; external Redis often requires a password set via env or sidecar. |
| Search credentials | `search.{username, password, privilegedUsername, privilegedPassword}` | OpenSearch index reads + management. |
| Queue (SQS) credentials | `stream.{key, secret}` at the top level, or per-topic overrides under each `stream.topics.<topic-name>` block (the `key` and `secret` sub-fields) | AWS access key / secret for SQS topics. |
| Queue token | `stream.token` at the top level, or per-topic override under each `stream.topics.<topic-name>` block (the `token` sub-field) | Token-based auth for stream backends that support it (alternative to key/secret pairs). |
| File-store token | `file.token` | Token-based auth for object-store backends that support it (alternative to username/password). |
| Chart-default LLM API key | `engines.default.apiKey` | Default outbound LLM API key consumed by any microservice that delegates to the chart-default engine. Per-microservice overrides (`summary.existing.apiKey`, `extract.agent.apiKey`) take precedence. |
| Outbound summary LLM API key | `summary.existing.apiKey` | External LLM endpoint auth when `summary.api.enabled: false` + `summary.inference.enabled: false`. |
| Outbound extract LLM API key | `extract.agent.apiKey` | External LLM endpoint auth for the extract agent. |
| Extract-side object-store credentials | `extract.file.{username, password}` | When the extract pipeline writes to a *different* S3 bucket than the ingest pipeline. AWS access key / secret for that bucket. |
| Extract callback API key | `extract.callbackApiKey` | Validates inbound callbacks the extract pipeline POSTs results to. |
| GCP service account JSON (OCR) | `layout.ocr.credentials` is a string path to a chart-packaged JSON file (e.g. `files/ocr/credentials.json`). Chart materializes a ConfigMap from the file at install time. | Google Cloud Vision API auth when `layout.ocr.type: google`. |
| GCP service account JSON (extract save) | `extract.save.gcpCredentials` | Google Drive / Sheets API auth when extracting to Google Drive. |
| Workspace runner token | `workspace.token` | GitHub / GitLab `git push` auth. |
| GitHub App private key | `workspace.github.privateKeyPem` or `workspace.github.privateKeySecret.{name,key}` | GitHub App token-minting key. |
| GitLab API token | `workspace.gitlab.token` or `workspace.gitlab.tokenSecret.{name,key}` | GitLab API auth. |
| Image-pull secrets | `cluster.imagePullSecrets` | Pulls private container images (Chainguard, internal mirror). |
| Cluster-wide TLS cert | `cluster.tls.existingSecret` | In-cluster TLS for service-to-service. References a `kubernetes.io/tls` Secret. |
| Internal API keys (callback, internal-service) | `cluster.validApiKeys` | API keys the chart bakes into the runtime config as recognized credentials. |

For schema-level field-shape detail per credential, see `values-yaml.md`. For the standard env-var names the chart accepts when reading credentials from a mounted Secret (`GROUNDX_*`, `MYSQL_*`, `AWS_*`, `WORKSPACE_RUNNER_TOKEN`, `GITHUB_APP_PRIVATE_KEY_PEM`), see `values-yaml.md` § 8.2.

## 2. Pattern selection guide

Six patterns. Pick one per credential type, not one for the whole deployment. Mixing is the norm.

| Pattern | Where credentials live | When to use |
| --- | --- | --- |
| **1. Inline in main values.yaml** | Plain text in `values.yaml`. | Dev / sandbox only. Never production. The main values file is reviewed and version-controlled — credentials in it leak. |
| **2. Secret companion file** | Plain text in `values.<env>.secret.yaml`, gitignored or stored encrypted out-of-band. | Single-environment deployments where SecretOps tooling is overkill. Same shape as inline; just separated for git hygiene. |
| **3. Kubernetes Secret reference** (`groundx-secret` prereq chart) | A pre-installed Kubernetes Secret named e.g. `eyelevel-secret-credentials`. Chart references it via `cluster.secrets: [<name>]`. | Production baseline. SOC2-friendly. The Secret is created from the same companion-file shape (Pattern 2) but installed once, never re-applied with each deploy. |
| **4. External Secrets Operator** (ESO + cloud secret manager) | The Kubernetes Secret is **synced from** AWS Secrets Manager / Azure Key Vault / GCP Secret Manager / HashiCorp Vault by ESO. The chart references the Secret the same way as Pattern 3. | Production at scale. Rotations happen in the secret manager; ESO syncs. Auditable; tooling-integrated. |
| **5. Sealed Secrets** (Bitnami sealed-secrets) | Encrypted `SealedSecret` manifests committed to git. The sealed-secrets controller in the cluster decrypts on apply. | GitOps deployments where every Kubernetes resource is committed. |
| **6. SOPS / Helm Secrets** | `values.<env>.secret.yaml` is SOPS-encrypted; `helm-secrets` plugin decrypts at install time. Encrypted file committed to git. | GitOps deployments that prefer per-file encryption over per-resource (Sealed Secrets). |
| **Workload Identity** (IRSA / AKS WI / GKE WIF) | No credential in values.yaml at all. The ServiceAccount is bound to a cloud IAM role that grants the chart's pods access to AWS / Azure / GCP services. | **Replaces** Patterns 1–6 for cloud service credentials (S3, RDS, SQS, ElastiCache, AOS). Pattern 3+ still needed for non-cloud credentials (LLM API keys, GitHub tokens, license key). |

**Decision tree for picking a pattern per credential:**

1. **Is this a cloud-service credential** (AWS S3 / SQS / RDS / ElastiCache, Azure Database / Cache / Blob, GCP Storage / SQL)?
   - Yes → prefer workload identity (IRSA / AKS WI / GKE WIF). No credential goes in values.yaml.
   - No → continue.
2. **Does the deployment use GitOps with everything in git?**
   - Yes → Pattern 5 (Sealed Secrets) or Pattern 6 (SOPS).
   - No → continue.
3. **Does the deployment have a centralized secret manager** (AWS SM / Azure KV / GCP SM / Vault) with rotation policy?
   - Yes → Pattern 4 (External Secrets Operator).
   - No → continue.
4. **Production deployment?**
   - Yes → Pattern 3 (Kubernetes Secret via `groundx-secret` prereq chart). Never Pattern 1.
   - No → Pattern 1 acceptable for dev / sandbox / minikube.

## 3. Pattern 1 — Inline in main values.yaml

```yaml
db:
  username: eyelevel
  password: <secret>
```

**Use only for** dev clusters, minikube, sandbox CI runs. Never check the resulting values.yaml into a shared repo.

**Cross-environment leakage risk:** the same dev values.yaml gets copied as the starting point for staging / prod and credentials propagate. The team's discipline is the only safeguard. This is why Pattern 1 is a dev-only path.

## 4. Pattern 2 — Secret companion file

Split credentials into `values.<env>.secret.yaml` (gitignored or stored encrypted out-of-band):

```sh
helm upgrade --install groundx ./src/groundx -n eyelevel \
  -f values.prod.yaml \
  -f values.prod.secret.yaml
```

The chart sees the merged result; helm treats both files as one values document. The split exists purely for git-hygiene reasons.

**Hygiene checklist:**

- Add `*.secret.yaml` to the deployer repo's gitignore at the root.
- Add a gitleaks-style pre-commit hook to catch accidents.
- Treat `values.<env>.secret.yaml` like any password file: backed up encrypted, never emailed, never pasted in chat.

**Limitations:** scales poorly past one or two environments — every operator who deploys needs a copy of the file. Use Pattern 3 / 4 / 5 / 6 in production.

## 5. Pattern 3 — Kubernetes Secret reference (groundx-secret prereq chart)

The upstream `groundx-on-prem` repo's `groundx-secret` prereq chart wraps a Kubernetes Secret. The chart's values shape:

```yaml
name: eyelevel-secret-credentials
namespace: eyelevel
data:
  GROUNDX_LICENSE_KEY: <license>
  GROUNDX_ADMIN_API_KEY: <uuid>
  GROUNDX_ADMIN_EMAIL: <email>
  GROUNDX_ADMIN_PASSWORD: <password>
  GROUNDX_ADMIN_USERNAME: <uuid>
  GROUNDX_AGENT_API_KEY: <llm-api-key>
  GROUNDX_ACCESS_KEY_ID: <aws-key>           # if not using IRSA
  GROUNDX_SECRET_ACCESS_KEY: <aws-secret>    # if not using IRSA
  MYSQL_INIT_USER: <priv-user>
  MYSQL_INIT_PASSWORD: <priv-password>
  MYSQL_USER: <app-user>
  MYSQL_USERNAME: <app-user>             # alias to MYSQL_USER on some deployments
  MYSQL_PASSWORD: <app-password>
  WORKSPACE_RUNNER_TOKEN: <git-token>
  GITLAB_TOKEN: <gitlab-api-token>       # only when gitProvider is gitlab
  GITHUB_APP_PRIVATE_KEY_PEM: |
    -----BEGIN PRIVATE KEY-----
    ...
    -----END PRIVATE KEY-----
```

Install once, before the main chart:

```sh
helm upgrade --install groundx-secret groundx/groundx-secret \
  -n eyelevel \
  -f values.prod.secret.yaml
```

Then reference from the main chart:

```yaml
# values.prod.yaml
cluster:
  secrets:
    - eyelevel-secret-credentials
```

The chart wires the Secret's env-var-named keys into every pod via `envFrom`. The application reads `GROUNDX_*` / `MYSQL_*` / `AWS_*` / `WORKSPACE_RUNNER_TOKEN` / `GITHUB_APP_PRIVATE_KEY_PEM` at startup and maps them to runtime config.

**Per-feature Secret references** (alternative or complementary to `cluster.secrets`):

- `workspace.existingSecret: <secret-name>` — looks for `WORKSPACE_RUNNER_TOKEN` in the named Secret.
- `workspace.secretName: <secret-name>` — alternative top-level Secret reference for workspace credentials.
- `workspace.github.secretName: <secret-name>` — alternative provider-flexible Secret reference for GitHub credentials (carries multiple GitHub-related keys in one Secret).
- `workspace.github.privateKeySecret.{name, key}` — names a Secret + key holding the GitHub App private key (precise key reference).
- `workspace.gitlab.secretName: <secret-name>` — alternative provider-flexible Secret reference for GitLab credentials.
- `workspace.gitlab.tokenSecret.{name, key}` — names a Secret + key holding the GitLab token (precise key reference).
- `extract.agent.existingSecret: true` + `extract.agent.secretName: <name>` — looks for the LLM API key.
- `extract.save.existingSecret: true` + `extract.save.secretName: <name>` — looks for the GCP service account JSON.
- `cluster.tls.existingSecret: <secret-name>` — references a `kubernetes.io/tls` Secret for in-cluster TLS.

**Chart-auto-materialized workspace Secrets.** When the deployer provides workspace credentials *inline* in values.yaml (rather than via Pattern 3's `existingSecret` / `secretName` references), the chart auto-materializes three separate Secrets:

| Inline field | Auto-generated Secret name | Carries env var |
| --- | --- | --- |
| `workspace.token` | `<workspace-service>-secret` (overridable via `workspace.secretName`) | `WORKSPACE_RUNNER_TOKEN` |
| `workspace.github.privateKeyPem` | `<workspace-service>-github-secret` (overridable via `workspace.github.secretName`) | `GITHUB_APP_PRIVATE_KEY_PEM` |
| `workspace.gitlab.token` | `<workspace-service>-gitlab-secret` (overridable via `workspace.gitlab.secretName`) | `GITLAB_TOKEN` |

**Dual write semantics** when `workspace.token` is inline (per upstream README line 385): the chart writes the token to *both* the generated GroundX `config.yaml` (as `workspace.token`) and the runner `config.py` (as `runner_token`), **and** creates the `<workspace-service>-secret` carrying `WORKSPACE_RUNNER_TOKEN` as an environment-variable fallback. When `workspace.existingSecret` is provided instead, the config files render the token *empty* and the GroundX API service + workspace runner pods fall back to the env-var path. This dual-write-vs-env-fallback design lets the chart support both inline (dev) and Secret-referenced (production) patterns transparently.

**GitHub private-key mount path:** when `workspace.github.privateKeySecret.{name, key}` is used (production path), the named Secret is mounted only into workspace API + worker pods at `/var/run/secrets/workspace/github/private-key.pem`. GitHub credentials are not mounted into the GroundX API service pods. (Source: upstream README line 409.)

## 6. Pattern 4 — External Secrets Operator (ESO + cloud secret manager)

ESO syncs Kubernetes Secrets from an external secret backend. Rotations happen in the backend; ESO re-syncs on a configured interval.

**Architecture:**

```
AWS Secrets Manager
        │ (or Azure KV / GCP SM / Vault)
        ▼
External Secrets Operator (in-cluster)
        │
        ▼
Kubernetes Secret: eyelevel-secret-credentials
        │
        ▼
GroundX pods (via cluster.secrets reference)
```

**Setup outline (AWS Secrets Manager example):**

1. Create the secret in AWS Secrets Manager with the same env-var-name keys as in Pattern 3 (`GROUNDX_LICENSE_KEY`, etc.).
2. Install ESO in the cluster (separate chart, separate namespace).
3. Create a `ClusterSecretStore` pointing at AWS Secrets Manager (auth via IRSA-bound ServiceAccount).
4. Create an `ExternalSecret` that maps AWS secret keys to a Kubernetes `Secret` named `eyelevel-secret-credentials`. ESO creates / updates that Secret automatically.
5. In the main chart's values.yaml, reference the synced Secret: `cluster.secrets: [eyelevel-secret-credentials]`.

The application doesn't know ESO is involved — from its perspective the Secret just exists.

**Trade-offs:**

- **Pros:** Rotations happen in one place (AWS SM). Auditable. Multi-environment isolation built in (separate AWS secrets per environment). No credentials in helm values or git.
- **Cons:** Extra moving part (ESO must be running for the application to start cleanly after a Secret refresh). Backend lock-in (changing AWS SM → Vault means rewriting `ClusterSecretStore` + `ExternalSecret` resources).

## 7. Pattern 5 — Sealed Secrets (GitOps-friendly)

Bitnami's sealed-secrets controller encrypts a `Secret` into a `SealedSecret` resource. The `SealedSecret` is safe to commit to git; only the in-cluster controller can decrypt it.

**Setup outline:**

1. Install the sealed-secrets controller in the cluster.
2. Locally: encrypt the secret companion values:
   ```sh
   kubectl create secret generic eyelevel-secret-credentials \
     -n eyelevel \
     --from-literal=GROUNDX_LICENSE_KEY=<license> \
     --from-literal=MYSQL_USER=<user> \
     ... \
     --dry-run=client -o yaml | kubeseal -o yaml > sealed-secret.yaml
   ```
3. Commit `sealed-secret.yaml` to git.
4. The cluster's GitOps controller (Flux / ArgoCD) applies `sealed-secret.yaml`; the sealed-secrets controller decrypts it into a real `Secret`.
5. Main chart references the resulting Secret via `cluster.secrets: [eyelevel-secret-credentials]`.

**Trade-offs:**

- **Pros:** Everything in git; per-cluster encryption keypair gives strong cluster-scoping. Works with any GitOps controller.
- **Cons:** Rotation requires re-sealing + re-applying. Cluster keypair must be backed up (lose it and you can't decrypt; rotate it and every `SealedSecret` in git must be re-sealed). Doesn't integrate with cloud secret managers — manual rotation only.

## 8. Pattern 6 — SOPS / Helm Secrets

[SOPS](https://github.com/getsops/sops) encrypts only the values of a YAML / JSON file, leaving the keys readable. Encrypted file is committed to git. The `helm-secrets` plugin decrypts at install time.

**Setup outline:**

1. Pick a backend: AWS KMS, Azure Key Vault, GCP KMS, age, PGP.
2. Encrypt the secret companion file:
   ```sh
   sops -e values.prod.secret.yaml > values.prod.secret.enc.yaml
   ```
3. Commit `values.prod.secret.enc.yaml` to git.
4. Install the `helm-secrets` plugin: `helm plugin install https://github.com/jkroepke/helm-secrets`.
5. Install: `helm secrets upgrade --install groundx ./src/groundx -n eyelevel -f values.prod.yaml -f secrets://values.prod.secret.enc.yaml`.

**Trade-offs:**

- **Pros:** File-level rather than resource-level encryption (simpler model). Pluggable backend (KMS / KV / GPG / age). Auditable (git history of encrypted file).
- **Cons:** Decryption happens at install time on the operator's machine — that machine has cluster credentials AND backend access. Plugin must be installed everywhere helm is run.

## 9. Workload Identity — replaces credentials for cloud services

Workload Identity (IRSA on AWS EKS, Azure Workload Identity, GKE Workload Identity Federation) binds a Kubernetes ServiceAccount to a cloud IAM principal. Pods using that ServiceAccount get cloud credentials *automatically* via short-lived tokens. **No AWS / Azure / GCP credentials need to live in values.yaml or any Kubernetes Secret.**

**What workload identity replaces:**

| Credential | What workload identity covers |
| --- | --- |
| `file.{username, password}` (S3) | IAM role grants S3 read/write to the configured bucket. Omit `file.username` / `file.password` entirely. |
| `stream.{key, secret}` (SQS) | IAM role grants SQS access. Omit `stream.key` / `stream.secret`. |
| `extract.file.{username, password}` (S3) | Same as `file.*`. Omit. |
| `extract.save.gcpCredentials` (GCP Drive / Sheets) | When the cluster runs on GCP with WIF, the GCP SA binding covers Drive access. |
| `layout.ocr.credentials` (GCV) | Same — WIF on GCP gives Vision API access. |
| `db.*` credentials | Limited — RDS / Azure Database / Cloud SQL support IAM auth, but the chart's MySQL driver may not. Test before relying on it. Most deployments still set `db.{username, password}` even with workload identity for the cluster. |
| `cache.existing.*` credentials | Same — Redis Auth via cloud IAM is technology-specific. Most deployments still set Redis AUTH credentials out-of-band. |

**What workload identity does NOT cover:**

- License key (`licenseKey`)
- Bootstrap admin (`admin.*`)
- LLM API keys (`summary.existing.apiKey`, `extract.agent.apiKey`)
- GitHub / GitLab tokens (`workspace.token`, `workspace.github.*`, `workspace.gitlab.*`)
- Database credentials (in most cases — see above)
- Cache credentials (in most cases — see above)
- The `cluster.validApiKeys` list

So workload identity reduces but does not eliminate the credential surface. Mix workload identity with Pattern 3 / 4 for the remaining credentials.

**Setup per platform:**

- **AWS EKS (IRSA):** Annotate the ServiceAccount with `eks.amazonaws.com/role-arn=arn:aws:iam::<account>:role/<role-name>`. The role's trust policy must allow the EKS OIDC issuer. Set `serviceAccount.name` in values.yaml.
- **Azure AKS (Workload Identity):** Enable Workload Identity on the AKS cluster. Annotate the ServiceAccount with `azure.workload.identity/client-id=<client-id>`. Set `serviceAccount.name`.
- **GCP GKE (Workload Identity Federation):** Annotate the ServiceAccount with `iam.gke.io/gcp-service-account=<sa>@<project>.iam.gserviceaccount.com`. Set `serviceAccount.name`.

## 10. Mixing patterns

A real deployment typically mixes patterns. Common production composition:

- **Workload identity** for AWS S3 / SQS access (no credential in values.yaml).
- **External Secrets Operator** synced from AWS Secrets Manager for: license key, bootstrap admin, LLM API keys, GitHub App private key, MySQL credentials, OpenSearch credentials.
- **Direct `cluster.tls.existingSecret`** reference for the in-cluster TLS cert installed by cert-manager.
- **Per-feature `existingSecret`** fields for workspace runner + extract agent that point at the ESO-synced Secret.

Or for a GitOps deployment:

- **Workload identity** for cloud services.
- **Sealed Secrets** for: license key, admin credentials, LLM API keys.
- **SOPS** for the cluster TLS cert + GitHub App private key.

Pick patterns per credential. Don't insist on one pattern across the whole credential surface.

## 11. Rotation patterns

Per credential, the recommended rotation cadence + how to roll without downtime:

| Credential | Cadence | Rotation procedure |
| --- | --- | --- |
| License key | At renewal (annual) | Update the Secret. Pods read at startup. Restart pods to pick up new value. |
| Bootstrap admin password | One-time at install. Rotate via the management API thereafter. | Don't rotate via values.yaml — use the API. |
| MySQL app password | Quarterly | Update the Secret. Update RDS / Percona user password to match. Roll pods (drain one at a time). |
| MySQL privileged password | Quarterly | Update the Secret. Used only at install / upgrade time. |
| LLM API keys | Per rotation policy (often quarterly) | Update the Secret. Roll pods. Keep the old key valid in the LLM provider for an overlap window. |
| GitHub App private key | At GitHub App rotation (rarely) | Update the Secret. Roll workspace pods. GitHub supports keeping two keys valid during rotation. |
| GitLab token | Per token TTL (often 1 year) | Update the Secret. Roll workspace pods. |
| Cluster TLS cert | Per cert-manager renewal (90 days typical for Let's Encrypt) | cert-manager updates the Secret automatically. Pods need to pick up the new cert — chart's TLS-aware microservices either watch the Secret or require a restart. |
| AWS access keys (when not using IRSA) | Per IAM policy (often 90 days) | Switch to IRSA. If keys are unavoidable, update the Secret + IAM policy together. |

**Universal rotation tip:** the chart reads most credentials at pod startup, not via watch. Rotation requires a pod restart for the new value to take effect. Use a `kubectl rollout restart deployment` per affected microservice to roll cleanly.

## 12. CI/CD secret injection

For pipelines that drive `helm install` / `helm upgrade`:

1. **Pipeline pulls credentials from the secret manager** (AWS SM / Azure KV / GCP SM / Vault) using the pipeline's own service identity.
2. **Pipeline materializes the secret companion file** (Pattern 2) in the pipeline-run sandbox, then deletes it before the run terminates.
3. **Pipeline runs `helm upgrade -f values.prod.yaml -f /tmp/secret-companion.yaml`.**
4. **No secret is ever committed to git or persisted to the pipeline run logs.**

Alternative (preferred for production):

1. **Pipeline installs / re-syncs ESO** if needed.
2. **Pipeline runs `helm upgrade -f values.prod.yaml`** with no secret companion — the chart references the ESO-synced Kubernetes Secret directly.
3. **No credential touches the pipeline run at all.**

Common CI/CD platforms have native integrations: GitHub Actions has the AWS / Azure / GCP OIDC plugins; GitLab has Vault integration; Jenkins has Vault and AWS / Azure / GCP credentials plugins. Use them rather than environment-variable-based secret injection where possible.

## 13. Multi-environment strategies

For a deployment with `dev` / `staging` / `prod`:

| Strategy | Implementation |
| --- | --- |
| **Separate namespaces, separate Secrets, separate ESO bindings** | Three namespaces in one cluster: `groundx-dev`, `groundx-staging`, `groundx-prod`. Each has its own `eyelevel-secret-credentials` Secret pointing at its own AWS SM secret (or its own SOPS / Sealed Secret). |
| **Separate clusters per environment** | Strongly preferred for production — full isolation. Each cluster has its own ESO + own secret-manager binding. |
| **Same namespace, different release names** | Not recommended — namespace co-tenanting causes credential bleed. The chart assumes namespace ownership; sharing the namespace breaks isolation. |

For values.yaml composition:

- One `values.yaml` per environment (`values.dev.yaml`, `values.staging.yaml`, `values.prod.yaml`).
- All three reference the same `cluster.secrets: [eyelevel-secret-credentials]` — but the Secret is per-namespace, so each environment sees its own credentials.
- Never copy a `values.<env>.yaml` from prod → dev without scrubbing credentials. The Pattern 2 companion-file split helps here.

## 14. Common mistakes

| Mistake | What goes wrong | Fix |
| --- | --- | --- |
| Credentials in the main values.yaml committed to git | Secrets leak to anyone with read access to the repo. | Pattern 2 minimum; ideally Pattern 3+. |
| Same credentials across environments | Compromise of dev exposes prod. | Per-environment Secrets / per-environment ESO bindings. |
| Workload identity assumed to cover ALL credentials | LLM API keys, license, GitHub tokens still leak. | § 9 — workload identity covers cloud services only. |
| Sealed Secret committed to git without backing up the cluster keypair | Cluster recreation loses the ability to decrypt every `SealedSecret`. | Back up the sealed-secrets controller's keypair to a cold-storage backend. |
| SOPS `.enc.yaml` committed; encryption key managed casually | KMS / age key compromise = all environments compromised. | Treat the SOPS encryption key like a root credential. |
| Helm `-f` order wrong | A `values.yaml` later in `-f` order overrides credentials in the secret companion. | Put `-f values.prod.secret.yaml` LAST (rightmost) so it wins. |
| Rotating a credential without restarting pods | New value never gets read; pods continue with the cached startup value. | `kubectl rollout restart` after every credential rotation. |
| `cluster.imagePullSecrets` missing for Chainguard pulls | Pods stuck in `ImagePullBackOff`. | Always set `cluster.imagePullSecrets: [<chainguard-pull-secret>]` when `imageType: chainguard`. |
| `db.existing.rootCerts` omitted for managed DB with TLS-required | DB connection fails with TLS handshake error. | Set the rootCerts PEM bundle. See `values-yaml.md` § 4.2. |
| Mixing inline `db.password` + `cluster.secrets`-referenced `MYSQL_PASSWORD` | One wins, one is silently ignored — usually the inline one. | Pick one pattern per credential, not both. |

## 15. Placeholder discipline for documentation

This skill's example files and code blocks contain **placeholder credentials only** — they must remain non-functional and clearly identifiable as placeholders. The rules:

| Placeholder type | Convention |
| --- | --- |
| UUID-shaped (API keys, admin IDs, license keys) | `00000000-0000-0000-0000-000000000000` literally, OR angle-bracketed `<license-key-from-procurement>`. Never paste real UUIDs even if they look anonymized. |
| OpenAI-style API keys | `<openai-api-key>` angle-bracketed. Never start with `sk-` or `sk-proj-` even as a fake. |
| MySQL passwords | `<db-password>` / `<password>`. Never use real strings like `Lovegroundx` even if those are upstream samples — they leak procedure. |
| GitHub / GitLab tokens | `<github-token>` / `<gitlab-token>`. Never `ghp_*` / `glpat-*` shapes. |
| AWS access keys | `<aws-access-key-id>` / `<aws-secret-access-key>`. Never start with `AKIA` even as a fake. |
| GCP service account JSON | `<gcp-service-account-json>`. Never paste real JSON shapes. |
| Email addresses | `support@example.com`, `admin@example.com`. Never personal emails. |
| Hostnames | `mycorp.example.com`, `<bucket-name>.s3.<region>.amazonaws.com`. Never real customer hostnames. |
| Bucket names, RDS endpoints, OpenSearch endpoints | Angle-bracketed placeholders. Never customer-specific names. |
| TLS cert PEMs | A literal placeholder block, e.g. `<DigiCert Global Root G2 PEM here>`, OR a well-known public CA PEM with a comment indicating it's the public CA. Never customer-specific or self-signed PEMs. |
| GitHub App IDs / installation IDs | Numeric placeholders or angle-bracketed. Never the real `3668636` / `131211506` from upstream files. |

**Rationale:** Placeholders that look real (`AKIA...`, `sk-...`, real UUIDs) sometimes leak into production by accident. Strict angle-bracketed conventions make it visually impossible to confuse a placeholder with a working credential.

**Enforcement:** the skill's example files have been audited for this discipline. New files should follow the conventions above and run a gitleaks-style scan to catch accidents.

## 16. What this file does not cover

- **Field shapes credentials populate** → `values-yaml.md` § 8.
- **Discovery questionnaire that selects a credential pattern at deployment time** → `values-authoring.md` § 3.8.
- **TLS / cert-manager / custom CA authoring** → `tls-and-certs.md`.
- **License key procurement** → out of scope; contact EyeLevel / GroundX.
- **Cloud IAM policy authoring for IRSA / WI / WIF** → out of scope; consult the cloud provider's documentation.
- **Sealed-secrets controller install, ESO install, helm-secrets plugin install** → out of scope; consult upstream documentation.
- **Architectural rationale for the credential surface** → `groundx-architecture/references/identity-and-trust.md`.
- **Architectural multi-tenancy enforcement** → `groundx-architecture/references/multi-tenancy.md`.
