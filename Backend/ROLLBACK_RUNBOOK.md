# Rollback Runbook

## Scope

This runbook covers manual rollback of the production Docker deployment defined in
[`docker-compose.prod.yml`](/c:/Users/Osman.saleh/OneDrive/Cartella%20progetto/product-finder%202/Backend/docker-compose.prod.yml).

Use it when:
- a deploy completes but `/health` fails
- the frontend is unreachable after deploy
- a regression is severe enough that reverting code is safer than hot-fixing

## Preconditions

- SSH access to the production server
- access to the deployed app directory
- the previous known-good git commit or release tag
- the production `.env` file already present on the server

## Quick Checks Before Rollback

1. Confirm the failure is real:
   - `docker compose -f docker-compose.prod.yml ps`
   - `docker compose -f docker-compose.prod.yml logs app --tail=100`
   - `docker compose -f docker-compose.prod.yml logs caddy --tail=100`
   - `python3 scripts/check_health.py http://127.0.0.1/health --expect-backend postgres`
2. If the issue is only transient startup delay, wait for the app import to finish before rolling back.
3. If the issue is clearly a bad release, continue below.

## Rollback Procedure

1. Connect to the server and enter the deployed app directory.
2. Return the codebase to the previous known-good revision:

```bash
git fetch --all --tags
git checkout <known-good-tag-or-commit>
```

3. Recreate the stack with the previous code:

```bash
chmod +x scripts/deploy_prod.sh
./scripts/deploy_prod.sh "$(pwd)"
```

4. Validate rollback:
   - `docker compose -f docker-compose.prod.yml ps`
   - `python3 scripts/check_health.py http://127.0.0.1/health --expect-backend postgres`
   - open `https://<APP_DOMAIN>/frontend/`
   - verify login and one critical search flow

## If the Problem Is Data-Related

If code rollback is not enough and the database must be restored:

1. Identify the correct `.sql` backup.
2. Export the current damaged state before overwriting anything.
3. Restore with:

```powershell
$env:PGPASSWORD="your-postgres-password"
.\scripts\restore_postgres_backup.ps1 -BackupFile .\backups\<backup-file>.sql
```

4. Re-run the post-restore validation:
   - `/health`
   - login
   - saved quote retrieval
   - one datasheet/download path

## After Rollback

- record the failed release ref
- record the symptom and the first failing check
- keep the relevant `app` and `caddy` logs
- do not redeploy until the failure cause is understood
