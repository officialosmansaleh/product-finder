# Railway Deploy

This repository can be deployed to Railway directly from the repo root.

## Recommended path for this project

Use the Railway CLI from the local workspace if you want to deploy the latest local code immediately.

Why:
- the local repo can be pushed and versioned through GitHub
- you may still want CLI deploys when testing local, not-yet-pushed changes

## What Railway should run

- Build method: Dockerfile
- Dockerfile path: repo root `Dockerfile`
- Health check path: `/health`

The root Dockerfile copies the `Backend/` app into the container and starts FastAPI on `0.0.0.0:$PORT`, which is what Railway expects.

## Required Railway variables

Set these in the Railway service:

- `OPENAI_API_KEY`
- `AUTH_JWT_SECRET`
- `ADMIN_BOOTSTRAP_EMAIL`
- `ADMIN_BOOTSTRAP_PASSWORD`
- `ADMIN_BOOTSTRAP_NAME`

## Database options

### Option A: Fastest first deploy

Use SQLite inside the container:

- `USE_SQLITE=1`
- `PRODUCT_DB_BACKEND=sqlite`
- `PRODUCT_DB_PATH=data/products.db`
- `AUTH_DB_PATH=data/auth.db`
- `AUTH_COOKIE_SECURE=true`

Note:
- this is okay for a first smoke test
- Railway deployments use ephemeral container filesystems, so SQLite is not a good long-term production choice unless you add a persistent volume

### Option B: Recommended production setup

Add a Railway PostgreSQL service and set:

- `USE_SQLITE=0`
- `PRODUCT_DB_BACKEND=postgres`
- `PRODUCT_DATABASE_URL=${{Postgres.DATABASE_URL}}`
- `AUTH_DATABASE_URL=${{Postgres.DATABASE_URL}}`
- `RATE_LIMIT_DATABASE_URL=${{Postgres.DATABASE_URL}}`
- `AUTH_COOKIE_SECURE=true`

If you expose the app on your production domain, also set:

- `CORS_ALLOWED_ORIGINS=https://laiting.disano.it`

## Optional variables

- `PIM_XLSX=data/PIM_20260324.xlsx`
- `FAMILY_MAP_XLSX=data/family_map.xlsx`
- `ENABLE_DEBUG_ENDPOINTS=false`
- `AUTH_COOKIE_SAMESITE=lax`
- `IMAGE_PARSE_MAX_BYTES=8388608`
- `PDF_PARSE_MAX_UPLOAD_BYTES=10485760`

## CLI flow

1. Install the CLI:

```powershell
npm install -g @railway/cli
```

2. Log in:

```powershell
railway login
```

3. From the repo root, create or link a project:

```powershell
railway init
```

4. Set the variables in Railway.

5. Deploy:

```powershell
railway up
```

6. Add the public domain in Railway and test:

```text
https://laiting.disano.it/health
https://laiting.disano.it/frontend/
```

## First checks after deploy

- `/health` returns `200`
- `/frontend/` loads
- admin bootstrap login works
- search returns products

## Important note about data

This app imports product files at startup, so the first Railway boot can take longer than a simple API.
