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

- The frontend now supports `signup`, `login`, and `logout` from the page header.
- New accounts are created as `pending` and must be approved by an admin.
- Configure bootstrap admin credentials in `Backend/.env` with:
  - `ADMIN_BOOTSTRAP_EMAIL`
  - `ADMIN_BOOTSTRAP_PASSWORD`
  - `ADMIN_BOOTSTRAP_NAME`
- Admin Panel documentation is available in `Backend/ADMIN_PANEL_DOCUMENTATION.md`.
- Admin settings reference is available in `Backend/ADMIN_SETTINGS_REFERENCE.md`.
- Italian IT handover guide for Admin settings is available in `Backend/ADMIN_SETTINGS_IT_GUIDE_IT.md`.

## PostgreSQL

- Product catalog and auth can both run on PostgreSQL.
- Set:
  - `PRODUCT_DB_BACKEND=postgres`
  - `PRODUCT_DATABASE_URL=postgresql://...`
  - `AUTH_DATABASE_URL=postgresql://...`

## Docker

- Baseline container files are included:
  - `Backend/Dockerfile`
  - `Backend/docker-compose.yml`
  - `Backend/DEPLOYMENT.md`
