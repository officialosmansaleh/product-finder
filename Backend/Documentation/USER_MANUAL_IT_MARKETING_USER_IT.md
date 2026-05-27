# Manuale utente - Laiting Product Finder

Versione: 14 maggio 2026

## Scopo

Questo manuale descrive l'utilizzo del workspace Laiting Product Finder per tre profili operativi:

- utente normale
- utente IT
- utente Marketing

Il documento copre le pagine visibili, le funzioni disponibili e le azioni consigliate per ogni profilo. Le funzioni amministrative complete per `admin`, `director` e `manager` sono documentate separatamente.

## Accesso alla piattaforma

Indirizzi principali:

- Home / Finder: `/frontend/`
- Workspace confronto: `/frontend/tools.html`
- Carrello offerta: `/frontend/quote.html`
- Pannello account / admin: `/frontend/admin.html`

Per usare le funzioni personali e salvare offerte e preferenze e' necessario accedere con un account approvato.

## Login e richiesta accesso

1. Aprire `/frontend/`.
2. Usare il pulsante account in alto a destra.
3. Se si possiede gia' un account, inserire email e password e premere login.
4. Se non si possiede un account, aprire la scheda di registrazione e compilare:
   - nome completo
   - email
   - password
   - azienda
   - paese
5. Dopo la registrazione, l'account resta in stato `pending` fino ad approvazione.

Regole password:

- almeno 10 caratteri
- almeno una lettera
- almeno un numero

Stati account:

- `pending`: richiesta inviata, accesso non ancora consentito
- `approved`: account attivo
- `rejected`: accesso rifiutato o bloccato

## Matrice rapida dei profili

| Funzione | Utente normale | IT | Marketing |
|---|---:|---:|---:|
| Ricerca prodotti | Si | Possibile, ma profilo pensato per Settings | Si, se usa la home |
| Filtri catalogo | Si | Possibile, ma non workflow IT principale | Si, se usa la home |
| Confronto prodotti | Si | No, Tools reindirizza al pannello IT | Si, se usa Tools |
| Carrello offerta | Si | Non previsto come workflow IT | Si, se usa Quote |
| Cambio password da pannello | Si | Si | Si |
| Settings tecnici | No | Si, escluso Scoring | No |
| Settings Website | No | Si | Si, solo Website |
| Test email SMTP | No | Si | No |
| Catalog health | No | No | Si |
| Release changes catalogo | No | No | Si |
| Utenti, approvazioni, quote visibili | No | No | No |
| Analytics | No | No | No |
| Scoring | No | No | No |

Nota: il ruolo IT e' pensato come profilo tecnico di configurazione. Se un utente IT apre il workspace confronto, viene reindirizzato al pannello `Settings`; nella Home le azioni commerciali di confronto/offerta non sono il workflow previsto per questo profilo.

## Utente normale

### Pagine disponibili

Un utente normale approvato usa principalmente:

- Home / Finder
- Workspace confronto
- Carrello offerta
- sezione Password del pannello account

### Home / Finder

La Home serve per cercare prodotti nel catalogo.

Funzioni principali:

- ricerca per codice prodotto
- ricerca per nome prodotto
- ricerca per famiglia
- filtri tecnici per produttore, famiglia, fotometria, protezione, elettrico, meccanico e durata
- selezione accessori tramite `Include accessories in search`
- apertura scheda tecnica o pagina prodotto quando disponibile
- aggiunta prodotto al carrello offerta

Uso consigliato:

1. Inserire un codice o una descrizione nel campo ricerca.
2. Premere Invio oppure usare la ricerca automatica.
3. Applicare filtri solo dopo una prima ricerca ampia.
4. Controllare punteggio, famiglia, dati tecnici e immagine.
5. Aggiungere i prodotti validi al carrello offerta.

### Filtri

I filtri sono organizzati per gruppi:

- Product families
- Protection
- Photometric
- Electrical
- Mechanical
- Lifetime
- All

I filtri selezionati appaiono come chip nella sezione `Selected filters`. Per rimuovere un filtro basta cliccare sul relativo chip. Il pulsante `Reset` pulisce ricerca e filtri.

### Workspace confronto

Il workspace confronto serve per confrontare alternative o partire da un requisito di progetto.

Funzioni principali:

- applicare un codice prodotto di partenza
- confrontare due o tre codici
- generare una comparazione PDF
- visualizzare alternative consigliate
- inviare prodotti selezionati al carrello offerta

Flusso consigliato:

1. Inserire un codice sorgente in `Project requirement`.
2. Premere `Apply Code`.
3. Analizzare gli abbinamenti consigliati.
4. Inserire codici in `COMPARE OPTIONS`.
5. Premere `Compare`.
6. Aggiungere al carrello i prodotti da proporre.

Nota: le opzioni di ordinamento per prezzo sono visibili solo agli amministratori.

### Carrello offerta

Il carrello offerta serve per preparare una proposta di progetto.

Funzioni principali:

- inserire nome progetto
- vedere azienda associata all'account
- indicare stato progetto
- aggiungere note progetto
- inserire contractor e consultant
- aggiungere prodotti da codice
- modificare quantita', riferimento e note per riga
- salvare offerte personali
- riaprire offerte salvate
- esportare riepilogo offerta
- esportare pacchetto schede tecniche

Flusso consigliato:

1. Aprire `/frontend/quote.html`.
2. Compilare `Project name`.
3. Selezionare `Project status`.
4. Aggiungere prodotti da Finder, Tools o codice manuale.
5. Verificare quantita' e note.
6. Salvare l'offerta.
7. Esportare PDF o datasheet quando serve condividerli.

### Cookie e analytics

La piattaforma mostra una scelta cookie. Gli eventi analytics vengono registrati solo dopo consenso esplicito. Il consenso puo' essere modificato dalle preferenze cookie.

### Cambio password

1. Aprire `/frontend/admin.html`.
2. Con ruolo `user` viene mostrata solo la sezione `Password`.
3. Inserire password attuale.
4. Inserire nuova password e conferma.
5. Salvare.

## Pannello IT

### Scopo del profilo IT

Il profilo IT serve per gestire configurazioni tecniche operative, soprattutto sicurezza browser, dominio, sessioni ed email.

Accesso:

- `/frontend/admin.html`

Sezioni visibili:

- Settings
- Password

Sezioni non visibili:

- Users
- Quotes
- Analytics
- Catalog health
- Release changes
- Administration
- Scoring

### Settings disponibili per IT

Il profilo IT vede le impostazioni disponibili in `Settings`, ma non puo' modificare lo `Scoring`.

Categorie principali:

- Website
- Email

Possibili impostazioni Website:

- `DISANO_STORE_IDS`
- `DISANO_LANG_ID`
- `APP_DOMAIN`
- `CORS_ALLOWED_ORIGINS`
- `AUTH_TOKEN_EXPIRE_MINUTES`
- `AUTH_REFRESH_TOKEN_EXPIRE_DAYS`
- `AUTH_COOKIE_SECURE`
- `AUTH_COOKIE_SAMESITE`

Possibili impostazioni Email:

- `SMTP_HOST`
- `SMTP_PORT`
- `SMTP_USERNAME`
- `SMTP_PASSWORD`
- `SMTP_FROM_EMAIL`

### Come leggere una impostazione

Ogni card mostra:

- nome leggibile
- chiave tecnica
- descrizione
- stato `Configured` o `Not set`
- indicazione `Hot apply` o `Restart needed`
- valore mascherato se segreto

Significato:

- `Hot apply`: il sistema prova a usare il valore subito dopo il salvataggio
- `Restart needed`: il valore viene salvato, ma serve restart o redeploy per effetto completo
- `Masked`: il valore e' sensibile; lasciando vuoto il campo non viene cambiato

### Modificare una impostazione

Procedura consigliata:

1. Aprire `Settings`.
2. Cercare la card desiderata.
3. Annotare il valore attuale o lo stato configurato.
4. Inserire il nuovo valore.
5. Premere `Save`.
6. Leggere il messaggio di conferma o errore.
7. Eseguire un test operativo.
8. Se la card indica `Restart needed`, pianificare restart o redeploy.

Regola pratica:

- cambiare una sola impostazione sensibile per volta
- testare subito dopo ogni modifica
- non modificare dominio, CORS, cookie, token e SMTP insieme nella stessa operazione

### Test email SMTP

Il profilo IT puo' usare il box `Email test`.

Uso:

1. Aprire `Settings`.
2. Inserire un indirizzo destinatario.
3. Premere `Send test email`.
4. Verificare la ricezione.

Usare questo test dopo modifiche a:

- `SMTP_HOST`
- `SMTP_PORT`
- `SMTP_USERNAME`
- `SMTP_PASSWORD`
- `SMTP_FROM_EMAIL`

### Impostazioni critiche

Da trattare con particolare attenzione:

- `APP_DOMAIN`: influenza dominio pubblico e link applicativi
- `CORS_ALLOWED_ORIGINS`: influenza quali frontend possono chiamare il backend
- `AUTH_COOKIE_SECURE`: in produzione deve essere coerente con HTTPS
- `AUTH_COOKIE_SAMESITE`: influenza il comportamento browser dei cookie
- `SMTP_PASSWORD`: secret sensibile

### Cambio password IT

1. Aprire la sezione `Password`.
2. Inserire password corrente.
3. Inserire nuova password e conferma.
4. Salvare.

## Pannello Marketing

### Scopo del profilo Marketing

Il profilo Marketing serve per controllare la qualita' del catalogo visibile, consultare le modifiche di release e gestire solo le impostazioni Website autorizzate.

Accesso:

- `/frontend/admin.html`

Sezioni visibili:

- Catalog health
- Release changes
- Settings
- Password

Sezioni non visibili:

- Users
- Quotes
- Analytics
- Administration
- Scoring
- Email test

### Catalog health

La sezione `Catalog health` mostra la qualita' del dataset caricato.

Indicatori principali:

- numero prodotti
- famiglie uniche
- produttori unici
- prodotti con prezzo
- copertura dei campi
- famiglie principali
- problemi rilevati
- ultimi file importati

Uso consigliato:

1. Aprire `Catalog health`.
2. Controllare i valori di riepilogo.
3. Verificare `Field coverage` per capire quali campi sono incompleti.
4. Controllare `Detected issues`.
5. Segnalare al data owner eventuali problemi su famiglie, prezzi o campi tecnici.

Nota: il Marketing puo' vedere lo stato del catalogo, ma l'import PIM, family map e price list e' disponibile solo agli admin.

### Release changes

La sezione `Release changes` mostra le modifiche dell'ultima release catalogo rispetto alla precedente.

Indicatori principali:

- prodotti modificati totali
- prodotti aggiunti
- prodotti cambiati
- prodotti rimossi
- lista delle ultime modifiche
- campi modificati per prodotto

Azioni:

- premere refresh per aggiornare i dati
- esportare CSV con `Export release CSV`

Uso consigliato:

1. Aprire `Release changes` dopo un aggiornamento catalogo.
2. Controllare quanti prodotti sono stati aggiunti, cambiati o rimossi.
3. Aprire il dettaglio delle modifiche principali.
4. Esportare CSV se serve condividerlo internamente.

### Settings Website per Marketing

Il Marketing vede solo la categoria `Website` delle impostazioni.

Impostazioni visibili:

- `DISANO_STORE_IDS`
- `DISANO_LANG_ID`
- `APP_DOMAIN`
- `CORS_ALLOWED_ORIGINS`
- `AUTH_TOKEN_EXPIRE_MINUTES`
- `AUTH_REFRESH_TOKEN_EXPIRE_DAYS`
- `AUTH_COOKIE_SECURE`
- `AUTH_COOKIE_SAMESITE`

Uso consigliato:

- modificare direttamente solo impostazioni concordate con IT
- usare `DISANO_STORE_IDS` e `DISANO_LANG_ID` per configurazioni contenuto/lookup se approvate
- non modificare dominio, CORS o cookie senza coordinamento IT

Attenzione:

- alcune impostazioni Website sono tecniche e possono impattare login, sicurezza o raggiungibilita' del sito
- se una card mostra `Restart needed`, il cambio non va considerato operativo finche' IT non completa restart o redeploy

### Cambio password Marketing

1. Aprire `Password`.
2. Inserire password corrente.
3. Inserire nuova password e conferma.
4. Salvare.

## Errori comuni e risoluzione

| Problema | Possibile causa | Azione consigliata |
|---|---|---|
| Login non riuscito | email o password errata | verificare credenziali o usare password reset |
| Account in attesa | richiesta non approvata | attendere approvazione da admin/director |
| Account rifiutato | account in stato rejected | contattare amministratore |
| Finder non mostra risultati | filtri troppo restrittivi | usare `Reset` e riprovare con meno filtri |
| Tools non accessibile per IT | comportamento previsto | usare `/frontend/admin.html#settingsSection` |
| Marketing non vede utenti o quote | comportamento previsto | il ruolo Marketing non ha accesso a gestione utenti e quote |
| Modifica settings non efficace | setting con `Restart needed` | pianificare restart/redeploy |
| Email non arriva | SMTP non configurato o bloccato | usare Email test e verificare dati SMTP |

## Buone pratiche

Utente normale:

- partire da una ricerca ampia e restringere con filtri
- salvare le offerte prima di esportarle
- usare note progetto e note riga per non perdere contesto

IT:

- modificare una configurazione sensibile alla volta
- testare login, reset password ed email dopo modifiche tecniche
- coordinare ogni cambio `Restart needed`

Marketing:

- controllare `Catalog health` dopo aggiornamenti dati
- esportare `Release changes` quando serve validare una release
- non modificare parametri tecnici Website senza accordo IT

## Riferimenti interni

Documenti collegati:

- `Backend/ADMIN_PANEL_DOCUMENTATION.md`
- `Backend/ADMIN_SETTINGS_IT_GUIDE_IT.md`
- `Backend/ADMIN_SETTINGS_REFERENCE.md`

File applicativi principali:

- `Backend/frontend/index.html`
- `Backend/frontend/tools.html`
- `Backend/frontend/quote.html`
- `Backend/frontend/admin.html`
- `Backend/frontend/assets/auth.js`
- `Backend/app/auth_router.py`
- `Backend/app/admin_settings.py`
