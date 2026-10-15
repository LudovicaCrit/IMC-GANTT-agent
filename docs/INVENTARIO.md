# INVENTARIO — IMC-GANTT-agent

*Fotografia del codice e del DB al 15/10/2026, commit `3316929` (HEAD di `main`), working tree pulito salvo `GANTT_PONTE_OPUS.md` non tracciato.
Prodotto in SOLA LETTURA: nessun file di codice/migration/seed/config toccato, sul DB solo SELECT (sessione con `default_transaction_read_only=on`), nessun server o test avviato.
Ogni affermazione porta `file:riga` (path relativi alla radice del repo) o la query usata. `DA VERIFICARE` = non accertato.
`GANTT_PONTE_OPUS.md` è stato usato come elenco di cose da verificare, mai come prova.*

Durante la stesura nessun file tracciato è cambiato sotto mano (`git status` identico all'inizio e alla fine; HEAD sempre `3316929`).

---

## 1. Pagine frontend

Router: `frontend/src/App.jsx:181-240`. Menu: `navItems` `App.jsx:27-44` (**11 voci**; il commento `App.jsx:96-98` dice «12 voci, 9 con requiresManager» — stantio).
Ruoli: il menu mostra le voci `requiresManager` solo se `ruolo_app === 'manager'` (`App.jsx:55-56`); `RequireManager` rende `<Forbidden/>` a chiunque non sia manager (`components/RequireManager.jsx:37-38`). **Un PM vede esattamente quello che vede un dipendente: Home + Consuntivazione.** Il ruolo `pm` cambia solo il contenuto di Home e della Consuntivazione.

| Route | Componente | Menu | Ruoli | Endpoint chiamati | Stato |
|---|---|---|---|---|---|
| `/` | `pages/Home.jsx` | Home | tutti | `GET /api/home/dashboard`; `GET /api/consuntivi/me` (solo pm/user, `Home.jsx:428-430`) | VIVA |
| `/consuntivazione` | `pages/ConsuntivazioneOre.jsx` (+ `components/consuntivazione/*`) | Consuntivazione | tutti | `GET /api/consuntivi/me`, `POST /api/consuntivi/salva-blocchi`, `GET /api/consuntivi/settimana` (VistaPM/VistaManagement), `GET /api/tasks` (AggiungiRiga), fetch grezzi `/api/progetti` e `/api/segnalazioni` (`VistaManagement.jsx:54-55`) | VIVA |
| `/consuntivazione/ore`, `/consuntivazione-new` | redirect a `/consuntivazione` | no | tutti | — | VIVA (redirect, `App.jsx:197-198`) |
| `/gantt` | `pages/Gantt.jsx` | GANTT | manager | `GET /api/progetti`, `/api/dipendenti`, `/api/gantt/strutturato`, `/api/gantt/export-pdf`; fetch grezzi `/api/gantt/export-png` `Gantt.jsx:379`, `/api/gantt/export-excel` `Gantt.jsx:398` | VIVA (export PDF/PNG rotti, §7) |
| `/cantiere` | `pages/Cantiere.jsx` | Cantiere | manager | `GET /api/gantt/strutturato?stato=all`, `POST /api/progetti/completo`, `PUT /api/progetti/{id}/completo`, `POST /api/progetti/{id}/task-multipli`, `GET /api/dipendenti` | VIVA |
| `/cantiere/:progettoId` | `pages/CantiereDettaglio.jsx` | no | manager | strutturato, dipendenti, `/api/config/ruoli`, PATCH/DELETE progetti, POST/PATCH/DELETE fasi, POST/PATCH tasks, PUT dipendenze, PATCH elimina, `/api/risorse/saturazione-periodo`, 5 endpoint `/api/sottotask` (`CantiereDettaglio.jsx:44-57`) | VIVA (link da `Cantiere.jsx:320`, `ElencoDettaglio.jsx:247`) |
| `/elenco/:progettoId` | `pages/ElencoDettaglio.jsx` | no | **manager** | strutturato, dipendenti, 3 endpoint `/api/sal` | VIVA (link da Gantt, Cantiere, Archivio, Home) |
| `/analisi` | `pages/AnalisiInterventi.jsx` («**Tavolo di Lavoro**») | Tavolo di Lavoro | manager | dipendenti, progetti, tasks, segnalazioni, `/api/risorse/suggerisci-bilanciamento`, `/api/agent/interpreta-scenario`, `/api/scenario/simula`, `/api/scenario/conferma`, `/api/tasks/applica` | VIVA |
| `/risorse` | `pages/Risorse.jsx` | Risorse | manager | dipendenti, `/api/risorse/carico?settimane=12`, tasks, progetti (`Risorse.jsx:51`) | VIVA |
| `/pipeline` | `pages/Pipeline.jsx` | Pipeline | manager | progetti, tasks, dipendenti, `/api/tasks/applica`, `/api/agent/suggerisci-task`; fetch grezzi `/api/config/fasi-catalogo` `:45`, `POST /api/fasi` `:190` | **VIVA di nome, vuota nei fatti** (sotto) |
| `/economia` | `pages/Economia.jsx` | Economia | manager | `GET /api/economia/margini`, `GET /api/progetti` (`Economia.jsx:95`) | VIVA |
| `/attivita-interne` | `pages/AttivitaInterne.jsx` | Attività Interne | manager | `GET /api/attivita-interne`, `DELETE /api/attivita-interne/{id}` | VIVA |
| `/archivio` | `pages/Archivio.jsx` | Archivio | manager | `GET /api/gantt/strutturato?stato=all` (`Archivio.jsx:35`) | VIVA |
| `/configurazione` | `pages/Configurazione.jsx` | Configurazione | manager | solo fetch grezzi su `/api/config/*` (`Configurazione.jsx:16,26,36,45`) | VIVA |
| `/login` | `pages/Login.jsx` | no | anonimi | `/api/auth/login`, `/me`, `/logout` (via `contexts/AuthContext.jsx:21-25`) | VIVA |
| `*` | `pages/NotFound.jsx` | no | tutti | — | VIVA |
| — | `pages/Forbidden.jsx` | no | non-manager | — | VIVA solo via `RequireManager.jsx:19,38`; l'import in `App.jsx:17` è morto |

Nessuna pagina ORFANA o MORTA in `pages/`. Nessun componente in `components/` inutilizzato. Nessuna chiamata frontend a endpoint inesistenti.

**Codice morto dentro pagine vive**
- `api.js`: funzioni mai chiamate — `fetchDipendente` `:165`, `createProgetto` `:177`, `fetchAgentStatus` `:399`, `sendChatMessage` `:403`, `richiediAnalisiGantt` `:407`, `verificaPianificazione` `:411` (importata in `Pipeline.jsx:2`, mai invocata), `salvaBozza` `:439` / `caricaBozza` `:447` (fanno solo `throw`; importate in Pipeline e AnalisiInterventi).
- `Gantt.jsx`: `StatoBadge` locale `:236-259` mai renderizzato; `export { buildTimeline }` `:29` senza importatori; `fetchCaricoRisorse` importato `:3` e mai usato.
- `cantiere/_costanti.js:32,38`: `STATI_PROGETTO`, `STATI_PROGETTO_ATTIVI` mai importati.
- Dipendenza npm `frappe-gantt` (`frontend/package.json:12`): mai importata in `frontend/src`.

### Cosa mostrano oggi le pagine vive
- **Home** — manager (`Home.jsx:461-488`): un riquadro per società (polso), striscia team (persone/sovraccarichi → /risorse, interne → /attivita-interne), blocchi «Da guardare» per ramo. PM (`:491-536`): «Le mie cose» (task della settimana, da compilare, interne) + «I progetti che seguo» collassato. User (`:537-539`): «Le mie cose» + `CennoProgetti` (solo pastiglie). **Bug**: per PM/user il click su un progetto fa `navigate('/elenco/'+pid)` (`Home.jsx:455`), route manager-only → pagina 403.
- **Consuntivazione**: griglia giorni×unità di lavoro (task o sottotask), mezze giornate, testata-riga con stato/residuo/nota, salva con `salva-blocchi`. Manager e PM hanno il toggle «la mia settimana / tutta l'azienda / i miei progetti» (`GuscioConsuntivazione.jsx:27-56`). `VistaManagement.jsx:221` legge `s.dipendente_nome`, chiave che il payload non ha (`data_db_impl.py:2490` usa `dipendente`) → mostra l'id.
- **GANTT**: timeline progetto→fase→task (GanttChartFasi), filtri stato/progetto/profilo, export PDF/PNG/Excel, click → /elenco. La tendina progetti filtra `['In esecuzione','In bando']` (`Gantt.jsx:334`): 'In bando' non esiste più, i Sospeso non sono selezionabili. Gli export PNG/Excel non controllano `res.ok` (`Gantt.jsx:379-410`).
- **Cantiere**: «Bozze da completare» (riapre il Wizard) e «Progetti attivi e sospesi». Esclude `tipologia==='interna'` (`Cantiere.jsx:113`) — contraddice `AttivitaInterne.jsx:28-30` che rimanda al Cantiere per i task interni. **I progetti in stato «Da iniziare» non compaiono in nessuna sezione** (`Cantiere.jsx:116-119`) né nel GANTT (default "attivi" = `In esecuzione`+`Sospeso`, `backend/routes/progetti.py:319-320`, `backend/models.py:99`).
- **CantiereDettaglio**: tab Design (KPI, anagrafica, persone, fasi/task con modali, sottotask) e tab Scenari (criticità calcolate lato client, senza IA, `:365-394`). La modifica di una fase esistente invia solo `{stato}` (`SezioneFasiTask.jsx:210,221`): **ore vendute e date di una fase esistente non sono modificabili da UI**.
- **ElencoDettaglio**: sola lettura, tab Design / Scenari / **SAL**; bottone «Modifica in Cantiere».
- **SAL** (`components/_shared/SezioneSAL.jsx`): montato SOLO in `ElencoDettaglio.jsx:294`. Consolida con nota, storico, apertura snapshot con mini-GANTT (TimelineBars) e diff col precedente. 0 snapshot in DB.
- **Risorse**: banner >125%, heatmap saturazione 12 settimane (soglie 90/100/125/150, `Risorse.jsx:14-37`), dettaglio persona-settimana, «Disponibilità corrente», anagrafica. Il dettaglio spalma **`ore_stimate`** lato client (`Risorse.jsx:62-110`) mentre la heatmap viene dal backend che usa **`ore_pianificate`** (`backend/data_db_impl.py:1317`): due numeri diversi nella stessa pagina (27 task commerciali su 114 hanno pianificate≠stimate). `Promise.all` senza `.catch` (`:51-53`). Il backend esclude ancora `P010` per id (`backend/routes/risorse.py:335`), che oggi è un progetto cliente (Maida).
- **Attività interne**: vista per persona dei 27 progetti `tipologia='interna'`, famiglie Corsi/Mansioni continuative/Sviluppo interno/Altre derivate dal prefisso id (`backend/routes/attivita_interne.py:123`), sezione «senza assegnatario», elimina (soft). Nessun form di creazione.
- **Configurazione** (`Configurazione.jsx:404-434`): tab Dipendenti (CRUD), Ruoli (aggiungi/rimuovi, niente modifica), Competenze, Fasi (catalogo `/config/fasi-catalogo`). Fetch grezzi senza gestione 401/403 né `res.ok` (`:16-18,45`). Il form dipendente non ha il campo `sede` → **ogni PATCH sovrascrive `dipendenti.sede` con `''`** (`backend/routes/configurazione.py:169,570`).
- **Archivio**: card dei Completato/Annullato (filtro client su `stato=all`, `Archivio.jsx:35-54`), ore consumate/vendute, click → /elenco. Nessuna IA.
- **Economia**: tab Margini (per società + tabella) e tab Avanzamento (Gauge tempo/budget-ore, solo commerciali `In esecuzione`). Margini mostra 11 progetti commerciali (tutti gli stati), Avanzamento 8 (query: 8 commerciali in esecuzione, 1 Bozza, 1 Completato, 1 Sospeso).
- **Pipeline**: 3 tab che filtrano `'In bando'`, `'Vinto - Da pianificare'`, `['Sospeso','Completato']` (`Pipeline.jsx:650-652`). I primi due stati non esistono più (CHECK `ck_progetti_stato_ammessi`; migration `c3d4e5f6a7b8…:64-67` li ha convertiti in Bozza) e `fetchProgetti()` senza parametro restituisce solo In esecuzione+Sospeso → **bandi e pianificare sempre vuote, archivio mostra solo i Sospeso**. Di conseguenza `PianificazioneProgetto` (`:14-617`, con l'IA «Suggerisci struttura») è irraggiungibile. L'archivio calcola «Consumate» come somma di `ore_stimate` dei task (`:664-666`): dato falso.
- **Tavolo di Lavoro** (`/analisi`): scelta progetto In esecuzione, editor tabellare dei task, IA testo→modifiche (`interpreta-scenario`), «Verifica impatto» (`scenario/simula`, motore deterministico, GANTT prima/dopo), «Applica» (`scenario/conferma` + `tasks/applica`, **scrive sul DB vero**), pannello Bilanciamento. Legge `t.predecessore` (`AnalisiInterventi.jsx:400`) che `/api/tasks` non restituisce più → dipendenze sempre vuote. Liste cablate `PROFILI`/`FASI`/`STATI_TASK` (`:19-21`), profilo default 'Tecnico Senior' non presente in `PROFILI` (`:397`).

### Wizard creazione progetto (`components/cantiere/WizardCreazioneProgetto.jsx`)
- Invariante `oreQuadrano = Σ fasi.ore_vendute === budget_ore` (`:102`), richiesta solo per «Crea · Da iniziare/In esecuzione» (`:113-114`); «Salva come Bozza» richiede solo nome+budget>0 (`:258`).
- Il backend impone la stessa uguaglianza a **ogni** stato, Bozza inclusa, se `budget_ore` non è null (`backend/routes/progetti.py:414-422` POST, `:584-590` PUT); il Wizard manda sempre un numero (`:142`) → **una Bozza con ore che non quadrano riceve 422**.
- Dopo la creazione l'invariante non è difeso: `PATCH /api/progetti/{id}` accetta `budget_ore` libero (`progetti.py:906-907`), `POST /api/fasi` aggiunge ore vendute libere.
- Campi inviati (`:131-160`): progetto {id, nome, cliente, tipologia, stato, pm_id, date, budget_ore}; fasi {nome, ordine, date, ore_vendute}; task {nome, fase_idx, dipendente_id, ore_stimate, date}. **Non invia** descrizione, valore_contratto, giornate_vendute, priorità, urgenza, sede, azienda_id, profilo_richiesto, dipendenze.

### Colori GANTT per stato
| Stato | GanttChartFasi | TimelineBars | StatoBadge (`_costanti.js`) | Legenda `Gantt.jsx` STATUS_COLORS |
|---|---|---|---|---|
| Task Da iniziare / In corso / Completato | grigio / blu / verde (`:35-37`) | idem (`:67-69`) | gray/blue/green | idem (`:8-10`) |
| Task Bloccato | rosso (`:38`) | rosso (`:70`) | red-700 | **assente** |
| Task Sospeso | **assente → fallback grigio** (`:517`) | ambra (`:71`) | yellow-700 | ambra (`:11`) |
| Task Annullato | **assente → fallback grigio** | grigio scuro (`:72`) | red-900 | **assente** |
| Fasi (5 stati) | tutti presenti (`:27-31`) | tutti (`:59-63`) | presenti | — |

La pagina GANTT mostra una legenda (Sospeso=ambra) che contraddice le barre (Sospeso grigio). Debito dichiarato in `TimelineBars.jsx:50-56`.

---

## 2. Endpoint

78 endpoint in 19 router (prefisso nell'`APIRouter` di ciascun file; montati in `backend/main.py:40-58`; nessuna route `@app.*`). Dipendenze: `get_current_user` (`backend/deps.py:34-63`, cookie httpOnly JWT, rilegge `utenti` a ogni chiamata), `require_manager` (`deps.py:70-80`, 403 se `ruolo_app != 'manager'`), `_autorizza_progetto` (`routes/sal.py:34-46`: manager oppure `dipendente_id == progetti.pm_id`, indipendente dal ruolo `pm`).
Legenda chiamante: nome funzione `api.js` o «grezzo» = fetch diretto; **ORFANO** = nessun chiamante in `frontend/src`.

| Router (file) | Metodo Path | Riga | Auth | Chiamante FE | Tabelle R / W |
|---|---|---|---|---|---|
| auth (`auth_routes.py`) | POST /api/auth/login | 107 | **nessuna** (5/min per IP `:108` + 5/60s per email in memoria `:27-45`) | login | R utenti, dipendenti / W utenti.ultimo_login `:139` |
| | GET /api/auth/me | 163 | user | getCurrentUser | R utenti, dipendenti |
| | POST /api/auth/logout | 172 | **nessuna** | logout | — |
| dipendenti | GET /api/dipendenti | 91 | manager | fetchDipendenti | R dipendenti, ruoli, task, progetti, competenze |
| | GET /api/dipendenti/{id} | 190 | user, self-or-manager `:200` | **ORFANO** | idem |
| progetti | GET /api/progetti | 306 | manager | fetchProgetti, grezzo VistaManagement | R progetti, task, ore_settimanali, consuntivi |
| | POST /api/progetti | 348 | manager | **ORFANO** | W progetti |
| | POST /api/progetti/completo | 394 | manager | createProgettoCompleto | W progetti, fasi, task |
| | PUT /api/progetti/{id}/completo | 559 | manager, solo Bozza | completaProgetto | W progetti; DELETE+INSERT fasi (task in cascata) |
| | POST /api/progetti/{id}/task-multipli | 739 | manager | aggiungiTaskMultipli | W task, dipendenza_task |
| | PATCH /api/progetti/{id} | 887 | manager (setattr cieco `:906-907`) | updateProgetto | W progetti |
| | DELETE /api/progetti/{id} | 915 | manager, solo Bozza | deleteProgetto | W progetti (cascade ORM fasi/task; dipendenza_task DA VERIFICARE) |
| economia | GET /api/economia/margini | 71 | manager | fetchMarginiEconomia | R dipendenti, ruoli, azienda, progetti, task, fasi, ore_settimanali |
| risorse | GET /api/risorse/carico | 125 | manager | fetchCaricoRisorse | R dipendenti, ruoli, task |
| | GET /api/risorse/saturazione-periodo | 180 | manager | fetchSaturazionePeriodo | R dipendenti, task |
| | GET /api/risorse/suggerisci-bilanciamento | 311 | manager | fetchBilanciamento | R dipendenti, ruoli, dipendenti_ruoli_aggiuntivi, task, progetti |
| gantt | GET /api/gantt | 199 | manager | **ORFANO** | R task, progetti, dipendenza_task, ore_settimanali, dipendenti |
| | GET /api/gantt/strutturato | 283 | manager | fetchGanttStrutturato | R progetti, fasi, task, dipendenza_task, ore_settimanali, sottotask, dipendenti |
| | GET /api/gantt/export-pdf | 769 | manager | exportGanttPdf | R task, progetti, dipendenti — **ImportError reportlab** (§7) |
| | GET /api/gantt/export-png | 827 | manager | grezzo Gantt.jsx:379 | idem + `pdftoppm` |
| | GET /api/gantt/export-excel | 904 | manager | grezzo Gantt.jsx:398 | R task, progetti, fasi, dipendenti |
| segnalazioni | GET /api/segnalazioni | 76 | manager | fetchSegnalazioni, grezzo VistaManagement | R segnalazioni, dipendenti (fallback in-memory `main.SEGNALAZIONI_STORE` `:64-84`) |
| pianificazione | POST /api/pianificazione/salva-bozza | 68 | manager → sempre 410 | **ORFANO** | — |
| | GET /api/pianificazione/bozza/{id} | 73 | manager → sempre 410 | **ORFANO** | — |
| consuntivi | GET /api/consuntivi/settimana | 325 | user; manager tutto, pm perimetro `pm_id`, altri 403 (`:358-371`) | fetchConsuntiviSettimana | R consuntivi, ore_settimanali, dipendenti, ruoli, task, progetti |
| | GET /api/consuntivi/me | 572 | user, self-only | fetchConsuntiviMe | R dipendenti, task, blocchi_ore, consuntivi, consuntivo_sottotask, sottotask |
| | POST /api/consuntivi/salva-blocchi | 692 | user, self-only (`:711`) | salvaBlocchi | W blocchi_ore, consuntivi, consuntivo_sottotask, task.stato (propagazione `data_db_impl.py:2959-3001`) |
| tasks | GET /api/tasks | 156 | user (non-manager: solo i propri, `:175`) | fetchTasks | R task, progetti, fasi, dipendenza_task |
| | POST /api/tasks | 270 | manager | createTask | W task, dipendenza_task |
| | PUT /api/tasks/{id}/dipendenze | 390 | manager | sostituisciDipendenzeTask | W dipendenza_task |
| | PATCH /api/tasks/{id} | 416 | manager | updateTask | W task |
| | POST /api/tasks/applica | 549 | manager | applicaModifiche (Pipeline, Tavolo) | W task (campo **libero**, §10), dipendenza_task, progetti.stato |
| | PATCH /api/tasks/{id}/elimina | 724 | manager | deleteTask | W task.stato='Eliminato' |
| sottotask | POST /api/sottotask · GET /{task_id} · PATCH /{id} · PUT /{task_id}/riordina · DELETE /{id} | 395, 446, 522, 575, 640 | manager | SottotaskManager | W sottotask; R consuntivo_sottotask |
| attivita-interne | GET /api/attivita-interne | 134 | user, **nessun filtro per persona** | fetchAttivitaInterne | R progetti, task, dipendenti, ruoli |
| | DELETE /api/attivita-interne/{task_id} | 249 | user, self-or-manager `:285` | eliminaAttivitaInterna | W task.stato |
| config (`configurazione.py`, `/api/config`) | GET/POST ruoli · DELETE ruoli/{id} | 194, 233, 265 | manager | grezzi Configurazione.jsx; fetchRuoli | ruoli |
| | PATCH ruoli/{id} | 249 | manager | **ORFANO** | ruoli |
| | GET/POST competenze · DELETE /{id} | 283, 293, 309 | manager | grezzi | competenze |
| | GET aziende | 327 | manager | grezzo | azienda |
| | GET/POST dipendenti · PATCH/DELETE /{id} | 345, 492, 538, 585 | manager | grezzi | dipendenti, dipendenti_competenze |
| | GET/POST fasi-standard · DELETE /{id} | 603, 625, 642 | manager | **ORFANI** | fasi_standard |
| | GET/POST fasi-catalogo · DELETE /{id} | 660, 690, 720 | manager | grezzi Configurazione, Pipeline | fasi_standard |
| agent | GET /api/agent/status | 242 | user | **ORFANO** (solo healthcheck Playwright) | — |
| | POST /api/agent/chat | 252 | user (non-manager forzato a se stesso `:263-264`) | **ORFANO** | R task, dipendenti, progetti / W segnalazioni; Gemini |
| | POST /api/agent/analisi-gantt | 436 | manager | **ORFANO** | R dipendenti, ruoli, task, progetti; Gemini |
| | POST /api/agent/suggerisci-task | 577 | manager | suggerisciTask (Pipeline, irraggiungibile) | solo body; Gemini |
| | POST /api/agent/verifica-pianificazione | 625 | manager | **ORFANO** | R dipendenti, ruoli, task; Gemini |
| | POST /api/agent/interpreta-scenario | 704 | manager | interpretaScenario (Tavolo) | R progetti, task, dipendenti, ruoli; Gemini |
| scenario | POST /api/scenario/simula | 243 | manager | simulaScenario | R task, dipendenti, ruoli, progetti |
| | POST /api/scenario/conferma | 338 | manager | confermaScenario | W task (date, ore_pianificate) |
| fasi | POST /api/fasi | 214 | manager | createFase, grezzo Pipeline | W fasi |
| | PATCH /api/fasi/{id} | 256 | manager | updateFase | W fasi, task (cascata stato) |
| | DELETE /api/fasi/{id} | 371 | manager | deleteFase | W fasi |
| | GET /api/fasi/{progetto_id} | 410 | manager | **ORFANO** (solo e2e) | R fasi, task, ore_settimanali |
| home | GET /api/home/criticita | 79 | user | **ORFANO** | R progetti, task, fasi, ore_settimanali |
| | GET /api/home/dashboard | 196 | user, perimetro `progetti_attivi_visibili` | fetchHomeDashboard | R progetti, task, fasi, sottotask, ore_settimanali, azienda, dipendenti |
| sal | POST /api/sal/{pid} · GET /snapshot/{id} · GET /{pid} | 49, 66, 84 | user + `_autorizza_progetto` | SezioneSAL | W/R sal_snapshot |
| bollettino | POST /api/bollettino/{pid} · GET /snapshot/{id} · GET /{pid} | 37, 57, 74 | user + `_autorizza_progetto` | **ORFANI** (anche negli e2e) | W/R bollettino_economico |

Totale ORFANI: **18** (16 senza alcun chiamante nemmeno e2e). Senza autenticazione: solo login/logout; in più `/docs`, `/redoc`, `/openapi.json` pubblici (default FastAPI, `main.py:33`).
Note: CORS solo `localhost:3000/5173` (`main.py:61-67`); due istanze `Limiter` distinte (`auth_routes.py:20` e `main.py:36`, effetto DA VERIFICARE); codice morto in `main.py`: `SimulaRiassegnaRequest` `:93-95`; `SEGNALAZIONI_STORE` serve solo un fallback probabilmente irraggiungibile (DA VERIFICARE).

---

## 3. Modello dati

**Alembic**: `alembic heads` = `alembic current` = **`a6b7c8d9e0f1`**. `alembic check` (in read-only) → «No new upgrade operations detected.»
Nota: gli indici `ix_sal_snapshot_progetto_id` e `ix_bollettino_economico_progetto_id` (creati dalle migration `c9d0e1f2a3b4:64`, `d0e1f2a3b4c5:54`) **non esistono nel DB** e le FK hanno nomi di default: il DB è stato creato con `create_all` e poi marcato a head. Il DB "vero" non è quindi riproducibile a identità solo con `alembic upgrade`.

**Righe** (`count(*)` esatto): assegnazioni 114 · azienda 2 · blocchi_ore 2249 · bollettino_economico 0 · competenze 38 · consuntivi 2635 · consuntivo_sottotask 0 · dipendenti 18 · dipendenti_competenze 68 · dipendenti_ruoli_aggiuntivi 7 · dipendenza_task 33 · fasi 71 · fasi_standard 18 · interventi 0 · note_progetto 0 · progetti 38 · ruoli 10 · sal_snapshot 0 · segnalazioni 3 · sottotask 0 · task 114 · utenti 4 · vista ore_settimanali 2249.
22 classi `Base` ↔ 22 tabelle (più `alembic_version`); la vista è mappata come `Table` fuori da `Base.metadata` (`backend/models.py:1198-1205`).

**Vista `ore_settimanali`**: `SELECT task_id, dipendente_id, date_trunc('week', giorno)::date AS settimana, sum(ore) FROM blocchi_ore GROUP BY 1,2,3`. Creata in `backend/alembic/versions/f0a1b2c3d4e5_vista_ore_settimanali.py:27-36` e, in duplicato, da un evento DDL `after_create` in `models.py:1175-1185`. Lettori: `data_db_impl.py:466, 726, 1613-1622, 2929-2933, 3074-3080, 3332-3334`; `routes/consuntivi.py:405-414`; `routes/fasi.py:316-321, 438-447`; `routes/gantt.py:221-223, 425-427`. Tutti i 2249 blocchi sono `fonte='storico'`, tutti di lunedì, dal 2025-06-30 al 2026-07-20: **la griglia non ha mai scritto un blocco manuale nel DB vero**.

**Vincoli**: i 25 CHECK/UNIQUE del DB combaciano con `__table_args__`, tranne: `ck_consuntivo_sottotask_stato` presente nel DB ma assente dal modello (`models.py:1089-1094`) → un `create_all` su DB nuovo non lo crea; `consuntivi.stato_dichiarato` senza CHECK (asimmetria con la tabella gemella).
**Indici**: `task` ha solo la PK (nessun indice su progetto_id, fase_id, dipendente_id); `consuntivi` solo PK + `uq_consuntivo(task_id, dipendente_id, settimana)`; `blocchi_ore` ha PK, `ix_task_id`, `ix_sottotask_id`, `uq_blocchi_ore … NULLS NOT DISTINCT`.

### Colonne per tabella
Legenda: VIVA (scritta a runtime e letta da un consumatore reale) · SOLO SCRITTA (nessuna lettura arriva a un consumatore) · SOLO LETTA (a runtime nessuno la scrive: valori da seed/migration/default) · MORTA. `created_at`/`updated_at`: valorizzate dai default ORM, mai lette (unica eccezione `segnalazioni.created_at`, usata per ordinare `data_db_impl.py:2478`) → **SOLO SCRITTA** ovunque; non ripetute sotto.

| Tabella | Colonna | Scrive | Legge | Pieni | Verdetto |
|---|---|---|---|---|---|
| ruoli | id, nome, attivo | `configurazione.py:241,257,273` | `:221-226` → Configurazione | 10 | VIVA |
| | descrizione | `:241,259` | payload, nessun lettore FE | 1 | SOLO SCRITTA |
| | tipo | nessuno a runtime (server_default 'base'; seed; migration `a5b6c7d8e9f0`) | `:223` → Configurazione | 10 | SOLO LETTA |
| competenze | id, nome, attivo | `configurazione.py:301,317` | Configurazione, Risorse, Pipeline | 38 | VIVA (la M2M letta in `dipendenti.py:144` non filtra `attivo`) |
| dipendenti_competenze | dipendente_id, competenza_id | `configurazione.py:417,575-578` | `dipendenti.py:144`, `data_db_impl.py:420` | 68 | VIVA |
| dipendenti_ruoli_aggiuntivi | dipendente_id, ruolo_id | **solo seed** `seed.py:293` | match bilanciamento `risorse.py:326,388,432` | 7 | SOLO LETTA |
| fasi_standard | template_nome, fase_nome, ordine | `configurazione.py:630-632,709-711` | `/fasi-catalogo` → Configurazione, Pipeline | 18 | VIVA (catalogo `_catalogo` vuoto → fallback sui template `:674-683`) |
| | percentuale_ore | `:633` (endpoint orfano), seed | solo `GET /fasi-standard` (orfano) | 18 | SOLO SCRITTA |
| utenti | id, email, password_hash, ruolo_app, dipendente_id, attivo | **solo seed** `seed.py:575-600` (nessun endpoint utenti, né cambio password) | auth/deps | 4 | SOLO LETTA |
| | ultimo_login | `auth_routes.py:139` | nessuno | 4 | SOLO SCRITTA |
| azienda | id, nome | solo seed `seed.py:176` | Configurazione, Home, Economia | 2 | SOLO LETTA |
| dipendenti | id, nome, azienda_id, ruolo_id, ore_sett, costo_ora, attivo | `configurazione.py:512-521,561-568,593` | ovunque | 18 | VIVA |
| | email | `:521,569` | solo il form Configurazione | **1/18** (D018, valore `''`) | VIVA marginale |
| | sede | `:521,570`, **sovrascritta a `''` da ogni PATCH** | payload, nessun lettore FE | 1 (`''`) | SOLO SCRITTA (distruttiva) |
| | data_assunzione, note | nessuno | nessuno | 0 | MORTA |
| progetti | id, nome, stato, cliente, tipologia, data_inizio, data_fine, pm_id | POST/PUT/PATCH `progetti.py:367-386,449-456,621-637,906-907` | ovunque | 38 (pm_id **10**) | VIVA |
| | budget_ore | vedi sotto | gauge Economia | 38 | VIVA |
| | valore_contratto | solo DTO, **nessun mittente FE** | Economia `data_db_impl.py:3392,3405` | 38 (12 distinti) | SOLO LETTA |
| | azienda_id | **solo seed** `seed.py:355`; assente dai DTO | Home `home.py:335-345`, Economia | 11 (27 interne NULL) | SOLO LETTA — un progetto creato da UI nasce NULL ed è trattato come **interno** dalla Home (`home.py:335`) |
| | urgenza, fase_corrente | solo default DTO / nessun mittente FE | Home, SAL / Pipeline `:785` | 38 | SOLO LETTA |
| | descrizione | solo DTO, nessun mittente FE | non esposta da `GET /api/progetti` (`progetti.py:285-303`); `Pipeline.jsx:709` la legge e trova sempre undefined | 38 | SOLO SCRITTA di fatto |
| | priorita, area | default DTO / seed | solo JSON SAL non letto dal FE | 38 / 2 | SOLO SCRITTA |
| | giornate_vendute, sede, scadenza_bando, motivo_sospensione, lezioni_apprese, note | solo DTO | solo JSON SAL o nessuno | **0** | MORTA |
| fasi | id, progetto_id, nome, ordine, date, stato | `fasi.py:238-248,340`, `progetti.py:464,652` | GANTT, SAL, Cantiere | 71 | VIVA |
| | ore_vendute, ore_pianificate | vedi sotto | | 71 | VIVA / vedi sotto |
| | note | POST (FE manda sempre `''`) | solo endpoint orfano `fasi.py:472` | 0 | SOLO SCRITTA |
| | urgenza | solo PATCH `fasi.py:159`, nessun mittente FE | gantt payload, nessun lettore FE | 0 | MORTA |
| task | id, progetto_id, fase_id, nome, date, stato, dipendente_id, profilo_richiesto, ordine | creazione + `modifica_task` `data_db_impl.py:2444-2457` | ovunque | 114 (profilo_richiesto: 44 `''`) | VIVA |
| | ore_stimate, ore_pianificate | vedi sotto | | 114 | VIVA / vedi sotto |
| | motivo_blocco, note | nessuno (raggiungibili solo via campo libero di `/applica`) | solo JSON SAL | 0 | MORTA |
| dipendenza_task | pred, succ, tipo | `data_db_impl.py:2309,2425`, `progetti.py:860` | GANTT, tasks, scenario_engine, agent | 33 | VIVA |
| sottotask | tutte | `sottotask.py:423,558,575,674` | /me, gantt, sottotask | **0 righe** | VIVA nel codice, mai usata |
| assegnazioni | tutte (incl. `ore_assegnate`) | **nessuno** (seed potato `seed.py:487-496`) | **nessuno** (solo relationship cascade `models.py:754`) | 114 fossili del 20/07 | MORTA |
| consuntivi | task_id, dipendente_id, settimana, nota | `salva_blocchi_settimana` `data_db_impl.py:2852,2866-2902` | /me, /settimana | 2635 (nota 1253) | VIVA |
| | stato_dichiarato | `:2850` | /me, VistaPM, propagazione Task.stato | **3** | VIVA, poco usata |
| | presa_visione | `:2856` | /me, `unitaLavoro.js:49` | 2635, **tutte false** | VIVA, mai a true |
| | ore_stimate_residue | `:2854` | /me, VistaPM | **0** | VIVA nel codice, mai compilata |
| | compilato | `:2901,2949` | letta ma le chiavi `dichiarato`/`tasso_compilazione` non arrivano al FE | 2635 | SOLO SCRITTA di fatto |
| | data_compilazione | `:2902,2949` | nessuno | 2252 | SOLO SCRITTA |
| consuntivo_sottotask | tutte | `data_db_impl.py:2849-2902` | /me (tranne compilato, data_compilazione) | **0 righe** | VIVA nel codice |
| blocchi_ore | dipendente_id, giorno, task_id, sottotask_id, ore, fonte | `data_db_impl.py:2813-2824` | /me, vista | 2249 (fonte: solo `storico`) | VIVA |
| segnalazioni | id, priorita, dipendente_id, dettaglio | unico scrittore runtime `aggiungi_segnalazione` `data_db_impl.py:2498` ← `/agent/chat` ORFANO | VistaManagement, Tavolo | 3 (da seed) | SOLO LETTA |
| | tipo, fonte, stato | idem | mai lette | 3 | SOLO SCRITTA |
| | progetto_id, destinatario | nessuno | nessuno | 0 | MORTA |
| sal_snapshot | tutte | `data_db_impl.py:3168-3173` ← `/api/sal` | SezioneSAL | **0 righe** | VIVA nel codice, mai consolidato |
| bollettino_economico | tutte | `data_db_impl.py:3532` ← router orfano | nessun FE | 0 | MORTA (raggiungibile solo via API) |
| note_progetto, interventi | tutte | nessuno | nessuno (solo `models.py:1228-1251`) | 0 | MORTA |

### Colonne-ore: TUTTI gli scrittori

**`Task.ore_stimate`** (Integer, `models.py:729`)
- Backend: `aggiungi_task` `backend/data_db_impl.py:2285` ← `POST /api/tasks` `routes/tasks.py:358` e `/applica` nuovi_task `routes/tasks.py:672`; `routes/progetti.py:523` (POST /completo), `:706` (PUT /completo), `:834` (task-multipli); `modifica_task` `data_db_impl.py:2454` ← PATCH `routes/tasks.py:543` (campo nel DTO `:262`) e `/applica` `routes/tasks.py:661` (`int()` a `:658-659`); seed `seed.py:415+`.
- Frontend: `WizardCreazioneProgetto.jsx:157`, `SezioneFasiTask.jsx:758` (nuovo) e `:778` (modifica), `AggiungiTaskModal.jsx:72`, `Pipeline.jsx:179`, `AnalisiInterventi.jsx:518,527`.
- Lettori di calcolo: nessun calcolo economico né di carico (verificato su `carico_settimanale_dipendente` `data_db_impl.py:1317` e `margini`); display e contesti IA (`agent.py:472-487`, `contesto.py:165,183`), dettaglio Risorse lato client.

**`Task.ore_pianificate`** (Float, `models.py:730`)
- Backend: `/api/scenario/conferma` `routes/scenario.py:381` via `modifica_task`; `/api/tasks/applica` `routes/tasks.py:661` **solo in teoria** (il campo è una stringa libera, nessun FE manda `ore_pianificate`); seed `seed.py:429`; backfill migration `b8c9d0e1f2a3` (26/06).
- **Nessun percorso di creazione la imposta**: `aggiungi_task` (`data_db_impl.py:2278-2300`) e i tre `Task(...)` di `routes/progetti.py:520,703,831` passano solo `ore_stimate` → **ogni task creato da UI nasce con `ore_pianificate` NULL** e vale 0 nel carico (`data_db_impl.py:1317`), nella saturazione e nel `pianificato` di Economia. Oggi 0 NULL solo perché tutti i 114 task vengono dal seed.
- `ModificaTaskSingolo` (`routes/tasks.py:260-267`) non ha il campo.
- Frontend: nessuno direttamente; indirettamente il Tavolo via `simula/conferma` (`AnalisiInterventi.jsx:491,529-532`).

**`Fase.ore_vendute`** (Float, `models.py:645`)
- Backend: `POST /api/fasi` `routes/fasi.py:244`; PATCH setattr `fasi.py:340` (DTO `:146`); `routes/progetti.py:467,655`; seed `seed.py:392`.
- Frontend: `WizardCreazioneProgetto.jsx:149`, `SezioneFasiTask.jsx:668` (solo nuova fase), `Pipeline.jsx:199`. Nessuna UI modifica le vendute di una fase esistente.

**`Fase.ore_pianificate`** (Float, `models.py:646`)
- Backend: `POST /api/fasi` `fasi.py:245`; PATCH `fasi.py:340` (DTO `:147`, nessun mittente FE); `routes/progetti.py:467,655` scrivono **`None`**; seed `seed.py:393` (= ore_vendute).
- Frontend: `SezioneFasiTask.jsx:669` scrive **sempre 0**.
- DB: su 71 fasi `ore_pianificate = ore_vendute` in tutte; ≠ Σ `task.ore_pianificate` in 15.

**`Progetto.budget_ore`** (Integer)
- Backend: POST `routes/progetti.py:377`, POST /completo `:452`, PUT /completo `:629`, PATCH setattr `:907`; seed `seed.py:360`. Invariante Σ vendute = budget imposto solo in `:414-422` e `:584-590`.
- Frontend: `WizardCreazioneProgetto.jsx:142`, `SezioneAnagrafica.jsx:47`.
- DB: 11/11 commerciali violano l'invariante; 27/27 interne lo rispettano (query nel §6).

---

## 4. Residui del mondo slider

**Spariti davvero** (schema e codice eseguibile): `consuntivi.percentuale`, `ore_effettive`, `ore_dichiarate`, `modalita`, `motivo_fermo`; `consuntivo_sottotask.percentuale`, `ore_effettive`; `task.ore_consumate`, `task.ore_rimanenti`; tabelle `presenze_settimanali`, `spese` (7 migration del commit `a5c0850`). `ControlliAvanzamento`, `PezzoSottotask` (commit `ad6382c`), motore `salva_consuntivo` / ore-derivate (commit `9f68ec5`), `POST /api/consuntivi/salva` (commit `78fd798`; l'e2e verifica il 404, `e2e/pagina-unica.spec.js:113-118`). Nessuna occorrenza eseguibile di `ore_derivate`, `avanzamento_uniforme`, `slider`, `baseline`.

| Residuo | Esiste? | Chi lo usa | DB | Rimovibile senza effetti? |
|---|---|---|---|---|
| Tabella `consuntivo_sottotask` | sì (`models.py:1039-1094`) | scritta da `salva_blocchi` `data_db_impl.py:2880-2887`, letta da /me | 0 righe | **No**: è la dichiarazione del mondo a blocchi sui pezzi |
| `stato_dichiarato`, `presa_visione`, `ore_stimate_residue` | sì | griglia, VistaPM, /me | 3 / 0 true / 0 | No: canali vivi, dati assenti |
| Parametri `percentuale`, `ore_consumate`, `ore_pianificate` di `colore_unita` | sì (`data_db_impl.py:154-155`) | nessun chiamante li passa (`:909,913,921,928`), solo test `test_semaforo.py:135,150-151,200-202` | — | Sì (aggiornando i test); è un «gancio strato 2» voluto, `percentuale` non ha più fonte |
| `agent.py:183-187` `_contesto_cache` | sì | mai letto | — | Sì |
| `contesto.invalida_cache_contesto` `contesto.py:199` | sì | nessun chiamante | — | Sì (ma la cache TTL 60s non viene mai invalidata) |
| `ChatRequest` slider-era (`agent.py:191-200`) | sì | endpoint orfano | — | vedi §5 |
| Import `salvaBozza`/`caricaBozza`/`verificaPianificazione` | sì (`Pipeline.jsx:2`, `AnalisiInterventi.jsx:2`) | nessuno | — | Sì |
| Commenti/docstring stantii | sì: `models.py:1049-1050, 1125`; `routes/sottotask.py:167-170`; `routes/attivita_interne.py:95-98`; `SottotaskManager.jsx:10-11,149-150`; `AttivitaInterne.jsx:35`; `data_db_impl.py:1184-1202, 1259, 1684-1694`; `api.js:559-561`; `App.jsx:184-187`; `GuscioConsuntivazione.jsx:8`, `BarraSalvataggio.jsx:5`, `PromemoriaNota.jsx:10`, `formato.js:5`; `models.py:672-674` e `:690-693` (dicono che `ordine` è tutto NULL: falso dal 07/09) | — | — | Sì, sono solo testo, ma ingannano chi legge |
| «Distribuzione uniforme» in `carico_settimanale_dipendente` | sì (`data_db_impl.py:1255-1318`) | Risorse, Home, agent, contesto | — | **Non è un residuo slider**: è il debito vivo del carico pianificato spalmato |
| `fasi_standard.percentuale_ore`, `percentuale` in scenario | sì | template / dedicazione | 18 | Non sono slider |

**SEMAFORO strato 1** — `colore_unita(data_fine, stato, oggi, …)` `data_db_impl.py:154-281`, funzione pura. Regola in ordine: stato in `STATI_FINITI_SEMAFORO` (Completato/a, Annullato/a, Eliminato, `:102-106`) → verde; stato in `STATI_FERMI_SEMAFORO` (Sospeso/a, `:120`) → grigio; `data_fine` NULL → grigio; `data_fine < oggi` → rosso; giallo mai emesso; altrimenti verde. Aggregazione peggio-dei-figli (`_nodo_semaforo` `:325-388`, rank `:302`), cammino progetto→fase→task→sottotask in `semaforo_progetti` `:788-936` (il sottotask eredita la data del task, `:908-910`).
**Legge solo date e stati** (`progetti/fasi/task.data_fine`, `.stato`, `sottotask.stato`). Nessuna colonna slider, nessuna ora, nessun consuntivo. Tutti gli input hanno scrittori vivi (Cantiere, Tavolo, propagazione `stato_dichiarato`→`Task.stato` `data_db_impl.py:2959-3001`). **Non legge nulla di non più scritto.** Effetto coi dati attuali: 61 dei 68 task «In corso» sono scaduti, quindi quasi tutto è rosso. Consumatori: `routes/gantt.py:468`, `routes/home.py:282` → `PastigliaSemaforo.jsx`.

---

## 5. Codice IA esistente

- **Modello**: `"gemini-2.5-flash"` **cablato** in `backend/gemini_client.py:59`; SDK `google-genai==2.12.1` (`requirements.txt:23`; c'è anche il vecchio `google-ai-generativelanguage`). Chiave da env `GEMINI_API_KEY` (`gemini_client.py:26`). Un `genai.Client` nuovo e una rilettura del prompt da disco a ogni richiesta (`:53-54`).
- **Endpoint `/api/agent/*`** (§2): l'unico usato davvero è `interpreta-scenario` (Tavolo). `suggerisci-task` è chiamato solo da una parte di Pipeline irraggiungibile. `chat`, `analisi-gantt`, `verifica-pianificazione`, `status` sono ORFANI. `analisi-gantt` (`agent.py:436`, prompt `analisi_segnalazioni.md` `:534`) ha perso l'ultimo chiamante (`CentroSegnalazioni.jsx`) nel commit `de5cbcc` del 07/09; `chat` ha perso `Consuntivazione.jsx` nel `167dd36`.
- **Prompt** (`backend/prompts/`): tutti e 5 referenziati, ma solo `interpreta_scenario.md` serve un percorso vivo.
- **Streaming NDJSON e `FaseStreamExtractor`: NON ESISTONO in questo repo.** Zero `StreamingResponse`, `generate_content_stream`, `x-ndjson`, `getReader`; `git log --all -S FaseStreamExtractor` vuoto. La classe sta in un altro progetto (`~/progetti/demand-scoring/backend/app/services/streaming_json.py:34`, usata da `.../routes/ai_methodology.py:195-251` con `HttpOptions(timeout=120000)`). L'affermazione del ponte «c'è già FaseStreamExtractor/NDJSON» (§6 giorno D-E) è **falsa per questo repo**; andrebbe portata (è la regola dei progetti distinti: copia consapevole, non travaso).
- **Timeout lungo la catena**: frontend `apiFetch` (`api.js:39-110`) senza AbortController né timeout né retry; proxy Vite `'/api': 'http://localhost:8000'` senza opzioni (`vite.config.js:9-11`, default http-proxy DA VERIFICARE); backend: endpoint `def` sincroni, nessun timeout, `uvicorn.run` senza opzioni (`main.py:104`); chiamata Gemini `generate_content` (`gemini_client.py:218-224, 243-249`) **senza `http_options`/timeout e senza retry**. In produzione il timeout effettivo sarà quello di IIS/ARR (default 120s DA VERIFICARE).
- **Contratto d'ingresso del vecchio mondo**: `ChatRequest` (`routes/agent.py:191-200`) prende dal BODY `ore_compilate: dict[task→ore settimanali]`, `stati_compilati`, `ore_assenza`, `tipo_assenza`, `nota_assenza`, `spese` — contratto della vecchia pagina di consuntivazione pre-griglia. Le tabelle presenze/spese non esistono più; il prompt `consuntivazione.md:86-123` emette `[MAPPATURA_ORE] {"ore": {TASK_ID: ORE}, …}` parsato in `agent.py:345-380`, incompatibile con `salva-blocchi` (blocchi per giorno). Non contiene percentuali: "slider" nel ponte va letto come «vecchia pagina».
- Tutti i contesti IA usano il **carico pianificato** e `ore_stimate`, mai le ore reali della vista (`agent.py:472-487`, `contesto.py:165,183`, `scenario.py:216-221`).
- **Embrioni recuperabili**
  - Tavolo (`AnalisiInterventi.jsx`): ciclo completo interpreta (IA) → simula (motore deterministico `scenario_engine.py:213`) → conferma. È l'embrione dell'IA «scenari». Da rifare su ore reali/residue e competenze, con streaming e timeout.
  - Pipeline: la trasformazione `task_suggeriti` → piano fasi+deliverable (`Pipeline.jsx:232-273`) + prompt `suggerisci_task.md` + `/suggerisci-task`: embrione di «Costruisci-GANTT». Il resto della pagina è morto.
  - `/analisi-gantt` (`agent.py:447-531`): motore di proposte di redistribuzione completo lato backend, senza UI.
  - `/verifica-pianificazione`: backend completo, mai chiamato.

---

## 6. Verifica dei debiti di `GANTT_PONTE_OPUS.md` (§2, §3, §7)

| Voce del ponte | Verdetto | Prova |
|---|---|---|
| **Bug ordine task: tutti i 114 con `ordine` NULL** (§7) | **RISOLTO** — il ponte sbaglia | Query: 114/114 `ordine` non NULL, 0 doppioni per fase. `Fase.task` ordina `order_by="Task.ordine, Task.id"` (`models.py:694-695`). Commit `288d0e9` (07/09, ROW_NUMBER per fase) e `7fba4af` (07/09, `contatore_ordine_task` in tutti i punti di creazione: `data_db_impl.py:2282`, `progetti.py:521,704,832`). Restano query che ordinano per sola `Task.id` (`attivita_interne.py:166`, `data_db_impl.py:1327,1567`, `dipendenti.py:129`, `fasi.py:322`) e due commenti stantii (`models.py:672-674,690-693`) |
| **`modifica_task(stato="Eliminato")` fuori dal CHECK → 500** (§7) | **RISOLTO** — il ponte sbaglia | `ck_task_stato_ammessi` nel DB include 'Eliminato' (query `pg_constraint`); `STATI_TASK_IN_DB` `models.py:248-258`. Commit `c8a62fa` (03/09, migration `f8a9b0c1d2e3`) |
| **`aggiungi_task(dipendente_id="")` viola FK in due rami** (§7) | **RISOLTO** — il ponte sbaglia | Commit `11daad4` (07/09). Normalizzazione in tutti i rami: `data_db_impl.py:2300` (difesa interna), `tasks.py:355` (POST), `tasks.py:672-690` (/applica nuovi_task), `progetti.py:526,709,837` (wizard e task-multipli). `attivita_interne.py` non crea più task (form rimosso, commit `8eac358` 03/09) |
| Tabella `Assegnazione` morta (1 lettore, 4 scrittori) | **ANCORA VERO, ma i numeri sono cambiati: 0 lettori, 0 scrittori** | `models.py:936-952` (docstring MONCONE); nessun lettore né scrittore; 114 righe fossili. Si può droppare |
| `assegnazioni.ore_assegnate` morto | ANCORA VERO | idem; la chiave `ore_assegnate` in `risorse.py:167,306` è un'altra cosa (carico), omonimia da evitare |
| `pm_id` NULL 28/38 | ANCORA VERO | query: 28/38 |
| 6/7 PM senza account; solo D002 `pm` | ANCORA VERO | `utenti`: 4 righe (2 manager D001/D011, 1 pm D002, 1 user D004). `ruolo_app` sta su `utenti`, non su `dipendenti` |
| email NULL 18/18 | **QUASI**: 17/18 NULL | D018 ha `''` (stringa vuota, scritta dal form) |
| Finestra-settimana in 3 copie | **ANCORA VERO, e peggio**: le righe citate (1721/1890/2180) non corrispondono più | Calcolo del lunedì in: `data_db_impl.py:1292` (inline), `:1337-1356` `_lunedi` (+ alias `:1949`), `routes/consuntivi.py:373-375`, `routes/risorse.py:162,249`, `scenario_engine.py:78-81`, `routes/gantt.py:1000`. **La fine settimana differisce**: carico usa lun..**ven** (`data_db_impl.py:1293`), /me usa lun..**dom** (`:1449`), `consuntivi.py:375` chiama `ven_date` una domenica (+6) |
| `budget_ore`: invariante del wizard violato da tutti gli 11 | ANCORA VERO | query: 11/11 commerciali (`ordinario` 9, `bando` 2) con `budget_ore ≠ Σ fasi.ore_vendute`; interne 27/27 uguali. Invariante in `WizardCreazioneProgetto.jsx:102` + backend `progetti.py:414-422,584-590`; nessuna difesa in PATCH |
| Trappola `PUT /{id}/completo` azzera descrizione/note | ANCORA VERO, più largo | `progetti.py:621-637` assegna TUTTI i campi dal DTO: `descrizione` `:631`, `note` `:637`, ma anche `valore_contratto` `:630`, `giornate_vendute`, `fase_corrente`, `sede`, `scadenza_bando`; `priorita`/`urgenza` tornano ai default. Il Wizard non li manda |
| `ore_pianificate` non scrivibile da `ModificaTaskSingolo` | ANCORA VERO, più grave | DTO `tasks.py:260-267` senza il campo; inoltre **i task nuovi nascono con `ore_pianificate` NULL** (§3) |
| UNIQUE(pred, succ) blocca SS+FF simultanei | ANCORA VERO | `uq_dipendenza_task UNIQUE (task_predecessore_id, task_successore_id)` (query `pg_constraint`); duplicati rifiutati anche in `data_db_impl.py:2246-2253` |
| Colori GANTT 4 stati vs 6 | ANCORA VERO | GanttChartFasi ha 4 stati task (`:35-38`), TimelineBars 6 (`:67-72`); vedi §1 |
| `ore_stimate` mosso dal PM non letto da nessun calcolo | ANCORA VERO | carico `data_db_impl.py:1317` e economia `:3510-3513` usano `ore_pianificate`; lo legge solo il dettaglio Risorse lato client |
| `Fase.ore_pianificate` ferma alle vendute, doppione | ANCORA VERO | 71/71 = vendute; 15 ≠ Σ task; il Cantiere la scrive a 0, il wizard a NULL |
| `ore_rimanenti` = due formule sotto lo stesso nome | ANCORA VERO | `data_db_impl.py:1855` (pianificate − consumato, task) e `routes/fasi.py:464` (vendute − consumate, fase; endpoint orfano) |
| `Consuntivo.ore_stimate_residue` 0 utilizzi | ANCORA VERO | query: 0/2635 |
| `presa_visione` tenuta, 2635 righe | ANCORA VERO | 2635 non NULL, tutte false |
| `Sottotask` 0 righe | ANCORA VERO | query |
| Saturazione su `ore_pianificate` spalmate uniformi | ANCORA VERO | `data_db_impl.py:1311-1318` |
| BOLLETTINO: zero frontend, manca un GET live | ANCORA VERO | `routes/bollettino.py:37,57,74`: POST crea snapshot, i due GET leggono snapshot (0 righe); nessun chiamante FE |
| STIMATE assenti da margini/bollettino | ANCORA VERO | `_serializza_economia_progetto` somma solo vendute e pianificate (`data_db_impl.py:3505-3517`) |
| `dipendente_id` mancante in `dettaglio_persone` | ANCORA VERO | `data_db_impl.py:3342-3345` (dict senza id) |
| `descrizione` non esposta e non nel wizard | ANCORA VERO | payload `progetti.py:285-303`; `Pipeline.jsx:709` la legge invano |
| Margini 11 vs Avanzamento 8 | ANCORA VERO | query stati commerciali: 8 In esecuzione, 1 Bozza, 1 Completato, 1 Sospeso |
| Pipeline/Tavolo «morti da eliminare» | **IMPRECISO**: entrambe sono VIVE (in menu); Pipeline è vuota nei fatti, il Tavolo funziona e scrive sul DB | §1 |
| `/api/agent/analisi-gantt` orfano | ANCORA VERO | §5 |
| `agent.py` prende i dati dal BODY (vecchio contratto) | ANCORA VERO | `ChatRequest` `agent.py:191-200` |
| «c'è già `FaseStreamExtractor`/NDJSON» | **FALSO per questo repo** | §5 |
| Repo senza cartella `tests/` | ANCORA VERO | test sparsi in `backend/test_*.py` + `e2e/` |
| Doc che descrivono lo SQLite vecchio | ANCORA VERO | occorrenze di "sqlite": `SECURITY_BACKLOG.md` 2, `documento_MCP_privacy_AI_Act.md` 1, `README.md` 3 |
| Alembic head `a6b7c8d9e0f1`; `alembic check` pulito | VERO | §3 |
| Storico 2249 blocchi | VERO | query |
| Suite e2e 61/61 | 61 a runtime (52 `test(` nel sorgente): conteggio **non eseguito** | §9 |
| Vitest «da montare» | ANCORA VERO | `frontend/package.json` senza vitest né script test |
| File citati in §8 del ponte (`PIANO_LAVORO_GANTT.md`, `HANDOFF_GANTT.md`, `MAPPA_FATTIBILITA.md`, `DESIGN_SOTTOTASK.md`, `DESIGN_SAL.md`) | **NON PRESENTI** nel repo | `ls` → No such file; `docs/` contiene solo `AUTH_MODEL.md`. Il dump `~/backup_gantt_pre_5.6_20260923_1530.dump` esiste |

**Chi ha ragione sulle voci «chiuse ad inizio settembre»**: il codice. I commit `288d0e9`/`7fba4af` (ordine), `11daad4` (dipendente_id vuoto) sono del **07/09** e `c8a62fa` (Eliminato nel CHECK) del **03/09**; il ponte, scritto il 30/09, le riporta ancora aperte in §7. Probabilmente l'elenco «monconi» è stato copiato da una memoria più vecchia.

---

## 7. Portabilità verso Windows Server 2022 (IIS + NSSM)

**Bloccanti / funzionali**
- **`reportlab` non è in `backend/requirements.txt` né installato** nella `.venv` (`ModuleNotFoundError` verificato): `gantt_pdf.py:6-10` → `/api/gantt/export-pdf` e `export-png` rispondono 500 **già oggi su Linux** (import lazy, `routes/gantt.py:775,833`).
- **Export PNG** usa `subprocess.run(["pdftoppm", …])` (`routes/gantt.py:874-877`, messaggio `apt install poppler-utils` `:895-896`): binario di sistema Linux; su Windows serve poppler nel PATH del servizio o una libreria (pdf2image/PyMuPDF).
- `e2e/playwright.config.js:7` e `e2e/dati_prova.js:29`: `.venv/bin/python` (su Windows `.venv\Scripts\python.exe`).
- Avvio: `main.py:104` `uvicorn.run(host="0.0.0.0", port=8000)` senza `proxy_headers`/`forwarded_allow_ips`; import "piatti" → AppDirectory NSSM = `backend\`. Dietro IIS/ARR il rate limit per IP (`main.py:36`, `auth_routes.py:108`) vedrebbe un solo IP per tutti (DA VERIFICARE con la config ARR). CORS cablato a localhost (`main.py:63`). `COOKIE_SECURE` default False (`auth_routes.py:48-52`).
- `utils.get_oggi()` = `datetime.now()` naive (`utils.py:35-41`) e numerosi `date.today()`/`datetime.now()`: il server deve stare sul fuso italiano oppure va introdotto `zoneinfo` (+ pacchetto `tzdata` su Windows). `datetime.utcnow` nei default dei modelli (`models.py` ~20 righe): nel DB convivono orari UTC e locali. Frontend: `new Date().toISOString().slice(0,10)` dà la data UTC (`WizardCreazioneProgetto.jsx:117`, `TimelineBars.jsx:161`, `SezioneFasiTask.jsx:846-848`, `api.js:584`, `Gantt.jsx:385,404`).

**Encoding**
- `open()`/`read_text()` senza encoding: `backend/scripts/audit_permessi.py:80,129,154` (sorgenti con `═`, `→`: rischio UnicodeDecodeError con cp1252). Il resto è esplicito (`seed.py:46`, `gemini_client.py:34`).
- Stampe con emoji/simboli in `seed.py:128-252,607` e negli script e2e: con stdout rediretto da NSSM in cp1252 → UnicodeEncodeError possibile. Consigliato `PYTHONUTF8=1` nell'ambiente del servizio.

**Percorsi e script**
- Nessun separatore `\\` cablato; il codice runtime usa `pathlib`/`__file__` (`seed.py:44`, `gemini_client.py:27`). Assoluto Linux solo in `backend/_snapshot_dipendenze.py:20` (`/tmp/...`, script di diagnostica).
- Script shell: `backend/test_solidita.sh`, `backend/test_endpoint_scenario.sh` (curl/cut, senza cookie → probabilmente tutti 401, obsoleti DA VERIFICARE). **Nessuno script shell è necessario al funzionamento.** `.envrc` (direnv) è solo dev. README (`:343-394`) con istruzioni solo Linux (`source`, `sudo -u postgres`, heredoc, `--reload`).
- Nessun `.gitattributes`: con `core.autocrlf=true` i `.sh` diventerebbero CRLF.
- `psycopg2-binary==2.9.12` ok in principio; la venv è Python **3.14.4**: disponibilità delle wheel Windows cp314 per psycopg2-binary, numpy 2.5, pandas 3.0, grpcio, lxml **DA VERIFICARE**. Ridondanze: `python-jose` + `PyJWT`, `passlib` + `bcrypt` mentre `auth.py:8` usa argon2.

---

## 8. Valori IMC cablati

| Valore | Dove | Dove dovrebbe vivere |
|---|---|---|
| Nome prodotto «IMC-Group GANTT Agent» | `backend/main.py:33`, `frontend/index.html:6` | config (`APP_NAME`/`VITE_APP_NAME`) |
| Titolo PDF «GANTT IMC-Group» | `backend/gantt_pdf.py:31`, `routes/gantt.py:811,863` | config / tabella azienda |
| Logo e alt «IMC», «IMC-Group», «Prototipo R1» | `App.jsx:67,71`, `Login.jsx:83,172`, `frontend/public/logo.png` | asset/config per tenant |
| «Ordinario (progetto sviluppato da IMC)»; placeholder clienti reali «Sparkasse, Reale Mutua, BNP» | `WizardCreazioneProgetto.jsx:335,328` | testi neutri / i18n |
| Placeholder «Sparkasse ha anticipato la scadenza DORA…» | `AnalisiInterventi.jsx:628` | testo neutro |
| Prompt Gemini con «IMC-Group», «azienda di circa 15 persone… bandi pubblici», clienti e persone d'esempio, 8h/40h | `prompts/analisi_segnalazioni.md:1,4`; `consuntivazione.md:1,4,48-63,113`; `interpreta_scenario.md:1,4,11-12,50,73,98-103`; `suggerisci_task.md:1,4,8`; `verifica_pianificazione.md:1,4` | template con segnaposto valorizzati da DB/config |
| Modello `gemini-2.5-flash` | `gemini_client.py:59` | env |
| **Filtro per id `P010`** (oggi progetto cliente Maida) | `routes/risorse.py:335` | filtro per `tipologia='interna'` (come `data_db_impl.py:3303`) |
| Famiglie attività interne dal prefisso id (`PC`/`PI`/`PN`) | `routes/attivita_interne.py:123` | colonna/tabella categoria |
| Tipologie `ordinario`/`bando`/`interna` | `models.py:544`, `routes/progetti.py:150`, Wizard `:334-337` (senza `interna`) | tabella tipologie |
| Ore settimanali default 40 | `models.py:490`, `configurazione.py:166`, `gemini_client.py:67`, `scenario_engine.py:441,653`, `data_db_impl.py:397,409`, `Configurazione.jsx:230,240,247` | parametro azienda |
| 8 h/giorno e 5 giorni | `SezioneFasiTask.jsx:541`; `soglie.js:19` (`GIORNI_LAVORATIVI = 5`); `scenario_engine.py:50,62,73` (`weekday() < 5`) | parametro azienda / calendario |
| Festività nazionali italiane fisse + Pasqua; nessun patrono (manca S. Ambrogio 7/12) | `frontend/src/utils/festivita.js:69-86`; **nessun equivalente backend** (frontend e backend contano i giorni lavorativi in modo diverso) | tabella `calendario_festivita` per azienda/sede |
| Soglie saturazione 90/100/125/150 | `Risorse.jsx:14-29,161-164`; `SezioneFasiTask.jsx:566-740` (100% già «sovraccarico», in Risorse no); `routes/risorse.py:396-455`; `gemini_client.py:167` | tabella parametri |
| Soglie 85/100 (incoerenti con le 90 di Risorse) | `AnalisiInterventi.jsx:48,52,703`, `Pipeline.jsx:565` | idem |
| Altre soglie: budget >90/>70 (`VistaManagement.jsx:181`), sforamento fase >50% (`ElencoDettaglio.jsx:65,88`), erosione ≥15/≥5 (`Economia.jsx:19-21`), `GIORNI_IMMINENTE = 7` (`Home.jsx:233`), `soglie.js:21-31` | | tabella parametri |
| Liste profili/fasi cablate | `Pipeline.jsx:5`, `AnalisiInterventi.jsx:19-21` | tabella `ruoli` / `fasi_standard` (esistono già) |
| Stati e colori duplicati frontend | `cantiere/_costanti.js:21-75` vs `models.py:77-112` | esposti dal backend |
| Default cookie `imc_session`, issuer `imc-gantt` | `deps.py:14`, `auth_routes.py:48`, `auth.py:19` | già da env, default da neutralizzare |
| Nomi di persone reali in docstring/commenti | `contesto.py:34-48`, `routes/fasi.py:12,54`, `agent.py:56,77,709`, `configurazione.py:105`, `risorse.py:52`, `consuntivi.py:10,49,106,109`, `dipendenti.py:30,68`, `economia.py:32,46`, `auth_routes.py:69`, `gantt.py:65,83,111`, `data_db_impl.py:587` | da ripulire prima della commercializzazione |
| Seed: aziende `IMC-Improve`/`Innovation Plaza` (`seed.py:171`), ruoli `:96`, competenze `:133`, template fasi `:309`, segnalazioni con nomi reali e cliente «Duferco» `:551-566`, **utenti con password in chiaro `admin123`/`user123`** `:575-600` | `backend/seed.py` | `seed_data.json` / seed demo separato; mai password in chiaro nel repo |
| Script una tantum `add_p010.py` (inserisce P010 «interno», oggi falso) | `backend/add_p010.py:18,26` | da eliminare |
| e2e: utenti `helena@`/`ludovica@imcgroup.it` con `user123`, D004/D002/D011, P002, T112 | `e2e/utenti.js:13,17`, `dati_prova.py:56`, `scenario_*.py`, spec varie | fixture di test (accettabile, ma dipendono dal seed IMC) |

Tariffe: nessuna nel codice (`costo_ora` per dipendente, `models.py:491`).

---

## 9. Test e strumenti

**Suite e2e** (Playwright, `e2e/`, NON eseguita): 52 `test(` nel sorgente, **61 a runtime** (`letture-intatte` itera 10 URL). Config `e2e/playwright.config.js`: baseURL `localhost:3000`, `workers: 1`, timezone Europe/Rome, `webServer` uvicorn+vite con `reuseExistingServer: true` (la trappola «uvicorn vecchio» è reale), healthcheck su `/api/agent/status` (che risponde 401 senza cookie).

| Spec | test | Copre |
|---|---|---|
| `aggiungi-riga.spec.js` | 5 | «Ho lavorato su altro» |
| `banner-scoperti.spec.js` | 5 | banner attività senza spiegazione |
| `economia-avanzamento.spec.js` | 6 | scheda Avanzamento senza pageerror |
| `guardia-fasi.spec.js` | 4 | PATCH fase → 409/200 |
| `letture-intatte.spec.js` | 5 (14 runtime) | le GET rispondono; i campi sganciati non tornano |
| `pagina-unica.spec.js` | 9 | routing /consuntivazione, 404 di `/salva`, salva-blocchi |
| `sottotask-griglia.spec.js` | 7 | scenario T950-T954 |
| `unita-lavoro.spec.js` | 11 | `unitaLavoro.js` + contatore Home |

Nessun test copre Cantiere, Wizard, GANTT, Risorse, Configurazione, Tavolo, SAL, export. La suite lavora sul **DB di sviluppo vero** (impronta md5 prima/dopo).

**Script che scrivono sul DB** (chiamati automaticamente da `apparecchia.js`/`sparecchia.js`): `e2e/dati_prova.py`, `e2e/scenario_sottotask.py` (progetto `PPROVA`, T950-T954), `e2e/scenario_fasi.py` (`PFASI`, T960-T961). Più `backend/add_p010.py` (obsoleto).

**Test backend**: `test_scenario_engine.py` (9, puro), `test_semaforo.py` (11, puro), `test_semaforo_aggregazione.py` (8, **scrive su Postgres** e ripulisce), `test_semaforo_gantt.py` (8, Postgres). Runner `__main__`; `pytest` non è in requirements né nella venv. `backend/scripts/audit_permessi.py`: analisi statica dei decoratori (sola lettura).

**Frontend**: nessun test (niente vitest, `package.json` ha solo dev/build/preview).

**`.gitignore`**
- **Nessuna regola `*.md` generica** in nessuno dei tre `.gitignore`: solo nomi precisi (`.gitignore:17` HANDOFF.md, `:18` NOTE_AFFINAMENTO.md, `:32` frontend/tasks.md, `:41` console.md, `:42` backend/AI.md, `:43` AI.md, `:45` backend/tryback.md, `:46` ROADMAP_GANTT.md).
- `git check-ignore -v docs/INVENTARIO.md CLAUDE.md docs/X.md README.md GANTT_PONTE_OPUS.md` → nessun output, exit 1: **né `docs/` né `CLAUDE.md` verrebbero ignorati**. (Attenzione: il ponte §1 dice «NON versiona i `.md` di design (gitignore)»: è vero solo per i nomi elencati sopra, non per regola.)
- `.gitignore:4` ignora `.venvu/`, ma la venv reale è `.venv/` (ignorata solo dal `.gitignore` interno che crea venv).
- `.gitignore:33` ignora **`*.sql`** ovunque (anche eventuali migration SQL o dump futuri).
- `backend/.gitignore:5` **`_*.py`** colpisce anche `__init__.py`: `backend/routes/__init__.py` è tracciato solo perché aggiunto prima; un nuovo package backend non verrebbe aggiunto da `git add`.
- Tracciati ma ignorati: `backend/_snapshot_dipendenze.py`, `backend/diagnostico_d1.py`, `backend/routes/__init__.py`.

---

## 10. Sorprese

1. **Export PDF del GANTT rotto**: manca `reportlab` (§7). Il bottone è nella pagina GANTT (`Gantt.jsx:373`).
2. **I task nuovi nascono con `ore_pianificate` NULL** → invisibili a carico, saturazione e costo pianificato (§3). Oggi non si vede perché tutti i task vengono dal seed.
3. **`POST /api/tasks/applica` accetta qualunque `campo`** (`AzioneModifica.campo: str`, `routes/tasks.py:112-115`) e lo passa a `modifica_task`, che fa `setattr` su qualunque attributo esistente (`data_db_impl.py:2450-2454`): un manager può scrivere `id`, `progetto_id`, `fase_id`, `ore_pianificate`… con un valore stringa. È solo manager, ma è un buco di integrità. Anche `PATCH /api/progetti/{id}` e `PATCH /api/fasi/{id}` fanno setattr, però limitati dal DTO.
4. **La griglia non ha mai scritto un blocco nel DB vero**: 2249 blocchi, tutti `storico`, ultimo giorno 20/07/2026. `stato_dichiarato` 3 righe (22/07). Il sistema non è mai stato usato davvero.
5. **Home → /elenco = 403 per PM e dipendenti** (`Home.jsx:455`).
6. **Progetti «Da iniziare» invisibili** in Cantiere e GANTT (§1); un progetto creato dal Wizard in quello stato si ritrova solo conoscendo l'URL.
7. **Progetti creati da UI senza `azienda_id`** → la Home li conta tra gli interni (`home.py:335`); Economia li raggruppa senza società.
8. **Ogni salvataggio di un dipendente in Configurazione azzera la sede** (`configurazione.py:169,570`).
9. **Il DB vero è stato creato con `create_all` e "timbrato"** (indici e nomi FK delle migration assenti, §3): `alembic check` è pulito, ma una ricostruzione da migration produrrebbe uno schema leggermente diverso. Inoltre `ck_consuntivo_sottotask_stato` esiste solo in DB/migration, non nel modello.
10. **Nessun indice su `task.progetto_id/fase_id/dipendente_id`** né su `consuntivi(dipendente_id, settimana)`: irrilevante a 114 task, non a scala prodotto.
11. **`/docs` e `/openapi.json` pubblici**: in produzione espongono la mappa di tutte le API.
12. **Password demo in chiaro** nel seed versionato (`seed.py:575-600`); se il DB di produzione nasce dal seed, gli account hanno `admin123`/`user123`. Non esiste un endpoint per cambiare password.
13. **`GET /api/attivita-interne` non filtra per persona**: qualunque utente autenticato vede le attività interne di tutti (la pagina è manager-only, l'API no).
14. **Il ponte cita file che non esistono nel repo** (§6) e un FaseStreamExtractor che sta in un altro progetto: la «memoria» e il codice divergono anche sugli strumenti, non solo sui debiti.
15. `frontend/src/api.js:559-561` e `App.jsx:184-187` descrivono come presenti cose già rimosse; `carico_settimanale_dipendente` ha docstring che dice `ore_stimate` (`data_db_impl.py:1259`) mentre il codice usa `ore_pianificate` (`:1317`).
16. Dipendenza npm `frappe-gantt` inutilizzata; `auth_gantt.zip` (17 KB, ignorato) nella radice; `console.md` vuoto.
