# Configurazione OAuth2 / SSO per Laiting

Questo documento e' destinato all'IT per configurare l'accesso OAuth2/OIDC dell'app Laiting tramite Microsoft Entra ID.

## Stato Applicazione

L'app e' gia' predisposta lato backend e frontend per OAuth2/OIDC.

L'utente con ruolo `it` puo' accedere al pannello:

```text
/frontend/admin.html#settingsSection
```

e configurare i parametri OAuth2 nella categoria `Security`.

Il ruolo `it` puo' modificare i settings tecnici, ma non puo' accedere alle impostazioni di scoring o alle funzioni amministrative complete.

## Redirect URI

Registrare in Microsoft Entra ID il seguente redirect URI di produzione:

```text
https://laiting.disano.it/auth/oauth/callback
```

Per eventuali test locali:

```text
http://127.0.0.1:8000/auth/oauth/callback
```

## Configurazione Microsoft Entra ID

Creare una App Registration dedicata, ad esempio:

```text
Laiting
```

Impostazioni consigliate:

- account type: single tenant, se l'accesso deve essere limitato agli utenti dell'organizzazione;
- platform: Web;
- redirect URI: `https://laiting.disano.it/auth/oauth/callback`;
- protocollo: OAuth2 Authorization Code Flow con OpenID Connect;
- scope applicativi usati dall'app: `openid profile email`.

Dopo la creazione recuperare:

- Directory tenant ID;
- Application client ID;
- Client secret value.

Nota: copiare il valore del client secret al momento della creazione, non il Secret ID.

## Settings Da Inserire Nel Pannello Laiting

Accedere con utente ruolo `it`, aprire `Settings`, categoria `Security`, e valorizzare:

| Setting | Valore atteso |
|---|---|
| `OAUTH2_ENABLED` | `true` |
| `OAUTH2_PROVIDER_NAME` | `Microsoft Entra ID` |
| `OAUTH2_TENANT_ID` | Directory tenant ID |
| `OAUTH2_CLIENT_ID` | Application client ID |
| `OAUTH2_CLIENT_SECRET` | Client secret value |
| `OAUTH2_REDIRECT_URI` | `https://laiting.disano.it/auth/oauth/callback` |
| `OAUTH2_ALLOWED_DOMAINS` | dominio email ammesso, es. `disano.it` |
| `OAUTH2_AUTO_APPROVE` | `true` oppure `false`, in base alla policy IT |
| `OAUTH2_ADMIN_EMAILS` | email degli utenti che devono diventare admin app |
| `LOCAL_LOGIN_ENABLED` | `false` dopo collaudo SSO |
| `LOCAL_SIGNUP_ENABLED` | `false` dopo collaudo SSO |

Durante il primo collaudo si consiglia di lasciare temporaneamente:

```text
LOCAL_LOGIN_ENABLED=true
LOCAL_SIGNUP_ENABLED=true
```

In questo modo resta disponibile il fallback locale se la configurazione Entra ID non e' ancora completa.

Una volta validato l'accesso SSO, impostare:

```text
LOCAL_LOGIN_ENABLED=false
LOCAL_SIGNUP_ENABLED=false
```

## Comportamento Utenti

Al primo login OAuth2:

- l'app legge l'identita' dal token OpenID Connect;
- usa l'email come identificativo utente;
- crea o aggiorna l'utente interno Laiting;
- assegna il ruolo di default `user`, salvo email presenti in `OAUTH2_ADMIN_EMAILS`;
- mantiene i ruoli applicativi Laiting per autorizzazioni interne.

Se `OAUTH2_AUTO_APPROVE=true`, i nuovi utenti SSO vengono approvati automaticamente.

Se `OAUTH2_AUTO_APPROVE=false`, l'utente viene creato ma resta in stato `pending` fino ad approvazione da parte di un admin/director.

## Verifica Funzionale

Dopo aver salvato i settings:

1. Aprire l'app.
2. Verificare che sia visibile il pulsante `Accedi con SSO Microsoft Entra ID`.
3. Accedere con un account del dominio ammesso.
4. Confermare che l'app rientri correttamente su:

```text
https://laiting.disano.it/auth/oauth/callback
```

5. Verificare da pannello utenti che l'utente sia stato creato o aggiornato.
6. Disattivare login e signup locali solo dopo collaudo positivo.

## Note Sicurezza

- Il client secret e' trattato come setting segreto e viene mascherato nel pannello.
- Il callback OAuth2 valida lo `state` per protezione anti-CSRF.
- In produzione il token OpenID Connect viene validato tramite le chiavi pubbliche JWKS del provider.
- I cookie applicativi restano `httpOnly`; il frontend non gestisce direttamente access token OAuth2.

## Dati Necessari All'App

Per completare la configurazione servono:

- Tenant ID;
- Client ID;
- Client Secret;
- dominio email consentito;
- lista email amministratori app;
- conferma se i nuovi utenti SSO devono essere approvati automaticamente o manualmente.
