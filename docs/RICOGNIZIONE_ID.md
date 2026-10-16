# Ricognizione: id numerici e baseline delle migration

*Passo R0, sola lettura. Fotografia al commit `61e69af` (16/10/2026), con l'albero di lavoro pulito; il lavoro dell'altra sessione su `routes/progetti.py`, `tests/test_ciclo_progetto.py` ed `e2e/scenario_*.py` è entrato nel commit `0b52e2d`. Come INVENTARIO.md, non si aggiorna.*

**Premesse del prompt.**
- Nessun database di produzione.
- Tutti i database si ricostruiscono dal seed.
- I dipendenti vivono nel seed.

**Metodo.**
- Solo lettura statica.
- Le righe sono verificate con grep e sed.
- Non ho interrogato nessun database.
- Le righe del codice vanno lette sulla versione su disco a questa data.

---

## 1. Dove gli id di progetti, task e dipendenti sono usati come testo

### 1.1 Chiavi esterne e colonne che li contengono

Oggi sono tutte `String(10)`; le righe sono di `backend/models.py`.

**Verso `progetti.id`** (PK a 557)

| Tabella.colonna | Riga | Regola | Note |
|---|---|---|---|
| fasi.progetto_id | 710 | CASCADE | |
| task.progetto_id | 785 | CASCADE | |
| note_progetto.progetto_id | 1316 | CASCADE | tabella morta (BACKLOG) |
| segnalazioni.progetto_id | 1303 | nessuna, nullable | |
| sal_snapshot.progetto_id | 1365 | nessuna | `fk_sal_snapshot_progetto_id` |
| bollettino_economico.progetto_id | 1389 | nessuna | `fk_bollettino_economico_progetto_id` |

**Verso `task.id`** (PK a 784)

| Tabella.colonna | Riga | Regola | Note |
|---|---|---|---|
| dipendenza_task.task_predecessore_id e task_successore_id | 903-910 | CASCADE | `uq_dipendenza_task`, CHECK `ck_dipendenza_task_no_self` |
| sottotask.task_id | 970 | CASCADE | con `uq_sottotask_id_task (id, task_id)` a 1001, bersaglio di una FK composta |
| assegnazioni.task_id | 1038 | CASCADE | tabella morta (BACKLOG) |
| consuntivi.task_id | 1056 | CASCADE | `uq_consuntivo` |
| blocchi_ore.task_id | 1218 | CASCADE | indicizzata |
| blocchi_ore (sottotask_id, task_id) → sottotask (id, task_id) | 1231-1234 | CASCADE | FK composta `fk_blocchi_ore_sottotask_task`; inoltre `uq_blocchi_ore` NULLS NOT DISTINCT (1238-1241) |
| vista `ore_settimanali` | 1259-1266 | | GROUP BY su task_id e dipendente_id. È dichiarata anche come `Table` di sola lettura (1285-1286, String(10)) e nella migration f0a1b2c3d4e5 |

**Verso `dipendenti.id`** (PK a 508)

| Tabella.colonna | Riga | Note |
|---|---|---|
| dipendenti_competenze.dipendente_id | 383 | CASCADE, `uq_dip_comp` |
| dipendenti_ruoli_aggiuntivi.dipendente_id | 426 | CASCADE, `uq_dip_ruolo_agg` |
| utenti.dipendente_id | 465 | nullable |
| progetti.pm_id | 599 | nullable |
| task.dipendente_id | 838 | nullable |
| sottotask.dipendente_id | 982 | nullable, `sottotask_dipendente_id_fkey` |
| assegnazioni.dipendente_id | 1039 | morta |
| consuntivi.dipendente_id | 1057 | |
| consuntivo_sottotask.dipendente_id | 1138 | `uq_consuntivo_sottotask` |
| blocchi_ore.dipendente_id | 1214 | parte di `uq_blocchi_ore` |
| segnalazioni.dipendente_id | 1302 | nullable |
| note_progetto.autore_id | 1317 | morta |
| interventi.approvato_da | 1332 | morta |

**Colonne senza chiave esterna che contengono gli stessi id**
- `sal_snapshot.consolidato_da` (1368) e `bollettino_economico.consolidato_da` (1392): id del dipendente, senza FK di proposito.
- `interventi.segnalazione_id` (1328): punta a `segnalazioni.id`, anch'esso `String(10)` (1299).
- JSONB `stato` di `sal_snapshot` e `bollettino_economico`: vedi 1.2.4.

`utenti.id`, `fasi.id`, `sottotask.id`, `ruoli`, `competenze` e `azienda` sono già interi.

### 1.2 Backend

**1.2.1 Tipi testuali nell'API**
- **Path e query `str`:**
  - `progetti.py:607, 781, 931, 962`
  - `tasks.py:106, 338, 364, 496`
  - `fasi.py:410`
  - `sal.py:34, 51, 86`
  - `bollettino.py:39, 76`
  - `dipendenti.py:192`
  - `configurazione.py:538, 585`
  - `attivita_interne.py:250`
  - `sottotask.py:335, 362, 447, 577`
  - `risorse.py:126, 129` (`escludi_task_id: str = None`)
  - `gantt.py:190, 271, 284, 710, 761`
- **DTO:**
  - `progetti.py`:
    - `ProgettoCreate.id` (177): il client sceglie l'id;
    - `pm_id` (197, 235);
    - `dipendente_id` (270, 296);
    - `TaskStaffing.predecessore` (300).
  - `tasks.py`:
    - `task_predecessore_id` (96);
    - `progetto_id` (170);
    - **`dipendente_id: str = ""` (178)**: la stringa vuota vale «nessuno»;
    - altro `dipendente_id` (212).
  - `fasi.py:124`
  - `sottotask.py:208, 212, 235`
  - `consuntivi.py:214` (`Union[str, int]`, vedi 2.4)
  - `auth_routes.py:68`

**1.2.2 Generazione degli id**
- **Progetti:**
  - in `models.py`: `PREFISSO_ID_PROGETTO`, `CIFRE_ID_PROGETTO`, sequenza `progetti_numero_seq`, `formatta_id_progetto` e `riallinea_numero_progetti` (662-694);
  - `data_db_impl.py:2122-2131` `_next_progetto_id`, chiamata da `progetti.py:405` e `487` come `req.id or _next_progetto_id()`: il client può imporre un id libero, e l'unicità si controlla in Python (408, 489-492).
- **Task:**
  - `data_db_impl.py:2019-2026` `_next_task_id` e `2082-2119` `genera_id_task_multipli`, basate su `max(Task.id)` testuale;
  - chiamate da `progetti.py:525, 704, 863` e da `tasks.py:304` tramite `aggiungi_task`;
  - è il bloccante 3.1 dell'audit: si inceppa oltre T999.
- **Dipendenti:** `configurazione.py:506-511`, con `max(Dipendente.id)` testuale. Il commento a 497-498 cita una sequenza che non esiste.
- **Segnalazioni:** nessun generatore. Gli id vengono solo dal seed (`S001`–`S003`).

**1.2.3 Ordinamenti che dipendono dal testo dell'id**
- `ordine_progetti()` (`models.py:694-703`), usato da:
  - `consuntivi.py:442`
  - `progetti.py:369`
  - `gantt.py:405, 727`
  - `attivita_interne.py:156`
- `ORDER BY Task.id` usato come ordine e non solo come spareggio:
  - `data_db_impl.py:1321` («prima occorrenza vince»)
  - `dipendenti.py:129` (il commento a 119-121 dice che cambiarlo cambierebbe il payload)
  - `data_db_impl.py:1561`
  - `attivita_interne.py:165`
  - `fasi.py:321`
- `ORDER BY Task.id` come spareggio: `data_db_impl.py:3059` e `models.py:777` (`order_by="Task.ordine, Task.id"`).
- `sorted()` in Python sugli id: `data_db_impl.py:2386, 2889, 2908, 2953`.

**1.2.4 Id dentro JSON, nomi file e messaggi**
- **Snapshot SAL** (JSONB, `schema_version` 2): `progetto.id` (3014), `pm_id` (3024), `task.id` (3073), `dipendente_id` (3080), `task_predecessore_id` (3084).
- **Bollettino** (JSONB, `schema_version` 1): `progetto_id` (3365). `dettaglio_persone` nasce da un dict indicizzato per id del dipendente (3304-3311), e come ripiego usa l'id al posto del nome (3305).
- **Nome file dell'Excel:** `gantt.py:991-995`, `gantt_<progetto_id|portafoglio>_<data>`, allineato a `esportaGantt.nomeBaseFile`.
- **Messaggi all'utente con l'id:**
  - `progetti.py:408, 491, 662, 668, 808, 816, 833, 901, 947, 971, 977`
  - `tasks.py:257, 408, 484, 491`
  - `sottotask.py:346, 388, 615`
  - `attivita_interne.py:278, 288`
  - `fasi.py:325`
  - `sal.py:40`
  - `risorse.py:177`
  - `consuntivi.py:240, 732, 737`
  - `data_db_impl.py:411, 2200, 2240, 2367, 2377, 2386, 2562, 2645, 2962, 3005, 3464`
  - Il frontend ne riparsa uno (1.3.2).

**1.2.5 Stringa vuota usata come «nessun dipendente»**
- In ingresso: `tasks.py:178`, `data_db_impl.py:398`.
- In uscita: `gantt.py:174, 569, 745`, `tasks.py:146`, `data_db_impl.py:399` (`{"id": ""}`) e `2473`.
- Con id interi diventerebbe un tipo misto int/"".

**1.2.6 Confronti fra l'id del path e un valore letto dal DB**
- Se il parametro di path non diventa `int`, `"5" != 5` fallisce in silenzio. I punti:
  - `dipendenti.py:200`
  - `sal.py:41`
  - `attivita_interne.py:284`
  - `tasks.py:254`
  - `sottotask.py:608`
  - `data_db_impl.py:2373`
  - `data_db_impl.py:3461` (`p["progetto_id"] == pid`)
- Nessun id viene interpolato in SQL. L'unica f-string SQL è `setval('{nome}')` (`models.py:688, 690`), con il nome preso da una costante.

### 1.3 Frontend

**1.3.1 URL**
- **Rotte:** `/cantiere/:progettoId` (`App.jsx:212`) e `/elenco/:progettoId` (`App.jsx:218`). Il parametro arriva da `useParams`, quindi è sempre una stringa. Oggi viene solo inoltrato all'API (`CantiereDettaglio.jsx:220, 248, 256, 263, 269`; `ElencoDettaglio.jsx:191, 247, 294`).
- **`navigate` con id:**
  - `Home.jsx:455`
  - `Cantiere.jsx:290, 320`
  - `Archivio.jsx:132`
  - `Gantt.jsx:201, 207`
  - `ElencoDettaglio.jsx:247`
- **`api.js`, id nel path senza `encodeURIComponent`:**
  - 190, 200, 207, 212 (progetti)
  - 281, 288, 296 (task)
  - 320, 355 (sottotask del task)
  - 426, 438 (SAL)
  - 467 (attività interne)
- **`api.js`, id in query string:** 217, 228, 238, 385, 388, filtrati per verità. Con id numerici un id 0 verrebbe scartato; non accade, perché le identity partono da 1.
- **Configurazione:** il client proprio `useCrud` (`Configurazione.jsx:36, 45`) mette l'id del dipendente nel path.
- **`sessionStorage.postLoginRedirect`** (`api.js:74`, `RequireAuth.jsx:29`, `RequireManager.jsx:32`, `Login.jsx:47-48`) salva URL con l'id.

**1.3.2 `<select>` e confronti: il punto critico**

Il `value` di un `<select>` è sempre una stringa. Oggi gli id sono stringhe e i confronti con `===` funzionano; con id numerici smettono di funzionare in silenzio.

| Dove | Cosa succede con id numerici |
|---|---|
| `SezioneFasiTask.jsx:863` (responsabile, via `FormSelect`, `Form.jsx:96`) → `:733` e `:835` `dipendenti.find(d => d.id === form.dipendente_id)` | il controllo di saturazione oltre 125% e `IndicatoreCapacita` non trovano più il dipendente |
| `SezioneFasiTask.jsx:762, 782` `dipendente_id: form.dipendente_id \|\| ''` | «nessuno» viaggia come `''`, che un campo intero rifiuta |
| `SezioneFasiTask.jsx:880-888` dipendenze (`e.target.value`) → 769, 786, `CantiereDettaglio.jsx:309` | tipi misti: stringa dopo un cambio, numero se arriva dall'API (713) |
| `WizardCreazioneProgetto.jsx:122` `anagrafica.pm_id.trim()` | **TypeError** se `pm_id` arriva numerico dalla bozza (55, da `Cantiere.jsx:74`) |
| `WizardCreazioneProgetto.jsx:363-367, 150` (PM) e `611-619, 167` (dipendente dei task) | il valore inviato è una stringa |
| `AggiungiTaskModal.jsx:156-163, 71` | il valore inviato è una stringa. Per `fase_id` a `:145` si usa già `Number(...)`, ed è il modello da seguire |
| `Gantt.jsx:131` `ganttFiltrato.find(p => p.id === filtroProgetto)` | il titolo dell'export perde il nome del progetto |

Confronti fra due id che arrivano entrambi dall'API. Funzionano finché il backend li tipizza allo stesso modo su tutti e due i lati:
- `SezionePersone.jsx:24, 37`
- `SezioneFasiTask.jsx:147, 166, 794, 819, 919, 924`
- `Risorse.jsx:67, 68, 80, 95, 185`
- `unitaLavoro.js:87`
- `ConsuntivazioneOre.jsx:174, 471, 793`
- `AggiungiRiga.jsx:72`
- `Gantt.jsx:205`
- `Economia.jsx:299, 302, 308`

Map e Set con chiave id:
- `ConsuntivazioneOre.jsx`: 164-170, 217-223, 333-339
- `AggiungiRiga.jsx`: 73, 80-88
- `diffSnapshot.js`: 108, 140-185
- `SezioneSAL.jsx`: 116-126
- `GanttChartFasi.jsx`: 57, 80, 102-103, 206-221
- `SezioneFasiTask.jsx`: 68-75, 187-189, 295
- `VistaManagement.jsx`: 109-120

`ConsuntivazioneOre.jsx:817-828` (`leggiErrori`) riparsa il messaggio 400 del backend con `/^(task \S+|sottotask \d+)(:|,)/`. Regge gli id numerici, ma dipende dal testo del messaggio: se il backend scrivesse un codice al posto dell'id, la mappa non troverebbe più nulla.

**1.3.3 Id mostrati all'utente**

Oggi è l'id stesso a fare da codice leggibile.
- **Progetto:**
  - `SezioneAnagrafica.jsx:90` (riga «ID»)
  - `Cantiere.jsx:296`, `Archivio.jsx:145`, `ElencoDettaglio.jsx:242`, `CantiereDettaglio.jsx:354`
  - `AttivitaInterne.jsx:194`
  - `WizardCreazioneProgetto.jsx:192`
  - come ripiego del nome: `AggiungiRiga.jsx:83`, `ConsuntivazioneOre.jsx:219`
  - nomi file dell'export: `esportaGantt.js:60-61`
- **Task:**
  - `SezioneFasiTask.jsx:302, 432, 459, 825` («Modifica task {id}»), `887` (opzione «{id} — {nome}»), `919, 922`
  - `AggiungiRiga.jsx:76` (ricerca sul testo dell'id), `222`
  - `ConsuntivazioneOre.jsx:177` (campo `codice` = `` `${t.task_id} · #${p.id}` ``), mostrato a `836` e `951`
- **Dipendente:**
  - `SezioneAnagrafica.jsx:97` mostra `pm_id` grezzo al posto del nome: un difetto già oggi;
  - `VistaManagement.jsx:221` usa l'id come ripiego del nome.

**1.3.4 Chiavi React**
- 64 `key={…id…}` in 19 file, innocue: React accetta numeri.
- Chiavi composte, mai riparsate:
  - `GanttChartFasi.jsx:271, 303, 324, 439, 459, 500`
  - `SezioneSAL.jsx:99, 103`
  - `ConsuntivazioneOre.jsx:176, 191, 204, 207, 224`
- Attributi DOM usati dagli e2e:
  - `ganttSvg.js:369` `data-id`
  - `Economia.jsx:398` `data-progetto`
  - `AggiungiRiga.jsx:216` `data-aggiungi-task`
  - `griglia.js:16` `data-riga="task:${id}"`

### 1.4 Seed

**`seed_data.json`**
- Contiene:
  - 18 dipendenti, D001–D018;
  - 38 progetti: P001–P011, PC01–PC05, PI01–PI15, PI05b, PI12b, PI13b, PI15b, PN01–PN03;
  - 114 task, T001–T114;
  - 2632 consuntivi.
- Riferimenti incrociati, tutti testuali:
  - `pm_id` (10 valorizzati);
  - `progetto_id` e `dipendente_id` dei task;
  - `predecessore` (24 con un id, 90 con `""`);
  - `task_id` e `dipendente_id` dei consuntivi.
- Nessun riferimento orfano.

**`seed.py`**
- Id espliciti:
  - dipendenti 219;
  - progetti 365, con `pm_id` a 363 e 372;
  - task 435-457.
- Chiave interna `(pid, fase_nome)` (390-418).
- `riallinea_numero_progetti` alla riga 383.
- **Dipendenze SS/FF cablate** per id (483-495).
- **Segnalazioni cablate:** S001/D008, S002/D004, S003/D003 (570-586).
- **Utenti legati ai dipendenti per id** (594-619): D001, D002, D011, D004.

### 1.5 Migration

- **Catena:** lineare, 41 file, senza branch.
  - Prima: `e733e23ae7a1_create_initial_schema`.
  - Head: `c8d9e0f1a2b3_sequenza_numero_progetti`.
- **Dipendono dalla forma degli id:**
  - `c8d9e0f1a2b3:41-49`: sequenza e `max(substr(id,2)::bigint) WHERE id ~ '^P[0-9]+$'`;
  - `f6a7b8c9d0e1:71-73`: `UPDATE progetti SET tipologia='interna' WHERE id = 'P010'`;
  - `c1d2e3f4a5b6:81-88`: `ROW_NUMBER() OVER (PARTITION BY fase_id ORDER BY id)`, cioè l'ordine dei task ricavato dall'id testuale;
  - `e5f6a7b8c9d0:107-148`: copia di `task.predecessore`, che è testo.
- **Scrivono dati:**
  - `a7b8c9d0e1f2:66, 92-106`: azienda cablata più `UPDATE dipendenti`;
  - `a5b6c7d8e9f0:67-74`: ruolo «PM»;
  - `f1a2b3c4d5e6:93`: blocchi_ore ricavati dai consuntivi;
  - più gli upgrade e downgrade di c3d4, b8c9, f8a9, a3b4, d1e2, e2f3, f3a4.

### 1.6 Test pytest

- **`conftest.py:90-145`:** a ogni sessione, su `gantt_test`:
  - `DROP SCHEMA public CASCADE`;
  - `alembic upgrade head` su tutta la catena;
  - `seed.py`.
- **`test_id_progetti.py`:** è interamente sulla forma dell'id:
  - `^P[0-9]+$` (32);
  - `int(pid[1:])` (75, 148);
  - «P012»/«P1000» (120-121);
  - «PPROVA», «PZ01», «P450» → «P451» (134-141);
  - «P999», «PA01» → «P1000» e ordine numerico-poi-alfabetico (154-181).
- **`test_ciclo_progetto.py`:** id espliciti PT501–PT531 nei payload e negli URL (100-398).
- **Altri test su DB:** prendono «il primo» progetto o task senza `order_by`, quindi dipendono dall'ordine fisico (per esempio `test_semaforo_aggregazione.py:201`, `test_semaforo_gantt.py:273-276`).

### 1.7 E2E (scrivono su gantt_db, il database di sviluppo)

- **`utenti.js:68-77`:** helena = `'D004'`, ludovica = `'D011'`.
- **`dati_prova.py`:**
  - `DIPENDENTE="D004"` (72);
  - task di prova da T900 a T907 su P002 e P008, **con `fase_id` cablati 8 e 31** (103-110): valgono solo su un seed appena caricato;
  - cancella per `Task.id.in_(ids)` (134-139);
  - `--impronta` ordina per id testuale (155-180).
- **`scenario_fasi.py`:** `PFASI`, `D004`, `T960`/`T961` (52-56).
- **`scenario_sottotask.py`:** `PPROVA`, `D004`, `D002`, T950–T954 (101-106, 159-212).
- **Spec con id cablati:**
  - `aggiungi-riga` (30-43: T900–T907, più i task del seed T004, T020, T030, T043, T104, T109)
  - `banner-scoperti` (20-21)
  - `pagina-unica` (119, 133, 142)
  - `unita-lavoro` (24-25, 101-105)
  - `sottotask-griglia` (27-176)
  - `guardia-fasi` (24-116, anche `/api/fasi/PFASI`)
  - `letture-intatte` (34-35, `/api/fasi/P002`, `/api/sal/P002`)
  - **`ciclo-progetto.spec.js:94`** `toMatch(/^P\d{3,}$/)`
  - `export-gantt` (149-157, sul nome file)
- **`backend/test_solidita.sh`:** `D001`, `P001`, `T003` (47-60). Lo script è già morto (porta 8000, nessuna autenticazione).

---

## 2. Dove la forma dell'id porta un significato

| # | Dove | Significato | Cosa diventa |
|---|---|---|---|
| 2.1 | `attivita_interne.py:117-126` `FAMIGLIE = {"PC": "Corsi", "PI": "Mansioni continuative", "PN": "Sviluppo interno"}`, `_famiglia(id[:2])` | la famiglia di un'attività interna. Il commento dice che non c'è una colonna | serve un dato: vedi 3.4 |
| 2.2 | `models.py:670-672` regex `^P[0-9]+$` e `substr(id, 2)`; `riallinea_numero_progetti` (679-691); migration c8d9 | «generato» o «scritto a mano», e il numero progressivo | non serve più: genera il DB |
| 2.3 | `models.py:694-703` `ordine_progetti()` | l'ordine delle liste: prima gli id generati per numero, poi gli altri alfabetici | ordine per id (cioè di creazione) o per codice, vedi 3.5 |
| 2.4 | `consuntivi.py:213-214, 244-248` | il **tipo** dell'id distingue task (`str`, «es. "T017"») da sottotask (`int`) | con task interi la validazione respinge ogni unità task: resta solo `tipo` a distinguere |
| 2.5 | `data_db_impl.py:2024-2026, 2112-2116`; `configurazione.py:507-511` | `startswith("T"/"D")`, `[1:]`, `isdigit`, `:03d`, ripiego `"T001"` | spariscono |
| 2.6 | `ORDER BY Task.id` (1.2.3); migration `c1d2e3f4a5b6` | l'ordine di creazione letto dal testo, dove già oggi T1000 viene prima di T999 | `ORDER BY ordine, id` numerico |
| 2.7 | Prefissi P / T / D / S | distinguono a colpo d'occhio un progetto da un task nei messaggi e nei log. Con id interi `5` può essere un progetto o un task | i messaggi nominano l'entità («task 5», o il nome) |
| 2.8 | `seed_data.json`: PC, PI, PN e i suffissi `b` (PI05b…) | la famiglia e la variante, come convenzione del seed | colonna famiglia, e codice libero |
| 2.9 | `f6a7b8c9d0e1:71-73` `'P010'`; `add_p010.py`, `diagnostico_d1.py` | id cablati | spariscono con la baseline e con la rimozione degli script morti |
| 2.10 | `e2e/ciclo-progetto.spec.js:94` `/^P\d{3,}$/`, `test_id_progetti.py` | verificano la forma | diventano verifiche sul codice leggibile |

La tipologia «interna» **non** dipende dal prefisso: è la colonna `tipologia`. Fa eccezione la sola migration f6a7, che l'ha impostata per P010.

---

## 3. Schema di arrivo proposto

### 3.1 Tipo degli id

`progetti.id`, `task.id`, `dipendenti.id` e `segnalazioni.id` diventano `Integer`, chiave primaria generata dal database con `GENERATED BY DEFAULT AS IDENTITY` (`Identity()` in SQLAlchemy). Tutte le FK della tabella 1.1 diventano `Integer`, e lo stesso vale per `consolidato_da`, `interventi.segnalazione_id` e le colonne della vista.

Motivi:
- **Il generatore sta nel database.** Chiude da solo il bloccante dell'audit (T1000) e le corse fra creazioni contemporanee, e toglie tre generatori applicativi diversi.
- **Integer e non BigInteger.** Sono 2 miliardi di valori, e le altre PK del modello (`fasi`, `sottotask`, `blocchi_ore`) sono già Integer. Un tipo solo per tutte le chiavi evita confronti misti.
- **Identity e non `serial`.** È lo standard SQL; la sequenza appartiene alla colonna e la segue in dump e restore. `BY DEFAULT` e non `ALWAYS` perché un ripristino o un test possono ancora inserire un id esplicito.
- **Il client non sceglie più l'id.** Oggi `ProgettoCreate.id` (`progetti.py:177`) lo permette. L'id interno non è un dato dell'utente: quello che l'utente vuole scegliere è il codice (3.2).

### 3.2 Chi ha un codice leggibile

| Entità | Codice | Regola | Motivo |
|---|---|---|---|
| **Progetto** | sì: `progetti.codice VARCHAR(20) NOT NULL`, **UNIQUE** | generato dal DB se non viene fornito; modificabile dal manager | il codice di commessa è il modo in cui le persone parlano di un progetto (P002, PC03), finisce nei nomi file, nelle riunioni e nei gestionali esterni |
| **Dipendente** | no codice generato. Facoltativa una `matricola VARCHAR(20) NULL`, UNIQUE quando presente | scritta da chi gestisce il personale, mai generata | le persone si riconoscono per nome. La matricola, se un'azienda la vuole, viene dal suo ufficio del personale: generarla noi creerebbe un secondo numero da tenere allineato (regola 1). I legami tecnici (seed, utenti, e2e) passano per l'email |
| **Task** | no | — | nessuno nomina un task con un codice fuori dall'applicazione. Dentro l'applicazione si riconosce da nome, fase e progetto. Dove serve un riferimento breve (messaggi d'errore, tendina delle dipendenze) basta «#id» |
| **Segnalazione** | no | — | non ha uso esterno, e oggi nessuno la crea dall'interfaccia |

**Generazione del codice di progetto.**
- Una sequenza `progetti_codice_seq`, che è l'attuale `progetti_numero_seq` rinominata, alimenta il default `<prefisso><numero a 3 cifre>`, cioè P001, P002, … P1000.
- Il prefisso e il numero di cifre diventano parametri di configurazione: oggi sono costanti nel codice (`models.py:662-663`), e la regola 5 non le vuole cablate.
- Il codice si calcola nel servizio alla creazione, leggendo `nextval` nella stessa transazione dell'INSERT. Non si calcola in Python a partire dal massimo.
- Un codice inserito a mano (PC03, una commessa del gestionale) non tocca la sequenza. Se collide, risponde 409 grazie al vincolo UNIQUE, e non per un controllo applicativo che due richieste potrebbero superare insieme.
- Il confronto di unicità è sensibile alle maiuscole. Proposta: normalizzare in maiuscolo alla scrittura, con un CHECK `codice = upper(codice)`, così «p002» e «P002» non convivono.
- `riallinea_numero_progetti` resta solo per il seed, che inserisce codici espliciti.

**Alternativa scartata:** un numero di task progressivo per progetto (P002-07). Servirebbe un secondo generatore con lock sulla riga del progetto per un dato che oggi nessuno usa fuori dall'applicazione. Si può aggiungere dopo, se qualcuno lo chiede.

### 3.3 URL e API

- **URL con l'id numerico:** `/cantiere/12`, `/elenco/12`; nella pagina si mostrano codice e nome.
  - Il codice è modificabile: un URL basato sul codice si romperebbe a ogni rinomina, e i link salvati smetterebbero di funzionare.
  - L'id non cambia mai.
- **Parametri di path tipizzati `int` in FastAPI.** Un `/api/progetti/P002` risponde 422, non 404: chiunque usi ancora un id vecchio se ne accorge subito.
- **Ricerca per codice:** un parametro di filtro sulla lista dei progetti (`?codice=P002`), non un secondo modo di indirizzare la stessa risorsa.
- **Nessun dipendente:** `null`, mai `""`. Vale in entrata e in uscita (1.2.5, 1.3.2).
- **Nomi file dell'export:** `gantt_<codice>_<data>`, oppure `gantt_portafoglio_<data>`.

### 3.4 Famiglie delle attività interne

- Oggi la famiglia è dedotta dal prefisso (2.1). Proposta:
  - una tabella `categorie_attivita` (`id`, `nome`, `ordine`, `attivo`), gestita da Configurazione;
  - `progetti.categoria_id` nullable, FK;
  - CHECK `tipologia = 'interna' OR categoria_id IS NULL`.
- Il seed crea «Corsi», «Mansioni continuative» e «Sviluppo interno» e le assegna come fanno oggi i prefissi.
- **Motivo:** è un'informazione di dominio e deve stare in un dato (regola 1). Le famiglie di un'altra azienda saranno diverse (regola 5, DECISIONI §96).
- **Alternativa scartata:** una colonna di testo libero, che porta refusi e nessuna lista da cui scegliere.

### 3.5 Ordinamenti

- **Liste di progetti:** `ORDER BY codice, id`, oppure per nome, come deciderà la pagina. `ordine_progetti()` sparisce. Un codice libero riporta il problema P999/P1000 nell'ordine alfabetico. Proposta: ordinare per id, cioè per ordine di creazione, quando serve un ordine stabile, e per codice solo dove l'utente lo sceglie.
- **Task:** `ORDER BY ordine, id`, numerico.
- **Snapshot JSONB:** SAL passa a `schema_version` 3 e bollettino a 2. Dentro restano gli id e si aggiunge il codice del progetto. Con la ricostruzione dei database non sopravvive nessuno snapshot vecchio, quindi non serve un lettore per la versione 2.

---

## 4. Baseline delle migration

### 4.1 Come la costruirei

1. **Prima una baseline a schema invariato, poi il cambio degli id.** Sono due passi distinti: se in un passo solo si rifanno le migration e si cambiano i tipi, una differenza di schema non si saprebbe a quale dei due attribuirla.
2. Si parte da un database vuoto con lo schema `public` ricreato, come fa `conftest.py`:
   - su questo si genera una bozza con `alembic revision --autogenerate`;
   - **la bozza si rivede riga per riga**, come chiede la regola 10, e si scrive a mano ciò che l'autogenerate non vede:
     - la vista `ore_settimanali`, con lo stesso testo di `models.py:1259-1266`;
     - i CHECK nominati;
     - `postgresql_nulls_not_distinct` su `uq_blocchi_ore`;
     - le sequenze;
     - i `server_default`.
3. Il file nuovo, per esempio `0001_baseline.py`, ha `down_revision = None`. Le 41 migration attuali si tolgono con `git rm` e restano nella storia di git.
4. Il downgrade della baseline è `DROP SCHEMA` oppure niente: tornare indietro da una baseline significa ricostruire il database.

### 4.2 Cosa contiene

- **Solo lo schema:**
  - tabelle, PK, FK con le loro regole ON DELETE;
  - UNIQUE, CHECK e indici;
  - le sequenze: oggi quella dei progetti, domani le identity;
  - la vista.
- **Nessun dato.** Gli INSERT di a7b8 (azienda cablata), a5b6 (ruolo «PM»), f6a7 (P010) e f1a2 (blocchi dai consuntivi) erano adattamenti di database esistenti, che oggi non ci sono. In un database nuovo i dati di base li porta il seed in sviluppo, e la Configurazione in produzione. Il codice non cerca il ruolo «PM» per nome: verificato con grep su route e strato dati.
- **Da decidere prima di scriverla** (sono domande per te):
  - **Le tabelle morte** `assegnazioni`, `note_progetto` e `interventi`, e le colonne morte del BACKLOG. Una baseline è l'occasione per non ricrearle, dato che non c'è nessun dato da salvare, ma lo schema cambia e la verifica 4.3 va fatta prima. Proposta: baseline identica, e un passo successivo che le toglie.
  - **Una `naming_convention` sul MetaData** (già nel BACKLOG). In una baseline costa zero, ma cambia i nomi dei vincoli che oggi sono quelli di default di Postgres (`task_fase_id_fkey`, citato da `b7c8:38`). Stessa proposta: dopo, in un passo separato.

### 4.3 Come si verifica che produca lo schema del modello

Servono tre controlli, perché ciascuno da solo ha un punto cieco.

1. **Baseline contro catena attuale.** Lo schema prodotto dalle 41 migration va confrontato con quello prodotto dalla baseline.
   - Non con `pg_dump --schema-only` grezzo: l'ordine delle colonne è diverso (una colonna aggiunta da una migration tardiva sta in fondo, e nella baseline sta dove la mette il modello), e il dump lo riporterebbe come una differenza.
   - Il confronto va fatto su un'interrogazione normalizzata del catalogo:
     - `information_schema.columns`, ordinata per tabella e colonna, con tipo, nullabilità e default;
     - `pg_get_constraintdef` di ogni vincolo, ordinati per nome;
     - `pg_indexes`;
     - `pg_get_viewdef`;
     - `pg_sequences`.
   - Il risultato atteso è **nessuna differenza**.
2. **Baseline contro modello, con `create_all`.** Lo stesso confronto fra il database della baseline e uno creato con `Base.metadata.create_all`. Copre i CHECK, che `alembic check` non confronta. È esattamente il buco che ha lasciato sparire i CHECK sugli stati (`models.py:257-269`).
3. **`alembic check` sul database della baseline.** Deve dire «nessuna operazione», ed è il controllo che gira poi a ogni passo futuro.

**Dove fare i confronti.**
- `vicacrit` non può creare database (`conftest.py:97`).
- I confronti 1 e 2 usano quindi due schemi dentro `gantt_test`, non due database: alembic con `search_path` impostato, e `create_all` con `schema_translate_map`. Va provato; se non regge, serve un secondo database creato da chi ha i permessi.
- Proposta: rendere permanente il confronto 2 come test pytest (`test_schema_allineato.py`), così la deriva fra modello e migration diventa un test rosso e non una scoperta su `pg_constraint`.

### 4.4 Cosa succede ai database e agli script

- **gantt_test:** nessun intervento. `conftest.py` già svuota lo schema e applica `upgrade head` a ogni sessione. Dalla baseline in poi applicherà un file solo, e la sessione di test partirà più in fretta.
- **gantt_db:**
  - la tabella `alembic_version` contiene `c8d9e0f1a2b3`, che dopo la baseline non esiste più, e `alembic upgrade` si fermerebbe con «Can't locate revision». Quindi **gantt_db va ricostruito**: svuotamento dello schema `public`, `alembic upgrade head`, `seed.py`;
  - oggi questa procedura vive solo dentro `conftest.py`. Proposta: uno script `backend/scripts/ricostruisci_db.py`, portabile su Windows, con:
    - una guardia sul nome del database (rifiuta tutto ciò che non è nella lista dei database di sviluppo);
    - una conferma esplicita;
    - l'impronta dei dipendenti stampata prima e dopo;
  - in alternativa, `alembic stamp` sulla baseline senza ricostruire. Vale solo per la baseline a schema identico, e ha senso solo se il confronto 4.3 sul catalogo di gantt_db è vuoto. Per il cambio degli id non basta.
- **seed:** nella baseline a schema invariato non cambia. Con gli id numerici cambia molto (passi 5.5-5.7):
  - inserisce senza id, e risolve i riferimenti del JSON attraverso un dizionario «chiave del seed → id generato»;
  - le chiavi del JSON (D001, P002, T063) possono restare come etichette interne del file, oppure diventare codice ed email.
- **e2e:**
  - non toccano lo schema, quindi nella baseline non cambiano: si fa girare la suite completa per conferma;
  - con gli id numerici vanno riscritte le fixture con id cablati, cioè T900–T907, T950–T954, T960–T961, PFASI, PPROVA, D004, D011 e i `fase_id` 8 e 31. Le fixture creano senza id, scrivono gli id ottenuti in un manifesto JSON che gli spec leggono, e cancellano per chiave esatta leggendo lo stesso manifesto. La regola «si cancella per chiave esatta di ciò che hai creato» resta, e anzi diventa più forte: si cancella esattamente ciò che è stato creato, non un intervallo di id scelto a mano.

### 4.5 Rischi

1. **L'impronta md5 di CLAUDE.md non sopravvive a una ricostruzione.**
   - `md5(string_agg(d::text …))` include `created_at` e `updated_at`, quindi ricaricare il seed la cambia anche a dati identici. Con gli id numerici cambia comunque, perché cambia l'id.
   - La regola va adattata prima di questi passi, con una decisione tua: l'unico file che questo passo può scrivere è questo, e CLAUDE.md non lo tocco.
   - Proposta: un'impronta sulle sole colonne di contenuto (nome, email, ruolo e azienda per nome, ore, costo, attivo), ordinata per email e id.
   - Anche l'impronta di `dati_prova.py:155-180` ordina per id e va rifatta.
2. **Un'impronta md5 da sola non dice cosa è cambiato.** Per il confronto prima e dopo la ricostruzione di gantt_db serve un dump ordinato dei dipendenti, cioè di persone reali. Va tenuto fuori dal repo e cancellato dopo il confronto.
3. **I dati in gantt_db non sono garantiti uguali al seed.** Se qualcuno ha modificato a mano dipendenti o configurazione in gantt_db, la ricostruzione li perde. Prima di ricostruire va fatto un confronto gantt_db contro seed.
4. **README.md:247-254 e DECISIONI.md:92 dicono altro.** Il README afferma che i dati degli utenti di prova «non sono ricostruibili» e che «niente più drop & recreate»; DECISIONI §10 dice che il database di produzione nasce da `alembic upgrade`. La baseline è coerente con DECISIONI, ma il README va corretto nello stesso passo.
5. **La finestra si chiude.** Baseline e cambio di tipo a costo zero sono possibili solo finché non esiste un database da preservare: il primo giro su Windows Server (PIANO, chiusura della fase) va fatto dopo questi passi, non prima.
6. **La sessione parallela.** Il cambio degli id tocca quasi tutti i file del backend e molti del frontend, e un'altra sessione lavora in parallelo sul repo, di recente proprio su `progetti.py` e sugli scenari e2e. Serve un periodo in cui lavora una sessione sola, oppure passi molto brevi.
7. **I `<select>` del frontend (1.3.2).** Il guasto non si vede: nessun errore, solo un confronto falso e una funzione che smette di agire (il controllo di saturazione, il titolo dell'export). Gli e2e attuali non coprono tutti quei punti.
8. **I test che prendono «il primo» record senza `order_by`.** Con un seed reinserito l'ordine fisico può cambiare, e un test può diventare rosso senza che il codice c'entri.
9. **L'autogenerate non vede tutto.** CHECK, viste, `nulls_not_distinct` e i `server_default` espressi come funzione si controllano a mano, con il confronto 4.3.2.
10. **Windows.** Lo script di ricostruzione e il confronto di schema vanno scritti in Python con pathlib, senza `psql` né bash, perché le guide e le procedure di ripristino devono girare anche sul server.

---

## 5. Sequenza di passi committabili

Ogni passo lascia l'applicazione funzionante. Le verifiche di ogni passo sono quelle di sempre (build, `npm run test:disegno`, pytest, e2e completa spec per spec, elenco degli endpoint), più quelle indicate.

| Passo | Contenuto | Verifica specifica |
|---|---|---|
| **R1 — Regola dell'impronta** | decidi tu la nuova impronta dei dipendenti, stabile alla ricostruzione (4.5.1), e il testo di CLAUDE.md; `dati_prova.py --impronta` ordinato senza dipendere dall'id | impronta identica su gantt_db prima e dopo un `seed` su `gantt_test` ricostruito due volte |
| **R2 — Script di ricostruzione** | `scripts/ricostruisci_db.py` con guardia sul nome, conferma, impronta prima e dopo; `conftest.py` usa la stessa funzione | pytest verde; lo script rifiuta un nome non ammesso; su gantt_db ricostruito l'impronta R1 è identica e la suite e2e è verde |
| **R3 — Baseline a schema invariato** | `0001_baseline.py` rivisto riga per riga, `git rm` delle 41 migration, README corretto; `test_schema_allineato.py` (confronto del catalogo baseline contro `create_all`) | confronto del catalogo catena-vecchia contro baseline vuoto (4.3.1); `alembic check` vuoto; gantt_db ricostruito con impronta identica; e2e verde |
| **R4 — Frontend indifferente al tipo** | i `<select>` di id convertono il valore (`Number(...)`, `null` per «nessuno»); niente `.trim()` su `pm_id`; il backend accetta `null` al posto di `""` per `dipendente_id` e lo restituisce | e2e verde con gli id ancora testuali; test del modulo dove applicabile; un e2e nuovo sulla modale task: scelta del responsabile, poi controllo di saturazione |
| **R5 — Fixture e2e senza id cablati** | `dati_prova.py` e gli scenari creano senza id, scrivono un manifesto e cancellano per manifesto; spec e `utenti.js` legano i dipendenti per email; addio ai `fase_id` 8 e 31 | e2e verde; impronta R1 identica prima e dopo la suite |
| **R6 — Famiglie delle attività interne** | tabella `categorie_attivita` più `progetti.categoria_id` (3.4), migration a mano, Configurazione, seed; `_famiglia` dal dato | pytest su raggruppamento e CHECK, compreso il caso nullo; e2e verde; la pagina Attività interne mostra gli stessi gruppi di prima |
| **R7 — Progetti: id numerico più `codice`** | schema, servizio, route `int`, URL, frontend, seed, `test_id_progetti.py` riscritto sul codice, `ciclo-progetto.spec.js:94` sul codice, nomi file degli export; via `ordine_progetti` e la regex | pytest, tra cui: codice generato, codice a mano, collisione → 409, maiuscole, due creazioni concorrenti; e2e verde; impronta dei dipendenti identica, perché la tabella non cambia |
| **R8 — Dipendenti: id numerico** | schema, `matricola` facoltativa se la vuoi, generatore in configurazione rimosso, `utenti` legati per id ma nel seed risolti per email | e2e verde; **l'impronta cambia**, ed è l'unico passo che lo fa: il prompt deve autorizzarlo, con l'impronta R1 di contenuto invariata |
| **R9 — Task: id numerico** | schema (comprese FK composta e vista), via `_next_task_id` e `genera_id_task_multipli`, validazione `UnitaConsuntivoIn` sul solo `tipo`, `ORDER BY ordine, id`, messaggi «task #id», `leggiErrori` del frontend allineato, snapshot `schema_version` 3 | pytest su consuntivi, task e dipendenze, compreso T1000+ (oltre mille task creati di fila); e2e verde; impronta invariata |
| **R10 — Segnalazioni e pulizia** | `segnalazioni.id` numerico; rimozione di `add_p010.py`, `diagnostico_d1.py`, `test_solidita.sh`, `riallinea` dove non serve più; ARCHITETTURA e INVENTARIO aggiornati, BACKLOG ripulito | grep senza più occorrenze di `startswith("P"/"T"/"D")`, `[1:].isdigit`, `^P[0-9]`; suite completa |

**Regole su R7–R9.**
- Fino alla prima installazione vera, i passi R7–R9 **modificano la baseline** e ricostruiscono gantt_db, invece di aggiungere migration di conversione. Non c'è nessun dato da convertire, e una migration che riscrive i tipi di una dozzina di FK sarebbe codice da rivedere riga per riga per poi buttarlo via.
- È una scelta da fissare in DECISIONI.md, con la data dalla quale smette di valere.
- Se la preferisci diversa, ogni passo porta la sua migration con le guardie della regola 10.
- L'ordine R7 → R8 → R9 va dal cambio più visibile all'utente (il codice di commessa) a quello con più riferimenti (i task: sei tabelle, una FK composta e la vista). Se prima si vuole chiudere il bloccante T1000 dell'audit, R9 può venire subito dopo R5: è indipendente da R7 e R8.

---

## Cosa questa ricognizione non ha verificato

- Lo stato reale di gantt_db: id presenti, nomi effettivi dei vincoli, se diverge dal seed.
- Che `alembic check` sia oggi vuoto su gantt_db.
- Che il confronto del catalogo con due schemi in `gantt_test` sia praticabile con i permessi di `vicacrit`.
- Il comportamento a runtime di ogni punto del frontend con id numerici: è dedotto dalla lettura del codice.
- I numeri di riga valgono al commit `61e69af`: i passi successivi li spostano.
