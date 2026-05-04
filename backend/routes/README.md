# routes/

Cartella predisposta per il refactoring di main.py (~3500 righe in router separati).

## Struttura prevista

- configurazione.py    ruoli, dipendenti, competenze, fasi catalogo
- pipeline.py          progetti, fasi
- gantt.py             tasks, anteprima impatto, modifiche, pianificazione
- ai.py                agent/chat, suggerisci, verifica, analisi-gantt, simulazione
- consuntivazione.py   consuntivi, segnalazioni, attivita interne
- economia.py          margini, costi
- risorse.py           heatmap saturazioni, suggerisci bilanciamento
- dashboard.py         KPI, home

## Procedura per estrarre un router

1. Crea routes/dominio.py con un APIRouter:
   - prefix="/api/dominio", tags=["Dominio"]
   - import di get_current_user, require_manager da deps
   - import di Utente da auth_routes

2. Sposta gli endpoint da main.py a routes/dominio.py.
   Rimuovi il prefix dai path: @app.get("/api/dominio/foo") diventa @router.get("/foo").

3. In main.py aggiungi:
   from routes import dominio
   app.include_router(dominio.router)

4. Test: python scripts/audit_permessi.py deve continuare a dare 0 missing.
   Lo script va aggiornato per leggere anche da routes/.

5. Test funzionale: chiamata curl a un endpoint estratto deve dare la stessa risposta di prima.

6. Commit: un router alla volta, mai grossi rifacimenti in un commit unico.

## TODO

- Aggiornare scripts/audit_permessi.py per analizzare anche file in routes/.
- Decidere ordine di estrazione: dal piu piccolo (es. segnalazioni, agent/status) al piu grande (es. consuntivazione).

## Riferimenti

- HANDOFF_v12.1.md sezione "Refactoring main.py" per piano completo
- AUTH_MODEL.md per il blueprint permessi
