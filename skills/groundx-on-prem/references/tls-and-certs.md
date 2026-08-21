# TLS, Certificates, and Custom CAs

This file documents **how TLS and certificates fit into a GroundX deployment**: ingress TLS, backing-service TLS, OpenShift Route TLS, and the inert cluster-wide schema field.

The chart **does not** own the TLS authoring lifecycle. It exposes per-Ingress TLS references and selected backing-service trust values, but no cluster-wide certificate or general CA-bundle mount. This file describes the prereqs the deployer is responsible for.

For backing-service-specific TLS details (DB root CAs, OpenSearch certs), route to `services-prereqs.md` and `values-yaml.md` § 4. For the Secret-handling patterns that hold TLS material, route to `credentials.md` § 8.

## 1. TLS surfaces

A GroundX deployment touches TLS in four distinct ways. The same `tls` word means different things at each surface.

| Surface | What it protects | Who provisions the cert | Field path |
| --- | --- | --- | --- |
| **1. Ingress TLS** | External-client → cluster traffic. The TLS terminates at the ingress controller (ALB / NGINX / AKS AGIC). | Deployer (or cert-manager) provisions the cert Secret. The Ingress controller references it. | `<microservice>.ingress.tls[]` per chart-ingress block. |
| **2. Cluster-wide / in-cluster TLS** | Service-to-service inside the cluster. | Chart 0.2.7 has no supported cluster-wide TLS switch. Use a service mesh or another customer-controlled network layer. | `cluster.tls.existingSecret` is accepted by the schema but does not change rendered resources or mount a Secret. |
| **3. Backing-service TLS** | The application's outbound connection to the relational DB / OpenSearch / Redis / Kafka / object store. The cert lives outside the chart (in the backing service). | The backing-service operator or cloud provider (AWS RDS, Azure Database for MySQL, AWS OpenSearch). | `db.existing.rootCerts` / `db.rootCerts` / per-service equivalents. |
| **4. OpenShift Route TLS** | External traffic via OpenShift `Route` resources instead of standard `Ingress`. The chart auto-terminates at edge with `insecureEdgeTerminationPolicy: Redirect`. | OpenShift's certificate-management story (typically OpenShift's auto-managed router cert, optionally cert-manager). | Implicit — set `<microservice>.serviceType: Route` and the chart emits the Route with TLS termination. |

These are independent. A deployment can run cert-manager-issued ingress TLS, mTLS-disabled in-cluster, RDS-managed DB TLS, and have no Routes (non-OpenShift cluster). Or it can run pure OpenShift Routes everywhere. Pick the pattern per surface.

Security posture note: the chart supports the TLS surfaces above, but does not make
mutual TLS a native API requirement. If a customer requires mTLS, enforce it at the
ingress, service mesh, API gateway, Kafka/backing-service client configuration, or other
customer-controlled network layer.

## 2. Surface 1 — Ingress TLS

Every chart-managed Ingress (`groundx`, `layout.api`, `layoutWebhook`, `ranker.api`, `summary.api`, `extract.api`, `workspace.api`, `file`) supports the standard Kubernetes Ingress TLS shape:

```yaml
groundx:
  ingress:
    enabled: true
    ingressClassName: alb           # or nginx, azure-application-gateway, etc.
    hostName: api.mycorp.example.com
    tls:
      - hosts: [api.mycorp.example.com]
        secretName: groundx-tls-cert
```

The `secretName` references a `kubernetes.io/tls` Secret that **must already exist** in the GroundX namespace before the chart installs (or before the Ingress is reconciled).

### 2.1 Pattern A — cert-manager + Let's Encrypt (in-cluster ACME)

Most deployments. cert-manager is installed cluster-wide once and issues per-ingress certs from an `Issuer` or `ClusterIssuer`.

Setup outline:

1. Install cert-manager: `helm install cert-manager jetstack/cert-manager -n cert-manager --create-namespace`.
2. Create a `ClusterIssuer` for Let's Encrypt (HTTP-01 or DNS-01 solver).
3. Annotate the chart's `Ingress` to trigger cert-manager:
   ```yaml
   groundx:
     ingress:
       enabled: true
       annotations:
         cert-manager.io/cluster-issuer: letsencrypt-prod
       hostName: api.mycorp.example.com
       tls:
         - hosts: [api.mycorp.example.com]
           secretName: groundx-tls-cert    # cert-manager creates this
   ```
4. cert-manager watches the Ingress, requests a cert from Let's Encrypt, creates the `groundx-tls-cert` Secret. Rotation is automatic at the configured cert lifecycle.

### 2.2 Pattern B — cert-manager + private CA / corporate PKI

Same as Pattern A, but the `ClusterIssuer` points at a corporate CA (Vault PKI, Smallstep, HashiCorp Boundary, etc.) instead of Let's Encrypt. Useful for internal deployments where Let's Encrypt isn't reachable.

### 2.3 Pattern C — manually-issued static cert

For air-gapped deployments or one-off TLS:

```sh
kubectl create secret tls groundx-tls-cert \
  --cert=path/to/cert.crt --key=path/to/cert.key \
  -n eyelevel
```

Then reference it in `<microservice>.ingress.tls` as in § 2. Rotation is manual: re-`create` (or `apply` with `--dry-run=client -o yaml`) when the cert expires.

### 2.4 Pattern D — TLS terminated at the LoadBalancer

When using cloud-provider TLS termination (ACM cert on an AWS ALB, Application Gateway listener on AKS), the chart's Ingress doesn't manage the cert — the cloud provider does. Use the ingress controller's annotations to attach the cloud cert:

```yaml
groundx:
  ingress:
    enabled: true
    ingressClassName: alb
    annotations:
      alb.ingress.kubernetes.io/certificate-arn: arn:aws:acm:<region>:<account>:certificate/<id>
      alb.ingress.kubernetes.io/listen-ports: '[{"HTTPS":443}]'
      alb.ingress.kubernetes.io/scheme: internet-facing
```

No `tls:` block needed in this case; the ACM cert is attached at the AWS layer.

## 3. Surface 2: Cluster-wide / in-cluster TLS

Chart 0.2.7 accepts `cluster.tls.existingSecret` in the schema, but no template reads it. No workload mounts the named Secret, and setting it does not change rendered resources.

Do not use this field to satisfy an in-cluster TLS requirement. Enforce service-to-service TLS with a service mesh, API gateway, or another customer-controlled network layer. Configure ingress and backing-service trust through their supported fields in §§ 2 and 4.

### 3.2 Custom CA bundle

If the cluster uses a custom CA that issues *external* certs (e.g., a corporate Vault PKI), GroundX pods may need to trust that CA for outbound calls (to backing services, LLM endpoints, etc.). The chart does not have a single `customCABundle` field — instead:

- For DB outbound TLS: set `db.existing.rootCerts` to the PEM bundle (see § 4.1).
- For other outbound destinations: chart 0.2.7 has no general CA-bundle mount. Use certificates already trusted by the workload image, a service mesh or proxy, or a reviewed chart change.

## 4. Surface 3 — Backing-service TLS

The chart connects to five backing services. Each has its own TLS story.

### 4.1 Relational DB (MySQL / RDS / Azure Database)

When the DB is external (Mode 1 / Mode 3) and requires TLS:

```yaml
db:
  existing:
    ro: <rds-endpoint>.<region>.rds.amazonaws.com
    rw: <rds-endpoint>.<region>.rds.amazonaws.com
    port: 3306
    rootCerts: |
      -----BEGIN CERTIFICATE-----
      <root CA PEM bundle>
      -----END CERTIFICATE-----
```

**When required:** AWS RDS / Azure Database for MySQL with `require_secure_transport=ON`. Without `rootCerts`, the connection fails at TLS handshake.

**Where to get the cert:**
- AWS RDS: download from [Amazon Trust Services](https://docs.aws.amazon.com/AmazonRDS/latest/UserGuide/UsingWithRDS.SSL.html). Use the regional or global root CA bundle.
- Azure Database for MySQL: download the DigiCert Global Root G2 PEM (canonical in `values.aks.yaml` of the upstream repo).
- Google Cloud SQL: download from the Cloud SQL instance's "Connections" tab.

For bundled in-cluster Percona (Mode 2), the chart's `db.rootCerts` top-level field accepts a TLS root CA used to verify the bundled DB's cert. This is rarely needed for Mode 2 because the chart's DB cert is trusted by chart-managed pods automatically.

### 4.2 OpenSearch / Retrieval DB

When OpenSearch is external (Mode 1 / Mode 3) and uses HTTPS:

- The chart connects via `search.existing.url` (HTTPS URL).
- Chart 0.2.7 has no OpenSearch CA-bundle field or general Secret-file mount. A self-signed or private-CA endpoint therefore needs trust supplied outside the current values surface, such as the workload image, a service mesh or proxy, or a reviewed chart change.
- For AWS OpenSearch managed, the public AWS root CA is already trusted by the chart's pods; no additional setup needed.

### 4.3 Cache / Redis

When Redis is external (Mode 1 / Mode 3) with TLS:

```yaml
cache:
  existing:
    addr: <redis-endpoint>.example.com
    port: 6380
    ssl: true
```

`cache.existing.ssl: true` triggers the application's TLS dial. For self-signed Redis, mount the CA bundle (same pattern as § 4.2). For AWS ElastiCache or Azure Cache for Redis, the public CA is already trusted.

### 4.4 Kafka / Stream

When Kafka is external with TLS:

```yaml
stream:
  existing:
    domain: <kafka-broker>.example.com
    port: 9093
```

The chart's Kafka client connects to the configured broker and port, but chart 0.2.7 has no Kafka keystore, truststore, or general Secret-file mount. Private-CA TLS, mTLS, and SASL/SCRAM therefore require an application-supported environment contract verified separately, a service mesh or proxy, or a reviewed chart change.

For SQS (the alternative queue backend), TLS is implicit (HTTPS endpoint).

### 4.5 Object store (S3 / MinIO)

S3 (Mode 3) uses HTTPS by default; the public AWS root CA is trusted by the chart's pods. No deployer action needed.

For external MinIO (Mode 1) with self-signed / custom-CA TLS, mount the CA bundle (same pattern as § 4.2).

For bundled in-cluster MinIO (Mode 2), traffic stays inside the cluster — TLS is optional and rarely set.

## 5. Surface 4 — OpenShift Route TLS

On OpenShift, set `<microservice>.serviceType: Route` and the chart emits a `Route` resource with TLS termination:

```yaml
spec:
  tls:
    insecureEdgeTerminationPolicy: Redirect
    termination: edge
```

(Source: `src/groundx/templates/_helpers/elements/interface.tpl` line 61.)

**Edge termination:** the OpenShift router terminates TLS at the edge and routes plain HTTP to the chart's pods inside the cluster. The router uses OpenShift's default wildcard cert unless the Route specifies its own.

**Override the cert:** to use a custom cert per Route, the deployer adds the cert fields to the Route resource via OpenShift's `oc patch route` after install. The chart does not expose per-microservice Route cert overrides in values.yaml.

**Redirect HTTP → HTTPS:** baked in via `insecureEdgeTerminationPolicy: Redirect`. Clients that hit the HTTP endpoint get a 302 to HTTPS.

## 6. Rotation

| Surface | Rotation source | Procedure |
| --- | --- | --- |
| Ingress TLS (cert-manager) | Automatic | cert-manager re-issues before expiry; updates the Secret in place. Ingress controllers (NGINX, ALB) pick up the new cert automatically. No pod restart needed. |
| Ingress TLS (manual) | Deployer | `kubectl create secret tls --dry-run=client -o yaml ... | kubectl apply -f -` to replace the Secret. Ingress controller picks up. |
| Cluster-wide TLS | Customer-controlled network layer | Follow the service mesh or gateway rotation procedure. `cluster.tls.existingSecret` does not mount or rotate certificates. |
| DB rootCerts | AWS / Azure / GCP (per-provider rotation) | When the cloud provider rotates the root CA (rare, on multi-year cadence), update `db.existing.rootCerts` in values.yaml and re-apply: `helm upgrade --install groundx ./src/groundx -f values.<env>.yaml`. Restart application pods. |
| OpenShift Route cert | OpenShift router | OpenShift manages the router's wildcard cert. Per-Route certs are deployer-managed. |
| Backing-service CA bundles | Operator or cloud provider | Update the supported per-service trust value or the customer-controlled trust layer, then roll affected application pods when that mechanism loads trust at startup. |

Ingress-controller-managed Secret rotation follows the controller's behavior. Application trust material supplied through values or a customer-controlled mount generally requires rolling the affected pods unless that mechanism documents live reload.

## 7. Common mistakes

| Mistake | What goes wrong | Fix |
| --- | --- | --- |
| Set `cluster.tls.existingSecret` expecting cluster-wide TLS | The value is accepted but has no rendered effect, leaving the requirement unmet. | Configure a service mesh or another customer-controlled TLS layer. |
| Use Let's Encrypt with HTTP-01 solver on an internal-only LoadBalancer | ACME challenge can't reach the LB; cert issuance fails. | Switch to DNS-01 solver, or use a private CA via cert-manager. |
| Forget `db.existing.rootCerts` on RDS with `require_secure_transport=ON` | App pods fail to connect to DB | Set `db.existing.rootCerts` to the RDS root CA PEM (see § 4.1). |
| Rotate application trust material without reloading affected pods | Pods can continue using the old trust state | Follow the supplying mechanism's reload procedure; roll the affected deployment when it loads trust only at startup. |
| Mix Ingress TLS + LoadBalancer TLS termination | TLS double-termination or hostname mismatch | Pick one: either chart `Ingress` with cert references, or cloud LB with ACM/Key Vault cert. Don't both. |
| Use a wildcard cert with an Ingress that requires SAN matching | TLS handshake fails | Ensure the cert's SAN list includes the chart's exact hostname. |
| OpenShift Route with custom cert never gets applied | The cert override has to be done via `oc patch route` post-install — the chart doesn't render it. | Apply the Route cert manually after `helm install`. |
| Forget to set `cache.existing.ssl: true` on TLS-enabled external Redis | Connection fails on TLS handshake | Set `cache.existing.ssl: true`. |

## 8. What this file does not cover

- **Generic cert-manager / Let's Encrypt setup** → consult upstream cert-manager documentation. This file only describes how the chart integrates.
- **Field-level reference for the inert `cluster.tls.existingSecret`, `<microservice>.ingress.tls[]`, and `db.existing.rootCerts`** → `values-yaml.md` § 3 (cluster), § 4.2 (db), § 5.10 (common ingress shape).
- **Secret-handling patterns that hold TLS material** (Sealed Secrets, ESO, SOPS) → `credentials.md` § 5–§ 8.
- **OpenShift Route quirks beyond TLS** → `openshift.md`.
- **NetworkPolicy authoring (which traffic to allow)** → `troubleshooting.md` and `architecture.md` § 4.
- **Architectural rationale for TLS at the trust-boundary level** → `groundx-architecture/references/identity-and-trust.md` § 6.
