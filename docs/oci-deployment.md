# OCI production deployment (Sydney)

This runbook deploys the Next.js web app, FastAPI API, PostgreSQL, and Nginx on one Ubuntu Ampere A1 VM with Docker Compose. Nginx serves `postbridge.dev`, redirects `www.postbridge.dev`, and proxies `api.postbridge.dev`; only ports 80 and 443 are public. The Expo app uses the same API through `EXPO_PUBLIC_API_URL`. The existing AWS and local-development paths remain available.

## 1. OCI account and network

1. In **Identity & Security > Compartments**, create a compartment such as `creatormind-production`. Select **Australia East (Sydney)** (`ap-sydney-1`) before creating regional resources.
2. Create a VCN (for example `10.0.0.0/16`), public subnet (for example `10.0.1.0/24`), Internet Gateway, and route rule `0.0.0.0/0` to that gateway. Associate the subnet route table.
3. Prefer an NSG attached to the VM VNIC. Allow TCP 80 and 443 from `0.0.0.0/0`; allow TCP 22 only from the administrator's fixed source CIDR. Do not add 5432. Egress must permit DNS, HTTPS, package mirrors, OCI APIs, Meta, Google, and other integrations. Keep Ubuntu `ufw` consistent with these rules.
4. Reserve and assign a public IPv4 address so DNS does not change after VM lifecycle operations.

## 2. VM and SSH

Create an **VM.Standard.A1.Flex** ARM64 instance using a current Canonical Ubuntu 24.04 ARM64 image. The target sizing is 1 OCPU and 4 GB RAM. Keep `POSTBRIDGE_GUNICORN_WORKERS=1` at this size and monitor memory before increasing it. OCI limits and eligible shapes can change, so confirm the Console's cost estimate. Use at least a 50 GB boot volume and monitor storage.

Upload an SSH public key during creation. Keep the private key outside this repository with restrictive permissions. Connect as `ubuntu`; disable password SSH and restrict port 22 at the NSG to the administrator's IP.

## 3. Object Storage and least privilege

Create a private Standard-tier bucket in `ap-sydney-1`. Record its bucket name and tenancy Object Storage namespace. Enable retention/versioning only after considering Always Free storage consumption.

A user API signing key can use this compartment-scoped policy (replace placeholders in the Console, not in Git):

```text
Allow group <creator-app-group> to manage objects in compartment <compartment-name> where target.bucket.name='<bucket-name>'
Allow group <creator-app-group> to read buckets in compartment <compartment-name> where target.bucket.name='<bucket-name>'
```

For tighter separation, use a dynamic group and instance principal later; the current adapter supports OCI config-file or API-signing-key environment configuration. Store the private key only on the VM under an untracked `secrets/` directory, mode `0600`. The S3 Compatibility API is not used. If adopted later it needs a Customer Secret Key, uses a regional compatibility endpoint, and does not expose every native Object Storage feature.

## 4. Install Docker

Follow Docker's official Ubuntu repository instructions for ARM64, then install `docker-ce`, `docker-ce-cli`, `containerd.io`, `docker-buildx-plugin`, and `docker-compose-plugin`. Add `ubuntu` to the docker group only if accepting its root-equivalent privileges. Verify:

```sh
docker version
docker compose version
uname -m
```

`uname -m` should report `aarch64`. Images used here publish linux/arm64 variants. Python wheels/native dependencies must be rechecked whenever requirements change.

## 5. Repository and environment

Clone the repository onto the VM and change to its root. Copy the placeholder file and restrict it:

```sh
cp .env.oci.example .env.oci
chmod 600 .env.oci
mkdir -p backups secrets
chmod 700 backups secrets
```

Fill `.env.oci` without committing it. URL-encode special characters in the password embedded in `POSTBRIDGE_DATABASE_URL`. For direct variables, set `OCI_PRIVATE_KEY_HOST_PATH` to the VM-side key, keep `OCI_PRIVATE_KEY_PATH=/run/secrets/oci_api_key.pem`, and leave `OCI_CONFIG_FILE` blank. For a config file instead, set `OCI_CONFIG_HOST_PATH` and `OCI_CONFIG_FILE=/run/secrets/oci_config`. `POSTBRIDGE_ALLOWED_HOSTS` contains hostnames only; CORS entries are full origins. Passwordless login codes, hashed bearer sessions, OAuth state, encrypted provider tokens, tracked content, and predictions are persisted in PostgreSQL. Client session storage never contains Meta, Gemini, database, SMTP, or OCI credentials.

Required production variables:

- Domains/runtime: `POSTBRIDGE_WEB_DOMAIN`, `POSTBRIDGE_WWW_DOMAIN`, `POSTBRIDGE_API_DOMAIN`, `POSTBRIDGE_PUBLIC_API_URL`, `POSTBRIDGE_ENV`, `FRONTEND_BASE_URL`.
- API security: `POSTBRIDGE_ALLOWED_HOSTS`, `POSTBRIDGE_CORS_ALLOWED_ORIGINS`, `POSTBRIDGE_DATABASE_URL`, `POSTBRIDGE_MAX_UPLOAD_BYTES`, `POSTBRIDGE_AUTH_SECRET`.
- Email login: `POSTBRIDGE_SMTP_HOST`, `POSTBRIDGE_SMTP_PORT`, `POSTBRIDGE_SMTP_USERNAME`, `POSTBRIDGE_SMTP_PASSWORD`, `POSTBRIDGE_SMTP_SSL`, `POSTBRIDGE_EMAIL_FROM`. `POSTBRIDGE_LOGIN_CODE_COOLDOWN_SECONDS` defaults to 60.
- PostgreSQL: `POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD`.
- Instagram: `POSTBRIDGE_INSTAGRAM_CLIENT_ID`, `POSTBRIDGE_INSTAGRAM_CLIENT_SECRET`, `POSTBRIDGE_INSTAGRAM_REDIRECT_URI`, `POSTBRIDGE_INSTAGRAM_APP_RETURN_URI`, `POSTBRIDGE_TOKEN_ENCRYPTION_KEY`, `POSTBRIDGE_OAUTH_STATE_SECRET`.
- OCI media: `POSTBRIDGE_MEDIA_STORAGE`, `OCI_REGION`, `OCI_NAMESPACE`, `OCI_BUCKET_NAME`, plus either `OCI_CONFIG_FILE`/`OCI_CONFIG_PROFILE` or `OCI_USER_OCID`, `OCI_TENANCY_OCID`, `OCI_FINGERPRINT`, `OCI_PRIVATE_KEY_PATH`; Compose also needs `OCI_PRIVATE_KEY_HOST_PATH`.
- TLS: `CERTBOT_EMAIL`.

Feature-dependent variables are `YOUTUBE_API_KEY`, `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, `YOUTUBE_OAUTH_REDIRECT_URI`, `GEMINI_API_KEY`, and `GEMINI_MODEL`. Tuning variables are `POSTBRIDGE_RUN_MIGRATIONS`, `POSTBRIDGE_GUNICORN_WORKERS`, `POSTBRIDGE_GUNICORN_TIMEOUT`, `NGINX_CLIENT_MAX_BODY_SIZE`, `OCI_BACKUP_PREFIX`, and `BACKUP_RETENTION_DAYS`.

## 6. Build, migrate, and start

Validate and build both production images for the VM architecture:

```sh
docker compose --env-file .env.oci -f docker-compose.oci.yml config --quiet
sh scripts/oci/deploy.sh
```

The API entrypoint also migrates before Gunicorn starts, making normal restarts safe. The Next.js public API URL is embedded during the frontend image build, so changing `POSTBRIDGE_PUBLIC_API_URL` requires rebuilding `frontend`. There is currently no application-admin model or admin command, so no admin user is applicable.

## 7. DNS and HTTPS

At Porkbun, point the apex and API records to the reserved OCI IP and redirect `www` through a CNAME:

| Type | Host | Value |
| --- | --- | --- |
| A | blank | `149.118.72.50` |
| A | `api` | `149.118.72.50` |
| CNAME | `www` | `postbridge.dev` |

The production domain variables are:

```env
POSTBRIDGE_WEB_DOMAIN=postbridge.dev
POSTBRIDGE_WWW_DOMAIN=www.postbridge.dev
POSTBRIDGE_API_DOMAIN=api.postbridge.dev
POSTBRIDGE_PUBLIC_API_URL=https://api.postbridge.dev
POSTBRIDGE_ALLOWED_HOSTS=api.postbridge.dev
POSTBRIDGE_CORS_ALLOWED_ORIGINS=https://postbridge.dev
POSTBRIDGE_INSTAGRAM_REDIRECT_URI=https://api.postbridge.dev/api/instagram/connect/callback
POSTBRIDGE_INSTAGRAM_APP_RETURN_URI=postbridge://instagram-connected
FRONTEND_BASE_URL=https://postbridge.dev
```

After all three names resolve to OCI, obtain one certificate containing the apex, `www`, and `api` names. The scripts read only the required public domain and email values from `.env.oci`; they do not source passwords or other secrets into the shell:

```sh
sh scripts/oci/init-https.sh
sh scripts/oci/validate.sh
```

Schedule `scripts/oci/renew-certificates.sh` (for example twice daily using systemd timer or cron). Only Nginx publishes 80/443. Nginx sets TLS, upload limits, proxy headers, HSTS and baseline security headers.

## 8. Verification

```sh
curl --fail "https://postbridge.dev/"
curl --fail "https://api.postbridge.dev/health"
curl --head "https://www.postbridge.dev/"
docker compose --env-file .env.oci -f docker-compose.oci.yml ps
docker compose --env-file .env.oci -f docker-compose.oci.yml logs --tail=200 frontend app nginx db
```

Restart `db` and verify application data remains to test the named PostgreSQL volume. Upload a permitted screenshot below both configured size limits. For OCI media, run a non-sensitive test upload through the adapter and verify the object in the private bucket; the present application does not persist screenshot uploads, so enabling the adapter does not change that API behavior.

In Meta and Google consoles, register the exact HTTPS Instagram and YouTube callback URLs. Verify connect, denial, invalid state, reconnect, and mobile deep-link/user experience. Also verify any Instagram/X webhook URL and signing secret actually implemented by the product; this repository currently has Instagram OAuth/API routes but no X integration or inbound webhook route, so those cannot be validated here. Do not assume provider-side configuration from a healthy API.

## 9. Operations, updates, and rollback

View logs with `docker compose --env-file .env.oci -f docker-compose.oci.yml logs -f --tail=200`. Stop containers while preserving data with `docker compose --env-file .env.oci -f docker-compose.oci.yml stop`. Never use `down -v` unless intentionally deleting data.

Before update, create and verify a backup, record the current Git commit/image tag, pull the intended revision, build, migrate, and run `scripts/oci/update.sh`. For rollback, restore the previous Git revision/image, review migration downgrade safety, start the prior app, and restore a database dump only when schema/data compatibility requires it. Database restore is destructive and is intentionally confirmation-gated.

Next.js is built as a standalone, non-root production container and its immutable assets are served by that container through Nginx. Expo assets follow the mobile release workflow. The FastAPI service has no collectstatic/build step.
