# IMC-Group GANTT Agent — Sistema di gestione progetti e settimana lavorativa

Strumento di **consuntivazione** dell'operato dei dipendenti, **censimento progetti**
(anagrafica generale) e **controllo marginalità** per IMC Group (Milano).
Non un project management classico, non un timesheet: un sistema che ricostruisce
la **settimana lavorativa completa** — progetti commerciali, attività interne,
formazione — con assistente IA a supporto di pianificazione e simulazione.

La sua particolarità è la **dinamicità**: intercetta cosa succede in azienda
in tempo reale, non solo registra a posteriori.

**Stato:** R1 in sviluppo. Target consegna 17 giugno 2026 (fine stage IT
sviluppatrice). Backend al 100%, frontend in completamento sulle 4 pagine principali.

**Contesto:** Progetto interno IMC Group, sviluppato in fase di stage IA back-end
(gennaio-giugno 2026). R2 a settembre 2026 (ripreso da Roberto Pezzuto, Manager IT).


## Cosa fa il sistema

Il sistema risponde a **tre esigenze concrete** del management IMC Group:

### 1. Consuntivazione dell'operato (richiesta di Vincenzo)
Ogni settimana, ogni dipendente registra le ore dedicate ai task dei propri progetti,
alle attività interne (formazione, prevendita, monitoraggio bandi), e alle assenze.
Il sistema raccoglie, valida e aggrega questi dati per fornire una visione completa
della settimana lavorativa aziendale.

### 2. Censimento dei progetti (anagrafica generale)
Ogni progetto ha la sua anagrafica completa: cliente, stato, tipologia
(ordinario o bando), Project Manager, fasi, task, budget ore, valore contratto,
scadenze, lezioni apprese. Lo strumento mantiene la **storia organica** di ogni
progetto dal momento della pipeline fino al completamento.

### 3. Controllo marginalità (richiesta di Roberto)
Per ogni progetto, il sistema calcola la marginalità basata sul costo orario reale
dei dipendenti coinvolti (formula: `valore_contratto - Σ(ore_lavorate × costo_orario)`).
Roberto vuole che questo dato sia **visibile e immediato**, per mostrare al management
quanto sovraccaricare le risorse umane porti a un calo della marginalità — un
indicatore che oggi spesso resta implicito.


## Le 4 pagine — dove vive il sistema

Vincenzo Carolla (AD) ha cristallizzato il prodotto in **4 pagine principali**, ognuna
con una funzione netta:

### Home — visione d'insieme
KPI aziendali trasversali. È la prima pagina che vede chi entra: stato dei progetti
attivi, ore consuntivate vs vendute, marginalità aggregata, numero risorse sovraccariche.

### GANTT — stato attuale per fasi
Diagramma temporale di tutti i progetti, raggruppati per fase. Sola lettura.
È il "cruscotto della pianificazione corrente". Il manager vede a colpo d'occhio
chi sta facendo cosa, in quale fase, e se ci sono ritardi.

### Pipeline — creazione di nuovi progetti
Form di creazione di un nuovo progetto, con divisione bando vs ordinario.
Per i bandi: 3 fasi standard fisse (Monitoraggio, Proposal, Project Management),
di cui solo PM ha ore vendute. Per gli ordinari: fasi libere create dal PM.

### Tavolo di Lavoro — evoluzione dinamica
Spazio dove il manager modifica progetti in corso, riassegna task, simula impatti
di ritardi o anticipi tramite l'assistente IA. È il "punto di adattamento":
quando la realtà cambia, qui si aggiorna il sistema.


## Filosofia: la settimana intera, non solo i progetti

Il principio architetturale fondante (intuizione condivisa con Vincenzo) è che il
sistema **non si limita ai progetti commerciali**. La settimana lavorativa di un
dipendente IMC contiene anche:

- **Attività interne**: formazione, riunioni, coordinamento (raccolto sotto P010,
  "Attività Interne" come progetto-contenitore)
- **Attività commerciali**: monitoraggio bandi, prevendita, scrittura proposte
  (a sentimento, senza fasi dedicate)
- **Assenze**: ferie, permessi, malattia (con tipo e nota)

Tutto questo viene catturato nello stesso framework. La conseguenza pratica:
quando il sistema dice "Helena questa settimana ha lavorato 38 ore", quella cifra
è **già scomposta** tra progetti, attività interne, assenze. Non serve fare
estrazioni separate da tool diversi.


## Scenario B — chi vede cosa

Il sistema implementa una distinzione netta dei diritti di accesso (consolidata
con Vincenzo e Andrea Morstabilini):

- **User (es. Helena)**: vede solo le proprie cose. Il proprio GANTT, le proprie ore,
  i propri task. Non può vedere chi-fa-cosa di un altro consultant in dettaglio.
- **Manager (es. Vincenzo, Roberto, Cosimo, Ludovica come stagista IA)**: vede
  tutto, può modificare quasi tutto, ha accesso aggregato e individuale.

Non è un'estrema misura di sicurezza: è coerenza con il modo di lavorare di IMC.


## Le entità di dominio

Le entità principali del modello (17 tabelle nel database):

### Dipendente
ID, nome, profilo (job title), ruolo aziendale, ore settimanali contrattuali, costo orario,
competenze (lista piatta di 33 voci tipo "GRC", "DORA", "ARIS"), email per autenticazione.
Riferimento principale per ogni operazione di consuntivazione.

### Progetto
ID, nome, cliente, stato (In esecuzione, Vinto - Da pianificare, Sospeso, Completato),
**tipologia** (ordinario o bando), Project Manager, date, budget ore, valore contratto,
descrizione, scadenza bando (se applicabile), lezioni apprese, note.
Ogni progetto contiene una serie di Fasi.

### Fase
ID, progetto di appartenenza, nome (es. "Analisi", "Sviluppo", "Testing"), ordine,
date, ore vendute, ore pianificate, stato, note.
Unità di pianificazione: in fase di vendita si dichiara "questa fase ha 80 ore vendute".
Ogni fase contiene una serie di Task.

### Task
ID, progetto, fase di appartenenza, nome, stato, date, ore stimate, profilo richiesto,
dipendente assegnato, eventuale predecessore.
Unità di esecuzione: ciò su cui le persone consuntivano effettivamente le ore.

### Consuntivo
Dipendente, task, settimana, ore dichiarate, modalità (sede/remoto), assenze.
Lo stato vivo del lavoro. Ogni venerdì sera (o il lunedì successivo), ogni dipendente
compila i propri consuntivi della settimana appena trascorsa.

### Segnalazione
Tipo, priorità, dipendente, progetto, dettaglio testuale.
Generate automaticamente dal chatbot quando un dipendente dichiara un blocco
("task X non procede perché Y") o uno sforamento, oppure inserite a mano dal manager.

### Cataloghi (Configurazione)
Ruoli aziendali (9 voci), competenze (33 voci), fasi standard (template usati
dalla Pipeline). Gestiti tramite la pagina Configurazione, accessibile solo ai manager.


## Architettura — Stack e moduli

### Stack tecnologico

| Layer | Tecnologia | Versione | Note |
|---|---|---|---|
| Backend | Python + FastAPI | 3.10 + 0.115 | API REST, JWT auth, rate limiting |
| ORM | SQLAlchemy | 2.x | Modelli dichiarativi |
| Database | PostgreSQL | 16.13 | Migrato da SQLite il 6 mag 2026 |
| Migration | Alembic | 1.18.4 | Schema tracciato, niente drop & recreate |
| IA | Gemini (Google) | 2.5 Flash | Assistente di pianificazione e analisi |
| Frontend | React + Vite | 19 + 6 | Tailwind + react-router-dom 7 |
| Auth | JWT + cookie httpOnly | - | Secure, SameSite=Lax, scadenza 8h |

### Pipeline backend — 16 router separati

Il backend è organizzato in **16 router**, ognuno dedicato a un dominio funzionale.
Il file `main.py` è ridotto a 98 righe (entry point puro: imports, app FastAPI,
rate limiter, registrazione router, CORS).

```
main.py (98 r)
 ├── auth_routes.py (3 endpoint /api/auth/*)
 └── routes/ (16 file, 51 endpoint)
     ├── dipendenti.py            # CRUD dipendenti
     ├── progetti.py              # lista progetti
     ├── economia.py              # marginalità
     ├── risorse.py               # carico, suggerisci bilanciamento
     ├── gantt.py                 # vista GANTT + 3 export (PDF/PNG/Excel)
     ├── segnalazioni.py          # lista segnalazioni
     ├── pianificazione.py        # bozze
     ├── consuntivi.py            # consuntivazione (settimana, me, salva)
     ├── tasks.py                 # CRUD task con simulazione impatto
     ├── simulazione.py           # ritardo singolo + cascate
     ├── attivita_interne.py      # P010 contenitore attività non-progetto
     ├── configurazione.py        # CRUD admin (17 endpoint)
     ├── agent.py                 # 6 endpoint IA (chat, analisi, suggerisci, ecc.)
     ├── scenario.py              # motore deterministico simulazioni
     └── fasi.py                  # gestione fasi (in espansione, Blocco 2)
```

### Layer di accesso ai dati — 4 file dedicati

```
models.py (387 r)              # Schema SQLAlchemy: 17 tabelle
data.py (38 r)                 # Router intelligente db/memory (dispatcher)
data_db_impl.py (486 r)        # Implementazione live PostgreSQL
data_legacy.py (580 r)         # Dati grezzi del seed iniziale
seed.py (307 r)                # Setup script per popolare il db
dataframes.py (68 r)           # Helper DataFrame condivisi
```

`data_legacy.py` contiene i dati fittizi credibili (15 dipendenti, 10 progetti,
1282 consuntivi simulati) usati da `seed.py` per popolare il db iniziale. Il nome
è storico: in origine era "modalità memoria di fallback", ma da quando PostgreSQL
è stabile (6 mag 2026) il file ha solo il ruolo di dati seed.


## Struttura del repository

```
~/Azienda/Use_Case_3_GANTT/
├── backend/
│   ├── main.py                       # Entry point (98 r)
│   ├── models.py                     # Schema SQLAlchemy (17 classi)
│   ├── data.py + data_db_impl.py     # Layer dati live
│   ├── data_legacy.py                # Dati grezzi seed
│   ├── seed.py                       # Setup script
│   ├── auth.py + auth_routes.py      # Auth JWT
│   ├── deps.py                       # Dependency: get_current_user, require_manager
│   ├── scenario_engine.py            # Motore deterministico simulazioni
│   ├── agent.py                      # Wrapper Gemini
│   ├── gantt_pdf.py                  # Rendering PDF GANTT
│   ├── utils.py + dataframes.py + contesto.py   # Helper condivisi
│   ├── alembic/                      # Migration tracciate
│   │   ├── env.py
│   │   └── versions/
│   ├── alembic.ini                   # Config Alembic
│   ├── routes/                       # 16 router (51 endpoint)
│   ├── scripts/
│   │   └── audit_permessi.py         # Audit RBAC: verifica protezione endpoint
│   └── .env                          # Config sensibile (gitignored)
└── frontend/
    └── src/
        ├── api.js                    # Client HTTP centralizzato
        ├── App.jsx                   # Routing + sidebar dinamica per ruolo
        ├── contexts/AuthContext.jsx  # Provider auth + bootstrap su /me
        ├── components/
        │   ├── RequireAuth.jsx
        │   ├── RequireManager.jsx
        │   └── FullScreenLoader.jsx
        └── pages/                    # Le 4 pagine + accessori
            ├── Login.jsx + Forbidden.jsx
            ├── Home.jsx
            ├── Gantt.jsx
            ├── Pipeline.jsx
            ├── Tavolo di lavoro       # (in sviluppo)
            ├── Consuntivazione.jsx
            ├── Risorse.jsx
            ├── Economia.jsx
            ├── AnalisiInterventi.jsx
            ├── AttivitaInterne.jsx
            └── Configurazione.jsx
```


## Scelte tecniche principali

### Perché PostgreSQL e non SQLite?

Il prototipo iniziale girava su SQLite — un singolo file, perfetto per dev rapido.
Quando il sistema è stato pensato per l'uso aziendale (15+ utenti concorrenti,
demo settimanali, dati con valore reale), si è migrato a PostgreSQL.

PostgreSQL gestisce concurrent users, ha backup nativi, supporta tipi enum/JSON
con vincoli forti, e la transizione a produzione (server aziendale a settembre)
sarà solo una stringa di connessione nel `.env`. SQLAlchemy è agnostico al dialetto:
il codice non cambia.

### Perché Alembic?

Da un certo punto del progetto in poi, i dati immessi dagli utenti (Helena, Vincenzo,
Cosimo che testano) hanno **valore proprio**: non sono ricostruibili da `seed.py`.
Da quel momento, ogni cambio di schema deve preservare i dati.

Alembic genera automaticamente migration scripts confrontando `models.py` con il
database reale. Ogni script Python ha un ID univoco, sa cosa precede e cosa segue,
e può essere applicato/annullato con un comando. La storia dello schema diventa
parte del repository, esattamente come il codice.

Da quando Alembic è in piedi (6 mag 2026), **niente più drop & recreate** del db.

### Perché 16 router separati e non un unico file?

`main.py` è cresciuto fino a 2780 righe prima del refactoring. Inestricabile per
chi entra. Lo strangler pattern (un router alla volta, audit verde dopo ogni
estrazione) ha prodotto 16 file da ~80-200 righe ciascuno, ognuno con un dominio
funzionale chiaro e un header descrittivo di 70-100 righe (storia, endpoint,
pattern auth, dipendenze).

L'header serve a Roberto: a settembre 2026 quando lui riprenderà il progetto,
ogni file gli racconterà subito cosa fa, perché esiste, da dove viene.

### Perché RBAC duale e non gradi multipli?

IMC ha 15 dipendenti. Una struttura di permessi basata su gruppi multipli con
ereditarietà sarebbe sovradimensionata. La distinzione **manager/user** è
sufficiente per il 99% dei casi e mappa direttamente al modo in cui IMC opera:
i manager (AD, Manager IT, Manager HR, Senior Consultant) coordinano, gli user
(consultant) eseguono e consuntivano.

Per casi in cui un dipendente deve avere visibilità su un progetto specifico
(es. PM del proprio progetto), il `pm_id` su Progetto consente di implementare
ABAC (Attribute-Based Access Control) in R2 senza ristrutturare i ruoli.

### Perché Gemini e non OpenAI o modelli locali?

Gemini 2.5 Flash offre un buon compromesso tra latenza, costo e qualità per i casi
d'uso del progetto: chat di assistenza, analisi GANTT, suggerimento task, verifica
pianificazione, interpretazione scenari. È stato scelto in fase di prototipo per
costi contenuti e API stabili.

In R1 il modello è `google.generativeai` (legacy SDK). Migrazione a `google.genai`
(SDK moderno) prevista in fase di hardening, prima della consegna del 17 giugno.

### Perché un assistente IA e non solo regole deterministiche?

L'IA è **un supporto**, non il core. Le decisioni operative (chi fa cosa, ore,
fasi, budget) sono determinate dal manager — l'IA può proporre, simulare,
analizzare, ma non decidere autonomamente.

Casi d'uso attuali:
- Chat con il dipendente in fase di consuntivazione (raccoglie segnalazioni)
- Analisi del GANTT corrente con commento sulle criticità
- Suggerimento di task simili a uno dato
- Verifica di una pianificazione proposta
- Interpretazione di uno scenario simulato in linguaggio naturale

Tutto il resto (calcolo marginalità, simulazione cascate, redistribuzione carichi)
è implementato in **motori deterministici** (`scenario_engine.py`).


## Setup e utilizzo

### Prerequisiti
- WSL 2 (Ubuntu 24.04 testato)
- Python 3.10+ con venv
- PostgreSQL 16
- Node.js 18+ con npm
- Pacchetti Python: vedere `requirements.txt` (in particolare `fastapi`, `uvicorn`,
  `sqlalchemy`, `psycopg2-binary`, `alembic`, `python-dotenv`, `python-jose`,
  `slowapi`, `google-generativeai`, `pandas`)
- Pacchetti frontend: vedere `frontend/package.json`

### Primo avvio

```bash
# 1. Clona il repository
git clone https://github.com/LudovicaCrit/IMC-GANTT-agent.git
cd IMC-GANTT-agent

# 2. Setup ambiente Python
python3 -m venv .venvu
source .venvu/bin/activate
pip install -r requirements.txt

# 3. Avvia PostgreSQL (in WSL non parte automaticamente)
sudo service postgresql start

# 4. Crea utente e database
sudo -u postgres psql -c "CREATE USER gantt_user WITH PASSWORD 'gantt_dev_2026';"
sudo -u postgres psql -c "CREATE DATABASE gantt_db OWNER gantt_user;"

# 5. Configura .env nel backend (NON committato)
cat > backend/.env << EOF
DATABASE_URL=postgresql://gantt_user:gantt_dev_2026@localhost:5432/gantt_db
JWT_SECRET=<chiave-segreta-da-generare>
JWT_ALGORITHM=HS256
JWT_EXPIRE_HOURS=8
COOKIE_NAME=imc_session
COOKIE_SECURE=False
COOKIE_SAMESITE=lax
GEMINI_API_KEY=<api-key-Google-AI-Studio>
EOF

# 6. Applica le migration Alembic
cd backend
alembic upgrade head

# 7. Popola il db con dati di esempio
python seed.py

# 8. Avvia il backend
python3 -m uvicorn main:app --reload --port 8000

# 9. In altro terminal, avvia il frontend
cd frontend
npm install
npm run dev
# Apre su http://localhost:3000
```

### Avvio quotidiano (dopo il primo setup)

```bash
# Terminal 1 — backend
cd ~/Azienda/Use_Case_3_GANTT/backend
sudo service postgresql start
source ../.venvu/bin/activate
python3 -m uvicorn main:app --reload --port 8000

# Terminal 2 — frontend
cd ~/Azienda/Use_Case_3_GANTT/frontend
npm run dev
```

### Verifica audit (RBAC)

```bash
cd ~/Azienda/Use_Case_3_GANTT/backend
python scripts/audit_permessi.py
```

Atteso: 54 endpoint totali, 0 missing, RBAC duale + Pattern Y intatti.


## Database PostgreSQL

17 tabelle di dominio + 1 di Alembic:

| Tabella | Scopo | Righe attuali (seed) |
|---|---|---|
| `ruoli` | Ruoli aziendali (admin/manager/user mapping) | 9 |
| `competenze` | Catalogo competenze | 34 |
| `dipendenti` | Anagrafica dipendenti | 15 |
| `dipendenti_competenze` | Mapping N:M dipendente↔competenza | 55 |
| `presenze_settimanali` | Sede/remoto/assenze per settimana | 0 (popolato da Helena) |
| `progetti` | Anagrafica progetti | 10 |
| `utenti` | Account login (email + password_hash + ruolo_app) | 4 |
| `fasi` | Fasi per progetto (auto-create dai task in seed) | 36 |
| `fasi_standard` | Template fasi riutilizzabili in Pipeline | 18 |
| `task` | Unità di esecuzione | 70 |
| `assegnazioni` | Mapping N:M task↔dipendenti coinvolti | (variabile) |
| `consuntivi` | Ore dichiarate per task per settimana | 1282 |
| `segnalazioni` | Allarmi (sovraccarico, blocco, sforamento) | 3 |
| `interventi` | Azioni applicate su segnalazioni | 0 (popolato in uso) |
| `note_progetto` | Annotazioni libere su progetti | 0 |
| `pianificazioni_bozza` | Snapshot intermedio di pianificazioni in corso | 0 |
| `spese` | Spese imputate per dipendente/progetto | 0 |
| `alembic_version` | Versione corrente schema | 1 (Alembic baseline) |


## Funzionalità trasversali

### Auth JWT con cookie httpOnly

L'autenticazione usa JSON Web Tokens trasportati in cookie httpOnly + Secure +
SameSite=Lax. Vantaggi:
- Token mai esposto a JavaScript (impossibile estrarre via XSS)
- Non serve gestione manuale lato frontend
- Logout pulito (cookie eliminato dal server)

Login rate-limited: 5 tentativi/minuto per IP + 5 tentativi/minuto per email.
Scadenza token: 8 ore.

### RBAC duale

Implementato con due dependency FastAPI:
- `Depends(get_current_user)`: estrae l'utente dal cookie, ne richiede l'attivazione
- `Depends(require_manager)`: aggiunge il check sul ruolo (`manager` o `admin`)

Distribuzione attuale dei 54 endpoint:
- **MANAGER (admin only)**: 43 endpoint (tutto ciò che è amministrativo)
- **AUTH+FILTRO**: 6 endpoint (l'utente vede ma con filtro: solo le proprie cose)
- **AUTH-ONLY**: 3 endpoint (`/api/consuntivi/me`, `/api/agent/status`, `/api/auth/me`)
- **PUBLIC+RL**: 1 endpoint (`/api/auth/login`, rate-limited)
- **PUBLIC**: 1 endpoint (`/api/auth/logout`)

### Pattern Y (anti-impersonation)

Per le scritture (POST/PATCH/DELETE), il body può contenere `dipendente_id`.
Il backend non si fida del body: verifica che, se l'utente è user (non manager),
il `dipendente_id` nel body coincide con `current_user.dipendente_id`. Altrimenti 403.

Esempi: salvataggio consuntivo, creazione attività interna, chat con l'agent.


## Stato del progetto e roadmap

R1 è suddiviso in **6 blocchi** non-negoziabili per la consegna del 17 giugno:

| # | Blocco | Stima | Stato |
|---|---|---|---|
| 1 | **Fondamenta backend** | 2.5 g | ✅ Chiuso 6 mag (-2 g) |
| 2 | **Macchina delle Fasi** | 3.5 g | ⏳ In corso |
| 3 | **Esperienza utente: Vista Helena + Consuntivazione ridisegnata** | 3.5 g | |
| 4 | **Ciclo vita progetto: Pipeline + Tavolo di Lavoro** | 5.5 g | |
| 5 | **Sistema decisionale: Risorse + Marginalità** | 3.5 g | |
| 6 | **Hardening pre-consegna** | 3 g | |

Buffer fino al 17 giugno: ~6 giorni.

### R2 (settembre 2026, ripreso da Roberto)

- **Avatar vocale Vincenzo "dall'auto"**: il chatbot consuntivazione diventa
  interfaccia vocale per quando Vincenzo è in macchina
- **Layer semantico**: vector DB / MongoDB / Neo4J (decisione tecnica aperta)
- **ABAC** su pm_id (un PM modifica solo i suoi progetti)
- **Marginalità avanzata**: erosione margine da sovraccarico
- **Notifiche Teams**: alert push per blocchi e sforamenti
- **Setup PostgreSQL produzione**: stringa connessione su server aziendale

### R3 (futura)

- **Multi-role groups**: dipendente in più gruppi (es. PM + Sviluppatore)
- **Mobile app dedicata**
- **Reportistica dirigenziale**: PDF mensile per Vincenzo


## Audit di sicurezza

Lo script `backend/scripts/audit_permessi.py` esegue un'analisi statica dei
decoratori in tutti i router per verificare che ogni endpoint abbia una
protezione appropriata. Lanciato dopo ogni modifica al backend.

```bash
cd backend
python scripts/audit_permessi.py
```

Output atteso al 6 mag 2026:
```
Totale endpoint:        54
✓ MANAGER (admin only): 43
✓ AUTH+FILTRO:          6
✓ AUTH-ONLY:            3
✓ PUBLIC+RL (login):    1
✓ PUBLIC (logout/me):   1
⚠️ MISSING:              0
✅ Tutti gli endpoint sono protetti correttamente!
```

In caso di endpoint senza protezione, lo script restituisce exit code 1 (utile
per CI/CD futuro).


## Test

I test unitari sono in `backend/tests/` (in espansione durante il Blocco 6).
Per ora la validazione è basata su:
- **Audit**: protezione di tutti gli endpoint
- **Test runtime via curl**: dopo ogni modifica, login + chiamata endpoint critico
- **Test SQLAlchemy**: query dirette sul db per verificare i dati

In Blocco 6 (hardening) si aggiungeranno:
- Stress test (Locust o k6, ~10 scenari)
- Smoke test E2E (Helena + Ludovica + manager generico)
- Test di rollback Alembic


## Convenzioni di sviluppo

### Conventional Commits in italiano
```
refactor(backend): estratto router fasi (ULTIMO router del refactoring)

[corpo del commit articolato 10-30 righe, con storia,
test certificati, motivazione]
```

### Niente più drop & recreate
Da quando Alembic è in piedi (6 mag 2026), ogni cambio di schema:
1. Modifica `models.py`
2. `alembic revision --autogenerate -m "messaggio"`
3. Lettura attenta dello script generato
4. `alembic upgrade head`
5. Lo script va in git (è una migration committed)

### Header descrittivi nei router
Ogni router ha un header di 70-140 righe con SCOPO, ENDPOINT ESPOSTI, DETTAGLIO
ENDPOINT, PATTERN AUTH, DIPENDENZE, NOTE TECNICHE, TODO, STORIA. È documentazione
viva che cresce con il file.

### Principio architetturale
> Le scelte architetturali (organizzazione file, prefissi URL, separation of
> concerns) hanno priorità sulle coincidenze storiche del codice. Quando emerge
> un'incoerenza, la fixiamo subito (se piccola) o la registriamo come debito
> tecnico (se grande).


## Prossimi passi

1. **Macchina delle Fasi (Blocco 2)** — Fase diventa entità centrale, GANTT
   raggruppato per fasi, endpoint nuovi su `routes/fasi.py`
2. **Esperienza utente (Blocco 3)** — Vista Helena + Consuntivazione ridisegnata
3. **Ciclo vita progetto (Blocco 4)** — Pipeline bando/ordinario + Tavolo di Lavoro
4. **Sistema decisionale (Blocco 5)** — Marginalità + Risorse heatmap
5. **Hardening (Blocco 6)** — Test, performance, demo prep, migrazione `google.genai`


## Crediti

**Sviluppatrice principale:** Ludovica Di Cianni — stagista IA back-end IMC Group
(gennaio-giugno 2026)

**Stakeholder e validatori:**
- Vincenzo Carolla, AD — visione di prodotto, le 4 pagine, Scenario B
- Roberto Pezzuto, Manager IT — architettura, sicurezza, marginalità
- Andrea Morstabilini, Senior Consultant — Scenario B
- Francesco Carolla, Resp. amministrazione — modello bandi (tipologia, fasi standard)
- Cosimo Pacifico, Manager HR — costi orari per marginalità