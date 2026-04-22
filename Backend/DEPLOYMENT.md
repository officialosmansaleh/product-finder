# Deployment

## Local Docker

1. Copy [`.env.docker.example`](/c:/Users/Osman.saleh/OneDrive/Cartella%20progetto/product-finder%202/Backend/.env.docker.example) to `.env`.
2. Set at least:
   - `OPENAI_API_KEY`
   - `AUTH_JWT_SECRET`
   - `ADMIN_BOOTSTRAP_EMAIL`
   - `ADMIN_BOOTSTRAP_PASSWORD`
   - `ADMIN_BOOTSTRAP_NAME`
   - `POSTGRES_PASSWORD`
3. Start the stack:

```bash
docker compose up --build
```

4. Open:
   - Finder: `http://localhost:8000/frontend/`
   - Tools: `http://localhost:8000/frontend/tools.html`
   - Docs: `http://localhost:8000/docs`

5. Optional health check:

```bash
curl http://localhost:8000/health
```

## Notes

- The application imports the PIM dataset at startup, so the first boot can take longer.
- For production, replace inline secrets in `.env` with proper secret management.
- The admin panel now includes a DB-backed Settings area for maintainable runtime/admin values and masked secret rotation support.
- Deployment/infrastructure-sensitive values such as `APP_DOMAIN`, `POSTGRES_PASSWORD`, and some security settings may still require restart or redeploy even if updated from the admin UI.
- Password reset is implemented in the app; real email delivery depends on SMTP configuration, which can now be entered from the admin Settings panel once IT provides the Microsoft 365 mailbox details.
- External SMTP coordination is tracked in [ASK_IT_TODO.md](/c:/Users/Osman.saleh/OneDrive/Cartella%20progetto/product-finder%202/Backend/ASK_IT_TODO.md).
- Inside Docker Compose, the app now forces `PRODUCT_DATABASE_URL` and `AUTH_DATABASE_URL` to use the `postgres` service host. This avoids the common mistake of leaving `localhost` in `.env`.
- If PostgreSQL runs outside Docker, point `PRODUCT_DATABASE_URL` and `AUTH_DATABASE_URL` to the external host and remove the `postgres` service from the compose file.
- Healthchecks are enabled for both `postgres` and `app`, so startup order is more reliable.
- Verified locally on March 20, 2026:
  - `docker compose up -d --build` completed successfully
  - `/health` returned `200 OK`
  - the app reported `database_backend: "postgres"` with product catalog loaded
  - anonymous public catalog mode and authenticated quote/export flows were validated in the browser
- Restart recovery was also verified locally:
  - `docker compose down` followed by `docker compose up -d --build`
  - approved users and saved quotes were still present after restart

## Production Docker

1. Copy [`.env.prod.example`](/c:/Users/Osman.saleh/OneDrive/Cartella%20progetto/product-finder%202/Backend/.env.prod.example) to `.env`.
2. Set at least:
   - `APP_DOMAIN`
   - `ACME_EMAIL`
   - `OPENAI_API_KEY`
   - `AUTH_JWT_SECRET`
   - `ADMIN_BOOTSTRAP_EMAIL`
   - `ADMIN_BOOTSTRAP_PASSWORD`
   - `ADMIN_BOOTSTRAP_NAME`
   - `POSTGRES_PASSWORD`
3. Make sure your DNS already points `APP_DOMAIN` to the server public IP.
4. Start the production stack:

```bash
docker compose -f docker-compose.prod.yml up -d --build
```

5. The reverse proxy will terminate HTTPS automatically through Caddy and forward traffic to the FastAPI app.

## Deployment Automation

- GitHub Actions deployment workflow: [backend-deploy-prod.yml](/c:/Users/Osman.saleh/OneDrive/Cartella%20progetto/product-finder%202/.github/workflows/backend-deploy-prod.yml)
- Server-side deploy helper: [deploy_prod.sh](/c:/Users/Osman.saleh/OneDrive/Cartella%20progetto/product-finder%202/Backend/scripts/deploy_prod.sh)
- Shared health probe: [check_health.py](/c:/Users/Osman.saleh/OneDrive/Cartella%20progetto/product-finder%202/Backend/scripts/check_health.py)

Required GitHub environment/repository secrets:
- `PROD_HOST`
- `PROD_USER`
- `PROD_SSH_KEY`
- `PROD_PORT` (optional, defaults to `22`)
- `PROD_APP_PATH`

Recommended flow:
1. create/update production `.env` on the server
2. run the `Backend Deploy Production` workflow manually
3. let the workflow copy `Backend/` to the server and execute `./scripts/deploy_prod.sh`
4. confirm the post-deploy healthcheck succeeds

## Monitoring And Alerts

- Scheduled monitor workflow: [backend-monitor.yml](/c:/Users/Osman.saleh/OneDrive/Cartella%20progetto/product-finder%202/.github/workflows/backend-monitor.yml)
- Probe script reused by monitor and deploy: [check_health.py](/c:/Users/Osman.saleh/OneDrive/Cartella%20progetto/product-finder%202/Backend/scripts/check_health.py)

Required secrets:
- `HEALTHCHECK_URL`

Optional secret:
- `ALERT_WEBHOOK_URL`

Current behavior:
- runs every 15 minutes
- fails the workflow if `/health` is not reachable or reports bad status
- sends a webhook notification on failure when `ALERT_WEBHOOK_URL` is configured

## Backups

- A first backup helper is available at [`scripts/backup_postgres.ps1`](/c:/Users/Osman.saleh/OneDrive/Cartella%20progetto/product-finder%202/Backend/scripts/backup_postgres.ps1).
- A restore helper is available at [`scripts/restore_postgres_backup.ps1`](/c:/Users/Osman.saleh/OneDrive/Cartella%20progetto/product-finder%202/Backend/scripts/restore_postgres_backup.ps1).
- Example usage:

```powershell
.\scripts\backup_postgres.ps1
```

- It creates timestamped `.sql` dumps under `Backend/backups/`.
- Restore example:

```powershell
$env:PGPASSWORD="your-postgres-password"
.\scripts\restore_postgres_backup.ps1 -BackupFile .\backups\productfinder-local-YYYYMMDD-HHMMSS.sql
```

- Verified locally on March 20, 2026 with a real dump/restore check:
  - source DB `productfinder`
  - restored DB `productfinder_restore_check`
  - `products = 6104`
  - `users = 3`
  - `saved_quotes = 2`

## Current Status

- Docker is installed on this machine and available from the terminal.
- Verified locally on March 20, 2026:
  - `docker --version` -> `Docker version 29.2.1, build a5c7197`
  - `docker compose version` -> `Docker Compose version v5.1.0`
- The local compose stack has been executed successfully and is usable for day-to-day local validation.
- Local operational checks are complete:
  - healthchecks verified
  - Docker restart persistence verified
  - backup and restore verified
- A production-oriented stack is also prepared with HTTPS reverse proxy and reusable Postgres backup scripts.
- The main remaining deployment gap is the first real server rollout with DNS and HTTPS on the final host.

## CI

- A GitHub Actions CI pipeline is available at [backend-ci.yml](/c:/Users/Osman.saleh/OneDrive/Cartella%20progetto/product-finder%202/.github/workflows/backend-ci.yml).
- It runs Python dependency installation, backend compile checks, `pytest`, and a Docker image build.
- The workflow triggers on backend pushes, pull requests, and manual runs.

## Rollback

- Formal rollback runbook: [ROLLBACK_RUNBOOK.md](/c:/Users/Osman.saleh/OneDrive/Cartella%20progetto/product-finder%202/Backend/ROLLBACK_RUNBOOK.md)
