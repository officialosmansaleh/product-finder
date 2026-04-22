# Product Finder - Stato Remediation rispetto al report esterno

Data aggiornamento: 21 marzo 2026

## Obiettivo

Questo documento traccia lo stato reale delle attività rispetto al report sintetico:

`ProductFinder Disano – Refactoring & Cloud Deployment (Summary)`

Scopo del documento:
- distinguere ciò che è stato chiuso da ciò che è solo parziale
- collegare ogni finding a fix concrete nel codice
- raccogliere evidenze verificabili
- chiarire cosa resta aperto e con quale priorità

Legenda stato:
- `Closed`: finding sostanzialmente risolto
- `Partial`: mitigato o affrontato in parte, ma non chiuso al 100%
- `Open`: non ancora implementato
- `Optional`: non implementato e non necessario per il go-live minimo

## Executive Summary

### Closed
- autenticazione reale utenti/admin
- reset password self-service con token monouso
- pannello admin per manutenzione impostazioni e segreti mascherati
- migrazione da SQLite a PostgreSQL per catalogo prodotti e auth
- modalità catalogo pubblico read-only per utenti anonimi
- protezione endpoint debug/admin
- CORS esplicito
- mitigazione SSRF sui fetch outbound
- hardening upload base
- CI minima
- deploy manuale assistito via GitHub Actions + SSH
- flussi funzionali principali validati localmente
- backup/restore Postgres verificato
- monitor healthcheck schedulato con webhook di alert
- runbook di rollback operativo

### Partial
- refactor del monolite
- rate limiting
- monitoring/logging
- test coverage
- hardening security avanzato
- deploy production reale

### Optional
- Cognito
- Bedrock
- CloudFront
- S3
- CloudWatch

## Stato per finding / area

| Area report | Stato | Fix / situazione attuale | Evidenza | Prossimo passo |
|---|---|---|---|---|
| Monolithic architecture | Partial | `main.py` è stato alleggerito con estrazione di logiche core in moduli dedicati | [main.py](/c:/Users/Osman.saleh/OneDrive/Cartella%20progetto/product-finder%202/Backend/app/main.py), [search_logic.py](/c:/Users/Osman.saleh/OneDrive/Cartella%20progetto/product-finder%202/Backend/app/search_logic.py), [facets_logic.py](/c:/Users/Osman.saleh/OneDrive/Cartella%20progetto/product-finder%202/Backend/app/facets_logic.py), [compare_logic.py](/c:/Users/Osman.saleh/OneDrive/Cartella%20progetto/product-finder%202/Backend/app/compare_logic.py), [quote_logic.py](/c:/Users/Osman.saleh/OneDrive/Cartella%20progetto/product-finder%202/Backend/app/quote_logic.py), [alternatives_logic.py](/c:/Users/Osman.saleh/OneDrive/Cartella%20progetto/product-finder%202/Backend/app/alternatives_logic.py), [schema.py](/c:/Users/Osman.saleh/OneDrive/Cartella%20progetto/product-finder%202/Backend/app/schema.py) | Continuare solo se emergono nuovi punti caldi; non è più emergenza critica |
| SQLite non production-grade | Closed | Catalogo prodotti e auth possono girare su PostgreSQL; runtime già configurato per Postgres | [database.py](/c:/Users/Osman.saleh/OneDrive/Cartella%20progetto/product-finder%202/Backend/app/database.py), [db_runtime.py](/c:/Users/Osman.saleh/OneDrive/Cartella%20progetto/product-finder%202/Backend/app/db_runtime.py), [auth.py](/c:/Users/Osman.saleh/OneDrive/Cartella%20progetto/product-finder%202/Backend/app/auth.py) | Consolidare solo il deploy reale containerizzato |
| No authentication | Closed | Signup self-service con approvazione admin, login JWT/cookie, ruoli base `admin/user`, endpoint protetti e password reset self-service | [auth.py](/c:/Users/Osman.saleh/OneDrive/Cartella%20progetto/product-finder%202/Backend/app/auth.py), [auth_router.py](/c:/Users/Osman.saleh/OneDrive/Cartella%20progetto/product-finder%202/Backend/app/auth_router.py), [main.py](/c:/Users/Osman.saleh/OneDrive/Cartella%20progetto/product-finder%202/Backend/app/main.py), [reset-password.html](/c:/Users/Osman.saleh/OneDrive/Cartella%20progetto/product-finder%202/Backend/frontend/reset-password.html) | In futuro: policy password più ricca, audit login |
| Exposed debug endpoints | Closed | Endpoint debug/admin disabilitati di default o protetti con policy admin/local-only | [debug_router.py](/c:/Users/Osman.saleh/OneDrive/Cartella%20progetto/product-finder%202/Backend/app/debug_router.py), [security.py](/c:/Users/Osman.saleh/OneDrive/Cartella%20progetto/product-finder%202/Backend/app/security.py) | Eventuale audit log admin |
| CORS not configured | Closed | CORS configurato con allowlist esplicita via env | [security.py](/c:/Users/Osman.saleh/OneDrive/Cartella%20progetto/product-finder%202/Backend/app/security.py), [.env.example](/c:/Users/Osman.saleh/OneDrive/Cartella%20progetto/product-finder%202/Backend/.env.example) | Rifinire solo per dominio definitivo |
| SSRF vulnerability | Closed | I fetch outbound usano validazione host/schema e allowlist host pubblici | [security.py](/c:/Users/Osman.saleh/OneDrive/Cartella%20progetto/product-finder%202/Backend/app/security.py), [main.py](/c:/Users/Osman.saleh/OneDrive/Cartella%20progetto/product-finder%202/Backend/app/main.py) | Riesame futuro se vengono aggiunte nuove integrazioni esterne |
| Weak file upload validation | Closed | Controlli size, content-type e file signature aggiunti su PDF/immagini; rischio base mitigato per l'uso attuale | [main.py](/c:/Users/Osman.saleh/OneDrive/Cartella%20progetto/product-finder%202/Backend/app/main.py), [security.py](/c:/Users/Osman.saleh/OneDrive/Cartella%20progetto/product-finder%202/Backend/app/security.py) | Possibile scanning/isolation più forte solo come hardening extra |
| No rate limiting | Partial | Rate limit base in-memory presente sugli endpoint più esposti | [security.py](/c:/Users/Osman.saleh/OneDrive/Cartella%20progetto/product-finder%202/Backend/app/security.py) | In produzione valutare rate limiting condiviso lato proxy o Redis |
| No automated tests | Partial | Test backend presenti e verdi; smoke suite copre auth, catalogo pubblico, admin approval, export e quote persistence; Playwright aggiunge smoke browser su ricerca anonima, approval admin e quote save/load; CI esegue `pytest` e build Docker | [tests](/c:/Users/Osman.saleh/OneDrive/Cartella%20progetto/product-finder%202/Backend/tests), [e2e](/c:/Users/Osman.saleh/OneDrive/Cartella%20progetto/product-finder%202/Backend/e2e), [backend-ci.yml](/c:/Users/Osman.saleh/OneDrive/Cartella%20progetto/product-finder%202/.github/workflows/backend-ci.yml) | Ampliare coverage browser su edge case e deploy smoke |
| No deployment pipeline | Closed | CI attiva sul repo root e workflow di deploy manuale via GitHub Actions copiano `Backend/` sul server ed eseguono deploy con healthcheck finale | [backend-ci.yml](/c:/Users/Osman.saleh/OneDrive/Cartella%20progetto/product-finder%202/.github/workflows/backend-ci.yml), [backend-deploy-prod.yml](/c:/Users/Osman.saleh/OneDrive/Cartella%20progetto/product-finder%202/.github/workflows/backend-deploy-prod.yml), [deploy_prod.sh](/c:/Users/Osman.saleh/OneDrive/Cartella%20progetto/product-finder%202/Backend/scripts/deploy_prod.sh), [check_health.py](/c:/Users/Osman.saleh/OneDrive/Cartella%20progetto/product-finder%202/Backend/scripts/check_health.py) | Configurare secrets GitHub `PROD_*` e usare environment `production` |
| Monitoring / alerting | Closed | `/health` è ora consumato da workflow schedulato ogni 15 minuti con alert webhook opzionale e probe riutilizzabile | [backend-monitor.yml](/c:/Users/Osman.saleh/OneDrive/Cartella%20progetto/product-finder%202/.github/workflows/backend-monitor.yml), [check_health.py](/c:/Users/Osman.saleh/OneDrive/Cartella%20progetto/product-finder%202/Backend/scripts/check_health.py), [main.py](/c:/Users/Osman.saleh/OneDrive/Cartella%20progetto/product-finder%202/Backend/app/main.py#L1935) | Configurare `HEALTHCHECK_URL` e `ALERT_WEBHOOK_URL` nei secrets |
| Backup strategy | Closed | Backup e restore Postgres documentati e testati su DB separato | [backup_postgres.ps1](/c:/Users/Osman.saleh/OneDrive/Cartella%20progetto/product-finder%202/Backend/scripts/backup_postgres.ps1), [restore_postgres_backup.ps1](/c:/Users/Osman.saleh/OneDrive/Cartella%20progetto/product-finder%202/Backend/scripts/restore_postgres_backup.ps1), [DEPLOYMENT.md](/c:/Users/Osman.saleh/OneDrive/Cartella%20progetto/product-finder%202/Backend/DEPLOYMENT.md) | Automatizzare schedulazione backup sul server |
| Docker / EC2 / reverse proxy / SSL | Partial | Stack Docker locale eseguito e validato con healthcheck, persistenza Postgres e restart recovery; stack production predisposto con Caddy HTTPS, ma non ancora eseguito su server reale | [Dockerfile](/c:/Users/Osman.saleh/OneDrive/Cartella%20progetto/product-finder%202/Backend/Dockerfile), [docker-compose.yml](/c:/Users/Osman.saleh/OneDrive/Cartella%20progetto/product-finder%202/Backend/docker-compose.yml), [docker-compose.prod.yml](/c:/Users/Osman.saleh/OneDrive/Cartella%20progetto/product-finder%202/Backend/docker-compose.prod.yml), [Caddyfile](/c:/Users/Osman.saleh/OneDrive/Cartella%20progetto/product-finder%202/Backend/deploy/Caddyfile), [DEPLOYMENT.md](/c:/Users/Osman.saleh/OneDrive/Cartella%20progetto/product-finder%202/Backend/DEPLOYMENT.md) | Deploy su server con DNS/HTTPS veri e smoke test ambiente |
| Frontend auth / access flow | Closed | Login/signup/account/admin panel integrati nel frontend, con forgot-password e pagina reset dedicata | [auth.js](/c:/Users/Osman.saleh/OneDrive/Cartella%20progetto/product-finder%202/Backend/frontend/assets/auth.js), [index.html](/c:/Users/Osman.saleh/OneDrive/Cartella%20progetto/product-finder%202/Backend/frontend/index.html), [tools.html](/c:/Users/Osman.saleh/OneDrive/Cartella%20progetto/product-finder%202/Backend/frontend/tools.html), [admin.html](/c:/Users/Osman.saleh/OneDrive/Cartella%20progetto/product-finder%202/Backend/frontend/admin.html), [reset-password.html](/c:/Users/Osman.saleh/OneDrive/Cartella%20progetto/product-finder%202/Backend/frontend/reset-password.html) | Solo rifiniture UX se utili |
| Public catalog + quote workflow | Closed | Utenti anonimi hanno catalogo read-only con ricerca e filtri; utenti autenticati hanno quote, comparazione, salvataggio preventivi e storico per progetto | [index.html](/c:/Users/Osman.saleh/OneDrive/Cartella%20progetto/product-finder%202/Backend/frontend/index.html), [quote.html](/c:/Users/Osman.saleh/OneDrive/Cartella%20progetto/product-finder%202/Backend/frontend/quote.html), [tools.html](/c:/Users/Osman.saleh/OneDrive/Cartella%20progetto/product-finder%202/Backend/frontend/tools.html), [quote_logic.py](/c:/Users/Osman.saleh/OneDrive/Cartella%20progetto/product-finder%202/Backend/app/quote_logic.py), [auth_router.py](/c:/Users/Osman.saleh/OneDrive/Cartella%20progetto/product-finder%202/Backend/app/auth_router.py) | Nessun blocker funzionale noto; tenere solo testato contro regressioni |
| Session hardening locale | Closed | Sessione basata su cookie HttpOnly con refresh rotation, timeout inattività lato frontend e durata JWT ridotta a 120 minuti | [auth.js](/c:/Users/Osman.saleh/OneDrive/Cartella%20progetto/product-finder%202/Backend/frontend/assets/auth.js), [quote.html](/c:/Users/Osman.saleh/OneDrive/Cartella%20progetto/product-finder%202/Backend/frontend/quote.html), [auth.py](/c:/Users/Osman.saleh/OneDrive/Cartella%20progetto/product-finder%202/Backend/app/auth.py) | In futuro valutare solo ulteriore audit/security analytics |
| Admin-maintainable configuration | Closed | Pannello admin con settings catalog categorizzato, tabs UX, config DB-backed, segreti mascherati e hint `restart required` | [admin_settings.py](/c:/Users/Osman.saleh/OneDrive/Cartella%20progetto/product-finder%202/Backend/app/admin_settings.py), [auth_router.py](/c:/Users/Osman.saleh/OneDrive/Cartella%20progetto/product-finder%202/Backend/app/auth_router.py), [admin.html](/c:/Users/Osman.saleh/OneDrive/Cartella%20progetto/product-finder%202/Backend/frontend/admin.html) | Ampliare solo se emergono nuove impostazioni da esporre |
| Rollback runbook | Closed | Procedura formale di rollback documentata con validation checklist e path per restore dati | [ROLLBACK_RUNBOOK.md](/c:/Users/Osman.saleh/OneDrive/Cartella%20progetto/product-finder%202/Backend/ROLLBACK_RUNBOOK.md), [restore_postgres_backup.ps1](/c:/Users/Osman.saleh/OneDrive/Cartella%20progetto/product-finder%202/Backend/scripts/restore_postgres_backup.ps1), [deploy_prod.sh](/c:/Users/Osman.saleh/OneDrive/Cartella%20progetto/product-finder%202/Backend/scripts/deploy_prod.sh) | Tenere aggiornato il commit/tag noto stabile dopo ogni release |
| Cognito | Optional | Non implementato | Nessuna | Non necessario per go-live minimo |
| Bedrock + OpenAI fallback | Optional | Non implementato | Nessuna | Valutare solo se cambia strategia AI/cloud |
| CloudFront / S3 / CloudWatch | Optional | Non implementato | Nessuna | Valutare solo con vero stack cloud enterprise |

## Evidenze tecniche principali

### Test
- smoke suite backend verde per auth, catalogo pubblico, admin approval, export e quote persistence
- smoke suite Playwright verde per browser flows critici (`3 passed`)
- CI GitHub Actions configurata su repo root per eseguire test e Docker build

### Database
- PostgreSQL locale verificato con catalogo prodotti attivo
- restart Docker locale verificato con persistenza dati applicativi
- verifica backup/restore eseguita su database dedicato `productfinder_restore_check`
- esito verifica restore:
  - `products = 6104`
  - `users = 3`
  - `saved_quotes = 2`

### Sicurezza
- auth JWT attiva
- admin approval flow attivo
- sessione basata su cookie HttpOnly con refresh rotation
- sessione browser non più persistente oltre la sessione del browser
- timeout inattività lato frontend
- durata token ridotta a `120` minuti
- reset password con token monouso a scadenza
- debug endpoints chiusi di default
- CORS configurato
- SSRF mitigato con safe outbound fetch
- upload PDF/immagini con controlli di base
- pannello admin per gestione settings e segreti mascherati

### Deploy preparedness
- compose locale eseguito e validato
- compose production pronto
- reverse proxy HTTPS pronto
- workflow deploy manuale pronto
- workflow monitor/alert pronto
- runbook rollback pronto
- `.env` example per locale, Docker e produzione disponibili

## Gap residui ad alta priorità

### 1. Deploy reale
Manca ancora l’esecuzione su server reale con:
- DNS configurato
- dominio pubblico
- prima validazione HTTPS end-to-end

### 2. Monitoring più completo
Mancano ancora:
- raccolta log centralizzata

### 3. Test end-to-end più ampi
La base backend e browser smoke è buona, ma non copre ancora:
- flussi browser completi su tutti i casi edge
- regressioni frontend più profonde
- smoke test di deploy su host reale

## Gap residui medi

- refactor ulteriore del bootstrap `main.py` solo se necessario
- rate limiting più robusto lato infrastruttura
- SMTP per invio reale delle email di reset, attualmente dipendente da IT Microsoft 365
- documentazione rollback più formale

## Decisione pratica consigliata

Per un go-live prudente senza software house:
- considerare chiusi i finding di sicurezza principali
- considerare il refactor monolite come mitigato in modo sostanziale
- non trattare come blocker Cognito, Bedrock, CloudFront o CloudWatch
- concentrare il prossimo lavoro su deploy reale, logging centralizzato e SMTP production-ready

## Note

Questo documento fotografa lo stato del progetto dopo la remediation fatta internamente sul repository `Backend/`.
Va aggiornato ogni volta che cambia in modo significativo uno di questi aspetti:
- sicurezza
- deploy
- testing
- infrastruttura
