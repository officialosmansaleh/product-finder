# product-finder
Disano smart product finder

## API key setup (backend only)
1. Copy `.env.example` to `.env`
2. Set `OPENAI_API_KEY` in `Backend/.env`
3. Start backend normally

Notes:
- Do not put API keys in frontend files.
- Keep `.env` out of git.

## Auth

- The frontend supports OAuth2/OIDC SSO, plus optional local `signup`, `login`, and `logout` fallback from the page header.
- For Microsoft Entra ID SSO set:
  - `OAUTH2_ENABLED=true`
  - `OAUTH2_TENANT_ID`
  - `OAUTH2_CLIENT_ID`
  - `OAUTH2_CLIENT_SECRET`
  - `OAUTH2_REDIRECT_URI=https://<app-domain>/auth/oauth/callback`
  - `OAUTH2_ALLOWED_DOMAINS=disano.it`
- In production, set `LOCAL_LOGIN_ENABLED=false` and `LOCAL_SIGNUP_ENABLED=false` once SSO is validated.
- New accounts are created as `pending` and must be approved by an admin.
- Configure bootstrap admin credentials in `Backend/.env` with:
  - `ADMIN_BOOTSTRAP_EMAIL`
  - `ADMIN_BOOTSTRAP_PASSWORD`
  - `ADMIN_BOOTSTRAP_NAME`
- Admin Panel documentation is available in `Backend/ADMIN_PANEL_DOCUMENTATION.md`.
- Admin settings reference is available in `Backend/ADMIN_SETTINGS_REFERENCE.md`.
- Italian IT handover guide for Admin settings is available in `Backend/ADMIN_SETTINGS_IT_GUIDE_IT.md`.
- Italian user manual for normal users, IT, and Marketing is available in `Backend/Documentation/USER_MANUAL_IT_MARKETING_USER_IT.md`.

## PostgreSQL

- The product catalog requires PostgreSQL. SQLite is no longer a supported product-catalog runtime.
- Auth can also run on PostgreSQL, or keep its local fallback if `AUTH_DATABASE_URL` is not configured.
- Set:
  - `PRODUCT_DB_BACKEND=postgres`
  - `PRODUCT_DATABASE_URL=postgresql://...`
  - `AUTH_DATABASE_URL=postgresql://...`

## Docker

- Baseline container files are included:
  - `Backend/Dockerfile`
  - `Backend/docker-compose.yml`
  - `Backend/DEPLOYMENT.md`
