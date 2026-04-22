# Guida IT alle Impostazioni del Pannello Admin

## Scopo del documento

Questo documento e' pensato per l'IT manager che deve prendere in carico la parte infrastrutturale e di sicurezza del pannello `Settings` dell'Admin Panel.

Obiettivo:

- chiarire quali impostazioni sono di competenza IT
- spiegare dove impattano
- distinguere tra modifiche applicate subito e modifiche che richiedono restart/redeploy
- fornire una procedura operativa di gestione e verifica
- rendere esplicita la responsabilita' IT sulle configurazioni sensibili

Frontend di accesso:

- `/frontend/admin.html`

Nota importante:

- la sezione `Settings` e' accessibile solo a utenti con ruolo `admin`
- il presente documento copre le impostazioni IT della sezione `Settings`
- la sezione `Scoring` non rientra nel perimetro IT puro, salvo supporto tecnico

## Sintesi Esecutiva

Le impostazioni che devono essere presidiate dal reparto IT sono principalmente queste categorie:

- `Security`
- `Email`
- `Deployment`
- `Operations`
- parte di `Administration`

Le impostazioni che possono richiedere coinvolgimento condiviso con business o fornitore applicativo sono:

- `AI`
- `Catalog`

Le impostazioni piu' sensibili, da trattare come responsabilita' diretta IT, sono:

- `AUTH_JWT_SECRET`
- `CORS_ALLOWED_ORIGINS`
- `AUTH_COOKIE_SECURE`
- `AUTH_COOKIE_SAMESITE`
- `APP_DOMAIN`
- `ACME_EMAIL`
- `POSTGRES_PASSWORD`
- `SMTP_HOST`
- `SMTP_PORT`
- `SMTP_USERNAME`
- `SMTP_PASSWORD`
- `SMTP_FROM_EMAIL`
- `RATE_LIMIT_STORE`
- `RATE_LIMIT_DATABASE_URL`
- `ENABLE_DEBUG_ENDPOINTS`

## Cosa Significa “Presa in Carico IT”

Per questo progetto, la presa in carico IT significa che il referente IT:

- decide i valori corretti delle impostazioni tecniche
- approva le modifiche in produzione
- conserva in modo sicuro i secret
- verifica l'effetto delle modifiche dopo il salvataggio
- pianifica i restart/redeploy quando necessari
- gestisce il rollback in caso di errore
- mantiene allineati dominio, SMTP, sicurezza cookie, CORS e password database con l'infrastruttura reale

## Come Funziona la Sezione Settings

La sezione `Settings` del pannello Admin espone configurazioni applicative salvabili da interfaccia.

Comportamento generale:

- i valori sensibili sono mostrati mascherati
- per i secret, lasciare il campo vuoto mantiene il valore gia' presente
- alcune modifiche sono `Hot apply`, quindi il backend prova a usarle subito
- altre sono `Restart needed`, quindi il valore viene salvato ma serve riavvio o redeploy per effetto completo

In pratica bisogna distinguere tre casi:

1. valore salvato e applicato subito
2. valore salvato ma da validare con un nuovo login o con un test operativo
3. valore salvato ma da attivare con restart/redeploy

## Procedura Operativa Consigliata

### Accesso

1. Aprire `/frontend/admin.html`
2. Accedere con un account `admin`
3. Aprire la sezione `Settings`
4. Cercare la categoria desiderata

### Lettura delle Etichette

Nel pannello ogni impostazione mostra:

- `Configured` oppure `Not set`
- `Restart needed` oppure `Hot apply`
- `Masked` se il valore e' segreto

Interpretazione:

- `Configured`: esiste gia' un valore attivo o salvato
- `Hot apply`: la modifica e' pensata per essere utilizzata subito
- `Restart needed`: il backend o l'infrastruttura richiedono un riavvio per usare davvero il nuovo valore

### Modalita' Corretta di Modifica

1. Annotare il valore attuale o almeno il fatto che sia configurato
2. Inserire il nuovo valore
3. Premere `Save`
4. Leggere il messaggio di conferma
5. Eseguire il test operativo specifico della categoria
6. Se la voce e' `Restart needed`, pianificare subito restart o redeploy

### Regola di Sicurezza

Non modificare in un'unica sessione:

- segreti di autenticazione
- parametri cookie
- CORS
- dominio
- database

Meglio una modifica alla volta, con verifica immediata.

## Matrice di Responsabilita'

| Categoria | Owner principale | Coinvolgimento secondario |
|---|---|---|
| Security | IT | Fornitore applicativo |
| Email | IT | Business owner per caselle e processi |
| Deployment | IT | Dev/Fornitore |
| Operations | IT | Dev/Fornitore |
| Administration | IT | Owner applicativo |
| AI | Condivisa | Business + Dev + IT |
| Catalog | Condivisa | Business + Data owner + IT |

## Walkthrough Dettagliato per Categoria

## Security

Questa e' la categoria con il rischio piu' alto, perche' impatta accesso, sessioni, browser policy e superficie esposta.

### `AUTH_JWT_SECRET`

Cos'e':

- il segreto usato per firmare i token di accesso

Impatto:

- influisce sulla validazione delle sessioni utente
- una modifica errata puo' rendere invalidi i token esistenti

Modalita' operativa:

- trattare come secret critico
- ruotarlo solo in finestra controllata
- dopo il salvataggio e' necessario restart/redeploy

Responsabilita' IT:

- generazione del segreto
- custodia sicura
- pianificazione della rotazione
- comunicazione di eventuale logout forzato agli utenti

Verifica post-modifica:

- nuovo login admin riuscito
- login utente riuscito
- refresh sessione riuscito

### `AUTH_TOKEN_EXPIRE_MINUTES`

Cos'e':

- durata dei nuovi access token

Impatto:

- influenza la frequenza con cui la sessione necessita refresh

Comportamento attuale:

- il backend ricarica questo valore a runtime
- l'effetto atteso riguarda i nuovi token emessi dopo la modifica

Raccomandazione:

- usare valori troppo bassi solo se il refresh flow e' gia' stato validato

Verifica:

- eseguire nuovo login
- controllare che la sessione resti stabile

### `AUTH_REFRESH_TOKEN_EXPIRE_DAYS`

Cos'e':

- durata delle refresh session

Impatto:

- definisce per quanto tempo un utente puo' rinnovare la sessione senza nuovo login completo

Nota tecnica importante:

- il pannello la espone come modifica immediata
- nella versione corrente il backend salva il valore, ma il refresh runtime di questa specifica proprieta' va considerato da verificare con attenzione
- per prudenza operativa, trattarla come modifica da testare con nuovo login e con test di refresh session

Raccomandazione IT:

- dopo modifica fare sempre test end-to-end
- in produzione considerare comunque una finestra di riavvio se si vuole certezza applicativa

### `AUTH_COOKIE_SECURE`

Cos'e':

- definisce se i cookie auth vengono inviati solo su HTTPS

Regola pratica:

- in produzione deve essere `true`
- in locale HTTP puo' essere `false`

Rischio:

- se impostato male in produzione il login puo' comportarsi in modo incoerente

Verifica:

- login via browser
- logout
- refresh pagina
- verifica permanenza sessione

### `AUTH_COOKIE_SAMESITE`

Cos'e':

- policy browser per i cookie auth

Valori validi:

- `lax`
- `strict`
- `none`

Raccomandazione:

- default consigliato: `lax`
- usare `none` solo se serve davvero un contesto cross-site e con HTTPS corretto

Verifica:

- login normale
- apertura link diretti a pagine protette
- flusso password reset

### `CORS_ALLOWED_ORIGINS`

Cos'e':

- lista degli origin browser autorizzati a chiamare il backend

Formato:

- elenco separato da virgole

Esempio:

- `https://example.com,https://app.example.com`

Rischio:

- troppo restrittivo: frontend non comunica con backend
- troppo permissivo: superficie esposta inutilmente

Comportamento:

- richiede restart/redeploy per effetto completo

Responsabilita' IT:

- mantenere allineati gli origin reali di produzione, staging e test

Verifica:

- apertura frontend
- login
- chiamata search
- apertura pannello admin

### `ENABLE_DEBUG_ENDPOINTS`

Cos'e':

- abilita endpoint di debug e manutenzione locale

Raccomandazione forte:

- in produzione deve restare `false`

Rischio:

- se attivato senza controllo, aumenta la superficie amministrativa

Quando usarlo:

- solo per troubleshooting controllato
- solo per finestre temporanee e documentate

Verifica:

- se attivato, disattivarlo appena conclusa l'analisi

### `ADMIN_TOKEN`

Cos'e':

- token legacy per endpoint debug o manutenzione residuale

Raccomandazione:

- se non serve, lasciarlo non usato
- se usato, trattarlo come secret

Nota:

- non e' il meccanismo principale del pannello Admin moderno

## Email

Questa categoria va assegnata chiaramente all'IT, perche' impatta recapito, reset password e notifiche amministrative.

### `SMTP_HOST`

Cos'e':

- hostname del server SMTP

### `SMTP_PORT`

Cos'e':

- porta del server SMTP

Valori tipici:

- `587`
- `25`

### `SMTP_USERNAME`

Cos'e':

- utente di autenticazione SMTP

### `SMTP_PASSWORD`

Cos'e':

- password o app password SMTP

### `SMTP_FROM_EMAIL`

Cos'e':

- indirizzo mittente usato per email applicative

Dettaglio molto importante:

- nella versione corrente questo indirizzo non e' solo il mittente
- viene anche usato come indirizzo che riceve la notifica di nuova richiesta accesso

Conseguenza operativa:

- l'IT deve decidere una mailbox reale, monitorata, e non un indirizzo fittizio
- se si usa una casella condivisa, bisogna concordare chi la presidia

Flussi che dipendono da SMTP:

- password reset
- notifica interna di nuova richiesta accesso
- email all'utente quando la richiesta e' stata ricevuta
- email all'utente quando l'accesso viene approvato

Procedura consigliata di setup:

1. recuperare i dati della mailbox da Microsoft 365 o dal provider SMTP
2. compilare `SMTP_HOST`, `SMTP_PORT`, `SMTP_USERNAME`, `SMTP_PASSWORD`, `SMTP_FROM_EMAIL`
3. salvare i valori dal pannello
4. eseguire un test di password reset
5. eseguire un test di signup con richiesta accesso

Verifica minima obbligatoria:

- arriva l'email di reset password
- arriva la notifica interna di nuova richiesta accesso
- l'utente riceve conferma richiesta

## Administration

Questa categoria non e' solo applicativa: contiene credenziali e identita' dell'account admin bootstrap.

### `ADMIN_BOOTSTRAP_EMAIL`

Cos'e':

- email dell'account admin bootstrap garantito all'avvio

### `ADMIN_BOOTSTRAP_NAME`

Cos'e':

- nome visualizzato dell'admin bootstrap

### `ADMIN_BOOTSTRAP_PASSWORD`

Cos'e':

- password dell'admin bootstrap

Comportamento:

- il backend cerca di garantire la presenza di questo admin all'avvio
- le modifiche sono applicate come override runtime dal servizio auth

Rischio:

- se l'IT cambia questi dati senza controllo, puo' alterare l'account amministrativo di riferimento

Uso corretto:

- definire un account amministrativo istituzionale
- evitare account personali
- conservare la password in password manager aziendale

Verifica:

- login con l'account bootstrap
- accesso al pannello Admin

## Deployment

Questa categoria e' di responsabilita' IT quasi totale.

### `APP_DOMAIN`

Cos'e':

- dominio pubblico principale usato dal deployment

Impatto:

- rilevante per reverse proxy e HTTPS
- usato anche per costruire il link di reset password

Dettaglio operativo:

- se il valore non contiene `http://` o `https://`, l'app costruisce il link come `https://<dominio>`

Comportamento:

- richiede restart/redeploy

Dipendenze esterne:

- DNS
- reverse proxy
- certificato TLS

Verifica:

- il dominio risolve correttamente
- il frontend si apre
- il reset password genera link corretti

### `ACME_EMAIL`

Cos'e':

- email usata per emissione/rinnovo certificati

Responsabilita' IT:

- deve essere una mailbox reale presidiata
- deve ricevere alert o notifiche legate al certificato

Comportamento:

- richiede restart/redeploy

### `POSTGRES_PASSWORD`

Cos'e':

- password del database PostgreSQL usata dal deployment

Rischio:

- e' una delle impostazioni piu' sensibili dell'intero sistema

Comportamento:

- richiede restart/redeploy
- se cambiata in modo non coordinato puo' interrompere applicazione e database

Regola operativa:

- non cambiarla mai solo nel pannello
- coordinare sempre:
  database reale
  secret/compose/env del server
  applicazione
  eventuali backup/restore script

Verifica:

- healthcheck applicativo
- accesso login
- lettura catalogo

## Operations

Questa categoria copre debug e rate limiting.

### `RATE_LIMIT_STORE`

Cos'e':

- backend usato per il rate limiting

Valori da usare nel pannello:

- `memory`
- `database`
- `db`

Nota pratica:

- alcuni file esempio storici mostrano `shared`
- dal pannello Admin conviene usare `database`, che e' coerente con la validazione della UI

Scelta consigliata:

- ambiente singolo/non critico: `memory`
- ambiente condiviso o multiistanza: `database`

### `RATE_LIMIT_DATABASE_URL`

Cos'e':

- connessione database per il rate limiting condiviso

Comportamento:

- se valorizzato, il sistema puo' usare una tabella dedicata `rate_limit_hits`

Responsabilita' IT:

- definire se il rate limiting deve essere locale o condiviso
- verificare disponibilita' del database

Rischio:

- configurazione incoerente puo' degradare protezioni o generare problemi di accesso concorrente

Verifica:

- controllare che il servizio risponda normalmente
- controllare che non compaiano errori di connessione database

## AI

Categoria parzialmente IT, parzialmente applicativa.

### `OPENAI_API_KEY`

Cos'e':

- chiave backend per funzionalita' AI

Responsabilita':

- IT gestisce il secret
- owner applicativo decide se la funzione deve essere attiva

Impatto:

- parsing AI
- ragionamento assistito

Comportamento:

- hot apply

Verifica:

- testare una funzione AI dal backend o dal finder

### `DISANO_STORE_IDS`

Cos'e':

- store IDs usati per lookup di contenuti immagine esterni

### `DISANO_LANG_ID`

Cos'e':

- identificativo lingua usato nelle interrogazioni di contenuto Disano

Ownership consigliata:

- business o owner applicativo per il valore funzionale
- IT solo come supporto di configurazione

## Catalog

Categoria condivisa tra IT e owner del dato/catalogo.

### `PIM_XLSX`

Cos'e':

- percorso del file Excel PIM principale importato all'avvio

### `FAMILY_MAP_XLSX`

Cos'e':

- percorso del file Excel di mapping famiglie

### `PIM_VERBOSE`

Cos'e':

- abilita logging verboso in fase import PIM

Raccomandazione:

- `PIM_XLSX` e `FAMILY_MAP_XLSX` vanno trattati come impostazioni di deploy/import
- cambiare i path richiede restart/redeploy
- `PIM_VERBOSE` puo' essere usato temporaneamente per troubleshooting

Ownership:

- il contenuto del file e' del data owner/business
- la disponibilita' del file, i path e i permessi sono responsabilita' IT

## Tabella Rapida di Ownership IT

| Impostazione | Ownership IT | Azione richiesta |
|---|---|---|
| `AUTH_JWT_SECRET` | Totale | Custodia, rotazione, restart controllato |
| `AUTH_TOKEN_EXPIRE_MINUTES` | Totale | Politica sessione |
| `AUTH_REFRESH_TOKEN_EXPIRE_DAYS` | Totale | Politica sessione con test end-to-end |
| `AUTH_COOKIE_SECURE` | Totale | Sicurezza browser/prod |
| `AUTH_COOKIE_SAMESITE` | Totale | Compatibilita' browser |
| `CORS_ALLOWED_ORIGINS` | Totale | Allineamento frontend/backend |
| `ENABLE_DEBUG_ENDPOINTS` | Totale | Tenerlo disattivo salvo emergenze |
| `ADMIN_TOKEN` | Totale | Secret legacy, se usato |
| `SMTP_*` | Totale | Casella, relay, credenziali, test recapito |
| `ADMIN_BOOTSTRAP_*` | Totale | Account admin istituzionale |
| `APP_DOMAIN` | Totale | DNS, reset link, reverse proxy |
| `ACME_EMAIL` | Totale | Mailbox certificati |
| `POSTGRES_PASSWORD` | Totale | Rotazione coordinata DB/app |
| `RATE_LIMIT_STORE` | Totale | Politica protezione traffico |
| `RATE_LIMIT_DATABASE_URL` | Totale | DB condiviso per rate limit |
| `OPENAI_API_KEY` | Condivisa | Secret custodito da IT |
| `PIM_XLSX` | Condivisa | Path e disponibilita' file |
| `FAMILY_MAP_XLSX` | Condivisa | Path e disponibilita' file |

## Test Minimi Dopo Ogni Modifica

### Se si tocca Security

- login admin
- login utente
- logout
- refresh pagina protetta

### Se si tocca Email

- richiesta password reset
- ricezione email reset
- test signup con ricezione notifiche

### Se si tocca Deployment

- `/health`
- apertura frontend
- login
- reset password con link corretto

### Se si tocca Database o Rate Limiting

- `/health`
- login
- ricerca catalogo
- nessun errore DB nei log

## Regole di Cambio in Produzione

- una sola modifica sensibile per volta
- sempre annotare data, ora, autore e motivazione
- eseguire test subito dopo il salvataggio
- se la voce richiede restart, non considerare chiuso il cambio finche' il restart non e' stato fatto e validato
- per `AUTH_JWT_SECRET`, `POSTGRES_PASSWORD`, `APP_DOMAIN`, `CORS_ALLOWED_ORIGINS` serve change management rigoroso

## Checklist di Presa in Carico IT

Il reparto IT dovrebbe confermare formalmente questi punti:

- dispone di un account `admin` dedicato
- custodisce `AUTH_JWT_SECRET`
- custodisce `POSTGRES_PASSWORD`
- custodisce `SMTP_PASSWORD`
- conosce il dominio finale e il DNS associato
- presidia la mailbox `ACME_EMAIL`
- presidia la mailbox `SMTP_FROM_EMAIL`
- ha verificato il flusso password reset
- ha verificato il flusso signup e approvazione
- sa distinguere tra `Hot apply` e `Restart needed`
- dispone di procedura di rollback

## Raccomandazione Finale di Governance

Per evitare zone grigie, suggerisco di attribuire all'IT manager la responsabilita' esplicita delle categorie:

- `Security`
- `Email`
- `Deployment`
- `Operations`
- `Administration`

e di lasciare in ownership condivisa:

- `AI`
- `Catalog`

In questo modo tutto cio' che tocca credenziali, dominio, sessioni, email, database, protezioni e parametri infrastrutturali ha un owner chiaro e non resta in carico implicito al team applicativo.

## Riferimenti Tecnici

File principali da considerare come base tecnica del presente documento:

- `Backend/frontend/admin.html`
- `Backend/app/admin_settings.py`
- `Backend/app/auth.py`
- `Backend/app/auth_router.py`
- `Backend/app/security.py`
- `Backend/DEPLOYMENT.md`
- `Backend/ADMIN_SETTINGS_REFERENCE.md`
