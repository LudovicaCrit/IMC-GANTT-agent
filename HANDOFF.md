# IMC-Group GANTT Agent — Handoff v4 (25 marzo 2026, sera)

## Per riprendere
Leggi questo file e il NOTE_AFFINAMENTO.md. Questa è Ludovica, stagista IA back-end a IMC-Group (~15 persone, sedi Milano e Puglia). Il progetto è commissionato da Vincenzo (capo). Repo GitHub: https://github.com/LudovicaCrit/IMC-GANTT-agent

Le chat precedenti:
- Chat 1 (Streamlit → React): https://claude.ai/chat/c9fb06c4-4297-4e7e-b3c5-a4fdc0e5ba29
- Chat 2 (React completo): https://claude.ai/chat/089578cf-0635-45e8-bde3-ec67d8e56e4e
- Chat 3 (DB + Approccio B + Pipeline): questa chat

## Stato attuale — Cosa funziona (v0.4)

### Stack
- **Backend**: Python FastAPI (`backend/main.py`) su porta 8000
- **Frontend**: React + Vite + Tailwind CSS (`frontend/`) su porta 3000
- **Database**: SQLite via SQLAlchemy (`backend/imcgroup.db`) — persistente tra riavvii
- **Agente AI**: Gemini 2.5 Flash (chiave: `GEMINI_API_KEY` in `backend/.env`)
- **Prompt**: cartella `backend/prompts/` con file .md separati
- **Fallback**: se il db non esiste, usa `data_legacy.py` in memoria

### Database SQLite (NUOVO — sessione 25 marzo)
- File: `backend/imcgroup.db` (generato da `seed.py`)
- ORM: SQLAlchemy (`backend/models.py`)
- Tabelle: dipendenti, progetti, task, assegnazioni, consuntivi, segnalazioni, pianificazioni_bozza, note_progetto, interventi, presenze_settimanali, spese
- Data layer: `data.py` (router) → `data_db_impl.py` (db) o `data_legacy.py` (fallback)
- Schema PostgreSQL pronto: `backend/schema.sql` — quando si migra a PostgreSQL, cambiare solo DATABASE_URL in `models.py`
- Le modifiche ai dati (aggiungi_task, modifica_task, cambia_stato_progetto) scrivono nel db E ricaricano la cache DataFrame

### Pagine funzionanti (React) — v0.4
1. **Home** — KPI cliccabili, panoramica progetti con progress bar, alert
2. **GANTT** — Visualizzazione, filtro progetto/profilo, auto-zoom, auto-scroll a "Oggi", **export PDF funzionante** (bottone 📥), legenda stati
3. **Analisi e Interventi** — Esplorazione (simulazione ritardo multi-task, GANTT prima/dopo), Interventi (segnalazioni + analisi agente + proposte A/B/C + **bottone Applica con anteprima impatto** — collegato ma non testato)
4. **Risorse** — Heatmap, barre disponibilità, assegnazione task→profilo→persona
5. **Consuntivazione** — Form ore, smart working, assenze, spese, chat Gemini con **Approccio B funzionante** (il dipendente racconta, l'agente mappa le ore, pannello conferma blu precompila il form), segnalazioni automatiche persistenti nel db
6. **Pipeline** — Bandi (countdown), **Da pianificare con strumento GANTT completo** (tabella editabile, dipendenze FS/SS/FF, saturazione dinamica, pannello impatto risorse, **salvataggio bozze persistente nel db**, **"Conferma e avvia" funzionante** — crea task nel db e li mostra nel GANTT principale), Archivio
7. **Economia** — Gauge SVG, analisi agente, tabella riepilogativa

### Approccio B — Consuntivazione (NUOVO — sessione 25 marzo)
Il dipendente racconta al chatbot cosa ha fatto in linguaggio naturale. L'agente:
- Mappa le attività sui task esistenti (usando `task_assegnati` nel contesto)
- Propone ore a grana grossa (multipli di 2h: mezza giornata=4h, giornata=8h, "un po'"=2h)
- Quando il dipendente menziona un collega, propone i task del collega (usando `colleghi_task`)
- Gestisce attività non mappabili chiedendo chiarimento (mai inventando)
- Alla conferma, genera blocco `[MAPPATURA_ORE]` parsato dal backend
- Il frontend mostra pannello blu con riepilogo editabile (Conferma/Correggo io)
- Chat history mantenuta tra i messaggi (passata al backend)
- Coesiste col form manuale — il dipendente sceglie

Testato con successo: mappatura diretta, task scritto informalmente ("iscrizioni" → T041), aiuto collega ("ho aiutato Alessandro con la dashboard"), testo lungo multi-giornata.

Regole prompt affinate: call=8h (lavoro pieno), niente commenti su ore extra, empatia su sovraccarico (non chiedere ore mancanti se il dipendente esprime frustrazione), no sigle (DA FIXARE — l'agente le usa ancora).

### Export PDF GANTT (NUOVO — sessione 25 marzo)
- Endpoint: `GET /api/gantt/export-pdf?progetto_id=P001` (o senza filtro per tutti)
- Modulo: `backend/gantt_pdf.py` (reportlab)
- Barre colorate per stato, header mesi, linea "Oggi", legenda, bande alternate per progetto
- Multi-pagina automatico
- Bottone "📥 Esporta PDF" nella pagina GANTT (rispetta il filtro progetto)

### Backend endpoints chiave
- `GET /api/gantt` — dati GANTT formattati
- `GET /api/gantt/export-pdf` — **NUOVO** genera PDF scaricabile
- `GET /api/segnalazioni` — segnalazioni (dal db se disponibile)
- `POST /api/simulazione/ritardo-multiplo` — simula ritardi
- `POST /api/agent/analisi-gantt` — analisi agente con proposte A/B/C
- `POST /api/agent/chat` — chatbot consuntivazione con **Approccio B** (parsa MAPPATURA_ORE + SEGNALAZIONE, passa chat_history)
- `POST /api/task/anteprima-impatto` — **NUOVO** calcola impatto senza scrivere
- `POST /api/task/applica` — **NUOVO** applica modifiche (crea task, modifica, cambia stato progetto)
- `POST /api/pianificazione/salva-bozza` — **NUOVO** salva bozza nel db
- `GET /api/pianificazione/bozza/{id}` — **NUOVO** carica bozza

### Dati attuali nel db
- 9 progetti originali + App Mobilità Sostenibile (P007 avviato, 10 task creati)
- 8 dipendenti, 69 task totali, ~392 consuntivi
- Pressione: Alessandro 133%, Roberto 106%, Sara 102%

## Cose da fare — PROSSIMI PASSI

### Priorità 1 — Per la demo a Vincenzo (settimana prossima)

#### P1. Fix sigle nel prompt consuntivazione
L'agente scrive ancora T003, T013 nelle risposte. La regola c'è nel prompt ma Gemini non la rispetta sempre. Affinare con esempi più espliciti o aggiungere post-processing nel backend che rimuove le sigle.

#### P2. Bottone "Applica" in Analisi e Interventi — TEST
Il codice c'è (anteprima impatto + conferma), ma non è stato testato end-to-end con l'agente Gemini. Serve: generare un'analisi, verificare che le azioni proposte siano nel formato giusto, applicare e verificare nel GANTT.

#### P3. "Invia consuntivo" che salva nel db
Il bottone è placeholder. Serve endpoint `POST /api/consuntivi/salva` che scriva nella tabella consuntivi. La tabella esiste già nello schema.

#### P4. Export PNG e Excel
PNG: utile per PowerPoint/email. Excel: utile per chi vuole manipolare i dati.

#### P5. Bande cromatiche nel GANTT web
Il GANTT "tutti i progetti" è confusionario — servono bande colorate per raggruppare i task per progetto, come nel PDF.

#### P6. Dettaglio task nella pagina GANTT
Attualmente poco utile. Ripensare: forse un pannello laterale con info task al click sulla barra?

#### P7. Diversificazione dati
Clienti nazionali/internazionali (UBAE, Reale Mutua, Duferco, Boggi). 12-15 dipendenti simulati.

### Priorità 2 — Importanti ma non bloccanti

#### P8. IA verifica pianificazione (il placeholder in basso in Pipeline)
Ludovica ha identificato il caso d'uso perfetto: task orfani (senza successori), dipendenze mancanti, stime irrealistiche. Il task "Integrazione bike/car sharing" non ha successori — un'IA dovrebbe segnalarlo. Prompt da scrivere.

#### P9. IA suggerisci task (il placeholder in alto in Pipeline)
Descrivere il progetto → l'IA propone struttura task/fasi/ore/profili. Utile ma non critico.

#### P10. Restyling UI
L'interfaccia sembra ancora una demo. Per un prodotto vendibile serve: tipografia, spaziatura, colori raffinati, micro-interazioni. Usare lo skill frontend-design.

#### P11. Placeholder "Ricordamelo dopo" in Consuntivazione
Non fa nulla. O lo rimuoviamo o lo colleghiamo a un promemoria.

### Priorità 3 — Futuro

#### P12. MCP — integrazione Teams/Outlook
Notifiche, promemoria, raccolta info da email. Da progettare con Vincenzo.

#### P13. Streaming SSE per risposte agente
Per risposte lunghe dell'agente, mostrare il testo man mano. Migliora l'UX.

#### P14. Multi-persona per task (I3 del vademecum)
Un task può essere assegnato a più persone. La tabella `assegnazioni` nel db lo supporta già.

#### P15. Saturazione settimanale reale (I1 del vademecum)
Calcolo settimana per settimana invece di media piatta. Critico per il valore del prodotto.

#### P16. Espansione progetti in corso (D2 del vademecum)
Aggiungere fasi/task a un progetto attivo senza ricrearlo.

#### P17. Fase pilota e rodaggio (E1-E2 del vademecum)
Piano graduale: settimane 1-4 solo compilazione, 5-8 report settimanali, 9+ segnalazioni attive.

#### P18. Documento architetturale per Vincenzo

## Vincoli e decisioni prese

### Dalla sessione del 25 marzo (nuove)
- Le ore sono un dettaglio burocratico — il sistema parla la lingua delle persone e traduce silenziosamente
- Call/riunioni = lavoro a tutti gli effetti (8h giornata con call)
- Non commentare ore extra — non sappiamo come funzionano gli straordinari in IMC-Group
- Se il dipendente esprime frustrazione, NON chiedere delle ore mancanti
- L'agente NON riassegna — la realtà è che il management "chiama a raccolta" le persone e redistribuisce il focus, non sposta pedine
- La priorità nei progetti è una decisione del management (alta/media/bassa), non calcolata — serve come contesto per l'agente
- SQLite per sviluppo, PostgreSQL per produzione — cambia solo DATABASE_URL
- get_dipendente e get_progetto sono safe — restituiscono "Non assegnato" se l'id è vuoto

### Dalla sessione precedente (confermate)
- L'agente NON critica l'organico — propone soluzioni con le risorse esistenti
- L'agente NON usa sigle tecniche (D001, T003) — DA ENFORCIARE MEGLIO
- La simulazione ritardi vive in Analisi e Interventi, NON nel GANTT
- Il GANTT è solo visualizzazione — separazione netta osservare/esplorare/intervenire
- Le percentuali di saturazione sono il tessuto connettivo tra GANTT
- I sottotask esistono come note strutturate dentro i task, non nel GANTT
- Fase pilota: l'agente parte soft e si attiva progressivamente
- Il prodotto ha potenziale commerciale (Svizzera) — va costruito per impressionare

## Domande per Vincenzo — da portare alla riunione
(Lista invariata dal handoff v3 — vedi sezione dedicata)
Aggiunta: "Come gestite le ore extra/straordinari? Il sistema deve tracciarli in modo specifico?"

## Struttura file attuale
```
Use_Case_3_GANTT/
├── backend/
│   ├── main.py              (FastAPI — tutti gli endpoint, v0.4)
│   ├── agent.py             (Gemini, contesto con task_assegnati + colleghi_task)
│   ├── data.py              (router: db o legacy)
│   ├── data_db_impl.py      (implementazione database — NUOVO)
│   ├── data_legacy.py       (fallback in memoria — ex data.py)
│   ├── models.py            (modelli SQLAlchemy — NUOVO)
│   ├── seed.py              (popola il db — NUOVO)
│   ├── gantt_pdf.py          (generazione PDF GANTT — NUOVO)
│   ├── schema.sql           (schema PostgreSQL — NUOVO, documentazione)
│   ├── imcgroup.db          (database SQLite — NUOVO, NON committare)
│   ├── .env                 (GEMINI_API_KEY=...)
│   └── prompts/
│       ├── consuntivazione.md   (v2 con Approccio B)
│       └── analisi_segnalazioni.md
├── frontend/
│   ├── index.html
│   ├── vite.config.js
│   ├── package.json
│   └── src/
│       ├── main.jsx
│       ├── App.jsx           (routing + sidebar, 7 pagine, v0.3)
│       ├── api.js            (tutte le chiamate API, v0.4)
│       ├── index.css
│       └── pages/
│           ├── Home.jsx
│           ├── Gantt.jsx             (export PDF, v0.4)
│           ├── AnalisiInterventi.jsx (bottone Applica con anteprima, v0.4)
│           ├── Risorse.jsx
│           ├── Consuntivazione.jsx   (Approccio B, v0.4)
│           ├── Pipeline.jsx          (conferma+avvia, bozze, v0.4)
│           └── Economia.jsx
├── .venvu/
├── .gitignore               (aggiungere: imcgroup.db, __pycache__)
├── NOTE_AFFINAMENTO.md
└── HANDOFF.md
```

## Come avviare
```bash
# Terminal 1 — Backend
cd backend
source ../.venvu/bin/activate
pip install sqlalchemy reportlab  # solo la prima volta
python seed.py                    # solo la prima volta (crea e popola il db)
python3 -m uvicorn main:app --reload --port 8000
# Deve stampare: "✓ Database attivo — dati persistenti"

# Terminal 2 — Frontend
cd frontend
npm run dev
```
Apri http://localhost:3000

## Cosa è stato fatto nella sessione del 25 marzo (mattina + pomeriggio)

### Mattina
1. Schema database PostgreSQL completo (11 tabelle + vista + trigger)
2. Approccio B consuntivazione — prompt v2, backend (parsing MAPPATURA_ORE + colleghi_task), frontend (pannello conferma blu)
3. Test Approccio B: mappatura diretta, task informale, aiuto collega, testo lungo, caso sovraccarico
4. Fix chat_history (l'agente perdeva memoria tra i messaggi)
5. Fix prompt: call=8h, empatia sovraccarico, no commenti ore extra

### Pomeriggio
6. Database SQLite con SQLAlchemy (models.py, seed.py, data_db_impl.py)
7. Data layer con fallback (data.py router → db o legacy)
8. Endpoint applica/anteprima impatto + salvataggio bozze
9. Pipeline "Conferma e avvia" → task nel GANTT principale (funzionante!)
10. Fix reload DataFrame (le modifiche si propagano agli endpoint)
11. Fix get_dipendente safe (gestisce id vuoti)
12. Fix conversione nome→id dipendente nella conferma progetto
13. Rimosso pannello impatto ridondante in Pipeline
14. Export PDF GANTT con reportlab (multi-pagina, bande progetto, legenda)
15. Handoff v4
