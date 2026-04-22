# Checklist Pre-Consegna (Software House)

## A. Codice e Repository
- [ ] Repository aggiornato e avviabile da clone pulito
- [ ] Nessun file temporaneo/backup inutile committato
- [ ] Branch di consegna definito (es. `handover/v1`)
- [ ] Tag versione consegna creato (es. `handover-2026-03`)

## B. Sicurezza e Segreti
- [ ] Nessuna API key nel codice frontend
- [ ] `.env` reale escluso dalla consegna
- [ ] Rimossi token/codici sensibili da file testuali
- [ ] Verificato `.gitignore` per segreti e artefatti

## C. Documentazione
- [ ] README tecnico handover presente e aggiornato
- [ ] Lista endpoint principali presente
- [ ] Istruzioni setup locale validate da zero
- [ ] Architettura e flussi Finder/Comparison/Quote descritti

## D. Configurazione e Dati
- [ ] Percorsi PIM/family map/price list documentati
- [ ] Disponibile dataset demo/sanitizzato per test
- [ ] Dipendenze allineate (`requirements.txt`)
- [ ] Runtime config documentata (`config/runtime_config.txt`)

## E. Test Funzionali Minimi
- [ ] Finder: ricerca base funzionante
- [ ] Finder: filtri manuali funzionanti
- [ ] Analyze files (PDF/immagine) funzionante
- [ ] Compare: popolamento slot e confronto funzionante
- [ ] Quote: add/remove/qty/notes funzionante
- [ ] Quote: add by code + autocomplete funzionante
- [ ] Export CSV/PDF/ZIP funzionanti

## F. Stabilita e Qualita
- [ ] Backend avvia senza errori (`server.bat` o uvicorn)
- [ ] Nessun errore bloccante in console browser
- [ ] Verifica encoding testi multilingua (no mojibake)
- [ ] Verifica session storage/navigation Finder <-> Comparison

## G. Deploy e Operativita
- [ ] Processo deploy documentato
- [ ] HTTPS/reverse proxy definiti
- [ ] Strategia backup dati definita
- [ ] Piano monitoraggio errori definito
- [ ] Piano rollback definito

## H. Handover Contrattuale
- [ ] Perimetro supporto tecnico definito (correttiva/evolutiva)
- [ ] SLA e tempi presa in carico definiti
- [ ] Ownership IP/licenza codice formalizzata
- [ ] Accessi ambienti (dev/stage/prod) censiti

## I. Pacchetto da Inviare alla Software House
- [ ] Codice sorgente completo (zip o accesso git)
- [ ] README handover + checklist
- [ ] Env example (senza segreti)
- [ ] Dataset test e credenziali demo (se previste)
- [ ] Elenco issue note / backlog prioritizzato

## J. Go/No-Go
- [ ] Tutti i blocchi A-I completati
- [ ] Approvazione finale interna (business + tecnico)
- [ ] Data ufficiale handover confermata


