# Render + Neon deployment

This release is a pilot foundation. Complete the production gates in REQUIREMENTS.md before using identifiable health data. No Render services or Neon databases are provisioned by this repository.

## Database

1. Create a managed PostgreSQL database in an approved region. Evaluate residency, health-data governance, connection limits and provider terms before use.
2. Copy the direct connection string for Alembic migration jobs and the appropriate pooled connection string for the API. Require TLS (`sslmode=require`). Store them as Render secrets, never frontend variables or committed files.
3. Use a separate database for each development, staging and production environment. The same production database can host multiple organizations, with API organization authorization on every operational access.

## Backend on Render

Create a Python web service from this repository, root directory `backend`.

- Build: `pip install -r requirements.txt`
- Pre-deploy: `python -m alembic upgrade head && python -m app.seed`
- Start: `python -m uvicorn app.main:app --host 0.0.0.0 --port $PORT`
- Health check: `/health`
- Environment: `DATABASE_URL`, `JWT_SECRET`, `SETUP_TOKEN`, `ENVIRONMENT`, `CORS_ORIGINS`, `FRONTEND_URL`; optional SMTP settings as documented in `.env.example`.
- Generate independent random secrets: `python -c 'import secrets; print(secrets.token_urlsafe(48))'`. Do not paste secrets into public issues or logs.
- Set `ENVIRONMENT=staging` while validating, and `production` only after release gates pass. Production rejects default JWT secrets, missing setup token, SQLite and non-HTTPS CORS origins.
- Supply `CORS_ORIGINS` as an exact comma-separated allowlist. No wildcard credential access.
- On plans without pre-deploy commands, run migrations and seed once through an authorized Render shell before exposing the service. Never run schema creation at API import time.
- Configure a distributed API gateway rate limiter before scaling to multiple workers/instances. The built-in one-minute limiter is process-local and is not a multi-instance protection guarantee.

## Frontend on Render

Create a static site, root directory `frontend`.

- Build: `npm ci && npm run build`
- Publish directory: `dist`
- Set `VITE_API_URL=https://YOUR-API.onrender.com` at build time. This is a public URL, never a secret.
- Add rewrite: `/*` → `/index.html` (rewrite, not redirect).
- Configure `X-Content-Type-Options: nosniff`, `Referrer-Policy: no-referrer`, `X-Frame-Options: DENY`, and a deployment-specific CSP allowing only approved API, static asset, font and map providers.
- Add the frontend origin to backend CORS and `FRONTEND_URL`.
- HTTPS is required for service-worker installation. The service worker caches static bundled assets only; API responses and health records are never cached.

## Organization onboarding

1. Visit the frontend, select **Set up your organization**.
2. Use the operator-issued setup token. This token is entered once and not persisted in browser storage.
3. Choose region and searchable MMDA; enter health sub-districts and facilities, administrator and programmes.
4. After setup, add locally approved indicators (including definitions and approval references). Add communities and scoped staff accounts; import facilities through the validated CSV/XLSX workflow.
5. Passwords and refresh tokens are never written to browser localStorage. Refresh tokens are rotated and stored only in memory; reload requires sign-in. Logout invalidates every server session for that account.
6. Configure SMTP before relying on password-reset email. Reset responses do not reveal whether an account exists. Reset links expire in 30 minutes and invalidate existing sessions.

## National/regional roles and registry maintenance

Provision higher-scope roles only from the restricted backend shell. Every district must be explicitly assigned. Technical System Administrator membership grants status/audit access, not client access.

```sh
python -m app.admin grant-membership --email officer@example.org --name 'Authorized Officer' --organization ORGANIZATION_UUID --role 'Regional Nutrition Officer' --operator CHANGE_REFERENCE
python -m app.admin add-programme --code approved-programme --name 'Approved Programme' --operator CHANGE_REFERENCE
python -m app.seed --directory /approved/versioned/master-data --operator CHANGE_REFERENCE
```

National/regional `/api/aggregate/dashboard` pools reporting counts only over explicit memberships. Standardized national indicator IDs, suppression rules and cross-district indicator comparability remain rollout gates.

## Docker

Backend and frontend Dockerfiles are included. Frontend `VITE_API_URL` is a build argument. Nginx runs without root on port 8080. For local Compose, set `POSTGRES_PASSWORD` and create `backend/.env` using the internal host `db`. Run migrations and seed with `docker compose run --rm api python -m alembic upgrade head` and `docker compose run --rm api python -m app.seed` before opening the app.

## Verification

After deployment: verify `/health`, migrate/seed, confirm all 16 regions and 261 MMDA rows, test setup, sign-in, a second organization access denial, facility role scope, report approval/locking/amendment, sign-out, password reset email delivery and mobile operation. Test database restore independently. Do not load real client data until acceptance and governance approvals are complete.
