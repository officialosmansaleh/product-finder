# Admin Settings Reference

Questa tabella riassume le impostazioni esposte nel pannello admin `Settings` e il loro comportamento operativo.

| Impostazione | Modificabile da admin | Effetto immediato | Richiede restart/redeploy | Cautela |
|---|---|---:|---:|---|
| `OPENAI_API_KEY` | Sì | Sì | No | Media |
| `DISANO_STORE_IDS` | Sì | Sì | No | Bassa |
| `DISANO_LANG_ID` | Sì | Sì | No | Bassa |
| `ENABLE_DEBUG_ENDPOINTS` | Sì | Sì | No | Alta |
| `CORS_ALLOWED_ORIGINS` | Sì | No | Sì | Alta |
| `AUTH_TOKEN_EXPIRE_MINUTES` | Sì | Sì | No | Media |
| `AUTH_REFRESH_TOKEN_EXPIRE_DAYS` | Sì | Sì | No | Media |
| `AUTH_COOKIE_SECURE` | Sì | Sì | No | Media |
| `AUTH_COOKIE_SAMESITE` | Sì | Sì | No | Media |
| `AUTH_JWT_SECRET` | Sì | No | Sì | Molto alta |
| `ADMIN_BOOTSTRAP_EMAIL` | Sì | Sì | No | Media |
| `ADMIN_BOOTSTRAP_NAME` | Sì | Sì | No | Bassa |
| `ADMIN_BOOTSTRAP_PASSWORD` | Sì | Sì | No | Alta |
| `ADMIN_TOKEN` | Sì | Sì | No | Alta |
| `SMTP_HOST` | Sì | Sì | No | Media |
| `SMTP_PORT` | Sì | Sì | No | Bassa |
| `SMTP_USERNAME` | Sì | Sì | No | Media |
| `SMTP_PASSWORD` | Sì | Sì | No | Alta |
| `SMTP_FROM_EMAIL` | Sì | Sì | No | Bassa |
| `PIM_XLSX` | Sì | No | Sì | Media |
| `FAMILY_MAP_XLSX` | Sì | No | Sì | Media |
| `PIM_VERBOSE` | Sì | Sì | No | Bassa |
| `RATE_LIMIT_STORE` | Sì | Sì | No | Media |
| `RATE_LIMIT_DATABASE_URL` | Sì | Sì | No | Alta |
| `APP_DOMAIN` | Sì | No | Sì | Molto alta |
| `ACME_EMAIL` | Sì | No | Sì | Media |
| `POSTGRES_PASSWORD` | Sì | No | Sì | Molto alta |

## Regola pratica

- `Effetto immediato`: il backend usa il nuovo valore subito o quasi subito.
- `Restart/redeploy`: il valore può essere salvato dal pannello, ma serve riavvio app o redeploy per effetto completo.
- `Cautela alta/molto alta`: modificare solo sapendo l'impatto su sicurezza, login, dominio o database.

## Prime impostazioni utili da configurare

Per l'operatività quotidiana, le impostazioni più utili da configurare dal pannello sono:

- `SMTP_HOST`
- `SMTP_PORT`
- `SMTP_USERNAME`
- `SMTP_PASSWORD`
- `SMTP_FROM_EMAIL`
- `OPENAI_API_KEY`
- `AUTH_TOKEN_EXPIRE_MINUTES`
- `AUTH_REFRESH_TOKEN_EXPIRE_DAYS`

## Impostazioni da toccare solo con attenzione

- `POSTGRES_PASSWORD`
- `AUTH_JWT_SECRET`
- `APP_DOMAIN`
- `CORS_ALLOWED_ORIGINS`
- `ENABLE_DEBUG_ENDPOINTS`
