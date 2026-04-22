# Product Finder - README Handover (Software House)

## 1. Obiettivo
Questa applicazione supporta:
- ricerca prodotti (`Finder`)
- confronto tecnico e alternative (`Comparison tool`)
- gestione preventivo (`Quote`)
- parsing requisiti da testo, PDF e immagine (AI + parser locale)

Repository root operativo: `Backend/`.

## 2. Stack Tecnologico
- Backend: `FastAPI` (Python)
- Frontend: HTML/CSS/JS statici serviti dal backend
- Storage principale: SQLite (con fallback DataFrame)
- AI: integrazione OpenAI per parsing/intenti/vision

Percorsi principali:
- Backend API: `Backend/app/main.py`
- Frontend Finder: `Backend/frontend/index.html`
- Frontend Comparison: `Backend/frontend/tools.html`
- Frontend Quote: `Backend/frontend/quote.html`
- Config runtime: `Backend/config/runtime_config.txt`

## 3. Requisiti Ambiente
- Python 3.11+ (consigliato 3.12)
- pip
- Accesso al file PIM Excel in `Backend/data/`
- Variabile `OPENAI_API_KEY` per funzioni AI

Dipendenze Python: `Backend/requirements.txt`

## 4. Avvio Locale (Windows)
Da cartella `Backend/`:

```bat
server.bat
```

`server.bat`:
- verifica dipendenze
- installa eventuali mancanti
- avvia `uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload`

URL locale tipico:
- `http://localhost:8000/`

## 5. Variabili e Segreti
Non condividere mai segreti reali.

Minimo necessario:
- `OPENAI_API_KEY`
- opzionali: `PIM_XLSX`, `FAMILY_MAP_XLSX`, `PRICE_LIST_XLSX`, flags runtime

File sensibili da non consegnare:
- `Backend/.env` reale
- file con codici ngrok o token

## 6. Dati e Import
La base prodotti deriva dal PIM Excel.

Note importanti:
- Il dataset ricerca principale esclude alcune righe non-luminaire (es. accessori) in fase loader.
- La funzione autocomplete codici in Quote include anche la lista codici originale del PIM (accessori inclusi).

Endpoint utili:
- `POST /search`
- `POST /facets`
- `POST /compare-products`
- `POST /compare-spec-products`
- `POST /quote/export-pdf`
- `POST /quote/datasheets-zip`
- `GET /codes/suggest`

## 7. Flusso UI
1. Finder:
- query + filtri
- analisi PDF/immagine per estrazione requisiti
- risultati exact/similar

2. Comparison tool:
- confronto fino a 3 slot
- sheet differenze campi
- integrazione da Finder

3. Quote:
- aggiunta da Finder o da codice diretto (autocomplete)
- export CSV/PDF/ZIP datasheet

## 8. Stato Funzionale Attuale
Incluso:
- persistenza stato Finder/Tools in sessionStorage
- chips AI/standard separate
- compare preview in header Finder
- import file unificato (`Analyze files`)
- aggiunta diretta a Quote da codice con autocomplete

Da verificare in audit esterno:
- copertura test e regressioni UI
- gestione encoding i18n legacy in alcune pagine
- hardening sicurezza e logging
- performance su dataset PIM grandi

## 9. Deploy (linee guida)
Minimo:
- host Python con uvicorn dietro reverse proxy (nginx/caddy)
- HTTPS obbligatorio
- gestione segreti via env del server
- backup periodico di DB/data
- monitoraggio errori backend

## 10. Ownership e Supporto
Per presa in carico software house, concordare:
- proprieta intellettuale (IP) del codice
- SLA manutenzione correttiva/evolutiva
- tempi di intervento
- processo rilascio (branching, review, test, deploy)

## 11. Contatti Handover
Inserire qui:
- referente business
- referente tecnico interno
- canale per incidenti urgenti


